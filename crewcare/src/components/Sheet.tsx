import { PHONE } from '../theme'

/**
 * A modal sheet over the thread, in the shape iOS and Android both use.
 *
 * The scrim is the point: without it a bottom panel reads as more page rather
 * than as something that has taken over and is waiting on you. It also gives
 * a way out that does not require finding the Cancel control — tapping away
 * dismisses, which is what people try first.
 *
 * Scoped to the phone frame, not the browser window, so the demo chrome
 * around the device stays visible and undimmed.
 */
export function Sheet({
  label,
  onDismiss,
  children,
  inset = 70,
}: {
  label: string
  onDismiss: () => void
  children: React.ReactNode
  /** Gap left above the sheet, in px. */
  inset?: number
}) {
  return (
    <>
      <div
        className="cc-scrim absolute inset-0 z-20 bg-cc-primary/40"
        onClick={onDismiss}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className="cc-sheet absolute inset-x-0 bottom-0 z-30 flex flex-col rounded-t-[18px] bg-white shadow-[0_-18px_44px_-10px_rgba(8,23,156,0.45)]"
        style={{ maxHeight: PHONE.height - inset }}
      >
        <div className="flex justify-center pt-2 pb-1">
          <span aria-hidden="true" className="h-1 w-9 rounded-full bg-black/15" />
        </div>
        {children}
      </div>
    </>
  )
}
