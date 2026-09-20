/**
 * Mock data for the administrator dashboard.
 *
 * Every figure here is illustrative, not measured.
 *
 * This module is the ONLY data source the admin path imports. It contains no
 * health answers, no symptoms, no names, no employee IDs and no badge numbers,
 * and it has no reference to conversation state — the worker intake is
 * structurally unreachable from any admin view, not merely hidden by it.
 *
 * The 25-member k-anonymity floor is applied here, at the bottom of the stack,
 * so no view can accidentally render a suppressed cell.
 */

/** Cells describing fewer than this many members are suppressed outright. */
export const K_ANONYMITY_FLOOR = 25

export const LOCAL = '100'
export const PERIOD = 'Nov 2026'
export const PERIODS = ['Sep 2026', 'Oct 2026', 'Nov 2026'] as const

export type Stat = { label: string; value: string; note: string }

export const stats: Stat[] = [
  { label: 'Enrolled members', value: '1,240', note: 'of roughly 1,900 in the local' },
  { label: 'Tours logged', value: '38,900', note: 'this period' },
  { label: 'Median tour exposure', value: '1.6×', note: 'vs. system median' },
]

export type LineExposure = { line: string; ratio: number }

/** Six lines, descending. Hard-coded. */
export const byLine: LineExposure[] = [
  { line: '6', ratio: 2.6 },
  { line: '4', ratio: 2.2 },
  { line: 'A', ratio: 1.9 },
  { line: 'L', ratio: 1.4 },
  { line: '7', ratio: 1.1 },
  { line: 'N', ratio: 0.8 },
]

export const CHART_CAPTION =
  'Illustrative values — cells under 25 members suppressed.'

type RawRow = {
  id: string
  line: string
  tour: string
  title: string
  members: number
  ratio: number
}

/** Source rows, before suppression. Aggregates only — no individual anywhere. */
const rawRows: RawRow[] = [
  { id: 'r1', line: '6', tour: 'Midnights', title: 'Conductor', members: 214, ratio: 2.6 },
  { id: 'r2', line: '6', tour: 'Days', title: 'Train Operator', members: 186, ratio: 2.3 },
  { id: 'r3', line: '4', tour: 'Midnights', title: 'Conductor', members: 142, ratio: 2.2 },
  { id: 'r4', line: 'A', tour: 'Midnights', title: 'Conductor', members: 97, ratio: 1.9 },
  { id: 'r5', line: 'A', tour: 'Evenings', title: 'Station Agent', members: 18, ratio: 1.7 },
  { id: 'r6', line: 'L', tour: 'Days', title: 'Train Operator', members: 64, ratio: 1.4 },
  { id: 'r7', line: '7', tour: 'Evenings', title: 'Conductor', members: 41, ratio: 1.1 },
  { id: 'r8', line: 'N', tour: 'Days', title: 'Cleaner', members: 22, ratio: 0.9 },
]

export type ExposureRow = {
  id: string
  line: string
  tour: string
  title: string
  members: number
  /** Null when the cell falls under the k-anonymity floor. */
  ratio: number | null
  /** Percentage against the system median, e.g. "+160%". Null when suppressed. */
  vsSystemMedian: string | null
  suppressed: boolean
}

function relativeToMedian(ratio: number): string {
  const delta = Math.round((ratio - 1) * 100)
  return `${delta > 0 ? '+' : ''}${delta}%`
}

/**
 * Suppression happens on the way out of this module. A suppressed row keeps
 * its member count — which is what justifies the suppression — and loses the
 * exposure figures entirely.
 */
function suppress(row: RawRow): ExposureRow {
  const suppressed = row.members < K_ANONYMITY_FLOOR
  return {
    id: row.id,
    line: row.line,
    tour: row.tour,
    title: row.title,
    members: row.members,
    ratio: suppressed ? null : row.ratio,
    vsSystemMedian: suppressed ? null : relativeToMedian(row.ratio),
    suppressed,
  }
}

export const exposureRows: ExposureRow[] = rawRows.map(suppress)

/** Contents of the export stub. Aggregates only, by construction. */
export const exportContents = [
  'Median tour exposure by line',
  'Median tour exposure by tour and title',
  'Member counts per cell (suppressed under 25)',
  'Period comparison against the system median',
]
