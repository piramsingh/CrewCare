/**
 * Plain statement of what happens to the data on screen. Rendered on the
 * worker thread and in the admin footer.
 */
const COPY = {
  worker:
    'Your answers and any files you send stay in this browser tab. They shape only your own alerts, never a report. Nothing is transmitted or retained — closing the tab erases it.',
  admin:
    'Aggregate exposure only. No individual health information is collected in this view.',
} as const

export function DataNotice({ variant }: { variant: keyof typeof COPY }) {
  return (
    <p className="flex items-start gap-2 text-[12px] leading-snug text-cc-grey">
      <LockGlyph />
      <span>{COPY[variant]}</span>
    </p>
  )
}

function LockGlyph() {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      className="mt-px h-3.5 w-3.5 shrink-0 fill-none stroke-current"
      strokeWidth="1.4"
    >
      <rect x="3.25" y="7" width="9.5" height="6.5" rx="1.6" />
      <path d="M5.5 7V5.25a2.5 2.5 0 0 1 5 0V7" />
    </svg>
  )
}
