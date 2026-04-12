# Backend Setup

This backend is a Django + DRF API with these runtime layers:

- Core API endpoints for translation, verification, telemetry, health, Wiki-Voz, and TTS
- SQLite persistence for `CulturalTerm` and `TranslationLog`
- Local NLLB translation runtime with optional LoRA adapters

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Python | 3.12.x recommended | Matches workspace `.venv` |
| pip | Yes | For `requirements.txt` |
| SQLite | Built-in | Default DB (`backend/db.sqlite3`) |
| Node.js | No | Frontend only |
| Internet access | Optional | Needed only for `edge-tts` synthesis |

## Python packages in `requirements.txt`

### Core API runtime

| Package | Purpose |
|---|---|
| `django` | Web framework |
| `djangorestframework` | API views/serializers/testing helpers |
| `django-cors-headers` | LAN-safe CORS support |
| `python-dotenv` | Loads `backend/.env` |

### Local translation runtime

| Package | Purpose |
|---|---|
| `torch` | Tensor runtime for NLLB |
| `transformers` | Model/tokenizer loading |
| `huggingface_hub` | Model download/helper APIs |
| `sentencepiece` | Tokenizer backend |
| `accelerate` | Loading/device helpers |
| `peft` | LoRA adapter loading/switching |
| `bitsandbytes` | Optional 8-bit quantization |
| `protobuf` | Transformer serialization support |

### Optional runtime add-ons

| Package | Purpose | Notes |
|---|---|---|
| `edge-tts` | `/api/tts/` MP3 synthesis | Requires outbound internet |
| `psutil` | RAM telemetry metrics | `/api/telemetry/` |
| `GPUtil` | GPU telemetry fallback | Used when torch path unavailable |
| `sacrebleu` | Eval utilities | Used by ML scripts |
| `pandas` | Data script support | Used in pipeline tooling |
| `pdfplumber` | PDF extraction support | Used in notebook/data scripts |
| `ijson` | Streaming JSON parser | Used for JSONL conversion tooling |

## Environment variables

Copy `backend/.env.example` to `backend/.env` and set at least:

| Variable | Required | Purpose |
|---|---:|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | Dev/production behavior |
| `ALLOWED_HOSTS` | Recommended | Host whitelist |
| `ML_MODEL_PATH` | Recommended | Local NLLB model directory |
| `STRICT_OFFLINE_MODE` | Recommended | Disables internet-dependent services |
| `PUENTE_API_KEY` | Optional | Enables `X-API-Key` checks on write endpoints |
| `DRF_THROTTLE_ANON_RATE` | Optional | DRF anonymous throttle rate |
| `EDGE_TTS_*` | Optional | Voice/rate/volume/pitch overrides |

## Runtime endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/translate/` | `POST` | Main translation endpoint with TM cache + Wiki-Voz interception |
| `/api/btvl/` | `POST` | Back-translation verification loop |
| `/api/tts/` | `POST` | MP3 synthesis via `edge-tts` |
| `/api/wiki/` | `GET` | Cultural term search/list |
| `/api/logs/` | `GET` | Observer activity log feed |
| `/api/telemetry/` | `GET` | RAM + GPU telemetry |
| `/api/health/` | `GET` | Backend/model/TTS/API-key status |
| `/` | `GET` | API root index |

## Local run

```bash
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Windows PowerShell (workspace layout):

```powershell
cd backend
& "../.venv/Scripts/python.exe" manage.py migrate
& "../.venv/Scripts/python.exe" manage.py runserver 0.0.0.0:8000
```

## Notes

- Translation/BTVL require local model files in `ML_MODEL_PATH`.
- If model files are missing, `/api/translate/` and `/api/btvl/` return `503` with `offline-model-missing`.
- Edge-TTS can still be available while translation is blocked by missing local model.
- `ingest_lexicon` populates `CulturalTerm` from lexicon JSON and should be run after dataset prep when Wiki-Voz DB is empty.
