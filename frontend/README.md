# Frontend Setup

The frontend is a React 19 + Vite 7 progressive web app that talks to the Django backend over LAN.

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Node.js | 18+ | Needed for Vite and the React toolchain |
| npm | 9+ | Comes with Node.js |
| Python | No | Backend only |

## Runtime dependencies (`dependencies`)

| Package | Purpose |
|---|---|
| `axios` | HTTP client for `/api/translate/`, `/api/wiki/`, `/api/health/`, and `/api/tts/` |
| `react` | UI runtime |
| `react-dom` | Browser renderer |

## Development/build dependencies (`devDependencies`)

| Package | Purpose |
|---|---|
| `vite` | Dev server and production bundler |
| `@vitejs/plugin-react-swc` | Fast React transform with SWC |
| `vite-plugin-pwa` | Service worker + PWA integration |
| `@eslint/js` | ESLint base config |
| `eslint` | Linting |
| `eslint-plugin-react-hooks` | React Hooks lint rules |
| `eslint-plugin-react-refresh` | React refresh lint rules |
| `globals` | Shared ESLint globals |
| `tailwindcss` | Utility CSS framework |
| `@tailwindcss/vite` | Tailwind integration for Vite |
| `postcss` | CSS transform pipeline |
| `autoprefixer` | Vendor prefixing |
| `@types/react` | React types for tooling |
| `@types/react-dom` | React DOM types for tooling |

## Frontend features that depend on the backend

| Feature | Backend dependency |
|---|---|
| Translation | `/api/translate/` |
| Wiki-Voz API mode | `/api/wiki/` |
| TTS buttons | `/api/tts/` with backend `edge-tts` installed |
| Health badge / settings | `/api/health/` |

## Notes

- The frontend still works with offline seed data for Wiki-Voz when the backend wiki API is unavailable.
- The TTS buttons now use the backend `edge-tts` endpoint instead of the browser Web Speech API.
- The frontend automatically derives the API host from `window.location.hostname`, so it stays LAN-friendly without hardcoded IP addresses.
