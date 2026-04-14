"""Cloud LoRA training pipeline for Project PUENTE (Colab + VS Code tunnel).

Why this version exists:
- Google Drive mounted under /content/drive is reliable but high-latency for tight
  training loops due to FUSE-backed reads.
- GPU training is faster and more stable when datasets are staged to local SSD-like
  Colab storage (/content/data) before DataLoader access.
- Checkpoints are written directly to Drive at save intervals so abrupt Colab runtime
    stops do not erase progress.

This script enforces a strict runtime contract:
1) Copy train/eval/test JSONL from source storage -> /content/data with SHA-256 verification.
2) Train from /content/data using nested translation schema JSONL.
3) Write checkpoints directly to artifact storage every configured save interval (default 500 steps).
4) Export final LoRA adapter to artifact storage /models/lora_adapters.
"""

from __future__ import annotations

import gc
import importlib
import inspect
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
)

from colab_drive_sync import (
    ensure_parent_dir,
    stage_split_jsonl,
)


def import_hf_datasets_symbols():
    """Import huggingface datasets safely even if local datasets/ folder exists.

    The repository contains a top-level folder named datasets, which can shadow
    the third-party huggingface package when current working directory is the
    project root. This guard sanitizes sys.path for the import operation.
    """
    project_root = Path(__file__).resolve().parents[2]
    original_sys_path = list(sys.path)

    sanitized = []
    for entry in original_sys_path:
        # Empty entry maps to current working directory.
        if entry == '' and Path.cwd().resolve() == project_root:
            continue
        try:
            if Path(entry).resolve() == project_root:
                continue
        except Exception:
            pass
        sanitized.append(entry)

    try:
        sys.path = sanitized
        datasets_mod = importlib.import_module('datasets')
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            'Missing dependency: datasets. Install Colab runtime deps with '
            'pip install -r notebooks/scripts/requirements_colab.txt'
        ) from exc
    finally:
        sys.path = original_sys_path

    if not hasattr(datasets_mod, 'load_dataset'):
        raise ImportError(
            'Imported module named datasets does not expose load_dataset. '
            'A local folder may be shadowing huggingface datasets, or the package is missing.'
        )

    return datasets_mod.DatasetDict, datasets_mod.load_dataset


def env_str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value.strip() if value and value.strip() else default


def env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if not value:
        return default
    return int(value)


def env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if not value:
        return default
    return float(value)


def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if not value:
        return default
    return value.strip().casefold() in {'1', 'true', 'yes', 'y', 'on'}


def resolve_hf_token() -> Optional[str]:
    for env_name in ('HF_TOKEN', 'HUGGINGFACEHUB_API_TOKEN', 'HUGGINGFACE_TOKEN'):
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()

    token_file = os.getenv('PUENTE_HF_TOKEN_FILE', '').strip()
    if token_file:
        path = Path(token_file).expanduser()
        if path.is_file():
            try:
                for raw_line in path.read_text(encoding='utf-8').splitlines():
                    candidate = raw_line.strip().strip('"').strip("'")
                    if candidate:
                        return candidate
            except OSError:
                pass

    return None


def hf_auth_kwargs(from_pretrained_callable, token: Optional[str]) -> Dict[str, str]:
    if not token:
        return {}

    try:
        params = inspect.signature(from_pretrained_callable).parameters
    except Exception:
        params = {}

    if 'token' in params:
        return {'token': token}
    if 'use_auth_token' in params:
        return {'use_auth_token': token}
    return {'token': token}


def model_dtype_kwargs(dtype_value) -> Dict[str, torch.dtype]:
    try:
        params = inspect.signature(AutoModelForSeq2SeqLM.from_pretrained).parameters
    except Exception:
        params = {}

    if 'dtype' in params:
        return {'dtype': dtype_value}
    return {'torch_dtype': dtype_value}


def infer_default_dataset_rel_dir(project_root: str) -> str:
    root = Path(project_root).expanduser()
    candidates = (
        'datasets/processed/80-10-10_split/01_chavacano',
        'datasets/processed/01_chavacano',
        'datasets/processed/001_chavacano',
    )
    required_files = ('train.jsonl', 'eval.jsonl', 'test.jsonl')

    for rel_dir in candidates:
        candidate_root = root / rel_dir
        if all((candidate_root / filename).is_file() for filename in required_files):
            return rel_dir

    # Keep legacy default when candidate probes are unavailable.
    return 'datasets/processed/001_chavacano'


FLORES_TO_SCHEMA_KEY = {
    'eng': 'en',
    'spa': 'es',
    'tgl': 'tl',
    'cbk': 'cbk',
    'ceb': 'ceb',
    'hil': 'hil',
}

SCHEMA_KEY_RE = re.compile(r'^[a-z][a-z0-9]{1,11}$')


def is_valid_schema_key(value: str) -> bool:
    return bool(SCHEMA_KEY_RE.fullmatch(value))


def _normalize_text_pair(source_text, target_text) -> Optional[tuple[str, str]]:
    if not isinstance(source_text, str) or not isinstance(target_text, str):
        return None

    source_text = source_text.strip()
    target_text = target_text.strip()
    if not source_text or not target_text:
        return None

    return source_text, target_text


def _extract_source_target_text(record: Dict, cfg: ColabConfig) -> Optional[tuple[str, str]]:
    """Extract a source/target text pair from supported dataset schemas.

    Supported formats:
    1) Nested translation contract:
       {"translation": {"<source_key>": "...", "en": "..."}}
    2) Flat paired text contract:
       {"source_text": "...", "target_text": "..."}
    3) Generic flat paired text contract:
       {"source": "...", "target": "..."}
    4) Flat language-key contract:
       {"cbk": "...", "en": "..."}
    """
    if not isinstance(record, dict):
        return None

    translation_block = record.get('translation')
    if isinstance(translation_block, dict):
        normalized = _normalize_text_pair(
            translation_block.get(cfg.source_translation_key),
            translation_block.get(cfg.target_translation_key),
        )
        if normalized is not None:
            return normalized

    normalized = _normalize_text_pair(record.get('source_text'), record.get('target_text'))
    if normalized is not None:
        return normalized

    normalized = _normalize_text_pair(record.get('source'), record.get('target'))
    if normalized is not None:
        return normalized

    normalized = _normalize_text_pair(
        record.get(cfg.source_translation_key),
        record.get(cfg.target_translation_key),
    )
    if normalized is not None:
        return normalized

    return None


@dataclass
class ColabConfig:
    # Dynamic paths
    drive_root: str
    dataset_rel_dir: str
    local_data_dir: str
    local_output_root: str
    drive_output_rel_dir: str
    run_name: str

    # Dataset schema
    train_filename: str
    eval_filename: str
    test_filename: str
    source_translation_key: str
    target_translation_key: str

    # Model/language setup
    model_id: str
    source_flores: str
    target_flores: str
    max_length: int

    # LoRA hyperparameters
    lora_r: int
    lora_alpha: int
    lora_dropout: float

    # Trainer hyperparameters
    batch_size_train: int
    batch_size_eval: int
    grad_accum_steps: int
    learning_rate: float
    num_epochs: float
    logging_steps: int
    eval_steps: int
    save_steps: int
    save_total_limit: int
    gradient_checkpointing: bool


def build_config() -> ColabConfig:
    source_flores = env_str('PUENTE_SOURCE_FLORES', 'cbk_Latn')
    target_flores = env_str('PUENTE_TARGET_FLORES', 'eng_Latn')
    source_tag = source_flores.split('_', 1)[0].casefold()
    target_tag = target_flores.split('_', 1)[0].casefold()
    dataset_tag = env_str('PUENTE_DATASET_TAG', '')
    default_source_key = FLORES_TO_SCHEMA_KEY.get(source_tag, source_tag)
    default_target_key = FLORES_TO_SCHEMA_KEY.get(target_tag, target_tag)
    source_translation_key = env_str('PUENTE_SOURCE_TRANSLATION_KEY', default_source_key).casefold()
    target_translation_key = env_str('PUENTE_TARGET_TRANSLATION_KEY', default_target_key).casefold()

    if not is_valid_schema_key(source_translation_key):
        raise ValueError(
            'PUENTE_SOURCE_TRANSLATION_KEY must be a lowercase schema key like cbk, ceb, es, hil, or tl.'
        )
    if target_translation_key != 'en':
        raise ValueError(
            f'PUENTE_TARGET_TRANSLATION_KEY must be en for this sequential source-to-English pipeline, got {target_translation_key!r}.'
        )

    default_project_root = env_str('PUENTE_PROJECT_ROOT', '/content/drive/MyDrive/ProjectPuenteCloud')
    if dataset_tag:
        default_dataset_rel_dir = f'datasets/processed/{dataset_tag}'
    else:
        default_dataset_rel_dir = infer_default_dataset_rel_dir(default_project_root)

    return ColabConfig(
        drive_root=env_str('PUENTE_DRIVE_ROOT', default_project_root),
        dataset_rel_dir=env_str('PUENTE_DATASET_REL_DIR', default_dataset_rel_dir),
        local_data_dir=env_str('PUENTE_LOCAL_DATA_DIR', '/content/data'),
        local_output_root=env_str('PUENTE_LOCAL_OUTPUT_ROOT', '/content/outputs'),
        drive_output_rel_dir=env_str('PUENTE_DRIVE_OUTPUT_REL_DIR', 'outputs'),
        run_name=env_str('PUENTE_RUN_NAME', f'lora-{source_tag}-to-{target_tag}-cloud'),
        train_filename=env_str('PUENTE_TRAIN_FILENAME', 'train.jsonl'),
        eval_filename=env_str('PUENTE_EVAL_FILENAME', 'eval.jsonl'),
        test_filename=env_str('PUENTE_TEST_FILENAME', 'test.jsonl'),
        source_translation_key=source_translation_key,
        target_translation_key=target_translation_key,
        model_id=env_str('PUENTE_MODEL_ID', 'facebook/nllb-200-distilled-600M'),
        source_flores=source_flores,
        target_flores=target_flores,
        max_length=env_int('PUENTE_MAX_LENGTH', 128),
        lora_r=env_int('PUENTE_LORA_R', 16),
        lora_alpha=env_int('PUENTE_LORA_ALPHA', 32),
        lora_dropout=env_float('PUENTE_LORA_DROPOUT', 0.05),
        batch_size_train=env_int('PUENTE_BATCH_SIZE_TRAIN', 4),
        batch_size_eval=env_int('PUENTE_BATCH_SIZE_EVAL', 4),
        grad_accum_steps=env_int('PUENTE_GRAD_ACCUM_STEPS', 4),
        learning_rate=env_float('PUENTE_LR', 2e-4),
        num_epochs=env_float('PUENTE_EPOCHS', 3.0),
        logging_steps=env_int('PUENTE_LOGGING_STEPS', 20),
        eval_steps=env_int('PUENTE_EVAL_STEPS', 100),
        save_steps=env_int('PUENTE_SAVE_STEPS', 500),
        save_total_limit=env_int('PUENTE_SAVE_TOTAL_LIMIT', 3),
        gradient_checkpointing=env_bool('PUENTE_GRADIENT_CHECKPOINTING', True),
    )


def gpu_gc(reason: str) -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass
    print(f'[gpu-gc] {reason}')


def resolve_paths(cfg: ColabConfig) -> Dict[str, Path]:
    drive_root = Path(cfg.drive_root).expanduser().resolve()
    artifact_root = Path(env_str('PUENTE_ARTIFACT_ROOT', cfg.drive_root)).expanduser().resolve()
    local_data_dir = Path(cfg.local_data_dir).expanduser().resolve()
    local_output_root = Path(cfg.local_output_root).expanduser().resolve() / cfg.run_name
    drive_checkpoint_dir = (artifact_root / 'models' / 'checkpoints').resolve()
    drive_lora_adapter_dir = (artifact_root / 'models' / 'lora_adapters' / cfg.run_name).resolve()

    drive_data_dir = drive_root / cfg.dataset_rel_dir
    drive_output_root = drive_root / cfg.drive_output_rel_dir / cfg.run_name

    paths = {
        'drive_root': drive_root,
        'artifact_root': artifact_root,
        'drive_data_dir': drive_data_dir,
        'local_data_dir': local_data_dir,
        'local_output_root': local_output_root,
        'drive_output_root': drive_output_root,
        'drive_train_jsonl': drive_data_dir / cfg.train_filename,
        'drive_eval_jsonl': drive_data_dir / cfg.eval_filename,
        'drive_test_jsonl': drive_data_dir / cfg.test_filename,
        'local_train_jsonl': local_data_dir / cfg.train_filename,
        'local_eval_jsonl': local_data_dir / cfg.eval_filename,
        'local_test_jsonl': local_data_dir / cfg.test_filename,
        'checkpoint_output_dir': drive_checkpoint_dir,
        'drive_lora_adapter_dir': drive_lora_adapter_dir,
    }
    paths['run_config_local'] = local_output_root / 'run_config.json'
    paths['run_config_drive'] = drive_output_root / 'run_config.json'
    paths['metrics_local'] = local_output_root / 'training_metrics.json'
    paths['metrics_drive'] = drive_output_root / 'training_metrics.json'
    return paths


def stage_datasets_from_drive(paths: Dict[str, Path]) -> None:
    print('[stage] copying datasets from source storage to local storage with checksums...')
    staged = stage_split_jsonl(
        drive_dataset_dir=paths['drive_data_dir'],
        local_data_dir=paths['local_data_dir'],
        filenames={
            'train': paths['drive_train_jsonl'].name,
            'eval': paths['drive_eval_jsonl'].name,
            'test': paths['drive_test_jsonl'].name,
        },
    )
    for split_name, local_path in staged.items():
        print(f'[stage] ready: {split_name} -> {local_path}')


def _read_first_json_line(jsonl_path: Path) -> Dict:
    with jsonl_path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f'Preflight failed: first non-empty line is invalid JSON in {jsonl_path}'
                ) from exc

            if not isinstance(payload, dict):
                raise ValueError(
                    f'Preflight failed: first JSONL record is not an object in {jsonl_path}'
                )
            return payload

    raise ValueError(f'Preflight failed: no JSON records found in {jsonl_path}')


def preflight_validate_local_splits(paths: Dict[str, Path], cfg: ColabConfig) -> None:
    """Hard-fail early if split files or schema contract are invalid.

    Strict checks:
    - train/eval/test must exist in /content/data (high-speed local storage).
    - first JSONL record in each split must expose a valid source/target text pair.
    """
    expected_local_root = Path('/content/data').resolve()
    configured_root = Path(cfg.local_data_dir).expanduser().resolve()
    if configured_root != expected_local_root:
        raise ValueError(
            f'Preflight failed: local_data_dir must be /content/data, got {configured_root}'
        )

    required_splits = {
        'train': paths['local_train_jsonl'],
        'eval': paths['local_eval_jsonl'],
        'test': paths['local_test_jsonl'],
    }

    for split_name, split_path in required_splits.items():
        if not split_path.exists():
            raise ValueError(
                f'Preflight failed: missing {split_name} split file in /content/data: {split_path}'
            )

        first_record = _read_first_json_line(split_path)
        extracted_pair = _extract_source_target_text(first_record, cfg)
        if extracted_pair is None:
            raise ValueError(
                f'Preflight failed: {split_name} split first record in {split_path} '
                'does not match any supported schema. Supported schemas include '
                '{"translation": {"<source_key>": "...", "en": "..."}}, '
                '{"source_text": "...", "target_text": "..."}, '
                '{"source": "...", "target": "..."}, or '
                f'flat language keys like {{"{cfg.source_translation_key}": "...", "{cfg.target_translation_key}": "..."}}.'
            )

    print('[preflight] split files and dataset schema validated successfully.')


def load_parallel_dataset(paths: Dict[str, Path]):
    _, load_dataset = import_hf_datasets_symbols()
    return load_dataset(
        'json',
        data_files={
            'train': str(paths['local_train_jsonl']),
            'validation': str(paths['local_eval_jsonl']),
            'test': str(paths['local_test_jsonl']),
        },
    )


def sanitize_dataset_records(dataset, cfg: ColabConfig):
    """Drop malformed rows to avoid crashing during tokenization.

    Any row that does not produce a non-empty source/target text pair is removed.
    This keeps long-running cloud jobs resilient to occasional bad records.
    """
    split_names = ['train', 'validation', 'test']
    before_counts = {split: len(dataset[split]) for split in split_names}

    def is_valid_record(example):
        return _extract_source_target_text(example, cfg) is not None

    sanitized = dataset.filter(is_valid_record)
    after_counts = {split: len(sanitized[split]) for split in split_names}

    dropped_total = 0
    for split in split_names:
        dropped = before_counts[split] - after_counts[split]
        dropped_total += dropped
        print(f'[data] {split}: kept {after_counts[split]}/{before_counts[split]} rows (dropped {dropped}).')

    if after_counts['train'] == 0 or after_counts['validation'] == 0 or after_counts['test'] == 0:
        raise ValueError(
            'Dataset sanitization removed all rows from at least one split. '
            'Verify JSONL schema and text fields.'
        )

    if dropped_total > 0:
        print('[data] Sanitization removed malformed rows; training will proceed with valid records only.')

    return sanitized


def build_training_args(cfg: ColabConfig, paths: Dict[str, Path]) -> Seq2SeqTrainingArguments:
    checkpoint_output_dir = paths['checkpoint_output_dir']
    checkpoint_output_dir.mkdir(parents=True, exist_ok=True)
    args_kwargs = {
        'output_dir': str(checkpoint_output_dir),
        'per_device_train_batch_size': cfg.batch_size_train,
        'per_device_eval_batch_size': cfg.batch_size_eval,
        'gradient_accumulation_steps': cfg.grad_accum_steps,
        'learning_rate': cfg.learning_rate,
        'num_train_epochs': cfg.num_epochs,
        'logging_steps': cfg.logging_steps,
        'eval_steps': cfg.eval_steps,
        'save_strategy': 'steps',
        'save_steps': cfg.save_steps,
        'save_total_limit': cfg.save_total_limit,
        'predict_with_generate': False,
        'fp16': torch.cuda.is_available(),
        'report_to': 'none',
        'save_safetensors': True,
    }

    # Transformers changed this arg name across versions.
    init_params = inspect.signature(Seq2SeqTrainingArguments.__init__).parameters
    if 'evaluation_strategy' in init_params:
        args_kwargs['evaluation_strategy'] = 'steps'
    elif 'eval_strategy' in init_params:
        args_kwargs['eval_strategy'] = 'steps'
    else:
        args_kwargs['do_eval'] = True

    return Seq2SeqTrainingArguments(**args_kwargs)


def main() -> None:
    cfg = build_config()
    paths = resolve_paths(cfg)

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    # Ensure output paths exist early for crash-safe metadata writes.
    paths['local_output_root'].mkdir(parents=True, exist_ok=True)
    paths['drive_output_root'].mkdir(parents=True, exist_ok=True)

    run_config = {
        'config': asdict(cfg),
        'paths': {key: str(value) for key, value in paths.items()},
        'notes': {
            'io_strategy': 'datasets are copied from source storage to /content/data before training',
            'reliability': f'trainer checkpoints are written directly to artifact storage every {cfg.save_steps} steps',
        },
    }
    ensure_parent_dir(paths['run_config_local'])
    paths['run_config_local'].write_text(json.dumps(run_config, indent=2), encoding='utf-8')
    ensure_parent_dir(paths['run_config_drive'])
    paths['run_config_drive'].write_text(json.dumps(run_config, indent=2), encoding='utf-8')

    stage_datasets_from_drive(paths)
    preflight_validate_local_splits(paths, cfg)
    gpu_gc('before-model-load')

    hf_token = resolve_hf_token()
    if hf_token:
        print('[auth] HF token detected; authenticated model download enabled.')
    else:
        print('[auth] HF token not detected; unauthenticated download may be rate-limited.')

    print('[model] loading tokenizer and base model...')
    tokenizer = AutoTokenizer.from_pretrained(
        cfg.model_id,
        **hf_auth_kwargs(AutoTokenizer.from_pretrained, hf_token),
    )
    base_model = AutoModelForSeq2SeqLM.from_pretrained(
        cfg.model_id,
        **model_dtype_kwargs(torch.float16 if torch.cuda.is_available() else torch.float32),
        **hf_auth_kwargs(AutoModelForSeq2SeqLM.from_pretrained, hf_token),
    )

    print('[model] applying LoRA adapter configuration...')
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=['q_proj', 'v_proj'],
        bias='none',
    )
    model = get_peft_model(base_model, lora_config)

    if cfg.gradient_checkpointing and hasattr(model, 'gradient_checkpointing_enable'):
        model.gradient_checkpointing_enable()
        if hasattr(model, 'config') and hasattr(model.config, 'use_cache'):
            model.config.use_cache = False
        print('[model] gradient checkpointing enabled.')

    model.print_trainable_parameters()

    dataset = load_parallel_dataset(paths)
    dataset = sanitize_dataset_records(dataset, cfg)

    def preprocess_function(example):
        tokenizer.src_lang = cfg.source_flores
        tokenizer.tgt_lang = cfg.target_flores

        extracted_pair = _extract_source_target_text(example, cfg)
        if extracted_pair is None:
            raise ValueError(
                'Invalid translation payload. Expected one of the supported schemas: '
                '{"translation": {"<source_key>": "...", "en": "..."}}, '
                '{"source_text": "...", "target_text": "..."}, '
                '{"source": "...", "target": "..."}, or '
                f'flat language keys like {{"{cfg.source_translation_key}": "...", "{cfg.target_translation_key}": "..."}}.'
            )
        source_text, target_text = extracted_pair

        inputs = tokenizer(
            source_text,
            max_length=cfg.max_length,
            truncation=True,
        )
        labels = tokenizer(
            text_target=target_text,
            max_length=cfg.max_length,
            truncation=True,
        )
        inputs['labels'] = labels['input_ids']
        return inputs

    print('[data] tokenizing train/validation/test splits...')
    tokenized_datasets = dataset.map(
        preprocess_function,
        remove_columns=dataset['train'].column_names,
    )
    print("Schema mapping successful. First tokenized example:", tokenized_datasets["train"][0])
    gpu_gc('after-tokenization')

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    training_args = build_training_args(cfg, paths)

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets['train'],
        eval_dataset=tokenized_datasets['validation'],
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    metrics: Dict[str, Dict] = {}
    try:
        print('[train] starting LoRA fine-tuning...')
        train_result = trainer.train()
        metrics['train'] = train_result.metrics

        print('[eval] running holdout evaluation on test split...')
        test_metrics = trainer.evaluate(eval_dataset=tokenized_datasets['test'], metric_key_prefix='test')
        metrics['test'] = test_metrics

    finally:
        gpu_gc('after-train')

    print('[export] saving final LoRA adapter to artifact storage...')
    paths['drive_lora_adapter_dir'].mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(paths['drive_lora_adapter_dir']))

    local_adapter_backup = paths['local_output_root'] / 'adapter'
    local_adapter_backup.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(local_adapter_backup))

    adapter_zip_path = paths['local_output_root'] / 'adapter.zip'
    if adapter_zip_path.exists():
        adapter_zip_path.unlink()
    shutil.make_archive(
        base_name=str(adapter_zip_path.with_suffix('')),
        format='zip',
        root_dir=str(local_adapter_backup),
    )

    # Persist metrics on both local and source-storage paths for reproducibility.
    ensure_parent_dir(paths['metrics_local'])
    paths['metrics_local'].write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    ensure_parent_dir(paths['metrics_drive'])
    paths['metrics_drive'].write_text(json.dumps(metrics, indent=2), encoding='utf-8')

    print('[done] Cloud training pipeline completed successfully.')
    print(f"[done] local output root: {paths['local_output_root']}")
    print(f"[done] source output root: {paths['drive_output_root']}")
    print(f"[done] artifact root: {paths['artifact_root']}")
    print(f"[done] checkpoint output dir: {paths['checkpoint_output_dir']}")
    print(f"[done] final LoRA adapter dir: {paths['drive_lora_adapter_dir']}")


if __name__ == '__main__':
    main()
