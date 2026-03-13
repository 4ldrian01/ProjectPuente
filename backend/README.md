# Backend Setup

This backend is a Django + DRF API with three runtime layers:

- core API endpoints for translation, health, Wiki-Voz, and TTS
- PostgreSQL for `CulturalTerm` and `TranslationLog`
- optional cloud fallbacks for Gemini and Edge TTS

## Required system software

| Dependency | Required | Notes |
|---|---:|---|
| Python | 3.12.x | Matches the configured workspace virtual environment |
| pip | Yes | Used for `requirements.txt` |
| PostgreSQL | 17 | Main database used by Django |
| Node.js | No | Frontend only |
| Internet access | Optional | Needed only for Gemini fallback and `edge-tts` speech synthesis |

## Python packages in `requirements.txt`

### Core API runtime

| Package | Purpose |
|---|---|
| `django` | Main web framework |
| `djangorestframework` | API views, serializers, testing client |
| `django-cors-headers` | LAN-friendly CORS for the Vite frontend |
| `psycopg2-binary` | PostgreSQL driver |
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

### Optional cloud/runtime add-ons

| Package | Purpose | Notes |
|---|---|---|
| `google-genai` | Gemini fallback translation | Used only when the local NLLB model is unavailable |
| `edge-tts` | Speech synthesis endpoint at `/api/tts/` | Requires outbound internet to Microsoft's TTS service |

## Environment variables

Copy `backend/.env.example` to `backend/.env` and set at least these values:

| Variable | Required | Purpose |
|---|---:|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | Development mode toggle |
| `DB_NAME` | Yes | PostgreSQL database name |
| `DB_USER` | Yes | PostgreSQL user |
| `DB_PASSWORD` | Yes | PostgreSQL password |
| `DB_HOST` | Yes | PostgreSQL host |
| `DB_PORT` | Yes | PostgreSQL port |
| `ML_MODEL_PATH` | Recommended | Local NLLB model directory |
| `GOOGLE_API_KEY` | Optional | Enables Gemini fallback |
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
| `/api/translate/` | `POST` | Main translation endpoint |
| `/api/tts/` | `POST` | MP3 speech synthesis via `edge-tts` |
| `/api/wiki/` | `GET` | Wiki-Voz search and full-list endpoint |
| `/api/health/` | `GET` | Backend, NLLB, adapter, and TTS health |

## Notes

- Translation remains offline-first when the NLLB model is present locally.
- Gemini and Edge TTS are both optional online services.
- If you want the whole stack in one environment, install backend dependencies first, then see `../ml_models/README.md` and `../notebooks/README.md` for the extra packages used outside the live API.
