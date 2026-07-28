import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// design.md D20: proxy /api/* to the FastAPI backend so the browser only
// ever sees ONE origin (this dev server's) -- avoids needing CORS
// middleware on either side, in dev and during Playwright verification.
const BACKEND_URL = 'http://127.0.0.1:8420'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false, // design.md AC-07.2 -- public/manifest.json is hand-authored
      includeManifestIcons: false,
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
})
