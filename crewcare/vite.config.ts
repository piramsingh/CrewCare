import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
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
  build: {
    // Inline every asset we ship, so the built demo issues no requests of its
    // own beyond the document itself.
    assetsInlineLimit: 16384,
  },
})
