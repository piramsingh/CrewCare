/**
 * Client for the operations API.
 *
 * Every figure here is computed by the team's Python models in
 * `admin_dashboard_model/` and served by `server/ops/api.py`. Nothing in the
 * front end calculates an environmental value, and nothing substitutes a
 * plausible number when a request fails — a failure surfaces as an error the
 * dashboard renders.
 */
import { API_BASE } from '../config'

export type Provenance = {
  outdoor: string
  platform: string
  risk: string
  reports: string
  environmentalWindow: string
}

export type OpsStation = {
  id: string
  name: string | null
  routes: string[]
  borough: string | null
  structure: string | null
  lat: number | null
  lon: number | null
  level: number | null
  levelName: string | null
  driver: string | null
  pm25: number | null
  tempF: number | null
  feelsF: number | null
  humidity: number | null
  mould: string | null
  reports: number
}

export type Concern = { label: string; count: number; percent: number }

export type OpsSnapshot = {
  generatedAt: string
  range: string
  rangeDays: number | null
  kpis: {
    stationsMonitored: number
    highRiskPlatforms: number
    workerReports: number
    bothSignals: number
  }
  stations: OpsStation[]
  concerns: Concern[]
  reportsAreDemo: boolean
  provenance: Provenance
}

export type StationReport = {
  id: string
  station_id: string
  reported_on: string | null
  category: string | null
  severity: string | null
  text: string | null
  demo: boolean
}

export class OpsError extends Error {}

async function get<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`)
  } catch {
    throw new OpsError(`Can't reach the CrewCare server at ${API_BASE}.`)
  }
  if (!response.ok) {
    let detail = `${response.status}`
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? detail
    } catch {
      /* the body was not JSON; the status is enough */
    }
    throw new OpsError(detail)
  }
  return (await response.json()) as T
}

export function fetchSnapshot(range: string): Promise<OpsSnapshot> {
  return get<OpsSnapshot>(`/api/ops/snapshot?range=${encodeURIComponent(range)}`)
}

export function fetchStationReports(
  stationId: string,
  range: string,
): Promise<{ stationId: string; reports: StationReport[] }> {
  return get(`/api/ops/station/${encodeURIComponent(stationId)}?range=${encodeURIComponent(range)}`)
}

/** Risk band colours, matching risk.py's LEVEL_COLORS. */
export const LEVEL_COLOR: Record<number, string> = {
  1: '#0ca30c',
  2: '#fab219',
  3: '#ec835a',
  4: '#d03b3b',
  5: '#6b1420',
}

export const LEVEL_LEGEND = [
  { level: 1, label: 'Low' },
  { level: 2, label: 'Caution' },
  { level: 3, label: 'Elevated' },
  { level: 4, label: 'High' },
]
