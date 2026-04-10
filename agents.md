# PUENTE — Agent Architecture (Latest)

> 5-agent pipeline documentation, synchronized with the current backend/frontend implementation.

---

## Overview

PUENTE runs a **5-agent pipeline** for translation, with two supporting modules for verification and telemetry.

```text
Request Flow (Translate):

[Browser] -- POST /api/translate/ --> [Routing Agent]
                                      │
                                      ├--> [Interceptor Agent]  (greedy Wiki-Voz phrase match)
                                      │
                                      ├--> [TM Cache Check]      (TranslationLog lookup)
                                      │
                                      ├--> [Neural Agent]        (NLLB-200 + optional LoRA)
                                      │
                                      └--> [Observer Agent]      (TranslationLog write)
                                                      │
                                                      ▼
                                            [Presentation Agent]
                                         (React render + UX feedback)

Supporting endpoints:
- POST /api/btvl/      (Back-Translation Verification Loop)
- GET  /api/telemetry/ (RAM / VRAM metrics)
```

---

## Agent 1: Routing Agent

### Role

Validates requests, enforces language contract, guards write endpoints (optional API key), and controls execution path.

### Implementation

- `backend/core_api/views.py` → `TranslateView.post()`, `BackTranslationVerifyView.post()`, `TextToSpeechView.post()`
- `backend/core_api/serializers.py` → request serializers
- `backend/core_api/languages.py` → canonical language scope

### Behavior (`POST /api/translate/`)

1. Optional `X-API-Key` guard if `PUENTE_API_KEY` is configured.
2. Serializer validation (`text`, `source_lang`, `target_lang`, `mode`).
3. Interceptor lookup for cultural phrase match.
4. Translation Memory lookup (normalized text + language pair).
5. Same-language short-circuit (`passthrough`) when source and target are equivalent.
6. Local neural inference via NLLB path when needed.
7. Observer logging (`TranslationLog`) for success/error.

### Validation Rules

| Field | Constraint | Source |
|---|---|---|
| `text` | max 250 characters | `TranslateRequestSerializer` |
| `source_lang` | one of `auto,en,es,tl,cbk,hil,ceb` | `SOURCE_LANGUAGE_CODES` |
| `target_lang` | one of `en,es,tl,cbk,hil,ceb` | `TARGET_LANGUAGE_CODES` |
| `mode` | `formal` or `street` (default `formal`) | Serializer choice |

### URL Routes

| Endpoint | View | Method |
|---|---|---|
| `/` | `APIRootView` | GET |
| `/admin/` | Django Admin | — |
| `/api/translate/` | `TranslateView` | POST |
| `/api/btvl/` | `BackTranslationVerifyView` | POST |
| `/api/tts/` | `TextToSpeechView` | POST |
| `/api/wiki/` | `WikiVozView` | GET |
| `/api/telemetry/` | `telemetry_view` | GET |
| `/api/health/` | `HealthCheckView` | GET |

---

## Agent 2: Interceptor Agent (Wiki-Voz)

### Role

Finds culturally meaningful terms/phrases before translation and injects matching Wiki-Voz metadata in responses.

### Implementation

- `backend/core_api/views.py`:
  - `_normalize_text_for_phrase_scan()`
  - `_get_cultural_term_candidates()`
  - `_find_wiki_voz_phrase_match()`
- `backend/core_api/models.py` → `CulturalTerm`
- `backend/core_api/serializers.py` → `CulturalTermSerializer`

### Matching Strategy

- Uses normalized text (`NFKC`, lowercase, punctuation-folded whitespace).
- Builds candidate terms from language-scoped aliases (e.g., `cbk/chavacano/zamboanga`).
- Sorts candidates by descending normalized length.
- Returns the **longest phrase match** contained in the input.

This is more robust than old exact whole-input matching.

---

## Agent 3: Neural Agent (Translation Engine)

### Role

Executes translation using local NLLB-200 with dynamic LoRA adapter selection, direct many-to-many routing, and proximate-pivot fallback when confidence is critically low.

### Implementation

- Loader: `backend/core_api/apps.py` (`CoreApiConfig.ready()`)
- Inference: `backend/core_api/views.py` (`nllb_translate`, `_infer_once`)
- Contract source: `backend/core_api/languages.py`

### Runtime Details

- Model path defaults to `ml_models/nllb-200-distilled-600M` (override via `ML_MODEL_PATH`).
- Device strategy:
  - CUDA + bitsandbytes → INT8
  - CUDA without bitsandbytes → FP16
  - CPU → FP32
- LoRA adapters (`lora-cbk-formal`, `lora-cbk-street`) are loaded dynamically and switched via `set_adapter`.

### FLORES Mapping

| App Code | FLORES |
|---|---|
| `en` | `eng_Latn` |
| `es` | `spa_Latn` |
| `tl` | `tgl_Latn` |
| `cbk` | `cbk_Latn` |
| `ceb` | `ceb_Latn` |
| `hil` | `hil_Latn` |
| `auto` | `eng_Latn` |

### Pivot Policy

Routing is direct-first for all pairs. When direct confidence is critically low, proximate fallback may run:

- `cbk`-involved pair: pivot via `es` when usable
- local<->local pair: pivot via `tl`
- if `tl` is already source or target: secondary pivot `ceb`
- `en` is never selected as pivot for local-to-local Philippine pairs

---

## Agent 4: Observer Agent (ISO 25010 Metrics)

### Role

Logs every translate request outcome (success/error, cache hit/miss path, latency/tokens/model metadata).

### Implementation

- `backend/core_api/models.py` → `TranslationLog`
- `backend/core_api/views.py` → write points in `TranslateView`
- `backend/core_api/admin.py` → admin inspection tools

### Logged Dimensions

- Reliability: `status`, `error_message`
- Performance: `latency_ms`, token counts
- Functional suitability: `pivot_used`, `pivot_language`, `route_strategy`, `wiki_voz_triggered`, `wiki_voz_term`
- Traceability: `model_name`, language pair, mode

---

## Agent 5: Presentation Agent (React Frontend)

### Role

Renders responsive UX, sends LAN-aware API requests, and exposes verification/health/telemetry state to users.

### Implementation

- Shell: `frontend/src/App.jsx`
- Styling/motion: `frontend/src/index.css`, `frontend/src/App.css`
- Screens: `TranslateScreen.jsx`, `WikiVozScreen.jsx`, `SettingsScreen.jsx`
- Popup: `CulturalTermPopup.jsx`

### Key Frontend Behaviors

- API URL is LAN-derived: `http://${window.location.hostname}:8000/api`
- Optional API key forwarding via `VITE_PUENTE_API_KEY` (`X-API-Key` header)
- Theme persistence (`dark/light`) via localStorage + cross-tab sync
- Spring-tuned transitions for tabs/icons/indicators/screens

### Translate Screen

- Source/target language mutual exclusion
- Debounced auto-translate (800ms)
- Formal/Street toggle
- Character limit aligned to backend (250)
- Character counter shown only when typing begins
- Back-Translation Verification button (`/api/btvl/`)
- Wiki-term inline hover tooltip + clickable modal details

### Wiki-Voz Screen

- API-backed entries with offline fallback
- Search + filter panel (category and language chips)
- Progressive pagination: first 20 cards, then `View More` in +20 batches
- Masonry-style card layout with deterministic varied aspect ratios
- Local placeholder fallback for non-local/invalid images

### Settings Screen

- Default language + theme persistence
- Health status rendering (backend/model/adapters/TTS/API-key requirement)
- Live telemetry polling (`/api/telemetry/`) for RAM + GPU metrics

---

## Supporting Module A: Translation Memory (TM Cache)

Before neural inference, translate requests attempt cache retrieval from `TranslationLog`:

- Normalization: `strip + casefold` (NFKC)
- Match keys: `source_lang`, `target_lang`, normalized input
- Response includes `model: "tm-cache"` and `is_cached: true`

This reduces repeated inference cost on duplicate requests.

---

## Supporting Module B: BTVL (Back-Translation Verification Loop)

`POST /api/btvl/` translates target text to a verification language (`en` by default) for semantic checks.

- Validates payload with dedicated serializer
- Requires local model loaded
- Returns verified text + latency/token/model metadata

---

## Error Handling Matrix (Current)

| Error | Source | HTTP |
|---|---|---:|
| Missing/invalid payload | DRF serializer | 400 |
| Unsupported language code | Serializer choices | 400 |
| Missing/invalid API key (when enabled) | Header guard | 401 |
| Local NLLB model unavailable | `CoreApiConfig.model_loaded` check | 503 |
| Inference failure | `nllb_translate` exception | 500 |
| Strict-offline TTS attempt | `TextToSpeechView` gate | 503 |

---

## Known Limitations

- If local NLLB files are missing, translate and BTVL remain unavailable (503).
- `edge-tts` requires internet and is disabled when strict offline mode is enabled.
- API-key protection is optional; frontend and backend keys must match when enabled.

---

See `README.md` and `PROJECT_PUENTE_COMPREHENSIVE_SCAN.md` for broader architecture and repository-level inventory details.
