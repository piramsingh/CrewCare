import { useState } from 'react'

import { requestLinkingCode, LinkingError } from '../../api/linking'
import { AgencyMark } from '../../components/AgencyMark'
import { DataNotice } from '../../components/DataNotice'
import { DemoBanner } from '../../components/DemoBanner'
import { PhoneFrame } from '../../components/PhoneFrame'
import { WHATSAPP_NUMBER_DISPLAY, whatsappDeepLink } from '../../config'
import { channels, type Channel } from '../../theme'

/**
 * After sign-in: link this worker's phone, or preview the conversation here.
 *
 * Two genuinely different things, kept apart on purpose:
 *
 *   Link my phone   asks the server for a one-time code tied to the employee
 *                   id from sign-in. The worker texts it to the CrewCare
 *                   number and the real conversation runs on their phone.
 *                   This is the only action in the app that touches a network.
 *
 *   Preview here    runs the simulated thread in the browser. No network, no
 *                   phone, nothing leaves the tab — useful for showing the
 *                   flow on a projector.
 */
export function ChannelSelect({
  employeeId,
  onChoose,
  onSignOut,
}: {
  employeeId: string
  onChoose: (channel: Channel) => void
  onSignOut: () => void
}) {
  const [code, setCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [preview, setPreview] = useState(false)

  async function link() {
    setPending(true)
    setError(null)
    try {
      const issued = await requestLinkingCode(employeeId)
      setCode(issued.code)
    } catch (caught) {
      setError(caught instanceof LinkingError ? caught.message : 'Something went wrong.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="prototype. The WhatsApp link is real; the exposure figures are modeled." />
      </div>

      <PhoneFrame>
        <div className="flex flex-1 flex-col px-7 pt-[68px] pb-8">
          <div className="flex items-center gap-3">
            <AgencyMark size={40} />
            <div>
              <p className="text-[15px] font-bold text-cc-primary">You're signed in.</p>
              <p className="text-[14px] text-cc-grey">Let's get CrewCare on your phone.</p>
            </div>
          </div>

          {code ? (
            <CodeIssued code={code} />
          ) : (
            <div className="pt-8">
              <p className="text-[14px] leading-snug text-cc-primary">
                CrewCare messages you on WhatsApp, on your own phone. Linking takes one text.
              </p>
              <button
                type="button"
                onClick={link}
                disabled={pending}
                className="mt-4 w-full rounded-full bg-cc-primary px-4 py-3.5 text-[16px] font-bold text-white transition active:scale-[0.99] disabled:opacity-50"
              >
                {pending ? 'Getting your code…' : 'Link my phone'}
              </button>
              {error && (
                <p className="pt-3 text-[13px] leading-snug text-cc-exposure">{error}</p>
              )}
            </div>
          )}

          {!code && (
            <div className="pt-7">
              <p className="pb-2 text-[12px] font-semibold tracking-wide text-cc-grey uppercase">
                Or see it without a phone
              </p>
              {preview ? (
                <div className="flex flex-col gap-2">
                  {(['imessage', 'whatsapp'] as Channel[]).map((id) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => onChoose(id)}
                      className="flex w-full items-center justify-between rounded-xl border border-cc-grey/25 bg-white px-4 py-3 text-left"
                    >
                      <span className="text-[15px] font-bold text-cc-primary">
                        {channels[id].label}
                      </span>
                      <span className="text-[12px] text-cc-grey">simulated</span>
                    </button>
                  ))}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setPreview(true)}
                  className="w-full rounded-full border border-cc-grey/35 bg-white px-4 py-3 text-[15px] font-semibold text-cc-primary"
                >
                  Preview the conversation here
                </button>
              )}
            </div>
          )}

          <div className="flex-1" />
          <DataNotice variant="linking" />
          <button
            type="button"
            onClick={onSignOut}
            className="pt-3 text-left text-[13px] font-semibold text-cc-accent"
          >
            Sign out
          </button>
        </div>
      </PhoneFrame>
    </div>
  )
}

/** The code, and the two ways to get it into WhatsApp. */
function CodeIssued({ code }: { code: string }) {
  return (
    <div className="pt-7">
      <p className="text-[14px] leading-snug text-cc-primary">
        Text this code to <span className="font-bold">{WHATSAPP_NUMBER_DISPLAY}</span> on
        WhatsApp.
      </p>

      <div className="mt-3 rounded-xl border border-cc-grey/25 bg-white py-5 text-center">
        <p className="font-mono text-[34px] leading-none font-bold tracking-[0.18em] text-cc-primary">
          {code}
        </p>
        <p className="pt-2 text-[12px] text-cc-grey">Expires in 10 minutes</p>
      </div>

      <a
        href={whatsappDeepLink(code)}
        target="_blank"
        rel="noreferrer"
        className="mt-3 block w-full rounded-full bg-[#25D366] px-4 py-3.5 text-center text-[16px] font-bold text-white"
      >
        Open WhatsApp
      </a>

      <p className="pt-3 text-[13px] leading-snug text-cc-grey">
        The button opens WhatsApp with the code already typed. Send it and CrewCare will
        reply on your phone.
      </p>
    </div>
  )
}
