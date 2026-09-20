import { useLayoutEffect, useRef, useState } from 'react'

import { LEVEL_COLOR, LEVEL_LEGEND, type OpsStation } from '../../api/ops'

/**
 * The station map.
 *
 * Real coordinates from the spine, projected into the panel rather than drawn
 * on map tiles. Tiles would mean a third-party request on every pan; an
 * equirectangular projection over a 25 km city is accurate to well under a
 * pixel here, and the marker positions are the part that has to be right.
 */
const PAD = 0.04

function MapButton({
  children,
  label,
  onClick,
}: {
  children: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded-md bg-white/95 text-[17px] leading-none font-semibold text-cc-primary shadow-sm hover:bg-white"
    >
      {children}
    </button>
  )
}

/**
 * One label per borough, placed at the centroid of its own stations.
 *
 * Derived from the same coordinates as the markers rather than hand-placed,
 * so the labels cannot drift out of agreement with the dots.
 */
function boroughLabels(
  stations: OpsStation[],
  project: (s: OpsStation) => { x: number; y: number },
) {
  const groups = new Map<string, { x: number; y: number; n: number }>()
  for (const station of stations) {
    if (!station.borough) continue
    const point = project(station)
    const acc = groups.get(station.borough) ?? { x: 0, y: 0, n: 0 }
    groups.set(station.borough, { x: acc.x + point.x, y: acc.y + point.y, n: acc.n + 1 })
  }
  return [...groups.entries()]
    .filter(([, g]) => g.n >= 5)
    .map(([name, g]) => ({ name, x: g.x / g.n, y: g.y / g.n }))
}

const POPUP_W = 340
//: Tall enough for the metrics and three reports, short enough that the map
//: it sits on is still readable around it.
const POPUP_MAX_H = 430
const GAP = 14

export function RiskMap({
  stations,
  selectedId,
  onSelect,
  popup,
  popupOpen,
  onDismiss,
}: {
  stations: OpsStation[]
  selectedId: string | null
  onSelect: (id: string) => void
  /** The station detail card. Rendered over the map, anchored to the marker. */
  popup?: React.ReactNode
  popupOpen: boolean
  onDismiss: () => void
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(1)
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null)
  const placed = stations.filter((s) => s.lat != null && s.lon != null)
  const lats = placed.map((s) => s.lat as number)
  const lons = placed.map((s) => s.lon as number)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)

  const project = (station: OpsStation) => ({
    // Latitude increases north, so y is inverted.
    x: (((station.lon as number) - minLon) / (maxLon - minLon)) * (1 - 2 * PAD) * 100 + PAD * 100,
    y: (1 - ((station.lat as number) - minLat) / (maxLat - minLat)) * (1 - 2 * PAD) * 100 + PAD * 100,
  })

  const selected = placed.find((s) => s.id === selectedId) ?? null

  /**
   * Anchor the popup beside its marker, then keep it inside the map.
   *
   * Preferred side is right of the marker; it flips left when that would
   * overflow, and the result is clamped on both axes, so a marker at any
   * edge still gets a fully visible card.
   */
  useLayoutEffect(() => {
    if (!popupOpen || !selected || !boxRef.current) {
      setPlace(null)
      return
    }
    const box = boxRef.current.getBoundingClientRect()
    const height = Math.min(popupRef.current?.offsetHeight ?? 320, POPUP_MAX_H)
    const point = project(selected)
    // Markers scale about the centre, so the anchor must too.
    const markerX = box.width / 2 + ((point.x / 100) * box.width - box.width / 2) * zoom
    const markerY = box.height / 2 + ((point.y / 100) * box.height - box.height / 2) * zoom

    let left = markerX + GAP
    if (left + POPUP_W > box.width - GAP) left = markerX - GAP - POPUP_W
    left = Math.min(Math.max(GAP, left), Math.max(GAP, box.width - POPUP_W - GAP))

    let top = markerY - height / 2
    top = Math.min(Math.max(GAP, top), Math.max(GAP, box.height - height - GAP))

    setPlace({ left, top })
  }, [popupOpen, selectedId, zoom, stations.length])

  return (
    <section className="flex flex-col rounded-xl border border-cc-grey/15 bg-white">
      <header className="flex items-start justify-between gap-6 px-6 pt-5 pb-4">
        <div>
          <h2 className="text-[15px] font-bold text-cc-primary">Live Risk Map</h2>
          <p className="pt-0.5 text-[13px] text-cc-grey">
            Air quality, heat and environmental risks across the MTA subway system.
          </p>
        </div>
        <ul className="flex shrink-0 items-center gap-4 pt-1">
          {LEVEL_LEGEND.map((band) => (
            <li key={band.level} className="flex items-center gap-1.5 text-[12px] text-cc-primary">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: LEVEL_COLOR[band.level] }}
              />
              {band.label}
            </li>
          ))}
        </ul>
      </header>

      <div
        ref={boxRef}
        onClick={onDismiss}
        className="relative mx-4 mb-4 min-h-[460px] flex-1 overflow-hidden rounded-lg bg-[#0B1B3F]">
        <svg
          viewBox="0 0 100 62"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          <rect width="100" height="62" fill="#0B1B3F" />
          <g stroke="#24407D" strokeWidth="0.18" opacity="0.7">
            {[10, 20, 30, 40, 50].map((y) => (
              <line key={y} x1="0" y1={y} x2="100" y2={y} />
            ))}
            {[20, 40, 60, 80].map((x) => (
              <line key={x} x1={x} y1="0" x2={x} y2="62" />
            ))}
          </g>
        </svg>

        <div
          className="absolute inset-0 origin-center transition-transform duration-200"
          style={{ transform: `scale(${zoom})` }}
        >
        {boroughLabels(placed, project).map((label) => (
          <span
            key={label.name}
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 text-[11px] font-semibold tracking-wide text-white/35"
            style={{ left: `${label.x}%`, top: `${label.y}%` }}
          >
            {label.name}
          </span>
        ))}

        {placed.map((station) => {
          const { x, y } = project(station)
          const selected = station.id === selectedId
          return (
            <button
              key={station.id}
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onSelect(station.id)
              }}
              title={`${station.name} — ${station.levelName ?? 'no data'}`}
              aria-label={`${station.name}, ${station.levelName ?? 'no data'}`}
              className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full transition-[width,height]"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                width: selected ? 14 : 7,
                height: selected ? 14 : 7,
                background: LEVEL_COLOR[station.level ?? 1] ?? '#7C858C',
                boxShadow: selected
                  ? '0 0 0 3px rgba(255,255,255,0.95)'
                  : '0 0 0 0.5px rgba(0,0,0,0.35)',
                zIndex: selected ? 2 : 1,
              }}
            />
          )
        })}
        </div>

        <div className="absolute top-3 right-3 flex flex-col gap-1.5" onClick={(e) => e.stopPropagation()}>
          <MapButton label="Zoom in" onClick={() => setZoom((z) => Math.min(3, +(z + 0.4).toFixed(1)))}>+</MapButton>
          <MapButton label="Zoom out" onClick={() => setZoom((z) => Math.max(1, +(z - 0.4).toFixed(1)))}>−</MapButton>
          <MapButton label="Reset view" onClick={() => setZoom(1)}>
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-none stroke-current stroke-[1.5]">
              <circle cx="8" cy="8" r="4.5" />
              <path d="M8 1v2M8 13v2M1 8h2M13 8h2" />
            </svg>
          </MapButton>
        </div>

        {popupOpen && selected && place && (
          <div
            ref={popupRef}
            onClick={(event) => event.stopPropagation()}
            className="absolute z-20"
            style={{
              left: place.left,
              top: place.top,
              width: POPUP_W,
              maxHeight: Math.min(POPUP_MAX_H, (boxRef.current?.clientHeight ?? 500) - 2 * GAP),
            }}
          >
            {popup}
          </div>
        )}

        <p className="pointer-events-none absolute right-3 bottom-2 rounded bg-[#0B1B3F]/80 px-1.5 py-0.5 text-[10px] text-white/55">
          {placed.length} stations · live outdoor readings, modelled platform values
        </p>
      </div>
    </section>
  )
}
