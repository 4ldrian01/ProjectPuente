# Project Puente - Comprehensive Repository Scan (Fully Updated)

Generated: 2026-04-07T06:17:46+08:00  
Workspace: /home/rauf/Desktop/Machine Learning/ProjectPuente  
Branch: main

This report is a full, source-backed re-scan of the repository and active runtime state.
It supersedes prior snapshots and was rebuilt from current files, git metadata, command validation, and live endpoint checks.

## Delta Updates In This Pass

- Re-scanned backend/frontend/ML/notebook source files directly from disk.
- Revalidated live runtime behavior for root, health, translate, BTVL, TTS, telemetry, and wiki endpoints.
- Re-ran quality checks with current environment:
  - backend tests
  - frontend lint/build
  - training preflight
- Corrected runtime assertions to match current local-only behavior:
  - `translate` and `btvl` currently return `503` because local model files are missing.
  - cloud/API fallback is disabled (`cloud_fallback_allowed: false`).
- Updated git inventory to current state (`tracked=136`, `modified tracked=21`, `untracked=7`).
- Added a new **File Purpose Index** section to summarize purpose for files not previously covered in depth.

---

## 0) Completeness Verification (This Pass)

### 0.1 Evidence Sources Used

- Full reads of core backend/frontend/ML/notebook files.
- Live git commands:
  - `git ls-files`
  - `git status --short`
  - `git branch --show-current`
- Runtime probes via `curl`:
  - `/`
  - `/api/health/`
  - `/api/translate/`
  - `/api/btvl/`
  - `/api/tts/`
  - `/api/telemetry/`
  - `/api/wiki/`
- Validation commands:
  - `backend/manage.py test`
  - `frontend npm run lint`
  - `frontend npm run build`
  - `ml_models/training_preflight.py`

### 0.2 Repository Snapshot

- Branch: `main`
- Tracked files: `136`
- Git status lines: `28`
- Modified tracked entries: `21`
- Untracked entries: `7`

Current git short status:

```text
 M PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
 M README.md
 M backend/backend/settings.py
 M backend/core_api/apps.py
 M backend/core_api/views.py
 M backend/requirements.txt
 M frontend/index.html
 M frontend/package-lock.json
 M frontend/package.json
 M frontend/src/App.jsx
 M frontend/src/components/CulturalTermPopup.jsx
 M frontend/src/components/layout/BottomNav.jsx
 M frontend/src/components/layout/Header.jsx
 M frontend/src/components/screens/TranslateScreen.jsx
 M frontend/src/components/screens/WikiVozScreen.jsx
 M ml_models/download_model.py
 M ml_models/training_preflight_report.json
 M notebooks/lora_training.ipynb
 M notebooks/model_validation.ipynb
 M notebooks/sample.ipynb
 M run_project.sh
?? .tools/
?? CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md
?? frontend/src/components/screens/GapAnalysisTerminal.jsx
?? frontend/src/components/screens/SystemEvaluationScreen.jsx
?? ml_models/lora_adapters/
?? notebooks/scripts/colab_lora_training_pipeline.py
?? notebooks/scripts/colab_vscode_tunnel_setup.md
```

### 0.3 Current Structural Notes

- `.tools/` exists and is untracked (`~167 MB`).
- `frontend/node_modules` exists and is ignored (`~314 MB`).
- `frontend/dist` exists from current build and is ignored (`~760 KB`).
- Previous unusual untracked notebook files named like `=0.x.y` are no longer present.
- `ml_models/lora_adapters/` currently exists but only contains `README.md` (no adapter folders yet).

### 0.4 Database Snapshot (Current Runtime)

From Django shell query in current environment:

- `CulturalTerm` rows: `0`
- `TranslationLog` rows: `10`

This explains empty current `/api/wiki/` query results.

---

## 1) High-Level System Summary

PUENTE is an offline-first LAN translation stack with Django + DRF backend, React + Vite frontend, local NLLB translation pipeline, optional LoRA adapters, optional Edge TTS, and telemetry/verification support.

Primary runtime stack:

- Backend: Django + DRF + SQLite
- Frontend: React 19 + Vite 7 + Tailwind 4
- Neural runtime: local `nllb-200-distilled-600M` (expected at `ml_models/nllb-200-distilled-600M`) with optional LoRA
- Speech: `edge-tts` endpoint (internet-dependent unless strict offline mode blocks it)

Architecture model in repository:

- `agents.md` defines the 5-agent flow:
  - Routing
  - Interceptor (Wiki-Voz)
  - Neural
  - Observer
  - Presentation

Current backend language scope:

- `auto`, `en`, `es`, `tl`, `cbk`, `hil`, `ceb`

Core routes currently registered:

- `POST /api/translate/`
- `POST /api/btvl/`
- `POST /api/tts/`
- `GET /api/wiki/`
- `GET /api/telemetry/`
- `GET /api/health/`
- `GET /`

---

## 2) Live Runtime Validation (Current Session)

### 2.1 Runtime Availability

- Backend endpoints responded on `127.0.0.1:8000`.
- Frontend responded on `127.0.0.1:5173` (`HTTP 200`).

### 2.2 Live Endpoint Probe Results

| Endpoint | HTTP | Observed Result |
|---|---:|---|
| `/` | 200 | API root online, engine reports `offline-model-missing` |
| `/api/health/` | 200 | `nllb_loaded=false`, `tts_available=true`, `strict_offline_mode=false`, `cloud_fallback_allowed=false` |
| `/api/translate/` | 503 | Local model unavailable error (explicitly states cloud fallback disabled) |
| `/api/btvl/` | 503 | Local model unavailable error |
| `/api/tts/` | 200 | Returned `audio/mpeg`, `X-TTS-Voice: en-US-EmmaMultilingualNeural` |
| `/api/telemetry/` | 200 | RAM and GPU payload present |
| `/api/wiki/` | 200 | `{\"results\":[]}` |
| `/api/wiki/?q=vinta` | 200 | `{\"results\":[]}` |
| `http://127.0.0.1:5173/` | 200 | Frontend reachable |

### 2.3 Current Validation Runs

| Check | Command Status | Result |
|---|---:|---|
| Backend tests | 0 | `46/46` passing |
| Frontend lint | 0 | passed (`eslint .`) |
| Frontend build | 0 | passed (`vite build`, PWA assets generated) |
| Training preflight | 2 | `BLOCKED` (`PASS=13, WARN=1, BLOCKER=1`) |

Notes:

- Frontend checks were run using local Node path export (`.tools/node/bin`) because `npm` was not on default shell PATH.

### 2.4 Migration State (Current)

`manage.py showmigrations core_api` reports all applied:

- `[X] 0001_initial`
- `[X] 0002_culturalterm_category_culturalterm_language_and_more`
- `[X] 0003_add_es_language_choices`
- `[X] 0004_culturalterm_language_free_text`

---

## 3) Backend Deep Scan (Source-Backed)

### 3.1 `backend/backend/settings.py`

Confirmed behavior:

- Loads env from `backend/.env` via `python-dotenv`.
- Hard-fails startup if `SECRET_KEY` is empty.
- Uses helper parsers `_env_bool` / `_env_list`.
- Defaults DB to SQLite (`backend/db.sqlite3`).
- CORS/CSRF are env-driven with local defaults.
- DRF anonymous throttling configured (`DRF_THROTTLE_ANON_RATE`, default `240/min`).
- Optional write-endpoint API key gate via `PUENTE_API_KEY`.
- `STRICT_OFFLINE_MODE` supported.
- `ML_MODEL_PATH` supported (default `ml_models/nllb-200-distilled-600M`).
- `HF_*` settings exist in config, but runtime inference path in views is local-only.
- Edge TTS voice/rate/volume/pitch env variables available.

### 3.2 `backend/backend/urls.py`

Routes currently registered:

- `/` -> `APIRootView`
- `/admin/`
- `/api/translate/` -> `TranslateView`
- `/api/btvl/` -> `BackTranslationVerifyView`
- `/api/telemetry/` -> `telemetry_view`
- `/api/tts/` -> `TextToSpeechView`
- `/api/wiki/` -> `WikiVozView`
- `/api/health/` -> `HealthCheckView`

### 3.3 `backend/core_api/languages.py`

Canonical language contract is centralized here:

- `SUPPORTED_LANGUAGES` includes `es`.
- `SOURCE_LANGUAGE_CODES` includes `auto`.
- `TARGET_LANGUAGE_CODES` excludes `auto`.
- `FLORES_MAP` includes `es -> spa_Latn`.
- `PIVOT_LANG = eng_Latn`.

### 3.4 `backend/core_api/serializers.py`

Confirmed validation constraints:

- `TranslateRequestSerializer`
  - `text`: max 250
  - `source_lang`: source set including `auto`
  - `target_lang`: target set (no `auto`)
  - `mode`: `formal|street`, default `formal`
- `BackTranslationRequestSerializer`
  - `text`: max 250
  - `source_lang`: target set
  - `target_lang`: `en` (default)
- `TextToSpeechRequestSerializer`
  - `text`: max 1000
  - `lang_code`: source set including `auto`
  - optional `voice`

### 3.5 `backend/core_api/models.py`

#### `CulturalTerm`

- `term` unique/indexed
- `definition`, `image_url`, `language`, `category`
- `language` is free text (not enum-restricted)
- ordered by `term`

#### `TranslationLog`

- Captures request/output metadata, model name, pivot flag
- Captures latency/status/error fields
- Captures Wiki-Voz interception fields
- Indexed on `created_at`, language pair, and `status`

### 3.6 `backend/core_api/apps.py` (Singleton Loader)

Confirmed loader behavior:

- Uses class-level singleton state for tokenizer/model/adapters.
- Startup load is gated by `PUENTE_LOAD_MODEL_ON_STARTUP` (default off).
- Skips heavy init for management commands (`makemigrations`, `migrate`, `collectstatic`, `test`).
- Resolves model path from `settings.ML_MODEL_PATH`.
- Local-only loading (`local_files_only=True`) is enforced.
- Device strategy:
  - CUDA + bitsandbytes -> INT8
  - CUDA no bitsandbytes -> FP16
  - CPU -> FP32
- Adapter load path:
  - `ml_models/lora_adapters/lora-cbk-formal`
  - `ml_models/lora_adapters/lora-cbk-street`
- Current health output confirms no adapters loaded.

### 3.7 `backend/core_api/views.py`

#### Verified global utilities

- API key helpers:
  - `_has_valid_api_key`
  - `_require_api_key_or_401`
- TM normalization:
  - `_normalize_text_for_cache_lookup`
- Phrase scan normalization:
  - `_normalize_text_for_phrase_scan`
- Interceptor matcher:
  - `_find_wiki_voz_phrase_match` (greedy longest match)

#### `TranslateView.post()` behavior

Execution order in source:

1. Optional API key check
2. Serializer validation
3. Greedy Wiki-Voz phrase interception
4. Translation Memory lookup from `TranslationLog`
5. Same-language passthrough shortcut
6. Local NLLB translation path (if model loaded)
7. Structured logging + payload response

TM cache lookup details:

- Uses `Lower(Trim('input_text'))` annotation.
- Match keys: normalized text + source/target pair.
- Returns `model='tm-cache'`, `is_cached=true`.

Current runtime path if model missing:

- Returns `503` with explicit message that cloud/API fallback is disabled.

#### `BackTranslationVerifyView.post()`

- Optional API key check
- Serializer validation
- Returns `503` when local model unavailable
- Calls `nllb_translate(... mode='formal')` when available

#### `TextToSpeechView.post()`

- Optional API key check
- Blocks with `503` when strict offline mode enabled
- Validates request
- Synthesizes MP3 via `edge-tts`
- Returns `audio/mpeg` + `X-TTS-Voice`

#### `WikiVozView.get()`

- `q` filter uses `term__icontains` and returns up to 20
- without `q`, returns first 100 ordered terms

#### `telemetry_view`

- RAM via `psutil`
- GPU via `torch.cuda` primary path
- GPU fallback via `GPUtil` if torch unavailable

#### `HealthCheckView.get()`

Returns:

- model status + adapter list
- tts availability + engine
- strict offline mode
- API key requirement metadata
- supported language list
- `cloud_fallback_allowed: false`
- `inference_mode: offline-local-only`

### 3.8 `backend/core_api/admin.py`

- `CulturalTermAdmin`: search/filter/order configured
- `TranslationLogAdmin`: ISO-focused columns, filters, readonly date field

### 3.9 `backend/core_api/tests.py`

Current suite count by source: `46` tests.

Coverage includes:

- serializer validation boundaries
- language/FLORES contract checks
- pivot routing behavior (`es -> hil` test)
- TM cache hit/miss behavior
- greedy longest phrase interception
- API key protection behavior for write endpoints
- BTVL and TTS endpoint behavior
- health/wiki checks

### 3.10 Migrations

Current migration set in repo and DB:

- `0001_initial`
- `0002_culturalterm_category_culturalterm_language_and_more`
- `0003_add_es_language_choices`
- `0004_culturalterm_language_free_text`

### 3.11 Backend Utility Scripts (`backend/scripts/`)

Current script set:

- `create_superuser.py`
- `list_superusers.py`
- `seed_spanish_baseline.py`
- `seed_spanish_loanwords.py`

Key behavior:

- `seed_spanish_baseline.py`
  - seeds 5 Spanish baseline entries
  - supports `--dry-run` and `--skip-existing`
- `seed_spanish_loanwords.py`
  - reads `datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv`
  - normalizes/upserts entries case-insensitively
  - supports `--dry-run` and `--skip-existing`

---

## 4) Frontend Deep Scan (Source-Backed)

### 4.1 `frontend/src/App.jsx`

Confirmed behavior:

- API base is LAN-derived:
  - `http://${window.location.hostname}:8000/api`
- Health polling every 30 seconds.
- API key header support via `withApiKeyHeaders()`.
- AbortController cancels stale translation requests.
- Theme sync via localStorage + cross-tab events.
- Screen routing includes:
  - `translate`
  - `wiki-voz`
  - `evaluation` (uses `SystemEvaluationScreen`)
  - settings overlay/panel
- Translate readiness gate:
  - `backendUp && nllbLoaded && (!apiKeyRequired || clientApiKeyConfigured)`

### 4.2 `frontend/src/components/screens/TranslateScreen.jsx`

Confirmed UX/logic:

- Source/target language rosters include Spanish.
- Mutual exclusion source/target handling.
- Debounced auto-translate (`800ms`).
- Character guard aligned to backend (`CHAR_LIMIT = 250`).
- BTVL trigger and diagnostics rendering.
- Edge-TTS controls for source/target text.
- Telemetry polling (`4500ms`) and RAM/GPU bar rendering.
- Gap analysis panel (`GapAnalysisTerminal`) with transaction-flush style logs.
- Local model health messaging through mode status banner.
- Current layout sizing:
  - source/target cards: `min-h-[9rem] md:min-h-[12rem]`
  - gap/telemetry cards mirror same min-height profile
  - container width up to `max-w-[78rem]`

### 4.3 `frontend/src/components/LanguageSelector.jsx`

- Desktop: tab strip with animated active underline.
- Mobile: unified dropdown selector.
- Excludes opposite-side language selection.
- Includes Spanish in available options.

### 4.4 `frontend/src/components/screens/WikiVozScreen.jsx`

Confirmed behavior:

- Loads `/api/wiki/` on mount.
- Falls back to local `wikiVozData` seed entries when API unavailable or empty.
- Search sanitation:
  - strips `<> {} \` $`
  - max length 10 (`SEARCH_QUERY_MAX_LENGTH = 10`)
- Validation message + counter under search field.
- Category and language filters.
- Spanish category handling explicitly included.
- Progressive pagination (`20` cards at a time).
- Masonry-style layout with deterministic aspect ratio variation.
- Local placeholder for remote/invalid images.
- Uses shared modal component (`CulturalTermPopup`).

### 4.5 `frontend/src/components/screens/SettingsScreen.jsx`

Confirmed behavior:

- Persists default source/target + theme to localStorage.
- Polls telemetry every `4000ms`.
- Displays backend/model/adapter/TTS/API-key state.
- Shows wiki entry goal stats from local dataset map.

### 4.6 Layout Components

- `Header.jsx`
  - Branding text now `PUENTE`
  - desktop nav contains Translate / Wiki-Voz / Evaluation / Settings
  - no-wrap labels and animated indicator
- `BottomNav.jsx`
  - mobile nav includes Translate / Wiki-Voz / Evaluate / Settings
  - one-line labels (`whitespace-nowrap`)

### 4.7 `frontend/src/components/CulturalTermPopup.jsx`

- Fixed backdrop + centered modal structure
- scroll-safe max-height behavior
- in-modal Edge-TTS support for term+definition narration

### 4.8 Frontend Utility Libraries

- `src/lib/settings.js`
  - canonical language arrays + setting sanitization
  - enforces valid source/target pair behavior
  - emits `puente-settings-updated`
- `src/lib/ttsClient.js`
  - backend `/api/tts/` blob request
  - single active playback + cleanup lifecycle
  - blob error parsing to readable messages
- `src/lib/apiAuth.js`
  - optional `VITE_PUENTE_API_KEY` -> `X-API-Key` header

### 4.9 Styling and Shell

- `src/main.jsx` uses `StrictMode` + `ErrorBoundary`.
- `src/index.css` defines dark/light design tokens and semantic status colors.
- `src/App.css` defines animation timing tokens, toggle styles, and motion utilities.
- `frontend/index.html` title is `PUENTE` and manifest is linked.

### 4.10 PWA / Build Config

`frontend/vite.config.js` confirms:

- plugins: React SWC + Tailwind + Vite PWA
- PWA auto-disables if current working path contains `'`
- runtime cache policies for `/api/health/` and `/api/wiki/`

### 4.11 Untracked Frontend Screens In Active Use

- `frontend/src/components/screens/GapAnalysisTerminal.jsx` (untracked)
- `frontend/src/components/screens/SystemEvaluationScreen.jsx` (untracked)

These files are imported by tracked components and compile successfully in current local workspace, but remain untracked in git.

---

## 5) ML and Training Pipeline Scan

### 5.1 `ml_models/README.md`

Documents:

- required package families
- optional evaluation/training extras
- expected model and adapter structure
- FLORES code mapping

### 5.2 `ml_models/download_model.py`

Confirmed behavior:

- downloads `facebook/nllb-200-distilled-600M` via `snapshot_download`
- targets fixed absolute path:
  - `/home/rauf/Desktop/Machine Learning/ProjectPuente/ml_models/nllb-200-distilled-600M`
- warns when target folder is non-empty
- verifies essential expected files

### 5.3 `ml_models/evaluate_metrics.py`

Confirmed capabilities:

- local evaluation for configurable language pair/mode
- BLEU + chrF++ scoring (`sacrebleu`)
- dependency guard writes structured error JSON with install command
- output default: `evaluation_results.json`

### 5.4 `ml_models/evaluate_spanish_baseline.py`

Confirmed capabilities:

- fixed baseline task: `spa_Latn -> eng_Latn`
- optional JSON input pairs
- BLEU + chrF++ output report
- output default: `spanish_baseline_metrics.json`

### 5.5 `ml_models/train_lora.py`

Confirmed capabilities:

- trains `formal` or `street` LoRA adapters
- consumes processed NLLB-ready JSON files
- writes adapters to:
  - `ml_models/lora-cbk-formal` or `ml_models/lora-cbk-street`

Important consistency note:

- Backend loader currently expects adapter folders under:
  - `ml_models/lora_adapters/lora-cbk-formal`
  - `ml_models/lora_adapters/lora-cbk-street`

### 5.6 `ml_models/training_preflight.py`

Fresh run result in this session:

- exit code: `2`
- overall: `BLOCKED`
- summary: `PASS=13, WARN=1, BLOCKER=1`
- blocker: missing local model directory
- warn: missing python modules (`sacrebleu`, `pandas`, `pdfplumber`)

### 5.7 `ml_models/validate_model.py`

- local model smoke-test script
- runs sample multilingual test translations
- checks for presence of local LoRA directories

---

## 6) Data and Notebook Pipeline Scan

### 6.1 Dataset Structure

Current major roots present:

- `datasets/processed/001_chavacano/`
- `datasets/processed/01_chavacano/`
- `datasets/raw/` (Tagalog/Chavacano/Cebuano/Hiligaynon/monolingual buckets)

Confirmed processed NLLB-ready files in `001_chavacano`:

- `chavacano_lexicon_nllb.json`
- `chavacano_parallel_sentences_nllb.json`
- `tatoeba_parallel_nllb.json`
- `creole_rc_chavacano_nllb.json`

### 6.2 Notebook Scripts (`notebooks/scripts/`)

Current tracked active scripts:

- `_path_utils.py`
- `deep_clean_wiki.py`
- `extract_chavacano_pdf_REFINED.py`
- `harvest_creole_rc_REFINED.py`
- `process_chavacano_csv_REFINED.py`
- `process_tatoeba_REFINED.py`
- `process_wiki_dump.py`
- `run_nllb_pipeline.py`

Pipeline orchestration:

- `run_nllb_pipeline.py` launches child scripts through `sys.executable` and writes readiness report outputs.

### 6.3 Additional Untracked Cloud Workflow Files

- `notebooks/scripts/colab_lora_training_pipeline.py`
- `notebooks/scripts/colab_vscode_tunnel_setup.md`
- `CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md`

These define Colab tunnel + cloud LoRA training handoff workflow but are currently untracked.

### 6.4 Notebook Artifacts in Git Status

Modified tracked notebooks:

- `notebooks/lora_training.ipynb`
- `notebooks/model_validation.ipynb`
- `notebooks/sample.ipynb`

### 6.5 Path-Case Hygiene Note

- Canonical project path is lowercase `datasets/`.
- Some non-primary scripts (`process_wiki_dump.py`, `deep_clean_wiki.py`) still reference uppercase `Datasets/` in static path strings.

---

## 7) Operations, Launchers, and Tooling

### 7.1 Launcher Scripts

- `run_project.sh` (Linux/macOS) supports:
  - `--backend-only`
  - `--frontend-only`
  - full stack mode
  - port conflict checks
  - Python path probing across common venv locations
  - local Node path inclusion (`.tools/node/bin`)
- sets `PUENTE_LOAD_MODEL_ON_STARTUP=true` when launching backend.

### 7.2 Windows Launchers

- `run_project.ps1`
  - supports backend-only/frontend-only/full-stack
  - checks listening ports and process lifecycle
  - waits for port readiness and prints LAN URLs
- `run_project.bat`
  - wrapper to execute the PowerShell launcher

### 7.3 Root Package Scripts

`package.json` scripts:

- `backend`: `cd backend && python manage.py runserver`
- `frontend`: `cd frontend && npm run dev`
- `start`: `run_project.bat`

### 7.4 VS Code Task State

- `.vscode/tasks.json` is currently absent.
- Current root README already documents this absence.

### 7.5 Local Toolchain Note

- System `npm` was not available in default shell during checks.
- Local `.tools/node/bin` was used successfully for frontend lint/build.

---

## 8) API Contract (Current Source + Runtime)

### 8.1 `POST /api/translate/`

Request body:

- `text` (max 250)
- `source_lang` in `auto,en,es,tl,cbk,hil,ceb`
- `target_lang` in `en,es,tl,cbk,hil,ceb`
- `mode` in `formal,street` (default `formal`)

Runtime behavior now:

- executes local-only path when model exists
- includes TM cache short-circuit and `is_cached` flag
- includes optional `wiki_voz` payload on interceptor hit
- currently returns `503` because local model directory is missing

### 8.2 `POST /api/btvl/`

Request body:

- `text` (max 250)
- `source_lang` in `en,es,tl,cbk,hil,ceb`
- `target_lang` default `en`

Runtime behavior now:

- returns `503` when local model is unavailable

### 8.3 `POST /api/tts/`

Request body:

- `text` (max 1000)
- `lang_code` in `auto,en,es,tl,cbk,hil,ceb`
- optional `voice`

Runtime behavior now:

- returned `200` with `audio/mpeg` in this session
- `X-TTS-Voice` header present
- blocked with `503` only when strict offline mode is enabled

### 8.4 `GET /api/wiki/`

Runtime behavior now:

- endpoint healthy (`200`)
- currently returns empty `results` due zero `CulturalTerm` rows

### 8.5 `GET /api/health/`

Current runtime payload includes:

- `engine: offline-model-missing`
- `nllb_loaded: false`
- `lora_adapters: []`
- `tts_available: true`
- `strict_offline_mode: false`
- `cloud_fallback_allowed: false`
- `inference_mode: offline-local-only`

### 8.6 `GET /api/telemetry/`

Current runtime payload includes:

- RAM used/total/percent
- GPU availability/name/VRAM/percent

---

## 9) Security, Reliability, and Consistency Findings

### 9.1 Confirmed Strengths

- Validation boundaries are explicit and test-covered.
- Language/FLORES contract is centralized.
- TM cache reduces repeated inference cost.
- Greedy phrase interception is implemented (not naive exact whole-input match).
- Observer logs capture key reliability/performance/traceability fields.
- Frontend aborts stale requests to prevent race-condition UI updates.
- Launcher scripts include port conflict checks and controlled startup behavior.

### 9.2 Confirmed Active Gaps / Risks

1. Local model missing (runtime blocker)
- `translate` and `btvl` are currently unavailable (`503`).

2. Empty Wiki-Voz DB state
- endpoint works, but returns empty data because `CulturalTerm` count is `0`.

3. LoRA path contract mismatch
- trainer writes `ml_models/lora-cbk-*`, while loader expects `ml_models/lora_adapters/lora-cbk-*`.

4. Untracked but imported frontend files
- `SystemEvaluationScreen.jsx` and `GapAnalysisTerminal.jsx` are used in build but untracked.

5. Untracked large toolchain directory
- `.tools/` is large and untracked; maintain explicit policy for commit packaging.

6. Absolute machine-specific model path in downloader
- `download_model.py` uses a fixed absolute path, reducing portability across machines.

7. Mixed path casing in non-canonical notebook scripts
- some scripts reference uppercase `Datasets/` path.

---

## 10) Complete Inventory Manifests

### 10.1 Exact Tracked Manifest (`git ls-files`, current)

```text
.gitignore
PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
README.md
TRAINING_PREFLIGHT_CHECKLIST.md
agents.md
backend/.env.example
backend/README.md
backend/backend/__init__.py
backend/backend/asgi.py
backend/backend/settings.py
backend/backend/urls.py
backend/backend/wsgi.py
backend/core_api/__init__.py
backend/core_api/admin.py
backend/core_api/apps.py
backend/core_api/languages.py
backend/core_api/migrations/0001_initial.py
backend/core_api/migrations/0002_culturalterm_category_culturalterm_language_and_more.py
backend/core_api/migrations/0003_add_es_language_choices.py
backend/core_api/migrations/0004_culturalterm_language_free_text.py
backend/core_api/migrations/__init__.py
backend/core_api/models.py
backend/core_api/serializers.py
backend/core_api/tests.py
backend/core_api/views.py
backend/manage.py
backend/requirements.txt
backend/scripts/create_superuser.py
backend/scripts/list_superusers.py
backend/scripts/seed_spanish_baseline.py
backend/scripts/seed_spanish_loanwords.py
datasets/processed/001_chavacano/NLLB_READINESS_REPORT.md
datasets/processed/001_chavacano/chavacano_lexicon_nllb.json
datasets/processed/001_chavacano/chavacano_parallel_sentences_nllb.json
datasets/processed/001_chavacano/creole_rc_chavacano_nllb.json
datasets/processed/001_chavacano/creole_rc_sentences.txt
datasets/processed/001_chavacano/pipeline_report.json
datasets/processed/001_chavacano/tatoeba_parallel_nllb.json
datasets/processed/01_chavacano/chavacano_lexicon.json
datasets/processed/01_chavacano/creole_rc_chavacano_text.txt
datasets/processed/01_chavacano/new_chavacano_master_dataset.json
datasets/processed/01_chavacano/tatoeba_dataset.json
datasets/processed/01_chavacano/wiki_monolingual_FINAL.txt
datasets/raw/01_Tagalog/dumpwikimedia/tlwiki-latest-pages-articles.xml.bz2
datasets/raw/01_Tagalog/hatespeech_filipino/README (1).md
datasets/raw/01_Tagalog/hatespeech_filipino/gitattributes (1)
datasets/raw/01_Tagalog/hatespeech_filipino/hatespeech_filipino.py
datasets/raw/01_Tagalog/hatespeech_filipino/hatespeech_raw.zip
datasets/raw/01_Tagalog/news_ph/README.md
datasets/raw/01_Tagalog/news_ph/gitattributes
datasets/raw/01_Tagalog/news_ph/newsph.py
datasets/raw/01_Tagalog/news_ph/newsph.zip
datasets/raw/02_Chavacano/cbk-en.txt.zip
datasets/raw/02_Chavacano/cbk_zamwiki-latest-pages-articles.xml.bz2
datasets/raw/02_Chavacano/chavacano-to-english-parallel-sentences.csv
datasets/raw/02_Chavacano/creole_rc/LICENSE (1)
datasets/raw/02_Chavacano/creole_rc/README (2).md
datasets/raw/02_Chavacano/creole_rc/__init__.py
datasets/raw/02_Chavacano/creole_rc/creole_rc.py
datasets/raw/02_Chavacano/creole_rc/gitattributes (2)
datasets/raw/02_Chavacano/creole_rc/requirements.txt
datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv
datasets/raw/02_Chavacano/tatoeba_extracted/LICENSE
datasets/raw/02_Chavacano/tatoeba_extracted/README
datasets/raw/02_Chavacano/tatoeba_extracted/Tatoeba.cbk-en.cbk
datasets/raw/02_Chavacano/tatoeba_extracted/Tatoeba.cbk-en.en
datasets/raw/02_Chavacano/tatoeba_extracted/Tatoeba.cbk-en.xml
datasets/raw/03_Cebuano_Bisaya/ceb-en.txt (1).zip
datasets/raw/03_Cebuano_Bisaya/ceb-en.txt.zip
datasets/raw/04_Hiligaynon/en-hil.txt.zip
datasets/raw/monolingual/ChavacanoIdiomsandDictionary.pdf
datasets/raw/monolingual/conversations/cake-ordering.csv
"datasets/raw/monolingual/conversations/zambo-artesan\303\255a.csv"
frontend/.env.example
frontend/.gitignore
frontend/README.md
frontend/eslint.config.js
frontend/index.html
frontend/package-lock.json
frontend/package.json
frontend/public/local-assets/README.md
frontend/public/local-assets/placeholder.jpg
frontend/public/manifest.json
frontend/public/vinta.svg
frontend/public/vite.svg
frontend/src/App.css
frontend/src/App.jsx
frontend/src/assets/react.svg
frontend/src/components/CulturalTermPopup.jsx
frontend/src/components/ErrorBoundary.jsx
frontend/src/components/LanguageSelector.jsx
frontend/src/components/icons/NavIcons.jsx
frontend/src/components/icons/VintaIcon.jsx
frontend/src/components/icons/index.js
frontend/src/components/layout/BottomNav.jsx
frontend/src/components/layout/Header.jsx
frontend/src/components/screens/SettingsScreen.jsx
frontend/src/components/screens/TranslateScreen.jsx
frontend/src/components/screens/WikiVozScreen.jsx
frontend/src/data/wikiVozData.js
frontend/src/index.css
frontend/src/lib/apiAuth.js
frontend/src/lib/settings.js
frontend/src/lib/ttsClient.js
frontend/src/main.jsx
frontend/vite.config.js
ml_models/.gitkeep
ml_models/README.md
ml_models/download_model.py
ml_models/evaluate_metrics.py
ml_models/evaluate_spanish_baseline.py
ml_models/evaluation_results.json
ml_models/spanish_baseline_input.json
ml_models/spanish_baseline_metrics.json
ml_models/train_lora.py
ml_models/training_preflight.py
ml_models/training_preflight_report.json
ml_models/validate_model.py
notebooks/README.md
notebooks/lora_training.ipynb
notebooks/model_validation.ipynb
notebooks/sample.ipynb
notebooks/scripts/_path_utils.py
notebooks/scripts/deep_clean_wiki.py
notebooks/scripts/extract_chavacano_pdf_REFINED.py
notebooks/scripts/harvest_creole_rc_REFINED.py
notebooks/scripts/process_chavacano_csv_REFINED.py
notebooks/scripts/process_tatoeba_REFINED.py
notebooks/scripts/process_wiki_dump.py
notebooks/scripts/run_nllb_pipeline.py
package-lock.json
package.json
puente_high_level_architecture.mmd
run_project.bat
run_project.ps1
run_project.sh
```

### 10.2 Untracked Manifest (Current)

```text
.tools/
CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md
frontend/src/components/screens/GapAnalysisTerminal.jsx
frontend/src/components/screens/SystemEvaluationScreen.jsx
ml_models/lora_adapters/
notebooks/scripts/colab_lora_training_pipeline.py
notebooks/scripts/colab_vscode_tunnel_setup.md
```

### 10.3 Modified Tracked Files (Current)

```text
PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
README.md
backend/backend/settings.py
backend/core_api/apps.py
backend/core_api/views.py
backend/requirements.txt
frontend/index.html
frontend/package-lock.json
frontend/package.json
frontend/src/App.jsx
frontend/src/components/CulturalTermPopup.jsx
frontend/src/components/layout/BottomNav.jsx
frontend/src/components/layout/Header.jsx
frontend/src/components/screens/TranslateScreen.jsx
frontend/src/components/screens/WikiVozScreen.jsx
ml_models/download_model.py
ml_models/training_preflight_report.json
notebooks/lora_training.ipynb
notebooks/model_validation.ipynb
notebooks/sample.ipynb
run_project.sh
```

### 10.4 Runtime-Local Sensitive Artifacts (Existence Only)

```text
backend/.env
backend/db.sqlite3
```

---

## 11) File Purpose Index (Added Coverage)

This section adds concise purpose summaries for files that were previously only listed by inventory.

### 11.1 Root-Level Files

| File | Purpose |
|---|---|
| `README.md` | Source-synced project-level architecture, API, and operations guide |
| `PROJECT_PUENTE_COMPREHENSIVE_SCAN.md` | Repository-wide technical inventory and runtime audit report |
| `agents.md` | 5-agent architecture mapping and behavior contract |
| `TRAINING_PREFLIGHT_CHECKLIST.md` | Operator checklist for ML readiness and preflight interpretation |
| `puente_high_level_architecture.mmd` | Mermaid architecture diagram source |
| `package.json` | root convenience scripts (`backend`, `frontend`, `start`) |
| `package-lock.json` | root npm dependency lockfile |
| `run_project.sh` | Linux/macOS launcher with backend/frontend modes and port checks |
| `run_project.ps1` | Windows PowerShell launcher with process orchestration |
| `run_project.bat` | Windows wrapper that invokes PowerShell launcher |
| `.gitignore` | git ignore policies |
| `CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md` (untracked) | cloud-to-local LoRA transfer playbook |

### 11.2 Backend Files

| File | Purpose |
|---|---|
| `backend/README.md` | backend environment, dependency, and endpoint setup notes |
| `backend/.env.example` | backend env template for local and secured modes |
| `backend/manage.py` | Django management command entrypoint |
| `backend/backend/__init__.py` | backend package marker |
| `backend/backend/asgi.py` | ASGI entrypoint |
| `backend/backend/wsgi.py` | WSGI entrypoint |
| `backend/backend/settings.py` | Django runtime/security/ML/TTS configuration |
| `backend/backend/urls.py` | route registry for root/admin/API endpoints |
| `backend/core_api/__init__.py` | core API app package marker |
| `backend/core_api/apps.py` | singleton local model + adapter loader |
| `backend/core_api/languages.py` | canonical language and FLORES contract |
| `backend/core_api/models.py` | `CulturalTerm` + `TranslationLog` data schema |
| `backend/core_api/serializers.py` | DRF validation contracts for translate/BTVL/TTS/wiki |
| `backend/core_api/views.py` | API behavior for translate/BTVL/wiki/tts/telemetry/health |
| `backend/core_api/admin.py` | Django admin configuration for both models |
| `backend/core_api/tests.py` | backend functional and contract test suite |
| `backend/core_api/migrations/0001_initial.py` | initial schema |
| `backend/core_api/migrations/0002_*.py` | category/language schema extension |
| `backend/core_api/migrations/0003_add_es_language_choices.py` | Spanish language choice expansion |
| `backend/core_api/migrations/0004_culturalterm_language_free_text.py` | language field flexibility update |
| `backend/scripts/create_superuser.py` | secure random superuser provisioning |
| `backend/scripts/list_superusers.py` | superuser listing utility |
| `backend/scripts/seed_spanish_baseline.py` | seeds baseline Spanish control entries |
| `backend/scripts/seed_spanish_loanwords.py` | imports Spanish loanword map CSV into `CulturalTerm` |
| `backend/requirements.txt` | backend python dependency manifest |

### 11.3 Frontend Files

| File | Purpose |
|---|---|
| `frontend/README.md` | frontend setup and backend dependency notes |
| `frontend/.env.example` | frontend API-key mirror env template |
| `frontend/package.json` | frontend scripts and dependency declarations |
| `frontend/package-lock.json` | frontend npm lockfile |
| `frontend/eslint.config.js` | lint rules for JS/JSX |
| `frontend/index.html` | app shell HTML, manifest link, theme meta, title |
| `frontend/vite.config.js` | Vite, Tailwind, and PWA runtime config |
| `frontend/public/manifest.json` | PWA manifest metadata |
| `frontend/public/local-assets/placeholder.jpg` | offline fallback card image |
| `frontend/public/local-assets/README.md` | local asset usage notes |
| `frontend/public/vinta.svg` | app icon asset |
| `frontend/public/vite.svg` | Vite default asset |
| `frontend/src/main.jsx` | React bootstrap + strict mode + error boundary |
| `frontend/src/App.jsx` | top-level screen routing, health polling, translation orchestration |
| `frontend/src/App.css` | animation, toggle, and utility classes |
| `frontend/src/index.css` | theme tokens and Tailwind theme variable mapping |
| `frontend/src/components/ErrorBoundary.jsx` | global UI crash fallback |
| `frontend/src/components/LanguageSelector.jsx` | responsive source/target language selector |
| `frontend/src/components/CulturalTermPopup.jsx` | centered modal for wiki term details + TTS |
| `frontend/src/components/layout/Header.jsx` | desktop header nav and active indicator |
| `frontend/src/components/layout/BottomNav.jsx` | mobile bottom nav |
| `frontend/src/components/icons/NavIcons.jsx` | shared icon set |
| `frontend/src/components/icons/VintaIcon.jsx` | branded boat icon component |
| `frontend/src/components/icons/index.js` | icon export barrel |
| `frontend/src/components/screens/TranslateScreen.jsx` | translation workspace + BTVL + telemetry + gap panel |
| `frontend/src/components/screens/WikiVozScreen.jsx` | cultural term browser/search/filter screen |
| `frontend/src/components/screens/SettingsScreen.jsx` | settings + health + telemetry panel |
| `frontend/src/components/screens/GapAnalysisTerminal.jsx` (untracked) | terminal-style translation path log panel |
| `frontend/src/components/screens/SystemEvaluationScreen.jsx` (untracked) | static metrics dashboard route for evaluation view |
| `frontend/src/lib/settings.js` | settings persistence, sanitization, and theme helpers |
| `frontend/src/lib/apiAuth.js` | API-key header injection helper |
| `frontend/src/lib/ttsClient.js` | backend Edge-TTS client with playback lifecycle |
| `frontend/src/data/wikiVozData.js` | offline wiki seed data, templates, and alias map |
| `frontend/src/assets/react.svg` | React starter asset |

### 11.4 ML Files

| File | Purpose |
|---|---|
| `ml_models/README.md` | ML stack, package requirements, and script expectations |
| `ml_models/download_model.py` | local base model downloader |
| `ml_models/validate_model.py` | base model load + smoke translation validation |
| `ml_models/train_lora.py` | local LoRA fine-tuning script |
| `ml_models/training_preflight.py` | architecture/data/dependency preflight checker |
| `ml_models/evaluate_metrics.py` | general BLEU/chrF++ evaluator |
| `ml_models/evaluate_spanish_baseline.py` | Spanish control-variable baseline evaluator |
| `ml_models/spanish_baseline_input.json` | optional baseline input samples |
| `ml_models/evaluation_results.json` | evaluator output artifact |
| `ml_models/spanish_baseline_metrics.json` | Spanish baseline metric artifact |
| `ml_models/training_preflight_report.json` | latest preflight output artifact |
| `ml_models/.gitkeep` | placeholder for empty-folder preservation |
| `ml_models/lora_adapters/README.md` (untracked) | expected local adapter placement contract |

### 11.5 Notebook and Pipeline Files

| File | Purpose |
|---|---|
| `notebooks/README.md` | notebook kernel/dependency guidance |
| `notebooks/lora_training.ipynb` | interactive LoRA experimentation notebook |
| `notebooks/model_validation.ipynb` | model validation notebook |
| `notebooks/sample.ipynb` | sample notebook workspace |
| `notebooks/scripts/_path_utils.py` | canonical dataset path resolver helper |
| `notebooks/scripts/run_nllb_pipeline.py` | master orchestrator for refined preprocessing scripts |
| `notebooks/scripts/extract_chavacano_pdf_REFINED.py` | PDF lexicon extraction pipeline |
| `notebooks/scripts/process_chavacano_csv_REFINED.py` | CSV parallel sentence normalization pipeline |
| `notebooks/scripts/process_tatoeba_REFINED.py` | Tatoeba ZIP extract/normalize pipeline |
| `notebooks/scripts/harvest_creole_rc_REFINED.py` | CreoleVal remote corpus harvest pipeline |
| `notebooks/scripts/process_wiki_dump.py` | wiki XML dump extraction utility |
| `notebooks/scripts/deep_clean_wiki.py` | aggressive post-cleaning utility for wiki monolingual text |
| `notebooks/scripts/colab_lora_training_pipeline.py` (untracked) | Colab GPU LoRA training script |
| `notebooks/scripts/colab_vscode_tunnel_setup.md` (untracked) | VS Code remote tunnel setup recipe for Colab |

### 11.6 Dataset and Asset Purpose Groups

| Path Group | Purpose |
|---|---|
| `datasets/raw/01_Tagalog/**` | raw Tagalog corpora and auxiliary scripts |
| `datasets/raw/02_Chavacano/**` | raw Chavacano corpora (CSV, Tatoeba, wiki dump, loanword map) |
| `datasets/raw/03_Cebuano_Bisaya/**` | raw Cebuano parallel archives |
| `datasets/raw/04_Hiligaynon/**` | raw Hiligaynon parallel archives |
| `datasets/raw/monolingual/**` | monolingual resources and conversation files |
| `datasets/processed/001_chavacano/**` | canonical NLLB-ready processed outputs |
| `datasets/processed/01_chavacano/**` | legacy/alternate processed outputs and cleaned wiki text |

---

## 12) Final Practical Status (As Of This Scan)

- Backend API structure is coherent and test-green (`46/46`).
- Frontend lint/build are green in current environment.
- Translation and BTVL are blocked only by missing local NLLB model files.
- TTS endpoint is operational now (`strict_offline_mode=false`, `edge-tts` available).
- Wiki endpoint is healthy but currently empty due zero `CulturalTerm` rows.
- Training preflight remains blocked by one blocker (missing model dir).
- Repository includes untracked files that are actively used by current frontend route map.

### Immediate High-Impact Next Steps

1. Install local base model at `ml_models/nllb-200-distilled-600M` and re-run translate/BTVL probes.
2. Seed `CulturalTerm` records (`seed_spanish_baseline.py`, `seed_spanish_loanwords.py`) so `/api/wiki/` returns real data.
3. Resolve LoRA adapter path contract mismatch between trainer output and backend loader expectations.
4. Decide tracking policy for currently untracked but active files (`SystemEvaluationScreen`, `GapAnalysisTerminal`, cloud docs/scripts).
5. Review and clean `.tools/` and other non-source artifacts before commit packaging.
