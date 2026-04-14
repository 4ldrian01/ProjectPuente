# Project PUENTE - Cloud-to-Local Deployment Playbook

This document defines the thesis deployment path:

- Phase A (Cloud): train LoRA adapters in Colab GPU through remote development.
- Phase B (Edge): run inference fully offline from local `ml_models` with zero API calls.

---

## Task 1 - VS Code <-> Colab Remote Tunnel

### Colab setup sequence

1. Open a fresh Colab GPU notebook.
2. Run the cells from:
   - `notebooks/scripts/colab_vscode_tunnel_setup.md`
3. Complete tunnel sign-in URL shown in Colab logs.
4. In local VS Code, use `Remote Tunnels: Connect to Tunnel...`.

### Why this architecture

This allows local code ergonomics while training executes in cloud GPU memory,
so large checkpoints and temporary training artifacts do not burden the laptop.

---

## Task 2 - Cloud LoRA Training

### Training script

Use:

- `notebooks/scripts/colab_lora_training_pipeline.py`

Expected input files in Drive:

- `/content/drive/MyDrive/ProjectPuenteCloud/data/train.jsonl`
- `/content/drive/MyDrive/ProjectPuenteCloud/data/eval.jsonl`

Expected JSONL schema:

```json
{"translation": {"cbk": "Good morning", "en": "Buenos dias"}}
```

This unified schema applies to both Chavacano (`cbk`) and Cebuano (`ceb`) datasets,
using the same nested `translation` object with the source language key (`cbk` or
`ceb`) and the target key `en`.

LoRA configuration in script:

- `r=16`
- `lora_alpha=32`
- `target_modules=["q_proj", "v_proj"]`

Export products:

- adapter directory in Drive output
- zip archive containing adapter files
- metadata JSON for reproducibility

---

## Task 3 - Offline Local Preparation

### Download base model locally (one-time, optional until inference staging)

From project root:

```bash
cd ml_models
python download_model.py
```

Dependency-only exception:

- You may defer this step during system setup and install all packages first.
- If deferred, backend still boots, but translation and BTVL stay in explicit 503 state until local weights are present.

This writes to:

- `/home/rauf/Desktop/Machine Learning/ProjectPuente/ml_models/nllb-200-distilled-600M`

### Place LoRA adapters locally

Directory contract:

- `ml_models/lora_adapters/lora-cbk-formal/`
- `ml_models/lora_adapters/lora-cbk-street/`

See placement details:

- `ml_models/lora_adapters/README.md`

---

## Task 4 - Strict Edge Inference Refactor

Backend now enforces local-only model execution:

- `backend/core_api/apps.py`
  - loads base model from local disk
  - loads local LoRA adapters into RAM at startup
  - enforces `local_files_only=True`
- `backend/core_api/views.py`
  - `POST /api/translate/` uses local `nllb_translate(...)`
  - `POST /api/btvl/` uses local `nllb_translate(...)`
  - no outbound network inference path

Startup flag:

```bash
PUENTE_LOAD_MODEL_ON_STARTUP=true ./run_project.sh --backend-only
```

---

## Task 5 - Offline Telemetry Calibration

`GET /api/telemetry/` now reports local hardware stress for live panel demos:

- RAM via `psutil`
- GPU VRAM via `torch.cuda` (primary)
- GPU fallback via `GPUtil` when needed

This keeps frontend telemetry tied to actual laptop utilization during inference.

---

## Recommended Validation Checklist

1. Start backend with preload flag and confirm `model_loaded=true` in `/api/health/`.
2. Run EN->ES and CBK->EN sample requests via `/api/translate/`.
3. Run `/api/btvl/` against a known phrase and verify semantic back-translation.
4. Open frontend dashboard and verify telemetry updates during active translation.
5. Disable network and repeat request tests to prove offline operation.
