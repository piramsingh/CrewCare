import { useRef } from 'react'

import { BrandMark } from '../components/BrandMark'
import { resolveRole, type Role } from '../auth/roles'
import { DemoBanner } from '../components/DemoBanner'
import { PhoneFrame } from '../components/PhoneFrame'
import { brand } from '../theme'

/**
 * Central sign-in, built to the Figma mockup (node 1:2, 402×874).
 *
 * One door for everyone: the role comes off the account and the app routes
 * itself. The screen never asks which kind of person this is.
 *
 * This is a visual mock. Both fields are uncontrolled, any input is accepted
 * including empty, and nothing typed is validated, transmitted or stored. The
 * employee ID is read once on submit to resolve a role and is then cleared;
 * the password field is a no-op that is never read at all.
 */
export function SignIn({ onContinue }: { onContinue: (role: Role) => void }) {
  const idRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const role = resolveRole(idRef.current?.value ?? '')
    // Clear both fields before routing. Neither value outlives this handler.
    if (idRef.current) idRef.current.value = ''
    if (passwordRef.current) passwordRef.current.value = ''
    onContinue(role)
  }

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="simulated sign-in. No credentials are collected or stored." />
      </div>

      <PhoneFrame>
        <form onSubmit={handleSubmit} className="flex flex-1 flex-col px-10 pt-[76px]">
          <div className="flex flex-col items-center">
            <BrandMark size={96} />
            <h1 className="pt-4 text-[30px] leading-none font-bold text-black">
              {brand.wordmark}
            </h1>
            <p className="pt-2.5 text-center text-[17px] leading-[1.3] font-normal text-cc-grey">
              {brand.taglineLines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </p>
          </div>

          <div className="pt-8">
            <Field label="Employee ID">
              <input
                ref={idRef}
                name="employee-id"
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder="Enter here"
                className="w-full rounded-lg border border-cc-grey/55 bg-white px-4 py-3 text-[16px] font-normal text-black outline-none placeholder:text-cc-grey/70 focus:border-cc-accent focus:ring-2 focus:ring-cc-accent/15"
              />
            </Field>

            <div className="pt-4">
              <Field label="Password">
                {/* No-op field. Never read, never held in state. */}
                <input
                  ref={passwordRef}
                  name="password"
                  type="password"
                  autoComplete="off"
                  placeholder="Enter here"
                  className="w-full rounded-lg border border-cc-grey/55 bg-white px-4 py-3 text-[16px] font-normal text-black outline-none placeholder:text-cc-grey/70 focus:border-cc-accent focus:ring-2 focus:ring-cc-accent/15"
                />
              </Field>
            </div>

            <button
              type="button"
              onClick={(event) => event.preventDefault()}
              className="pt-2 text-[13px] font-normal text-cc-grey/90"
            >
              Forgot Password?
            </button>
          </div>

          <div className="pt-6">
            <button
              type="submit"
              className="w-full rounded-full bg-cc-primary px-6 py-4 text-[17px] font-normal text-white transition active:scale-[0.99] hover:bg-[#060F73]"
            >
              Continue
            </button>
            {/*
              DEMO ONLY — delete with the rest of the simulated auth.

              The product never asks a person which role they are; the role
              comes off the account and the app routes itself. These two
              buttons break that rule on purpose, because a visitor to the
              public demo has no account and should not have to be told an
              employee ID to type. They are labelled as a demo shortcut so
              the real behaviour is not misread from this screen.
            */}
            <div className="pt-5">
              <p className="pb-2.5 text-center text-[13px] font-normal text-cc-grey">
                No account? Jump straight in:
              </p>
              <div className="flex gap-2.5">
                <DemoEntry label="As a worker" onClick={() => onContinue('worker')} />
                <DemoEntry label="As a union rep" onClick={() => onContinue('admin')} />
              </div>
            </div>
          </div>
        </form>
      </PhoneFrame>
    </div>
  )
}

/** A demo shortcut into one of the two paths. Removed with the simulated auth. */
function DemoEntry({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex-1 rounded-full border border-cc-accent px-4 py-3 text-[15px] font-semibold text-cc-accent transition active:scale-[0.99] hover:bg-cc-accent hover:text-white"
    >
      {label}
    </button>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block pb-2 text-[16px] font-bold text-black">{label}</span>
      {children}
    </label>
  )
}
