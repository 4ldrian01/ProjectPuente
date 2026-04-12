# PUENTE

**Preserving Understanding through Enhanced Neural Translation Engines**

Offline-first LAN translation platform with:

- Django + DRF backend
- React + Vite frontend
- Local NLLB translation engine
- Optional LoRA adapters
- Optional Edge TTS
- Wiki-Voz cultural context integration

Last synchronized: 2026-04-10

This README is source-synced to the current repository state and runtime checks from this machine.

---

## 1) Project Summary

PUENTE is a local-first translation system focused on Philippine languages and sociolinguistic nuance.

Current implementation supports:

- Translation with local NLLB inference (`/api/translate/`)
- Direct many-to-many routing with confidence-gated proximate pivot fallback
- Optional formal/street register mode via LoRA adapters
- Translation Memory cache lookup before model inference
- Greedy Wiki-Voz phrase interception for cultural term context
- Back-Translation Verification Loop (BTVL)
- Optional speech synthesis endpoint via `edge-tts`
- Hardware telemetry endpoint (RAM/GPU)
- Observer activity logs endpoint (`/api/logs/`)
- Expanded frontend operations suite (Activity Logs, DB Admin, System Evaluation)

---

## 2) Source Of Truth And Scope

Primary files used to sync this README:

- `backend/backend/settings.py`
- `backend/backend/urls.py`
- `backend/core_api/languages.py`
- `backend/core_api/serializers.py`
- `backend/core_api/models.py`
- `backend/core_api/views.py`
- `backend/core_api/apps.py`
- `backend/core_api/tests.py`
- `backend/core_api/management/commands/ingest_lexicon.py`
- `frontend/src/App.jsx`
- `frontend/src/components/screens/TranslateScreen.jsx`
- `frontend/src/components/screens/WikiVozScreen.jsx`
- `frontend/src/components/screens/SettingsScreen.jsx`
- `frontend/src/components/screens/ActivityLogsScreen.jsx`
- `frontend/src/components/screens/DatabaseAdminScreen.jsx`
- `frontend/src/components/screens/SystemEvaluationScreen.jsx`
- `frontend/src/components/layout/GlobalHeader.jsx`
- `frontend/src/components/layout/SidebarNav.jsx`
- `frontend/src/lib/apiRuntime.js`
- `frontend/src/lib/settings.js`
- `frontend/src/lib/apiAuth.js`
- `frontend/src/lib/ttsClient.js`
- `frontend/vite.config.js`
- `run_project.sh`
- `run_project.ps1`
- `run_project.bat`
- `package.json`
- `frontend/package.json`
- `backend/requirements.txt`
- `notebooks/scripts/requirements_colab.txt`

---

## 3) Verified Feature Inventory

### 3.1 Backend API features

| Feature | Status | Implementation |
|---|---|---|
| API root | Present | `APIRootView` |
| Translation endpoint | Present | `TranslateView` |
| BTVL endpoint | Present | `BackTranslationVerifyView` |
| TTS endpoint | Present | `TextToSpeechView` |
| Wiki-Voz endpoint | Present | `WikiVozView` |
| Translation logs endpoint | Present | `TranslationLogListView` |
| Telemetry endpoint | Present | `telemetry_view` |
| Health endpoint | Present | `HealthCheckView` |
| Optional API key protection | Present | `_require_api_key_or_401` + `PUENTE_API_KEY` |
| Translation Memory cache | Present | `_find_translation_memory_hit` |
| Greedy phrase interception | Present | `_find_wiki_voz_phrase_match` |
| Local model singleton load | Present | `CoreApiConfig.ready()` |
| LoRA adapter switching | Present | `set_adapter` + loaded adapter names |
| Lexicon ingestion command | Present | `ingest_lexicon` |
| Translation logging model | Present | `TranslationLog` |
| Wiki terms model | Present | `CulturalTerm` |
| Django Admin for both models | Present | `core_api/admin.py` |

### 3.2 Frontend features

| Area | Status | Implementation |
|---|---|---|
| LAN-aware API URL | Present | `frontend/src/lib/apiRuntime.js` + `App.jsx` |
| projectpuente.local promotion/fallback | Present | `apiRuntime.js` |
| Health polling | Present | every 30s in `App.jsx` |
| Translate screen | Present | `TranslateScreen.jsx` |
| Wiki-Voz screen | Present | `WikiVozScreen.jsx` |
| Activity logs screen | Present | `ActivityLogsScreen.jsx` |
| Database admin screen | Present | `DatabaseAdminScreen.jsx` |
| System evaluation screen | Present | `SystemEvaluationScreen.jsx` |
| Settings screen | Present | `SettingsScreen.jsx` |
| Global desktop header | Present | `GlobalHeader.jsx` |
| Sidebar nav + mobile drawer | Present | `SidebarNav.jsx` |
| Theme persistence | Present | `settings.js` + localStorage |
| Source/target defaults persistence | Present | `settings.js` + localStorage |
| API key header injection | Present | `apiAuth.js` |
| TTS client integration | Present | `ttsClient.js` |
| BTVL trigger UI | Present | Translate screen action strip |
| Error boundary wrapper | Present | `ErrorBoundary.jsx` + `main.jsx` |
| PWA plugin integration | Present | `vite.config.js` + manual manifest |

### 3.3 ML and data tooling features

| Feature | Status | Script |
|---|---|---|
| Download local base model | Present | `ml_models/download_model.py` |
| Local model validation smoke test | Present | `ml_models/validate_model.py` |
| LoRA training script | Present | `ml_models/train_lora.py` |
| Read-only training preflight | Present | `ml_models/training_preflight.py` |
| General BLEU/chrF++ evaluator | Present | `ml_models/evaluate_metrics.py` |
| Pure Spanish baseline evaluator | Present | `ml_models/evaluate_spanish_baseline.py` |
| Parallel pillar builder | Present | `datasets/scripts/pillar1_merge_parallel_corpus.py` |
| Monolingual pillar builder | Present | `datasets/scripts/pillar2_structure_monolingual.py` |
| JSONL conversion (streaming) | Present | `datasets/scripts/json_to_jsonl_stream.py` |
| Legacy archive protocol | Present | `datasets/scripts/archive_legacy_data.py` |
| Notebook master pipeline runner | Present | `notebooks/scripts/run_nllb_pipeline.py` |
| Colab LoRA cloud pipeline | Present | `notebooks/scripts/colab_lora_training_pipeline.py` |

---

## 4) Language Contract

Canonical backend-supported app codes (`backend/core_api/languages.py`):

- `auto`
- `en`
- `es`
- `tl`
- `cbk`
- `hil`
- `ceb`

FLORES mapping:

| App Code | FLORES |
|---|---|
| `en` | `eng_Latn` |
| `es` | `spa_Latn` |
| `tl` | `tgl_Latn` |
| `cbk` | `cbk_Latn` |
| `hil` | `hil_Latn` |
| `ceb` | `ceb_Latn` |
| `auto` | `eng_Latn` |

Contract rules:

- `source_lang` supports `auto`
- `target_lang` excludes `auto`
- Direct inference is attempted first for all language pairs
- English is never selected as a pivot for local-to-local Philippine pairs
- Proximate pivot fallback matrix:
  - `cbk`-involved pair: `es` pivot (when not equal to source/target)
  - local<->local pair: `tl` pivot
  - if `tl` is already in pair: `ceb` secondary pivot

---

## 5) Translation Pipeline (Current Behavior)

For `POST /api/translate/`, execution order is:

1. Optional API key guard (if backend key configured)
2. Serializer validation
3. Wiki-Voz greedy phrase interception
4. Translation Memory cache lookup
5. Same-language passthrough shortcut
6. NLLB translation path (if model loaded)
7. TranslationLog write (success/error metadata)

Neural behavior:

- All pairs run direct inference first
- If direct confidence is critically low, proximate-pivot fallback may run
- Adapter switch attempts `formal` or `street` mode if available
- If model is not loaded, endpoint returns HTTP 503
- Cloud fallback is disabled (`cloud_fallback_allowed=false`)

---

## 6) API Contract

### 6.1 `POST /api/translate/`

Request constraints:

- `text`: max 250 chars
- `source_lang`: `auto,en,es,tl,cbk,hil,ceb`
- `target_lang`: `en,es,tl,cbk,hil,ceb`
- `mode`: `formal` or `street` (default `formal`)

Response includes fields such as:

- `translated_text`
- `model`
- `latency_ms`
- `tokens_in` / `tokens_out`
- `pivot_used`
- `pivot_language`
- `route_strategy`
- `route_confidence`
- `is_cached`
- optional `wiki_voz`

Auth:

- If `PUENTE_API_KEY` is configured, request must include `X-API-Key`.

### 6.2 `POST /api/btvl/`

Request constraints:

- `text`: max 250 chars
- `source_lang`: `en,es,tl,cbk,hil,ceb`
- `target_lang`: `en,es,tl` (defaults to `en`)

Response includes:

- `verified_text`
- latency/tokens/model/pivot metadata

Auth:

- Same optional `X-API-Key` enforcement as translate.

### 6.3 `POST /api/tts/`

Request constraints:

- `text`: max 1000 chars
- `lang_code`: `auto,en,es,tl,cbk,hil,ceb`
- optional `voice`

Response:

- `audio/mpeg` payload
- header `X-TTS-Voice`

Rules:

- Returns 503 in strict offline mode
- Returns 503 if `edge-tts` package unavailable

Auth:

- Same optional `X-API-Key` enforcement.

### 6.4 `GET /api/wiki/`

Behavior:

- with `?q=`: case-insensitive term filter, up to 20 results
- without query: first 100 terms, ordered by term

### 6.5 `GET /api/logs/`

Behavior:

- observer/activity log list with filters:
  - `limit`
  - `status`
  - `source_lang`
  - `target_lang`
  - `q`
- includes `route_strategy` and `pivot_language` normalization in response rows

### 6.6 `GET /api/telemetry/`

Returns structured RAM/GPU metrics:

- RAM used/total/percent
- GPU availability and utilization details

### 6.7 `GET /api/health/`

Returns backend status fields including:

- `engine`
- `nllb_loaded`
- `lora_adapters`
- `api_key_required`
- `tts_available`
- `strict_offline_mode`
- `supported_languages`

### 6.8 `GET /`

Returns:

- project status and endpoint index

---

## 7) Frontend Behavior Details

### 7.1 Translate Screen

Current behavior includes:

- Debounced auto-translate (800 ms)
- Source/target mutual exclusion logic
- Source character guard (`250` max)
- Mode toggle (Formal/Street)
- Source and target TTS actions via backend TTS endpoint
- Copy translation action
- BTVL verification action and diagnostics
- Cultural term inline highlighting with hover tooltip and popup
- Local telemetry/pipeline visual diagnostics panels

### 7.2 Wiki-Voz Screen

Current behavior includes:

- API fetch from `/api/wiki/`
- Fallback to local seed entries if API data unavailable or empty
- Search by term/definition/language/category
- Category and language filters
- Progressive pagination (`20` entries per expansion)
- Masonry-style desktop layout
- Local placeholder fallback for remote/invalid image URLs

### 7.3 Activity Logs Screen

Current behavior includes:

- API fetch from `/api/logs/`
- Status/source/target/query filters
- Route confidence, pivot, and intervention visualization
- Local suppress/delete-from-view behavior
- CSV export

### 7.4 Database Admin Screen

Current behavior includes:

- Mock local CRUD flows for CulturalTerm-style records
- CSV import helper
- API hydration with fallback to local seed dataset

### 7.5 System Evaluation Screen

Current behavior includes:

- static KPI cards + charted sociolinguistic/latency visualizations

### 7.6 Settings Screen

Current behavior includes:

- Theme toggle (dark/light)
- Default source/target persistence
- Live backend/model/TTS/API-key status display
- Health refresh integration

---

## 8) Persistence And Data Models

### 8.1 `CulturalTerm`

Core fields:

- `term` (unique, indexed)
- `definition`
- `image_url`
- `language` (free text)
- `category`
- timestamps

### 8.2 `TranslationLog`

Core fields include:

- request metadata (source/target/mode/input)
- output metadata (output text/tokens/model)
- performance (`latency_ms`)
- status (`success/error/timeout`)
- routing (`pivot_used`, `route_confidence`)
- Wiki-Voz interception markers
- timestamps and indexes

---

## 9) Repository Layout

```text
ProjectPuente/
├── README.md
├── PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
├── TRAINING_PREFLIGHT_CHECKLIST.md
├── CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md
├── agents.md
├── package.json
├── run_project.sh
├── run_project.ps1
├── run_project.bat
├── backend/
├── datasets/
├── frontend/
├── ml_models/
└── notebooks/
```

---

## 10) Dependency Manifests

Project-owned manifests currently present:

- `backend/requirements.txt`
- `frontend/package.json`
- `package.json`
- `notebooks/scripts/requirements_colab.txt`
- `datasets/raw/02_Chavacano/creole_rc/requirements.txt`

Primary runtime manifests:

- Backend runtime: `backend/requirements.txt`
- Frontend runtime/tooling: `frontend/package.json`

---

## 11) Setup From Scratch

### 11.1 Prerequisites

Install these first:

- Python 3
- Node.js + npm
- Git

SQLite is used by default and is built into Python.

### 11.2 Backend setup

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

Optional admin user:

```bash
python manage.py createsuperuser
```

### 11.3 Model setup

```bash
cd ../ml_models
python download_model.py
python validate_model.py
python training_preflight.py
```

### 11.4 Frontend setup

```bash
cd ../frontend
npm install
```

Optional frontend env file (only needed if backend API key protection is enabled):

```bash
cp .env.example .env
```

Set:

- `VITE_PUENTE_API_KEY=<same-value-as-backend-PUENTE_API_KEY>`

### 11.5 Run full stack

Linux/macOS:

```bash
cd ..
./run_project.sh
```

Windows CMD:

```bat
run_project.bat
```

Windows PowerShell:

```powershell
.\run_project.ps1
```

Default URLs:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Admin: `http://localhost:8000/admin/`

---

## 12) Launcher Scripts And Flags

### 12.1 `run_project.sh` (Linux/macOS)

Supported options:

- `--backend-only`
- `--frontend-only`

Behavior highlights:

- Validates required project files exist before launch
- Resolves Python executable from active/common venv paths
- Prepends `.tools/node/bin` to PATH if present
- Validates npm availability
- Checks port conflicts on 8000 and 5173 before start
- Handles `projectpuente.local` alias hints

### 12.2 `run_project.ps1` (Windows)

Supported switches:

- `-BackendOnly`
- `-FrontendOnly`

Behavior highlights:

- Port checks before startup
- Starts backend/frontend in current terminal context
- Waits for ports and prints LAN hints
- Sets `PUENTE_LOAD_MODEL_ON_STARTUP=true` during launcher-managed runs

### 12.3 `run_project.bat` (Windows wrapper)

- Wraps and forwards to `run_project.ps1`
- Accepts and forwards arguments

---

## 13) Root NPM Scripts

From `package.json`:

| Script | Command |
|---|---|
| `npm run backend` | `cd backend && python manage.py runserver` |
| `npm run frontend` | `cd frontend && npm run dev` |
| `npm run start` | `bash ./run_project.sh` |
| `npm run start:windows` | `run_project.bat` |
| `npm run start:backend-only` | `bash ./run_project.sh --backend-only` |
| `npm run start:frontend-only` | `bash ./run_project.sh --frontend-only` |

---

## 14) Environment Variables

### 14.1 Backend (`backend/.env`)

Important variables:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Required Django secret |
| `DEBUG` | Debug mode toggle |
| `ALLOWED_HOSTS` | Host whitelist |
| `CORS_ALLOW_ALL_ORIGINS` | CORS global toggle |
| `CORS_ALLOWED_ORIGINS` | Explicit CORS origins |
| `CSRF_TRUSTED_ORIGINS` | CSRF trusted origins |
| `DRF_THROTTLE_ANON_RATE` | DRF anonymous throttle (default `240/min`) |
| `ML_MODEL_PATH` | Local model directory |
| `PUENTE_API_KEY` | Optional write-endpoint API key |
| `STRICT_OFFLINE_MODE` | Disables internet-dependent services |
| `EDGE_TTS_VOICE_EN/ES/TL/CBK/HIL/CEB` | Voice overrides |
| `EDGE_TTS_RATE` | TTS rate |
| `EDGE_TTS_VOLUME` | TTS volume |
| `EDGE_TTS_PITCH` | TTS pitch |

### 14.2 Frontend (`frontend/.env`)

| Variable | Purpose |
|---|---|
| `VITE_PUENTE_API_KEY` | Optional client header for protected write endpoints |

### 14.3 Root placeholder (`.env`)

A workspace-level placeholder `.env` is present for shared tooling/documentation convenience.
Runtime loading still happens primarily from `backend/.env` and `frontend/.env`.

---

## 15) PWA Behavior

Current Vite PWA configuration:

- Plugin: `vite-plugin-pwa`
- Uses manual `public/manifest.json` (`manifest: false` in plugin config)
- Runtime cache rules:
  - `/api/health/` -> NetworkFirst
  - `/api/wiki/` -> NetworkFirst
- PWA plugin auto-disables when current working directory contains an apostrophe character

---

## 16) Verification Commands

### 16.1 Backend tests

```bash
cd backend
python manage.py test core_api
```

Current test function count in `backend/core_api/tests.py`: 57

### 16.2 Frontend lint/build

```bash
cd frontend
npm run lint
npm run build
```

### 16.3 Training preflight

```bash
cd ml_models
python training_preflight.py
```

Exit behavior:

- `0` = no blockers
- `2` = one or more blockers

---

## 17) Operational Script Inventory

### 17.1 Backend utility scripts

- `backend/scripts/create_superuser.py`
- `backend/scripts/list_superusers.py`
- `backend/scripts/seed_spanish_baseline.py`
- `backend/scripts/seed_spanish_loanwords.py`

### 17.2 Data scripts

- `datasets/scripts/pillar1_merge_parallel_corpus.py`
- `datasets/scripts/pillar2_structure_monolingual.py`
- `datasets/scripts/json_to_jsonl_stream.py`
- `datasets/scripts/json_to_jsonl_converter.py`
- `datasets/scripts/archive_legacy_data.py`

### 17.3 ML scripts

- `ml_models/download_model.py`
- `ml_models/validate_model.py`
- `ml_models/train_lora.py`
- `ml_models/training_preflight.py`
- `ml_models/evaluate_metrics.py`
- `ml_models/evaluate_spanish_baseline.py`

### 17.4 Notebook pipeline scripts

- `notebooks/scripts/run_nllb_pipeline.py`
- `notebooks/scripts/extract_chavacano_pdf_REFINED.py`
- `notebooks/scripts/process_chavacano_csv_REFINED.py`
- `notebooks/scripts/process_tatoeba_REFINED.py`
- `notebooks/scripts/harvest_creole_rc_REFINED.py`
- `notebooks/scripts/process_wiki_dump.py`
- `notebooks/scripts/deep_clean_wiki.py`
- `notebooks/scripts/colab_lora_training_pipeline.py`
- `notebooks/scripts/colab_drive_sync.py`
- `notebooks/scripts/_path_utils.py`

---

## 18) Known Runtime Behaviors And Troubleshooting

### 18.1 Translation endpoint returns 503

Cause:

- Local model directory missing or not loaded

Check:

- `ml_models/nllb-200-distilled-600M/` exists
- backend startup logs for model load warnings
- `/api/health/` -> `nllb_loaded`

### 18.2 BTVL endpoint returns 503

Cause:

- Same model-unavailable condition as translate

### 18.3 TTS endpoint returns 503

Possible causes:

- `STRICT_OFFLINE_MODE=True`
- `edge-tts` package missing
- backend cannot reach external TTS service

### 18.4 Protected write endpoints return 401

Cause:

- Backend `PUENTE_API_KEY` is set, but request missing/incorrect `X-API-Key`

Fix:

- Set matching key in frontend via `VITE_PUENTE_API_KEY` if using UI.

### 18.5 Frontend/Backend fail to start together

Cause:

- Port 8000 or 5173 already in use

Fix:

- Stop existing processes on those ports before launch.

### 18.6 Health reports `offline-model-missing`

Cause:

- base NLLB model assets are absent in configured `ML_MODEL_PATH`

Current observed state on this machine: model missing, frontend and backend still boot, translation/BTVL blocked.

---

## 19) Related Documentation

- `backend/README.md` — backend dependency and runtime notes
- `frontend/README.md` — frontend dependency and runtime notes
- `ml_models/README.md` — model/training dependency and script notes
- `notebooks/README.md` — notebook dependency notes
- `datasets/scripts/README_3_PILLAR_ARCHITECTURE.md` — 3-pillar data contract
- `TRAINING_PREFLIGHT_CHECKLIST.md` — preflight workflow
- `agents.md` — agent architecture
- `PROJECT_PUENTE_COMPREHENSIVE_SCAN.md` — full repository/runtime scan
