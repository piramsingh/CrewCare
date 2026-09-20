import { useState } from 'react'

import { DataNotice } from '../../components/DataNotice'
import { MaterialIcon, type MaterialIconName } from '../../components/MaterialIcon'
import { AgencyMark } from '../../components/AgencyMark'
import { type OpsSnapshot, type OpsStation } from '../../api/ops'
import { RANGES, type Range } from '../../data/mockOperations'
import { brand } from '../../theme'
import { useOps } from './useOps'
import { ConcernBars } from './ConcernBars'
import { ExposureChart } from './ExposureChart'
import { ExposureTable } from './ExposureTable'
import { RiskMap } from './RiskMap'
import { StationPanel } from './StationPanel'
import { TopStations } from './TopStations'

/**
 * Operations dashboard.
 *
 * Reads from `data/mockOperations.ts` and `data/mockExposure.ts` and nothing
 * else. There is no import, prop or route from here to conversation state,
 * so a worker's health answers remain unreachable rather than merely hidden.
 *
 * The worker reports shown here are station complaints — the one thing the
 * worker flow deliberately sends outward. They carry a station, a date and
 * what was written; never a name, an employee id or a health answer.
 *
 * A desk tool: fixed to a 1280px minimum, deliberately not responsive to
 * phone widths.
 */
const NAV: { label: NavItem; icon: MaterialIconName }[] = [
  { label: 'Overview', icon: 'home' },
  { label: 'Stations', icon: 'location_on' },
  { label: 'Worker Reports', icon: 'chat' },
  { label: 'Risk Analytics', icon: 'bar_chart' },
  { label: 'Alerts', icon: 'notifications' },
  { label: 'Resources', icon: 'description' },
  { label: 'Settings', icon: 'settings' },
]

type NavItem =
  | 'Overview'
  | 'Stations'
  | 'Worker Reports'
  | 'Risk Analytics'
  | 'Alerts'
  | 'Resources'
  | 'Settings'

export function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const [section, setSection] = useState<NavItem>('Overview')
  const [range, setRange] = useState<Range>('30 Days')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  // The detail card is a popup now, so selection and visibility are separate:
  // closing it keeps the station selected and the marker highlighted.
  const [detailOpen, setDetailOpen] = useState(false)
  const { state, reload } = useOps(range)

  const snapshot = state.status === 'ready' ? state.data : null
  // Nothing is selected until the operator picks something: the detail card
  // only appears on click now, which is the point of the change.
  const selected = snapshot?.stations.find((s) => s.id === selectedId) ?? null

  function select(id: string) {
    setSelectedId(id)
    setDetailOpen(true)
  }

  return (
    <div className="flex min-h-full min-w-[1280px] bg-cc-ground">
      <Rail section={section} onSelect={setSection} />

      <main className="flex min-w-0 flex-1 flex-col">
        <Header
          range={range}
          onRange={setRange}
          onSignOut={onSignOut}
          generatedAt={snapshot?.generatedAt ?? null}
          status={state.status}
          onRefresh={reload}
        />

        <div className="min-w-0 flex-1 px-6 pb-6">
          {section === 'Overview' && (
            <>
              {state.status === 'loading' && <Banner>Loading live conditions…</Banner>}
              {state.status === 'error' && (
                <Banner tone="error">
                  {state.message}{' '}
                  <button type="button" onClick={reload} className="font-bold underline">
                    Retry
                  </button>
                </Banner>
              )}
              {snapshot && (
                <Overview
                  snapshot={snapshot}
                  selected={selected}
                  onSelect={select}
                  detailOpen={detailOpen}
                  onDismissDetail={() => setDetailOpen(false)}
                  range={range}
                />
              )}
            </>
          )}
          {section === 'Risk Analytics' && (
            <div className="flex flex-col gap-5">
              <ExposureChart />
              <ExposureTable />
            </div>
          )}
          {section !== 'Overview' && section !== 'Risk Analytics' && (
            <EmptySection name={section} />
          )}

          <footer className="mt-6 border-t border-cc-grey/15 pt-4">
            <DataNotice variant="admin" />
          </footer>
        </div>
      </main>
    </div>
  )
}

function Banner({ children, tone }: { children: React.ReactNode; tone?: 'error' }) {
  return (
    <p
      className="mb-5 rounded-lg border px-4 py-3 text-[13px]"
      style={
        tone === 'error'
          ? { borderColor: '#d03b3b40', background: '#d03b3b0d', color: '#8f1f1f' }
          : { borderColor: '#7C858C33', background: '#FFFFFF', color: '#5C6F94' }
      }
    >
      {children}
    </p>
  )
}

function Overview({
  snapshot,
  selected,
  onSelect,
  detailOpen,
  onDismissDetail,
  range,
}: {
  snapshot: OpsSnapshot
  selected: OpsStation | null
  onSelect: (id: string) => void
  detailOpen: boolean
  onDismissDetail: () => void
  range: Range
}) {
  const { kpis } = snapshot
  const window = range === 'Live' || range === 'Today' ? range.toLowerCase() : `the last ${range.toLowerCase()}`

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-4 gap-5">
        <StatCard icon="station" value={kpis.stationsMonitored.toLocaleString()}
          label="Stations monitored" note="Across all boroughs" tone="plain" />
        <StatCard icon="warning" value={kpis.highRiskPlatforms.toLocaleString()}
          label="High-risk platforms" note="Level 4 risk (modelled)" tone="risk" />
        <StatCard icon="report" value={kpis.workerReports.toLocaleString()}
          label="Worker reports" note={`In ${window}`} tone="plain" />
        <StatCard icon="signal" value={kpis.bothSignals.toLocaleString()}
          label="Stations with both signals" note="Worker reports + elevated risk" tone="plain" />
      </div>

      {/* Map and the priority list at eye level together: "where are the
          risks" and "where do we look first" answered in one glance. Detail
          is progressive — it appears only on click, as a map popup. */}
      <div className="grid grid-cols-[70fr_30fr] gap-5 max-[1400px]:grid-cols-1">
        <RiskMap
          stations={snapshot.stations}
          selectedId={selected?.id ?? null}
          onSelect={onSelect}
          popupOpen={detailOpen}
          onDismiss={onDismissDetail}
          popup={
            <StationPanel station={selected} range={range} onClose={onDismissDetail} />
          }
        />
        <TopStations
          stations={snapshot.stations}
          selectedId={selected?.id ?? null}
          onSelect={onSelect}
        />
      </div>

      <div className="grid grid-cols-[1.4fr_1fr] gap-5">
        <ConcernBars
          concerns={snapshot.concerns}
          rangeLabel={`In ${window}`}
          demo={snapshot.reportsAreDemo}
        />
        <Recommendations />
      </div>
    </div>
  )
}

type StatIconName = 'station' | 'warning' | 'report' | 'signal'

function StatCard({
  label,
  value,
  note,
  icon,
  tone,
}: {
  label: string
  value: string
  note: string
  icon: StatIconName
  tone: 'plain' | 'risk'
}) {
  return (
    <div className="rounded-xl border border-cc-grey/15 bg-white px-5 py-4">
      <span
        className="flex h-6 w-6 items-center justify-center"
        style={{ color: tone === 'risk' ? '#D82233' : '#0062CF' }}
      >
        <StatIcon name={icon} />
      </span>
      <p className="pt-2 text-[28px] leading-none font-bold tracking-[-0.02em] text-cc-primary">
        {value}
      </p>
      <p className="pt-1.5 text-[14px] font-semibold text-cc-primary">{label}</p>
      <p className="pt-0.5 text-[12px] text-cc-grey">{note}</p>
    </div>
  )
}

function StatIcon({ name }: { name: StatIconName }) {
  const c = 'h-5 w-5 fill-none stroke-current stroke-[1.6]'
  switch (name) {
    case 'warning':
      return (
        <svg viewBox="0 0 20 20" className={c}>
          <path d="M10 2.5 18.5 17H1.5z" />
          <path d="M10 8v4M10 14.2v.3" />
        </svg>
      )
    case 'report':
      return (
        <svg viewBox="0 0 20 20" className={c}>
          <rect x="2.5" y="3" width="15" height="11" rx="2" />
          <path d="M6.5 17.5 10 14M10 6v4M10 11.7v.3" />
        </svg>
      )
    case 'signal':
      return (
        <svg viewBox="0 0 20 20" className={c}>
          <path d="M2 7.5a12 12 0 0 1 16 0M5 11a7.5 7.5 0 0 1 10 0M8 14.3a3 3 0 0 1 4 0" />
          <circle cx="10" cy="17" r="0.6" fill="currentColor" />
        </svg>
      )
    default:
      return (
        <svg viewBox="0 0 20 20" className={c}>
          <rect x="5" y="2.5" width="10" height="13" rx="3" />
          <path d="M8 17.5h4M7.5 12.5h5" />
        </svg>
      )
  }
}

function Rail({
  section,
  onSelect,
}: {
  section: NavItem
  onSelect: (item: NavItem) => void
}) {
  return (
    <nav className="flex w-[190px] shrink-0 flex-col bg-cc-primary px-3 py-5">
      <div className="flex items-center gap-2.5 px-2 pb-6">
        {/* On a white tile: the roundel's blue is close to the sidebar's own
            navy and disappears against it otherwise. */}
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white">
          <AgencyMark size={26} />
        </span>
        <span className="text-[16px] font-bold text-white">{brand.name}</span>
      </div>

      <ul className="flex flex-col gap-0.5">
        {NAV.map(({ label, icon }) => {
          const active = label === section
          return (
            <li key={label}>
              <button
                type="button"
                onClick={() => onSelect(label)}
                aria-current={active ? 'page' : undefined}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-[13.5px] transition ${
                  active
                    ? 'bg-cc-accent font-bold text-white'
                    : 'font-semibold text-white/70 hover:bg-white/10 hover:text-white'
                }`}
              >
                <MaterialIcon name={icon} size={19} className="shrink-0 opacity-90" />
                <span className="truncate">{label}</span>
              </button>
            </li>
          )
        })}
      </ul>

      <div className="flex-1" />
      <div className="flex items-center gap-2.5 border-t border-white/15 px-2 pt-4">
        <AgencyMark size={30} />
        <span className="text-[11px] leading-tight font-semibold text-white/80">
          Safer Workers
          <br />
          Stronger Transit
        </span>
      </div>
    </nav>
  )
}

function Header({
  range,
  onRange,
  onSignOut,
  generatedAt,
  status,
  onRefresh,
}: {
  range: Range
  onRange: (r: Range) => void
  onSignOut: () => void
  generatedAt: string | null
  status: 'loading' | 'ready' | 'error'
  onRefresh: () => void
}) {
  const stamp = generatedAt
    ? new Date(generatedAt).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit',
      }).replace(',', ',').replace(/,([^,]*)$/, ' ·$1')
    : '—'
  return (
    <header className="flex items-start justify-between gap-6 px-6 pt-5 pb-5">
      <div>
        <h1 className="text-[22px] font-bold tracking-[-0.01em] text-cc-primary">
          Operations Dashboard
        </h1>
        <p className="pt-0.5 text-[13px] text-cc-grey">
          Real-time environmental insights for a safer MTA.
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-4">
        <div className="flex items-center gap-1 rounded-lg bg-white p-1">
          {RANGES.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onRange(option)}
              aria-pressed={option === range}
              className={`rounded-md px-3 py-1.5 text-[13px] font-semibold transition ${
                option === range ? 'bg-cc-accent text-white' : 'text-cc-primary hover:bg-cc-ground'
              }`}
            >
              {option}
            </button>
          ))}
        </div>

        <button type="button" onClick={onRefresh} className="text-right" title="Refresh">
          <p className="text-[11px] text-cc-grey">Last updated</p>
          <p className="text-[13px] font-semibold text-cc-primary">{stamp}</p>
          <p className="flex items-center justify-end gap-1.5 pt-0.5 text-[11px] text-cc-grey">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  status === 'ready' ? '#009952' : status === 'error' ? '#d03b3b' : '#F6BC26',
              }}
            />
            {status === 'ready' ? 'Live data' : status === 'error' ? 'Data unavailable' : 'Loading…'}
          </p>
        </button>

        <button
          type="button"
          onClick={onSignOut}
          aria-label="Sign out"
          title="Sign out"
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-cc-grey/25 bg-white text-cc-primary"
        >
          <svg viewBox="0 0 20 20" className="h-4.5 w-4.5 fill-none stroke-current stroke-[1.5]">
            <circle cx="10" cy="7" r="3" />
            <path d="M4 16.5c1.2-2.6 3.4-4 6-4s4.8 1.4 6 4" />
          </svg>
        </button>
      </div>
    </header>
  )
}

/** Where the model's suggestions will land once it has data to work from. */
function Recommendations() {
  return (
    <section className="flex flex-col rounded-xl border border-cc-grey/15 bg-white px-5 pt-5 pb-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-cc-primary">Recommendations</h2>
        <span className="rounded bg-cc-accent/12 px-2 py-1 text-[11px] font-bold text-cc-accent">
          AI-assisted
        </span>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
        <svg viewBox="0 0 24 24" className="h-9 w-9 fill-none stroke-cc-grey/45 stroke-[1.3]">
          <path d="M6 2.5h8l4 4v15H6z" />
          <path d="M14 2.5V7h4M9 12h6M9 16h6" />
        </svg>
        <p className="pt-3 text-[13px] font-semibold text-cc-grey">
          Recommendations will appear here
        </p>
        <p className="pt-1 text-[12px] text-cc-grey/80">Based on live data and worker reports</p>
      </div>
    </section>
  )
}

function EmptySection({ name }: { name: NavItem }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-xl border border-dashed border-cc-grey/30 bg-white/60">
      <p className="text-[16px] font-bold text-cc-primary">{name}</p>
      <p className="pt-1.5 text-[14px] text-cc-grey">Not built yet.</p>
    </div>
  )
}
