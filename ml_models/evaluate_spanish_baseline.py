"""evaluate_spanish_baseline.py — A/B baseline evaluation for pure Spanish.

This script evaluates pure European Spanish (spa_Latn) -> English (eng_Latn)
translations using local NLLB-200 inference, then computes BLEU + chrF++
with sacrebleu and writes results to spanish_baseline_metrics.json.

Usage:
    cd ml_models
    python evaluate_spanish_baseline.py
    python evaluate_spanish_baseline.py --input ./spanish_baseline_input.json

Input format (JSON array):
[
  {"spanish": "Buenos días", "english": "Good morning"},
  {"source": "Para siempre", "reference": "Forever"}
]
"""

# pyright: reportMissingImports=false

import argparse
import json
import os
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


DEFAULT_BASELINE_SAMPLES = [
    {"spanish": "Buenos días", "english": "Good morning"},
    {"spanish": "Muchas gracias", "english": "Thank you very much"},
    {"spanish": "Para siempre", "english": "Forever"},
    {"spanish": "Estoy de acuerdo", "english": "I agree"},
    {"spanish": "Seguro", "english": "Certain"},
]

SOURCE_FLORES = 'spa_Latn'
TARGET_FLORES = 'eng_Latn'


def parse_args():
    parser = argparse.ArgumentParser(
        description='Evaluate pure Spanish baseline (spa_Latn->eng_Latn) with BLEU + chrF++.',
    )
    parser.add_argument(
        '--base-model',
        type=str,
        default='./nllb-200-distilled-600M',
        help='Path to local NLLB model directory.',
    )
    parser.add_argument(
        '--input',
        type=str,
        default='',
        help='Optional JSON file containing Spanish/English pairs.',
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./spanish_baseline_metrics.json',
        help='Output JSON report path.',
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
        help='Number of examples to include in the output report.',
    )
    return parser.parse_args()


def resolve_path(script_dir, raw_path):
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.normpath(os.path.join(script_dir, raw_path))


def load_pairs(input_path=''):
    if not input_path:
        return DEFAULT_BASELINE_SAMPLES

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f'Input JSON not found: {input_path}')

    with open(input_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    if not isinstance(payload, list):
        raise ValueError('Input JSON must be an array of objects.')

    pairs = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        src = (item.get('spanish') or item.get('source') or '').strip()
        ref = (item.get('english') or item.get('reference') or item.get('target') or '').strip()
        if src and ref:
            pairs.append({'spanish': src, 'english': ref})

    if not pairs:
        raise ValueError('No valid Spanish-English pairs found in input JSON.')

    return pairs


def load_model_and_tokenizer(base_model_dir):
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            f'Missing dependency: {exc}. Install torch and transformers first.'
        ) from exc

    if not os.path.isdir(base_model_dir):
        raise FileNotFoundError(
            f'Base model not found at {base_model_dir}. Run: python download_model.py'
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

    model.eval()
    return tokenizer, model


def translate_once(model, tokenizer, text, num_beams, max_new_tokens):
    import torch

    tokenizer.src_lang = SOURCE_FLORES
    encoded = tokenizer(text, return_tensors='pt', truncation=True, max_length=128)

    device = next(model.parameters()).device
    encoded = {k: v.to(device) for k, v in encoded.items()}

    start = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            **encoded,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(TARGET_FLORES),
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

    base_model_dir = resolve_path(script_dir, args.base_model)
    output_path = resolve_path(script_dir, args.output)
    input_path = resolve_path(script_dir, args.input) if args.input else ''

    _guard_required_dependencies(
        required_modules=['torch', 'transformers', 'sacrebleu'],
        output_path=output_path,
        context_payload={
            'base_model_path': base_model_dir,
            'input_path': input_path,
            'source_lang': 'es',
            'target_lang': 'en',
            'source_flores': SOURCE_FLORES,
            'target_flores': TARGET_FLORES,
        },
    )

    try:
        pairs = load_pairs(input_path)
        tokenizer, model = load_model_and_tokenizer(base_model_dir)

        predictions = []
        references = []
        latencies = []
        examples = []

        for idx, item in enumerate(pairs, start=1):
            src = item['spanish']
            ref = item['english']

            pred, elapsed_ms = translate_once(
                model=model,
                tokenizer=tokenizer,
                text=src,
                num_beams=args.num_beams,
                max_new_tokens=args.max_new_tokens,
            )

            predictions.append(pred)
            references.append(ref)
            latencies.append(elapsed_ms)

            if len(examples) < max(args.show_examples, 0):
                examples.append({
                    'index': idx,
                    'source_spanish': src,
                    'reference_english': ref,
                    'prediction_english': pred,
                    'latency_ms': round(elapsed_ms, 2),
                })

        metrics = compute_metrics(predictions, references)

        payload = {
            'status': 'success',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'base_model_path': base_model_dir,
            'input_path': input_path or '(embedded default samples)',
            'task': 'pure_spanish_baseline_ab_test',
            'source_lang': 'es',
            'target_lang': 'en',
            'source_flores': SOURCE_FLORES,
            'target_flores': TARGET_FLORES,
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

        write_json(output_path, payload)

        print('Spanish baseline evaluation complete.')
        print(f"BLEU:   {payload['metrics']['bleu']['score']}")
        print(f"chrF++: {payload['metrics']['chrf++']['score']}")
        print(f'Results written to: {output_path}')

    except Exception as exc:
        error_payload = {
            'status': 'error',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'error': str(exc),
            'base_model_path': base_model_dir,
            'input_path': input_path,
            'source_lang': 'es',
            'target_lang': 'en',
            'source_flores': SOURCE_FLORES,
            'target_flores': TARGET_FLORES,
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
