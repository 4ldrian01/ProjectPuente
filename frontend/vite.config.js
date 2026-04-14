import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react-swc'
import { VitePWA } from 'vite-plugin-pwa'

/* global process */
const disablePwaForCurrentPath = process.cwd().includes("'")
const preferredLocalHost = 'projectpuente.local'

// https://vite.dev/config/
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: [preferredLocalHost, 'localhost', '127.0.0.1'],
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
  plugins: [
    tailwindcss(),
    react(),
    VitePWA({
      disable: disablePwaForCurrentPath,
      registerType: 'autoUpdate',
      includeAssets: ['vinta.svg'],
      manifest: false,  // Using manual manifest.json in public/
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /\/api\/health\//,
            handler: 'NetworkFirst',
            options: { cacheName: 'health-cache', expiration: { maxEntries: 1 } },
          },
          {
            urlPattern: /\/api\/wiki\//,
            handler: 'NetworkFirst',
            options: { cacheName: 'wiki-cache', expiration: { maxEntries: 50, maxAgeSeconds: 86400 } },
          },
        ],
      },
    }),
  ],
})
