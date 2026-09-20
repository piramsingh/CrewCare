/**
 * Mock data for the operations dashboard.
 *
 * Every figure is illustrative. As with `mockExposure.ts`, this module is a
 * leaf: it imports nothing from the conversation and holds no health answer,
 * no name and no employee id. The worker reports below are STATION
 * complaints — the one thing the worker flow deliberately sends outward —
 * and they carry a station, a date and what was written, nothing else.
 */

/** Risk bands, in official MTA brand colours (rev. 2024-11-22). */
export const RISK = {
  1: { label: 'Low', color: '#009952' },
  2: { label: 'Caution', color: '#F6BC26' },
  3: { label: 'Elevated', color: '#EB6800' },
  4: { label: 'High', color: '#D82233' },
} as const

export type RiskLevel = keyof typeof RISK

/** Official line colours. Used for the route bullets. */
export const LINE_COLOR: Record<string, string> = {
  '1': '#D82233', '2': '#D82233', '3': '#D82233',
  '4': '#009952', '5': '#009952', '6': '#009952',
  '7': '#9A38A1',
  A: '#0062CF', C: '#0062CF', E: '#0062CF',
  B: '#EB6800', D: '#EB6800', F: '#EB6800', M: '#EB6800',
  N: '#F6BC26', Q: '#F6BC26', R: '#F6BC26', W: '#F6BC26',
  G: '#799534',
  J: '#8E5C33', Z: '#8E5C33',
  L: '#7C858C', S: '#7C858C',
}

export const LAST_UPDATED = 'Sep 16, 2026 · 10:24 AM'

export const RANGES = ['Live', 'Today', '7 Days', '30 Days', '60 Days'] as const
export type Range = (typeof RANGES)[number]

export type StatIconName = 'station' | 'warning' | 'report' | 'signal'
export type Stat = {
  label: string
  value: string
  note: string
  icon: StatIconName
  tone: 'plain' | 'risk'
}

export const stats: Stat[] = [
  { label: 'Stations monitored', value: '496', note: 'Across all boroughs', icon: 'station', tone: 'plain' },
  { label: 'High-risk platforms', value: '46', note: 'Level 4 risk (modelled)', icon: 'warning', tone: 'risk' },
  { label: 'Worker reports', value: '233', note: 'In the last 30 days', icon: 'report', tone: 'plain' },
  { label: 'Stations with both signals', value: '38', note: 'Worker reports + elevated risk', icon: 'signal', tone: 'plain' },
]

/** A pin on the proxy map. x/y are percentages of the map box. */
export type MapStation = {
  id: string
  name: string
  x: number
  y: number
  risk: RiskLevel
}

export const mapStations: MapStation[] = [
  { id: 'm1', name: '181 St', x: 30, y: 19, risk: 1 },
  { id: 'm2', name: '168 St', x: 44, y: 14, risk: 2 },
  { id: 'm3', name: '145 St', x: 56, y: 22, risk: 1 },
  { id: 'm4', name: '125 St', x: 64, y: 10, risk: 4 },
  { id: 'm5', name: '116 St', x: 72, y: 18, risk: 2 },
  { id: 'm6', name: '96 St', x: 60, y: 30, risk: 4 },
  { id: 'm7', name: '86 St', x: 76, y: 28, risk: 1 },
  { id: 'm8', name: '72 St', x: 47, y: 26, risk: 2 },
  { id: 'm9', name: '59 St–Columbus', x: 39, y: 35, risk: 1 },
  { id: 'm10', name: 'Times Sq–42 St', x: 50, y: 48, risk: 4 },
  { id: 'm11', name: '34 St–Herald Sq', x: 58, y: 42, risk: 4 },
  { id: 'm12', name: '14 St–Union Sq', x: 66, y: 45, risk: 4 },
  { id: 'm13', name: 'Canal St', x: 45, y: 39, risk: 2 },
  { id: 'm14', name: 'Fulton St', x: 55, y: 52, risk: 2 },
  { id: 'm15', name: 'Bowling Green', x: 33, y: 45, risk: 2 },
  { id: 'm16', name: 'Court Sq', x: 82, y: 40, risk: 2 },
  { id: 'm17', name: 'Queensboro Plaza', x: 88, y: 34, risk: 1 },
  { id: 'm18', name: 'Jackson Hts', x: 92, y: 45, risk: 2 },
  { id: 'm19', name: 'Atlantic Av–Barclays', x: 60, y: 62, risk: 4 },
  { id: 'm20', name: 'Hoyt–Schermerhorn', x: 48, y: 58, risk: 4 },
  { id: 'm21', name: 'Jay St–MetroTech', x: 39, y: 54, risk: 1 },
  { id: 'm22', name: 'Bedford Av', x: 71, y: 57, risk: 1 },
  { id: 'm23', name: 'Broadway Jct', x: 78, y: 66, risk: 3 },
  { id: 'm24', name: 'Church Av', x: 53, y: 70, risk: 1 },
  { id: 'm25', name: 'Coney Island', x: 43, y: 74, risk: 2 },
  { id: 'm26', name: 'Flatbush Av', x: 66, y: 76, risk: 4 },
  { id: 'm27', name: '161 St–Yankee', x: 25, y: 34, risk: 2 },
  { id: 'm28', name: '3 Av–149 St', x: 69, y: 62, risk: 1 },
]

export type WorkerReport = {
  id: string
  concern: string
  level: RiskLevel
  date: string
  quote: string
  icon: 'air' | 'heat' | 'noise' | 'water'
}

/**
 * Station complaints, shown to the local as they were written.
 *
 * Anonymous by construction: a report carries where, when and what, and
 * nothing that identifies who filed it.
 */
export const stationReports: WorkerReport[] = [
  {
    id: 'r1',
    concern: 'Dust or air quality',
    level: 1,
    date: 'Sep 16, 2026',
    quote: 'Platform is stifling by the end of the tour…',
    icon: 'air',
  },
  {
    id: 'r2',
    concern: 'Heat',
    level: 1,
    date: 'Sep 8, 2026',
    quote: 'Metallic taste in the mouth after a full tour…',
    icon: 'heat',
  },
  {
    id: 'r3',
    concern: 'Noise',
    level: 1,
    date: 'Aug 26, 2026',
    quote: 'Braking screech on the express track is p…',
    icon: 'noise',
  },
]

export type StationDetail = {
  name: string
  lines: string[]
  system: string
  risk: RiskLevel
  driver: string
  metrics: { label: string; value: string; unit?: string; tone?: 'risk' | 'good' }[]
}

export const selectedStation: StationDetail = {
  name: 'Times Sq–42 St',
  lines: ['1', '2', '3'],
  system: 'Subway',
  risk: 4,
  driver: 'Driven by particulates',
  metrics: [
    { label: 'PM2.5', value: '104.7', unit: 'µg/m³', tone: 'risk' },
    { label: 'Temperature', value: '93.8°F' },
    { label: 'Humidity', value: '30%' },
    { label: 'Feels Like', value: '92.7°F' },
    { label: 'Mould Risk', value: 'Low', tone: 'good' },
  ],
}

export type TopStation = {
  rank: number
  name: string
  lines: string[]
  risk: RiskLevel
  pm25: number
}

export const topStations: TopStation[] = [
  { rank: 1, name: 'Atlantic Av–Barclays Ctr', lines: ['2', '3', '4', '5'], risk: 4, pm25: 137 },
  { rank: 2, name: '125 St', lines: ['A', 'C', 'B', 'D'], risk: 4, pm25: 137 },
  { rank: 3, name: '14 St–Union Sq', lines: ['N', 'Q', 'R', 'W'], risk: 4, pm25: 137 },
  { rank: 4, name: '34 St–Herald Sq', lines: ['B', 'D', 'F', 'M'], risk: 4, pm25: 137 },
  { rank: 5, name: 'Hoyt–Schermerhorn Sts', lines: ['A', 'C', 'G'], risk: 4, pm25: 124 },
]

export type Concern = { label: string; percent: number }

export const concerns: Concern[] = [
  { label: 'Dust or air quality', percent: 28 },
  { label: 'Heat', percent: 28 },
  { label: 'Ventilation or airflow', percent: 15 },
  { label: 'Damp, mould or standing water', percent: 12 },
  { label: 'Noise', percent: 6 },
]
