import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react-swc'
import { VitePWA } from 'vite-plugin-pwa'

/* global process */
const disablePwaForCurrentPath = process.cwd().includes("'")

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
    VitePWA({
      disable: disablePwaForCurrentPath,
      registerType: 'autoUpdate',
      includeAssets: ['vinta.svg'],
      manifest: false,  // Using manual manifest.json in public/
      workbox: {
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
