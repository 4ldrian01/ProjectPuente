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
    nllb_model = None
    lora_adapters = {}
    model_loaded = False
    engine_name = 'offline-model-missing'
    _ready_ran = False

    def ready(self):
        """
        Load base NLLB + local LoRA adapters into RAM exactly once.

        Startup loading is intentionally guarded by PUENTE_LOAD_MODEL_ON_STARTUP
        so migrations/tests can run fast without huge model initialization.
        """
        if CoreApiConfig._ready_ran:
            return
        CoreApiConfig._ready_ran = True

        if not _env_flag('PUENTE_LOAD_MODEL_ON_STARTUP', False):
            logger.info('Model preload skipped (PUENTE_LOAD_MODEL_ON_STARTUP is false).')
            return

        if any(cmd in sys.argv for cmd in {'makemigrations', 'migrate', 'collectstatic', 'test'}):
            logger.info('Model preload skipped for management command: %s', ' '.join(sys.argv))
            return

        project_root = Path(getattr(settings, 'PROJECT_ROOT', Path(__file__).resolve().parents[2]))
        configured_model_path = getattr(settings, 'ML_MODEL_PATH', 'ml_models/nllb-200-distilled-600M')
        model_path = Path(configured_model_path)
        if not model_path.is_absolute():
            model_path = project_root / model_path
        model_path = model_path.resolve()

        adapter_root = project_root / 'ml_models' / 'lora_adapters'
        adapter_candidates = {
            'formal': adapter_root / 'lora-cbk-formal',
            'street': adapter_root / 'lora-cbk-street',
        }

        if not model_path.exists():
            logger.error('Local model path does not exist: %s', model_path)
            return

        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info('Loading local tokenizer from %s (offline enforced).', model_path)
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                local_files_only=True,
                use_fast=True,
            )

            load_kwargs = {'local_files_only': True}
            can_use_low_cpu_mem = False

            try:
                import accelerate  # noqa: F401

                can_use_low_cpu_mem = True
            except ImportError:
                can_use_low_cpu_mem = False

            if torch.cuda.is_available():
                try:
                    import bitsandbytes  # noqa: F401

                    load_kwargs.update({
                        'load_in_8bit': True,
                        'device_map': 'auto',
                    })
                    logger.info('CUDA + bitsandbytes detected: using 8-bit model loading.')
                except ImportError:
                    load_kwargs['dtype'] = torch.float16
                    logger.info('CUDA detected without bitsandbytes: using float16 model loading.')
            else:
                cpu_threads = min(2, os.cpu_count() or 2)
                torch.set_num_threads(cpu_threads)
                try:
                    torch.set_num_interop_threads(1)
                except RuntimeError:
                    # Safe to ignore if thread pool already initialized.
                    pass
                load_kwargs['dtype'] = torch.float32
                if can_use_low_cpu_mem:
                    load_kwargs['low_cpu_mem_usage'] = True
                logger.info(
                    'CUDA unavailable: using CPU float32 model loading (threads=%s).',
                    cpu_threads,
                )

            logger.info('Loading local NLLB base model from %s (offline enforced).', model_path)
            model = None
            last_error = None
            used_load_kwargs = dict(load_kwargs)

            load_attempts = [dict(load_kwargs)]
            if 'load_in_8bit' in load_kwargs:
                # Compatibility fallback for environments where 8-bit kwargs are
                # accepted by transformers but rejected by model constructors.
                fallback_kwargs = dict(load_kwargs)
                fallback_kwargs.pop('load_in_8bit', None)
                fallback_kwargs.pop('device_map', None)
                fallback_kwargs['dtype'] = torch.float16
                load_attempts.append(fallback_kwargs)

            for attempt_kwargs in load_attempts:
                try:
                    model = AutoModelForSeq2SeqLM.from_pretrained(
                        str(model_path),
                        **attempt_kwargs,
                    )
                    used_load_kwargs = attempt_kwargs
                    break
                except TypeError as exc:
                    exc_text = str(exc)

                    if 'dtype' in exc_text and 'dtype' in attempt_kwargs:
                        compat_kwargs = dict(attempt_kwargs)
                        compat_kwargs['torch_dtype'] = compat_kwargs.pop('dtype')
                        try:
                            model = AutoModelForSeq2SeqLM.from_pretrained(
                                str(model_path),
                                **compat_kwargs,
                            )
                            used_load_kwargs = compat_kwargs
                            break
                        except TypeError as compat_exc:
                            if (
                                'load_in_8bit' in str(compat_exc)
                                and 'load_in_8bit' in compat_kwargs
                            ):
                                logger.warning(
                                    '8-bit load unsupported in this runtime; retrying without quantization.'
                                )
                                last_error = compat_exc
                                continue
                            last_error = compat_exc
                            continue

                    if 'load_in_8bit' in exc_text and 'load_in_8bit' in attempt_kwargs:
                        logger.warning(
                            '8-bit load unsupported in this runtime; retrying without quantization.'
                        )
                        last_error = exc
                        continue

                    last_error = exc

            if model is None:
                if last_error:
                    raise last_error
                raise RuntimeError('Model loading failed with no captured exception.')

            using_int8 = bool(used_load_kwargs.get('load_in_8bit'))
            if torch.cuda.is_available() and not using_int8:
                model = model.to('cuda')
            model.eval()

            loaded_adapters = {}
            peft_wrapped = False

            # Academic note: adapters are loaded into RAM at boot to avoid
            # first-request latency spikes during live panel demonstrations.
            for mode, adapter_path in adapter_candidates.items():
                if not adapter_path.exists():
                    continue

                logger.info('Loading local LoRA adapter %s from %s', mode, adapter_path)
                if not peft_wrapped:
                    model = PeftModel.from_pretrained(
                        model,
                        str(adapter_path),
                        adapter_name=mode,
                        is_trainable=False,
                        local_files_only=True,
                    )
                    peft_wrapped = True
                else:
                    model.load_adapter(
                        str(adapter_path),
                        adapter_name=mode,
                        is_trainable=False,
                        local_files_only=True,
                    )
                loaded_adapters[mode] = mode

            if loaded_adapters and hasattr(model, 'set_adapter'):
                default_mode = 'formal' if 'formal' in loaded_adapters else next(iter(loaded_adapters))
                model.set_adapter(default_mode)

            CoreApiConfig.nllb_tokenizer = tokenizer
            CoreApiConfig.nllb_model = model
            CoreApiConfig.lora_adapters = loaded_adapters
            CoreApiConfig.model_loaded = True
            CoreApiConfig.engine_name = 'nllb-200-distilled-600M+local-lora' if loaded_adapters else 'nllb-200-distilled-600M'

            logger.info(
                'Offline inference stack ready. model_loaded=%s adapters=%s',
                CoreApiConfig.model_loaded,
                sorted(loaded_adapters.keys()),
            )
        except Exception:
            logger.exception('Failed to initialize local offline model stack.')
            CoreApiConfig.nllb_tokenizer = None
            CoreApiConfig.nllb_model = None
            CoreApiConfig.lora_adapters = {}
            CoreApiConfig.model_loaded = False
            CoreApiConfig.engine_name = 'offline-model-missing'

