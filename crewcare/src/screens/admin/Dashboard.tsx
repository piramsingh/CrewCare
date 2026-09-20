import { useState } from 'react'

import { DataNotice } from '../../components/DataNotice'
import { DemoBanner } from '../../components/DemoBanner'
import { AgencyMark } from '../../components/AgencyMark'
import {
  exportContents,
  LOCAL,
  PERIOD,
  PERIODS,
  stats,
} from '../../data/mockExposure'
import { ExposureChart } from './ExposureChart'
import { ExposureTable } from './ExposureTable'

/**
 * Administrator dashboard.
 *
 * This subtree imports from data/mockExposure.ts and nothing else. It has no
 * route to conversation state, no props carrying it and no import that could
 * reach it — so the intake answers are not merely hidden from this view, they
 * are unreachable from it. Nothing an individual worker typed exists here to
 * be rendered, exported or leaked.
 *
 * It is a desk tool: fixed to a 1280px minimum and deliberately not responsive
 * to phone widths.
 */
const NAV = ['Overview', 'By line', 'By tour', 'Reports'] as const
type NavItem = (typeof NAV)[number]

export function Dashboard({ onSignOut }: { onSignOut: () => void }) {
  const [section, setSection] = useState<NavItem>('Overview')
  const [exporting, setExporting] = useState(false)
  const [period, setPeriod] = useState<string>(PERIOD)

  return (
    <div className="flex min-h-full min-w-[1280px] flex-col bg-cc-ground">
      <DemoBanner text="simulated data. Every figure below is illustrative." />

      <div className="flex min-h-0 flex-1">
        <Rail section={section} onSelect={setSection} onSignOut={onSignOut} />

        <main className="min-w-0 flex-1 px-10 py-8">
          {section === 'Overview' ? (
            <Overview
              period={period}
              onPeriod={setPeriod}
              onExport={() => setExporting(true)}
            />
          ) : (
            <EmptySection name={section} />
          )}

          <footer className="border-t border-cc-grey/15 pt-5 mt-10">
            <DataNotice variant="admin" />
          </footer>
        </main>
      </div>

      {exporting && <ExportModal onClose={() => setExporting(false)} period={period} />}
    </div>
  )
}

function Rail({
  section,
  onSelect,
  onSignOut,
}: {
  section: NavItem
  onSelect: (item: NavItem) => void
  onSignOut: () => void
}) {
  return (
    <nav className="flex w-[248px] shrink-0 flex-col bg-cc-primary px-5 py-7">
      <div className="flex items-center gap-3 px-2">
        <AgencyMark size={36} />
        <div>
          <p className="text-[15px] leading-tight font-bold text-white">CrewCare</p>
          <p className="text-[12px] text-white/60">Local {LOCAL}</p>
        </div>
      </div>

      <ul className="flex flex-col gap-1 pt-9">
        {NAV.map((item) => {
          const active = item === section
          return (
            <li key={item}>
              <button
                type="button"
                onClick={() => onSelect(item)}
                aria-current={active ? 'page' : undefined}
                className={`w-full rounded-lg px-3 py-2.5 text-left text-[14px] transition ${
                  active
                    ? 'bg-white/12 font-bold text-white'
                    : 'font-semibold text-white/65 hover:bg-white/6 hover:text-white'
                }`}
              >
                {item}
              </button>
            </li>
          )
        })}
      </ul>

      <div className="flex-1" />
      <button
        type="button"
        onClick={onSignOut}
        className="rounded-lg px-3 py-2.5 text-left text-[13px] font-semibold text-white/60 hover:text-white"
      >
        Sign out
      </button>
    </nav>
  )
}

function Overview({
  period,
  onPeriod,
  onExport,
}: {
  period: string
  onPeriod: (p: string) => void
  onExport: () => void
}) {
  return (
    <>
      <header className="flex items-center justify-between gap-6 pb-7">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.01em] text-cc-primary">
            Local {LOCAL} — exposure overview
          </h1>
          <p className="pt-1 text-[14px] text-cc-grey">
            Modeled exposure across enrolled members. No individual data.
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <label className="relative">
            <span className="sr-only">Period</span>
            <select
              value={period}
              onChange={(event) => onPeriod(event.target.value)}
              className="appearance-none rounded-lg border border-cc-grey/25 bg-white py-2.5 pr-9 pl-4 text-[14px] font-semibold text-cc-primary outline-none focus:border-cc-accent"
            >
              {PERIODS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <svg
              viewBox="0 0 10 6"
              className="pointer-events-none absolute top-1/2 right-3.5 h-1.5 w-2.5 -translate-y-1/2 fill-none stroke-cc-grey stroke-2"
            >
              <path d="M1 1l4 4 4-4" />
            </svg>
          </label>
          <button
            type="button"
            onClick={onExport}
            className="rounded-lg bg-cc-accent px-4 py-2.5 text-[14px] font-bold text-white transition hover:bg-[#002F8C]"
          >
            Export report
          </button>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-5 pb-6">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-xl border border-cc-grey/15 bg-white p-5">
            <p className="text-[12px] font-bold tracking-wide text-cc-grey uppercase">
              {stat.label}
            </p>
            <p className="pt-2 text-[30px] leading-none font-bold tracking-[-0.02em] text-cc-primary">
              {stat.value}
            </p>
            <p className="pt-2 text-[13px] text-cc-grey">{stat.note}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-6">
        <ExposureChart />
        <ExposureTable />
      </div>
    </>
  )
}

function EmptySection({ name }: { name: NavItem }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-xl border border-dashed border-cc-grey/30 bg-white/60">
      <p className="text-[16px] font-bold text-cc-primary">{name}</p>
      <p className="pt-1.5 text-[14px] text-cc-grey">Not built in this demo.</p>
    </div>
  )
}

/** Export stub. Aggregates only — there is no individual data to offer. */
function ExportModal({ onClose, period }: { onClose: () => void; period: string }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-cc-primary/45 px-6"
      role="dialog"
      aria-modal="true"
      aria-label="Export report"
      onClick={onClose}
    >
      <div
        className="w-[480px] rounded-xl bg-white p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="text-[18px] font-bold text-cc-primary">Export report</h2>
        <p className="pt-1.5 text-[14px] text-cc-grey">
          Local {LOCAL} · {period}
        </p>

        <ul className="flex flex-col gap-2 pt-5">
          {exportContents.map((item) => (
            <li key={item} className="flex items-start gap-2.5 text-[14px] text-cc-primary">
              <svg viewBox="0 0 14 14" className="mt-1 h-3.5 w-3.5 shrink-0 fill-none stroke-cc-accent stroke-2">
                <path d="M2 7.5 5.5 11 12 3.5" />
              </svg>
              {item}
            </li>
          ))}
        </ul>

        <p className="mt-5 rounded-lg bg-cc-ground p-3.5 text-[13px] leading-snug text-cc-grey">
          The export carries aggregate exposure only. Health answers, names and employee IDs are
          not collected in this view and cannot be included.
        </p>

        <div className="flex justify-end gap-2 pt-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2.5 text-[14px] font-semibold text-cc-grey"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-cc-accent px-4 py-2.5 text-[14px] font-bold text-white"
            title="Nothing is generated in this demo"
          >
            Generate (demo)
          </button>
        </div>
      </div>
    </div>
  )
}
