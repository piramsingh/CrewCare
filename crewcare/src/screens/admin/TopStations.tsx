import { LineBullet } from '../../components/LineBullet'
import { LEVEL_COLOR, type OpsStation } from '../../api/ops'

/** Highest-risk stations, ranked by the model's own level then PM2.5. */
export function rankStations(stations: OpsStation[]): OpsStation[] {
  return [...stations]
    .filter((s) => s.level != null)
    .sort(
      (a, b) =>
        (b.level ?? 0) - (a.level ?? 0) ||
        (b.pm25 ?? 0) - (a.pm25 ?? 0) ||
        b.reports - a.reports,
    )
    .slice(0, 5)
}

/**
 * The five stations to look at first, beside the map.
 *
 * A list rather than a table: in a column this narrow a five-column table
 * wraps every station name onto three lines, which is the opposite of
 * scannable. Each row carries the same facts, stacked.
 */
export function TopStations({
  stations,
  selectedId,
  onSelect,
}: {
  stations: OpsStation[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const ranked = rankStations(stations)

  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-cc-grey/15 bg-white">
      <header className="px-4 pt-5 pb-3">
        <h2 className="text-[15px] font-bold text-cc-primary">Top 5 stations to look at</h2>
        <p className="pt-0.5 text-[12px] text-cc-grey">Ranked by modelled risk</p>
      </header>

      <ul className="flex flex-col border-t border-cc-grey/12">
        {ranked.map((station, index) => {
          const selected = station.id === selectedId
          return (
            <li key={station.id}>
              <button
                type="button"
                onClick={() => onSelect(station.id)}
                aria-current={selected ? 'true' : undefined}
                className={`flex w-full items-start gap-2.5 border-b border-cc-grey/10 px-4 py-3 text-left transition last:border-0 ${
                  selected ? 'bg-cc-accent/8' : 'hover:bg-cc-ground/70'
                }`}
              >
                <span className="w-3.5 shrink-0 pt-0.5 text-[13px] font-semibold text-cc-grey tabular-nums">
                  {index + 1}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-[14px] font-bold text-cc-primary">
                      {station.name}
                    </span>
                    <span className="shrink-0 text-[13px] font-bold text-cc-primary tabular-nums">
                      {station.pm25 == null ? '—' : Math.round(station.pm25)}
                      <span className="pl-0.5 text-[10px] font-normal text-cc-grey">µg/m³</span>
                    </span>
                  </span>

                  <span className="flex items-center gap-2 pt-1.5">
                    <span className="flex shrink-0 gap-1">
                      {station.routes.slice(0, 4).map((line) => (
                        <LineBullet key={line} line={line} size={18} />
                      ))}
                    </span>
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: LEVEL_COLOR[station.level ?? 1] }}
                      />
                      <span className="truncate text-[12px] text-cc-grey">
                        Level {station.level} · {station.driver}
                      </span>
                    </span>
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
