import { readFileSync } from 'node:fs'

import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Ship MapLibre's tile worker with the build.
 *
 * The bundle asks for `assets/maplibre-gl-worker.mjs` at runtime, but Rollup
 * does not emit it — and an SPA fallback answers the request with index.html
 * and a 200, so the worker receives HTML, dies on parse, and the map's `load`
 * event never fires. Nothing errors: the canvas mounts, the style downloads,
 * and anything gated on `load` (the station popup) is simply dead.
 *
 * The worker imports `maplibre-gl-shared.mjs` as a sibling, so both files
 * have to land in the same directory or the worker dies on that import
 * instead.
 */
function maplibreWorker(): Plugin {
  return {
    name: 'crewcare:maplibre-worker',
    apply: 'build',
    generateBundle() {
      for (const name of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) {
        this.emitFile({
          type: 'asset',
          fileName: `assets/${name}`,
          source: readFileSync(new URL(`./node_modules/maplibre-gl/dist/${name}`, import.meta.url)),
        })
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), maplibreWorker()],
  server: {
    // Production serves the API from the same origin (Vercel routes
    // /api/ops/* to the Python function). Proxying here means local dev and
    // preview route the same way, so a path that works in one works in both.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
    // Vite rejects requests whose Host header it does not recognise. When the
    // dev server is exposed through a tunnel for phone testing, the tunnel's
    // hostname has to be allowed or every request 403s.
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app', '.ngrok.io'],
  },
  optimizeDeps: {
    // MapLibre ships its renderer as a web worker. Vite's dep pre-bundling
    // rewrites the import and the worker then 404s, leaving an empty map
    // canvas with no error in the page — excluding it keeps the worker intact.
    exclude: ['maplibre-gl'],
  },
  preview: {
    // Production serves the API from the same origin (Vercel routes
    // /api/ops/* to the Python function). Proxying here means local dev and
    // preview route the same way, so a path that works in one works in both.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    // Inline every asset we ship, so the built demo issues no requests of its
    // own beyond the document itself.
    assetsInlineLimit: 16384,
  },
})
