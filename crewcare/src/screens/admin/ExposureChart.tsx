import { byLine, CHART_CAPTION } from '../../data/mockExposure'
import { color, mix } from '../../theme'

const TOP_N = 2
const AXIS = [0, 1, 2, 3]

/**
 * Median tour exposure by line.
 *
 * Signal Orange marks the two lines carrying the highest exposure — the colour
 * is doing the work of the reading, not decorating the chart. Everything below
 * walks from Line Blue toward Slate so the eye falls off the scale.
 */
export function ExposureChart() {
  const max = AXIS[AXIS.length - 1]

  return (
    <section className="rounded-xl border border-cc-grey/15 bg-white p-6">
      <h2 className="text-[15px] font-bold text-cc-primary">Median tour exposure by line</h2>
      <p className="pt-1 text-[13px] text-cc-grey">
        Multiple of the system median for an 8-hour tour.
      </p>

      <div className="flex gap-4 pt-6">
        <div className="relative h-[240px] w-8 shrink-0">
          {AXIS.map((value) => (
            <span
              key={value}
              className="absolute right-0 -translate-y-1/2 text-[12px] font-semibold text-cc-grey"
              style={{ bottom: `${(value / max) * 100}%` }}
            >
              {value.toFixed(1)}×
            </span>
          ))}
        </div>

        <div className="relative min-w-0 flex-1">
          <div className="absolute inset-0">
            {AXIS.map((value) => (
              <div
                key={value}
                className="absolute inset-x-0 border-t border-cc-grey/15"
                style={{ bottom: `${(value / max) * 100}%` }}
              />
            ))}
          </div>

          <ol className="relative flex h-[240px] items-end gap-6">
            {byLine.map((entry, index) => (
              <li key={entry.line} className="flex h-full min-w-0 flex-1 flex-col justify-end">
                <span
                  className="pb-1.5 text-center text-[13px] font-bold"
                  style={{ color: index < TOP_N ? color.exposure : color.primary }}
                >
                  {entry.ratio.toFixed(1)}×
                </span>
                <div
                  className="w-full rounded-t-[3px]"
                  style={{
                    height: `${(entry.ratio / max) * 100}%`,
                    background:
                      index < TOP_N
                        ? color.exposure
                        : mix(color.accent, color.grey, (index - TOP_N) / (byLine.length - TOP_N - 1)),
                  }}
                />
              </li>
            ))}
          </ol>

          <ol className="flex gap-6 pt-2.5">
            {byLine.map((entry) => (
              <li key={entry.line} className="flex min-w-0 flex-1 justify-center">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-cc-primary text-[13px] font-bold text-white">
                  {entry.line}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <p className="pt-5 text-[12px] text-cc-grey">{CHART_CAPTION}</p>
    </section>
  )
}
