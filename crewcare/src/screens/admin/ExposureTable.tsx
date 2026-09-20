import { exposureRows, K_ANONYMITY_FLOOR } from '../../data/mockExposure'
import { color } from '../../theme'

const HEADERS = ['Line', 'Tour', 'Title', 'Members', 'Median exposure', 'vs. system median']

/**
 * Exposure by line, tour and title.
 *
 * Suppression is not decided here — rows arrive from data/mockExposure.ts
 * already stripped, so a suppressed cell has nothing left in it to leak.
 */
export function ExposureTable() {
  return (
    <section className="overflow-hidden rounded-xl border border-cc-grey/15 bg-white">
      <div className="flex items-baseline justify-between border-b border-cc-grey/15 px-6 py-4">
        <h2 className="text-[15px] font-bold text-cc-primary">Exposure by tour</h2>
        <p className="text-[12px] text-cc-grey">
          Cells with fewer than {K_ANONYMITY_FLOOR} members are suppressed.
        </p>
      </div>

      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="bg-cc-ground">
            {HEADERS.map((header, i) => (
              <th
                key={header}
                scope="col"
                className={`px-6 py-3 text-[12px] font-bold tracking-wide text-cc-grey uppercase ${
                  i >= 3 ? 'text-right' : ''
                }`}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {exposureRows.map((row) => (
            <tr key={row.id} className="border-t border-cc-grey/12">
              <td className="px-6 py-3.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-cc-primary text-[12px] font-bold text-white">
                  {row.line}
                </span>
              </td>
              <td className="px-6 py-3.5 text-[14px] font-semibold text-cc-primary">{row.tour}</td>
              <td className="px-6 py-3.5 text-[14px] text-cc-grey">{row.title}</td>
              <td className="px-6 py-3.5 text-right text-[14px] font-semibold text-cc-primary tabular-nums">
                {row.members}
              </td>
              <td className="px-6 py-3.5 text-right text-[14px] font-bold tabular-nums">
                {row.suppressed ? (
                  <Suppressed />
                ) : (
                  <span style={{ color: row.ratio! >= 2 ? color.exposure : color.primary }}>
                    {row.ratio!.toFixed(1)}×
                  </span>
                )}
              </td>
              <td className="px-6 py-3.5 text-right text-[14px] font-semibold text-cc-grey tabular-nums">
                {row.suppressed ? <span className="text-cc-grey">—</span> : row.vsSystemMedian}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function Suppressed() {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="text-cc-grey">—</span>
      <span className="rounded bg-cc-ground px-1.5 py-0.5 text-[11px] font-bold text-cc-grey">
        n&lt;{K_ANONYMITY_FLOOR}
      </span>
    </span>
  )
}
