# Notebooks Setup

The notebooks in this repository are Python notebooks used for validation, model checks, data prep, and LoRA experimentation.

## Notebook kernel base

| Dependency | Required | Purpose |
|---|---:|---|
| Python | 3.12.x | Matches the workspace virtual environment |
| `jupyterlab` | Yes | Notebook UI/runtime |
| `notebook` | Recommended | Classic notebook compatibility |
| `ipykernel` | Yes | Python kernel registration |

## Reused ML stack

These packages overlap with `backend/requirements.txt` and are also needed in the notebook kernel for local model loading:

| Package | Purpose |
|---|---|
| `torch` | Model execution |
| `transformers` | NLLB model/tokenizer loading |
| `sentencepiece` | Tokenizer backend |
| `accelerate` | Model loading helpers |
| `peft` | LoRA adapter work |
| `bitsandbytes` | Optional 8-bit loading |
| `protobuf` | Transformer/model serialization |

## Packages observed in notebook scripts and notebook cells

### Data preparation / extraction

| Package | Where it appears |
|---|---|
| `pandas` | CSV harvesting and dataset processing scripts |
| `pdfplumber` | PDF extraction scripts |
| `beautifulsoup4` | HTML/text cleanup in notebook environment |
| `lxml` | Parsing support used with notebook tooling |
| `clean-text[gpl]` | Text cleaning in notebook workflow |

### Training / evaluation

| Package | Where it appears |
|---|---|
| `datasets` | Hugging Face dataset loading/evaluation cells |
| `evaluate` | Evaluation notebook cells |
| `sacrebleu` | Translation metric evaluation |
| `wandb` | Optional experiment tracking |

## Suggested install groups

### Minimum notebook kernel
- `jupyterlab`
- `ipykernel`
- everything from `backend/requirements.txt`

### Full notebook workflow
Add these on top of the minimum kernel:
- `pandas`
- `datasets`
- `evaluate`
- `sacrebleu`
- `pdfplumber`
- `beautifulsoup4`
- `lxml`
- `clean-text[gpl]`
- `wandb`

## Notes

- `model_validation.ipynb` and `sample.ipynb` both load `transformers` and `torch` directly.
- The notebook extras are documented separately because they are broader than what the live Django API needs at runtime.
- If you want a single environment for backend + notebooks, install backend requirements first, then add only the notebook extras you need.
