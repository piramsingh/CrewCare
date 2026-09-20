/**
 * Extract the Material Symbols paths the sidebar uses into a TS module.
 *
 * The icons come from Google's `@material-symbols/svg-400` package (Apache
 * 2.0) rather than the Google Fonts webfont, because a font link would be a
 * network request and this app makes none. Only the handful of glyphs
 * actually used are inlined, so the bundle carries bytes for seven icons
 * rather than for several thousand.
 *
 * Run: npm run build:icons
 */
import { readFileSync, writeFileSync } from 'node:fs'

const ICONS = [
  'home',
  'location_on',
  'chat',
  'bar_chart',
  'notifications',
  'description',
  'settings',
] as const

const SRC = (name: string) =>
  new URL(`../node_modules/@material-symbols/svg-400/outlined/${name}.svg`, import.meta.url)

const entries = ICONS.map((name) => {
  const svg = readFileSync(SRC(name), 'utf8')
  const path = svg.match(/ d="([^"]+)"/)?.[1]
  if (!path) throw new Error(`no path in ${name}.svg`)
  return `  ${name}:\n    '${path}',`
})

writeFileSync(
  new URL('../src/components/materialIcons.ts', import.meta.url),
  `/**
 * Material Symbols glyph paths, generated — do not edit by hand.
 *
 * Source: @material-symbols/svg-400 (Google, Apache 2.0), outlined weight 400.
 * Regenerate with: npm run build:icons
 *
 * These are inlined rather than loaded from the Google Fonts CDN, which would
 * be a network request. All paths share the 0 -960 960 960 viewBox Material
 * Symbols uses.
 */
export const MATERIAL_VIEWBOX = '0 -960 960 960'

export const MATERIAL_ICONS = {
${entries.join('\n')}
} as const

export type MaterialIconName = keyof typeof MATERIAL_ICONS
`,
)
console.log(`wrote ${ICONS.length} icon paths`)
