import { useEffect, useState } from 'react'

import { AgencyMark } from './AgencyMark'

/**
 * A simulated push notification, in the shape iOS uses.
 *
 * Shown once the worker opts into shift alerts, so the demo can answer the
 * obvious next question — "what does one actually look like?" — on the lock
 * screen rather than as another chat bubble.
 *
 * It behaves like the real thing: slides down below the status bar, sits over
 * whatever is on screen, and leaves on its own. Tapping dismisses it early.
 * Nothing is scheduled and nothing is sent; this is paint.
 */
const VISIBLE_MS = 7000

export function PushNotification({
  text,
  onDone,
}: {
  text: string
  onDone: () => void
}) {
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    const hide = setTimeout(() => setLeaving(true), VISIBLE_MS)
    return () => clearTimeout(hide)
  }, [])

  useEffect(() => {
    if (!leaving) return
    const done = setTimeout(onDone, 320)
    return () => clearTimeout(done)
  }, [leaving, onDone])

  return (
    <div
      role="status"
      aria-label="Notification preview"
      onClick={() => setLeaving(true)}
      className={`absolute inset-x-2.5 top-[52px] z-40 cursor-pointer rounded-[20px] bg-white/85 px-3.5 py-3 shadow-[0_10px_30px_-6px_rgba(0,0,0,0.35)] backdrop-blur-xl ${
        leaving ? 'cc-notify-out' : 'cc-notify-in'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="flex h-[18px] w-[18px] shrink-0 items-center justify-center overflow-hidden rounded-[5px] bg-white">
          <AgencyMark size={16} />
        </span>
        <span className="text-[12px] font-semibold tracking-wide text-black/55 uppercase">
          CrewCare
        </span>
        <span className="ml-auto text-[12px] text-black/45">now</span>
      </div>
      <p className="pt-1.5 text-[14px] leading-[1.35] text-black">{text}</p>
      {/* The grabber iOS puts under a banner. */}
      <span className="mx-auto mt-2 block h-1 w-9 rounded-full bg-black/15" />
    </div>
  )
}
