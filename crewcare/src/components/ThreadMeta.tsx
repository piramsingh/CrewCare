import { ASSIGNMENT_ON_FILE } from '../data/assignment'

/**
 * Standing context for the thread: today's date, the worker's role, and the
 * station they are at today.
 *
 * This lives in the chrome rather than in the conversation on purpose. It is
 * the agency's record, not an answer, so it should not cost a turn to state
 * or a tap to acknowledge — and it stays visible while the worker scrolls,
 * which a message would not.
 */
export function ThreadMeta({ date = today() }: { date?: string }) {
  return (
    <section
      aria-label="Today’s assignment"
      className="flex items-center gap-2 border-b border-black/5 bg-cc-ground px-4 py-2 text-[12px] leading-none"
    >
      <span className="shrink-0 font-semibold text-cc-grey">{date}</span>
      <Separator />
      <span className="shrink-0 font-bold text-cc-primary">{ASSIGNMENT_ON_FILE.role}</span>
      <Separator />
      <span className="truncate font-bold text-cc-primary">{ASSIGNMENT_ON_FILE.station}</span>
    </section>
  )
}

function Separator() {
  return (
    <span aria-hidden="true" className="shrink-0 text-cc-grey/50">
      ·
    </span>
  )
}

/** e.g. "Fri, Sep 19". Resolved once per mount. */
function today(): string {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}
