import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Inline every asset we ship, so the built demo issues no requests of its
    // own beyond the document itself.
    assetsInlineLimit: 16384,
  },
})
