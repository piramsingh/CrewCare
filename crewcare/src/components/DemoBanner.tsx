/**
 * Persistent demo banner. Deliberately not dismissible: anyone looking at a
 * screen with an employee-ID field on it should be able to tell at a glance
 * that it is a prototype.
 */
export function DemoBanner({ text }: { text: string }) {
  return (
    <div
      role="status"
      className="w-full border-l-4 border-cc-exposure bg-white px-4 py-3 text-[13px] leading-snug text-cc-primary shadow-sm"
    >
      <span className="font-bold">DEMO</span>
      <span className="text-cc-grey"> — {text}</span>
    </div>
  )
}
