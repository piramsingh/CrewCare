import agencyMark from '../assets/agency-mark.svg'

/**
 * The agency mark above the wordmark on sign-in, per the Figma mockup.
 *
 * `src/assets/agency-mark.svg` is the MTA's current roundel (in use since
 * 1994), from Wikimedia Commons. It is the agency's registered trademark and
 * is used here to match the approved design. Two consequences to keep in view:
 *
 *   1. This prototype must never be deployed anywhere it could be mistaken for
 *      an actual agency service. It pairs an agency trademark with an employee
 *      credential field, which is the shape of a phishing page — the standing
 *      DEMO banner and the absence of any real credential handling are what
 *      keep it on the right side of that line.
 *   2. Swapping in a different mark is a one-file change: replace the asset.
 *
 * The file is 898 bytes, so Vite inlines it as a data URI at build time and it
 * costs no network request.
 */
export function AgencyMark({ size = 108 }: { size?: number }) {
  return (
    <img
      src={agencyMark}
      alt=""
      aria-hidden="true"
      style={{ height: size }}
      className="block w-auto"
    />
  )
}
