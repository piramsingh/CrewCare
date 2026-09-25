import { useState } from 'react'

import { BrandMark } from '../../components/BrandMark'
import { DataNotice } from '../../components/DataNotice'
import { DemoBanner } from '../../components/DemoBanner'
import { PhoneFrame } from '../../components/PhoneFrame'
import { channels, type Channel } from '../../theme'

/**
 * Channel hand-off.
 *
 * In production the worker taps a link and the conversation continues in
 * their own messaging app. Here both choices open the same simulated thread,
 * skinned to match — the whole worker path runs in this tab, with no server
 * and no network.
 */
export function ChannelSelect({
  onChoose,
  onSignOut,
}: {
  onChoose: (channel: Channel) => void
  onSignOut: () => void
}) {
  // Stable per mount, regenerated on a fresh sign-in. Goes nowhere.
  const [demoCode] = useState(
    () =>
      Math.random().toString(36).slice(2, 6).toUpperCase() +
      '-' +
      Math.random().toString(36).slice(2, 5).toUpperCase(),
  )

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-5 bg-cc-ground px-6 py-10">
      <div className="w-[422px]">
        <DemoBanner text="simulated messaging. No message is ever sent." />
      </div>

      <PhoneFrame>
        <div className="flex flex-1 flex-col px-7 pt-[68px] pb-8">
          <div className="flex items-center gap-3">
            <BrandMark size={40} />
            <div>
              <p className="text-[15px] font-bold text-cc-primary">You're signed in.</p>
              <p className="text-[14px] text-cc-grey">Pick where CrewCare should reach you.</p>
            </div>
          </div>

          <div className="flex flex-col gap-3 pt-8">
            {(['imessage', 'whatsapp'] as Channel[]).map((id) => (
              <ChannelCard key={id} id={id} onChoose={onChoose} />
            ))}
          </div>

          <div className="pt-7">
            <p className="pb-2 text-[12px] font-semibold tracking-wide text-cc-grey uppercase">
              Or open the one-tap link
            </p>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-cc-grey/35 bg-white px-3.5 py-3">
              <span className="truncate font-mono text-[13px] text-cc-primary">
                crewcare.app/start/{demoCode}
              </span>
              <span className="shrink-0 rounded-full bg-cc-ground px-2.5 py-1 text-[11px] font-bold tracking-wide text-cc-grey uppercase">
                simulated
              </span>
            </div>
            <p className="pt-2.5 text-[13px] leading-snug text-cc-grey">
              However you start, CrewCare messages arrive on your own phone, in the app you
              already use. There is nothing to install.
            </p>
          </div>

          <div className="flex-1" />
          <DataNotice variant="worker" />
          <button
            type="button"
            onClick={onSignOut}
            className="pt-3 text-left text-[13px] font-semibold text-cc-accent"
          >
            Exit demo
          </button>
        </div>
      </PhoneFrame>
    </div>
  )
}

function ChannelCard({ id, onChoose }: { id: Channel; onChoose: (c: Channel) => void }) {
  const theme = channels[id]
  return (
    <button
      type="button"
      onClick={() => onChoose(id)}
      className="flex w-full items-center gap-3.5 rounded-2xl border border-cc-grey/20 bg-white p-4 text-left transition hover:border-cc-accent active:scale-[0.99]"
    >
      <span
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[13px]"
        style={{ background: id === 'imessage' ? '#0B93F6' : '#25D366' }}
      >
        <svg viewBox="0 0 24 24" className="h-6 w-6 fill-white">
          <path d="M12 3C6.98 3 3 6.42 3 10.64c0 2.4 1.29 4.54 3.33 5.94-.14 1.2-.6 2.3-1.36 3.2-.16.19-.02.48.23.45 1.9-.24 3.4-1.03 4.42-1.76.74.16 1.53.25 2.38.25 5.02 0 9-3.42 9-7.64S17.02 3 12 3Z" />
        </svg>
      </span>
      <span className="min-w-0">
        <span className="block text-[16px] font-bold text-cc-primary">
          Continue on {theme.label}
        </span>
        <span className="block text-[13px] text-cc-grey">{theme.blurb}</span>
      </span>
      <svg
        viewBox="0 0 8 14"
        className="ml-auto h-3.5 w-2 shrink-0 fill-none stroke-cc-grey stroke-2"
      >
        <path d="M1 1l6 6-6 6" />
      </svg>
    </button>
  )
}
