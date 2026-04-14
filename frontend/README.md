# Frontend Setup

The frontend is a React 19 + Vite 7 progressive web app that talks to the Django backend over LAN.

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Node.js | 20+ | Needed for Vite and the React toolchain |
| npm | 9+ | Comes with Node.js |
| Python | No | Backend only |

Local fallback supported by launcher:

- If system Node/npm is missing, place a local runtime at `.tools/node/bin` (used automatically by `run_project.sh`).

## Runtime dependencies (`dependencies`)

| Package | Purpose |
|---|---|
| `axios` | HTTP client for `/api/translate/`, `/api/wiki/`, `/api/health/`, and `/api/tts/` |
| `echarts` | High-performance charting engine for telemetry and evaluation visualizations |
| `echarts-for-react` | React wrapper for ECharts components |
| `lucide-react` | Icon set used across UI panels and controls |
| `react` | UI runtime |
| `react-dom` | Browser renderer |
| `react-is` | React runtime compatibility helpers used by charting/tooling integrations |

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
| `@types/react` | React types for tooling |
| `@types/react-dom` | React DOM types for tooling |

Compatibility note:

- `vite-plugin-pwa` is pinned to the Vite 7-compatible line (`^1.2.0`).

## Frontend features that depend on the backend

| Feature | Backend dependency |
|---|---|
| Translation | `/api/translate/` |
| Back-translation verification | `/api/btvl/` |
| Wiki-Voz API mode | `/api/wiki/` |
| TTS buttons | `/api/tts/` with backend `edge-tts` installed |
| Health badge / settings | `/api/health/` |
| Hardware telemetry panel | `/api/telemetry/` |

## Optional frontend environment variables

Copy `frontend/.env.example` to `frontend/.env` only when needed:

| Variable | Required | Purpose |
|---|---:|---|
| `VITE_PUENTE_API_KEY` | Optional | Sends `X-API-Key` header for `/api/translate/`, `/api/btvl/`, and `/api/tts/` when backend protection is enabled |

## Notes

- The frontend still works with offline seed data for Wiki-Voz when the backend wiki API is unavailable.
- The TTS buttons now use the backend `edge-tts` endpoint instead of the browser Web Speech API.
- The frontend automatically derives the API host from `window.location.hostname`, so it stays LAN-friendly without hardcoded IP addresses.
- If backend API-key protection is enabled, you must set `VITE_PUENTE_API_KEY` or write actions will be rejected with HTTP 401.
