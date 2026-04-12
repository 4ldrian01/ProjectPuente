# Project Puente - Comprehensive Repository Scan (Current)

Generated: 2026-04-10T23:39+08:00  
Workspace: `C:\Users\User's\ALL FILES - MACHINE LEARNING\ProjectPuente`  
Branch: `main`

This report is a full source-backed scan of the current repository plus live local runtime probes.  
It supersedes older snapshots and is synchronized to the currently checked out commit.

---

## 0) Completeness Verification

### 0.1 Evidence sources used

- Repository source reads across backend, frontend, datasets, ML, and notebooks
- Live git state probes:
  - `git branch --show-current`
  - `git rev-parse HEAD`
  - `git rev-parse origin/main`
  - `git rev-list --left-right --count HEAD...origin/main`
  - `git status --short`
  - `git ls-files`
- Live API probes:
  - `/`
  - `/api/health/`
  - `/api/wiki/`
  - `/api/logs/`
  - `/api/telemetry/`
- Quality checks:
  - `backend/manage.py test core_api`
  - `frontend npm run lint`
  - `frontend npm run build`
  - `ml_models/training_preflight.py`

### 0.2 Git provenance (current)

- Current branch: `main`
- `HEAD`: `7290ee6b071465f403d1c35d1cdc01c4fa63ec2b`
- `origin/main`: `7290ee6b071465f403d1c35d1cdc01c4fa63ec2b`
- Ahead/behind: `0 / 0`

### 0.3 Local modified working set (current)

```text
M frontend/package-lock.json
M frontend/package.json
M ml_models/download_model.py
```

### 0.4 Tracked-file count

- Tracked files (`git ls-files`): **187**

---

## 1) High-Level Architecture Summary

PUENTE is an offline-first LAN translation system with a layered 5-agent architecture documented in `agents.md`.

Runtime stack:

- Backend: Django + DRF + SQLite
- Frontend: React 19 + Vite 7 + Tailwind + PWA
- Neural runtime: local NLLB (`ml_models/nllb-200-distilled-600M`) + optional LoRA adapters
- Optional speech: `edge-tts`

Core backend routes:

- `POST /api/translate/`
- `POST /api/btvl/`
- `POST /api/tts/`
- `GET /api/wiki/`
- `GET /api/logs/`
- `GET /api/telemetry/`
- `GET /api/health/`
- `GET /`

Canonical language scope (`backend/core_api/languages.py`):

- `auto`, `en`, `es`, `tl`, `cbk`, `hil`, `ceb`

---

## 2) Runtime Validation (Local Machine, Current Session)

### 2.1 API health snapshot

`GET /api/health/` returned:

- `status: ok`
- `engine: offline-model-missing`
- `nllb_loaded: false`
- `lora_adapters: []`
- `api_key_required: false`
- `tts_available: true`
- `strict_offline_mode: false`
- `cloud_fallback_allowed: false`
- `inference_mode: offline-local-only`

### 2.2 Endpoint probe summary

| Endpoint | HTTP | Observed |
|---|---:|---|
| `/` | 200 | API root online, engine `offline-model-missing` |
| `/api/health/` | 200 | Backend online, model not loaded |
| `/api/wiki/` | 200 | Empty results array |
| `/api/logs/?limit=5` | 200 | Returns observer rows with route metadata |
| `/api/telemetry/` | 200 | RAM payload + GPU unavailable fallback reason |

### 2.3 DB cardinality snapshot

From Django shell in current environment:

- `CulturalTerm`: `0`
- `TranslationLog`: `4`

Implication:

- Wiki endpoint is healthy but currently empty because `CulturalTerm` has no rows.

### 2.4 Verification command results

| Check | Result |
|---|---|
| Backend tests | `57/57` passing |
| Frontend lint | pass |
| Frontend build | pass |
| Training preflight | `BLOCKED` (1 blocker) |

Latest preflight summary:

- `PASS: 16`
- `WARN: 2`
- `BLOCKER: 1`
- blocker: missing local base model directory

---

## 3) Backend Deep Scan

### 3.1 Settings and runtime gates

`backend/backend/settings.py` confirms:

- `SECRET_KEY` hard requirement
- SQLite default DB
- CORS/CSRF env controls
- DRF throttling support
- `ML_MODEL_PATH` support
- `PUENTE_API_KEY` optional write-endpoint protection
- `STRICT_OFFLINE_MODE` support
- `EDGE_TTS_*` tuning support

### 3.2 URL map

`backend/backend/urls.py` includes:

- root API, admin, translate, btvl, logs, telemetry, tts, wiki, health

### 3.3 Contracts and serializers

`backend/core_api/serializers.py` enforces:

- translate text max `250`
- btvl text max `250`
- tts text max `1000`
- strict language choice sets
- mode choices `formal|street`

### 3.4 Models

`backend/core_api/models.py` includes:

- `CulturalTerm` (term/definition/image/language/category)
- `TranslationLog` with route confidence + status + observer metadata

### 3.5 Loader and model bootstrap

`backend/core_api/apps.py`:

- singleton model/tokenizer/adapters
- gated startup load via `PUENTE_LOAD_MODEL_ON_STARTUP`
- local-only loading (`local_files_only=True`)
- adapter directories expected at:
  - `ml_models/lora_adapters/lora-cbk-formal`
  - `ml_models/lora_adapters/lora-cbk-street`

### 3.6 Views and pipeline behavior

`backend/core_api/views.py` confirms:

- API-key middleware behavior
- TM cache lookup before inference
- greedy phrase interception for Wiki-Voz
- same-language passthrough path
- direct-first routing + proximate pivot fallback
- observer logging on success/error
- logs endpoint filters and route normalization

### 3.7 Migrations

Tracked migration set:

- `0001_initial`
- `0002_culturalterm_category_culturalterm_language_and_more`
- `0003_add_es_language_choices`
- `0004_culturalterm_language_free_text`
- `0005_translationlog_route_confidence`

### 3.8 Tests

`backend/core_api/tests.py` currently exercises:

- serializer boundaries
- language contract + FLORES mapping
- pivot routing policy
- TM cache behavior
- interception behavior
- API key protection
- logs/health/wiki/btvl/tts endpoint contracts

---

## 4) Frontend Deep Scan

### 4.1 App shell

`frontend/src/App.jsx` currently mounts screens for:

- translate
- wiki-voz
- activity-logs
- evaluation
- db-admin
- settings

It handles:

- health polling
- route/path synchronization
- LAN API resolution flow
- request cancellation and toast feedback

### 4.2 Runtime host resolver

`frontend/src/lib/apiRuntime.js` provides:

- runtime host/port detection
- local alias handling (`projectpuente.local`, localhost variants)
- health-based API URL fallback selection

### 4.3 Layout system

- `GlobalHeader.jsx` for top status controls
- `SidebarNav.jsx` for desktop rail and mobile drawer

### 4.4 Screen-level functions

- `TranslateScreen.jsx`: translation/BTVL/TTS/telemetry workbench
- `WikiVozScreen.jsx`: API + fallback lexicon browser
- `ActivityLogsScreen.jsx`: observer flight recorder + CSV export
- `DatabaseAdminScreen.jsx`: mock CRUD + CSV import panel
- `SystemEvaluationScreen.jsx`: KPI/chart dashboard
- `SettingsScreen.jsx`: preference + health panel

### 4.5 PWA/build config

`frontend/vite.config.js`:

- PWA plugin enabled with manual manifest
- runtime caching for `/api/health/` and `/api/wiki/`
- PWA auto-disable when path contains apostrophe

---

## 5) Data and ML Pipeline Scan

### 5.1 3-pillar dataset architecture

Documented and implemented via `datasets/scripts`:

- Pillar 1 parallel corpus
- Pillar 2 monolingual corpus
- Pillar 3 lexicon SQL ingestion

Tracked outputs now include:

- `datasets/processed/pillars/...` JSON outputs
- `datasets/processed/jsonl/pillars/...` JSONL outputs

### 5.2 ML scripts

`ml_models/` includes:

- model downloader
- validation script
- LoRA training script
- evaluation scripts
- readiness preflight

### 5.3 Current blocker

Preflight blocker is still:

- missing base model directory at `ml_models/nllb-200-distilled-600M`

No download action was performed in this update pass (per instruction).

---

## 6) Requirements and Dependency Manifests

### 6.1 Backend requirements

`backend/requirements.txt` now documents and includes:

- Django/DRF core
- NLLB runtime stack
- telemetry + optional TTS
- script/preflight utilities (`pandas`, `pdfplumber`, `ijson`)

### 6.2 Colab requirements

`notebooks/scripts/requirements_colab.txt` now includes:

- core training stack
- reliability/evaluation helpers (`huggingface_hub`, `evaluate`, `sacrebleu`, `pandas`, `pyyaml`)

### 6.3 Raw dataset package requirement

`datasets/raw/02_Chavacano/creole_rc/requirements.txt` remains intentionally minimal and scoped to source retrieval (`seacrowd`).

---

## 7) Current Findings (Actionable)

### 7.1 Confirmed healthy areas

- Backend test suite passes (`57/57`)
- Frontend lint/build pass
- API health/logs/telemetry/wiki endpoints are reachable
- Language contract is synchronized for current code

### 7.2 Confirmed runtime limitations

1. **Translation/BTVL blocked by missing local model**
   - `offline-model-missing`, expected `503` for translate/BTVL until model assets exist.

2. **Wiki-Voz DB empty on this machine**
   - `CulturalTerm=0`, so `/api/wiki/` returns empty results.

3. **Environment duplication warning**
   - preflight reports both `venv/` and `.venv/` present.

4. **Interpreter module warning**
   - preflight indicates some modules missing in active interpreter context (`torch`, `transformers`, `peft`, `sacrebleu`).

---

## 8) Tracked File Manifest (Exact `git ls-files` Snapshot)

```text
.gitignore
CLOUD_TO_LOCAL_DEPLOYMENT_GUIDE.md
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
backend/core_api/management/__init__.py
backend/core_api/management/commands/__init__.py
backend/core_api/management/commands/ingest_lexicon.py
backend/core_api/migrations/0001_initial.py
backend/core_api/migrations/0002_culturalterm_category_culturalterm_language_and_more.py
backend/core_api/migrations/0003_add_es_language_choices.py
backend/core_api/migrations/0004_culturalterm_language_free_text.py
backend/core_api/migrations/0005_translationlog_route_confidence.py
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
datasets/archive/legacy_cleanup_20260407T230713Z/archive_manifest.json
datasets/processed/001_chavacano/NLLB_READINESS_REPORT.md
datasets/processed/001_chavacano/chavacano_lexicon_nllb.json
datasets/processed/001_chavacano/chavacano_parallel_sentences_nllb.json
datasets/processed/001_chavacano/creole_rc_chavacano_nllb.json
datasets/processed/001_chavacano/creole_rc_sentences.txt
datasets/processed/001_chavacano/eval.jsonl
datasets/processed/001_chavacano/pipeline_report.json
datasets/processed/001_chavacano/split_report.json
datasets/processed/001_chavacano/tatoeba_parallel_nllb.json
datasets/processed/001_chavacano/test.jsonl
datasets/processed/001_chavacano/train.jsonl
datasets/processed/01_chavacano/chavacano_lexicon.json
datasets/processed/01_chavacano/creole_rc_chavacano_text.txt
datasets/processed/01_chavacano/new_chavacano_master_dataset.json
datasets/processed/01_chavacano/tatoeba_dataset.json
datasets/processed/01_chavacano/wiki_monolingual_FINAL.txt
datasets/processed/jsonl/001_chavacano/chavacano_lexicon_nllb.jsonl
datasets/processed/jsonl/001_chavacano/chavacano_lexicon_nllb.jsonl.meta.json
datasets/processed/jsonl/001_chavacano/chavacano_parallel_sentences_nllb.jsonl
datasets/processed/jsonl/001_chavacano/chavacano_parallel_sentences_nllb.jsonl.meta.json
datasets/processed/jsonl/001_chavacano/creole_rc_chavacano_nllb.jsonl
datasets/processed/jsonl/001_chavacano/creole_rc_chavacano_nllb.jsonl.meta.json
datasets/processed/jsonl/001_chavacano/pipeline_report.jsonl
datasets/processed/jsonl/001_chavacano/pipeline_report.jsonl.meta.json
datasets/processed/jsonl/001_chavacano/tatoeba_parallel_nllb.jsonl
datasets/processed/jsonl/001_chavacano/tatoeba_parallel_nllb.jsonl.meta.json
datasets/processed/jsonl/jsonl_conversion_report.json
datasets/processed/jsonl/pillars/monolingual/chavacano_monolingual_corpus_nmt.jsonl
datasets/processed/jsonl/pillars/monolingual/chavacano_monolingual_corpus_nmt.jsonl.meta.json
datasets/processed/jsonl/pillars/parallel/master_parallel_corpus_nmt.jsonl
datasets/processed/jsonl/pillars/parallel/master_parallel_corpus_nmt.jsonl.meta.json
datasets/processed/pillars/monolingual/chavacano_monolingual_corpus_nmt.json
datasets/processed/pillars/parallel/master_parallel_corpus_nmt.json
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
datasets/scripts/README_3_PILLAR_ARCHITECTURE.md
datasets/scripts/_path_utils.py
datasets/scripts/archive_legacy_data.py
datasets/scripts/json_to_jsonl_converter.py
datasets/scripts/json_to_jsonl_stream.py
datasets/scripts/pillar1_merge_parallel_corpus.py
datasets/scripts/pillar2_structure_monolingual.py
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
frontend/src/App.css
frontend/src/App.jsx
frontend/src/assets/react.svg
frontend/src/components/CulturalTermPopup.jsx
frontend/src/components/ErrorBoundary.jsx
frontend/src/components/LanguageSelector.jsx
frontend/src/components/feedback/ToastViewport.jsx
frontend/src/components/icons/NavIcons.jsx
frontend/src/components/icons/VintaIcon.jsx
frontend/src/components/icons/index.js
frontend/src/components/layout/BottomNav.jsx
frontend/src/components/layout/GlobalHeader.jsx
frontend/src/components/layout/Header.jsx
frontend/src/components/layout/SidebarNav.jsx
frontend/src/components/screens/ActivityLogsScreen.jsx
frontend/src/components/screens/DatabaseAdminScreen.jsx
frontend/src/components/screens/GapAnalysisTerminal.jsx
frontend/src/components/screens/SettingsScreen.jsx
frontend/src/components/screens/SystemEvaluationScreen.jsx
frontend/src/components/screens/TranslateScreen.jsx
frontend/src/components/screens/WikiVozScreen.jsx
frontend/src/data/wikiVozData.js
frontend/src/index.css
frontend/src/lib/apiAuth.js
frontend/src/lib/apiRuntime.js
frontend/src/lib/settings.js
frontend/src/lib/ttsClient.js
frontend/src/main.jsx
frontend/src/temp.md
frontend/vite.config.js
ml_models/.gitkeep
ml_models/README.md
ml_models/download_model.py
ml_models/evaluate_metrics.py
ml_models/evaluate_spanish_baseline.py
ml_models/evaluation_results.json
ml_models/lora_adapters/README.md
ml_models/spanish_baseline_input.json
ml_models/spanish_baseline_metrics.json
ml_models/train_lora.py
ml_models/training_preflight.py
ml_models/training_preflight_report.json
ml_models/validate_model.py
notebooks/LOCAL_VSCODE_TUNNEL_CONNECTION_GUIDE.md
notebooks/PHASE_A_CLOUD_TRAINING_RUNBOOK.md
notebooks/README.md
notebooks/colab_vscode_tunnel_setup.ipynb
notebooks/lora_training.ipynb
notebooks/model_validation.ipynb
notebooks/sample.ipynb
notebooks/scripts/__init__.py
notebooks/scripts/_path_utils.py
notebooks/scripts/colab_drive_sync.py
notebooks/scripts/colab_lora_training_pipeline.py
notebooks/scripts/colab_vscode_tunnel_setup.md
notebooks/scripts/deep_clean_wiki.py
notebooks/scripts/extract_chavacano_pdf_REFINED.py
notebooks/scripts/harvest_creole_rc_REFINED.py
notebooks/scripts/process_chavacano_csv_REFINED.py
notebooks/scripts/process_tatoeba_REFINED.py
notebooks/scripts/process_wiki_dump.py
notebooks/scripts/requirements_colab.txt
notebooks/scripts/run_colab_phase_a_training.sh
notebooks/scripts/run_nllb_pipeline.py
package-lock.json
package.json
puente_high_level_architecture.mmd
run_project.bat
run_project.ps1
run_project.sh
```

---

## 9) Conclusion

This repository is fully synchronized to `origin/main` and structurally complete for backend/frontend operation and documentation-driven workflows.

Current system status is operational for shell/API/observer/telemetry/UI, with one intentional runtime blocker for translation workloads on this machine:

- missing local NLLB base model directory

No download actions were performed in this pass. This update focused on comprehensive scan and documentation/requirements alignment only.
