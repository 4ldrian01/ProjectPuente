# Local LoRA Adapter Placement (Offline Defense)

This directory stores LoRA adapters exported from cloud/local training runs.

## Required layout

- `ml_models/lora_adapters/lora-cbk-formal/`
- `ml_models/lora_adapters/lora-cbk-street/`

`backend/core_api/apps.py` currently looks for these exact folder names at startup.

## Required files per adapter folder

- `adapter_config.json`
- `adapter_model.bin` **or** `adapter_model.safetensors`

## Runtime behavior

- If adapters are present, backend loads them into RAM on startup and switches by mode (`formal` / `street`).
- If adapters are missing, backend still runs using base NLLB weights only.

## Restart examples after placing adapters

Linux/macOS:

```bash
PUENTE_LOAD_MODEL_ON_STARTUP=true ./run_project.sh --backend-only
```

Windows PowerShell:

```powershell
$env:PUENTE_LOAD_MODEL_ON_STARTUP = 'true'
.\run_project.ps1 -BackendOnly
```

`CoreApiConfig.ready()` enforces local-only loading (`local_files_only=True`).
