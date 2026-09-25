import brandMark from '../assets/brand-mark.svg'

/**
 * The CrewCares mark above the wordmark on sign-in.
 *
 * This deliberately replaces the MTA roundel that sat here previously.
 * `src/assets/agency-mark.svg` is the agency's registered trademark, and
 * pairing it with an employee credential field is the shape of a phishing
 * page — tolerable on a laptop during a hackathon, not on a public URL. The
 * file is left in the repo but is no longer rendered anywhere.
 *
 * The mark is Material Symbols "train" (Apache 2.0), the same set the rest of
 * the app inlines, so nothing new is fetched at runtime.
 */
export function BrandMark({ size = 108 }: { size?: number }) {
  return (
    <img
      src={brandMark}
      alt=""
      aria-hidden="true"
      style={{ height: size }}
      className="block w-auto"
    />
  )
}
