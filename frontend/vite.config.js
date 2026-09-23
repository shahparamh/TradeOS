import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev only: forwards /api and the WS stream to the backend on :8000 so the
    // frontend can always call same-origin relative paths (see services/api.js), matching
    // how the built app is served in production (single FastAPI process, same origin).
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
