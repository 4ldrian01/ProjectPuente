# PUENTE — Agent Architecture

> 5-agent pipeline documentation for the PUENTE translation system.

---

## Overview

PUENTE uses a **5-agent pipeline** where each agent owns a single responsibility. Three agents run in the Django backend, one spans the React frontend, and one is a cross-cutting observer.

```
Request Flow:

  [Browser]  ──POST /api/translate/──▶  [Routing Agent]
                                            │
      ┌─────────────────────────────────────┤
      │                                     │
      ▼                                     ▼
[Interceptor Agent]                   [Neural Agent]
  CulturalTerm.filter()               NLLB-200 + LoRA
    SQLite lookup                        local-only translation
      │                                     │
      └──────────────┬──────────────────────┘
                     │
                     ▼
             [Observer Agent]
              TranslationLog.save()
                     │
                     ▼
             [Presentation Agent]
              React UI rendering
```

---

## 2. Agent 1: Routing Agent

### Role
Request validation, language enforcement, and flow control.

### Implementation
- **File:** [core_api/views.py](backend/core_api/views.py) — `TranslateView.post()`
- **Serializer:** [core_api/serializers.py](backend/core_api/serializers.py) — `TranslateRequestSerializer`

### Behavior

```python
# Step 1: Validate input via DRF serializer
serializer = TranslateRequestSerializer(data=request.data)
if not serializer.is_valid():
    return Response({'errors': serializer.errors}, status=400)

# Step 2: Enforce strict 5-language scope
if source_lang not in SUPPORTED_LANGUAGES:
    return Response({'errors': {'source_lang': 'Unsupported'}}, status=400)
if target_lang not in SUPPORTED_LANGUAGES:
    return Response({'errors': {'target_lang': 'Unsupported'}}, status=400)

# Step 3: Dispatch to Interceptor → Neural → Observer
```

### Validation Rules

| Field | Constraint | Implementation |
|---|---|---|
| `text` | max 250 characters | `CharField(max_length=250)` in serializer |
| `source_lang` | ∈ {auto, en, tl, cbk, hil, ceb} | `SUPPORTED_LANGUAGES` dict check |
| `target_lang` | ∈ {en, tl, cbk, hil, ceb} | Same dict check (excludes auto) |
| `mode` | ∈ {formal, street}, default formal | `ChoiceField(choices=[...], default='formal')` |

### URL Routes (urls.py)

| Endpoint | View | Method |
|---|---|---|
| `/` | `APIRootView` | GET |
| `/admin/` | Django Admin | — |
| `/api/translate/` | `TranslateView` | POST |
| `/api/wiki/` | `WikiVozView` | GET |
| `/api/health/` | `HealthCheckView` | GET |

---

## Agent 2: Interceptor Agent (Wiki-Voz)

### Role
Cultural term detection and context injection before translation.

### Implementation
- **File:** [core_api/views.py](backend/core_api/views.py) — lines within `TranslateView.post()`
- **Model:** [core_api/models.py](backend/core_api/models.py) — `CulturalTerm`
- **API:** [core_api/views.py](backend/core_api/views.py) — `WikiVozView`

### Behavior

```python
# Exact-match lookup on full input text (case-insensitive)
wiki_match = CulturalTerm.objects.filter(term__iexact=text.strip()).first()

if wiki_match:
    wiki_data = CulturalTermSerializer(wiki_match).data
    # Attach cultural context metadata to the API response payload
```

### Data Flow

1. **During Translation:** `term__iexact` lookup → if matched, wiki_data attached to response
2. **WikiVozScreen (frontend):** `GET /api/wiki/` → returns all terms or filtered by `?q=<term>`
3. **Frontend fallback:** If API unreachable, WikiVozScreen uses hardcoded seed data from `wikiVozData.js`

### Database Query Performance

| Query Type | SQL Equivalent | Index |
|---|---|---|
| Exact match | `WHERE LOWER(term) = LOWER(?)` | B-tree on `term` (UNIQUE) |
| Search | `WHERE term ILIKE '%?%'` | Sequential scan (≤100 rows) |
| All terms | `SELECT * LIMIT 100` | Sequential scan |

### CulturalTerm Fields

| Field | Type | Purpose |
|---|---|---|
| `term` | VARCHAR(200), UNIQUE | The cultural term (e.g., "Satti") |
| `definition` | TEXT | Full cultural definition and context |
| `image_url` | VARCHAR(500) | Optional illustration URL |
| `language` | VARCHAR(50) | Language of origin (Chavacano, Hiligaynon, etc.) |
| `category` | VARCHAR(50) | Category (food, culture, expression, etc.) |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

---

## Agent 3: Neural Agent (Translation Engine)

### Role
Execute translation using the locally loaded NLLB-200 model with LoRA adapters.

### Implementation
- **Model Loader:** [core_api/apps.py](backend/core_api/apps.py) — `CoreApiConfig.ready()`
- **Inference:** [core_api/views.py](backend/core_api/views.py) — `nllb_translate()`, `_infer_once()`

### Primary Engine: NLLB-200 + LoRA

#### Singleton Loading (apps.py)

```python
class CoreApiConfig(AppConfig):
    nllb_tokenizer = None       # Shared tokenizer instance
    nllb_model = None           # 600M param base model (8-bit quantized)
    lora_adapters = {}          # {'formal': merged_model, 'street': merged_model}
    model_loaded = False

    def ready(self):
        # 1. Guard against double-load (Django auto-reloader)
        if os.environ.get('RUN_MAIN') != 'true':
            return
        # 2. Load tokenizer from ml_models/nllb-200-distilled-600M/
        # 3. Load base model with load_in_8bit=True (bitsandbytes)
        # 4. Merge LoRA adapters via PeftModel.merge_and_unload()
        # 5. Set model_loaded = True
```

#### Inference Function

```python
def _infer_once(model, tokenizer, text, src_flores, tgt_flores):
    tokenizer.src_lang = src_flores
    inputs = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)
    with torch.no_grad():
        translated_ids = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_flores),
            max_new_tokens=128,
            num_beams=4,
        )
    return tokenizer.batch_decode(translated_ids, skip_special_tokens=True)[0]
```

#### English Pivot Routing

```python
def nllb_translate(text, src_code, tgt_code, mode='formal'):
    src_flores = FLORES_MAP[src_code]   # e.g., 'ceb_Latn'
    tgt_flores = FLORES_MAP[tgt_code]   # e.g., 'cbk_Latn'

    if src_flores != PIVOT_LANG and tgt_flores != PIVOT_LANG:
        # Two-hop: src → eng_Latn → tgt
        mid_text = _infer_once(model, tokenizer, text, src_flores, 'eng_Latn')
        result = _infer_once(model, tokenizer, mid_text, 'eng_Latn', tgt_flores)
        pivot_used = True
    else:
        result = _infer_once(model, tokenizer, text, src_flores, tgt_flores)
        pivot_used = False
```

#### FLORES Language Code Mapping

| App Code | FLORES Code | Direct NLLB Support |
|---|---|---|
| `en` | `eng_Latn` | Yes (pivot language) |
| `tl` | `tgl_Latn` | Yes |
| `cbk` | `cbk_Latn` | Yes |
| `ceb` | `ceb_Latn` | Yes |
| `hil` | `hil_Latn` | Yes — native NLLB-200 support |
| `auto` | `eng_Latn` | Defaults to English |

### Model Availability Behavior

When `CoreApiConfig.model_loaded == False`, translate requests return HTTP 503
with a clear message instructing the operator to install the local model in
`ml_models/nllb-200-distilled-600M`.

### LoRA Adapter Selection

```python
# In nllb_translate():
model = CoreApiConfig.lora_adapters.get(mode, CoreApiConfig.nllb_model)
# If mode='formal' and lora-cbk-formal exists → use formal adapter
# If mode='street' and lora-cbk-street exists → use street adapter
# Otherwise → use base NLLB-200 model
```

| Mode | Adapter Directory | Register |
|---|---|---|
| `formal` | `ml_models/lora-cbk-formal/` | High variety Chavacano |
| `street` | `ml_models/lora-cbk-street/` | Low variety Chavacano |

---

## Agent 4: Observer Agent (ISO 25010 Metrics)

### Role
Log every translation request with ISO 25010 performance metrics.

### Implementation
- **Model:** [core_api/models.py](backend/core_api/models.py) — `TranslationLog`
- **Logging:** [core_api/views.py](backend/core_api/views.py) — within `TranslateView.post()`
- **Admin:** [core_api/admin.py](backend/core_api/admin.py) — `TranslationLogAdmin`

### Behavior

Every translation request (success or failure) creates a `TranslationLog` entry:

```python
log_entry = TranslationLog(
    source_lang=source_lang,
    target_lang=target_lang,
    mode=mode,
    input_text=text,
    input_chars=len(text),
)

# After translation:
log_entry.output_text = translated_text
log_entry.input_tokens = tokens_in       # NLLB tokenizer count
log_entry.output_tokens = tokens_out     # NLLB tokenizer count
log_entry.latency_ms = elapsed_ms        # time.perf_counter() delta
log_entry.pivot_used = pivot_used        # True for non-EN pairs
log_entry.model_name = model_used        # e.g., 'nllb-200-distilled-600M+lora-cbk-formal'
log_entry.status = 'success'             # or 'error', 'timeout'
log_entry.wiki_voz_triggered = wiki_match is not None
log_entry.wiki_voz_term = wiki_match.term if wiki_match else ''
log_entry.save()
```

### TranslationLog Fields

| Field | Type | ISO 25010 Category |
|---|---|---|
| `latency_ms` | FLOAT | Performance Efficiency |
| `input_tokens` | INTEGER | Performance Efficiency |
| `output_tokens` | INTEGER | Performance Efficiency |
| `status` | VARCHAR (success/error/timeout) | Reliability |
| `error_message` | TEXT | Reliability |
| `pivot_used` | BOOLEAN | Functional Suitability |
| `wiki_voz_triggered` | BOOLEAN | Functional Suitability |
| `wiki_voz_term` | VARCHAR | Functional Suitability |
| `model_name` | VARCHAR | Traceability |
| `source_lang` / `target_lang` | VARCHAR | Coverage Analysis |
| `mode` | VARCHAR | Sociolinguistic Analysis |

### Admin Dashboard

`TranslationLogAdmin` provides:
- **list_display:** created_at, source_lang, target_lang, mode, latency_ms, status, pivot_used, wiki_voz_triggered
- **list_filter:** status, mode, source_lang, target_lang, pivot_used, wiki_voz_triggered
- **search_fields:** input_text, output_text, error_message
- **date_hierarchy:** created_at

### Example Queries

```python
# Average latency by engine
TranslationLog.objects.values('model_name').annotate(
    avg_ms=Avg('latency_ms'), count=Count('id')
)

# Error rate
total = TranslationLog.objects.count()
errors = TranslationLog.objects.filter(status='error').count()
error_rate = (errors / total) * 100

# Pivot usage frequency
TranslationLog.objects.filter(pivot_used=True).count()

# Wiki-Voz interception rate
TranslationLog.objects.filter(wiki_voz_triggered=True).count()

# Latency histogram (for box plots)
TranslationLog.objects.filter(status='success').values_list('latency_ms', flat=True)
```

---

## Agent 5: Presentation Agent (React Frontend)

### Role
User interface rendering, LAN-aware API communication, offline-capable PWA.

### Implementation
- **Shell:** [frontend/src/App.jsx](frontend/src/App.jsx)
- **Screens:** [TranslateScreen.jsx](frontend/src/components/screens/TranslateScreen.jsx), [WikiVozScreen.jsx](frontend/src/components/screens/WikiVozScreen.jsx), [SettingsScreen.jsx](frontend/src/components/screens/SettingsScreen.jsx)
- **PWA:** [vite.config.js](frontend/vite.config.js), [manifest.json](frontend/public/manifest.json)

### LAN-Aware API URL

```javascript
// App.jsx — Derives API URL from browser's current hostname
const API_URL = `http://${window.location.hostname}:8000/api`
```

This ensures the frontend works from any LAN client without hardcoded IP addresses.

### Health Check State

```javascript
const [health, setHealth] = useState({
    checking: true,
    backendUp: false,
    nllbLoaded: false,        // NEW: NLLB-200 model loaded?
    loraAdapters: [],         // NEW: ['formal', 'street']
    engine: 'unknown',
})
```

The `apiReady` prop passed to TranslateScreen:
```javascript
apiReady={health.backendUp && health.nllbLoaded}
```
This means the translate button is enabled only when the backend is reachable and the local model is loaded.

### TranslateScreen Features

| Feature | Implementation |
|---|---|
| Character limit | `maxLength={250}`, `.slice(0, 250)`, counter shows `/250` |
| Debounced auto-translate | 800ms debounce via `useRef` timer |
| Formal/Street toggle | `pill-toggle` button sends `mode` in payload |
| TTS (Text-to-Speech) | Web Speech API with BCP-47 voice selection |
| Cultural term highlighting | Regex matches on CULTURAL_TERMS_MAP from wikiVozData.js |
| Language tabs | 3 visible + dropdown for remaining 2 (mutual exclusion) |

### WikiVozScreen — API-Backed

```javascript
// Fetch all cultural terms from backend on mount
useEffect(() => {
    axios.get(`${API_URL}/wiki/`, { timeout: 8000 })
        .then(({ data }) => {
            const mapped = (data.results || []).map(t => ({
                id: t.id, term: t.term, definition: t.definition,
                imageUrl: t.image_url, language: t.language, category: t.category,
            }))
            setApiEntries(mapped.length > 0 ? mapped : null)
        })
        .catch(() => setApiError(true))
}, [])

// Fallback: use hardcoded seed data if API fails
const allEntries = apiEntries || WIKI_VOZ_ENTRIES
```

### SettingsScreen — localStorage Persistence

```javascript
const STORAGE_KEY = 'puente_settings'

function loadSettings() {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
}

// Persist on every change
useEffect(() => {
    saveSettings({ autoTranslate, defaultSourceLang, defaultTargetLang, speechEnabled })
}, [autoTranslate, defaultSourceLang, defaultTargetLang, speechEnabled])
```

Settings includes NLLB model status display:
```jsx
<span>{health?.nllbLoaded ? 'Loaded' : 'Not Loaded'}</span>
{health?.loraAdapters?.length > 0 && (
    <span>LoRA: {health.loraAdapters.join(', ')}</span>
)}
```

### PWA Configuration

**vite.config.js:**
```javascript
VitePWA({
    registerType: 'autoUpdate',
    manifest: false,  // Using manual manifest.json
    workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
            { urlPattern: /\/api\/health\//, handler: 'NetworkFirst' },
            { urlPattern: /\/api\/wiki\//, handler: 'NetworkFirst', maxAge: 86400 },
        ],
    },
})
```

**manifest.json:**
```json
{
    "name": "PUENTE — Cultural Translation",
    "short_name": "PUENTE",
    "display": "standalone",
    "background_color": "#121212",
    "theme_color": "#121212"
}
```

---

## 7. Data Flow: Complete Request Lifecycle

```
1. User types "Mahal kita" in TranslateScreen
   └── sourceText state updates, 800ms debounce timer starts

2. Timer fires → handleTranslate({ text: "Mahal kita", source_lang: "tl", target_lang: "cbk", mode: "formal" })
   └── axios.post(`http://<lan-host>:8000/api/translate/`, payload)

3. [Routing Agent] TranslateView.post()
   ├── TranslateRequestSerializer validates (text ≤ 250, mode ∈ {formal, street})
   └── Checks source_lang/target_lang ∈ SUPPORTED_LANGUAGES

4. [Interceptor Agent] Wiki-Voz lookup
   └── CulturalTerm.objects.filter(term__iexact="Mahal kita") → no match

5. [Neural Agent] CoreApiConfig.model_loaded?
   ├── YES: nllb_translate("Mahal kita", "tl", "cbk", "formal")
   │   ├── FLORES: tgl_Latn → cbk_Latn (neither is eng_Latn → PIVOT)
   │   ├── Hop 1: _infer_once(model, tok, "Mahal kita", tgl_Latn, eng_Latn) → "I love you"
   │   ├── Hop 2: _infer_once(model, tok, "I love you", eng_Latn, cbk_Latn) → "Ta ama yo contigo"
   │   └── Return: ("Ta ama yo contigo", 1840.5, 12, 8, True, "nllb-200+lora-cbk-formal")
    └── NO: return HTTP 503 (local model missing)

6. [Observer Agent] TranslationLog.save()
   └── latency_ms=1840.5, pivot_used=True, status='success', tokens_in=12, tokens_out=8

7. Response → { translated_text, latency_ms, tokens_in, tokens_out, pivot_used, model }

8. [Presentation Agent] setTranslatedText("Ta ama yo contigo")
   └── Renders in output panel with copy/TTS buttons
```

---

## 8. Error Handling Matrix

| Error | Source | HTTP Status | User Message |
|---|---|---|---|
| Empty text | Serializer | 400 | Field validation error |
| Text > 250 chars | Serializer | 400 | "Ensure this field has no more than 250 characters" |
| Unsupported language | SUPPORTED_LANGUAGES check | 400 | "Unsupported. Valid: [auto, en, tl, cbk, hil, ceb]" |
| No NLLB model present | `TranslateView.post()` | 503 | "Local NLLB model is unavailable..." |
| Model inference failure | `nllb_translate()` | 500 | "Translation failed: {details}" |
| Backend unreachable | Frontend axios | — | "Connection failed. Is the backend running?" |

---

## 9. Security Considerations

| Aspect | Implementation |
|---|---|
| Input Sanitization | DRF serializer enforces max_length=250, mode choices |
| CORS | `CORS_ALLOW_ALL_ORIGINS=True` (LAN-only deployment) |
| SQL Injection | Django ORM (parameterized queries) |
| Model Inference | `torch.no_grad()` context — no gradient accumulation |
| Frontend Secrets | None — API key never exposed to browser |

---

## 10. Known Limitations & Defense Notes

| Limitation | Mitigation | Defense Answer |
|---|---|---|
| All 5 languages natively supported | Hiligaynon (`hil_Latn`) has direct NLLB-200 support | No proxy needed — all translations are direct or via English pivot |
| LoRA adapters not yet trained | Falls back to base NLLB-200 weights | Training pipeline documented in notebooks/ |
| ml_models/ empty by default | Translation returns 503 until model install | Model download script provided; one-time setup |
| `CORS_ALLOW_ALL_ORIGINS=True` | LAN-only deployment (no internet exposure) | Appropriate for controlled campus network |
| No rate limiting | 250-char limit + TranslationLog enables post-hoc monitoring | Can add Django throttling if needed |
| Google Fonts CDN removed | System font fallback | Self-host WOFF2 files for exact Inter rendering |

---

See `README.md` for architecture overview and quick start.
