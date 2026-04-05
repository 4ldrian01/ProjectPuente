# Project Puente — Comprehensive Repository Scan (Fully Updated)

Generated: 2026-04-05
Workspace: `c:\Users\User's\ALL FILES - MACHINE LEARNING\ProjectPuente`

This report is a full, source-backed re-scan of the repository and current workspace state.
It updates and replaces older sections with current code behavior, including:

- Spanish control-variable support (`es`) across backend/frontend/ML tooling
- Back-Translation Verification Loop (BTVL) endpoint and UI integration
- Translation Memory (TM) cache routing before NLLB inference
- Wiki-Voz greedy phrase/n-gram interception (longest match)
- New seed/evaluation scripts and their output artifacts
- Current operational scripts, PWA constraints, and validated test/lint status

### Delta updates in this pass

- Centralized backend language/FLORES contract in `backend/core_api/languages.py` and rewired models, serializers, views, and tests to use it.
- Added `ml_models/training_preflight.py` for read-only architecture/training readiness checks with JSON report output.
- Added `TRAINING_PREFLIGHT_CHECKLIST.md` for operator workflow before training/evaluation runs.
- Hardened active notebook pipeline scripts against cross-platform path casing via `notebooks/scripts/_path_utils.py` (`datasets/` canonical, `Datasets/` fallback).
- Updated `run_nllb_pipeline.py` to invoke child scripts via `sys.executable` (active interpreter consistency).
- Removed verified legacy duplicate notebook scripts superseded by refined variants:
	- `notebooks/scripts/extract_chavacano_pdf.py`
	- `notebooks/scripts/process_chavacano_csv.py`
	- `notebooks/scripts/process_tatoeba01.py`
	- `notebooks/scripts/harvest_creole-rc_data.py`

---

## 0) Completeness Verification (This Pass)

This scan used live repository/state checks and full-file reads of core implementation files.

- **Tracked files (authoritative):** run `git ls-files` for the current exact count.
- **Untracked files currently present:**
	- `PROJECT_PUENTE_COMPREHENSIVE_SCAN.md`
	- `TRAINING_PREFLIGHT_CHECKLIST.md`
	- `backend/core_api/languages.py`
	- `backend/core_api/migrations/0003_add_es_language_choices.py`
	- `backend/core_api/migrations/0004_culturalterm_language_free_text.py`
	- `backend/scripts/seed_spanish_baseline.py`
	- `backend/scripts/seed_spanish_loanwords.py`
	- `datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv`
	- `frontend/.env.example`
	- `frontend/public/local-assets/README.md`
	- `frontend/public/local-assets/placeholder.jpg`
	- `frontend/src/lib/apiAuth.js`
	- `ml_models/evaluate_metrics.py`
	- `ml_models/evaluate_spanish_baseline.py`
	- `ml_models/evaluation_results.json`
	- `ml_models/spanish_baseline_input.json`
	- `ml_models/spanish_baseline_metrics.json`
	- `ml_models/training_preflight.py`
	- `notebooks/scripts/_path_utils.py`
	- `puente_high_level_architecture.mmd`

### Validation runs observed in this session

- Django tests: `46/46` passing (`backend/manage.py test core_api.tests`)
- Frontend lint: passed (`npm run lint`)
- Migrations applied: `core_api.0003_add_es_language_choices`, `core_api.0004_culturalterm_language_free_text`
- Evaluation artifacts exist, but currently in `error` state due missing `torch` in runtime environment for metric execution

---

## 1) High-Level System Summary

PUENTE is an offline-first LAN translation system with a modular 5-agent architecture plus new BTVL verification.

Primary runtime stack:

- **Backend:** Django + DRF + SQLite
- **Frontend:** React 19 + Vite 7 + Tailwind 4
- **Neural runtime:** NLLB-200-distilled-600M (+ optional LoRA adapters)
- **Speech:** backend `edge-tts` endpoint (internet-dependent)

Current supported app language codes:

- `auto`, `en`, `es`, `tl`, `cbk`, `hil`, `ceb`

Core runtime endpoints:

- `POST /api/translate/`
- `POST /api/btvl/`
- `POST /api/tts/`
- `GET /api/wiki/`
- `GET /api/telemetry/`
- `GET /api/health/`
- `GET /` (API root metadata)

---

## 2) Backend Deep Scan (Actual File Internals)

### 2.1 `backend/backend/settings.py`

Key behavior inside the file:

- Loads env values from `backend/.env` using `python-dotenv`
- Hard-fails if `SECRET_KEY` is missing
- `DEBUG` parsed via helper `_env_bool`
- `ALLOWED_HOSTS` parsed via helper `_env_list`; in debug, appends `*` when absent
- SQLite default DB at `backend/db.sqlite3`
- Guard: if `DEBUG=False` and DB engine is non-SQLite, password must exist
- CORS/CSRF configurable via env with LAN/dev-friendly defaults
- DRF anonymous throttle configurable via `DRF_THROTTLE_ANON_RATE`
- Optional production flags: SSL redirect, secure cookies, HSTS
- `STRICT_OFFLINE_MODE` flag gates internet-dependent features
- Optional `PUENTE_API_KEY` protects write endpoints (`X-API-Key` header)
- Edge-TTS voice/rate/volume/pitch env fields defined per language code

### 2.2 `backend/backend/urls.py`

Routes registered now include BTVL:

- `/` → `APIRootView`
- `/admin/`
- `/api/translate/` → `TranslateView`
- `/api/btvl/` → `BackTranslationVerifyView`
- `/api/telemetry/` → `telemetry_view`
- `/api/tts/` → `TextToSpeechView`
- `/api/wiki/` → `WikiVozView`
- `/api/health/` → `HealthCheckView`

### 2.3 `backend/core_api/serializers.py`

#### `TranslateRequestSerializer`
- `text`: `CharField(max_length=250)`
- `source_lang`: `['auto','en','es','tl','cbk','hil','ceb']`
- `target_lang`: `['en','es','tl','cbk','hil','ceb']`
- `mode`: `formal|street` (default `formal`)

#### `BackTranslationRequestSerializer`
- `text`: `max_length=250`
- `source_lang`: `['en','es','tl','cbk','hil','ceb']`
- `target_lang`: only `en` (default)

#### `TextToSpeechRequestSerializer`
- `text`: `max_length=1000`
- `lang_code`: includes `auto,en,es,tl,cbk,hil,ceb`
- optional `voice`

### 2.4 `backend/core_api/models.py` + `backend/core_api/languages.py`

Language and FLORES scope is now centralized in `core_api/languages.py` and reused by:

- `models.py` (`LANGUAGE_CHOICES`, `TARGET_LANGUAGE_CHOICES`)
- `serializers.py` (`SOURCE_LANGUAGE_CODES`, `TARGET_LANGUAGE_CODES`)
- `views.py` (`SUPPORTED_LANGUAGES`, `FLORES_MAP`, `PIVOT_LANG`)

#### `CulturalTerm`
- Fields: `term` (unique/indexed), `definition`, `image_url`, `language`, `category`, timestamps
- `language` is free text (supports real origin labels like `Chavacano`, `Tausug`, `Zamboanga`)
- Ordering by `term`

#### `TranslationLog`
- Captures request metadata (`source_lang`, `target_lang`, `mode`, text, chars, tokens)
- Captures response metadata (`output_text`, output tokens, model name, pivot flag)
- Captures reliability/perf (`latency_ms`, `status`, `error_message`)
- Captures Wiki-Voz interception markers
- Indexed by `created_at`, language pair, and status

### 2.5 `backend/core_api/apps.py` (Singleton model loader)

Current loader behavior:

- Class-level singleton state: tokenizer/model/adapter map/loaded flag
- Skip heavy model init for commands: `test`, `migrate`, `makemigrations`, `collectstatic`, `createsuperuser`, `shell`, `dbshell`
- Respects env switch `PUENTE_LOAD_MODEL_ON_STARTUP` (can disable startup load)
- Avoids double-load during `runserver` autoreload (`RUN_MAIN` guard)
- Loads model from fixed project path: `ml_models/nllb-200-distilled-600M`
- Device strategy:
	- CUDA + bitsandbytes → INT8
	- CUDA no bitsandbytes → FP16
	- no CUDA → FP32 CPU
- LoRA logic:
	- Loads adapter directories if present (`lora-cbk-formal`, `lora-cbk-street`)
	- Stores adapter names for dynamic `set_adapter` use

### 2.6 `backend/core_api/views.py`

#### Global mappings/config
- `FLORES_MAP`: now includes `'es': 'spa_Latn'`
- `PIVOT_LANG = 'eng_Latn'`
- `SUPPORTED_LANGUAGES`: includes `es`
- `EDGE_TTS_DEFAULT_VOICES` includes Spanish default voice

#### Inference functions
- `_infer_once()`: single NLLB generate pass with `torch.no_grad()`, beams=4, max_new_tokens=128
- `nllb_translate()`:
	- Resolves adapter by `mode`
	- Handles same-language short-circuit
	- Uses English two-hop pivot when both source+target are non-English
	- Returns tuple: text, latency, token counts, pivot flag, model label

#### `TranslateView.post()`
- Enforces optional API key protection (`X-API-Key`) when backend key is configured
- Validates serializer
- Performs greedy multi-word Wiki-Voz phrase interception (length-desc matching)
- Checks Translation Memory cache in `TranslationLog` using normalized input (`strip + lowercase`) plus source/target language pair
- On cache hit: bypasses NLLB inference and returns cached output with `is_cached=true`
- Same-language pass-through path with immediate response + logging
- Fails with 503 when model not loaded
- Logs success/error in `TranslationLog`
- Returns translation payload including model, latency, token counts, pivot flag, `is_cached`, and optional `wiki_voz`

#### `BackTranslationVerifyView.post()`
- Endpoint: `/api/btvl/`
- Enforces optional API key protection (`X-API-Key`) when backend key is configured
- Validates BTVL serializer
- Requires model loaded (503 otherwise)
- Executes `nllb_translate(... mode='formal')` to target English
- Returns verification payload: text, model, latency, tokens, pivot flag

#### `WikiVozView.get()`
- `?q=` present → `term__icontains`, `[:20]`
- no query → full ordered list, `[:100]`

#### `TextToSpeechView.post()`
- Enforces optional API key protection (`X-API-Key`) when backend key is configured
- Blocks when strict offline mode is enabled
- Validates request serializer
- Calls `_synthesize_speech_bytes()` via `edge-tts`
- Returns `audio/mpeg` + headers (`X-TTS-Voice`, no-store)
- Handles validation/service exceptions with 400/503/502 paths

#### `HealthCheckView.get()`
- Returns backend/model/adapter/tts status and supported languages
- Exposes `api_key_required` + `api_key_header` and keeps `api_key_configured` for compatibility

### 2.7 `backend/core_api/admin.py`

- `CulturalTermAdmin`: search/filter/order by language/category/created
- `TranslationLogAdmin`: ISO-oriented metrics columns, filters, search, date hierarchy

### 2.8 `backend/core_api/tests.py`

Current suite totals **46 tests** covering:

- Translation serializer constraints
- TTS serializer validation
- BTVL serializer validation
- SUPPORTED_LANGUAGES scope and disallowed lang checks
- FLORES map completeness + Spanish mapping
- Pivot logic test (`es -> hil` confirms two-hop via English)
- CulturalTerm model queries
- TranslationLog model behavior
- Wiki endpoint behavior
- Health endpoint fields/language scope
- TTS endpoint mocked success/failure
- TranslateView validation cases
- Translation Memory cache hit/miss routing
- Greedy Wiki-Voz longest-phrase interception
- BTVL view success/error/validation cases
- API-key-protection behavior for write endpoints

### 2.9 Migrations

- `0001_initial.py`: base `CulturalTerm`
- `0002_culturalterm_category_culturalterm_language_and_more.py`: category/language + `TranslationLog`
- `0003_add_es_language_choices.py` (untracked/new): adds `es` to model-level field choices
- `0004_culturalterm_language_free_text.py` (untracked/new): restores free-text `CulturalTerm.language`

### 2.10 Backend scripts (`backend/scripts/`)

- `create_superuser.py`: generates strong random superuser creds and prints to stdout
- `list_superusers.py`: prints non-sensitive superuser account metadata
- `seed_spanish_baseline.py` (new): seeds 5 pure Spanish baseline terms (`language='es'`, category `Spanish Baseline`)
- `seed_spanish_loanwords.py` (new): ingests CSV mapping (`spanish_loanwords_mapping.csv`) into `CulturalTerm` with dry-run/update/skip support

---

## 3) Frontend Deep Scan (Actual File Internals)

### 3.1 `frontend/src/App.jsx`

Core responsibilities:

- Computes LAN API URL dynamically: `http://${window.location.hostname}:8000/api`
- Tracks app navigation state (`translate`, `wiki-voz`, `settings` overlay)
- Polls health every 30 seconds
- Aborts stale translation requests using `AbortController`
- Sends optional `X-API-Key` header to write endpoints when `VITE_PUENTE_API_KEY` is set
- Syncs persisted theme (`dark` / `light`) across tabs via localStorage + custom event
- Wraps screen transitions with motion classes (`screen-transition-in`) for smoother tab/screen changes
- Injects backend readiness into Translate screen:
	- `apiReady = backendUp && nllbLoaded && (!apiKeyRequired || clientApiKeyConfigured)`

### 3.2 `frontend/src/components/screens/TranslateScreen.jsx`

Implemented behaviors inside this file:

- Language selectors now include Spanish in source/target dropdown sets
- Mutual-exclusion logic between source/target language choices
- 800ms debounce auto-translate
- Sociolinguistic mode toggle (`formal` / `street`)
- Input handling uses **250-character guard** aligned with backend serializer
- Character counter appears only after user starts typing
- Source and target TTS buttons call backend `/api/tts/`
- BTVL button sends translated text to `/api/btvl/` and renders diagnostics panel
- Cultural term highlighting uses `CULTURAL_TERMS_MAP`
- Hover tooltip + modal entry display for Wiki-Voz terms
- Mode-status banner reflects backend/API-key/model/adapter readiness states
- Status banner uses semantic color variants and optional progress rail for model-not-loaded guidance

### 3.3 `frontend/src/components/LanguageSelector.jsx`

- Desktop: tab strip + animated underline indicator
- Mobile: single dropdown
- Language list includes `auto,en,tl,cbk,ceb,hil,es`
- Dynamically excludes opposite-side selected language code
- Uses spring motion classes for tab, icon, and indicator transitions

### 3.4 `frontend/src/components/screens/WikiVozScreen.jsx`

- Fetches `/api/wiki/` on mount
- Maps API payload to card schema
- Falls back to offline `WIKI_VOZ_ENTRIES` when API fails
- Filter panel supports both category chips and language chips
- Filter state supports reset (`Clear filters`) and active filter indicator
- First render shows 20 cards, with `View More` pagination in +20 increments
- Masonry-like column layout on larger breakpoints with deterministic varied image aspect ratios
- Forces image source to local placeholders for remote/non-local URLs
- Uses reusable `CulturalTermPopup` modal for card detail display

### 3.5 `frontend/src/components/screens/SettingsScreen.jsx`

- Persists default source/target language to localStorage via shared lib
- Persists and toggles full-app theme (`dark` / `light`)
- Shows backend/model/LoRA/TTS status from health payload
- Polls backend `/api/telemetry/` and renders live RAM/GPU utilization
- Shows API-key requirement + client key configuration status
- Shows about-card summary with Wiki-Voz seed counts

### 3.6 `frontend/src/lib/settings.js`

- Canonical source/target code arrays include Spanish
- Sanitizes persisted settings and prevents invalid same-language non-auto pair
- Emits `puente-settings-updated` custom event on save

### 3.7 `frontend/src/lib/ttsClient.js`

- Uses axios blob requests to `/api/tts/`
- Normalizes `lang_code` and supports default Spanish voice fallback
- Ensures single active playback (abort/cleanup old audio/object URLs)
- Converts blob error payloads to readable message

### 3.8 Frontend shell/config

- `frontend/src/main.jsx`: wraps app in `StrictMode` and `ErrorBoundary`; applies saved theme on boot
- `frontend/src/index.css`: defines dark/light design tokens and semantic status colors via CSS variables
- `frontend/src/App.css`: centralized spring timings, transition utilities, and screen/indicator motion tokens
- `frontend/src/lib/apiAuth.js`: optional frontend API-key header helper
- `frontend/.env.example`: template for `VITE_PUENTE_API_KEY`
- `frontend/index.html`: system font stack, manifest wired, dark theme metadata
- `frontend/public/manifest.json`: standalone PWA metadata + SVG icon declarations
- `frontend/vite.config.js`:
	- React SWC + Tailwind plugin
	- PWA plugin with path quirk guard: disabled if current path contains apostrophe (`'`)
	- runtime cache strategies for `/api/health/` and `/api/wiki/`

### 3.9 Navigation and modal interaction polish

- `frontend/src/components/layout/Header.jsx` adds animated desktop active-indicator tracking using measured button geometry
- `frontend/src/components/layout/BottomNav.jsx` adds spring-based mobile tab states and active rail indicator
- `frontend/src/components/CulturalTermPopup.jsx` is now a centered, reusable modal with backdrop blur, Esc-to-close, and resilient image fallback
- Transition design is tuned for smoother perceived behavior across both 60Hz and higher-refresh displays

### 3.10 Offline data file internals (`frontend/src/data/wikiVozData.js`)

- Defines curated entries + generated template entries
- Exports:
	- `WIKI_VOZ_ENTRIES`
	- `WIKI_VOZ_ENTRY_GOAL`
	- `CULTURAL_TERMS_MAP`
	- `getCulturalEntry()`
- Template generation by language:
	- Chavacano templates: 24
	- Hiligaynon templates: 26
	- Cebuano/Bisaya templates: 28

---

## 4) ML / Evaluation Pipeline Scan

### 4.1 `ml_models/README.md`

Documents:

- required runtime packages (`torch`, `transformers`, `sentencepiece`, `accelerate`, `peft`, optional `bitsandbytes`)
- optional extras (`datasets`, `evaluate`, `sacrebleu`, `wandb`)
- baseline evaluation scripts and expected output files
- supported FLORES code map (now includes `spa_Latn`)

### 4.2 `ml_models/evaluate_metrics.py` (new, untracked)

Key capabilities:

- Generic BLEU + chrF++ evaluator using local model
- Supports language pair options including Spanish
- Optional LoRA mode loading (`base`, `formal`, `street`)
- Flexible dataset extraction by candidate keys
- Outputs structured JSON report to `evaluation_results.json`
- On failure writes structured `status:error` payload

### 4.3 `ml_models/evaluate_spanish_baseline.py` (new, untracked)

Key capabilities:

- Focused Spanish baseline evaluator (`spa_Latn -> eng_Latn`)
- Accepts optional JSON input pair file
- Computes BLEU + chrF++ via `sacrebleu`
- Outputs structured report to `spanish_baseline_metrics.json`
- On failure writes structured error payload with FLORES metadata

### 4.4 Current generated artifacts

- `ml_models/evaluation_results.json` → `status: error` (missing `torch`)
- `ml_models/spanish_baseline_metrics.json` → `status: error` (missing `torch`)
- `ml_models/spanish_baseline_input.json` includes 7 Spanish-English pairs

### 4.5 Existing ML scripts (tracked)

- `download_model.py`: pulls NLLB-200-distilled-600M locally
- `train_lora.py`: LoRA finetuning workflow
- `validate_model.py`: model/adapter smoke checks

---

## 5) Data, Datasets, and Notebooks Scan

### 5.1 Datasets

`datasets/` contains:

- `processed/001_chavacano/` refined NLLB-ready outputs and readiness report
- `processed/01_chavacano/` legacy processed artifacts
- `raw/` corpora and archives for Tagalog/Chavacano/Cebuano/Hiligaynon and monolingual sources

New untracked dataset file:

- `datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv`
	- 20 Spanish-derived Chavacano terms with origin/gloss/definition/category columns

### 5.2 Notebooks and scripts

Notebook files:

- `notebooks/lora_training.ipynb`
- `notebooks/model_validation.ipynb`
- `notebooks/sample.ipynb`

`notebooks/scripts/` now keeps refined ETL/data-processing scripts plus `_path_utils.py` for canonical `datasets/` resolution.

`notebooks/README.md` documents notebook kernel dependencies and optional extras.

---

## 6) Operations, Launch, and Workspace Tooling

### 6.1 Launcher scripts

- `run_project.ps1`
	- Supports `-BackendOnly` / `-FrontendOnly`
	- Port conflict checks before startup
	- Starts backend/frontend subprocesses for full stack mode
	- Uses `PUENTE_LOAD_MODEL_ON_STARTUP=true`
	- Displays LAN endpoint summary
	- Cleans child process tree on exit

- `run_project.bat`
	- Validates script and required paths
	- Delegates to PowerShell launcher in same terminal

- `run_project.sh`
	- Linux/macOS equivalent with `--backend-only` / `--frontend-only`
	- Port checks and combined server lifecycle handling

### 6.2 VS Code task definitions (`.vscode/tasks.json`)

Tasks available:

- `Puente: Start full stack`
- `Puente: Start backend`
- `Puente: Start frontend`

Windows branches call `.bat`/`cmd`-compatible commands; non-Windows branches use `bash`.

### 6.3 Root package scripts (`package.json`)

- `backend`
- `frontend`
- `start` (points to `run_project.bat`)

---

## 7) API Contract (Current, Verified)

### `POST /api/translate/`

Input fields:

- `text` (<= 250 chars, backend enforced)
- `source_lang` in `auto,en,es,tl,cbk,hil,ceb`
- `target_lang` in `en,es,tl,cbk,hil,ceb`
- `mode` in `formal,street` (optional, defaults formal)
- requires `X-API-Key` only when backend `PUENTE_API_KEY` is configured

Success payload includes:

- `translated_text`, `model`, `latency_ms`, `tokens_in`, `tokens_out`, `pivot_used`, `is_cached`
- plus `wiki_voz` when phrase-level cultural intercept hits (greedy longest match)

### `POST /api/btvl/`

Input fields:

- `text` (<= 250 chars)
- `source_lang` in `en,es,tl,cbk,hil,ceb`
- optional `target_lang` (effectively fixed to `en`)
- requires `X-API-Key` only when backend `PUENTE_API_KEY` is configured

Success payload includes:

- `verified_text`, `source_lang`, `target_lang`, `model`, `latency_ms`, `tokens_in`, `tokens_out`, `pivot_used`

### `POST /api/tts/`

Input fields:

- `text` (<= 1000 chars)
- `lang_code` in `auto,en,es,tl,cbk,hil,ceb`
- optional `voice`
- requires `X-API-Key` only when backend `PUENTE_API_KEY` is configured

Returns:

- `audio/mpeg` bytes
- header `X-TTS-Voice`

### `GET /api/wiki/`

- with `?q=` → filtered search
- without `q` → first 100 ordered terms

### `GET /api/health/`

Returns:

- backend status
- engine / model-loaded status
- loaded LoRA adapter names
- TTS availability
- strict offline mode flag
- API-key requirement metadata (`api_key_required`, `api_key_header`)
- supported language code list

### `GET /api/telemetry/`

Returns live backend host metrics:

- RAM used/total/percent
- GPU used/total/percent (when CUDA is available)

---

## 8) Security, Reliability, and Consistency Findings

### Strong points

- Serializer validation at API boundary
- ORM-based DB queries (SQL injection-resistant pattern)
- Explicit model-not-loaded failfast and health introspection
- Translation logging with structured performance/reliability fields
- Request cancellation on frontend to avoid stale render races

### Important caveats (verified in source)

1. **NLLB model still missing in this workspace runtime**
	 - Backend logs show `ml_models/nllb-200-distilled-600M` missing, so translation/BTVL return 503 until model installation.

2. **PWA plugin path quirk**
	 - PWA build is auto-disabled when cwd contains apostrophe (`'`).

3. **API-key protection requires frontend/backend key parity**
	 - When backend `PUENTE_API_KEY` is set, frontend must provide matching `VITE_PUENTE_API_KEY` for write actions.

4. **Edge TTS availability constraints**
	 - `/api/tts/` depends on `edge-tts` + outbound internet
	 - forced disabled when `STRICT_OFFLINE_MODE=True`

5. **Large active untracked surface remains**
	 - Multiple new scripts/artifacts/docs are still untracked and should be reviewed before commit.

---

## 9) Complete Inventory Manifests

### 9.1 Exact tracked manifest (`git ls-files` snapshot)

```text
.gitignore
README.md
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
backend/core_api/migrations/0001_initial.py
backend/core_api/migrations/0002_culturalterm_category_culturalterm_language_and_more.py
backend/core_api/migrations/__init__.py
backend/core_api/models.py
backend/core_api/serializers.py
backend/core_api/tests.py
backend/core_api/views.py
backend/manage.py
backend/requirements.txt
backend/scripts/create_superuser.py
backend/scripts/list_superusers.py
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
datasets/raw/monolingual/conversations/zambo-artesanía.csv
frontend/.gitignore
frontend/README.md
frontend/eslint.config.js
frontend/index.html
frontend/package-lock.json
frontend/package.json
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
frontend/src/lib/settings.js
frontend/src/lib/ttsClient.js
frontend/src/main.jsx
frontend/vite.config.js
ml_models/.gitkeep
ml_models/README.md
ml_models/download_model.py
ml_models/train_lora.py
ml_models/training_preflight.py
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
run_project.bat
run_project.ps1
run_project.sh
```

### 9.2 Untracked manifest (current workspace)

```text
PROJECT_PUENTE_COMPREHENSIVE_SCAN.md
TRAINING_PREFLIGHT_CHECKLIST.md
backend/core_api/languages.py
backend/core_api/migrations/0003_add_es_language_choices.py
backend/core_api/migrations/0004_culturalterm_language_free_text.py
backend/scripts/seed_spanish_baseline.py
backend/scripts/seed_spanish_loanwords.py
datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv
frontend/.env.example
frontend/public/local-assets/README.md
frontend/public/local-assets/placeholder.jpg
frontend/src/lib/apiAuth.js
ml_models/evaluate_metrics.py
ml_models/evaluate_spanish_baseline.py
ml_models/evaluation_results.json
ml_models/spanish_baseline_input.json
ml_models/spanish_baseline_metrics.json
ml_models/training_preflight.py
notebooks/scripts/_path_utils.py
puente_high_level_architecture.mmd
```

### 9.3 Runtime-local sensitive artifacts (existence only)

```text
.env
backend/.env
backend/db.sqlite3
.vscode/tasks.json
```

---

## 10) Final Practical Status (As of This Scan)

- Backend routing/validation/model orchestration is coherent and currently test-green.
- `/api/translate/` now uses Translation Memory-first routing to reduce unnecessary GPU inference on repeat requests.
- Backend now supports optional API-key protection for mutating endpoints plus DRF anonymous throttling.
- Wiki-Voz interception is now phrase-aware with greedy longest-match behavior.
- Spanish control-variable integration is present across model mapping, serializers, UI selectors, TTS mapping, migration, and evaluation tooling.
- BTVL backend endpoint and frontend UX path are implemented.
- Frontend write requests now support optional `X-API-Key` propagation through `VITE_PUENTE_API_KEY`.
- Frontend now includes spring-tuned tab/screen transitions and reusable modal flows for Wiki-Voz detail views.
- Wiki-Voz list UX now supports category+language filtering and progressive 20-card pagination.
- ML evaluator scripts are in place but currently produce error reports in this environment until dependencies/model runtime are available.
- Input-limit semantics are now aligned at 250 characters across backend and UI.

### Recommended next hardening actions

1. Run `ml_models/training_preflight.py` and resolve all `BLOCKER` findings before starting LoRA training/evaluation.
2. Install local NLLB model files in `ml_models/nllb-200-distilled-600M` and re-validate end-to-end translation latency.
3. Decide whether `PUENTE_API_KEY` should be required by default for deployment profiles (campus LAN hardening policy).
4. Review and stage the untracked additions (new scripts/migrations/docs) with commit grouping.

