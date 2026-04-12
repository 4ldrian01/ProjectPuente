# Frontend Setup

The frontend is a React 19 + Vite 7 app for translation UX, observer dashboards, and operations panels.

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Node.js | 18+ | Vite runtime/tooling |
| npm | 9+ | Package manager |
| Python | No | Backend only |

## Runtime dependencies (`dependencies`)

| Package | Purpose |
|---|---|
| `react` | UI runtime |
| `react-dom` | Browser renderer |
| `axios` | API requests |
| `lucide-react` | Icon system |
| `recharts` | Evaluation charts |
| `react-is` | React utility compatibility |

## Development/build dependencies (`devDependencies`)

| Package | Purpose |
|---|---|
| `vite` | Dev server + build |
| `@vitejs/plugin-react-swc` | Fast React transform |
| `vite-plugin-pwa` | PWA build integration |
| `@tailwindcss/vite` | Tailwind + Vite integration |
| `tailwindcss` | Utility CSS framework |
| `eslint` + plugins | Linting |
| `@types/react` / `@types/react-dom` | Tooling support |

## Screens currently wired in app shell

- `TranslateScreen`
- `WikiVozScreen`
- `ActivityLogsScreen`
- `DatabaseAdminScreen`
- `SystemEvaluationScreen`
- `SettingsScreen`

Layout shell components:

- `GlobalHeader`
- `SidebarNav`
- `ToastViewport`

## Backend integrations

| Feature | Endpoint |
|---|---|
| Translation | `/api/translate/` |
| BTVL | `/api/btvl/` |
| Wiki entries | `/api/wiki/` |
| Activity logs | `/api/logs/` |
| TTS | `/api/tts/` |
| Health status | `/api/health/` |
| Telemetry | `/api/telemetry/` |

## Runtime host behavior

`src/lib/apiRuntime.js` handles:

- host detection from browser runtime
- `projectpuente.local` preference when reachable
- fallback to localhost aliases
- health-based API URL resolution

## Optional frontend environment variables

Copy `frontend/.env.example` to `frontend/.env` only when needed:

| Variable | Required | Purpose |
|---|---:|---|
| `VITE_PUENTE_API_KEY` | Optional | Adds `X-API-Key` to protected write requests |

## Run and verify

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --strictPort
npm run lint
npm run build
```

## Notes

- Wiki-Voz screen falls back to local seed data when API data is unavailable or empty.
- Local image placeholder fallback is sourced from `public/local-assets/placeholder.jpg`.
- If backend API-key protection is enabled, write actions need `VITE_PUENTE_API_KEY`.
