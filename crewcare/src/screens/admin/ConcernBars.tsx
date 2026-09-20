import type { Concern } from '../../api/ops'
import { color, mix } from '../../theme'

/** What workers are reporting, for the selected window. */
export function ConcernBars({
  concerns,
  rangeLabel,
  demo,
}: {
  concerns: Concern[]
  rangeLabel: string
  demo: boolean
}) {
  const max = Math.max(1, ...concerns.map((c) => c.percent))

  return (
    <section className="rounded-xl border border-cc-grey/15 bg-white px-5 pt-5 pb-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-[15px] font-bold text-cc-primary">Worker reports by concern type</h2>
          <p className="pt-0.5 text-[13px] text-cc-grey">{rangeLabel}</p>
        </div>
        {demo && (
          <span
            className="shrink-0 rounded bg-cc-ground px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-cc-grey uppercase"
            title="Seeded demo corpus, not real MTA submissions"
          >
            demo
          </span>
        )}
      </div>

      {concerns.length === 0 ? (
        <p className="py-10 text-center text-[13px] text-cc-grey">
          No worker reports in this period.
        </p>
      ) : (
        <ul className="flex flex-col gap-2.5 pt-4">
          {concerns.slice(0, 5).map((concern, index) => (
            <li key={concern.label} className="flex items-center gap-3">
              <span className="w-[120px] shrink-0 text-right text-[12px] leading-tight text-cc-primary">
                {concern.label}
              </span>
              <span className="h-3.5 min-w-0 flex-1 overflow-hidden rounded-sm bg-cc-ground">
                <span
                  className="block h-full rounded-sm"
                  style={{
                    width: `${(concern.percent / max) * 100}%`,
                    background: mix(color.accent, '#BBD2F0', index / 4),
                  }}
                />
              </span>
              <span className="w-9 shrink-0 text-right text-[12px] font-semibold text-cc-primary tabular-nums">
                {concern.percent}%
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
