import brandMark from '../assets/brand-mark.svg'
import { brand } from '../theme'

/**
 * The bar that matches the landing page, so a visitor who arrived from it
 * has an obvious way back.
 *
 * The demo is reached at /demo on the same origin as the landing page, so
 * "/" is a plain link rather than anything the app routes. It is chrome
 * around the product, never part of a screen: the phone frames below it are
 * the product, and this bar belongs to the site.
 */
export function SiteNav() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[#040B4A]/90 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1140px] items-center gap-4 px-6">
        <a href="/" className="flex items-center gap-2.5 text-white">
          <img src={brandMark} alt="" aria-hidden="true" className="h-[26px] w-auto brightness-0 invert" />
          <span className="text-[15px] font-extrabold tracking-[-0.03em]">{brand.name}</span>
        </a>
        <span className="rounded-full border border-white/25 px-2.5 py-1 text-[11px] font-semibold tracking-wide text-[#C3CFF5]">
          Demo
        </span>
        <nav className="ml-auto flex items-center gap-1.5">
          <a
            href="/"
            className="rounded-lg px-3 py-2 text-[13px] font-medium text-[#C3CFF5] transition hover:bg-white/10 hover:text-white"
          >
            Back to site
          </a>
          <a
            href="https://github.com/piramsingh/CrewCare"
            className="rounded-lg border border-white/30 px-3 py-2 text-[13px] font-medium text-white transition hover:border-[#8FE3FF] hover:text-[#8FE3FF]"
          >
            Read the code
          </a>
        </nav>
      </div>
    </header>
  )
}
