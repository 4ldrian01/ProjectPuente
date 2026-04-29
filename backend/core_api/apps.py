"""
core_api/apps.py - Singleton offline model loader for Project Puente.

Cloud-to-local architecture note:
- LoRA training can happen in cloud RDE sessions (Colab GPU).
- Thesis defense inference must run fully offline from local disk.

This module enforces the edge phase by loading only local artifacts
from ml_models with local_files_only=True and never pulling from network.
"""

import logging
import os
import sys
import gc
import threading
import atexit
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


def _env_flag(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


class CoreApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core_api'

    # Singleton class variables (shared by all requests in this process).
    nllb_tokenizer = None
    nllb_base_model = None
    nllb_model = None
    lora_adapters = {}
    adapter_paths = {}
    active_adapter_mode = ''
    model_loaded = False
    engine_name = 'offline-model-missing'
    _ready_ran = False
    _model_load_lock = threading.RLock()

    @classmethod
    def _resolve_model_path(cls):
        project_root = Path(getattr(settings, 'PROJECT_ROOT', Path(__file__).resolve().parents[2]))
        configured_model_path = getattr(settings, 'ML_MODEL_PATH', 'ml_models/nllb-200-distilled-600M')
        model_path = Path(configured_model_path)
        if not model_path.is_absolute():
            model_path = project_root / model_path
        return project_root, model_path.resolve()

    @classmethod
    def _resolve_adapter_paths(cls, project_root):
        adapter_root = project_root / 'ml_models' / 'lora_adapters'
        adapter_candidates = {
            'formal': adapter_root / 'lora-cbk-formal',
            'street': adapter_root / 'lora-cbk-street',
        }
        fallback_adapter_root = project_root / 'models' / 'lora_adapters'

        def _is_adapter_dir(path):
            if not path.exists() or not path.is_dir():
                return False
            if not (path / 'adapter_config.json').exists():
                return False
            if (path / 'adapter_model.safetensors').exists():
                return True
            if (path / 'adapter_model.bin').exists():
                return True
            return False

        adapter_paths = {}
        for mode, adapter_path in adapter_candidates.items():
            if _is_adapter_dir(adapter_path):
                adapter_paths[mode] = adapter_path

        if not adapter_paths and fallback_adapter_root.exists():
            fallback_candidates = [
                path for path in fallback_adapter_root.iterdir()
                if _is_adapter_dir(path)
            ]
            if fallback_candidates:
                fallback_choice = sorted(fallback_candidates, key=lambda p: str(p))[0]
                adapter_paths = {
                    'formal': fallback_choice,
                    'street': fallback_choice,
                }
                logger.warning(
                    'Fallback LoRA adapter detected at %s; using it for both formal/street modes.',
                    fallback_choice,
                )

        return adapter_paths

    @classmethod
    def load_model_stack(cls):
        """Load tokenizer, 8-bit base model, and local LoRA adapters safely."""
        with cls._model_load_lock:
            if cls.model_loaded and cls.nllb_model is not None and cls.nllb_tokenizer is not None:
                return True

            project_root, model_path = cls._resolve_model_path()

            if not model_path.exists():
                logger.error('Local model path does not exist: %s', model_path)
                return False

            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, BitsAndBytesConfig
            except ImportError:
                logger.exception('Transformers/torch unavailable; cannot load local model stack.')
                return False

            # Anti-spike protocol: clear host/device allocator state before model load.
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            if not torch.cuda.is_available():
                logger.error(
                    'CUDA is required for strict 8-bit inference. '
                    'Model load skipped because GPU is unavailable.'
                )
                return False

            try:
                import bitsandbytes  # noqa: F401
            except ImportError:
                logger.error(
                    'bitsandbytes is required for 8-bit inference. '
                    'Install with: pip install bitsandbytes'
                )
                return False

            try:
                from peft import PeftModel
            except ImportError:
                logger.error('peft is required. Install with: pip install peft')
                return False

            logger.info('Loading local tokenizer from %s (offline enforced).', model_path)
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                local_files_only=True,
                use_fast=True,
            )

            # THE VRAM SPILLOVER PROTOCOL
            # 1. device_map must be 'auto' to allow CPU spillover
            # 2. max_memory creates an artificial ceiling to prevent the crash
            
            # THE 4-BIT SILVER BULLET PROTOCOL
            # Compresses the base model massively so the 1GB spike survives.
            
            import torch # Ensure torch is imported for the dtype
            
            # THE NATIVE FP16 PROTOCOL (Bypassing BitsAndBytes entirely)
            # 600M params in float16 = ~1.2 GB. It natively fits in a 4GB RTX!
            
            import torch
            
            load_kwargs = {
    'local_files_only': True,
    'device_map': 'auto', 
    'torch_dtype': torch.float16,  # 🚀 Forces 1.2GB VRAM usage
    'low_cpu_mem_usage': True,
    'max_memory': {0: "2.5GiB", "cpu": "3GiB"} # 🚀 OS Safety Ceiling
}

            logger.info('Loading local NLLB base model from %s (offline enforced).', model_path)
            try:
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    str(model_path),
                    **load_kwargs,
                )
            except Exception:
                logger.exception('8-bit model load failed. Keep the model on disk and retry with enough GPU/CPU memory.')
                CoreApiConfig.nllb_tokenizer = None
                CoreApiConfig.nllb_base_model = None
                CoreApiConfig.nllb_model = None
                CoreApiConfig.lora_adapters = {}
                CoreApiConfig.adapter_paths = {}
                CoreApiConfig.active_adapter_mode = ''
                CoreApiConfig.model_loaded = False
                CoreApiConfig.engine_name = 'offline-model-missing'
                return False

            model.eval()

            adapter_paths = cls._resolve_adapter_paths(project_root)

            CoreApiConfig.nllb_tokenizer = tokenizer
            CoreApiConfig.nllb_base_model = model
            CoreApiConfig.nllb_model = model
            CoreApiConfig.adapter_paths = adapter_paths
            CoreApiConfig.lora_adapters = {
                mode: path.name for mode, path in adapter_paths.items()
            }
            CoreApiConfig.active_adapter_mode = ''
            CoreApiConfig.model_loaded = True
            CoreApiConfig.engine_name = (
                'nllb-200-distilled-600M+8bit-peft'
                if adapter_paths
                else 'nllb-200-distilled-600M+8bit'
            )

            logger.info(
                'Offline inference stack ready. model_loaded=%s adapters=%s',
                CoreApiConfig.model_loaded,
                sorted(adapter_paths.keys()),
            )
            return True

    @classmethod
    def ensure_model_loaded(cls):
        """Load the model stack on demand without forcing startup memory spikes."""
        if cls.model_loaded and cls.nllb_model is not None and cls.nllb_tokenizer is not None:
            return True
        return cls.load_model_stack()

    def ready(self):
        """Load base NLLB + local LoRA adapters into RAM exactly once."""
        import os
        import sys
        
        if CoreApiConfig._ready_ran:
            return
        CoreApiConfig._ready_ran = True

        # FIXED: Smart check that safely handles the --noreload command!
        is_using_reloader = '--noreload' not in sys.argv
        is_main_worker = os.environ.get('RUN_MAIN') == 'true'

        if is_using_reloader and not is_main_worker:
            logger.info("Skipping model load in Django auto-reloader thread to save RAM.")
            return

        if not _env_flag('PUENTE_LOAD_MODEL_ON_STARTUP', False):
            logger.info('Model preload skipped (PUENTE_LOAD_MODEL_ON_STARTUP is false).')
            return

        if any(cmd in sys.argv for cmd in {'makemigrations', 'migrate', 'collectstatic', 'test'}):
            logger.info('Model preload skipped for management command.')
            return

        logger.info("🚀 INITIATING NEURAL ENGINE BOOT SEQUENCE...")
        if not CoreApiConfig.load_model_stack():
            logger.warning('Startup model preload did not complete; model will be loaded on demand.')
            
        logger.info("🚀 INITIATING NEURAL ENGINE BOOT SEQUENCE...")
        if not CoreApiConfig.load_model_stack():
            logger.warning('Startup model preload did not complete.')
            
        # 🚀 FIX 1: THE VRAM CLEANUP PROTOCOL
        # Forces PyTorch to surrender GPU memory instantly on Ctrl+C
        @atexit.register
        def release_vram():
            import torch
            print("\n🛑 SHUTTING DOWN NEURAL ENGINE: Freeing RTX VRAM...")
            CoreApiConfig.nllb_model = None
            CoreApiConfig.nllb_base_model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()