# Backend Setup

This backend is a Django + DRF API with three runtime layers:

- core API endpoints for translation, verification, telemetry, health, Wiki-Voz, and TTS
- SQLite for `CulturalTerm` and `TranslationLog`
- local NLLB translation with optional Edge TTS

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Python | 3.12.x | Matches the configured workspace virtual environment |
| pip | Yes | Used for `requirements.txt` |
| SQLite | Built-in | Main database used by Django (`backend/db.sqlite3`) |
| Node.js | No | Frontend only |
| Internet access | Optional | Needed only for `edge-tts` speech synthesis |

## Python packages in `requirements.txt`

### Core API runtime

| Package | Purpose |
|---|---|
| `django` | Main web framework |
| `djangorestframework` | API views, serializers, throttling, testing client |
| `django-cors-headers` | LAN-friendly CORS for the Vite frontend |
| `python-dotenv` | Loads `backend/.env` |

### Local translation + ML runtime

| Package | Purpose |
|---|---|
| `torch` | Tensor runtime for NLLB-200 |
| `transformers` | NLLB tokenizer and model loading |
| `sentencepiece` | NLLB tokenizer backend |
| `accelerate` | Device and loading helpers |
| `peft` | LoRA adapter loading/switching |
| `bitsandbytes` | Optional 8-bit quantization |
| `protobuf` | Transformer/model serialization support |

### Optional runtime add-ons

| Package | Purpose | Notes |
|---|---|---|
| `edge-tts` | Speech synthesis endpoint at `/api/tts/` | Requires outbound internet to Microsoft's TTS service |
| `psutil` | RAM telemetry endpoint support | Enables `/api/telemetry/` hardware metrics |
| `sacrebleu` | Evaluation metrics helper | Used by ML evaluation scripts |

## Environment variables

Copy `backend/.env.example` to `backend/.env` and set at least these values:

| Variable | Required | Purpose |
|---|---:|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | Development mode toggle |
| `ML_MODEL_PATH` | Recommended | Local NLLB model directory |
| `STRICT_OFFLINE_MODE` | Recommended | Disables internet-dependent services when `True` |
| `PUENTE_API_KEY` | Optional | If set, write endpoints require `X-API-Key` header |
| `DRF_THROTTLE_ANON_RATE` | Optional | Per-IP DRF throttle rate (default `240/min`) |
| `EDGE_TTS_VOICE_EN` | Optional | Override English voice |
| `EDGE_TTS_VOICE_TL` | Optional | Override Tagalog voice |
| `EDGE_TTS_VOICE_CBK` | Optional | Override Chavacano voice |
| `EDGE_TTS_VOICE_HIL` | Optional | Override Hiligaynon voice |
| `EDGE_TTS_VOICE_CEB` | Optional | Override Cebuano/Bisaya voice |
| `EDGE_TTS_RATE` | Optional | Example: `+0%` |
| `EDGE_TTS_VOLUME` | Optional | Example: `+0%` |
| `EDGE_TTS_PITCH` | Optional | Example: `+0Hz` |

## Runtime endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/translate/` | `POST` | Main translation endpoint with TM cache (`is_cached`) and greedy Wiki-Voz phrase interception (API key protected when enabled) |
| `/api/btvl/` | `POST` | Back-translation verification loop (API key protected when enabled) |
| `/api/tts/` | `POST` | MP3 speech synthesis via `edge-tts` (API key protected when enabled) |
| `/api/wiki/` | `GET` | Wiki-Voz search and full-list endpoint |
| `/api/telemetry/` | `GET` | Live RAM + GPU telemetry for deployment monitoring |
| `/api/health/` | `GET` | Backend, NLLB, adapter, TTS, and API-key requirement status |

## Notes

- Translation remains offline-first when the NLLB model is present locally.
- Translation endpoint now checks SQLite TranslationLog as Translation Memory before GPU inference.
- Wiki-Voz interception in translation uses longest-phrase matching (not single exact-word only).
- Edge TTS is an optional online service.
- API-key protection is optional and intended for LAN hardening.
- If you want the whole stack in one environment, install backend dependencies first, then see `../ml_models/README.md` and `../notebooks/README.md` for the extra packages used outside the live API.
