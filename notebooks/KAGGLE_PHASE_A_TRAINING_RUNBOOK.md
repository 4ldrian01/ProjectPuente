# Project PUENTE - Phase A Kaggle Training Runbook

Use this runbook when Colab GPU quota is exhausted and you need to continue training on Kaggle.

## Scope

- Runtime: Kaggle notebook with GPU accelerator enabled
- Project path: `/kaggle/working/ProjectPuente` (recommended)
- Launcher: `notebooks/scripts/run_kaggle_phase_a_training.sh`
- Pipeline: `notebooks/scripts/colab_lora_training_pipeline.py` (runtime-aware)
- Runtime deps file: `notebooks/scripts/requirements_colab.txt`

## Read This First (Prevents Syntax Errors)

Kaggle code cells are Python by default.

- If you paste shell lines like `git clone ...` directly, Python raises syntax errors.
- If you paste markdown fence lines like ```bash or ```, Python raises syntax errors.

Rules:

1. For Python code cells, use commands prefixed with `!` and `%cd`.
2. For shell script style, use `%%bash` as the first line of the cell.
3. Never paste markdown fence lines into notebook code cells.
4. If your first pasted line starts with ``` (three backticks), stop and delete that line.
5. If copying from raw markdown source, copy only lines inside code blocks or use Markdown Preview's copy button.

This runbook defaults to Python-cell-safe commands to avoid regression.

## Runtime Python Dependencies (Auto-Installed)

The launcher installs these packages before training:

- `torch`
- `transformers`
- `datasets`
- `peft`
- `accelerate`
- `sentencepiece`
- `safetensors`

## 1) Prepare Kaggle Notebook Environment

1. Create a new Kaggle notebook.
2. In notebook settings, open `Settings` (right sidebar) and set:
    - `Accelerator`: `GPU T4 x2`
    - `Internet`: On (required for repo clone and model download)
3. Click `Turn on GPU T4 x2` and wait until the runtime reconnects.
4. Verify status at the top-right runtime indicator shows GPU enabled.
5. Run the following in a Kaggle Python code cell (safe for default notebook mode):

```python
!git clone https://github.com/4ldrian01/ProjectPuente.git /kaggle/working/ProjectPuente
%cd /kaggle/working/ProjectPuente
!git checkout development
!git pull --ff-only origin development
```

If clone says destination already exists, run this instead:

```python
%cd /kaggle/working/ProjectPuente
!git fetch origin
!git checkout development
!git pull --ff-only origin development
```

## 2) Validate Runtime and Dataset Layout

Ensure project root contains expected folders:

- `backend/`
- `frontend/`
- `datasets/`
- `notebooks/`

Run this Python cell to verify required directories:

```python
import os
root = '/kaggle/working/ProjectPuente'
required = ['backend', 'frontend', 'datasets', 'notebooks']
missing = [d for d in required if not os.path.isdir(os.path.join(root, d))]
print('project_root =', root)
if missing:
    raise RuntimeError(f'Missing required directories: {missing}')
print('OK: required directories found')
```

Check split files (recommended LATEST naming):

Exact replacement for your previously failing snippet (Python-cell safe):

```python
!ls -lah /kaggle/working/ProjectPuente/datasets/processed/80-10-10_split/01_chavacano/LATEST_cbk_en_train.jsonl /kaggle/working/ProjectPuente/datasets/processed/80-10-10_split/01_chavacano/LATEST_cbk_en_val.jsonl /kaggle/working/ProjectPuente/datasets/processed/80-10-10_split/01_chavacano/LATEST_cbk_en_test.jsonl
```

Equivalent robust Python check:

```python
from pathlib import Path

prj = Path('/kaggle/working/ProjectPuente')
base = prj / 'datasets/processed/80-10-10_split/01_chavacano'
checks = [
    base / 'LATEST_cbk_en_train.jsonl',
    base / 'LATEST_cbk_en_val.jsonl',
    base / 'LATEST_cbk_en_test.jsonl',
]

for p in checks:
    print(p, '->', 'OK' if p.exists() else 'MISSING')
```

The launcher auto-detects split filename triplets inside the selected dataset directory (LATEST-first):

- `LATEST_cbk_en_train.jsonl`, `LATEST_cbk_en_val.jsonl`, `LATEST_cbk_en_test.jsonl`
- `LATEST_ceb_en_train.jsonl`, `LATEST_ceb_en_val.jsonl`, `LATEST_ceb_en_test.jsonl`
- `FINAL_cbk_en_train.jsonl`, `FINAL_cbk_en_val.jsonl`, `FINAL_cbk_en_test.jsonl`
- `FINAL_ceb_en_train.jsonl`, `FINAL_ceb_en_val.jsonl`, `FINAL_ceb_en_test.jsonl`
- `cbk_en_train.jsonl`, `cbk_en_val.jsonl`, `cbk_en_test.jsonl`
- `ceb_en_train.jsonl`, `ceb_en_val.jsonl`, `ceb_en_test.jsonl`
- `train.jsonl`, `eval.jsonl`, `test.jsonl`
- `cbk_en_trial_train.jsonl`, `cbk_en_trial_val.jsonl`, `cbk_en_trial_test.jsonl`

Confirm CUDA before starting training:

```python
import torch, sys
print('cuda_available =', torch.cuda.is_available())
if not torch.cuda.is_available():
    print('ERROR: GPU not active. Re-open Kaggle Settings and re-enable Accelerator: GPU T4 x2.')
    sys.exit(1)
print('gpu_count =', torch.cuda.device_count())
print('active_gpu =', torch.cuda.get_device_name(0))
```

## 3) Optional HF Token Setup

What this token is:

- `HF token` means your Hugging Face access token (starts with `hf_...`).
- It is used so model downloads are authenticated and less likely to hit rate limits.
- For this project, a `Read` token is enough.

How to create it (one-time, in browser):

1. Sign in to Hugging Face.
2. Open `Settings -> Access Tokens`.
3. Create a new token with role `Read`.
4. Copy the token value (you may only see it once).

Recommended in Kaggle (safer): use Kaggle Secrets

1. In Kaggle notebook, open `Add-ons -> Secrets`.
2. Create secret name `HF_TOKEN` and paste your token value.
3. Run this cell:

```python
from kaggle_secrets import UserSecretsClient
from pathlib import Path
import os

token = UserSecretsClient().get_secret('HF_TOKEN').strip()
if not token.startswith('hf_'):
    raise RuntimeError('HF_TOKEN secret looks invalid. It should start with hf_.')

prj = Path('/kaggle/working/ProjectPuente')
secrets_dir = prj / '.secrets'
secrets_dir.mkdir(parents=True, exist_ok=True)
os.chmod(secrets_dir, 0o700)

token_file = secrets_dir / 'hf_token'
token_file.write_text(token + '\n')
os.chmod(token_file, 0o600)

print('HF token file ready:', token_file)
```

Direct file method (simpler, less secure in shared notebooks):

```python
from pathlib import Path
import os

prj = Path('/kaggle/working/ProjectPuente')
secrets_dir = prj / '.secrets'
secrets_dir.mkdir(parents=True, exist_ok=True)
os.chmod(secrets_dir, 0o700)

token_file = secrets_dir / 'hf_token'
token_file.write_text('hf_your_token_here\n')
os.chmod(token_file, 0o600)

print('Wrote token file:', token_file)
```

Verify token file quickly:

```python
from pathlib import Path

p = Path('/kaggle/working/ProjectPuente/.secrets/hf_token')
print('exists =', p.exists())
if p.exists():
    t = p.read_text().strip()
    print('starts_with_hf =', t.startswith('hf_'))
    print('length =', len(t))
```

## 4) Launch Training (Recommended)

Run this Python cell to launch training and print live log paths:

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
    'PUENTE_SOURCE_FLORES': 'cbk_Latn',
    'PUENTE_TARGET_FLORES': 'eng_Latn',
    'PUENTE_SOURCE_TRANSLATION_KEY': 'cbk',
    'PUENTE_TARGET_TRANSLATION_KEY': 'en',
    'PUENTE_DATASET_REL_DIR': 'datasets/processed/80-10-10_split/01_chavacano',
    'PUENTE_TRAIN_FILENAME': 'LATEST_cbk_en_train.jsonl',
    'PUENTE_EVAL_FILENAME': 'LATEST_cbk_en_val.jsonl',
    'PUENTE_TEST_FILENAME': 'LATEST_cbk_en_test.jsonl',
    'PUENTE_RUN_NAME': 'lora-cbk-full-kaggle',
    'PUENTE_REQUIRE_GPU': 'true',
})

# Optional resume:
# env['PUENTE_RESUME_FROM_CHECKPOINT'] = str(prj / 'models/checkpoints/lora-cbk-full-kaggle/checkpoint-500')

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
print('Tail logs with:')
print(f"!tail -f {log_file}")
```

Quick smoke-run before full training (recommended to avoid burning GPU hours on config mistakes):

```python
# Use these two env values in the launch cell above for smoke-run:
# env['PUENTE_DATASET_REL_DIR'] = 'datasets/processed/80-10-10_split/01_chavacano/trial_small'
# env['PUENTE_RUN_NAME'] = 'lora-cbk-trial-kaggle'
```

The launcher will auto-detect `cbk_en_trial_*` split filenames in `trial_small`.

## 5) After Launch: Monitor, Verify, and Finish

You already launched successfully if you saw:

- `Started PID = ...`
- `Log file = ...`

Now run the following steps.

### 5.1 Monitor the live training log

Use the exact command printed by the launch cell:

```python
!tail -f /kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/train_YYYYMMDD_HHMMSS.log
```

Replace `train_YYYYMMDD_HHMMSS.log` with your real filename.

Important notebook behavior:

- `tail -f` never exits on its own. It keeps streaming and holds the kernel busy.
- While that cell is running, later cells can appear stuck on `In [*]`.
- Use the notebook Stop/Interrupt button when you are done watching live logs.

Non-blocking alternatives (recommended for quick checks):

```python
!tail -n 120 /kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/train_YYYYMMDD_HHMMSS.log
!grep -n "\[done\]\|ERROR\|Traceback\|ValueError" /kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/train_YYYYMMDD_HHMMSS.log | tail -n 40
```

Expected progress markers from the pipeline include:

- `[runtime] detected runtime: kaggle`
- `[gpu] CUDA available ...`
- `[data] Using dataset splits from ...`
- `[model] loading tokenizer and base model...`
- `[train] starting LoRA fine-tuning...`
- `[eval] running holdout evaluation on test split...`
- `[done] Cloud training pipeline completed successfully.`

### 5.2 Check whether process is still running

```python
!ps -p 170 -o pid,etime,cmd
```

Replace `170` with your actual PID.

- If a row is returned, training is still running.
- If no row is returned, training has ended (success or failure). Check the final log lines.

### 5.3 Read final log lines after process exits

```python
!tail -n 120 /kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/train_YYYYMMDD_HHMMSS.log
```

Success is confirmed by this exact marker:

- `[done] Cloud training pipeline completed successfully.`

### 5.4 Verify output artifacts

Run this Python cell to verify expected outputs are present:

```python
from pathlib import Path

prj = Path('/kaggle/working/ProjectPuente')
run_name = 'lora-cbk-full-kaggle'

checks = {
    'checkpoints_dir': prj / 'models' / 'checkpoints' / run_name,
    'adapter_dir': prj / 'models' / 'lora_adapters' / run_name,
    'metrics_json': prj / 'outputs' / run_name / 'training_metrics.json',
    'run_config_json': prj / 'outputs' / run_name / 'run_config.json',
}

for name, path in checks.items():
    print(name, '->', path, '->', 'OK' if path.exists() else 'MISSING')
```

### 5.5 Inspect metrics

```python
import json
from pathlib import Path

metrics_path = Path('/kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/training_metrics.json')
if metrics_path.exists():
    data = json.loads(metrics_path.read_text())
    print('Top-level keys:', list(data.keys()))
    print('Train metrics keys:', list(data.get('train', {}).keys()))
    print('Test metrics keys:', list(data.get('test', {}).keys()))
else:
    print('Metrics file not found:', metrics_path)
```

### 5.6 If the run fails, use this quick recovery table

- `ERROR: Missing split file`: set `PUENTE_DATASET_REL_DIR` and/or split filenames to the directory that contains your JSONL files, then relaunch.
- `GPU is required but CUDA is not available`: re-enable Kaggle GPU, reconnect runtime, rerun from Step 2 CUDA check.
- `PUENTE_TARGET_TRANSLATION_KEY must be en`: keep `PUENTE_TARGET_TRANSLATION_KEY='en'` for this Phase A source-to-English pipeline.
- `HF token not detected` or download/rate-limit issues: recreate `.secrets/hf_token`, then relaunch.
- `TypeError: Seq2SeqTrainingArguments.__init__() got an unexpected keyword argument 'save_safetensors'`: first sync latest repo with Section 9 Cell 2 and relaunch from Section 9 Cell 7; if it still fails, run Section 9 Cell 6b then relaunch.
- `TypeError: Seq2SeqTrainer.__init__() got an unexpected keyword argument 'tokenizer'`: first sync latest repo with Section 9 Cell 2 and relaunch from Section 9 Cell 7; if it still fails, run Section 9 Cell 6b then relaunch.
- OOM during training: lower `PUENTE_BATCH_SIZE_TRAIN` and/or increase `PUENTE_GRAD_ACCUM_STEPS`, then relaunch.

### 5.7 Resume from a checkpoint (optional)

In the launch cell, uncomment and set:

```python
# env['PUENTE_RESUME_FROM_CHECKPOINT'] = str(prj / 'models/checkpoints/<run_name>/checkpoint-<step>')
```

Then rerun the launch cell.

### 5.8 Deterministic rerun for `Invalid translation payload`

If training crashes with `ValueError: Invalid translation payload` at tokenization time, run this exact sequence:

```python
# 1) Stop live tail cells first (Notebook Interrupt button), then check process status.
!ps -p 169 -o pid,etime,cmd
```

```python
# 2) Clear Hugging Face datasets cache used by this project runtime.
!rm -rf /kaggle/working/ProjectPuente/.cache/huggingface/datasets
```

```python
# 3) Relaunch with an isolated cache path and explicit split filenames.
import os
import subprocess
from pathlib import Path
from datetime import datetime

prj = Path('/kaggle/working/ProjectPuente')
os.chdir(prj)

run_name = f"lora-cbk-full-kaggle-rerun-{datetime.now():%Y%m%d_%H%M%S}"
log_dir = prj / 'outputs' / run_name
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"train_{datetime.now():%Y%m%d_%H%M%S}.log"

env = os.environ.copy()
env.update({
    'PUENTE_PROJECT_ROOT': str(prj),
    'PUENTE_DRIVE_ROOT': str(prj),
    'PUENTE_SOURCE_FLORES': 'cbk_Latn',
    'PUENTE_TARGET_FLORES': 'eng_Latn',
    'PUENTE_SOURCE_TRANSLATION_KEY': 'cbk',
    'PUENTE_TARGET_TRANSLATION_KEY': 'en',
    'PUENTE_DATASET_REL_DIR': 'datasets/processed/80-10-10_split/01_chavacano',
    'PUENTE_TRAIN_FILENAME': 'LATEST_cbk_en_train.jsonl',
    'PUENTE_EVAL_FILENAME': 'LATEST_cbk_en_val.jsonl',
    'PUENTE_TEST_FILENAME': 'LATEST_cbk_en_test.jsonl',
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

```python
# 4) Non-blocking health check.
!ps -p {proc.pid} -o pid,etime,cmd
!tail -n 160 {log_file}
!grep -n "\[runtime\]\|\[data\]\|\[train\]\|\[eval\]\|\[done\]\|ERROR\|Traceback\|ValueError" {log_file} | tail -n 80
```

## 6) Copy-Paste Safe Mini Checklist

Run these cells in order:

1. Step 1 clone/update cell
2. Step 2 directory verification cell
3. Step 2 split-file check cell
4. Step 2 CUDA check cell
5. Step 4 launch cell
6. Tail logs command printed by Step 4

If any step fails, fix that step first and do not continue.

## 7) Output Locations

- Checkpoints: `<project_root>/models/checkpoints/<run_name>/`
- Final adapter: `<project_root>/models/lora_adapters/<run_name>/`
- Metrics and config: `<project_root>/outputs/<run_name>/`

## 8) Troubleshooting

- If GPU check fails, re-open notebook settings and confirm Accelerator is GPU.
- If split files are missing, set `PUENTE_DATASET_REL_DIR` to the exact split directory.
- If HF rate limits occur, set token at `.secrets/hf_token`.
- If notebook session restarts, rerun launch block and follow latest log file.
- If you need reproducible persistence, click `Save Version` in Kaggle to capture notebook outputs under `/kaggle/working`.
- If you see `SyntaxError` on a line starting with ```bash or ```, remove that line and re-run the cell.
- If shell commands fail in a Python cell, add `!` before each shell command or use `%%bash`.
- If `ps -p <pid>` shows only the header row, that process is no longer running.
- If `git pull` aborts with `Your local changes ... would be overwritten by merge`, rerun Section 9 Cell 2. It auto-stashes local edits (including prior hotfix edits) before pulling latest `origin/development`.
- If `tail` or `grep` says log file does not exist, use a dynamic log lookup first:

```python
from pathlib import Path

logs = sorted(Path('/kaggle/working/ProjectPuente/outputs').glob('**/train_*.log'))
print('log_count =', len(logs))
for p in logs[-10:]:
    print(p)
```

- If your expected split files are missing, do not continue training until you discover available dataset directories and filenames:

```python
from pathlib import Path

root = Path('/kaggle/working/ProjectPuente/datasets/processed')
if not root.exists():
    print('MISSING:', root)
else:
    cands = sorted(root.glob('**/*train*.jsonl'))
    print('candidate_train_files =', len(cands))
    for p in cands[:200]:
        print(p)
```

- For robust relaunch when filename variants changed, use the launch cell without pinning `PUENTE_DATASET_REL_DIR` or `PUENTE_*_FILENAME`; the Kaggle launcher will auto-detect known split triplets.
- If you see `ValueError: Invalid translation payload...` during tokenization:
  1. Stop any active `tail -f` cell using notebook Interrupt/Stop.
  2. Run a non-blocking check first:

```python
!tail -n 200 /kaggle/working/ProjectPuente/outputs/lora-cbk-full-kaggle/train_YYYYMMDD_HHMMSS.log
```

  3. Validate both source JSONL and staged local JSONL schema:

```python
from pathlib import Path
import json

files = [
    'LATEST_cbk_en_train.jsonl',
    'LATEST_cbk_en_val.jsonl',
    'LATEST_cbk_en_test.jsonl',
]

roots = [
    Path('/kaggle/working/ProjectPuente/datasets/processed/80-10-10_split/01_chavacano'),
    Path('/kaggle/working/data'),
]

def norm(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip()

def valid(rec):
    if not isinstance(rec, dict):
        return False
    t = rec.get('translation')
    if isinstance(t, dict) and norm(t.get('cbk'), t.get('en')):
        return True
    if norm(rec.get('source_text'), rec.get('target_text')):
        return True
    if norm(rec.get('source'), rec.get('target')):
        return True
    if norm(rec.get('cbk'), rec.get('en')):
        return True
    return False

for root in roots:
    print('\nROOT:', root)
    for fn in files:
        p = root / fn
        if not p.exists():
            print(fn, '-> MISSING')
            continue
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
        print(f'{fn} -> total={total}, bad={bad}')
        if first_bad:
            print('  first_bad_line=', first_bad[0])
            print('  sample=', first_bad[1])
```

  4. If `bad > 0`, clean or regenerate dataset files and relaunch.
  5. If `bad == 0` but the same error persists, clear dataset cache and relaunch:

```python
!rm -rf /kaggle/working/ProjectPuente/.cache/huggingface/datasets
```

## 9) Emergency One-Pass (After Hard Refresh)

Use this section if you want one strict top-to-bottom sequence with no branching.

Policy for this section:

- Use only these split files for cbk:
    - `LATEST_cbk_en_train.jsonl`
    - `LATEST_cbk_en_val.jsonl`
    - `LATEST_cbk_en_test.jsonl`
- Do not switch to `cleaned_cbk_en` in this strict path unless you intentionally choose fallback troubleshooting.

### Cell 1: Stop old background jobs

```python
!pkill -f "run_kaggle_phase_a_training.sh" || true
!pkill -f "colab_lora_training_pipeline.py" || true
```

### Cell 2: Sync repository to development

```python
from pathlib import Path
import subprocess
from datetime import datetime

if not Path('/kaggle/working/ProjectPuente/.git').exists():
    !git clone https://github.com/4ldrian01/ProjectPuente.git /kaggle/working/ProjectPuente

%cd /kaggle/working/ProjectPuente
!git fetch origin
!git checkout development

status = subprocess.run(
    ['git', 'status', '--porcelain'],
    capture_output=True,
    text=True,
    check=False,
)

if status.stdout.strip():
    stash_name = f"kaggle-pre-sync-{datetime.now():%Y%m%d_%H%M%S}"
    print('Local changes detected; stashing before pull:', stash_name)
    subprocess.run(['git', 'stash', 'push', '-u', '-m', stash_name], check=True)
else:
    print('Working tree clean; no stash needed.')

!git pull --ff-only origin development
```

### Cell 3: Verify runtime readiness

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

### Cell 4: Ensure HF token is available

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

### Cell 5: Strict LATEST split validation (no cleaned fallback)

```python
from pathlib import Path
import json

prj = Path('/kaggle/working/ProjectPuente')
src = prj / 'datasets/processed/80-10-10_split/01_chavacano'
files = [
    src / 'LATEST_cbk_en_train.jsonl',
    src / 'LATEST_cbk_en_val.jsonl',
    src / 'LATEST_cbk_en_test.jsonl',
]

def norm(a, b):
    return isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip()

def valid(rec):
    if not isinstance(rec, dict):
        return False
    t = rec.get('translation')
    if isinstance(t, dict) and norm(t.get('cbk'), t.get('en')):
        return True
    if norm(rec.get('source_text'), rec.get('target_text')):
        return True
    if norm(rec.get('source'), rec.get('target')):
        return True
    if norm(rec.get('cbk'), rec.get('en')):
        return True
    return False

for p in files:
    if not p.exists():
        raise FileNotFoundError(f'Missing required strict split file: {p}')

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

    print(p.name, 'total=', total, 'bad=', bad)
    if first_bad:
        print('  first_bad_line=', first_bad[0])
        print('  sample=', first_bad[1])
    if bad > 0:
        raise RuntimeError(f'Strict LATEST validation failed for {p.name}. Fix source data before launch.')

print('Strict LATEST validation passed.')
```

### Cell 6: Clear caches and staged runtime files

```python
!rm -rf /kaggle/working/ProjectPuente/.cache/huggingface/datasets
!rm -f /kaggle/working/data/*.jsonl || true
```

### Cell 6b: Apply pipeline hotfix in Kaggle clone (fallback only)

Why this is needed:

- Use this only if you still hit known failures after syncing latest `origin/development`.
- On current `development`, these fixes are already included upstream for most runs.
- This hotfix edits tracked files in your Kaggle clone; future pulls can fail until changes are stashed/cleaned.

```python
from pathlib import Path

pipeline = Path('/kaggle/working/ProjectPuente/notebooks/scripts/colab_lora_training_pipeline.py')
text = pipeline.read_text(encoding='utf-8')

# 1) Force fresh filtering (no stale cache usage)
text = text.replace(
    'sanitized = dataset.filter(is_valid_record)',
    'sanitized = dataset.filter(is_valid_record, load_from_cache_file=False)'
)

# 2) Add residual invalid-row guard if missing
if 'Residual malformed rows detected after sanitization' not in text:
    needle = (
        "    if dropped_total > 0:\n"
        "        print('[data] Sanitization removed malformed rows; training will proceed with valid records only.')\n"
        "\n"
        "    return sanitized\n"
    )
    replacement = (
        "    if dropped_total > 0:\n"
        "        print('[data] Sanitization removed malformed rows; training will proceed with valid records only.')\n"
        "\n"
        "    residual_invalid = sanitized.filter(\n"
        "        lambda example: _extract_source_target_text(example, cfg) is None,\n"
        "        load_from_cache_file=False,\n"
        "    )\n"
        "    residual_counts = {split: len(residual_invalid[split]) for split in split_names}\n"
        "    if any(count > 0 for count in residual_counts.values()):\n"
        "        raise ValueError(\n"
        "            'Residual malformed rows detected after sanitization. '\n"
        "            f'Counts={residual_counts}. Clear dataset cache and verify JSONL schema.'\n"
        "        )\n"
        "\n"
        "    return sanitized\n"
    )
    if needle not in text:
        raise RuntimeError('Could not find expected sanitize block in pipeline; upstream layout changed.')
    text = text.replace(needle, replacement)

# 3) Replace preprocess_function with resilient preprocess_batch if needed
if 'def preprocess_batch(batch):' not in text:
    start = text.find('    def preprocess_function(example):')
    end_marker = "    print('[data] tokenizing train/validation/test splits...')\n"
    end = text.find(end_marker)
    if start == -1 or end == -1:
        raise RuntimeError('Could not find preprocess function block; upstream layout changed.')

    preprocess_replacement = (
        "    preprocess_stats = {'dropped_invalid': 0}\n"
        "\n"
        "    def preprocess_batch(batch):\n"
        "        tokenizer.src_lang = cfg.source_flores\n"
        "        tokenizer.tgt_lang = cfg.target_flores\n"
        "\n"
        "        if not batch:\n"
        "            return {'input_ids': [], 'attention_mask': [], 'labels': []}\n"
        "\n"
        "        first_key = next(iter(batch.keys()), None)\n"
        "        if first_key is None:\n"
        "            return {'input_ids': [], 'attention_mask': [], 'labels': []}\n"
        "\n"
        "        batch_size = len(batch[first_key])\n"
        "        source_texts = []\n"
        "        target_texts = []\n"
        "\n"
        "        for row_idx in range(batch_size):\n"
        "            record = {key: values[row_idx] for key, values in batch.items()}\n"
        "            extracted_pair = _extract_source_target_text(record, cfg)\n"
        "            if extracted_pair is None:\n"
        "                preprocess_stats['dropped_invalid'] += 1\n"
        "                continue\n"
        "\n"
        "            source_text, target_text = extracted_pair\n"
        "            source_texts.append(source_text)\n"
        "            target_texts.append(target_text)\n"
        "\n"
        "        if not source_texts:\n"
        "            return {'input_ids': [], 'attention_mask': [], 'labels': []}\n"
        "\n"
        "        inputs = tokenizer(\n"
        "            source_texts,\n"
        "            max_length=cfg.max_length,\n"
        "            truncation=True,\n"
        "        )\n"
        "        labels = tokenizer(\n"
        "            text_target=target_texts,\n"
        "            max_length=cfg.max_length,\n"
        "            truncation=True,\n"
        "        )\n"
        "        inputs['labels'] = labels['input_ids']\n"
        "        return inputs\n"
        "\n"
    )

    text = text[:start] + preprocess_replacement + text[end:]

# 4) Ensure map call uses preprocess_batch + batched mode + no cache
old_map = (
    "    tokenized_datasets = dataset.map(\n"
    "        preprocess_function,\n"
    "        remove_columns=dataset['train'].column_names,\n"
    "    )\n"
)
new_map = (
    "    tokenized_datasets = dataset.map(\n"
    "        preprocess_batch,\n"
    "        batched=True,\n"
    "        load_from_cache_file=False,\n"
    "        remove_columns=dataset['train'].column_names,\n"
    "    )\n"
    "\n"
    "    if preprocess_stats['dropped_invalid'] > 0:\n"
    "        print(f\"[data] tokenization dropped residual malformed rows: {preprocess_stats['dropped_invalid']}\")\n"
    "\n"
    "    for split_name in ('train', 'validation', 'test'):\n"
    "        if len(tokenized_datasets[split_name]) == 0:\n"
    "            raise ValueError(\n"
    "                f'Tokenization produced an empty split: {split_name}. '\n"
    "                'Check source JSONL schema and tokenizer input extraction rules.'\n"
    "            )\n"
)

if old_map in text:
    text = text.replace(old_map, new_map)

# 5) Ensure tie-word warning is silenced when loading config (optional quality-of-life)
if "AutoConfig" not in text:
    text = text.replace(
        "    AutoModelForSeq2SeqLM,\n",
        "    AutoConfig,\n    AutoModelForSeq2SeqLM,\n",
    )

if "config = AutoConfig.from_pretrained(" not in text:
    anchor = "    print('[model] loading tokenizer and base model...')\n"
    inject = (
        "    print('[model] loading tokenizer and base model...')\n"
        "    config = AutoConfig.from_pretrained(\n"
        "        cfg.model_id,\n"
        "        **hf_auth_kwargs(AutoConfig.from_pretrained, hf_token),\n"
        "    )\n"
        "    if hasattr(config, 'tie_word_embeddings'):\n"
        "        config.tie_word_embeddings = False\n"
    )
    if anchor in text:
        text = text.replace(anchor, inject)

text = text.replace(
    "    base_model = load_model_with_dtype_fallback(\n"
    "        model_id=cfg.model_id,\n"
    "        dtype_value=torch.float16 if torch.cuda.is_available() else torch.float32,\n"
    "        auth_kwargs=hf_auth_kwargs(AutoModelForSeq2SeqLM.from_pretrained, hf_token),\n"
    "    )\n",
    "    base_model = load_model_with_dtype_fallback(\n"
    "        model_id=cfg.model_id,\n"
    "        dtype_value=torch.float16 if torch.cuda.is_available() else torch.float32,\n"
    "        auth_kwargs=hf_auth_kwargs(AutoModelForSeq2SeqLM.from_pretrained, hf_token),\n"
    "        config=config,\n"
    "    )\n",
)

text = text.replace(
    "def load_model_with_dtype_fallback(model_id: str, dtype_value, auth_kwargs: Dict[str, str]):\n",
    "def load_model_with_dtype_fallback(model_id: str, dtype_value, auth_kwargs: Dict[str, str], config=None):\n",
)

text = text.replace(
    "        return AutoModelForSeq2SeqLM.from_pretrained(\n"
    "            model_id,\n"
    "            **preferred_kwargs,\n"
    "            **auth_kwargs,\n"
    "        )\n",
    "        return AutoModelForSeq2SeqLM.from_pretrained(\n"
    "            model_id,\n"
    "            **preferred_kwargs,\n"
    "            config=config,\n"
    "            **auth_kwargs,\n"
    "        )\n",
)

text = text.replace(
    "        return AutoModelForSeq2SeqLM.from_pretrained(\n"
    "            model_id,\n"
    "            **fallback_kwargs,\n"
    "            **auth_kwargs,\n"
    "        )\n",
    "        return AutoModelForSeq2SeqLM.from_pretrained(\n"
    "            model_id,\n"
    "            **fallback_kwargs,\n"
    "            config=config,\n"
    "            **auth_kwargs,\n"
    "        )\n",
)

# 6) Make Seq2SeqTrainingArguments kwargs robust across transformers versions.
# transformers>=5 can reject save_safetensors and other legacy kwargs.
text = text.replace(
    "        'report_to': 'none',\n"
    "        'save_safetensors': True,\n",
    "        'report_to': 'none',\n",
)

if "Ignoring unsupported Seq2SeqTrainingArguments keys" not in text:
    old_training_args_block = (
        "    # Transformers changed this arg name across versions.\n"
        "    init_params = inspect.signature(Seq2SeqTrainingArguments.__init__).parameters\n"
        "    if 'evaluation_strategy' in init_params:\n"
        "        args_kwargs['evaluation_strategy'] = 'steps'\n"
        "    elif 'eval_strategy' in init_params:\n"
        "        args_kwargs['eval_strategy'] = 'steps'\n"
        "    else:\n"
        "        args_kwargs['do_eval'] = True\n"
        "\n"
        "    return Seq2SeqTrainingArguments(**args_kwargs)\n"
    )

    new_training_args_block = (
        "    # Transformers changed arg names across versions.\n"
        "    init_params = inspect.signature(Seq2SeqTrainingArguments.__init__).parameters\n"
        "    if 'evaluation_strategy' in init_params:\n"
        "        args_kwargs['evaluation_strategy'] = 'steps'\n"
        "    elif 'eval_strategy' in init_params:\n"
        "        args_kwargs['eval_strategy'] = 'steps'\n"
        "    else:\n"
        "        args_kwargs['do_eval'] = True\n"
        "\n"
        "    if 'save_safetensors' in init_params:\n"
        "        args_kwargs['save_safetensors'] = True\n"
        "\n"
        "    supported_kwargs = {\n"
        "        key: value for key, value in args_kwargs.items() if key in init_params\n"
        "    }\n"
        "    unsupported_keys = sorted(set(args_kwargs) - set(supported_kwargs))\n"
        "    if unsupported_keys:\n"
        "        print(\n"
        "            '[args] Ignoring unsupported Seq2SeqTrainingArguments keys for this '\n"
        "            f'transformers version: {\", \".join(unsupported_keys)}'\n"
        "        )\n"
        "\n"
        "    return Seq2SeqTrainingArguments(**supported_kwargs)\n"
    )

    if old_training_args_block in text:
        text = text.replace(old_training_args_block, new_training_args_block)

# 7) Make Seq2SeqTrainer init robust across transformers versions.
# transformers>=5 can reject tokenizer= and require processing_class=.
old_trainer_block = (
    "    trainer = Seq2SeqTrainer(\n"
    "        model=model,\n"
    "        args=training_args,\n"
    "        train_dataset=tokenized_datasets['train'],\n"
    "        eval_dataset=tokenized_datasets['validation'],\n"
    "        data_collator=data_collator,\n"
    "        tokenizer=tokenizer,\n"
    "    )\n"
)

new_trainer_block = (
    "    trainer_kwargs = {\n"
    "        'model': model,\n"
    "        'args': training_args,\n"
    "        'train_dataset': tokenized_datasets['train'],\n"
    "        'eval_dataset': tokenized_datasets['validation'],\n"
    "        'data_collator': data_collator,\n"
    "    }\n"
    "    trainer_init_params = inspect.signature(Seq2SeqTrainer.__init__).parameters\n"
    "    if 'tokenizer' in trainer_init_params:\n"
    "        trainer_kwargs['tokenizer'] = tokenizer\n"
    "    elif 'processing_class' in trainer_init_params:\n"
    "        trainer_kwargs['processing_class'] = tokenizer\n"
    "    else:\n"
    "        print('[trainer] No tokenizer/processing_class parameter detected; continuing without explicit processor.')\n"
    "\n"
    "    trainer = Seq2SeqTrainer(**trainer_kwargs)\n"
)

if old_trainer_block in text:
    text = text.replace(old_trainer_block, new_trainer_block)

pipeline.write_text(text, encoding='utf-8')
print('Pipeline hotfix applied:', pipeline)
```

### Cell 7: Launch deterministic rerun (strict LATEST files)

```python
import os
import subprocess
from pathlib import Path
from datetime import datetime

prj = Path('/kaggle/working/ProjectPuente')
os.chdir(prj)

run_name = f"lora-cbk-latest-rerun-{datetime.now():%Y%m%d_%H%M%S}"
log_dir = prj / 'outputs' / run_name
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"train_{datetime.now():%Y%m%d_%H%M%S}.log"

env = os.environ.copy()
env.update({
    'PUENTE_PROJECT_ROOT': str(prj),
    'PUENTE_DRIVE_ROOT': str(prj),
    'PUENTE_SOURCE_FLORES': 'cbk_Latn',
    'PUENTE_TARGET_FLORES': 'eng_Latn',
    'PUENTE_SOURCE_TRANSLATION_KEY': 'cbk',
    'PUENTE_TARGET_TRANSLATION_KEY': 'en',
    'PUENTE_DATASET_REL_DIR': 'datasets/processed/80-10-10_split/01_chavacano',
    'PUENTE_TRAIN_FILENAME': 'LATEST_cbk_en_train.jsonl',
    'PUENTE_EVAL_FILENAME': 'LATEST_cbk_en_val.jsonl',
    'PUENTE_TEST_FILENAME': 'LATEST_cbk_en_test.jsonl',
    'PUENTE_RUN_NAME': run_name,
    'PUENTE_REQUIRE_GPU': 'true',
    'HF_DATASETS_CACHE': str(prj / '.cache' / 'huggingface' / f"datasets_{datetime.now():%Y%m%d_%H%M%S}"),
})

token_path = prj / '.secrets' / 'hf_token'
if token_path.exists():
    token = token_path.read_text().strip()
    if token and token != 'hf_your_token_here':
        env['HF_TOKEN'] = token

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

### Cell 8: Non-blocking status monitor

```python
!ps -p {proc.pid} -o pid,stat,etime,cmd
!tail -n 160 {log_file}
!grep -n "\[runtime\]\|\[data\]\|\[train\]\|\[eval\]\|\[done\]\|ERROR\|Traceback\|ValueError" {log_file} | tail -n 80
```

### Cell 9: Final artifact check

```python
from pathlib import Path
import subprocess

prj = Path('/kaggle/working/ProjectPuente')
status = subprocess.run(
    ['ps', '-p', str(proc.pid), '-o', 'stat='],
    capture_output=True,
    text=True,
)

proc_stat = status.stdout.strip()
proc_alive = bool(proc_stat) and not proc_stat.startswith('Z')

if proc_alive:
    print('Training still running; artifact files may still be MISSING at this moment.')
    print('Wait, then re-run Cell 8 and Cell 9.')
elif proc_stat.startswith('Z'):
    print('Training process is defunct (zombie): run has already exited. Check Cell 8 log output for final status.')
else:
    print('Training process is not running. Check artifact status below and inspect log for [done] or Traceback.')

checks = {
    'checkpoints_dir': prj / 'models' / 'checkpoints' / run_name,
    'adapter_dir': prj / 'models' / 'lora_adapters' / run_name,
    'metrics_json': prj / 'outputs' / run_name / 'training_metrics.json',
    'run_config_json': prj / 'outputs' / run_name / 'run_config.json',
}
for key, path in checks.items():
    print(key, '->', 'OK' if path.exists() else 'MISSING', '->', path)
```
