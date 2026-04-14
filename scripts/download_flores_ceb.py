#!/usr/bin/env python3
"""Download and validate FLORES+ Cebuano-English parallel data.

This script is production-oriented for ProjectPuente:
- safely imports huggingface datasets even when a local datasets/ folder exists
- downloads Cebuano and English splits from FLORES+
- verifies alignment by split and sentence id
- emits strict JSONL translation schema for training
- writes a metadata report with integrity hash
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "datasets" / "raw" / "ceb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download FLORES+ Cebuano-English splits, validate alignment, and write "
            "strict translation JSONL output."
        )
    )
    parser.add_argument(
        "--dataset-id",
        default="openlanguagedata/flores_plus",
        help="Hugging Face dataset id (default: openlanguagedata/flores_plus).",
    )
    parser.add_argument(
        "--source-config",
        default="ceb_Latn",
        help="Source language config name (default: ceb_Latn).",
    )
    parser.add_argument(
        "--target-config",
        default="eng_Latn",
        help="Target language config name (default: eng_Latn).",
    )
    parser.add_argument(
        "--splits",
        default="dev,devtest",
        help="Comma-separated split names to fetch in-order (default: dev,devtest).",
    )
    parser.add_argument(
        "--source-key",
        default="ceb",
        help='Translation output key for source language (default: "ceb").',
    )
    parser.add_argument(
        "--target-key",
        default="en",
        help='Translation output key for target language (default: "en").',
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for dataset artifacts.",
    )
    parser.add_argument(
        "--output-file",
        default="flores_ceb_en.jsonl",
        help="Output JSONL filename (default: flores_ceb_en.jsonl).",
    )
    parser.add_argument(
        "--metadata-file",
        default="flores_ceb_en.meta.json",
        help="Metadata report filename (default: flores_ceb_en.meta.json).",
    )
    parser.add_argument(
        "--expected-total",
        type=int,
        default=2009,
        help="Expected final row count; set 0 to disable strict count check (default: 2009).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional Hugging Face datasets cache directory override.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional dataset revision/tag/commit.",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="Optional Hugging Face token. Falls back to HF_TOKEN env var.",
    )
    parser.add_argument(
        "--hf-token-file",
        type=Path,
        default=None,
        help="Optional file containing a Hugging Face token on the first non-empty line.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output files if they already exist.",
    )
    parser.add_argument(
        "--include-id",
        action="store_true",
        help="Include sentence id in each output JSONL record.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retry attempts for transient HF errors (default: 5).",
    )
    parser.add_argument(
        "--retry-initial-seconds",
        type=float,
        default=3.0,
        help="Initial backoff wait in seconds (default: 3.0).",
    )
    parser.add_argument(
        "--retry-max-seconds",
        type=float,
        default=45.0,
        help="Maximum backoff wait in seconds (default: 45.0).",
    )
    parser.add_argument(
        "--retry-jitter-seconds",
        type=float,
        default=1.0,
        help="Random jitter added to each retry wait (default: 1.0).",
    )
    return parser.parse_args()


def resolve_hf_token(explicit_token: str | None, token_file: Path | None) -> str | None:
    if explicit_token is not None and explicit_token.strip():
        return explicit_token.strip()

    if token_file is not None:
        path = token_file.expanduser().resolve()
        if path.is_file():
            try:
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    value = raw_line.strip().strip('"').strip("'")
                    if value:
                        return value
            except OSError:
                pass

    for env_name in ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_TOKEN"):
        env_value = os.getenv(env_name)
        if env_value and env_value.strip():
            return env_value.strip()

    backend_env_path = PROJECT_ROOT / "backend" / ".env"
    if backend_env_path.is_file():
        try:
            for raw_line in backend_env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if not line.startswith("HF_TOKEN="):
                    continue
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
        except OSError:
            pass

    return None


def gated_dataset_help(dataset_id: str) -> str:
    return "\n".join(
        [
            f"Dataset {dataset_id} is gated.",
            "Accept dataset access terms on Hugging Face, then authenticate locally.",
            "Quick unblock options:",
            "1) export HF_TOKEN='hf_xxx'",
            "2) python scripts/download_flores_ceb.py --hf-token 'hf_xxx' --overwrite",
            "3) huggingface-cli login (stores token in local cache)",
        ]
    )


def is_transient_hf_error(exc: Exception) -> bool:
    text = str(exc).casefold()
    markers = (
        "429",
        "too many requests",
        "rate limit",
        "timed out",
        "timeout",
        "connection reset",
        "temporary failure",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "connection aborted",
    )
    return any(marker in text for marker in markers)


def load_dataset_with_retries(
    *,
    load_dataset,
    kwargs: Dict[str, str],
    split: str,
    config_name: str,
    max_retries: int,
    retry_initial_seconds: float,
    retry_max_seconds: float,
    retry_jitter_seconds: float,
):
    wait_seconds = max(0.0, retry_initial_seconds)
    attempts = max(1, max_retries)

    for attempt in range(1, attempts + 1):
        try:
            return load_dataset(**kwargs)
        except Exception as exc:  # datasets raises different exception classes by version
            lowered = str(exc).casefold()

            # These classes of errors should fail fast with actionable guidance.
            if "dataset scripts are no longer supported" in lowered:
                raise RuntimeError(
                    "Installed huggingface datasets version blocks script-based dataset repos. "
                    "Use a parquet/native dataset variant or pin datasets to a 3.x release."
                ) from exc

            if "gated dataset" in lowered or "must be authenticated" in lowered:
                raise PermissionError(gated_dataset_help(kwargs.get("path", "<dataset>"))) from exc

            # Retry only transient transport/rate-limit failures.
            if attempt >= attempts or not is_transient_hf_error(exc):
                raise

            jitter = random.uniform(0.0, max(0.0, retry_jitter_seconds))
            sleep_for = min(max(0.0, retry_max_seconds), wait_seconds + jitter)
            print(
                f"[retry] transient HF error for split={split} config={config_name}; "
                f"attempt {attempt}/{attempts}, waiting {sleep_for:.1f}s"
            )
            time.sleep(sleep_for)
            wait_seconds = min(max(0.0, retry_max_seconds), max(wait_seconds * 2.0, 1.0))


def parse_split_list(raw_splits: str) -> List[str]:
    splits = [item.strip() for item in raw_splits.split(",") if item.strip()]
    if not splits:
        raise ValueError("At least one split must be provided via --splits.")

    ordered_unique: List[str] = []
    seen = set()
    for split in splits:
        if split in seen:
            continue
        seen.add(split)
        ordered_unique.append(split)

    return ordered_unique


def import_hf_datasets_load_dataset(project_root: Path):
    """Import datasets.load_dataset safely, avoiding local datasets/ shadowing."""
    original_sys_path = list(sys.path)

    sanitized: List[str] = []
    for entry in original_sys_path:
        if entry == "" and Path.cwd().resolve() == project_root:
            continue
        try:
            if Path(entry).resolve() == project_root:
                continue
        except Exception:
            pass
        sanitized.append(entry)

    try:
        sys.path = sanitized
        datasets_mod = importlib.import_module("datasets")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing dependency: datasets. Install it with: pip install datasets"
        ) from exc
    finally:
        sys.path = original_sys_path

    if not hasattr(datasets_mod, "load_dataset"):
        raise ImportError(
            "Imported module named datasets does not expose load_dataset. "
            "A local folder may be shadowing the Hugging Face package."
        )

    return (
        datasets_mod.load_dataset,
        getattr(datasets_mod, "__version__", "unknown"),
        str(getattr(datasets_mod, "__file__", "unknown")),
    )


def extract_split_rows(split_name: str, records: Sequence[dict]) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{split_name}:{idx} is not a JSON object.")

        text = record.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{split_name}:{idx} missing non-empty text field.")

        raw_id = record.get("id")
        sid = str(raw_id).strip() if raw_id is not None else ""
        if not sid:
            sid = str(idx)

        uid = f"{split_name}:{sid}"
        rows.append((uid, text.strip()))

    return rows


def load_language_rows(
    *,
    load_dataset,
    dataset_id: str,
    config_name: str,
    splits: Sequence[str],
    cache_dir: Path | None,
    revision: str | None,
    hf_token: str | None,
    max_retries: int,
    retry_initial_seconds: float,
    retry_max_seconds: float,
    retry_jitter_seconds: float,
) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    all_rows: List[Tuple[str, str]] = []
    counts: Dict[str, int] = {}

    for split in splits:
        kwargs = {
            "path": dataset_id,
            "name": config_name,
            "split": split,
        }

        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)
        if revision:
            kwargs["revision"] = revision
        if hf_token:
            kwargs["token"] = hf_token

        dataset = load_dataset_with_retries(
            load_dataset=load_dataset,
            kwargs=kwargs,
            split=split,
            config_name=config_name,
            max_retries=max_retries,
            retry_initial_seconds=retry_initial_seconds,
            retry_max_seconds=retry_max_seconds,
            retry_jitter_seconds=retry_jitter_seconds,
        )

        split_rows = extract_split_rows(split, dataset)
        counts[split] = len(split_rows)
        all_rows.extend(split_rows)

    return all_rows, counts


def build_row_map(rows: Sequence[Tuple[str, str]], label: str) -> Tuple[Dict[str, str], List[str]]:
    row_map: Dict[str, str] = {}
    order: List[str] = []

    for uid, text in rows:
        if uid in row_map:
            raise ValueError(f"Duplicate sentence id in {label}: {uid}")
        row_map[uid] = text
        order.append(uid)

    return row_map, order


def align_parallel_rows(
    source_rows: Sequence[Tuple[str, str]],
    target_rows: Sequence[Tuple[str, str]],
) -> List[Tuple[str, str, str]]:
    source_map, source_order = build_row_map(source_rows, "source")
    target_map, _ = build_row_map(target_rows, "target")

    missing_in_target = [uid for uid in source_order if uid not in target_map]
    missing_in_source = [uid for uid in target_map if uid not in source_map]

    if missing_in_target or missing_in_source:
        sample_target = missing_in_target[:5]
        sample_source = missing_in_source[:5]
        raise ValueError(
            "Split/id alignment mismatch between source and target datasets. "
            f"Missing in target: {len(missing_in_target)} sample={sample_target}; "
            f"Missing in source: {len(missing_in_source)} sample={sample_source}."
        )

    aligned: List[Tuple[str, str, str]] = []
    for uid in source_order:
        aligned.append((uid, source_map[uid], target_map[uid]))

    return aligned


def write_jsonl(
    *,
    output_path: Path,
    aligned_rows: Sequence[Tuple[str, str, str]],
    source_key: str,
    target_key: str,
    include_id: bool,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output exists: {output_path}. Use --overwrite to replace it."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as handle:
        for uid, source_text, target_text in aligned_rows:
            record = {
                "translation": {
                    source_key: source_text,
                    target_key: target_text,
                }
            }
            if include_id:
                record["id"] = uid

            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    tmp_path.replace(output_path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def write_metadata(metadata_path: Path, payload: dict, overwrite: bool) -> None:
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(
            f"Metadata file exists: {metadata_path}. Use --overwrite to replace it."
        )

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    splits = parse_split_list(args.splits)

    hf_token = resolve_hf_token(args.hf_token, args.hf_token_file)
    output_dir = args.output_dir.expanduser().resolve()
    output_path = output_dir / args.output_file
    metadata_path = output_dir / args.metadata_file

    print("Downloading FLORES+ parallel data with strict alignment checks...")
    print(f"- dataset_id: {args.dataset_id}")
    print(f"- source_config: {args.source_config}")
    print(f"- target_config: {args.target_config}")
    print(f"- splits: {splits}")

    load_dataset, datasets_version, datasets_module_path = import_hf_datasets_load_dataset(PROJECT_ROOT)

    source_rows, source_counts = load_language_rows(
        load_dataset=load_dataset,
        dataset_id=args.dataset_id,
        config_name=args.source_config,
        splits=splits,
        cache_dir=args.cache_dir,
        revision=args.revision,
        hf_token=hf_token,
        max_retries=args.max_retries,
        retry_initial_seconds=args.retry_initial_seconds,
        retry_max_seconds=args.retry_max_seconds,
        retry_jitter_seconds=args.retry_jitter_seconds,
    )
    target_rows, target_counts = load_language_rows(
        load_dataset=load_dataset,
        dataset_id=args.dataset_id,
        config_name=args.target_config,
        splits=splits,
        cache_dir=args.cache_dir,
        revision=args.revision,
        hf_token=hf_token,
        max_retries=args.max_retries,
        retry_initial_seconds=args.retry_initial_seconds,
        retry_max_seconds=args.retry_max_seconds,
        retry_jitter_seconds=args.retry_jitter_seconds,
    )

    for split in splits:
        source_count = source_counts.get(split, 0)
        target_count = target_counts.get(split, 0)
        if source_count != target_count:
            raise ValueError(
                f"Split count mismatch for {split}: source={source_count}, target={target_count}"
            )

    aligned_rows = align_parallel_rows(source_rows, target_rows)

    if args.expected_total > 0 and len(aligned_rows) != args.expected_total:
        raise ValueError(
            f"Expected {args.expected_total} rows, got {len(aligned_rows)}. "
            "Set --expected-total 0 to disable strict count validation."
        )

    write_jsonl(
        output_path=output_path,
        aligned_rows=aligned_rows,
        source_key=args.source_key,
        target_key=args.target_key,
        include_id=args.include_id,
        overwrite=args.overwrite,
    )

    output_sha256 = sha256_file(output_path)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_id": args.dataset_id,
        "revision": args.revision,
        "source_config": args.source_config,
        "target_config": args.target_config,
        "source_key": args.source_key,
        "target_key": args.target_key,
        "splits": splits,
        "split_counts": {
            "source": source_counts,
            "target": target_counts,
        },
        "total_rows": len(aligned_rows),
        "expected_total": args.expected_total,
        "include_id": args.include_id,
        "output_jsonl": str(output_path),
        "output_sha256": output_sha256,
        "datasets_package": {
            "version": datasets_version,
            "module_path": datasets_module_path,
        },
    }

    write_metadata(metadata_path, metadata, overwrite=args.overwrite)

    print("Success: FLORES+ Cebuano-English dataset is ready.")
    print(f"- rows: {len(aligned_rows)}")
    print(f"- output: {output_path}")
    print(f"- metadata: {metadata_path}")
    print(f"- sha256: {output_sha256}")


if __name__ == "__main__":
    main()
