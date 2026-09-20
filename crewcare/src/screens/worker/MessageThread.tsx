import { useEffect, useRef, useState } from 'react'

import { Bubble } from '../../components/Bubble'
import { DataNotice } from '../../components/DataNotice'
import { ASSIGNMENT_ON_FILE } from '../../data/assignment'
import { ProviderMark } from '../../components/ProviderMark'
import { Sheet } from '../../components/Sheet'
import { QuickReplies } from '../../components/QuickReplies'
import { ThreadMeta } from '../../components/ThreadMeta'
import { TypingIndicator } from '../../components/TypingIndicator'
import {
  answerText,
  approveConnection,
  attachFile,
  beginReport,
  canGoBack,
  cancelReport,
  dismissConnection,
  goBack,
  canSkip,
  chooseOption,
  createState,
  currentStep,
  inputMode,
  optionsFor,
  phaseOf,
  skip,
  submitReport,
  tick,
  type State,
} from '../../conversation/machine'
import { channels, type Channel } from '../../theme'

/** Typing beat before each bot message. */
const TYPING_MIN = 600
const TYPING_MAX = 1000

const DONE_FOOTER = 'Demo build. Exposure values are modeled estimates, not measurements.'

/**
 * The simulated thread.
 *
 * All conversation logic lives in the machine; this component only paints it,
 * paces the typing indicator and collects input. Answers live in this
 * component's React state and nowhere else — no storage, no network, no
 * console. Nothing here is logged.
 *
 * The worker's role and station are not asked for or confirmed here. They are
 * the agency's record, so they sit in the chrome as standing context.
 *
 * Medical documents the worker chooses to attach are held as object URLs for
 * the life of this component and revoked on restart and unmount. They are
 * never read, never transmitted, and exist only to shape this worker's own
 * alerts — the admin path cannot import this state.
 *
 * The health-app connection is simulated end to end. There is no HealthKit or
 * CommonHealth bridge in a browser; the consent sheet records which data types
 * the worker granted and reads nothing.
 */
export function MessageThread({
  channel,
  onSignOut,
}: {
  channel: Channel
  onSignOut: () => void
}) {
  const theme = channels[channel]
  const [state, setState] = useState<State>(() => createState(channel))
  const [draft, setDraft] = useState('')

  const scrollRef = useRef<HTMLDivElement>(null)
  // Object URLs for attached documents, revoked on restart and unmount.
  const objectUrls = useRef<string[]>([])

  const phase = phaseOf(state)
  const step = currentStep(state)
  const mode = inputMode(state)

  // One typing beat per queued bot line.
  useEffect(() => {
    if (phase !== 'thinking') return
    const delay = TYPING_MIN + Math.random() * (TYPING_MAX - TYPING_MIN)
    const timer = setTimeout(() => setState(tick), delay)
    return () => clearTimeout(timer)
  }, [state, phase])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [state.messages.length, phase])

  // Undo can drop an attachment out of state. Anything no longer referenced is
  // released here, so a taken-back file does not linger in memory.
  useEffect(() => {
    const live = new Set(state.attachments.map((a) => a.url))
    objectUrls.current = objectUrls.current.filter((url) => {
      if (live.has(url)) return true
      URL.revokeObjectURL(url)
      return false
    })
  }, [state.attachments])

  function releaseObjectUrls() {
    for (const url of objectUrls.current) URL.revokeObjectURL(url)
    objectUrls.current = []
  }

  useEffect(() => releaseObjectUrls, [])

  function restart() {
    releaseObjectUrls()
    setDraft('')
    setState(createState(channel))
  }

  function handleFile(file: File | undefined) {
    if (!file) return
    const url = URL.createObjectURL(file)
    objectUrls.current.push(url)
    setState((s) =>
      attachFile(s, { name: file.name, url, isImage: file.type.startsWith('image/') }),
    )
  }

  return (
    <div
      className="flex min-h-0 flex-1 flex-col"
      style={{ background: theme.canvas, fontFamily: theme.font, letterSpacing: theme.tracking }}
    >
      <Header theme={theme} onSignOut={onSignOut} onRestart={restart} />

      <ThreadMeta />

      <div className="border-b border-black/5 bg-white/75 px-4 py-2 backdrop-blur">
        <DataNotice variant="worker" />
      </div>

      <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3.5 py-4">
        {state.messages.map((message) => (
          <Bubble key={message.id} message={message} theme={theme} />
        ))}
        {phase === 'thinking' && <TypingIndicator theme={theme} />}
      </div>

      <div
        className="border-t border-black/8 px-3.5 py-3"
        style={{ background: theme.composerBg }}
      >
        {canGoBack(state) && (
          <div className="flex pb-2">
            <button
              type="button"
              onClick={() => setState(goBack)}
              className="flex items-center gap-1.5 text-[13px] font-semibold text-cc-grey"
            >
              <svg viewBox="0 0 14 12" aria-hidden="true" className="h-3 w-3.5 fill-none stroke-current stroke-[1.6]">
                <path d="M13 9.5C13 6 10.5 4.5 7 4.5H2M5 1 1.5 4.5 5 8" />
              </svg>
              Back
            </button>
          </div>
        )}

        {mode === 'choice' && step?.kind === 'choice' && (
          <QuickReplies
            theme={theme}
            replies={step.options}
            onPick={(id) => setState((s) => chooseOption(s, id))}
            onSkip={canSkip(state) ? () => setState(skip) : undefined}
            skipLabel={step.skipLabel}
          />
        )}

        {mode === 'connect' && step?.kind === 'connect' && (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              {optionsFor(step, channel).map((provider) => (
                <button
                  key={provider.id}
                  type="button"
                  onClick={() => setState((s) => chooseOption(s, provider.id))}
                  className="flex flex-1 items-center justify-center gap-2 rounded-full border border-black/12 bg-white px-3 py-2.5 text-[14px] font-semibold text-cc-primary transition active:scale-[0.98]"
                >
                  <ProviderMark provider={provider.id} size={22} />
                  <span className="truncate">{provider.label}</span>
                </button>
              ))}
            </div>
            {canSkip(state) && (
              <button
                type="button"
                onClick={() => setState(skip)}
                className="self-end text-[13px] font-semibold text-cc-grey underline decoration-cc-grey/40 underline-offset-2"
              >
                {step.skipLabel ?? 'Skip'}
              </button>
            )}
          </div>
        )}

        {mode === 'text' && step?.kind === 'text' && (
          <div className="flex flex-col gap-2">
            <form
              className="flex items-center gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                setState((s) => answerText(s, draft))
                setDraft('')
              }}
            >
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={step.placeholder}
                autoFocus
                className="min-w-0 flex-1 rounded-full border border-black/12 bg-white px-4 py-2.5 text-[15px] text-cc-primary outline-none focus:border-cc-accent"
              />
              <button
                type="submit"
                aria-label="Send"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                style={{ background: theme.outgoingBg }}
              >
                <svg viewBox="0 0 16 16" className="h-4 w-4 fill-none stroke-2" style={{ stroke: theme.outgoingFg }}>
                  <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
                </svg>
              </button>
            </form>
            {canSkip(state) && (
              <button
                type="button"
                onClick={() => setState(skip)}
                className="self-end text-[13px] font-semibold text-cc-grey underline decoration-cc-grey/40 underline-offset-2"
              >
                Skip this question
              </button>
            )}
          </div>
        )}

        {mode === 'attach' && step?.kind === 'attach' && (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <label className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-full border border-black/12 bg-white px-3 py-2.5 text-[14px] font-semibold text-cc-primary">
                <svg viewBox="0 0 16 18" className="h-4 w-3.5 fill-none stroke-current stroke-[1.3]">
                  <path d="M2 1.5h7L14 6v10.5H2z" />
                  <path d="M9 1.5V6h5" />
                </svg>
                Attach a file
                <input
                  type="file"
                  accept={step.accept}
                  className="hidden"
                  onChange={(event) => handleFile(event.target.files?.[0])}
                />
              </label>
            </div>
            {canSkip(state) && (
              <button
                type="button"
                onClick={() => setState(skip)}
                className="self-end text-[13px] font-semibold text-cc-grey underline decoration-cc-grey/40 underline-offset-2"
              >
                No thanks, skip this
              </button>
            )}
          </div>
        )}

        {mode === 'report' && step?.kind === 'report' && (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => setState(beginReport)}
              className="w-full rounded-full bg-cc-primary px-4 py-3 text-[15px] font-bold text-white transition active:scale-[0.99]"
            >
              {step.actionLabel}
            </button>
            {canSkip(state) && (
              <button
                type="button"
                onClick={() => setState(skip)}
                className="self-end text-[13px] font-semibold text-cc-grey underline decoration-cc-grey/40 underline-offset-2"
              >
                {step.skipLabel ?? 'Skip'}
              </button>
            )}
          </div>
        )}

        {phase === 'done' && (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={restart}
              className="w-full rounded-full bg-cc-accent px-4 py-3 text-[15px] font-bold text-white"
            >
              Start over
            </button>
            <p className="text-center text-[12px] text-cc-grey">{DONE_FOOTER}</p>
          </div>
        )}

        {phase === 'thinking' && (
          <p className="py-1 text-center text-[12px] text-cc-grey">CrewCare is typing…</p>
        )}
      </div>

      {phase === 'reporting' && step?.kind === 'report' && (
        <ReportSheet
          placeholder={step.placeholder}
          onCancel={() => setState(cancelReport)}
          onSubmit={(text) =>
            setState((s) => submitReport(s, text, ASSIGNMENT_ON_FILE.station))
          }
        />
      )}

      {phase === 'connecting' && step?.kind === 'connect' && state.connecting && (
        <ConsentSheet
          provider={state.connecting}
          providerLabel={
            optionsFor(step, channel).find((o) => o.id === state.connecting)?.label ?? ''
          }
          scopes={step.scopes}
          onCancel={() => setState(dismissConnection)}
          onAllow={(granted) => setState((s) => approveConnection(s, granted))}
        />
      )}

    </div>
  )
}

function Header({
  theme,
  onSignOut,
  onRestart,
}: {
  theme: (typeof channels)[Channel]
  onSignOut: () => void
  onRestart: () => void
}) {
  return (
    <div
      className="relative z-10 flex items-center justify-between gap-2 border-b px-3 pt-[48px] pb-2.5"
      style={{ background: theme.headerBg, borderColor: theme.headerBorder, color: theme.headerFg }}
    >
      <button
        type="button"
        onClick={onSignOut}
        className="flex shrink-0 items-center gap-1 text-[13px] font-semibold opacity-80"
      >
        <svg viewBox="0 0 8 14" className="h-3 w-2 fill-none stroke-current stroke-2">
          <path d="M7 1 1 7l6 6" />
        </svg>
        Exit
      </button>
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-[15px] font-bold">CrewCare</span>
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-bold tracking-widest uppercase"
          style={{ background: theme.chipBg, color: theme.chipFg }}
        >
          demo
        </span>
      </div>
      <button
        type="button"
        onClick={onRestart}
        className="shrink-0 text-[13px] font-semibold opacity-80"
      >
        Start over
      </button>
    </div>
  )
}

/**
 * The station complaint box.
 *
 * One field. The station and the date ride along from the roster and the
 * clock, so the only thing asked of the worker is the sentence that nobody
 * else can write. A category picker would be asking them to do the filing
 * system's job at the end of a shift.
 *
 * The footer states what travels with it, because this is the one thing here
 * that is meant to be sent.
 */
function ReportSheet({
  placeholder,
  onCancel,
  onSubmit,
}: {
  placeholder: string
  onCancel: () => void
  onSubmit: (text: string) => void
}) {
  const [text, setText] = useState('')

  return (
    <Sheet label="Report a problem" onDismiss={onCancel}>
      <div className="flex items-center justify-between border-b border-black/5 px-4 py-3">
        <p className="text-[15px] font-bold text-cc-primary">Report a problem</p>
        <button type="button" onClick={onCancel} className="text-[14px] font-semibold text-cc-grey">
          Cancel
        </button>
      </div>

      <form
        className="flex min-h-0 flex-1 flex-col"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit(text)
        }}
      >
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <label className="block">
            <span className="sr-only">What's going on?</span>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={5}
              autoFocus
              placeholder={placeholder}
              className="w-full resize-none rounded-lg border border-cc-grey/30 px-3 py-2.5 text-[15px] text-cc-primary outline-none focus:border-cc-accent"
            />
          </label>
        </div>

        <div className="border-t border-black/5 p-3">
          <p className="pb-2.5 text-center text-[12px] leading-snug text-cc-grey">
            Sends the station, the date and what you wrote. Nothing about your health.
          </p>
          <button
            type="submit"
            disabled={!text.trim()}
            className="w-full rounded-full bg-cc-primary px-4 py-3 text-[15px] font-bold text-white disabled:opacity-40"
          >
            File it
          </button>
        </div>
      </form>
    </Sheet>
  )
}

/**
 * The health-app consent sheet.
 *
 * Modelled on the platform's own permission flow: every data type is listed
 * and granted individually, defaulting to on but each one refusable, and
 * nothing at all is granted until Allow is pressed. Turning everything off
 * disables Allow rather than silently granting an empty connection.
 */
function ConsentSheet({
  provider,
  providerLabel,
  scopes,
  onCancel,
  onAllow,
}: {
  provider: string
  providerLabel: string
  scopes: string[]
  onCancel: () => void
  onAllow: (granted: string[]) => void
}) {
  const [granted, setGranted] = useState<string[]>(scopes)

  function toggle(scope: string) {
    setGranted((current) =>
      current.includes(scope) ? current.filter((s) => s !== scope) : [...current, scope],
    )
  }

  return (
    <Sheet label={`Connect ${providerLabel}`} onDismiss={onCancel} inset={90}>
      <div className="flex items-start gap-3 border-b border-black/5 px-4 py-3.5">
        <ProviderMark provider={provider} size={34} />
        <div className="min-w-0">
          <p className="text-[15px] font-bold text-cc-primary">{providerLabel}</p>
          <p className="pt-0.5 text-[13px] text-cc-grey">
            CrewCare wants to read the following. Turn off anything you’d rather keep.
          </p>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-2">
        {scopes.map((scope) => {
          const on = granted.includes(scope)
          return (
            <label
              key={scope}
              className="flex cursor-pointer items-center justify-between gap-3 border-b border-black/5 py-3 last:border-0"
            >
              <span className="text-[15px] font-semibold text-cc-primary">{scope}</span>
              <input
                type="checkbox"
                checked={on}
                onChange={() => toggle(scope)}
                className="sr-only"
              />
              <span
                aria-hidden="true"
                className="relative h-[26px] w-[44px] shrink-0 rounded-full transition"
                style={{ background: on ? '#0062CF' : '#C7CBD1' }}
              >
                <span
                  className="absolute top-[3px] block h-5 w-5 rounded-full bg-white transition-all"
                  style={{ left: on ? 21 : 3 }}
                />
              </span>
            </label>
          )
        })}
      </div>

      <div className="border-t border-black/5 p-3">
        <p className="pb-2.5 text-center text-[12px] leading-snug text-cc-grey">
          Used only for your alerts. You can disconnect in {providerLabel} any time.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-full border border-cc-grey/40 px-4 py-3 text-[15px] font-semibold text-cc-grey"
          >
            Not now
          </button>
          <button
            type="button"
            disabled={granted.length === 0}
            onClick={() => onAllow(granted)}
            className="flex-1 rounded-full bg-cc-primary px-4 py-3 text-[15px] font-bold text-white disabled:opacity-40"
          >
            Allow
          </button>
        </div>
      </div>
    </Sheet>
  )
}
