/**
 * The conversation state machine.
 *
 * No React, no DOM, no side effects — every function here is pure and takes a
 * state in and returns a new state, so the whole flow can be exercised from a
 * test file without rendering anything.
 *
 * All conversation content lives in script.ts. This module only moves through
 * it. Nothing here persists, transmits or logs an answer: answers exist solely
 * inside the returned state object, which the UI holds in React state.
 */
import {
  FIRST_STEP,
  byId,
  script,
  type Line,
  type Option,
  type Step,
} from './script.ts'
import type { Channel } from '../theme'

export type Sender = 'bot' | 'worker'

export type SummaryRow = { label: string; value: string }

export type Message =
  | { id: string; from: Sender; kind: 'text'; text: string; sample?: boolean }
  | { id: string; from: 'worker'; kind: 'file'; name: string; url: string; isImage: boolean }
  | { id: string; from: 'bot'; kind: 'summary'; rows: SummaryRow[] }

export type Answer = {
  /** What the worker chose or typed, as shown in their own bubble. */
  label: string
  optionId?: string
  skipped: boolean
}

/**
 * Everything about a conversation except its undo stack. Snapshots of this
 * are what "Back" restores.
 */
export type Core = {
  /** Step the conversation is sitting on, or null once it has run out. */
  cursor: string | null
  /** Bot lines waiting to be emitted, one per typing-indicator beat. */
  queue: Line[]
  messages: Message[]
  answers: Record<string, Answer>
  /**
   * Files the worker chose to attach, as in-memory object URLs.
   *
   * These exist for one reason: shaping this worker's own alerts. They are
   * never aggregated and never leave this object — the admin path has no
   * import that can reach it. The UI owns revoking the URLs on reset.
   */
  attachments: Attachment[]
  /**
   * The health-app connection, once granted. Like the attachments, this feeds
   * the worker's own alerts only and has no path to the admin views.
   */
  connection: Connection | null
  /** Option id of the provider whose consent sheet is open, if any. */
  connecting: string | null
  /** The filed complaint, if the worker made one. */
  report: Report | null
  /** True while the complaint form is open over the thread. */
  reporting: boolean
  /**
   * Which messaging channel this conversation is running in.
   *
   * Only the health-app step reads it: the channel implies the platform, so
   * an iMessage thread is not offered an Android-only provider.
   */
  channel: Channel
  /** Monotonic counter for message keys. */
  seq: number
}

export type State = Core & {
  /**
   * Snapshots taken immediately before each recorded answer, oldest first.
   *
   * A mistapped quick reply is otherwise permanent: the thread is append-only
   * and there is no way to unsay something. Each snapshot is the exact state
   * the worker was in when the question was on screen and unanswered, so
   * restoring one puts the question back and drops everything said since.
   */
  history: Core[]
}

export type Attachment = { name: string; url: string; isImage: boolean }

/** A granted health-app connection. Scopes are the types actually allowed. */
export type Connection = { provider: string; scopes: string[] }

/**
 * A filed station complaint.
 *
 * The only object in this machine meant to leave the worker's device. It
 * carries where and what, and deliberately nothing about the person: no
 * health answer, no attachment, no health-app reading can reach it, because
 * none of them is in this shape.
 */
export type Report = { station: string; detail: string }

export type Phase = 'thinking' | 'awaiting' | 'connecting' | 'reporting' | 'done'

/** What the composer should offer while the machine waits for the worker. */
export type InputMode = 'choice' | 'text' | 'attach' | 'connect' | 'report' | 'none'

const SKIP_LABEL = 'Skip'

export function createState(channel: Channel = 'whatsapp'): State {
  const { cursor, lines } = collect(FIRST_STEP, channel)
  return {
    cursor,
    queue: lines,
    messages: [],
    answers: {},
    attachments: [],
    connection: null,
    connecting: null,
    report: null,
    reporting: false,
    channel,
    seq: 0,
    history: [],
  }
}

function coreOf({ history: _history, ...core }: State): Core {
  return core
}

/**
 * Take a snapshot before an answer is recorded.
 *
 * `at` lets a caller snapshot a slightly different state than the current one
 * — used by the sheets, so Back reopens the step rather than the sheet.
 */
function remember(state: State, at: Partial<Core> = {}): State {
  return { ...state, ...at, history: [...state.history, coreOf({ ...state, ...at })] }
}

/** True when there is an answer to take back and it is safe to do so. */
export function canGoBack(state: State): boolean {
  const phase = phaseOf(state)
  return state.history.length > 0 && (phase === 'awaiting' || phase === 'done')
}

/**
 * Undo the last recorded answer.
 *
 * The worker's reply and everything the bot said after it are removed from
 * the transcript, and the question is live again. Repeating walks further
 * back, one answer at a time.
 */
export function goBack(state: State): State {
  if (!canGoBack(state)) return state
  const history = [...state.history]
  const previous = history.pop()
  if (!previous) return state
  return { ...previous, history }
}

/**
 * Walk forward from `startId`, gathering every line the bot should say before
 * it next needs input. `say` steps fall through; anything else stops the walk.
 */
/** The lines a step says on a given channel. */
export function linesFor(step: Step, channel: Channel): Line[] {
  return step.byChannel?.[channel]?.lines ?? step.lines
}

/** The options a step offers on a given channel. */
export function optionsFor(step: Step, channel: Channel): Option[] {
  const override = step.byChannel?.[channel]?.options
  if (override) return override
  return 'options' in step ? step.options : []
}

function collect(startId: string, channel: Channel): { cursor: string; lines: Line[] } {
  const lines: Line[] = []
  let id = startId
  // The script is a finite graph; the bound is belt-and-braces against a
  // mis-edited `next` pointing backwards.
  for (let hops = 0; hops <= script.length; hops++) {
    const step = byId[id]
    if (!step) break
    lines.push(...linesFor(step, channel))
    if (step.kind === 'say' && step.next) {
      id = step.next
      continue
    }
    return { cursor: id, lines }
  }
  return { cursor: id, lines }
}

export function currentStep(state: State): Step | null {
  return state.cursor ? (byId[state.cursor] ?? null) : null
}

export function phaseOf(state: State): Phase {
  if (state.queue.length > 0) return 'thinking'
  if (state.connecting) return 'connecting'
  if (state.reporting) return 'reporting'
  const step = currentStep(state)
  if (!step || step.kind === 'done') return 'done'
  return 'awaiting'
}

export function inputMode(state: State): InputMode {
  if (phaseOf(state) !== 'awaiting') return 'none'
  const step = currentStep(state)
  switch (step?.kind) {
    case 'choice':
      return 'choice'
    case 'text':
      return 'text'
    case 'attach':
      return 'attach'
    case 'connect':
      return 'connect'
    case 'report':
      return 'report'
    default:
      return 'none'
  }
}

/** True when the current step offers a skip. Questions are never pressed. */
export function canSkip(state: State): boolean {
  return phaseOf(state) === 'awaiting' && Boolean(currentStep(state)?.allowSkip)
}

/**
 * Emit the next queued bot line. The UI calls this once per typing beat, so
 * the delay lives in the component and the ordering lives here.
 */
export function tick(state: State): State {
  if (state.queue.length === 0) return state
  const [line, ...rest] = state.queue
  const seq = state.seq + 1
  return {
    ...state,
    seq,
    queue: rest,
    messages: [...state.messages, toMessage(line, seq, state)],
  }
}

function toMessage(line: Line, seq: number, state: State): Message {
  const id = `m${seq}`
  if (typeof line === 'string') return { id, from: 'bot', kind: 'text', text: line }
  if ('special' in line) {
    return { id, from: 'bot', kind: 'summary', rows: summaryRows(state) }
  }
  return { id, from: 'bot', kind: 'text', text: line.text, sample: line.sample }
}

/** Omit that distributes over the Message union instead of collapsing it. */
type Unsent<T> = T extends unknown ? Omit<T, 'id'> : never

function say(state: State, message: Unsent<Message>): State {
  const seq = state.seq + 1
  return {
    ...state,
    seq,
    messages: [...state.messages, { ...message, id: `m${seq}` } as Message],
  }
}

/** Where the conversation goes after `step`, given how it was answered. */
function nextAfter(step: Step, optionId: string | undefined, skipped: boolean): string | null {
  if (skipped) return step.skipTo ?? step.next ?? null
  if (optionId && step.branch?.[optionId]) return step.branch[optionId]
  return step.next ?? null
}

function advance(state: State, step: Step, optionId?: string, skipped = false): State {
  const target = nextAfter(step, optionId, skipped)
  const queue: Line[] = []
  // A neutral acknowledgement, never an interpretation of what was said — and
  // never a claim that something happened when the step was skipped.
  const ack = skipped ? (step.skipAck ?? step.ack) : step.ack
  if (ack) queue.push(ack)
  if (!target) return { ...state, cursor: null, queue }
  const { cursor, lines } = collect(target, state.channel)
  return { ...state, cursor, queue: [...queue, ...lines] }
}

/** Record a quick-reply choice. */
export function chooseOption(state: State, optionId: string): State {
  const step = currentStep(state)
  if (!step || phaseOf(state) !== 'awaiting') return state
  if (step.kind !== 'choice' && step.kind !== 'connect') return state

  const option = optionsFor(step, state.channel).find((o) => o.id === optionId)
  if (!option) return state

  // Picking a provider opens its consent sheet. Nothing is granted until the
  // worker allows specific data types there.
  if (step.kind === 'connect') {
    return { ...state, connecting: option.id }
  }

  const withReply = say(remember(state), { from: 'worker', kind: 'text', text: option.label })
  const recorded: State = {
    ...withReply,
    answers: {
      ...withReply.answers,
      [step.id]: { label: option.label, optionId, skipped: false },
    },
  }
  return advance(recorded, step, optionId)
}

/** Record a free-text answer. Empty input is treated as a skip, never refused. */
export function answerText(state: State, text: string): State {
  const step = currentStep(state)
  if (!step || step.kind !== 'text' || phaseOf(state) !== 'awaiting') return state
  const trimmed = text.trim()
  if (!trimmed) return skip(state)

  const withReply = say(remember(state), { from: 'worker', kind: 'text', text: trimmed })
  const recorded: State = {
    ...withReply,
    answers: {
      ...withReply.answers,
      [step.id]: { label: trimmed, skipped: false },
    },
  }
  return advance(recorded, step)
}

/** Decline a question. The bot moves on without comment or follow-up. */
export function skip(state: State): State {
  const step = currentStep(state)
  if (!step || !step.allowSkip || phaseOf(state) !== 'awaiting') return state
  const withReply = say(remember(state), { from: 'worker', kind: 'text', text: SKIP_LABEL })
  const recorded: State = {
    ...withReply,
    answers: { ...withReply.answers, [step.id]: { label: 'Skipped', skipped: true } },
  }
  return advance(recorded, step, undefined, true)
}

/**
 * Attach a medical document.
 *
 * Nothing is read, parsed, interpreted or transmitted — the file is shown back
 * as an acknowledgement and held as an object URL for the life of the tab. The
 * bot never comments on the contents, exactly as it never comments on a health
 * answer.
 */
export function attachFile(state: State, file: Attachment): State {
  const step = currentStep(state)
  if (!step || step.kind !== 'attach' || phaseOf(state) !== 'awaiting') return state

  const withFile = say(
    { ...remember(state), attachments: [...state.attachments, file] },
    { from: 'worker', kind: 'file', name: file.name, url: file.url, isImage: file.isImage },
  )
  const recorded: State = {
    ...withFile,
    answers: {
      ...withFile.answers,
      [step.id]: { label: `${file.name} · stays on your phone`, skipped: false },
    },
  }
  return advance(recorded, step)
}

/** Open the complaint form. Nothing is filed by opening it. */
export function beginReport(state: State): State {
  const step = currentStep(state)
  if (!step || step.kind !== 'report' || phaseOf(state) !== 'awaiting') return state
  return { ...state, reporting: true }
}

/** Abandon the complaint form. The step stands and nothing is filed. */
export function cancelReport(state: State): State {
  return { ...state, reporting: false }
}

/**
 * File the complaint.
 *
 * `station` comes from the agency's roster rather than anything the worker
 * typed, so the record is exactly two things: where, and what they wrote.
 * There is no path by which a health answer, an attachment or a health-app
 * reading joins it.
 */
export function submitReport(state: State, text: string, station: string): State {
  const step = currentStep(state)
  if (!step || step.kind !== 'report' || !state.reporting) return state

  const detail = text.trim()
  if (!detail) return state

  const report: Report = { station, detail }
  const filed: State = { ...remember(state, { reporting: false }), report, reporting: false }
  const withReply = say(filed, { from: 'worker', kind: 'text', text: detail })
  const recorded: State = {
    ...withReply,
    answers: {
      ...withReply.answers,
      [step.id]: { label: detail, skipped: false },
    },
  }
  return advance(recorded, step)
}

/** Back out of the consent sheet. Nothing is granted and the step stands. */
export function dismissConnection(state: State): State {
  return { ...state, connecting: null }
}

/**
 * Grant a health-app connection, limited to the data types the worker ticked.
 *
 * No health data is actually read: there is no HealthKit or CommonHealth
 * bridge in a browser, and this demo makes no network calls. What is recorded
 * is the grant itself — which provider, which scopes — and nothing else.
 */
export function approveConnection(state: State, scopes: string[]): State {
  const step = currentStep(state)
  if (!step || step.kind !== 'connect' || !state.connecting) return state
  if (scopes.length === 0) return state

  const provider =
    optionsFor(step, state.channel).find((o) => o.id === state.connecting)?.label ??
    state.connecting
  const granted: State = {
    ...remember(state, { connecting: null }),
    connection: { provider, scopes },
    connecting: null,
  }
  const withReply = say(granted, {
    from: 'worker',
    kind: 'text',
    text: `Connected ${provider}`,
  })
  const recorded: State = {
    ...withReply,
    answers: {
      ...withReply.answers,
      [step.id]: {
        label: `${provider} · ${scopes.length} of ${step.scopes.length} types`,
        skipped: false,
      },
    },
  }
  return advance(recorded, step)
}

/**
 * Fresh conversation on the same channel.
 *
 * The caller must revoke the object URLs of `attachments` first — this
 * function cannot, because it is pure.
 */
export function reset(channel: Channel): State {
  return createState(channel)
}

/** Stage E summary, assembled from whatever the worker actually answered. */
export function summaryRows(state: State): SummaryRow[] {
  const rows: SummaryRow[] = []
  for (const step of script) {
    if (!step.summaryLabel) continue
    const answer = state.answers[step.id]
    if (!answer) continue
    rows.push({ label: step.summaryLabel, value: answer.label })
  }
  // Role and station are standing context at the top of the screen, not
  // something the worker shared, so they are not repeated here.
  return rows
}
