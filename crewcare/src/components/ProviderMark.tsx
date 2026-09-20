import appleHealth from '../assets/apple-health.png'

/**
 * Logos for the health providers offered in the connection step.
 *
 * Apple Health uses the actual icon, which Wikimedia Commons carries as
 * public domain (it is a simple geometric shape, below the threshold of
 * originality).
 *
 * CommonHealth has no freely licensed logo, so the mark below is a
 * PLACEHOLDER of our own — not The Commons Project's artwork, and not to be
 * passed off as it. To use the real one, drop the supplied file in beside
 * `apple-health.png` and reference it here.
 */
export function ProviderMark({ provider, size = 26 }: { provider: string; size?: number }) {
  if (provider === 'apple') {
    return (
      <img
        src={appleHealth}
        alt=""
        aria-hidden="true"
        width={size}
        height={size}
        className="block shrink-0 rounded-[6px]"
      />
    )
  }

  // Placeholder mark — see the note above.
  return (
    <span
      aria-hidden="true"
      className="flex shrink-0 items-center justify-center rounded-[6px]"
      style={{ width: size, height: size, background: '#0E7C7B' }}
    >
      <svg viewBox="0 0 24 24" style={{ width: size * 0.62, height: size * 0.62 }} className="fill-white">
        <path d="M10.4 3h3.2v4.4H18v3.2h-4.4V15h-3.2v-4.4H6V7.4h4.4z" />
        <path d="M6 17.2h12V20H6z" opacity="0.65" />
      </svg>
    </span>
  )
}
