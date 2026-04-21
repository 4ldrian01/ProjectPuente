# Project PUENTE - Kaggle Phase A Runbook (Spanish Only)

This runbook is dedicated to Spanish-to-English LoRA training on Kaggle.

## Fixed Contract

- Source language: Spanish (`es`, FLORES `spa_Latn`)
- Target language: English (`en`, FLORES `eng_Latn`)
- Strict split directory: `/kaggle/working/ProjectPuente/datasets/processed/80-10-10_split/04_spanish`
- Strict split files:
  - `LATEST_es_en_train.jsonl`
  - `LATEST_es_en_val.jsonl`
  - `LATEST_es_en_test.jsonl`
- Expected split sizes: `400 / 50 / 50` (total `500`)

## Quick Launch Cell (Spanish)

```python
import os
import subprocess
from pathlib import Path
from datetime import datetime

prj = Path('/kaggle/working/ProjectPuente')
os.chdir(prj)

env = os.environ.copy()
env.update({
    'PUENTE_PROJECT_ROOT': str(prj),
    'PUENTE_DRIVE_ROOT': str(prj),
    'PUENTE_SOURCE_FLORES': 'spa_Latn',
    'PUENTE_TARGET_FLORES': 'eng_Latn',
    'PUENTE_SOURCE_TRANSLATION_KEY': 'es',
    'PUENTE_TARGET_TRANSLATION_KEY': 'en',
    'PUENTE_DATASET_REL_DIR': 'datasets/processed/80-10-10_split/04_spanish',
    'PUENTE_TRAIN_FILENAME': 'LATEST_es_en_train.jsonl',
    'PUENTE_EVAL_FILENAME': 'LATEST_es_en_val.jsonl',
    'PUENTE_TEST_FILENAME': 'LATEST_es_en_test.jsonl',
    'PUENTE_RUN_NAME': 'lora-es-full-kaggle',
    'PUENTE_REQUIRE_GPU': 'true',
})

log_dir = prj / 'outputs' / env['PUENTE_RUN_NAME']
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"train_{datetime.now():%Y%m%d_%H%M%S}.log"

with open(log_file, 'w') as f:
    proc = subprocess.Popen(
        ['bash', 'notebooks/scripts/run_kaggle_phase_a_training.sh'],
        stdout=f,
        stderr=subprocess.STDOUT,
        env=env,
    )

print('Started PID =', proc.pid)
print('Log file   =', log_file)
```

## Emergency One-Pass (Cells 1-9, Spanish)

### Cell 1: Stop old jobs

```python
!pkill -f "run_kaggle_phase_a_training.sh" || true
!pkill -f "colab_lora_training_pipeline.py" || true
```

### Cell 2: Sync repository

```python
from pathlib import Path

if not Path('/kaggle/working/ProjectPuente/.git').exists():
    !git clone https://github.com/4ldrian01/ProjectPuente.git /kaggle/working/ProjectPuente

%cd /kaggle/working/ProjectPuente
!git fetch origin
!git checkout development
!git stash push -u -m "kaggle-pre-sync-$(date +%Y%m%d_%H%M%S)" || true
!git pull --ff-only origin development
!git log --oneline -n 3
```

### Cell 3: Runtime/GPU check

```python
import os
import torch

root = '/kaggle/working/ProjectPuente'
print('cwd =', os.getcwd())
for name in ['backend', 'frontend', 'datasets', 'notebooks']:
    p = os.path.join(root, name)
    print(p, 'exists =', os.path.isdir(p))

print('cuda_available =', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu_count =', torch.cuda.device_count())
    print('active_gpu =', torch.cuda.get_device_name(0))
```

### Cell 4: HF token check

```python
from pathlib import Path
import os

prj = Path('/kaggle/working/ProjectPuente')
token_path = prj / '.secrets' / 'hf_token'
token_path.parent.mkdir(parents=True, exist_ok=True)
os.chmod(token_path.parent, 0o700)

if not token_path.exists() or token_path.read_text().strip() in {'', 'hf_your_token_here'}:
    print('HF token is missing or placeholder. Put your real token in this file:')
    print(token_path)
else:
    os.chmod(token_path, 0o600)
    print('HF token ready:', token_path)
```

### Cell 5: Strict Spanish split validation (500 total)

```python
from pathlib import Path
import json

prj = Path('/kaggle/working/ProjectPuente')
src = prj / 'datasets/processed/80-10-10_split/04_spanish'
files = [
    src / 'LATEST_es_en_train.jsonl',
    src / 'LATEST_es_en_val.jsonl',
    src / 'LATEST_es_en_test.jsonl',
]

def norm(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip()

def valid(rec):
    if not isinstance(rec, dict):
        return False
    t = rec.get('translation')
    if isinstance(t, dict) and norm(t.get('es'), t.get('en')):
        return True
    if norm(rec.get('source_text'), rec.get('target_text')):
        return True
    if norm(rec.get('source'), rec.get('target')):
        return True
    if norm(rec.get('es'), rec.get('en')):
        return True
    return False

for p in files:
    if not p.exists():
        raise FileNotFoundError(f'Missing required strict split file: {p}')

row_counts = {}
for p in files:
    total = bad = 0
    first_bad = None
    with p.open('r', encoding='utf-8') as h:
        for i, line in enumerate(h, 1):
            s = line.strip()
            if not s:
                continue
            total += 1
            try:
                rec = json.loads(s)
            except Exception as e:
                bad += 1
                if first_bad is None:
                    first_bad = (i, f'json decode error: {e}')
                continue
            if not valid(rec):
                bad += 1
                if first_bad is None:
                    first_bad = (i, str(rec)[:240])

    row_counts[p.name] = total
    print(p.name, 'total=', total, 'bad=', bad)
    if first_bad:
        print('  first_bad_line=', first_bad[0])
        print('  sample=', first_bad[1])
    if bad > 0:
        raise RuntimeError(f'Strict LATEST validation failed for {p.name}.')

expected = {
    'LATEST_es_en_train.jsonl': 400,
    'LATEST_es_en_val.jsonl': 50,
    'LATEST_es_en_test.jsonl': 50,
}
for name, want in expected.items():
    got = row_counts.get(name, -1)
    if got != want:
        raise RuntimeError(f'Unexpected split size for {name}: expected {want}, got {got}')

if sum(row_counts.values()) != 500:
    raise RuntimeError(f"Unexpected total rows: {sum(row_counts.values())} (expected 500)")

print('Strict LATEST Spanish validation passed (500 rows total).')
```

### Cell 6: Clear caches

```python
!rm -rf /kaggle/working/ProjectPuente/.cache/huggingface/datasets
!rm -f /kaggle/working/data/*.jsonl || true
```

### Cell 7: Launch deterministic Spanish rerun

```python
import os
import subprocess
from pathlib import Path
from datetime import datetime

prj = Path('/kaggle/working/ProjectPuente')
os.chdir(prj)

run_name = f"lora-es-latest-rerun-{datetime.now():%Y%m%d_%H%M%S}"
log_dir = prj / 'outputs' / run_name
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"train_{datetime.now():%Y%m%d_%H%M%S}.log"

env = os.environ.copy()
env.update({
    'PUENTE_PROJECT_ROOT': str(prj),
    'PUENTE_DRIVE_ROOT': str(prj),
    'PUENTE_SOURCE_FLORES': 'spa_Latn',
    'PUENTE_TARGET_FLORES': 'eng_Latn',
    'PUENTE_SOURCE_TRANSLATION_KEY': 'es',
    'PUENTE_TARGET_TRANSLATION_KEY': 'en',
    'PUENTE_DATASET_REL_DIR': 'datasets/processed/80-10-10_split/04_spanish',
    'PUENTE_TRAIN_FILENAME': 'LATEST_es_en_train.jsonl',
    'PUENTE_EVAL_FILENAME': 'LATEST_es_en_val.jsonl',
    'PUENTE_TEST_FILENAME': 'LATEST_es_en_test.jsonl',
    'PUENTE_RUN_NAME': run_name,
    'PUENTE_REQUIRE_GPU': 'true',
    'HF_DATASETS_CACHE': str(prj / '.cache' / 'huggingface' / f"datasets_{datetime.now():%Y%m%d_%H%M%S}"),
})

with open(log_file, 'w') as f:
    proc = subprocess.Popen(
        ['bash', 'notebooks/scripts/run_kaggle_phase_a_training.sh'],
        stdout=f,
        stderr=subprocess.STDOUT,
        env=env,
    )

print('Started PID =', proc.pid)
print('Run name    =', run_name)
print('Log file    =', log_file)
```

### Cell 8: Non-blocking monitor

```python
!ps -p {proc.pid} -o pid,stat,etime,cmd
!tail -n 160 {log_file}
!grep -n "\[runtime\]\|\[data\]\|\[train\]\|\[eval\]\|\[done\]\|ERROR\|Traceback\|ValueError" {log_file} | tail -n 80
```

### Cell 9: Artifact checks

```python
from pathlib import Path
import re
import subprocess

prj = Path('/kaggle/working/ProjectPuente')
status = subprocess.run(
    ['ps', '-p', str(proc.pid), '-o', 'stat='],
    capture_output=True,
    text=True,
)

proc_stat = status.stdout.strip()
proc_alive = bool(proc_stat) and not proc_stat.startswith('Z')
log_path = Path(log_file)
done_marker = '[done] Cloud training pipeline completed successfully.'
traceback_marker = 'Traceback (most recent call last):'
log_text = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''

run_name_from_log = ''
source_root_match = re.search(
    r'\[done\]\s+source output root:\s+/kaggle/working/ProjectPuente/outputs/([^\s/]+)',
    log_text,
)
if source_root_match:
    run_name_from_log = source_root_match.group(1)

run_name_from_logfile = log_path.parent.name if log_path.parent.name.startswith('lora-') else ''
active_run_name = run_name_from_log or run_name_from_logfile

if not active_run_name:
    latest_output_dirs = sorted(
        (prj / 'outputs').glob('lora-*'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if latest_output_dirs:
        active_run_name = latest_output_dirs[0].name

print('resolved_run_name =', active_run_name or '(unresolved)')
print('log_exists =', log_path.exists())
print('done_marker_found =', done_marker in log_text)
print('traceback_found =', traceback_marker in log_text)

if proc_alive:
    print('Training still running; artifact files may still be MISSING at this moment.')
    print('Wait, then re-run Cell 8 and Cell 9.')
elif done_marker in log_text:
    print('Training completed successfully ([done] marker found in log).')
elif proc_stat.startswith('Z'):
    print('Training process is defunct (zombie): run has exited without a completion marker.')
    print('Inspect Cell 8 output for Traceback/ERROR details.')
else:
    print('Training process is not running. Check artifact status below and inspect log for [done] or Traceback.')

checks = {
    'checkpoints_dir': prj / 'models' / 'checkpoints' / active_run_name,
    'adapter_dir': prj / 'models' / 'lora_adapters' / active_run_name,
    'metrics_json': prj / 'outputs' / active_run_name / 'training_metrics.json',
    'run_config_json': prj / 'outputs' / active_run_name / 'run_config.json',
}
for key, path in checks.items():
    print(key, '->', 'OK' if path.exists() else 'MISSING', '->', path)
```