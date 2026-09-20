/**
 * Design tokens, from the MTA's official brand standard.
 *
 * Colours are the exact values published in "MTA Brand Colors / Subway, SIR &
 * ADA" (rev. 2024-11-22, mta.info/document/168976). They are NOT the legacy
 * Vignelli-era line colours (#0039A6 / #FF6319) that the original CrewCare
 * brief quoted — those are the pre-refresh subway palette.
 *
 * Token names describe the ROLE, not the hue, so the palette can be swapped
 * underneath without any name becoming a lie. This block and the matching
 * @theme block in index.css are the only places colour is defined.
 *
 * Two rules carried over from the standard itself:
 *   · "One gray only used throughout the New York City Subway System" — there
 *     is a single grey here, and no other neutral is introduced.
 *   · "Do not use white knock-out type on yellow" — yellow is unused, so the
 *     rule cannot be broken by accident.
 */
export const color = {
  /** MTA Blue. Dark chrome and primary actions. */
  primary: '#08179C',
  /** Blue. Interactive accents and links. */
  accent: '#0062CF',
  /** Neutral ground. Not an MTA brand colour: a page background, not identity. */
  ground: '#F4F6FA',
  /**
   * Orange. EXPOSURE INDICATION ONLY, never decoration — the one place the
   * colour carries meaning rather than style.
   */
  exposure: '#EB6800',
  /** Grey. Secondary text. The single permitted grey. */
  grey: '#7C858C',
  white: '#FFFFFF',
} as const

export const brand = {
  /** Compact form, used in app chrome (thread header, dashboard rail). */
  name: 'CrewCare',
  /** Sign-in wordmark, set as two words in the mockup. */
  wordmark: 'Crew Care',
  /** Sign-in tagline, set on two lines in the mockup. */
  taglineLines: ['Safer works', 'Stronger Transit.'],
  tagline: 'Safer Work. Stronger Transit.',
} as const

/** Phone frame used by the sign-in screen and the whole worker path. */
export const PHONE = { width: 402, height: 874 } as const

/** Blend two hex colors. Used to walk chart bars from Line Blue to Slate. */
export function mix(from: string, to: string, t: number): string {
  const parse = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  const a = parse(from)
  const b = parse(to)
  const out = a.map((v, i) => Math.round(v + (b[i] - v) * t))
  return `#${out.map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

/**
 * Channel skins for the simulated thread.
 *
 * Both channels run the identical conversation — only the paint changes.
 *
 * Note for whoever productionises this: iMessage has no inbound bot API, and
 * Apple Messages for Business requires brand registration this use case would
 * not obtain. The iMessage skin is a visual option only. WhatsApp Business API
 * is the buildable path.
 */
export type Channel = 'imessage' | 'whatsapp'

export type ChannelTheme = {
  label: string
  blurb: string
  canvas: string
  headerBg: string
  headerFg: string
  headerBorder: string
  outgoingBg: string
  outgoingFg: string
  incomingBg: string
  incomingFg: string
  incomingBorder: string
  composerBg: string
  /** Neutral chip pair for the DEMO marker. Never Signal Orange: that colour
      is reserved for exposure indication. */
  chipBg: string
  chipFg: string
  radius: string
  font: string
  /** Letter-spacing nudge; iOS type sits slightly tighter than WhatsApp's. */
  tracking: string
}

export const channels: Record<Channel, ChannelTheme> = {
  imessage: {
    label: 'iMessage',
    blurb: 'Messages app on your iPhone',
    canvas: '#FFFFFF',
    headerBg: '#F7F7F7',
    headerFg: '#000000',
    headerBorder: '#D8D8DC',
    outgoingBg: '#0B93F6',
    outgoingFg: '#FFFFFF',
    incomingBg: '#E9E9EB',
    incomingFg: '#000000',
    incomingBorder: 'transparent',
    composerBg: '#F7F7F7',
    chipBg: '#E3E3E7',
    chipFg: '#5C6F94',
    radius: '19px',
    font: '-apple-system, "SF Pro Text", BlinkMacSystemFont, "Helvetica Neue", sans-serif',
    tracking: '-0.01em',
  },
  whatsapp: {
    label: 'WhatsApp',
    blurb: 'WhatsApp on your own phone',
    canvas: '#EFE7DE',
    headerBg: '#075E54',
    headerFg: '#FFFFFF',
    headerBorder: '#064C44',
    outgoingBg: '#D9FDD3',
    outgoingFg: '#111B21',
    incomingBg: '#FFFFFF',
    incomingFg: '#111B21',
    incomingBorder: 'transparent',
    composerBg: '#F0F2F5',
    chipBg: 'rgba(255,255,255,0.22)',
    chipFg: '#FFFFFF',
    radius: '8px',
    font: '"Segoe UI", "Helvetica Neue", Roboto, Arial, sans-serif',
    tracking: '0',
  },
}
