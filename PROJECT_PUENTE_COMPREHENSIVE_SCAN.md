# Project Puente - Comprehensive Repository Scan (Refreshed)

Generated: 2026-04-14T05:41:18+08:00  
Workspace: /home/rauf/Desktop/Machine Learning/ProjectPuente  
Branch: main

This document replaces stale scan data with a current, source-backed refresh.
All statements below are tied to file reads, git output, command runs, and live endpoint probes executed in this session.

---

## 0) Evidence and Method

### 0.1 Commands and Probes Run

- Git inventory:
  - `git branch --show-current`
  - `git ls-files | wc -l`
  - `git status --short`
- Backend runtime probes:
  - `GET /`
  - `GET /api/health/`
  - `POST /api/translate/`
  - `POST /api/btvl/`
  - `POST /api/tts/`
  - `GET /api/telemetry/`
  - `GET /api/wiki/`
- Validation commands:
  - `backend/manage.py test`
  - `frontend npm run lint`
  - `frontend npm run build`
  - `ml_models/training_preflight.py`
- DB and migration checks:
  - `manage.py showmigrations`
  - `manage.py shell -c` for `CulturalTerm` and `TranslationLog` counts
- Dataset checks:
  - JSON entry count and unique language/category counts
  - SHA-256 comparison between canonical and frontend runtime JSON copies

### 0.2 Scope Clarification

- Backend was actively probed on `127.0.0.1:8000`.
- Frontend dev server was **not** running during this pass (`127.0.0.1:5173` returned connection refused).
- Frontend quality state was verified via lint/build, not live dev-server probe.

---

## 1) Repository Snapshot (Current)

### 1.1 Git Summary

- Branch: `main`
- Tracked files: `187`
- Git status lines: `19`
- Modified tracked files: `15`
- Untracked entries: `4`

### 1.2 Current `git status --short`

```text
 M CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md
 M README.md
 M backend/README.md
 M frontend/README.md
 M frontend/package-lock.json
 M frontend/package.json
 M frontend/src/components/screens/DatabaseAdminScreen.jsx
 M frontend/src/components/screens/SystemEvaluationScreen.jsx
 M frontend/src/components/screens/TranslateScreen.jsx
 M frontend/src/components/screens/WikiVozScreen.jsx
 M frontend/src/main.jsx
 M frontend/vite.config.js
 M ml_models/README.md
 M ml_models/training_preflight_report.json
 M package-lock.json
?? datasets/processed/pillars/parallel/wiki_voz_kb.json
?? frontend/public/data/
?? frontend/src/lib/dbAdminImport.js
?? frontend/src/lib/wikiVozLexicon.js
```

### 1.3 Scan Delta vs Previous Report

The prior scan had stale counts and stale assumptions. Corrected now:

- Tracked files are `187` (not `136`).
- Backend tests are `57` (not `46`).
- Wiki DB is populated (`25` rows), not empty.
- `core_api` migration `0005_translationlog_route_confidence` exists and is applied.
- `SystemEvaluationScreen.jsx` is tracked and ECharts-based.
- `WikiVozScreen.jsx` is local-JSON driven (not API-fallback driven).

---

## 2) Runtime Validation (Live)

### 2.1 Backend Endpoint Matrix

| Endpoint | HTTP | Observed Result |
|---|---:|---|
| `/` | 200 | `status: online`, `engine: offline-model-missing` |
| `/api/health/` | 200 | `nllb_loaded=false`, `tts_available=true`, `cloud_fallback_allowed=false` |
| `/api/translate/` | 503 | `error_code: model.local.unavailable`, `retryable: true` |
| `/api/btvl/` | 503 | `error_code: model.local.unavailable`, `retryable: true` |
| `/api/tts/` | 200 | Binary MP3 response; header `X-TTS-Voice: en-US-EmmaMultilingualNeural` |
| `/api/telemetry/` | 200 | `status: ok`; RAM/GPU objects present |
| `/api/wiki/` | 200 | Returns `results` array (length observed: `25`) |

### 2.2 Canonical Runtime Payload Facts

From captured JSON responses:

- Root:
  - `engine: offline-model-missing`
  - endpoint map includes `translate`, `btvl`, `logs`, `telemetry`, `tts`, `wiki_voz`, `health`
- Health:
  - `status: ok`
  - `nllb_loaded: false`
  - `lora_adapters: []`
  - `tts_engine: edge-tts`
  - `strict_offline_mode: false`
  - `cloud_fallback_allowed: false`
  - `inference_mode: offline-local-only`
- Translate/BTVL:
  - both return `model.local.unavailable`
- Telemetry:
  - `gpu.available: false`
  - `gpu.reason: torch-and-gputil-unavailable`

### 2.3 Frontend Runtime Probe State

- `http://127.0.0.1:5173/` was not reachable in this session (`curl` exit code `7`).
- Frontend build verification is included in Section 3.

---

## 3) Quality and Validation Runs (Current)

### 3.1 Backend Tests

Command:

- `backend/manage.py test`

Result:

- Found `57` tests
- `57/57` passed
- Exit code `0`

### 3.2 Frontend Lint

Command:

- `frontend npm run lint`

Result:

- Passed (`eslint .`)
- Exit code `0`

### 3.3 Frontend Build

Command:

- `frontend npm run build`

Result:

- Passed (`vite build`)
- PWA artifacts generated (`sw.js`, `workbox-*.js`)
- Chunk size warning still present for large JS bundle
- Exit code `0`

### 3.4 Training Preflight

Command:

- `ml_models/training_preflight.py`

Result:

- Exit code `2`
- Overall status: `BLOCKED`
- Summary: `PASS=16`, `WARN=2`, `BLOCKER=1`
- Active blocker:
  - Base model directory exists, but no weight file found (`model.safetensors` or `pytorch_model.bin`)
- Warnings include missing modules:
  - `torch`, `transformers`, `peft`, `sacrebleu`, `pandas`, `pdfplumber`

### 3.5 Migration and DB State

- `manage.py showmigrations` shows all listed migrations applied, including:
  - `core_api 0005_translationlog_route_confidence`
- DB counts from shell query:
  - `CulturalTerm: 25`
  - `TranslationLog: 15`

---

## 4) Backend Source Scan Highlights

### 4.1 API Contract and Flow

`backend/core_api/views.py` currently implements:

- Translation flow with:
  - API key gate (optional)
  - serializer validation
  - greedy Wiki-Voz phrase interception
  - Translation Memory cache lookup
  - same-language short-circuit
  - local NLLB path
  - observer logging
- Back-translation verification endpoint (`/api/btvl/`)
- TTS endpoint (`/api/tts/`) via `edge-tts`
- Wiki listing/search endpoint (`/api/wiki/`)
- Telemetry endpoint (`/api/telemetry/`)
- Health endpoint (`/api/health/`)

### 4.2 Model Loader

`backend/core_api/apps.py` confirms:

- Singleton loader state in `CoreApiConfig`
- Startup preload gated by `PUENTE_LOAD_MODEL_ON_STARTUP`
- Local-only model loading contract (`local_files_only=True`)
- Optional LoRA adapter load from `ml_models/lora_adapters/*`

### 4.3 Language and Serializer Contract

- Language scope includes: `auto`, `en`, `es`, `tl`, `cbk`, `hil`, `ceb`
- Translate payload constraints still enforce `text <= 250`
- BTVL and TTS serializers remain aligned with backend contracts

---

## 5) Frontend Source Scan Highlights

### 5.1 Routing and Screen Composition

`frontend/src/App.jsx` currently routes and mounts:

- `translate`
- `wiki-voz`
- `activity-logs`
- `evaluation`
- `db-admin`
- `settings`

### 5.2 Translate Screen

`frontend/src/components/screens/TranslateScreen.jsx` now includes:

- Lexicon hook integration:
  - `useWikiVozLexicon`
  - local path: `/data/wiki_voz_kb.json`
- Multi-match dedupe/merge of backend wiki hit plus local lexicon hits
- BTVL controls and telemetry polling

### 5.3 Wiki-Voz Screen

`frontend/src/components/screens/WikiVozScreen.jsx` is currently:

- Data-driven from local JSON path `/data/wiki_voz_kb.json`
- Dynamic language and category filters derived from loaded entries
- Search sanitation and memoized filter pipeline
- Full filtered list rendering (no incremental page-size gate)
- Consistent per-card action button: `View Details`
- Card-level trigger word display and popup integration

### 5.4 Wiki Lexicon Utility

`frontend/src/lib/wikiVozLexicon.js` provides:

- Cached lexicon loader (`loadWikiVozLexicon`)
- Cache reset helper (`resetWikiVozLexiconCache`)
- Longest-first phrase matcher (`findWikiVozMatches`)
- React hook wrapper (`useWikiVozLexicon`)

### 5.5 Evaluation Screen and Chart Stack

`frontend/src/components/screens/SystemEvaluationScreen.jsx` now uses:

- `echarts`
- `echarts-for-react`

with modular ECharts imports (`echarts/core`, chart/components, renderer registration).

### 5.6 Frontend Bootstrap and PWA Hardening

- `frontend/src/main.jsx` has global stale-chunk recovery:
  - listener for `vite:preloadError` with forced reload
- `frontend/vite.config.js` includes Workbox hardening:
  - `cleanupOutdatedCaches: true`
  - `clientsClaim: true`
  - `skipWaiting: true`

### 5.7 Frontend Dependencies

`frontend/package.json` now includes:

- `echarts`
- `echarts-for-react`

No `recharts` dependency exists in current frontend package manifest.

---

## 6) Data and Model Asset Scan

### 6.1 Wiki-Voz JSON Runtime Asset

Runtime file exists:

- `frontend/public/data/wiki_voz_kb.json`

Observed facts:

- Entry count: `165`
- Distinct language values: `4`
- Distinct category values: `5`

### 6.2 Canonical-to-Frontend Sync Check

Compared files:

- `datasets/processed/pillars/parallel/wiki_voz_kb.json`
- `frontend/public/data/wiki_voz_kb.json`

SHA-256 checksums are identical:

- `c00c00c723c5b5ee1f5a4f6fc36f2e9681062d1f947eab84dc22ae6c125096fd`

### 6.3 Model Availability State

Training preflight and runtime endpoints both confirm local translation remains blocked due missing base model weights in:

- `ml_models/nllb-200-distilled-600M`

---

## 7) Active Risks and Consistency Gaps

1. Translation path unavailable in runtime
- `/api/translate/` and `/api/btvl/` return `503` because local model weights are missing.

2. Training readiness blocked
- Preflight blocker still active on base model completeness.

3. Python ML stack incomplete in current interpreter
- Missing modules reported by preflight (`torch`, `transformers`, `peft`, etc.).

4. Untracked source artifacts in active workspace
- `datasets/processed/pillars/parallel/wiki_voz_kb.json`
- `frontend/public/data/`
- `frontend/src/lib/dbAdminImport.js`
- `frontend/src/lib/wikiVozLexicon.js`

5. Frontend runtime not currently active during scan
- Dev server not running at `127.0.0.1:5173`; only lint/build was validated.

---

## 8) Immediate Next Actions

1. Install/restore NLLB base model weights in `ml_models/nllb-200-distilled-600M`, then rerun translate/BTVL probes.
2. Decide commit policy for currently untracked but operational files (Wiki JSON source/runtime copies and helper libs).
3. Install missing ML dependencies in the canonical Python environment before full training/evaluation runs.
4. Start frontend dev server and perform live UX smoke check for Wiki-Voz and ECharts screens.

---

## 9) Final Status (This Pass)

- Repository scan is now aligned to **current** git state, source files, runtime probes, and validation commands.
- Previously stale claims (counts, wiki emptiness, charting stack, tracking status, test totals) were corrected.
- Runtime-critical blocker remains: local model weights are missing.
