import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  LngLatBounds,
  Map as MapLibreMap,
  type GeoJSONSource,
  type MapLayerMouseEvent,
  type MapMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

import { LEVEL_COLOR, LEVEL_LEGEND, type OpsStation } from '../../api/ops'

/**
 * The station map.
 *
 * Real coordinates from the spine on a real basemap, so the streets a station
 * sits on are visible. Tiles are CARTO's dark-matter vector style over
 * OpenStreetMap data: no API key, and dark enough that the risk colours stay
 * the brightest thing on the panel, which is the one job the map has.
 *
 * Markers are a GPU circle layer rather than 496 absolutely-positioned nodes —
 * DOM markers have to be repositioned on every frame of a pan, and at this
 * count that drops frames. The trade is keyboard reach, so the same stations
 * are also rendered as a visually-hidden button list below the canvas.
 *
 * Everything around the canvas — panel, header, legend, zoom buttons, popup
 * placement and the caption — is unchanged from the hand-projected version
 * this replaces.
 */
const BASEMAP = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/** Bounds padding, in pixels, when framing the whole network. */
const FIT_PAD = 28

const SOURCE = 'stations'
const LAYER = 'station-dots'
const LAYER_SELECTED = 'station-selected'

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

const POPUP_W = 340
//: Tall enough for the metrics and three reports, short enough that the map
//: it sits on is still readable around it.
const POPUP_MAX_H = 430
const GAP = 14

/** Level colour as a data-driven style expression, from the same table the legend uses. */
function colorExpression() {
  const match: (string | number | string[])[] = ['match', ['get', 'level']]
  for (const [level, color] of Object.entries(LEVEL_COLOR)) {
    match.push(Number(level), color)
  }
  match.push('#7C858C') // no level modelled
  return match
}

function toFeatureCollection(stations: OpsStation[]) {
  return {
    type: 'FeatureCollection' as const,
    features: stations.map((station) => ({
      type: 'Feature' as const,
      id: station.id,
      properties: {
        id: station.id,
        level: station.level ?? 0,
        name: station.name ?? '',
      },
      geometry: {
        type: 'Point' as const,
        coordinates: [station.lon as number, station.lat as number],
      },
    })),
  }
}

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
  const canvasRef = useRef<HTMLDivElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null)
  // Bumped on every map move so the popup re-anchors to its marker as the
  // operator pans or zooms underneath it.
  const [view, setView] = useState(0)

  const placed = stations.filter((s) => s.lat != null && s.lon != null)
  const selected = placed.find((s) => s.id === selectedId) ?? null

  const bounds = useCallback(() => {
    const box = new LngLatBounds()
    for (const station of placed) box.extend([station.lon as number, station.lat as number])
    return box
  }, [placed])

  // --- the map itself, created once ---------------------------------------
  useEffect(() => {
    if (!canvasRef.current || mapRef.current) return
    const map = new MapLibreMap({
      container: canvasRef.current,
      style: BASEMAP,
      center: [-73.94, 40.72],
      zoom: 9.6,
      attributionControl: { compact: true },
      // Bottom-left: the caption owns the bottom-right corner.
      canvasContextAttributes: {
        // Without this the WebGL buffer is cleared before anything can read it,
        // so the map is invisible to canvas exports and headless screenshots —
        // which is how the demo gets captured for slides.
        preserveDrawingBuffer: true,
      },
    })
    mapRef.current = map
    // Dev-only handle, so a browser test can project a station's coordinates
    // to a screen point and click the right pixel.
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__map = map

    map.on('load', () => {
      const attribution = map.getContainer().querySelector<HTMLElement>(
        '.maplibregl-ctrl-bottom-right',
      )
      if (attribution) {
        attribution.style.right = 'auto'
        attribution.style.left = '0'
      }
      map.addSource(SOURCE, { type: 'geojson', data: toFeatureCollection(placed) })
      map.addLayer({
        id: LAYER,
        type: 'circle',
        source: SOURCE,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 3.5, 12, 6, 15, 9],
          'circle-color': colorExpression() as never,
          'circle-stroke-width': 0.5,
          'circle-stroke-color': 'rgba(0,0,0,0.35)',
        },
      })
      map.addLayer({
        id: LAYER_SELECTED,
        type: 'circle',
        source: SOURCE,
        filter: ['==', ['get', 'id'], ''],
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 7, 12, 9, 15, 12],
          'circle-color': colorExpression() as never,
          'circle-stroke-width': 3,
          'circle-stroke-color': 'rgba(255,255,255,0.95)',
        },
      })
      if (placed.length) map.fitBounds(bounds(), { padding: FIT_PAD, animate: false })
      setReady(true)
    })

    map.on('click', LAYER, (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (feature) onSelect(String(feature.properties?.id))
    })
    // A click on the basemap itself dismisses, matching the old behaviour of
    // clicking the panel background.
    map.on('click', (event: MapMouseEvent) => {
      const hits = map.queryRenderedFeatures(event.point, { layers: [LAYER, LAYER_SELECTED] })
      if (!hits.length) onDismiss()
    })
    // Tile, style and WebGL failures arrive here and nowhere else; without a
    // handler the panel just stays empty with nothing in the console.
    map.on('error', (event) => console.error('[maplibre]', event.error?.message ?? event))
    map.on('mouseenter', LAYER, () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', LAYER, () => (map.getCanvas().style.cursor = ''))
    map.on('move', () => setView((v) => v + 1))

    return () => {
      map.remove()
      mapRef.current = null
    }
    // Created once: later station updates go through the source below.
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // --- data and selection updates -----------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const source = map.getSource(SOURCE) as GeoJSONSource | undefined
    source?.setData(toFeatureCollection(placed))
  }, [ready, placed])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || !map.getLayer(LAYER_SELECTED)) return
    map.setFilter(LAYER_SELECTED, ['==', ['get', 'id'], selectedId ?? ''])
  }, [ready, selectedId])

  /**
   * Anchor the popup beside its marker, then keep it inside the map.
   *
   * Preferred side is right of the marker; it flips left when that would
   * overflow, and the result is clamped on both axes, so a marker at any
   * edge still gets a fully visible card.
   */
  useLayoutEffect(() => {
    const map = mapRef.current
    if (!popupOpen || !selected || !boxRef.current || !map || !ready) {
      setPlace(null)
      return
    }
    const box = boxRef.current.getBoundingClientRect()
    const height = Math.min(popupRef.current?.offsetHeight ?? 320, POPUP_MAX_H)
    const point = map.project([selected.lon as number, selected.lat as number])

    let left = point.x + GAP
    if (left + POPUP_W > box.width - GAP) left = point.x - GAP - POPUP_W
    left = Math.min(Math.max(GAP, left), Math.max(GAP, box.width - POPUP_W - GAP))

    let top = point.y - height / 2
    top = Math.min(Math.max(GAP, top), Math.max(GAP, box.height - height - GAP))

    setPlace({ left, top })
  }, [popupOpen, selectedId, ready, view, stations.length])

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
        className="relative mx-4 mb-4 min-h-[460px] flex-1 overflow-hidden rounded-lg bg-[#0B1B3F]">
        {/* h-full as well as inset-0: maplibre-gl.css sets position:relative on
            its own container, which beats the absolute positioning and would
            otherwise collapse the map to zero height. */}
        <div ref={canvasRef} className="absolute inset-0 h-full w-full" />

        {/* Keyboard and screen-reader reach for markers the GPU layer draws. */}
        <ul className="sr-only">
          {placed.map((station) => (
            <li key={station.id}>
              <button type="button" onClick={() => onSelect(station.id)}>
                {station.name}, {station.levelName ?? 'no data'}
              </button>
            </li>
          ))}
        </ul>

        <div className="absolute top-3 right-3 z-10 flex flex-col gap-1.5">
          <MapButton label="Zoom in" onClick={() => mapRef.current?.zoomIn()}>+</MapButton>
          <MapButton label="Zoom out" onClick={() => mapRef.current?.zoomOut()}>−</MapButton>
          <MapButton
            label="Reset view"
            onClick={() =>
              placed.length && mapRef.current?.fitBounds(bounds(), { padding: FIT_PAD })
            }
          >
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

        <p className="pointer-events-none absolute right-3 bottom-2 z-10 rounded bg-[#0B1B3F]/80 px-1.5 py-0.5 text-[10px] text-white/55">
          {placed.length} stations · live outdoor readings, modelled platform values
        </p>
      </div>
    </section>
  )
}
