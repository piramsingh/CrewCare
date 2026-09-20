import type { Channel } from '../theme'

/**
 * The CrewCare conversation, as data.
 *
 * This file is purely declarative: questions, option sets, acknowledgements
 * and branching. It contains no logic and imports nothing. Questions can be
 * reworded or reordered here without touching machine.ts.
 *
 * Question wording and option sets in Stage B are verbatim from the intake
 * instrument and must not be paraphrased.
 */

/** A single bot utterance. Strings are plain text; objects carry a rendering hint. */
export type Line =
  | string
  | { text: string; sample?: true }
  | { special: 'summary' }

export type Option = {
  id: string
  label: string
}

type Base = {
  id: string
  /** Bot messages emitted when the step is entered, one bubble each. */
  lines: Line[]
  /** Neutral acknowledgement emitted after the worker answers. */
  ack?: string
  /**
   * Acknowledgement used when the step is SKIPPED instead of answered.
   *
   * Required wherever `ack` describes something that happened ("Filed.",
   * "Connected."), because skipping means it did not. Steps whose ack is
   * already neutral ("Got it.") need no override.
   */
  skipAck?: string
  /** Step entered after an answer, unless `branch` overrides for that option. */
  next?: string
  /** Per-option overrides of `next`. */
  branch?: Record<string, string>
  /** Adds a Skip chip. Skipping follows `skipTo` if set, otherwise `next`. */
  allowSkip?: boolean
  /** Wording of the skip chip, when "Skip" is too blunt for the step. */
  skipLabel?: string
  skipTo?: string
  /** Label under which the answer appears in the Stage E summary. */
  summaryLabel?: string
  /**
   * Per-channel overrides of `lines` and `options`.
   *
   * The conversation is otherwise identical across channels. The one place
   * it diverges is the health-app step, because the channel tells you the
   * platform: an iMessage thread means an iPhone, so offering CommonHealth
   * (Android) there would be offering something that cannot work.
   */
  byChannel?: Partial<Record<Channel, { lines?: Line[]; options?: Option[] }>>
}

export type Step =
  /** Bot talks, then falls through to `next` with no input. */
  | (Base & { kind: 'say' })
  /** Quick-reply chips. */
  | (Base & { kind: 'choice'; options: Option[] })
  /** Free text input. */
  | (Base & { kind: 'text'; placeholder: string })
  /** Optional file attachment (PDF or image). Always skippable. */
  | (Base & { kind: 'attach'; accept: string })
  /**
   * Optional health-app connection. Picking a provider opens a consent sheet
   * listing the data types; the worker grants them individually.
   */
  | (Base & { kind: 'connect'; options: Option[]; scopes: string[] })
  /**
   * Optional station complaint. The action opens a box to describe the
   * problem in the worker's own words — no categories to pick through.
   */
  | (Base & { kind: 'report'; actionLabel: string; placeholder: string })
  /** Terminal step. */
  | (Base & { kind: 'done' })

/** The exact disclosure required before any health question is asked. */
export const DISCLOSURE =
  'Your answers stay on your device for this demo. CrewCare is not a medical service and does not give medical advice.'

export const FIRST_STEP = 'intro'

export const script: Step[] = [
  // ── Stage A — Intro ────────────────────────────────────────────────────
  {
    id: 'intro',
    kind: 'choice',
    lines: [
      'Hey — this is CrewCare, from your local.',
      'It asks a few short questions about your health and your pick, then estimates how much airborne exposure your tours carry compared with the rest of the system.',
      DISCLOSURE,
    ],
    options: [
      { id: 'start', label: 'Get started' },
      { id: 'about', label: 'What is this?' },
    ],
    branch: { about: 'about' },
    next: 'q1',
  },
  {
    id: 'about',
    kind: 'choice',
    lines: [
      'CrewCare is a prototype built for transit workers. Nothing here is sent anywhere — no server, no account, no record.',
      'Your local sees exposure totals by line and tour only, never anything you say about your health.',
      'Takes about a minute.',
    ],
    options: [{ id: 'start', label: 'Get started' }],
    next: 'q1',
  },

  // ── Stage B — Health intake (verbatim) ─────────────────────────────────
  {
    id: 'q1',
    kind: 'choice',
    lines: ['How would you describe your overall health?'],
    options: [
      { id: 'excellent', label: 'Excellent' },
      { id: 'very-good', label: 'Very good' },
      { id: 'good', label: 'Good' },
      { id: 'fair', label: 'Fair' },
      { id: 'poor', label: 'Poor' },
      { id: 'prefer-not', label: 'Prefer not to say' },
    ],
    ack: 'Got it.',
    next: 'q2',
    allowSkip: true,
    summaryLabel: 'Overall health',
  },
  {
    id: 'q2',
    kind: 'choice',
    lines: [
      'Are you currently experiencing any health problems or symptoms that concern you?',
    ],
    options: [
      { id: 'yes', label: 'Yes' },
      { id: 'no', label: 'No' },
      { id: 'not-sure', label: 'Not sure' },
      { id: 'prefer-not', label: 'Prefer not to say' },
    ],
    ack: 'Got it.',
    // Yes and Not sure continue into Q3. No and Prefer not to say skip to
    // Stage C — the worker is never asked to elaborate on a "no".
    next: 'q3',
    branch: { no: 'medical', 'prefer-not': 'medical' },
    allowSkip: true,
    // Declining to answer is treated the same as declining to elaborate.
    skipTo: 'medical',
    summaryLabel: 'Current concern',
  },
  {
    id: 'q3',
    kind: 'text',
    lines: ['What is the main health problem or symptom you are experiencing?'],
    placeholder: 'Type your answer',
    ack: 'Got it.',
    next: 'q4',
    allowSkip: true,
    summaryLabel: 'Main problem',
  },
  {
    id: 'q4',
    kind: 'choice',
    lines: ['How long has the problem lasted?'],
    options: [
      { id: 'lt-1-day', label: 'Less than 1 day' },
      { id: '1-3-days', label: '1–3 days' },
      { id: 'lt-1-week', label: 'Less than 1 week' },
      { id: '1-4-weeks', label: '1–4 weeks' },
      { id: '1-3-months', label: '1–3 months' },
      { id: 'gt-3-months', label: 'More than 3 months' },
      { id: 'not-sure', label: 'Not sure' },
    ],
    ack: 'Got it.',
    next: 'q5',
    allowSkip: true,
    summaryLabel: 'Duration',
  },
  {
    id: 'q5',
    kind: 'choice',
    lines: ['Is the problem always present, or does it come and go?'],
    options: [
      { id: 'always', label: 'Always present' },
      { id: 'comes-and-goes', label: 'Comes and goes' },
      { id: 'during-work', label: 'Happens mainly during work' },
      { id: 'after-work', label: 'Happens mainly after work' },
      { id: 'occasionally', label: 'Happens occasionally' },
      { id: 'not-sure', label: 'Not sure' },
    ],
    ack: 'Got it.',
    next: 'medical',
    allowSkip: true,
    summaryLabel: 'Pattern',
  },

  // ── Stage C2 — Optional medical records ────────────────────────────────
  //
  // Anything attached here is used for one purpose only: shaping the alerts
  // this worker receives. It is never aggregated, never reported, and has no
  // path to the administrator dashboard — see data/mockExposure.ts.
  {
    id: 'medical',
    kind: 'attach',
    accept: 'image/*,application/pdf',
    lines: [
      'Anything from a doctor you want me to know about?',
      'A note or test results. PDF or photo, either works.',
      'It stays on your phone and only affects what I text you. Nobody else sees it.',
    ],
    ack: 'Got it. That stays on your phone.',
    skipAck: 'No problem.',
    next: 'health_app',
    allowSkip: true,
    summaryLabel: 'Medical records',
  },

  // ── Stage C3 — Optional health-app connection ──────────────────────────
  //
  // The deepest tier of sharing, and the most guarded: the worker picks the
  // provider, then grants each data type individually in a consent sheet
  // modelled on the platform's own. Nothing read here is aggregated and none
  // of it reaches the administrator dashboard.
  //
  // PRODUCTION NOTE: neither provider is reachable from a web page or from a
  // messaging thread. Apple Health requires a native iOS app using HealthKit,
  // and CommonHealth requires its Android SDK. In a real build this step hands
  // off to a companion app and comes back; here it is simulated end to end.
  {
    id: 'health_app',
    kind: 'connect',
    // Default is the cross-platform case; iMessage narrows it below.
    options: [
      { id: 'apple', label: 'Apple Health' },
      { id: 'commonhealth', label: 'CommonHealth' },
    ],
    scopes: ['Respiratory rate', 'Blood oxygen', 'Resting heart rate', 'Sleep'],
    lines: [
      'Want to connect Apple Health or CommonHealth and share that data?',
      'If you do, I can see how your breathing and sleep actually track against the tours you work.',
      'Same as the note: it stays on your phone and only changes what I text you.',
    ],
    byChannel: {
      imessage: {
        lines: [
          'Want to connect your Apple Health account?',
          'If you do, I can see how your breathing and sleep actually track against the tours you work.',
          'Same as the note: it stays on your phone and only changes what I text you.',
        ],
        options: [{ id: 'apple', label: 'Apple Health' }],
      },
    },
    ack: 'Connected. I’ll only use it for your alerts.',
    skipAck: 'That’s fine.',
    next: 'notify',
    allowSkip: true,
    skipLabel: 'Not now',
    summaryLabel: 'Health app',
  },

  // ── Stage D — Notification opt-in ──────────────────────────────────────
  {
    id: 'notify',
    kind: 'choice',
    lines: [
      'Now, the alerts. I can text you once per shift, 90 minutes before you report, with what the air’s like where you’re working that day.',
      'Want those?',
    ],
    options: [
      { id: 'daily', label: 'Yes, daily' },
      { id: 'big-changes', label: 'Only big changes' },
      { id: 'none', label: 'No thanks' },
    ],
    next: 'sample',
    // Declining must not fall through to the enrolled confirmation. The two
    // paths say different things because they mean different things.
    branch: { none: 'declined' },
    summaryLabel: 'Shift alerts',
  },
  {
    id: 'declined',
    kind: 'say',
    lines: [
      'No problem — I won’t message you.',
      'If you change your mind, reply START and I’ll switch them on.',
      'One note: these are modeled estimates from station and task, not measurements.',
    ],
    next: 'complaint',
  },
  {
    id: 'sample',
    kind: 'say',
    lines: [
      'Here’s what one looks like:',
      {
        // What to do, and nothing else. No ratio, no median, and no offer to
        // produce them: a worker heading into a shift wants the instruction,
        // not the evidence behind it. The bracketed phrase renders in Signal
        // Orange, so the severity is carried by colour rather than a number.
        text: '👋 Good morning. You’re at 42nd Street today and the dust is running [hotter than usual]. Wear an N95 to stay protected.',
        sample: true,
      },
      'You’re all set. Reply STOP at any time and the messages end.',
      'One note: these are modeled estimates from station and task, not measurements.',
    ],
    next: 'complaint',
  },

  // ── Stage F — Station complaint ────────────────────────────────────────
  //
  // The one thing in this app intended to LEAVE the worker's phone. Everything
  // else is theirs alone; a complaint is the point of the tool — it is how a
  // condition becomes the local's problem instead of the worker's. What it
  // carries is deliberately narrow: station, date, and what the worker wrote.
  // Never a health answer, never an attachment, never a health-app reading.
  //
  // No category picker: a worker at the end of a shift should be able to say
  // what is wrong, not classify it. The station and date come along on their
  // own, so the only thing asked for is the sentence only they can write.
  {
    id: 'complaint',
    kind: 'report',
    actionLabel: 'Report a problem',
    placeholder: 'What’s going on?',
    lines: [
      'One last thing. Anything wrong at a station you want on record?',
      'Takes a few seconds and it goes to your local, not just into a file somewhere.',
    ],
    ack: 'Filed. Your local gets the station, the date and what you wrote. Nothing about your health goes with it.',
    skipAck: 'Understood.',
    next: 'done',
    allowSkip: true,
    skipLabel: 'Nothing to report',
    summaryLabel: 'Station report',
  },

  // ── Stage E — Done ─────────────────────────────────────────────────────
  {
    id: 'done',
    kind: 'done',
    lines: [{ special: 'summary' }],
  },
]

export const byId: Record<string, Step> = Object.fromEntries(
  script.map((step) => [step.id, step]),
)
