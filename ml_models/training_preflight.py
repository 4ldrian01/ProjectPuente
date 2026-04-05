"""
training_preflight.py — Architecture and training readiness verifier for PUENTE.

Runs a no-install, read-only preflight audit across frontend/backend/ML/notebook
layers and writes a structured JSON report.

Usage:
    cd ml_models
    python training_preflight.py
    python training_preflight.py --output ./training_preflight_report.json
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | WARN | BLOCKER
    details: str


REQUIRED_DIRS = [
    'backend',
    'frontend',
    'datasets',
    'ml_models',
    'notebooks/scripts',
]

REQUIRED_FILES = [
    'backend/core_api/languages.py',
    'backend/core_api/views.py',
    'backend/core_api/serializers.py',
    'backend/core_api/models.py',
    'frontend/src/lib/settings.js',
    'frontend/src/components/screens/TranslateScreen.jsx',
    'notebooks/scripts/run_nllb_pipeline.py',
    'ml_models/train_lora.py',
    'ml_models/evaluate_metrics.py',
    'ml_models/evaluate_spanish_baseline.py',
]

REQUIRED_PROCESSED_FILES = [
    'chavacano_lexicon_nllb.json',
    'chavacano_parallel_sentences_nllb.json',
    'tatoeba_parallel_nllb.json',
    'creole_rc_chavacano_nllb.json',
]

OPTIONAL_MODEL_FILES = [
    'config.json',
    'tokenizer.json',
    'tokenizer_config.json',
    'sentencepiece.bpe.model',
]

ACTIVE_PIPELINE_SCRIPTS = [
    'notebooks/scripts/run_nllb_pipeline.py',
    'notebooks/scripts/extract_chavacano_pdf_REFINED.py',
    'notebooks/scripts/process_chavacano_csv_REFINED.py',
    'notebooks/scripts/process_tatoeba_REFINED.py',
    'notebooks/scripts/harvest_creole_rc_REFINED.py',
    'ml_models/train_lora.py',
]

LEGACY_SCRIPT_CANDIDATES = [
    'notebooks/scripts/extract_chavacano_pdf.py',
    'notebooks/scripts/process_chavacano_csv.py',
    'notebooks/scripts/process_tatoeba01.py',
    'notebooks/scripts/harvest_creole-rc_data.py',
]

REQUIRED_PYTHON_MODULES = [
    'torch',
    'transformers',
    'peft',
    'sacrebleu',
    'pandas',
    'pdfplumber',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run PUENTE training architecture preflight checks.')
    parser.add_argument(
        '--output',
        type=str,
        default='./training_preflight_report.json',
        help='Path to output JSON report.',
    )
    return parser.parse_args()


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def extract_python_dict_keys(py_file: Path, symbol_name: str) -> Optional[List[str]]:
    tree = ast.parse(read_text(py_file))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    if isinstance(node.value, ast.Dict):
                        keys = []
                        for key_node in node.value.keys:
                            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                                keys.append(key_node.value)
                        return keys
    return None


def extract_js_array(text: str, variable_name: str) -> Optional[List[str]]:
    pattern = rf"{re.escape(variable_name)}\s*=\s*\[(.*?)\]"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return None

    block = match.group(1)
    values = re.findall(r"'([^']+)'|\"([^\"]+)\"", block)
    flattened = []
    for left, right in values:
        flattened.append(left or right)
    return flattened


def add_result(results: List[CheckResult], name: str, status: str, details: str) -> None:
    results.append(CheckResult(name=name, status=status, details=details))


def check_structure(project_root: Path, results: List[CheckResult]) -> None:
    missing_dirs = [d for d in REQUIRED_DIRS if not (project_root / d).is_dir()]
    if missing_dirs:
        add_result(results, 'Directory structure', 'BLOCKER', f"Missing directories: {', '.join(missing_dirs)}")
    else:
        add_result(results, 'Directory structure', 'PASS', 'All required architecture directories are present.')

    missing_files = [f for f in REQUIRED_FILES if not (project_root / f).is_file()]
    if missing_files:
        add_result(results, 'Critical files', 'BLOCKER', f"Missing files: {', '.join(missing_files)}")
    else:
        add_result(results, 'Critical files', 'PASS', 'All required backend/frontend/ML files are present.')


def check_language_contract(project_root: Path, results: List[CheckResult]) -> None:
    backend_lang_file = project_root / 'backend/core_api/languages.py'
    frontend_settings = project_root / 'frontend/src/lib/settings.js'
    translate_screen = project_root / 'frontend/src/components/screens/TranslateScreen.jsx'

    backend_codes = extract_python_dict_keys(backend_lang_file, 'SUPPORTED_LANGUAGES') or []
    backend_source = backend_codes
    backend_target = [c for c in backend_codes if c != 'auto']

    settings_text = read_text(frontend_settings)
    frontend_source = extract_js_array(settings_text, 'SOURCE_LANGUAGE_CODES') or []
    frontend_target = extract_js_array(settings_text, 'TARGET_LANGUAGE_CODES') or []

    if set(backend_source) != set(frontend_source):
        add_result(
            results,
            'Language contract (source)',
            'BLOCKER',
            f"Backend source {sorted(backend_source)} != Frontend source {sorted(frontend_source)}",
        )
    else:
        add_result(results, 'Language contract (source)', 'PASS', f"Synchronized source languages: {sorted(backend_source)}")

    if set(backend_target) != set(frontend_target):
        add_result(
            results,
            'Language contract (target)',
            'BLOCKER',
            f"Backend target {sorted(backend_target)} != Frontend target {sorted(frontend_target)}",
        )
    else:
        add_result(results, 'Language contract (target)', 'PASS', f"Synchronized target languages: {sorted(backend_target)}")

    screen_text = read_text(translate_screen)
    source_visible = extract_js_array(screen_text, 'SOURCE_VISIBLE') or []
    source_dropdown = extract_js_array(screen_text, 'SOURCE_DROPDOWN') or []
    target_visible = extract_js_array(screen_text, 'TARGET_VISIBLE') or []
    target_dropdown = extract_js_array(screen_text, 'TARGET_DROPDOWN') or []

    source_union = sorted(set(source_visible + source_dropdown))
    target_union = sorted(set(target_visible + target_dropdown))

    if set(source_union) != set(frontend_source):
        add_result(
            results,
            'TranslateScreen source roster',
            'WARN',
            f"TranslateScreen source roster {source_union} != frontend settings {sorted(frontend_source)}",
        )
    else:
        add_result(results, 'TranslateScreen source roster', 'PASS', 'TranslateScreen source languages align with settings.js.')

    if set(target_union) != set(frontend_target):
        add_result(
            results,
            'TranslateScreen target roster',
            'WARN',
            f"TranslateScreen target roster {target_union} != frontend settings {sorted(frontend_target)}",
        )
    else:
        add_result(results, 'TranslateScreen target roster', 'PASS', 'TranslateScreen target languages align with settings.js.')


def check_pipeline_paths(project_root: Path, results: List[CheckResult]) -> None:
    active_missing = [p for p in ACTIVE_PIPELINE_SCRIPTS if not (project_root / p).is_file()]
    if active_missing:
        add_result(results, 'Active pipeline scripts', 'BLOCKER', f"Missing active scripts: {', '.join(active_missing)}")
    else:
        add_result(results, 'Active pipeline scripts', 'PASS', 'All active pipeline scripts are present.')

    uppercase_hits = []
    absolute_hits = []

    casing_scope = [
        rel_path for rel_path in ACTIVE_PIPELINE_SCRIPTS
        if rel_path.startswith('notebooks/scripts/')
    ]

    for rel_path in ACTIVE_PIPELINE_SCRIPTS:
        text = read_text(project_root / rel_path)
        if rel_path in casing_scope and 'Datasets' in text:
            uppercase_hits.append(rel_path)

        windows_abs_path_pattern = r"(?<![A-Za-z0-9])(?:[A-Za-z]:\\\\|[A-Za-z]:/(?!/))"
        if re.search(windows_abs_path_pattern, text):
            absolute_hits.append(rel_path)

    if uppercase_hits:
        add_result(
            results,
            'Canonical datasets path casing',
            'WARN',
            f"Found legacy 'Datasets' references in: {', '.join(uppercase_hits)}",
        )
    else:
        add_result(results, 'Canonical datasets path casing', 'PASS', 'No legacy uppercase datasets path references in active scripts.')

    if absolute_hits:
        add_result(
            results,
            'Hard-coded absolute paths',
            'WARN',
            f"Potential absolute path references in active scripts: {', '.join(absolute_hits)}",
        )
    else:
        add_result(results, 'Hard-coded absolute paths', 'PASS', 'No hard-coded absolute Windows paths in active scripts.')


def check_datasets_and_models(project_root: Path, results: List[CheckResult]) -> None:
    datasets_root = project_root / 'datasets'
    processed_root = datasets_root / 'processed' / '001_chavacano'

    if not datasets_root.is_dir():
        add_result(results, 'datasets root', 'BLOCKER', f'Missing datasets directory: {datasets_root}')
        return

    if not processed_root.is_dir():
        add_result(results, 'processed dataset root', 'BLOCKER', f'Missing processed dataset directory: {processed_root}')
    else:
        missing_processed = [f for f in REQUIRED_PROCESSED_FILES if not (processed_root / f).is_file()]
        if missing_processed:
            add_result(
                results,
                'NLLB-ready processed files',
                'WARN',
                f"Missing one or more processed files: {', '.join(missing_processed)}",
            )
        else:
            add_result(results, 'NLLB-ready processed files', 'PASS', 'Required processed dataset files are present.')

    model_root = project_root / 'ml_models' / 'nllb-200-distilled-600M'
    if not model_root.is_dir():
        add_result(
            results,
            'Base model directory',
            'BLOCKER',
            f'Model directory missing: {model_root} (run download_model.py before training/inference).',
        )
    else:
        missing_model_files = [f for f in OPTIONAL_MODEL_FILES if not (model_root / f).is_file()]
        if missing_model_files:
            add_result(
                results,
                'Base model file completeness',
                'WARN',
                f"Model directory exists but missing files: {', '.join(missing_model_files)}",
            )
        else:
            add_result(results, 'Base model file completeness', 'PASS', 'Base NLLB model files look complete.')


def check_environment_and_dependencies(project_root: Path, results: List[CheckResult]) -> None:
    backend_env_example = project_root / 'backend/.env.example'
    frontend_env_example = project_root / 'frontend/.env.example'

    missing_templates = []
    if not backend_env_example.is_file():
        missing_templates.append('backend/.env.example')
    if not frontend_env_example.is_file():
        missing_templates.append('frontend/.env.example')

    if missing_templates:
        add_result(results, 'Environment templates', 'WARN', f"Missing env template files: {', '.join(missing_templates)}")
    else:
        add_result(results, 'Environment templates', 'PASS', 'Backend and frontend env templates are present.')

    has_venv = (project_root / 'venv').is_dir()
    has_dot_venv = (project_root / '.venv').is_dir()
    if has_venv and has_dot_venv:
        add_result(
            results,
            'Virtual environment duplication',
            'WARN',
            'Both venv/ and .venv/ exist. Keep one canonical environment to reduce confusion.',
        )
    else:
        add_result(results, 'Virtual environment duplication', 'PASS', 'Single virtual environment layout detected.')

    missing_modules = [m for m in REQUIRED_PYTHON_MODULES if importlib.util.find_spec(m) is None]
    if missing_modules:
        add_result(
            results,
            'Python dependency availability',
            'WARN',
            f"Missing modules in current interpreter: {', '.join(missing_modules)}",
        )
    else:
        add_result(results, 'Python dependency availability', 'PASS', 'Required training/processing modules are importable.')


def check_redundancy_candidates(project_root: Path, results: List[CheckResult]) -> None:
    present_legacy = [p for p in LEGACY_SCRIPT_CANDIDATES if (project_root / p).is_file()]
    if present_legacy:
        add_result(
            results,
            'Legacy script redundancy',
            'WARN',
            'Legacy scripts still present (candidate cleanup): ' + ', '.join(present_legacy),
        )
    else:
        add_result(results, 'Legacy script redundancy', 'PASS', 'No known legacy duplicate scripts found.')


def summarize(results: List[CheckResult]) -> Dict[str, int]:
    counts = {'PASS': 0, 'WARN': 0, 'BLOCKER': 0}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def write_report(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_path = resolve_path(script_dir, args.output)

    results: List[CheckResult] = []

    check_structure(project_root, results)
    check_language_contract(project_root, results)
    check_pipeline_paths(project_root, results)
    check_datasets_and_models(project_root, results)
    check_environment_and_dependencies(project_root, results)
    check_redundancy_candidates(project_root, results)

    counts = summarize(results)
    overall_status = 'READY' if counts['BLOCKER'] == 0 else 'BLOCKED'

    payload = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'project_root': str(project_root),
        'python_executable': sys.executable,
        'overall_status': overall_status,
        'summary': counts,
        'results': [asdict(item) for item in results],
    }

    write_report(output_path, payload)

    print('\nPUENTE Training Preflight')
    print('=' * 72)
    print(f"Overall status : {overall_status}")
    print(f"PASS           : {counts['PASS']}")
    print(f"WARN           : {counts['WARN']}")
    print(f"BLOCKER        : {counts['BLOCKER']}")
    print('-' * 72)

    for item in results:
        marker = {'PASS': '[OK]', 'WARN': '[WARN]', 'BLOCKER': '[BLOCKER]'}.get(item.status, '[?]')
        print(f"{marker:<10} {item.name}: {item.details}")

    print('-' * 72)
    print(f'Report written : {output_path}')

    if counts['BLOCKER'] > 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
