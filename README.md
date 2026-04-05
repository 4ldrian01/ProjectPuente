# PUENTE

**Preserving Understanding through Enhanced Neural Translation Engines**

> Offline-first neural machine translation for Philippine heritage languages, deployed on a campus LAN with local NLLB translation and optional Edge TTS.

| | |
|---|---|
| **Languages** | English, Spanish (control baseline), Tagalog, Chavacano de Zamboanga, Hiligaynon, Cebuano/Bisaya |
| **ML Model** | NLLB-200-distilled-600M (INT8 quantized) + LoRA adapters |
| **Stack** | Django 5 + DRF, React 19 + Vite 7, SQLite, PyTorch 2, edge-tts |
| **Deployment** | LAN-only edge device (8 GB RAM, RTX 3050 Ti 4 GB VRAM) |

---

## Quick Start

### Fresh-machine prerequisites

Install these once before running the project:

- **Python 3.11 or 3.12** with `venv`
- **Node.js 20+** with `npm`
- **SQLite** (built into Python; no separate DB server needed)
- **Git** for cloning the repository
- **Optional but recommended:** NVIDIA CUDA-capable setup if you want faster local NLLB inference

What the install steps below will pull in for you:

- `backend/requirements.txt` installs Django, DRF, CORS, PyTorch + Transformers, and `edge-tts`
- `frontend/package.json` installs React, Vite, axios, PWA tooling, and linting packages
- `notebooks/README.md` lists the extra notebook-only packages such as JupyterLab, pandas, datasets, sacrebleu, and PDF/data-cleaning helpers

```bash
# 1. Clone and set up Python environment
cd ProjectPuente
python -m venv .venv && source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\Activate.ps1                         # Windows PowerShell

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt
cp .env.example .env   # Edit .env with SECRET_KEY and deployment/security options
# Optional: keep STRICT_OFFLINE_MODE=True in backend/.env for Chapter 1-3 offline simulation
# Optional: set PUENTE_API_KEY in backend/.env to protect write endpoints

# 3. Database setup (SQLite file is created automatically)
python manage.py migrate
python manage.py createsuperuser

# 4. Download the local NLLB-200 model (~2.4 GB one-time download)
cd ../ml_models
python download_model.py

# 4.1 Run architecture/training preflight (read-only, no installs)
python training_preflight.py

# 5. Install frontend dependencies
cd ../frontend
npm install
# Optional: cp .env.example .env and set VITE_PUENTE_API_KEY to match backend PUENTE_API_KEY

# 6. Launch both servers
cd ..
./run_project.sh       # Linux/macOS
# run_project.bat      # Windows

# 7. Optional in VS Code
#    Run: Tasks: Run Task → Puente: Start full stack
```

**Backend:** `http://0.0.0.0:8000` | **Frontend:** `http://0.0.0.0:5173` | **Admin:** `http://localhost:8000/admin/`

### Zorin Linux Commands

```bash
cd ~/Desktop/Machine\ Learning/ProjectPuente
chmod +x run_project.sh
./run_project.sh
```

### Installation notes by area

| Area | Installed from | Includes |
|---|---|---|
| Backend/API | `backend/requirements.txt` | Django, DRF, CORS, dotenv |
| Local ML runtime | `backend/requirements.txt` | PyTorch, Transformers, SentencePiece, PEFT, Accelerate, bitsandbytes, protobuf |
| Optional online services | `backend/requirements.txt` | Speech via `edge-tts` |
| Frontend | `frontend/package.json` | React, Vite, axios, Tailwind, PWA tooling, ESLint |
| Notebook extras | see `notebooks/README.md` | JupyterLab, pandas, datasets, evaluate, sacrebleu, pdfplumber, Beautiful Soup |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     LAN CLIENT (Browser PWA)                             │
│  React 19.2 + Vite 7.3 + Tailwind 4.1                                  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ TranslateScreen (250-char limit, 800ms debounce, formal/street)   │  │
│  │ WikiVozScreen (API-backed → GET /api/wiki/)                       │  │
│  │ SettingsScreen (localStorage-persisted preferences)               │  │
│  │ PWA: vite-plugin-pwa + Workbox + manifest.json                    │  │
│  └────────────────────────┬───────────────────────────────────────────┘  │
│                           │  axios HTTP (LAN-aware: window.location)     │
└───────────────────────────┼──────────────────────────────────────────────┘
                            │
                ════════════╪═══════════════
                LAN: http://<host>:8000/api/
                ════════════╪═══════════════
                            │
┌───────────────────────────┼──────────────────────────────────────────────┐
│               DJANGO DRF BACKEND (0.0.0.0:8000)                         │
│  ┌────────────────────────┴───────────────────────────────────────────┐  │
│  │  Routing Agent — urls.py → views.py                               │  │
│  │  POST /api/translate/  →  TranslateView (TM cache → NLLB fallback) │  │
│  │  POST /api/btvl/       →  BackTranslationVerifyView               │  │
│  │  GET  /api/wiki/?q=    →  WikiVozView (SQLite CulturalTerm)       │  │
│  │  GET  /api/telemetry/  →  TelemetryView (RAM/VRAM metrics)        │  │
│  │  GET  /api/health/     →  HealthCheckView (NLLB + LoRA status)    │  │
│  └──────────┬─────────────────────────────────┬──────────────────────┘  │
│             │                                 │                          │
│  ┌──────────▼──────────────┐  ┌───────────────▼──────────────────────┐  │
│  │  Interceptor Agent      │  │  Neural Agent (apps.py Singleton)    │  │
│  │  Greedy phrase scan     │  │  NLLB-200-distilled-600M (8-bit)    │  │
│  │  (length-desc n-grams)  │  │  + LoRA formal/street adapters       │  │
│  │  → Wiki-Voz injection   │  │  + English pivot for non-EN pairs    │  │
│  └─────────────────────────┘  │  Local-only translation runtime      │  │
│                               └──────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Observer Agent — TranslationLog model → SQLite                   │  │
│  │  latency_ms, tokens_in/out, pivot_used, status, wiki_voz_term    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Dependency Guides

To keep installation sane, each layer now has its own dependency guide:

| Area | Guide |
|---|---|
| Full project overview | `README.md` |
| Django backend + API + database | `backend/README.md` |
| React frontend + build tooling | `frontend/README.md` |
| NLLB model + LoRA scripts | `ml_models/README.md` |
| Jupyter notebooks + data prep extras | `notebooks/README.md` |

### Quick dependency summary

| Area | Main dependencies |
|---|---|
| Backend/API | `django`, `djangorestframework`, `django-cors-headers`, `python-dotenv` |
| Local translation runtime | `torch`, `transformers`, `sentencepiece`, `accelerate`, `peft`, `bitsandbytes`, `protobuf` |
| Optional online add-ons | `edge-tts` |
| Frontend runtime | `react`, `react-dom`, `axios` |
| Frontend tooling | `vite`, `vite-plugin-pwa`, `tailwindcss`, `eslint` and related plugins |
| Notebook extras | `jupyterlab`, `ipykernel`, `pandas`, `datasets`, `evaluate`, `sacrebleu`, `pdfplumber`, `beautifulsoup4`, `clean-text[gpl]`, `wandb` |

---

## Project Structure

```
ProjectPuente/
├── README.md                          # This file
├── TRAINING_PREFLIGHT_CHECKLIST.md    # Training readiness checklist and workflow
├── .vscode/tasks.json                 # Searchable VS Code launcher tasks
├── agents.md                          # 5-Agent system documentation
├── package.json                       # Root workspace
├── run_project.bat                    # Windows launcher (LAN-bound)
├── run_project.ps1                    # Windows PowerShell launcher + task entry point
├── run_project.sh                     # Linux/macOS launcher (LAN-bound)
│
├── backend/                           # Django DRF REST API
│   ├── manage.py
│   ├── README.md                      # Backend/API/database dependency guide
│   ├── requirements.txt
│   ├── .env.example                   # Template — copy to .env
│   ├── backend/
│   │   ├── settings.py                # DB, CORS, DRF, env config
│   │   ├── urls.py                    # Route registration
│   │   └── wsgi.py / asgi.py
│   ├── core_api/
│   │   ├── apps.py                    # Singleton NLLB-200 + LoRA loader
│   │   ├── languages.py               # Canonical language scope + FLORES map
│   │   ├── models.py                  # CulturalTerm + TranslationLog
│   │   ├── views.py                   # Translate (TM cache), Wiki-Voz, health, and TTS views
│   │   ├── serializers.py             # Request validation (max 250 chars)
│   │   ├── admin.py                   # Django admin panels
│   │   ├── tests.py                   # 46 automated backend tests
│   │   └── migrations/
│   └── scripts/                       # Admin helper scripts
│
├── frontend/                          # React 19 PWA
│   ├── index.html                     # Entry point (system fonts, no CDN)
│   ├── package.json
│   ├── README.md                      # Frontend dependency guide
│   ├── vite.config.js                 # PWA + Workbox caching
│   ├── public/manifest.json
│   └── src/
│       ├── App.jsx                    # Root: API URL, health state, navigation
│       ├── lib/ttsClient.js           # Browser client for backend edge-tts
│       ├── main.jsx                   # StrictMode + ErrorBoundary
│       ├── components/
│       │   ├── ErrorBoundary.jsx      # Crash recovery UI
│       │   ├── LanguageSelector.jsx   # Tab + dropdown language picker
│       │   ├── CulturalTermPopup.jsx  # Wiki-Voz popup for highlighted terms
│       │   ├── icons/                 # SVG icon components
│       │   ├── layout/                # Header + BottomNav
│       │   └── screens/               # TranslateScreen, WikiVozScreen, SettingsScreen
│       └── data/wikiVozData.js        # Offline seed data (50 starter/template cards)
│
├── ml_models/                         # Model weights (download required)
│   ├── README.md                      # ML/runtime dependency guide
│   ├── download_model.py              # One-time HuggingFace download
│   ├── train_lora.py                  # LoRA fine-tuning script
│   ├── training_preflight.py          # Cross-layer training readiness verifier
│   └── validate_model.py              # Inference smoke tests
│
├── datasets/                          # Training corpora (not used at runtime)
│   ├── processed/                     # NLLB-ready JSON datasets
│   └── raw/                           # Source corpora
│
└── notebooks/                         # Jupyter notebooks + data scripts
    ├── README.md                      # Notebook dependency guide
    ├── lora_training.ipynb
    ├── model_validation.ipynb
    ├── sample.ipynb
    └── scripts/
        ├── _path_utils.py             # Canonical datasets path resolver
        ├── extract_chavacano_pdf_REFINED.py
        ├── process_chavacano_csv_REFINED.py
        ├── process_tatoeba_REFINED.py
        ├── harvest_creole_rc_REFINED.py
        └── run_nllb_pipeline.py
```


---

## Technology Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| React | 19.2.0 | UI framework (JSX components, hooks-based state) |
| Vite | 7.3.1 | Dev server + production bundler |
| Tailwind CSS | 4.1.18 | Utility-first CSS framework |
| axios | 1.7.9 | HTTP client for API calls |
| vite-plugin-pwa | 1.2.0 | Service worker generation + Workbox caching |

### Backend

| Technology | Version | Purpose |
|---|---|---|
| Django | ≥5.0, <7.0 | Web framework |
| Django REST Framework | ≥3.15.0 | REST API serialization + views |
| django-cors-headers | ≥4.7.0 | LAN CORS support |
| python-dotenv | ≥1.0.0 | Environment variable loading from `backend/.env` |
| SQLite | Built-in | Primary database (CulturalTerm + TranslationLog) |

### ML / Neural Agent

| Technology | Version | Purpose |
|---|---|---|
| PyTorch | ≥2.2.0 | Tensor operations + model inference |
| Transformers | ≥4.44.0 | NLLB-200 model loading + tokenization |
| SentencePiece | ≥0.2.0 | NLLB tokenizer backend |
| accelerate | ≥0.30.0 | Device mapping (CPU/CUDA) |
| PEFT | ≥0.11.0 | LoRA adapter loading + switching |
| bitsandbytes | ≥0.43.0 | 8-bit quantization (reduces 2.4GB → ~1.2GB) |
| edge-tts | ≥7.2.0, <8.0 | Backend speech synthesis for the TTS buttons |

### Target Hardware

| Component | Specification |
|---|---|
| CPU | Ryzen 5 / Intel i5 (AVX2 required for PyTorch) |
| RAM | 8 GB minimum |
| OS | Windows 11 + WSL2 |
| Network | Campus LAN; internet optional for Edge TTS |
| Storage | ~3 GB for model weights + adapters |

---

## Language Scope

| App Code | NLLB FLORES Code | Language | Notes |
|---|---|---|---|
| `en` | `eng_Latn` | English | Pivot language for non-EN pairs |
| `es` | `spa_Latn` | Spanish | Control-variable baseline language |
| `tl` | `tgl_Latn` | Tagalog (Filipino) | National language |
| `cbk` | `cbk_Latn` | Chavacano de Zamboanga | Primary target — Spanish Creole |
| `hil` | `hil_Latn` | Hiligaynon | Native NLLB-200 support |
| `ceb` | `ceb_Latn` | Cebuano / Bisaya | Major Visayan language |
| `auto` | `eng_Latn` | Auto-Detect | Falls back to English |

**English Pivot Routing:** For language pairs where neither source nor target is English (e.g., Cebuano → Chavacano), the system performs a **two-hop translation** through English:
```
ceb_Latn → eng_Latn → cbk_Latn
```
This is implemented in `nllb_translate()` in `views.py`.

---

## Translation Engine

### Local-Engine Design

```
TranslateView.post(request)
│
├── Translation Memory lookup (SQLite TranslationLog)
│   ├── Normalize input (strip + lowercase)
│   ├── Match latest successful source/target pair
│   └── Cache hit → return saved output (`is_cached: true`)
│
├── CoreApiConfig.model_loaded == True?
│   │
│   ├── YES → PRIMARY (cache miss): nllb_translate()
│   │   ├── Select LoRA adapter based on mode (formal/street)
│   │   ├── Map source/target to FLORES codes
│   │   ├── If neither is eng_Latn → two-hop pivot
│   │   ├── _infer_once() with torch.no_grad()
│   │   ├── num_beams=4, max_new_tokens=128
│   │   └── Return (text, latency_ms, tokens_in, tokens_out, pivot_used, is_cached=false)
│   │
│   └── NO → Return 503 (local model missing)
│
└── Log everything to TranslationLog (SQLite)
```

### Singleton Model Loading

The NLLB-200 model is loaded **exactly once** during Django's startup via `CoreApiConfig.ready()`:

1. Check `RUN_MAIN == 'true'` (avoid double-load from auto-reloader)
2. Load tokenizer from `ml_models/nllb-200-distilled-600M/`
3. Load base model with 8-bit quantization (if `bitsandbytes` available)
4. Iterate `ml_models/lora-cbk-{formal,street}/` → load LoRA adapters via PEFT `load_adapter()`
5. Set `CoreApiConfig.model_loaded = True`

If `ml_models/` is empty, translation requests return a clear 503 until the local model is installed.

### Language Contract Source of Truth

Backend language scope and FLORES mapping are centralized in `backend/core_api/languages.py`.

- `SUPPORTED_LANGUAGES` is reused by views and health payloads
- `SOURCE_LANGUAGE_CODES` / `TARGET_LANGUAGE_CODES` are reused by serializers
- `LANGUAGE_CHOICES` / `TARGET_LANGUAGE_CHOICES` are reused by models

This prevents drift between validation, persistence, and API contract declarations.

### LoRA Adapter Strategy

| Mode | Adapter Path | Purpose |
|---|---|---|
| `formal` | `ml_models/lora-cbk-formal/` | High variety — formal, respectful Chavacano |
| `street` | `ml_models/lora-cbk-street/` | Low variety — casual colloquial Chavacano |

The sociolinguistic toggle in `TranslateScreen.jsx` sets `payload.mode` which selects the corresponding LoRA adapter (or falls back to base model if adapter is missing).

---

## Database Schema

### CulturalTerm (Wiki-Voz)

```sql
CREATE TABLE core_api_culturalterm (
    id          BIGSERIAL PRIMARY KEY,
    term        VARCHAR(200) UNIQUE NOT NULL,    -- B-tree indexed
    definition  TEXT NOT NULL,
    image_url   VARCHAR(500) DEFAULT '',
    language    VARCHAR(50) DEFAULT '',           -- e.g. 'Chavacano', 'Hiligaynon'
    category    VARCHAR(50) DEFAULT '',           -- e.g. 'food', 'culture'
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);
```

### TranslationLog (ISO 25010 Observer)

```sql
CREATE TABLE core_api_translationlog (
    id                  BIGSERIAL PRIMARY KEY,
    source_lang         VARCHAR(10) NOT NULL,
    target_lang         VARCHAR(10) NOT NULL,
    mode                VARCHAR(10) NOT NULL,        -- 'formal' | 'street'
    input_text          TEXT NOT NULL,
    input_chars         INTEGER NOT NULL,
    input_tokens        INTEGER DEFAULT 0,
    output_text         TEXT DEFAULT '',
    output_tokens       INTEGER DEFAULT 0,
    model_name          VARCHAR(100) NOT NULL,
    pivot_used          BOOLEAN DEFAULT FALSE,
    latency_ms          FLOAT NOT NULL,
    status              VARCHAR(20) NOT NULL,        -- 'success' | 'error' | 'timeout'
    error_message       TEXT DEFAULT '',
    wiki_voz_triggered  BOOLEAN DEFAULT FALSE,
    wiki_voz_term       VARCHAR(200) DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL
);
-- Indexes: created_at, (source_lang, target_lang), status
```

---

## API Reference

### POST /api/translate/

**Request:**
```json
{
  "text": "Kumusta ka?",
  "source_lang": "tl",
  "target_lang": "cbk",
  "mode": "formal"
}
```

**Validation:** `text` max 250 chars, `mode` ∈ {formal, street}, langs ∈ {auto, en, es, tl, cbk, hil, ceb}

**Response (Success):**
```json
{
  "translated_text": "Como esta tu?",
  "source_lang": "tl",
  "target_lang": "cbk",
  "mode": "formal",
  "model": "nllb-200-distilled-600M+lora-cbk-formal",
  "latency_ms": 1840.5,
  "tokens_in": 12,
  "tokens_out": 8,
  "pivot_used": true,
  "is_cached": false,
  "wiki_voz": null
}
```

On Translation Memory hit, the same response includes:

```json
{
  "translated_text": "Of course",
  "model": "tm-cache",
  "is_cached": true
}
```

### POST /api/btvl/

**Request:**
```json
{
  "text": "Ta ama yo contigo",
  "source_lang": "cbk",
  "target_lang": "en"
}
```

**Response (Success):**
```json
{
  "verified_text": "I love you",
  "source_lang": "cbk",
  "target_lang": "en",
  "model": "nllb-200-distilled-600M+lora-cbk-formal",
  "latency_ms": 842.7,
  "tokens_in": 6,
  "tokens_out": 4,
  "pivot_used": false
}
```

### GET /api/wiki/?q=satti

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "term": "Satti",
      "definition": "Grilled meat skewers served with rice and spicy sauce...",
      "image_url": "...",
      "language": "Chavacano",
      "category": "food"
    }
  ]
}
```
Without `?q=`, returns all terms (used by frontend to build dynamic cultural term map).

### GET /api/health/

**Response:**
```json
{
  "status": "ok",
  "engine": "nllb-200-distilled-600M",
  "nllb_loaded": true,
  "lora_adapters": ["formal", "street"],
  "api_key_required": false,
  "api_key_header": "",
  "api_key_configured": false,
  "tts_available": true,
  "tts_engine": "edge-tts",
  "supported_languages": ["auto", "en", "es", "tl", "cbk", "hil", "ceb"]
}
```

### GET /api/telemetry/

Returns live hardware usage from backend host:

```json
{
  "status": "ok",
  "timestamp_utc": "2026-04-05T10:10:33.123456+00:00",
  "ram": {
    "used_gb": 5.1,
    "total_gb": 7.8,
    "percent": 65.3
  },
  "gpu": {
    "available": true,
    "name": "NVIDIA GeForce RTX 3050 Ti Laptop GPU",
    "used_gb": 2.6,
    "total_gb": 4.0,
    "percent": 65.0
  }
}
```

### POST /api/tts/

**Request:**
```json
{
  "text": "Buenas dias",
  "lang_code": "cbk"
}
```

**Response:** raw `audio/mpeg` bytes.

Headers include:

- `X-TTS-Voice` — the Edge voice name used for synthesis

> `edge-tts` is integrated through the Django backend and no longer depends on the browser Web Speech API. It does, however, require outbound internet access to Microsoft's voice service.

---

## PWA & Offline Strategy

### Service Worker (Workbox)

| Asset Type | Strategy | Cache Name |
|---|---|---|
| Static assets (JS, CSS, HTML, fonts, SVG) | **Cache-First** | Workbox default |
| `GET /api/health/` | **Network-First** | `health-cache` |
| `GET /api/wiki/` | **Network-First** | `wiki-cache` (24h TTL, max 50 entries) |
| `POST /api/translate/` | **No browser caching** | Server-side TM cache is applied in Django before model inference |

### Offline Fonts

Google Fonts CDN links **removed** from `index.html`. The CSS cascades to system fonts: `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`.

For full offline Inter support, self-host WOFF2 files in `frontend/public/fonts/`.

### TTS caveat

The translation pipeline can run fully offline when the NLLB model is available locally. The new TTS feature is different: `edge-tts` uses Microsoft's cloud voices, so speech playback needs internet access even though the text translation path can stay local.

---

## LAN Deployment

| Setting | File | Value |
|---|---|---|
| Django bind address | `run_project.bat` | `0.0.0.0:8000` |
| Vite bind address | `run_project.bat` | `--host 0.0.0.0` |
| `ALLOWED_HOSTS` | `backend/settings.py` | Parsed from `.env` (`localhost,127.0.0.1,0.0.0.0` default) |
| `CORS_ALLOW_ALL_ORIGINS` | `backend/settings.py` | Env-driven (`DEBUG`-aware default) |
| Frontend API URL | `App.jsx` | `http://${window.location.hostname}:8000/api` |

Any LAN client can access the system at `http://<server-ip>:5173` (frontend) with API calls routed to `http://<server-ip>:8000/api`.

---

## ISO 25010 Quality Evaluation

### Performance Efficiency (via TranslationLog)

```python
# Average latency across all successful translations
TranslationLog.objects.filter(status='success').aggregate(Avg('latency_ms'))
# Target: < 3000ms per translation

# Latency by language pair
TranslationLog.objects.filter(status='success').values('source_lang', 'target_lang')
    .annotate(avg_ms=Avg('latency_ms'), count=Count('id'))
```

### Functional Suitability

```python
# Translation success rate
total = TranslationLog.objects.count()
success = TranslationLog.objects.filter(status='success').count()
rate = (success / total) * 100  # Target: > 95%

# Wiki-Voz interception rate
wiki_hits = TranslationLog.objects.filter(wiki_voz_triggered=True).count()
```

### Reliability

```python
# Error rate by type
TranslationLog.objects.filter(status='error').values('error_message').annotate(count=Count('id'))

# Pivot usage frequency
TranslationLog.objects.filter(pivot_used=True).count()
```

---

## Test Suite

Located in `core_api/tests.py` — 46 automated tests across serializer, view, health, TTS, BTVL, API-key protection, TM cache routing, and greedy phrase interception:

| Test Class | Coverage |
|---|---|
| `TranslateSerializerTests` | Valid payload, max 250 enforced, mode default/invalid, empty text |
| `SupportedLanguagesTests` | Expected language scope (includes Spanish control variable) |
| `FloresMapTests` | All lang codes mapped, hil→hil_Latn, cbk→cbk_Latn |
| `CulturalTermModelTests` | iexact match, icontains search |
| `TranslationLogTests` | Success/error log creation |
| `WikiVozViewTests` | Search results, empty-query-returns-all, no-match |
| `HealthCheckViewTests` | OK status, language list present |
| `TranslateViewValidationTests` | Missing text, unsupported lang, over 250 chars |
| `TranslationMemoryCacheTests` | Normalized cache hit bypass and miss-to-inference routing |
| `WikiVozPhraseInterceptorTests` | Longest-phrase match over overlapping cultural terms |
| `BackTranslationViewTests` | BTVL success/failure paths |
| `ApiKeyProtectionTests` | Optional X-API-Key enforcement on write endpoints |

Run: `cd backend && python manage.py test core_api`

---

## Key Files Reference

| File | Change Summary |
|---|---|
| `core_api/apps.py` | Singleton NLLB-200 loader with 8-bit quantization + LoRA |
| `core_api/languages.py` | Canonical language scope + FLORES mapping shared across models/serializers/views |
| `core_api/models.py` | TranslationLog model; CulturalTerm language kept as free text for real origin labels |
| `core_api/views.py` | TM cache + greedy phrase interceptor + NLLB local engine + telemetry + optional API-key enforcement |
| `core_api/serializers.py` | text max_length 2000→250 |
| `core_api/admin.py` | +TranslationLog admin panel |
| `core_api/tests.py` | 46 tests covering validation, TM cache, phrase interception, Wiki-Voz, health, TTS, BTVL, and auth guards |
| `backend/settings.py` | Env-driven hosts/CORS, DRF throttling, optional PUENTE_API_KEY |
| `backend/requirements.txt` | +torch, transformers, peft, bitsandbytes |
| `run_project.bat` | 0.0.0.0 binding for LAN |
| `frontend/src/App.jsx` | LAN-aware API_URL, NLLB health fields |
| `frontend/src/components/screens/TranslateScreen.jsx` | maxLength 250 |
| `frontend/src/components/screens/WikiVozScreen.jsx` | API-backed with seed fallback |
| `frontend/src/components/screens/SettingsScreen.jsx` | localStorage persistence, NLLB status |
| `frontend/index.html` | CDN fonts removed, manifest link added |
| `frontend/vite.config.js` | vite-plugin-pwa + Workbox strategies |
| `frontend/public/manifest.json` | Created — PWA manifest |
| `ml_models/training_preflight.py` | Read-only architecture/training readiness checks with JSON report output |
| `notebooks/scripts/_path_utils.py` | Canonical `datasets/` resolver with compatibility fallback |

---

See `agents.md` for detailed 5-agent system documentation.
