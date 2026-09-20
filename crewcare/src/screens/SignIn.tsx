import { useRef } from 'react'

import { AgencyMark } from '../components/AgencyMark'
import { DEMO_HINT, resolveRole, sessionEmployeeId, type Role } from '../auth/roles'
import { DemoBanner } from '../components/DemoBanner'
import { PhoneFrame } from '../components/PhoneFrame'
import { brand } from '../theme'

/**
 * Central sign-in, built to the Figma mockup (node 1:2, 402×874).
 *
 * One door for everyone: the role comes off the account and the app routes
 * itself. The screen never asks which kind of person this is.
 *
 * Both fields are uncontrolled and any input is accepted, including empty.
 * The password field is a no-op: never read, never held in state.
 *
 * The employee ID is read once on submit and handed to the app, because
 * linking a phone to a worker needs to know which worker. That is a real
 * change from the offline demo, where the ID was resolved to a role and
 * immediately discarded — the app now knows who you are for the length of
 * the session. It is still never persisted: signing out drops it, and a
 * reload starts over.
 */
export function SignIn({
  onContinue,
}: {
  onContinue: (role: Role, employeeId: string) => void
}) {
  const idRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const typed = idRef.current?.value ?? ''
    const role = resolveRole(typed)
    const employeeId = sessionEmployeeId(typed)
    // The password is never read. The ID is cleared from the field and lives
    // only in React state from here on.
    if (idRef.current) idRef.current.value = ''
    if (passwordRef.current) passwordRef.current.value = ''
    onContinue(role, employeeId)
  }

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="simulated sign-in. No credentials are collected or stored." />
      </div>

      <PhoneFrame>
        <form onSubmit={handleSubmit} className="flex flex-1 flex-col px-10 pt-[76px]">
          <div className="flex flex-col items-center">
            <AgencyMark size={108} />
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
            <p className="pt-3 text-center text-[13px] font-normal text-cc-grey">{DEMO_HINT}</p>
          </div>
        </form>
      </PhoneFrame>
    </div>
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
