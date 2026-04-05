"""
evaluate_metrics.py — Offline translation metric evaluator for Project Puente.

Computes BLEU and chrF++ (via sacrebleu) for local NLLB-200 predictions,
then writes a JSON report to ml_models/evaluation_results.json by default.

Usage:
    cd ml_models
    python evaluate_metrics.py
    python evaluate_metrics.py --mode formal --max-samples 100

Notes:
- Runs fully local (no cloud APIs).
- Expects a local NLLB model at ./nllb-200-distilled-600M.
- If mode is formal/street and a matching LoRA adapter exists,
  the script loads it from ./lora-cbk-<mode>.
"""

# pyright: reportMissingImports=false

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone


OFFLINE_RUNTIME_PACKAGES = ('torch', 'transformers', 'peft', 'sacrebleu', 'psutil')


def _build_dependency_fix_command():
    packages = ' '.join(OFFLINE_RUNTIME_PACKAGES)
    return f'"{sys.executable}" -m pip install {packages}'


def _find_missing_modules(required_modules):
    missing = []
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def _guard_required_dependencies(required_modules, output_path, context_payload):
    missing = _find_missing_modules(required_modules)
    if not missing:
        return

    install_command = _build_dependency_fix_command()
    missing_list = ', '.join(missing)

    print(f'[ERROR] Missing required dependencies: {missing_list}')
    print(f'[FIX] Run this command, then re-run the evaluator:\n{install_command}')

    error_payload = {
        'status': 'error',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'error': f'Missing dependencies: {missing_list}',
        'missing_dependencies': missing,
        'install_command': install_command,
        **context_payload,
    }
    write_json(output_path, error_payload)
    sys.exit(1)


FLORES_MAP = {
    'en': 'eng_Latn',
    'es': 'spa_Latn',
    'tl': 'tgl_Latn',
    'cbk': 'cbk_Latn',
    'ceb': 'ceb_Latn',
    'hil': 'hil_Latn',
}

LANGUAGE_KEYS = {
    'en': ['english', 'eng', 'en'],
    'es': ['spanish', 'español', 'espanol', 'spa', 'es'],
    'tl': ['tagalog', 'tl', 'tgl'],
    'cbk': ['chavacano', 'cbk', 'chabacano'],
    'ceb': ['cebuano', 'ceb', 'bisaya'],
    'hil': ['hiligaynon', 'hil'],
}


def parse_args():
    parser = argparse.ArgumentParser(
        description='Evaluate local NLLB translations with BLEU + chrF++.',
    )
    parser.add_argument(
        '--dataset',
        type=str,
        default='../datasets/processed/001_chavacano/chavacano_parallel_sentences_nllb.json',
        help='Path to dataset JSON containing parallel pairs.',
    )
    parser.add_argument(
        '--base-model',
        type=str,
        default='./nllb-200-distilled-600M',
        help='Path to local NLLB model directory.',
    )
    parser.add_argument(
        '--mode',
        choices=['base', 'formal', 'street'],
        default='base',
        help='Model mode to evaluate (base or LoRA adapter mode).',
    )
    parser.add_argument(
        '--src-lang',
        choices=sorted(FLORES_MAP.keys()),
        default='cbk',
        help='Source language code.',
    )
    parser.add_argument(
        '--tgt-lang',
        choices=sorted(FLORES_MAP.keys()),
        default='en',
        help='Target language code.',
    )
    parser.add_argument(
        '--max-samples',
        type=int,
        default=0,
        help='Maximum number of pairs to evaluate (0 = all).',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for sample selection when max-samples > 0.',
    )
    parser.add_argument(
        '--num-beams',
        type=int,
        default=4,
        help='Beam size for generation.',
    )
    parser.add_argument(
        '--max-new-tokens',
        type=int,
        default=128,
        help='Maximum generated tokens per sample.',
    )
    parser.add_argument(
        '--show-examples',
        type=int,
        default=10,
        help='How many sample predictions to store in output JSON.',
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./evaluation_results.json',
        help='Output JSON path for evaluation report.',
    )
    return parser.parse_args()


def resolve_path(script_dir, raw_path):
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.normpath(os.path.join(script_dir, raw_path))


def pick_value(entry, candidate_keys):
    for key in candidate_keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def extract_parallel_pairs(payload, src_lang, tgt_lang):
    entries = payload.get('entries', []) if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ValueError('Dataset JSON must be a list or a dict with an "entries" list.')

    src_candidates = LANGUAGE_KEYS.get(src_lang, []) + ['source', 'src']
    tgt_candidates = LANGUAGE_KEYS.get(tgt_lang, []) + ['target', 'tgt']

    pairs = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        src_text = pick_value(entry, src_candidates)
        tgt_text = pick_value(entry, tgt_candidates)

        if not src_text or not tgt_text:
            continue

        pairs.append((src_text, tgt_text))

    return pairs


def maybe_sample_pairs(pairs, max_samples, seed):
    if max_samples <= 0 or max_samples >= len(pairs):
        return pairs

    rng = random.Random(seed)
    selected_indices = sorted(rng.sample(range(len(pairs)), k=max_samples))
    return [pairs[i] for i in selected_indices]


def load_model_and_tokenizer(base_model_dir, mode, adapter_dir):
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            f'Missing dependency: {exc}. Install torch and transformers first.'
        ) from exc

    if not os.path.isdir(base_model_dir):
        raise FileNotFoundError(
            f'Base model not found at {base_model_dir}. '
            f'Run: python download_model.py'
        )

    tokenizer = AutoTokenizer.from_pretrained(base_model_dir, local_files_only=True)

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            base_model_dir,
            local_files_only=True,
            torch_dtype=torch.float16,
            device_map='auto',
        )
    else:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            base_model_dir,
            local_files_only=True,
            torch_dtype=torch.float32,
            device_map='cpu',
        )

    adapter_used = ''
    if mode in {'formal', 'street'} and os.path.isdir(adapter_dir):
        try:
            from peft import PeftModel
        except ImportError as exc:
            raise RuntimeError(
                f'LoRA adapter requested ({mode}) but peft is missing: {exc}'
            ) from exc

        model = PeftModel.from_pretrained(
            model,
            adapter_dir,
            local_files_only=True,
        )
        adapter_used = adapter_dir

    model.eval()
    return tokenizer, model, adapter_used


def translate_text(model, tokenizer, text, src_flores, tgt_flores, num_beams, max_new_tokens):
    import torch

    tokenizer.src_lang = src_flores
    encoded = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)

    device = next(model.parameters()).device
    encoded = {key: value.to(device) for key, value in encoded.items()}

    start = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            **encoded,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_flores),
            max_new_tokens=max_new_tokens,
            num_beams=num_beams,
        )
    elapsed_ms = (time.perf_counter() - start) * 1000

    prediction = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
    return prediction, elapsed_ms


def compute_metrics(predictions, references):
    try:
        from sacrebleu.metrics import BLEU, CHRF
    except ImportError as exc:
        raise RuntimeError(
            f'Missing dependency: {exc}. Install sacrebleu first.'
        ) from exc

    bleu_metric = BLEU()
    chrfpp_metric = CHRF(word_order=2)  # chrF++

    bleu = bleu_metric.corpus_score(predictions, [references])
    chrfpp = chrfpp_metric.corpus_score(predictions, [references])

    return {
        'bleu': {
            'score': round(float(bleu.score), 4),
            'signature': bleu_metric.get_signature(),
            'summary': str(bleu),
        },
        'chrf++': {
            'score': round(float(chrfpp.score), 4),
            'signature': chrfpp_metric.get_signature(),
            'summary': str(chrfpp),
        },
    }


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    dataset_path = resolve_path(script_dir, args.dataset)
    base_model_dir = resolve_path(script_dir, args.base_model)
    output_path = resolve_path(script_dir, args.output)
    adapter_dir = resolve_path(script_dir, f'./lora-cbk-{args.mode}')

    src_flores = FLORES_MAP[args.src_lang]
    tgt_flores = FLORES_MAP[args.tgt_lang]

    required_modules = ['torch', 'transformers', 'sacrebleu']
    if args.mode in {'formal', 'street'}:
        required_modules.append('peft')

    _guard_required_dependencies(
        required_modules=required_modules,
        output_path=output_path,
        context_payload={
            'dataset_path': dataset_path,
            'base_model_path': base_model_dir,
            'mode': args.mode,
            'source_lang': args.src_lang,
            'target_lang': args.tgt_lang,
        },
    )

    try:
        if args.src_lang == args.tgt_lang:
            raise ValueError('Source and target languages must be different for evaluation.')

        if not os.path.isfile(dataset_path):
            raise FileNotFoundError(
                f'Dataset file not found at {dataset_path}. '
                f'Provide --dataset with a valid JSON path.'
            )

        with open(dataset_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        pairs = extract_parallel_pairs(payload, args.src_lang, args.tgt_lang)
        if not pairs:
            raise ValueError(
                f'No valid parallel pairs found for {args.src_lang}->{args.tgt_lang} '
                f'in dataset: {dataset_path}'
            )

        pairs = maybe_sample_pairs(pairs, args.max_samples, args.seed)

        print(f'Loaded {len(pairs)} evaluation pairs from {dataset_path}')
        print(f'Loading model from {base_model_dir} (mode={args.mode}) ...')
        tokenizer, model, adapter_used = load_model_and_tokenizer(
            base_model_dir=base_model_dir,
            mode=args.mode,
            adapter_dir=adapter_dir,
        )

        predictions = []
        references = []
        examples = []
        latencies = []

        for idx, (src_text, ref_text) in enumerate(pairs, start=1):
            prediction, elapsed_ms = translate_text(
                model=model,
                tokenizer=tokenizer,
                text=src_text,
                src_flores=src_flores,
                tgt_flores=tgt_flores,
                num_beams=args.num_beams,
                max_new_tokens=args.max_new_tokens,
            )
            predictions.append(prediction)
            references.append(ref_text)
            latencies.append(elapsed_ms)

            if len(examples) < max(args.show_examples, 0):
                examples.append({
                    'index': idx,
                    'source': src_text,
                    'reference': ref_text,
                    'prediction': prediction,
                    'latency_ms': round(elapsed_ms, 2),
                })

            if idx % 25 == 0:
                print(f'  Translated {idx}/{len(pairs)} samples ...')

        metrics = compute_metrics(predictions, references)

        result_payload = {
            'status': 'success',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'dataset_path': dataset_path,
            'base_model_path': base_model_dir,
            'mode': args.mode,
            'adapter_path': adapter_used,
            'source_lang': args.src_lang,
            'target_lang': args.tgt_lang,
            'source_flores': src_flores,
            'target_flores': tgt_flores,
            'sample_count': len(pairs),
            'generation': {
                'num_beams': args.num_beams,
                'max_new_tokens': args.max_new_tokens,
            },
            'timing': {
                'avg_latency_ms': round(sum(latencies) / len(latencies), 4),
                'min_latency_ms': round(min(latencies), 4),
                'max_latency_ms': round(max(latencies), 4),
            },
            'metrics': metrics,
            'examples': examples,
        }

        write_json(output_path, result_payload)

        print('\nEvaluation complete.')
        print(f"BLEU:   {result_payload['metrics']['bleu']['score']}")
        print(f"chrF++: {result_payload['metrics']['chrf++']['score']}")
        print(f'Results written to: {output_path}')

    except Exception as exc:
        error_payload = {
            'status': 'error',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'error': str(exc),
            'dataset_path': dataset_path,
            'base_model_path': base_model_dir,
            'mode': args.mode,
            'source_lang': args.src_lang,
            'target_lang': args.tgt_lang,
        }
        try:
            write_json(output_path, error_payload)
        except Exception:
            pass

        print(f'ERROR: {exc}')
        print(f'Failure details written to: {output_path}')
        sys.exit(1)


if __name__ == '__main__':
    main()
