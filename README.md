# PUENTE

**Preserving Understanding through Enhanced Neural Translation Engines**

Offline-first LAN translation platform with:

- Django + DRF backend
- React + Vite frontend
- Local NLLB translation engine
- Optional LoRA adapters
- Optional Edge TTS
- Wiki-Voz cultural context integration

Last synchronized: 2026-04-06

This README is intentionally source-synced to the current repository state. It documents only behavior and files that currently exist.

---

## 1) Project Summary

PUENTE is a local-first translation system focused on Philippine languages and cultural nuance.

Current implementation supports:

- Translation with local NLLB inference
- Direct many-to-many routing with confidence-gated proximate pivots
- Optional formal/street register mode via LoRA adapters
- Translation Memory cache lookup before model inference
- Greedy Wiki-Voz phrase interception for cultural term context
- Back-Translation Verification Loop (BTVL)
- Optional speech synthesis endpoint via `edge-tts`
- Hardware telemetry endpoint (RAM/GPU)

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
- `frontend/src/App.jsx`
- `frontend/src/components/screens/TranslateScreen.jsx`
- `frontend/src/components/screens/WikiVozScreen.jsx`
- `frontend/src/components/screens/SettingsScreen.jsx`
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

Important repository note:

- `.vscode/tasks.json` is currently not present in this repository.

---

## 3) Verified Feature Inventory

### 3.1 Backend API features

| Feature | Status | Implementation |
|---|---|---|
| API root | Present | `APIRootView` |
| Translation endpoint | Present | `TranslateView` |
| BTVL endpoint | Present | `BackTranslationVerifyView` |
| TTS endpoint | Present | `TextToSpeechView` |
| Wiki-Voz endpoint | Present | `WikiVozViewSet` |
| Telemetry endpoint | Present | `telemetry_view` |
| Health endpoint | Present | `HealthCheckView` |
| Optional API key protection | Present | `_require_api_key_or_401` + `PUENTE_API_KEY` |
| Translation Memory cache | Present | `_find_translation_memory_hit` |
| Greedy phrase interception | Present | `_find_wiki_voz_phrase_match` |
| Local model singleton load | Present | `CoreApiConfig.ready()` |
| LoRA adapter switching | Present | `set_adapter` + loaded adapter names |
| Translation logging model | Present | `TranslationLog` |
| Wiki terms model | Present | `CulturalTerm` |
| Django Admin for both models | Present | `core_api/admin.py` |

### 3.2 Frontend features

| Area | Status | Implementation |
|---|---|---|
| LAN-aware API URL | Present | `frontend/src/App.jsx` |
| Health polling | Present | every 30s in `App.jsx` |
| Translate screen | Present | `TranslateScreen.jsx` |
| Wiki-Voz screen | Present | `WikiVozScreen.jsx` |
| Settings screen | Present | `SettingsScreen.jsx` |
| Theme persistence | Present | `settings.js` + localStorage |
| Source/target defaults persistence | Present | `settings.js` + localStorage |
| API key header injection | Present | `apiAuth.js` |
| TTS client integration | Present | `ttsClient.js` |
| BTVL trigger UI | Present | Translate screen button |
| Error boundary wrapper | Present | `ErrorBoundary.jsx` + `main.jsx` |
| PWA plugin integration | Present | `vite.config.js` + manifest |

### 3.3 ML and data tooling features

| Feature | Status | Script |
|---|---|---|
| Download local base model | Present | `ml_models/download_model.py` |
| Local model validation smoke test | Present | `ml_models/validate_model.py` |
| LoRA training script | Present | `ml_models/train_lora.py` |
| Read-only training preflight | Present | `ml_models/training_preflight.py` |
| General BLEU/chrF++ evaluator | Present | `ml_models/evaluate_metrics.py` |
| Pure Spanish baseline evaluator | Present | `ml_models/evaluate_spanish_baseline.py` |
| Notebook master pipeline runner | Present | `notebooks/scripts/run_nllb_pipeline.py` |

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

### 6.4 `GET|POST|DELETE /api/wiki/`

Behavior:

- `GET /api/wiki/`
  - list scoped Wiki-Voz rows
  - supports `q`, `language`, and `category` filters
- `POST /api/wiki/`
  - create row when `id` is not provided
  - update row when `id` is provided
  - write-protected by `X-API-Key` when `PUENTE_API_KEY` is configured
- `DELETE /api/wiki/?id=<pk>`
  - delete by query id
  - write-protected by `X-API-Key` when `PUENTE_API_KEY` is configured

Compatibility route:

- `DELETE /api/wiki/<pk>/`

### 6.5 `GET /api/telemetry/`

Returns structured RAM/GPU metrics:

- RAM used/total/percent
- GPU availability and utilization details

### 6.6 `GET /api/health/`

Returns backend status fields including:

- `engine`
- `nllb_loaded`
- `lora_adapters`
- `api_key_required`
- `tts_available`
- `strict_offline_mode`
- `supported_languages`

### 6.7 `GET /`

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
- Source and target TTS buttons via backend TTS endpoint
- Copy translation action
- BTVL verification action and diagnostics
- Cultural term inline highlighting with hover tooltip and popup

### 7.2 Wiki-Voz Screen

Current behavior includes:

- API fetch from `/api/wiki/`
- Search by term/definition/language/category/trigger words
- Strict category filter scope (`Idioms`, `False Cognates`, `Honorifics`, `Expressions`)
- Dynamic language filters from live API payload
- Scrollable data grid with card details popup
- Local placeholder fallback for missing/invalid image URLs

### 7.3 Settings Screen

Current behavior includes:

- Theme toggle (dark/light)
- Default source/target persistence
- Live backend/model/TTS/API-key status display
- Telemetry polling every 4 seconds
- RAM/GPU usage bars

---

## 8) Persistence And Data Models

### 8.1 `CulturalTerm`

Core fields:

- `term` (indexed)
- `definition`
- `trigger_words` (JSON list)
- `image_url`
- `language` (free text)
- `category`
- timestamps

Uniqueness constraint:

- unique pair on (`term`, `language`)

### 8.2 `TranslationLog`

Core fields include:

- request metadata (source/target/mode/input)
- output metadata (output text/tokens/model)
- performance (`latency_ms`)
- status (`success/error/timeout`)
- Wiki-Voz interception markers
- timestamps and indexes

---

## 9) Repository Layout

```text
ProjectPuente/
├── README.md
├── PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
├── TRAINING_PREFLIGHT_CHECKLIST.md
├── agents.md
├── package.json
├── run_project.sh
├── run_project.ps1
├── run_project.bat
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── README.md
│   ├── .env.example
│   ├── backend/
│   │   ├── settings.py
│   │   └── urls.py
│   ├── core_api/
│   │   ├── apps.py
│   │   ├── languages.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tests.py
│   │   └── admin.py
│   └── scripts/
├── frontend/
│   ├── package.json
│   ├── README.md
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   │   ├── manifest.json
│   │   └── local-assets/
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── components/
│       ├── data/
│       └── lib/
├── ml_models/
│   ├── README.md
│   ├── download_model.py
│   ├── validate_model.py
│   ├── train_lora.py
│   ├── training_preflight.py
│   ├── evaluate_metrics.py
│   └── evaluate_spanish_baseline.py
├── datasets/
│   ├── processed/
│   └── raw/
└── notebooks/
    ├── README.md
    ├── *.ipynb
    └── scripts/
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

- Python 3.12+
- Node.js 20+ + npm (or local `.tools/node/bin` fallback)
- Git

SQLite is used by default and is built into Python.

Optional local Node fallback (no system package manager required):

```bash
mkdir -p .tools
# Place a Node distribution so .tools/node/bin/node and .tools/node/bin/npm exist.
# run_project.sh will auto-prepend this path when present.
```

### 11.2 Backend setup

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

Optional CPU-only / low-`/tmp` install path (prevents large CUDA wheel downloads and temp-space failures):

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
mkdir -p ../.pip-tmp
TMPDIR="$PWD/../.pip-tmp" pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchaudio
TMPDIR="$PWD/../.pip-tmp" pip install --no-cache-dir -r requirements.txt
rm -rf ../.pip-tmp
cp .env.example .env
python manage.py migrate
```

Optional admin user:

```bash
python manage.py createsuperuser
```

### 11.3 Model setup (optional, deferred during dependency-only prep)

```bash
cd ../ml_models
python training_preflight.py
```

Notes:

- Keep model download deferred if you are only preparing dependencies right now.
- Do not run `python download_model.py` until you are ready to stage local NLLB weights.
- With no local weights, backend starts but `/api/translate/` and `/api/btvl/` return HTTP 503 by design.

### 11.4 Frontend setup

```bash
cd ../frontend
npm install
```

If using local Node fallback:

```bash
export PATH="$PWD/../.tools/node/bin:$PATH"
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

- Backend: `http://0.0.0.0:8000`
- Frontend: `http://0.0.0.0:5173`
- Admin: `http://localhost:8000/admin/`

### 11.6 Canonical Wiki Sync (Deployment Safe)

From repo root, use this pipeline for strict JSON-to-SQLite synchronization:

```bash
bash scripts/wiki_sync_pipeline.sh
```

Dry-run validation:

```bash
bash scripts/wiki_sync_pipeline.sh --dry-run
```

What it does:

- cleans/pads canonical Wiki-Voz JSON
- applies backend migrations
- runs `seed_wiki --prune` so stale DB rows are removed

### 11.7 Progressive Chavacano Curation

Generate an editable template from current Chavacano placeholders:

```bash
python scripts/replace_chavacano_placeholders.py --export-template scripts/chavacano_curation_template.json --dry-run
```

Apply curated replacements:

```bash
python scripts/replace_chavacano_placeholders.py --replacements scripts/chavacano_curated_updates.json
```

Notes:

- replacement tool preserves dataset shape (`200` total, `50` per language)
- only schema-valid Chavacano replacements are accepted
- after applying replacements, run the canonical sync pipeline to update SQLite

---

## 12) Launcher Scripts And Flags

### 12.1 `run_project.sh` (Linux/macOS)

Supported options:

- `--backend-only`
- `--frontend-only`

Behavior highlights:

- Validates required project files exist before launch
- Resolves Python executable in this order:
  - active `VIRTUAL_ENV`
  - `.venv/bin/python`
  - `venv/bin/python`
  - `../.venv/bin/python`
  - `python3`
  - `python`
- Prepends `.tools/node/bin` to PATH if present
- Validates npm availability
- Checks port conflicts on 8000 and 5173 before start

### 12.2 `run_project.ps1` (Windows)

Supported switches:

- `-BackendOnly`
- `-FrontendOnly`

Behavior highlights:

- Port checks before startup
- Starts backend/frontend in current terminal context
- Waits for ports and prints LAN hints

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
| `npm run start` | `run_project.bat` |

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

Current test function count in `backend/core_api/tests.py`: 46

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

### 17.2 ML scripts

- `ml_models/download_model.py`
- `ml_models/validate_model.py`
- `ml_models/train_lora.py`
- `ml_models/training_preflight.py`
- `ml_models/evaluate_metrics.py`
- `ml_models/evaluate_spanish_baseline.py`

### 17.3 Notebook pipeline scripts

- `notebooks/scripts/run_nllb_pipeline.py`
- `notebooks/scripts/extract_chavacano_pdf_REFINED.py`
- `notebooks/scripts/process_chavacano_csv_REFINED.py`
- `notebooks/scripts/process_tatoeba_REFINED.py`
- `notebooks/scripts/harvest_creole_rc_REFINED.py`
- `notebooks/scripts/process_wiki_dump.py`
- `notebooks/scripts/deep_clean_wiki.py`
- `notebooks/scripts/_path_utils.py`

---

## 18) Known Runtime Behaviors And Troubleshooting

### 18.1 Translation endpoint returns 503

Cause:

- Local model directory missing or not loaded

Check:

- `ml_models/nllb-200-distilled-600M/` exists
- backend startup logs for model load warnings

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

### 18.6 VS Code task command references

Current state:

- No committed `.vscode/tasks.json` in this repository right now.

---

## 19) Related Documentation

- `backend/README.md` — backend dependency and runtime notes
- `frontend/README.md` — frontend dependency and runtime notes
- `ml_models/README.md` — model/training dependency and script notes
- `notebooks/README.md` — notebook dependency notes
- `TRAINING_PREFLIGHT_CHECKLIST.md` — preflight workflow
- `agents.md` — agent architecture
- `PROJECT_PUENTE_COMPREHENSIVE_SCAN.md` — full repository/runtime scan

