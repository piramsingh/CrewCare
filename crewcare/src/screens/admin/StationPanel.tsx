import { useEffect, useState } from 'react'

import { LineBullet } from '../../components/LineBullet'
import {
  fetchStationReports,
  LEVEL_COLOR,
  type OpsStation,
  type StationReport,
} from '../../api/ops'

/**
 * Detail for the selected station, shown as a map popup.
 *
 * Every figure comes from the models. A metric they cannot produce for this
 * station renders "No data" — the panel never fills a gap with a number.
 *
 * Compact on purpose: it sits over the map, so it shows three reports and
 * defers the rest rather than growing tall enough to cover what the operator
 * is looking at.
 */
export function StationPanel({
  station,
  range,
  onClose,
}: {
  station: OpsStation | null
  range: string
  onClose?: () => void
}) {
  const [reports, setReports] = useState<StationReport[] | 'loading' | 'error'>('loading')

  useEffect(() => {
    if (!station) return
    let cancelled = false
    setReports('loading')
    fetchStationReports(station.id, range)
      .then((r) => !cancelled && setReports(r.reports))
      .catch(() => !cancelled && setReports('error'))
    return () => {
      cancelled = true
    }
  }, [station, range])

  if (!station) return null

  const color = LEVEL_COLOR[station.level ?? 1] ?? '#7C858C'

  return (
    <section
      aria-label={`Station details: ${station.name}`}
      className="flex max-h-full min-h-0 flex-col overflow-hidden rounded-xl border border-cc-grey/20 bg-white shadow-[0_8px_28px_-8px_rgba(6,39,101,0.35)]"
    >
      <header className="border-b border-cc-grey/12 px-4 pt-4 pb-3.5">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-[16px] leading-tight font-bold text-cc-primary">{station.name}</h2>
          <div className="flex shrink-0 items-center gap-1.5">
            <span
              className="rounded bg-cc-ground px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-cc-grey uppercase"
              title="Platform figures are modelled from a live outdoor reading"
            >
              modelled
            </span>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close station details"
                className="-mr-1 flex h-6 w-6 items-center justify-center rounded text-cc-grey hover:bg-cc-ground hover:text-cc-primary"
              >
                <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-none stroke-current stroke-[1.8]">
                  <path d="M4 4l8 8M12 4l-8 8" />
                </svg>
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {station.routes.map((line) => (
            <LineBullet key={line} line={line} size={19} />
          ))}
          <span className="text-[13px] text-cc-grey">· {station.structure ?? 'Subway'}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 pt-3">
          <span
            className="rounded px-2 py-1 text-[12px] font-bold text-white"
            style={{ background: color }}
          >
            Level {station.level} · {station.levelName}
          </span>
          <span className="text-[12px] text-cc-grey">
            {station.driver === 'Nothing elevated' ? 'Nothing elevated' : `Driven by ${String(station.driver).toLowerCase()}`}
          </span>
        </div>

        <dl className="flex items-start justify-between gap-1.5 pt-3.5">
          <Metric label="PM2.5" value={fmt(station.pm25, 1)} unit="µg/m³" tone={station.pm25 != null && station.pm25 >= 75 ? 'risk' : undefined} />
          <Metric label="Temperature" value={fmt(station.tempF, 1, '°F')} />
          <Metric label="Humidity" value={fmt(station.humidity, 0, '%')} />
          <Metric label="Feels Like" value={fmt(station.feelsF, 1, '°F')} />
          <Metric label="Mould Risk" value={station.mould ?? null} tone={station.mould === 'Low' ? 'good' : 'risk'} />
        </dl>
      </header>

      <div className="flex items-center justify-between px-4 pt-3 pb-1">
        <h3 className="text-[14px] font-bold text-cc-primary">
          Recent worker reports
          {Array.isArray(reports) ? ` (${reports.length})` : ''}
        </h3>
        {Array.isArray(reports) && reports.some((r) => r.demo) && (
          <span className="text-[10px] font-bold tracking-wide text-cc-grey uppercase">demo</span>
        )}
      </div>

      <div className="min-h-0 overflow-y-auto px-4 pb-4">
        {reports === 'loading' && <p className="py-6 text-[13px] text-cc-grey">Loading…</p>}
        {reports === 'error' && (
          <p className="py-6 text-[13px] text-cc-grey">Worker reports unavailable.</p>
        )}
        {Array.isArray(reports) && reports.length === 0 && (
          <p className="py-6 text-[13px] text-cc-grey">No recent worker reports.</p>
        )}
        {Array.isArray(reports) && reports.length > 0 && (
          <>
          <ul className="flex flex-col divide-y divide-cc-grey/10">
            {reports.slice(0, MAX_REPORTS).map((report) => (
              <li key={report.id} className="py-2.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate text-[13px] font-bold text-cc-primary">
                    {report.category}
                    {report.severity ? ` · ${report.severity}` : ''}
                  </p>
                  <span className="shrink-0 text-[11px] text-cc-grey">{report.reported_on}</span>
                </div>
                <p className="truncate text-[12px] text-cc-grey">“{report.text}”</p>
              </li>
            ))}
          </ul>
          {reports.length > MAX_REPORTS && (
            <button type="button" className="pt-2 text-[12px] font-semibold text-cc-accent">
              View all {reports.length} →
            </button>
          )}
          </>
        )}
      </div>
    </section>
  )
}

/** Three keeps the popup short enough not to cover the map it sits on. */
const MAX_REPORTS = 3

function Metric({
  label,
  value,
  unit,
  tone,
}: {
  label: string
  value: string | null
  unit?: string
  tone?: 'risk' | 'good'
}) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[11px] text-cc-grey">{label}</dt>
      <dd
        className="text-[15px] font-bold"
        style={{
          color: value == null ? '#7C858C' : tone === 'risk' ? '#d03b3b' : tone === 'good' ? '#0ca30c' : '#08179C',
        }}
      >
        {value ?? 'No data'}
      </dd>
      {unit && value != null && <p className="text-[10px] text-cc-grey">{unit}</p>}
    </div>
  )
}

function fmt(value: number | null, digits: number, suffix = ''): string | null {
  if (value == null || Number.isNaN(value)) return null
  return `${value.toFixed(digits)}${suffix}`
}
