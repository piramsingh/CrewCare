import { BrandMark } from '../components/BrandMark'
import { DemoBanner } from '../components/DemoBanner'
import { PhoneFrame } from '../components/PhoneFrame'
import { brand } from '../theme'
import type { Role } from '../auth/roles'

/**
 * The way into the demo.
 *
 * In the product this is a sign-in: one door for everyone, with the role
 * resolved from the account so the app can route itself without ever asking
 * which kind of person this is. `resolveRole` in `auth/roles.ts` is the swap
 * point where a real identity provider's claim goes.
 *
 * The public demo has no accounts, so a credential form here would collect
 * nothing and teach nothing — it was only ever a visual mock, and it stood
 * between a visitor and the thing they came to see. This screen picks the
 * path directly instead, and says what each one contains so the choice is
 * informed rather than a guess.
 */
export function Entry({ onContinue }: { onContinue: (role: Role) => void }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="no account and no sign-in. Nothing you do here leaves this tab." />
      </div>

      <PhoneFrame>
        <div className="flex flex-1 flex-col px-9 pt-[84px]">
          <div className="flex flex-col items-center">
            <BrandMark size={96} />
            <h1 className="pt-4 text-[30px] leading-none font-bold text-black">{brand.wordmark}</h1>
            <p className="pt-2.5 text-center text-[17px] leading-[1.3] font-normal text-cc-grey">
              {brand.taglineLines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </p>
          </div>

          <p className="pt-9 pb-4 text-center text-[15px] font-semibold text-black">
            Which side would you like to see?
          </p>

          <div className="flex flex-col gap-3">
            <Path
              label="As a worker"
              detail="The text thread: a shift alert, a private health check-in, and filing a station complaint."
              primary
              onClick={() => onContinue('worker')}
            />
            <Path
              label="As a union rep"
              detail="The dashboard: where complaints cluster across 496 stations, and where they match the model."
              onClick={() => onContinue('admin')}
            />
          </div>
        </div>
      </PhoneFrame>
    </div>
  )
}

function Path({
  label,
  detail,
  primary = false,
  onClick,
}: {
  label: string
  detail: string
  primary?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-2xl px-5 py-4 text-left transition active:scale-[0.99] ${
        primary
          ? 'bg-cc-primary text-white hover:bg-[#060F73]'
          : 'border border-cc-accent/45 bg-white text-cc-primary hover:border-cc-accent hover:bg-cc-accent/5'
      }`}
    >
      <span className="block text-[17px] font-bold">{label}</span>
      <span
        className={`block pt-1 text-[13px] leading-[1.4] font-normal ${
          primary ? 'text-white/80' : 'text-cc-grey'
        }`}
      >
        {detail}
      </span>
    </button>
  )
}
