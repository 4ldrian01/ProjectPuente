"""
train_lora.py — LoRA fine-tuning script for Chavacano formal/street adapters.

Usage:
    cd ml_models
    python train_lora.py --mode formal --dataset ../datasets/processed/pillars/parallel/
    python train_lora.py --mode street --dataset ../datasets/processed/pillars/parallel/

This version hardens data ingestion:
- accepts both .json and .jsonl payloads
- supports metadata-rich {metadata, entries} JSON files
- excludes lexicon/monolingual records from seq2seq loss tensors
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path


APP_TEXT_KEYS = {
    'en': ('english', 'eng', 'en'),
    'es': ('spanish', 'espanol', 'es'),
    'cbk': ('chavacano', 'cbk', 'chabacano'),
    'tl': ('tagalog', 'tl', 'tgl'),
    'ceb': ('cebuano', 'ceb', 'bisaya'),
    'hil': ('hiligaynon', 'hil'),
}

FLORES_TO_APP = {
    'eng_Latn': 'en',
    'spa_Latn': 'es',
    'cbk_Latn': 'cbk',
    'tgl_Latn': 'tl',
    'ceb_Latn': 'ceb',
    'hil_Latn': 'hil',
}

LEXICON_HINT_FIELDS = {'word', 'term', 'lemma', 'pos', 'definition'}
WHITESPACE_RE = re.compile(r'\s+')
DATASET_FILENAME_BLOCKLIST = {
    'lexicon',
    'dictionary',
    'monolingual',
    'pipeline_report',
    'archive_manifest',
    '.meta.',
}


def parse_args():
    parser = argparse.ArgumentParser(description='Train LoRA adapter for NLLB-200')
    parser.add_argument(
        '--mode',
        choices=['formal', 'street'],
        required=True,
        help='Sociolinguistic register: formal (high variety) or street (low variety)',
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default='../datasets/processed/pillars/parallel/',
        help='Path to processed dataset directory containing JSON/JSONL files.',
    )
    parser.add_argument(
        '--dataset-file',
        type=str,
        default='',
        help='Optional single dataset file (.json or .jsonl). Overrides directory scan.',
    )
    parser.add_argument(
        '--base-model',
        type=str,
        default='./nllb-200-distilled-600M',
        help='Path to the base NLLB-200 model directory',
    )
    parser.add_argument('--source-lang', type=str, default='eng_Latn', help='Tokenizer source FLORES code.')
    parser.add_argument('--target-lang', type=str, default='cbk_Latn', help='Tokenizer target FLORES code.')
    parser.add_argument('--epochs', type=int, default=3, help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=8, help='Training batch size')
    parser.add_argument('--lr', type=float, default=2e-4, help='Learning rate')
    parser.add_argument('--lora-r', type=int, default=16, help='LoRA rank')
    parser.add_argument('--lora-alpha', type=int, default=32, help='LoRA alpha scaling')
    parser.add_argument('--lora-dropout', type=float, default=0.05, help='LoRA dropout')
    return parser.parse_args()


def resolve_dataset_dir(dataset_arg):
    """Resolve dataset directory with compatibility fallback for old path casing."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    candidates = []

    if dataset_arg:
        candidates.append(os.path.abspath(os.path.join(script_dir, dataset_arg)))
        candidates.append(os.path.abspath(dataset_arg))

    candidates.extend([
        os.path.join(project_root, 'datasets', 'processed', 'pillars', 'parallel'),
        os.path.join(project_root, 'datasets', 'processed', 'jsonl', 'pillars', 'parallel'),
        os.path.join(project_root, 'datasets', 'processed', '001_chavacano'),
        os.path.join(project_root, 'Datasets', 'processed', '001_chavacano'),
    ])

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return os.path.abspath(os.path.join(script_dir, dataset_arg))


def normalize_text(value):
    text = str(value or '').strip()
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = WHITESPACE_RE.sub(' ', text)
    return text


def app_code_from_lang_code(lang_code):
    raw = str(lang_code or '').strip()
    if raw in FLORES_TO_APP:
        return FLORES_TO_APP[raw]
    if '_' in raw:
        raw = raw.split('_', 1)[0]
    return raw.casefold()


def pick_text(entry, aliases):
    for key in aliases:
        value = normalize_text(entry.get(key))
        if value:
            return value
    return ''


def build_source_aliases(source_lang):
    app = app_code_from_lang_code(source_lang)
    app_aliases = APP_TEXT_KEYS.get(app, ())
    generic = ('source_text', 'source', 'src', 'input_text', 'input')
    return tuple(dict.fromkeys([*app_aliases, *generic]))


def build_target_aliases(target_lang):
    app = app_code_from_lang_code(target_lang)
    app_aliases = APP_TEXT_KEYS.get(app, ())
    generic = ('target_text', 'target', 'tgt', 'reference', 'label')
    return tuple(dict.fromkeys([*app_aliases, *generic]))


def is_lexicon_entry(entry):
    if not isinstance(entry, dict):
        return False
    present = {key for key in LEXICON_HINT_FIELDS if key in entry}
    return 'definition' in present and len(present) >= 2


def iter_records_from_json(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))

    if isinstance(payload, dict):
        entries = payload.get('entries', [])
        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict):
                    yield item
        return

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item


def iter_records_from_jsonl(path):
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield record


def iter_dataset_records(path):
    if path.endswith('.jsonl'):
        yield from iter_records_from_jsonl(path)
        return

    if path.endswith('.json'):
        yield from iter_records_from_json(path)


def collect_dataset_files(dataset_dir, dataset_file=''):
    if dataset_file:
        resolved = os.path.abspath(dataset_file)
        if os.path.isfile(resolved):
            return [resolved]
        raise FileNotFoundError(f'Dataset file not found: {resolved}')

    candidates = []
    for root, _, files in os.walk(dataset_dir):
        for filename in files:
            if not (filename.endswith('.json') or filename.endswith('.jsonl')):
                continue

            lowered = filename.casefold()
            if any(marker in lowered for marker in DATASET_FILENAME_BLOCKLIST):
                continue

            normalized_path = os.path.join(root, filename).replace('\\', '/').casefold()
            if '/monolingual/' in normalized_path:
                continue

            candidates.append(os.path.join(root, filename))

    return sorted(candidates)


def load_parallel_data(dataset_files, source_lang, target_lang):
    """Load strict parallel sentence pairs and exclude lexicon/monolingual rows."""
    source_aliases = build_source_aliases(source_lang)
    target_aliases = build_target_aliases(target_lang)
    requested_source_code = app_code_from_lang_code(source_lang)
    requested_target_code = app_code_from_lang_code(target_lang)

    pairs = []
    seen = set()

    total_accepted = 0
    total_rejected = 0
    total_lexicon = 0
    total_duplicates = 0
    total_non_parallel = 0

    for filepath in dataset_files:
        accepted = 0
        rejected = 0
        lexicon = 0
        duplicates = 0
        non_parallel = 0

        print(f'  Loading: {os.path.basename(filepath)}')
        for entry in iter_dataset_records(filepath):
            if is_lexicon_entry(entry):
                lexicon += 1
                continue

            record_type = normalize_text(entry.get('record_type')).casefold()
            if record_type and record_type != 'parallel':
                non_parallel += 1
                continue

            src = ''
            tgt = ''

            canonical_src = normalize_text(entry.get('source_text'))
            canonical_tgt = normalize_text(entry.get('target_text'))
            row_source_code = app_code_from_lang_code(entry.get('source_lang'))
            row_target_code = app_code_from_lang_code(entry.get('target_lang'))

            if canonical_src and canonical_tgt:
                if row_source_code and row_target_code:
                    if row_source_code == requested_source_code and row_target_code == requested_target_code:
                        src = canonical_src
                        tgt = canonical_tgt
                    elif row_source_code == requested_target_code and row_target_code == requested_source_code:
                        src = canonical_tgt
                        tgt = canonical_src
                else:
                    src = canonical_src
                    tgt = canonical_tgt

            if not src or not tgt:
                src = pick_text(entry, source_aliases)
                tgt = pick_text(entry, target_aliases)

            if not src or not tgt:
                # Fallback for common legacy bilingual structure.
                src = src or normalize_text(entry.get('english') or entry.get('eng') or entry.get('en'))
                tgt = tgt or normalize_text(entry.get('chavacano') or entry.get('cbk') or entry.get('chabacano'))

            if not src or not tgt:
                rejected += 1
                continue

            key = (src.casefold(), tgt.casefold())
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)

            pairs.append((src, tgt))
            accepted += 1

        total_accepted += accepted
        total_rejected += rejected
        total_lexicon += lexicon
        total_duplicates += duplicates
        total_non_parallel += non_parallel

        print(
            f'    accepted={accepted} rejected={rejected} '
            f'lexicon_skipped={lexicon} non_parallel_skipped={non_parallel} '
            f'duplicates={duplicates}'
        )

    print(
        '  Dataset summary: '
        f'accepted={total_accepted} rejected={total_rejected} '
        f'lexicon_skipped={total_lexicon} non_parallel_skipped={total_non_parallel} '
        f'duplicates={total_duplicates}'
    )
    return pairs


def main():
    args = parse_args()
    dataset_dir = resolve_dataset_dir(args.dataset)

    # Validate prerequisites.
    if not os.path.isdir(args.base_model):
        print(f'ERROR: Base model not found at {args.base_model}')
        print('Run: python download_model.py')
        sys.exit(1)

    if not args.dataset_file and not os.path.isdir(dataset_dir):
        print(f'ERROR: Dataset directory not found at {dataset_dir}')
        sys.exit(1)

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model, TaskType
    except ImportError as e:
        print(f'ERROR: Missing dependency: {e}')
        print('Run: pip install torch transformers peft sentencepiece')
        sys.exit(1)

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f'lora-cbk-{args.mode}',
    )

    # Load data.
    print(f'\nLoading {args.mode} training data from {dataset_dir} ...')
    dataset_files = collect_dataset_files(dataset_dir, dataset_file=args.dataset_file)
    if not dataset_files:
        print('ERROR: No JSON/JSONL dataset files found after filtering.')
        sys.exit(1)

    pairs = load_parallel_data(
        dataset_files=dataset_files,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
    )
    print(f'  Loaded {len(pairs)} strict parallel sentence pairs')

    if len(pairs) < 10:
        print('WARNING: Very few training samples. Results may be poor.')

    # Load base model + tokenizer.
    print(f'\nLoading base model: {args.base_model}')
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.base_model,
        local_files_only=True,
        torch_dtype=torch.float32,
    )

    # Configure LoRA.
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=['q_proj', 'v_proj'],  # Attention projection layers
        bias='none',
    )

    print(f'\nApplying LoRA config: r={args.lora_r}, alpha={args.lora_alpha}')
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Prepare dataset.
    print('\nTokenizing training data ...')
    tokenizer.src_lang = args.source_lang

    train_encodings = []
    for src, tgt in pairs:
        inputs = tokenizer(src, truncation=True, max_length=128, padding='max_length')
        labels = tokenizer(
            text_target=tgt,
            truncation=True,
            max_length=128,
            padding='max_length',
        )
        inputs['labels'] = labels['input_ids']
        train_encodings.append(inputs)

    # Training loop (simplified - use Trainer for production).
    from torch.utils.data import DataLoader, Dataset

    class PairDataset(Dataset):
        def __init__(self, encodings):
            self.encodings = encodings

        def __len__(self):
            return len(self.encodings)

        def __getitem__(self, idx):
            return {k: torch.tensor(v) for k, v in self.encodings[idx].items()}

    dataset = PairDataset(train_encodings)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    model.train()

    print(f'\nTraining LoRA adapter ({args.mode}) for {args.epochs} epochs ...')
    for epoch in range(args.epochs):
        total_loss = 0.0
        for batch_idx, batch in enumerate(loader):
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total_loss += loss.item()

            if (batch_idx + 1) % 10 == 0:
                print(
                    f'  Epoch {epoch + 1}/{args.epochs}, '
                    f'Batch {batch_idx + 1}, Loss: {loss.item():.4f}'
                )

        avg_loss = total_loss / max(len(loader), 1)
        print(f'  Epoch {epoch + 1}/{args.epochs} complete - Avg Loss: {avg_loss:.4f}')

    # Save adapter.
    print(f'\nSaving LoRA adapter to: {output_dir}')
    model.save_pretrained(output_dir)

    print(f"\n{'=' * 60}")
    print('  LoRA adapter trained successfully!')
    print(f'  Mode: {args.mode}')
    print(f'  Output: {output_dir}')
    print(f'  Training samples: {len(pairs)}')
    print(f"{'=' * 60}")
    print('\nRestart the Django server to load the new adapter.')


if __name__ == '__main__':
    main()
