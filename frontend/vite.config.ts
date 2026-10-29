/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// During development the Vite server proxies /api to the backend, so the browser talks to a
// single origin. That keeps session cookies (Phase 3) same-site without loosening CORS.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // ws: true forwards the /api/v1/events WebSocket (live notifications) as well.
      '/api': { target: apiProxyTarget, changeOrigin: false, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Fixed time zone so formatted timestamps are the same on every machine.
    env: { TZ: 'UTC' },
    restoreMocks: true,
    unstubGlobals: true,
  },
})
