"""
core_api/apps.py — Singleton NLLB-200 model loader for Project Puente.

Loads the 8-bit quantized NLLB-200-distilled-600M base model and LoRA
(PEFT) adapters exactly ONCE at Django server startup via the ready() hook.
All views access the model through CoreApiConfig class variables — zero
per-request reloading.
"""

import os
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core_api'

    # ── Singleton Class Variables (shared across all requests) ──
    nllb_tokenizer = None
    nllb_model = None
    lora_adapters = {}          # {'formal': merged_model, 'street': merged_model}
    model_loaded = False
    engine_name = 'nllb-200-distilled-600M'

    def ready(self):
        """Load NLLB-200 + LoRA once at server startup (Singleton)."""
        # Prevent double-load from Django auto-reloader
        if os.environ.get('RUN_MAIN') != 'true':
            return
        if CoreApiConfig.model_loaded:
            return

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        PROJECT_ROOT = os.path.dirname(BASE_DIR)
        MODEL_DIR = os.path.join(PROJECT_ROOT, 'ml_models', 'nllb-200-distilled-600M')
        LORA_DIR = os.path.join(PROJECT_ROOT, 'ml_models')

        if not os.path.isdir(MODEL_DIR):
            logger.warning(
                'NLLB-200 model directory not found at %s. '
                'Translation will use FALLBACK mode (no local ML). '
                'Run the model download script first.',
                MODEL_DIR,
            )
            CoreApiConfig.model_loaded = False
            return

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            # ── Load Tokenizer ──
            logger.info('Loading NLLB-200 tokenizer from %s …', MODEL_DIR)
            CoreApiConfig.nllb_tokenizer = AutoTokenizer.from_pretrained(
                MODEL_DIR, local_files_only=True,
            )

            # ── Detect optimal device and quantization ──
            use_cuda = torch.cuda.is_available()
            quantize_8bit = False

            if use_cuda:
                try:
                    import bitsandbytes  # noqa: F401
                    quantize_8bit = True
                    logger.info('CUDA + bitsandbytes available — using INT8 on GPU.')
                except ImportError:
                    logger.info('CUDA available but bitsandbytes missing — using FP16 on GPU.')
            else:
                logger.info('No CUDA — loading model in FP32 on CPU.')

            # ── Load Base Model ──
            if quantize_8bit:
                base_model = AutoModelForSeq2SeqLM.from_pretrained(
                    MODEL_DIR, local_files_only=True,
                    load_in_8bit=True, device_map='auto',
                )
            elif use_cuda:
                base_model = AutoModelForSeq2SeqLM.from_pretrained(
                    MODEL_DIR, local_files_only=True,
                    torch_dtype=torch.float16, device_map='auto',
                )
            else:
                base_model = AutoModelForSeq2SeqLM.from_pretrained(
                    MODEL_DIR, local_files_only=True,
                    torch_dtype=torch.float32, device_map='cpu',
                )

            base_model.eval()
            CoreApiConfig.nllb_model = base_model

            # ── Load LoRA Adapters (dynamic switching, NOT merge) ──
            try:
                from peft import PeftModel

                first_adapter_loaded = False
                for mode in ['formal', 'street']:
                    adapter_path = os.path.join(LORA_DIR, f'lora-cbk-{mode}')
                    if os.path.isdir(adapter_path):
                        if not first_adapter_loaded:
                            logger.info('Loading LoRA adapter: %s', mode)
                            peft_model = PeftModel.from_pretrained(
                                base_model, adapter_path,
                                adapter_name=mode, local_files_only=True,
                            )
                            first_adapter_loaded = True
                        else:
                            logger.info('Loading additional LoRA adapter: %s', mode)
                            peft_model.load_adapter(adapter_path, adapter_name=mode)
                        CoreApiConfig.lora_adapters[mode] = mode
                    else:
                        logger.warning('LoRA adapter missing: %s', adapter_path)

                if first_adapter_loaded:
                    peft_model.eval()
                    CoreApiConfig.nllb_model = peft_model

            except ImportError:
                logger.warning(
                    'peft not installed — LoRA adapters will NOT be loaded. '
                    'Translations will use base NLLB-200 weights only.'
                )

            CoreApiConfig.model_loaded = True
            params = sum(p.numel() for p in base_model.parameters())
            logger.info(
                'NLLB-200 loaded: %s params, device: %s, LoRA adapters: %s',
                f'{params:,}',
                next(base_model.parameters()).device,
                list(CoreApiConfig.lora_adapters.keys()) or 'NONE',
            )

        except Exception:
            logger.exception('Failed to load NLLB-200 model — fallback mode active.')
            CoreApiConfig.model_loaded = False

