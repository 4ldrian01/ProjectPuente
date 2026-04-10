# Local LoRA Adapter Placement (Offline Defense)

This directory stores LoRA adapters exported from Colab after cloud training.

Required layout:

- `ml_models/lora_adapters/lora-cbk-formal/`
- `ml_models/lora_adapters/lora-cbk-street/`

Each adapter directory should include at minimum:

- `adapter_config.json`
- `adapter_model.bin` or `adapter_model.safetensors`

After placing adapters here, restart backend with model preload enabled:

```bash
cd /home/rauf/Desktop/Machine\ Learning/ProjectPuente
PUENTE_LOAD_MODEL_ON_STARTUP=true ./run_project.sh --backend-only
```

`CoreApiConfig.ready()` will load these adapters into RAM at startup with `local_files_only=True`.
