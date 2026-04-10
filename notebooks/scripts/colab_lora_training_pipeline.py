"""Cloud LoRA training pipeline for Project PUENTE (Colab + VS Code tunnel).

Why this version exists:
- Google Drive mounted under /content/drive is reliable but high-latency for tight
  training loops due to FUSE-backed reads.
- GPU training is faster and more stable when datasets are staged to local SSD-like
  Colab storage (/content/data) before DataLoader access.
- Checkpoints are continuously mirrored back to Drive so abrupt Colab runtime stops
  do not erase progress.

This script enforces a strict runtime contract:
1) Copy train/eval/test JSONL from Drive -> /content/data with SHA-256 verification.
2) Train locally from /content/data only.
3) Mirror local checkpoints to Drive periodically and on every save event.
4) Use aggressive GPU cache cleanup hooks to reduce VRAM fragmentation on T4.
"""

from __future__ import annotations

import gc
import importlib
import json
import os
import shutil
import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Tuple

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
)

from colab_drive_sync import (
    copy_file_with_checksum,
    ensure_parent_dir,
    stage_split_jsonl,
    sync_tree_with_checksums,
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
    source_column: str
    target_column: str

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

    # Reliability controls
    drive_sync_interval_sec: int
    drive_sync_step_interval: int


def build_config() -> ColabConfig:
    source_flores = env_str('PUENTE_SOURCE_FLORES', 'eng_Latn')
    target_flores = env_str('PUENTE_TARGET_FLORES', 'cbk_Latn')
    source_tag = source_flores.split('_', 1)[0].casefold()
    target_tag = target_flores.split('_', 1)[0].casefold()
    dataset_tag = env_str('PUENTE_DATASET_TAG', '001_chavacano')

    return ColabConfig(
        drive_root=env_str('PUENTE_DRIVE_ROOT', '/content/drive/MyDrive/ProjectPuenteCloud'),
        dataset_rel_dir=env_str('PUENTE_DATASET_REL_DIR', f'datasets/processed/{dataset_tag}'),
        local_data_dir=env_str('PUENTE_LOCAL_DATA_DIR', '/content/data'),
        local_output_root=env_str('PUENTE_LOCAL_OUTPUT_ROOT', '/content/outputs'),
        drive_output_rel_dir=env_str('PUENTE_DRIVE_OUTPUT_REL_DIR', 'outputs'),
        run_name=env_str('PUENTE_RUN_NAME', f'lora-{source_tag}-to-{target_tag}-cloud'),
        train_filename=env_str('PUENTE_TRAIN_FILENAME', 'train.jsonl'),
        eval_filename=env_str('PUENTE_EVAL_FILENAME', 'eval.jsonl'),
        test_filename=env_str('PUENTE_TEST_FILENAME', 'test.jsonl'),
        source_column=env_str('PUENTE_SOURCE_COLUMN', 'source_text'),
        target_column=env_str('PUENTE_TARGET_COLUMN', 'target_text'),
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
        save_steps=env_int('PUENTE_SAVE_STEPS', 100),
        save_total_limit=env_int('PUENTE_SAVE_TOTAL_LIMIT', 3),
        gradient_checkpointing=env_bool('PUENTE_GRADIENT_CHECKPOINTING', True),
        drive_sync_interval_sec=env_int('PUENTE_DRIVE_SYNC_INTERVAL_SEC', 120),
        drive_sync_step_interval=env_int('PUENTE_DRIVE_SYNC_STEP_INTERVAL', 50),
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
    local_data_dir = Path(cfg.local_data_dir).expanduser().resolve()
    local_output_root = Path(cfg.local_output_root).expanduser().resolve() / cfg.run_name

    drive_data_dir = drive_root / cfg.dataset_rel_dir
    drive_output_root = drive_root / cfg.drive_output_rel_dir / cfg.run_name

    paths = {
        'drive_root': drive_root,
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
        'local_trainer_dir': local_output_root / 'trainer_runs',
        'drive_trainer_dir': drive_output_root / 'trainer_runs',
        'local_adapter_dir': local_output_root / 'adapter',
        'drive_adapter_dir': drive_output_root / 'adapter',
    }
    paths['local_adapter_zip'] = local_output_root / 'adapter.zip'
    paths['drive_adapter_zip'] = drive_output_root / 'adapter.zip'
    paths['run_config_local'] = local_output_root / 'run_config.json'
    paths['run_config_drive'] = drive_output_root / 'run_config.json'
    paths['metrics_local'] = local_output_root / 'training_metrics.json'
    paths['metrics_drive'] = drive_output_root / 'training_metrics.json'
    return paths


def stage_datasets_from_drive(paths: Dict[str, Path]) -> None:
    print('[stage] copying datasets from Drive to local storage with checksums...')
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
    - first JSONL record in each split must include source_text and target_text.
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
        missing_keys = [
            key for key in (cfg.source_column, cfg.target_column)
            if key not in first_record
        ]
        if missing_keys:
            raise ValueError(
                f'Preflight failed: {split_name} split first record in {split_path} '
                f'missing required keys: {missing_keys}'
            )

    print('[preflight] split files and schema keys validated successfully.')


class CheckpointMirrorThread(threading.Thread):
    def __init__(self, src_root: Path, dst_root: Path, interval_sec: int, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.src_root = src_root
        self.dst_root = dst_root
        self.interval_sec = interval_sec
        self.stop_event = stop_event

    def run(self) -> None:
        while not self.stop_event.wait(self.interval_sec):
            try:
                copied, skipped = sync_tree_with_checksums(self.src_root, self.dst_root)
                if copied > 0:
                    print(f'[sync-thread] checkpoints mirrored: copied={copied} skipped={skipped}')
            except Exception as exc:
                print(f'[sync-thread] warning: {exc}')


class ReliabilityCallback(TrainerCallback):
    """Sync checkpoints + aggressively clear GPU cache during long runs."""

    def __init__(self, local_ckpt_dir: Path, drive_ckpt_dir: Path, sync_step_interval: int):
        self.local_ckpt_dir = local_ckpt_dir
        self.drive_ckpt_dir = drive_ckpt_dir
        self.sync_step_interval = max(1, sync_step_interval)

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step > 0 and (state.global_step % self.sync_step_interval) == 0:
            copied, skipped = sync_tree_with_checksums(self.local_ckpt_dir, self.drive_ckpt_dir)
            print(f'[callback] periodic checkpoint sync: copied={copied} skipped={skipped}')
            gpu_gc(f'step-{state.global_step}')
        return control

    def on_save(self, args, state, control, **kwargs):
        copied, skipped = sync_tree_with_checksums(self.local_ckpt_dir, self.drive_ckpt_dir)
        print(f'[callback] on_save sync: copied={copied} skipped={skipped}')
        gpu_gc(f'on-save-{state.global_step}')
        return control

    def on_evaluate(self, args, state, control, **kwargs):
        gpu_gc(f'on-evaluate-{state.global_step}')
        return control


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


def build_training_args(cfg: ColabConfig, paths: Dict[str, Path]) -> Seq2SeqTrainingArguments:
    paths['local_trainer_dir'].mkdir(parents=True, exist_ok=True)
    return Seq2SeqTrainingArguments(
        output_dir=str(paths['local_trainer_dir']),
        per_device_train_batch_size=cfg.batch_size_train,
        per_device_eval_batch_size=cfg.batch_size_eval,
        gradient_accumulation_steps=cfg.grad_accum_steps,
        learning_rate=cfg.learning_rate,
        num_train_epochs=cfg.num_epochs,
        logging_steps=cfg.logging_steps,
        evaluation_strategy='steps',
        eval_steps=cfg.eval_steps,
        save_steps=cfg.save_steps,
        save_total_limit=cfg.save_total_limit,
        predict_with_generate=False,
        fp16=torch.cuda.is_available(),
        report_to='none',
        save_safetensors=True,
    )


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
            'io_strategy': 'datasets are copied from Drive to /content/data before training',
            'reliability': 'checkpoints are mirrored to Drive periodically and on save',
        },
    }
    ensure_parent_dir(paths['run_config_local'])
    paths['run_config_local'].write_text(json.dumps(run_config, indent=2), encoding='utf-8')
    ensure_parent_dir(paths['run_config_drive'])
    paths['run_config_drive'].write_text(json.dumps(run_config, indent=2), encoding='utf-8')

    stage_datasets_from_drive(paths)
    preflight_validate_local_splits(paths, cfg)
    gpu_gc('before-model-load')

    print('[model] loading tokenizer and base model...')
    tokenizer = AutoTokenizer.from_pretrained(cfg.model_id)
    base_model = AutoModelForSeq2SeqLM.from_pretrained(
        cfg.model_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
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

    def preprocess_batch(examples):
        tokenizer.src_lang = cfg.source_flores
        inputs = tokenizer(
            examples[cfg.source_column],
            max_length=cfg.max_length,
            truncation=True,
        )
        labels = tokenizer(
            text_target=examples[cfg.target_column],
            max_length=cfg.max_length,
            truncation=True,
        )
        inputs['labels'] = labels['input_ids']
        return inputs

    print('[data] tokenizing train/validation/test splits...')
    tokenized = dataset.map(
        preprocess_batch,
        batched=True,
        remove_columns=dataset['train'].column_names,
    )
    gpu_gc('after-tokenization')

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    training_args = build_training_args(cfg, paths)

    callback = ReliabilityCallback(
        local_ckpt_dir=paths['local_trainer_dir'],
        drive_ckpt_dir=paths['drive_trainer_dir'],
        sync_step_interval=cfg.drive_sync_step_interval,
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized['train'],
        eval_dataset=tokenized['validation'],
        data_collator=data_collator,
        tokenizer=tokenizer,
        callbacks=[callback],
    )

    # Background thread gives extra resilience in case runtime dies between save steps.
    stop_event = threading.Event()
    sync_thread = CheckpointMirrorThread(
        src_root=paths['local_trainer_dir'],
        dst_root=paths['drive_trainer_dir'],
        interval_sec=cfg.drive_sync_interval_sec,
        stop_event=stop_event,
    )
    sync_thread.start()

    metrics: Dict[str, Dict] = {}
    try:
        print('[train] starting LoRA fine-tuning...')
        train_result = trainer.train()
        metrics['train'] = train_result.metrics

        print('[eval] running holdout evaluation on test split...')
        test_metrics = trainer.evaluate(eval_dataset=tokenized['test'], metric_key_prefix='test')
        metrics['test'] = test_metrics

    finally:
        # Stop thread and run one final guaranteed checkpoint mirror.
        stop_event.set()
        sync_thread.join(timeout=5)
        copied, skipped = sync_tree_with_checksums(paths['local_trainer_dir'], paths['drive_trainer_dir'])
        print(f'[sync-final] checkpoints mirrored: copied={copied} skipped={skipped}')
        gpu_gc('after-train')

    print('[export] saving adapter artifacts...')
    paths['local_adapter_dir'].mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(paths['local_adapter_dir']))
    copied, skipped = sync_tree_with_checksums(paths['local_adapter_dir'], paths['drive_adapter_dir'])
    print(f'[export] adapter mirrored: copied={copied} skipped={skipped}')

    if paths['local_adapter_zip'].exists():
        paths['local_adapter_zip'].unlink()
    shutil.make_archive(
        base_name=str(paths['local_adapter_zip'].with_suffix('')),
        format='zip',
        root_dir=str(paths['local_adapter_dir']),
    )
    copy_file_with_checksum(paths['local_adapter_zip'], paths['drive_adapter_zip'])

    # Persist metrics on both local and Drive paths for reproducibility.
    ensure_parent_dir(paths['metrics_local'])
    paths['metrics_local'].write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    ensure_parent_dir(paths['metrics_drive'])
    paths['metrics_drive'].write_text(json.dumps(metrics, indent=2), encoding='utf-8')

    print('[done] Cloud training pipeline completed successfully.')
    print(f"[done] local output root: {paths['local_output_root']}")
    print(f"[done] drive output root: {paths['drive_output_root']}")


if __name__ == '__main__':
    main()
