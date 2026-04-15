#!/usr/bin/env python3
"""Extract Chavacano-English parallel data from Hugging Face into strict JSONL.

Target output schema for every row:
{"translation": {"cbk": "...", "en": "..."}}

Sources:
1) Helsinki-NLP/tatoeba (cbk-en)
2) ajvicente/ChavacanoMT (cbk-eng)
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "datasets" / "raw" / "cbk"
DEFAULT_OUTPUT_FILE = "FINAL_cbk_en_raw.jsonl"
DEFAULT_METADATA_FILE = "FINAL_cbk_en_raw.meta.json"

LOCAL_TATOEBA_CBK_CANDIDATES = (
    PROJECT_ROOT / "datasets" / "raw" / "02_Chavacano" / "tatoeba_extracted" / "Tatoeba.cbk-en.cbk",
    PROJECT_ROOT / "datasets" / "raw" / "02_Chavacano" / "Tatoeba.cbk-en.cbk",
)
LOCAL_TATOEBA_EN_CANDIDATES = (
    PROJECT_ROOT / "datasets" / "raw" / "02_Chavacano" / "tatoeba_extracted" / "Tatoeba.cbk-en.en",
    PROJECT_ROOT / "datasets" / "raw" / "02_Chavacano" / "Tatoeba.cbk-en.en",
)


@dataclass
class SourceStats:
    source_name: str
    loaded: bool = False
    raw_rows: int = 0
    accepted_rows: int = 0
    dropped_invalid: int = 0
    dropped_duplicate: int = 0
    errors: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract and standardize Chavacano-English sentence pairs from Hugging Face "
            "datasets into strict NLLB JSONL schema."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output JSONL file name (default: {DEFAULT_OUTPUT_FILE}).",
    )
    parser.add_argument(
        "--metadata-file",
        default=DEFAULT_METADATA_FILE,
        help=f"Metadata JSON file name (default: {DEFAULT_METADATA_FILE}).",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="Optional Hugging Face token. Falls back to HF_TOKEN-like env vars.",
    )
    parser.add_argument(
        "--hf-token-file",
        type=Path,
        default=None,
        help="Optional file containing Hugging Face token on first non-empty line.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional datasets cache directory.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional dataset revision/tag/commit.",
    )
    parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Disable streaming mode and load full split in-memory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output and metadata files if they already exist.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Maximum retry attempts for transient HF errors (default: 4).",
    )
    parser.add_argument(
        "--retry-initial-seconds",
        type=float,
        default=2.0,
        help="Initial retry backoff in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--retry-max-seconds",
        type=float,
        default=30.0,
        help="Maximum retry backoff in seconds (default: 30.0).",
    )
    return parser.parse_args()


def resolve_hf_token(explicit_token: str | None, token_file: Path | None) -> str | None:
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    if token_file is not None:
        token_path = token_file.expanduser().resolve()
        if token_path.is_file():
            try:
                for raw_line in token_path.read_text(encoding="utf-8").splitlines():
                    candidate = raw_line.strip().strip('"').strip("'")
                    if candidate:
                        return candidate
            except OSError:
                pass

    for env_name in ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()

    return None


def import_hf_symbols(project_root: Path):
    """Import datasets and huggingface_hub symbols safely (avoid local shadowing)."""
    original_sys_path = list(sys.path)
    sanitized: list[str] = []

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
        hf_hub_mod = importlib.import_module("huggingface_hub")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing dependency. Install with: pip install datasets huggingface_hub"
        ) from exc
    finally:
        sys.path = original_sys_path

    if not hasattr(datasets_mod, "load_dataset"):
        raise ImportError(
            "Imported datasets module has no load_dataset attribute; local shadowing may exist."
        )
    if not hasattr(hf_hub_mod, "login"):
        raise ImportError("Imported huggingface_hub module has no login attribute.")

    return (
        datasets_mod.load_dataset,
        hf_hub_mod.login,
        str(getattr(datasets_mod, "__version__", "unknown")),
        str(getattr(datasets_mod, "__file__", "unknown")),
    )


def is_transient_hf_error(exc: Exception) -> bool:
    text = str(exc).casefold()
    patterns = (
        "429",
        "too many requests",
        "rate limit",
        "timed out",
        "timeout",
        "temporary failure",
        "connection reset",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "connection aborted",
    )
    return any(marker in text for marker in patterns)


def call_load_dataset(load_dataset, kwargs: dict[str, Any]):
    """Call load_dataset while handling token/use_auth_token compatibility."""
    try:
        return load_dataset(**kwargs)
    except TypeError as exc:
        if "token" not in str(exc):
            raise
        token = kwargs.pop("token", None)
        if token:
            kwargs["use_auth_token"] = token
        return load_dataset(**kwargs)


def load_dataset_with_retries(
    *,
    load_dataset,
    kwargs: dict[str, Any],
    source_name: str,
    max_retries: int,
    retry_initial_seconds: float,
    retry_max_seconds: float,
):
    attempts = max(1, max_retries)
    wait_seconds = max(0.0, retry_initial_seconds)

    for attempt in range(1, attempts + 1):
        try:
            return call_load_dataset(load_dataset, dict(kwargs))
        except Exception as exc:
            lowered = str(exc).casefold()

            # Fail fast with clear guidance for known hard failures.
            if "dataset scripts are no longer supported" in lowered:
                raise RuntimeError(
                    "Installed datasets package blocks script-based dataset repos. "
                    "Use a datasets 3.x compatible runtime or a parquet/native source mirror."
                ) from exc

            if "gated dataset" in lowered or "must be authenticated" in lowered:
                raise PermissionError(
                    f"{source_name} is gated and requires a valid HF token with accepted access terms."
                ) from exc

            if attempt >= attempts or not is_transient_hf_error(exc):
                raise

            jitter = random.uniform(0.0, 0.75)
            sleep_for = min(max(0.0, retry_max_seconds), wait_seconds + jitter)
            print(
                f"[retry] source={source_name} attempt={attempt}/{attempts} "
                f"waiting={sleep_for:.1f}s after transient error"
            )
            time.sleep(sleep_for)
            wait_seconds = min(max(0.0, retry_max_seconds), max(1.0, wait_seconds * 2.0))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def valid_pair(cbk_text: str, en_text: str) -> bool:
    return len(cbk_text) > 2 and len(en_text) > 2


def pair_key(cbk_text: str, en_text: str) -> str:
    return json.dumps(
        {"cbk": cbk_text.casefold(), "en": en_text.casefold()},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def extract_pair_from_row(row: dict[str, Any]) -> tuple[str, str] | None:
    if not isinstance(row, dict):
        return None

    # Variant 1: nested translation contract.
    translation = row.get("translation")
    if isinstance(translation, dict):
        cbk_text = translation.get("cbk") or translation.get("chavacano")
        en_text = translation.get("en") or translation.get("eng") or translation.get("english")
        if isinstance(cbk_text, str) and isinstance(en_text, str):
            return cbk_text, en_text

    # Variant 2: common flat keys from academic sets.
    cbk_candidates = (
        row.get("cbk"),
        row.get("chavacano"),
        row.get("source_text"),
        row.get("source"),
        row.get("src"),
    )
    en_candidates = (
        row.get("en"),
        row.get("english"),
        row.get("eng"),
        row.get("target_text"),
        row.get("target"),
        row.get("tgt"),
    )

    cbk_text = next((item for item in cbk_candidates if isinstance(item, str)), None)
    en_text = next((item for item in en_candidates if isinstance(item, str)), None)

    if isinstance(cbk_text, str) and isinstance(en_text, str):
        return cbk_text, en_text

    return None


def write_jsonl_atomic(path: Path, records: Sequence[dict], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Output exists: {path}. Use --overwrite to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    tmp_path.replace(path)


def write_metadata(path: Path, payload: dict, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Metadata exists: {path}. Use --overwrite to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_source(
    *,
    load_dataset,
    source_name: str,
    dataset_kwargs: dict[str, Any],
    unique_keys: set[str],
    records: list[dict],
    max_retries: int,
    retry_initial_seconds: float,
    retry_max_seconds: float,
) -> SourceStats:
    stats = SourceStats(source_name=source_name)

    try:
        dataset_rows = load_dataset_with_retries(
            load_dataset=load_dataset,
            kwargs=dataset_kwargs,
            source_name=source_name,
            max_retries=max_retries,
            retry_initial_seconds=retry_initial_seconds,
            retry_max_seconds=retry_max_seconds,
        )
        stats.loaded = True
    except Exception as exc:
        stats.errors += 1
        print(f"[warn] source={source_name} failed to load: {exc}")

        # Fallback 1: Use locally staged OPUS Tatoeba files when script-based
        # dataset loading is blocked by current datasets package.
        if source_name == "tatoeba_cbk_en":
            fallback_stats = process_tatoeba_local_fallback(
                source_name=source_name,
                unique_keys=unique_keys,
                records=records,
            )
            if fallback_stats.loaded:
                fallback_stats.errors += stats.errors
                return fallback_stats

        # Fallback 2: Load gated ChavacanoMT cbk-en text file directly from HF.
        if source_name == "chavacanomt_cbk_eng":
            fallback_stats = process_chavacanomt_text_fallback(
                load_dataset=load_dataset,
                source_name=source_name,
                streaming=bool(dataset_kwargs.get("streaming", True)),
                cache_dir=dataset_kwargs.get("cache_dir"),
                revision=dataset_kwargs.get("revision"),
                hf_token=dataset_kwargs.get("token") or dataset_kwargs.get("use_auth_token"),
                unique_keys=unique_keys,
                records=records,
                max_retries=max_retries,
                retry_initial_seconds=retry_initial_seconds,
                retry_max_seconds=retry_max_seconds,
            )
            if fallback_stats.loaded:
                fallback_stats.errors += stats.errors
                return fallback_stats

        return stats

    for row in dataset_rows:
        stats.raw_rows += 1

        pair = extract_pair_from_row(row)
        if pair is None:
            stats.dropped_invalid += 1
            continue

        cbk_text, en_text = pair
        cbk_clean = normalize_text(cbk_text)
        en_clean = normalize_text(en_text)

        if not valid_pair(cbk_clean, en_clean):
            stats.dropped_invalid += 1
            continue

        key = pair_key(cbk_clean, en_clean)
        if key in unique_keys:
            stats.dropped_duplicate += 1
            continue

        unique_keys.add(key)
        records.append(
            {
                "translation": {
                    "cbk": cbk_clean,
                    "en": en_clean,
                }
            }
        )
        stats.accepted_rows += 1

    return stats


def resolve_existing_parallel_files(
    cbk_candidates: Sequence[Path],
    en_candidates: Sequence[Path],
) -> tuple[Path, Path] | None:
    for cbk_path, en_path in zip(cbk_candidates, en_candidates):
        if cbk_path.is_file() and en_path.is_file():
            return cbk_path, en_path
    return None


def process_tatoeba_local_fallback(
    *,
    source_name: str,
    unique_keys: set[str],
    records: list[dict],
) -> SourceStats:
    stats = SourceStats(source_name=source_name)
    pair = resolve_existing_parallel_files(
        LOCAL_TATOEBA_CBK_CANDIDATES,
        LOCAL_TATOEBA_EN_CANDIDATES,
    )
    if pair is None:
        stats.errors += 1
        print("[warn] local Tatoeba fallback files not found.")
        return stats

    cbk_path, en_path = pair
    print(f"[fallback] source={source_name} using local files: {cbk_path.name} + {en_path.name}")

    with cbk_path.open("r", encoding="utf-8", errors="replace") as cbk_file, en_path.open(
        "r", encoding="utf-8", errors="replace"
    ) as en_file:
        stats.loaded = True
        for cbk_line, en_line in zip_longest(cbk_file, en_file):
            stats.raw_rows += 1

            if cbk_line is None or en_line is None:
                stats.dropped_invalid += 1
                continue

            cbk_clean = normalize_text(cbk_line)
            en_clean = normalize_text(en_line)

            if not valid_pair(cbk_clean, en_clean):
                stats.dropped_invalid += 1
                continue

            key = pair_key(cbk_clean, en_clean)
            if key in unique_keys:
                stats.dropped_duplicate += 1
                continue

            unique_keys.add(key)
            records.append(
                {
                    "translation": {
                        "cbk": cbk_clean,
                        "en": en_clean,
                    }
                }
            )
            stats.accepted_rows += 1

    return stats


def parse_chavacanomt_cbk_en_line(line: str) -> tuple[str, str] | None:
    text = normalize_text(line)
    if not text:
        return None

    # Most rows are tab-separated: cbk<TAB>en
    if "\t" in text:
        left, right = text.split("\t", 1)
        return left, right

    # Conservative fallback for occasional delimiter drift.
    for delim in (" ||| ", "\u241f", "\u001f"):
        if delim in text:
            left, right = text.split(delim, 1)
            return left, right

    return None


def process_chavacanomt_text_fallback(
    *,
    load_dataset,
    source_name: str,
    streaming: bool,
    cache_dir: str | None,
    revision: str | None,
    hf_token: str | None,
    unique_keys: set[str],
    records: list[dict],
    max_retries: int,
    retry_initial_seconds: float,
    retry_max_seconds: float,
) -> SourceStats:
    stats = SourceStats(source_name=source_name)
    text_url = "hf://datasets/ajvicente/ChavacanoMT/cbk-en.txt"

    kwargs: dict[str, Any] = {
        "path": "text",
        "data_files": {"train": text_url},
        "split": "train",
        "streaming": streaming,
    }
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    if revision:
        kwargs["revision"] = revision
    if hf_token:
        kwargs["token"] = hf_token

    try:
        dataset_rows = load_dataset_with_retries(
            load_dataset=load_dataset,
            kwargs=kwargs,
            source_name=f"{source_name}_text_fallback",
            max_retries=max_retries,
            retry_initial_seconds=retry_initial_seconds,
            retry_max_seconds=retry_max_seconds,
        )
        stats.loaded = True
        print(f"[fallback] source={source_name} using hf text file: {text_url}")
    except Exception as exc:
        stats.errors += 1
        print(f"[warn] source={source_name} text fallback failed: {exc}")
        return stats

    try:
        for row in dataset_rows:
            stats.raw_rows += 1
            raw_text = row.get("text") if isinstance(row, dict) else None
            if not isinstance(raw_text, str):
                stats.dropped_invalid += 1
                continue

            pair = parse_chavacanomt_cbk_en_line(raw_text)
            if pair is None:
                stats.dropped_invalid += 1
                continue

            cbk_text, en_text = pair
            cbk_clean = normalize_text(cbk_text)
            en_clean = normalize_text(en_text)

            if not valid_pair(cbk_clean, en_clean):
                stats.dropped_invalid += 1
                continue

            key = pair_key(cbk_clean, en_clean)
            if key in unique_keys:
                stats.dropped_duplicate += 1
                continue

            unique_keys.add(key)
            records.append(
                {
                    "translation": {
                        "cbk": cbk_clean,
                        "en": en_clean,
                    }
                }
            )
            stats.accepted_rows += 1
    except Exception as exc:
        # Gated repos can raise during the first streamed read even if dataset object creation succeeds.
        stats.errors += 1
        print(f"[warn] source={source_name} text fallback stream failed: {exc}")

    return stats


def main() -> None:
    args = parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_path = output_dir / args.output_file
    metadata_path = output_dir / args.metadata_file

    hf_token = resolve_hf_token(args.hf_token, args.hf_token_file)
    load_dataset, hf_login, datasets_version, datasets_module_path = import_hf_symbols(PROJECT_ROOT)

    print("Starting Chavacano-English master extraction via Hugging Face API...")
    print(f"- output_path: {output_path}")
    print(f"- metadata_path: {metadata_path}")
    print(f"- datasets_version: {datasets_version}")
    print(f"- datasets_module: {datasets_module_path}")
    print(f"- streaming: {not args.no_streaming}")

    if hf_token:
        try:
            hf_login(token=hf_token, add_to_git_credential=False)
            print("- hf_auth: token detected and login succeeded")
        except Exception as exc:
            print(f"[warn] hf login failed; proceeding with token-based dataset calls: {exc}")
    else:
        print("[warn] HF token not found. Public datasets may still work, gated ones may fail.")

    common_kwargs: dict[str, Any] = {
        "split": "train",
        "streaming": not args.no_streaming,
    }
    if args.cache_dir is not None:
        common_kwargs["cache_dir"] = str(args.cache_dir.expanduser().resolve())
    if args.revision:
        common_kwargs["revision"] = args.revision
    if hf_token:
        common_kwargs["token"] = hf_token

    sources: list[tuple[str, dict[str, Any]]] = [
        (
            "tatoeba_cbk_en",
            {
                **common_kwargs,
                "path": "Helsinki-NLP/tatoeba",
                "lang1": "cbk",
                "lang2": "en",
            },
        ),
        (
            "chavacanomt_cbk_eng",
            {
                **common_kwargs,
                "path": "ajvicente/ChavacanoMT",
                "name": "cbk-eng",
            },
        ),
    ]

    unique_keys: set[str] = set()
    master_records: list[dict] = []
    source_stats: list[SourceStats] = []

    for source_name, kwargs in sources:
        print(f"[extract] source={source_name} ...")
        stats = process_source(
            load_dataset=load_dataset,
            source_name=source_name,
            dataset_kwargs=kwargs,
            unique_keys=unique_keys,
            records=master_records,
            max_retries=args.max_retries,
            retry_initial_seconds=args.retry_initial_seconds,
            retry_max_seconds=args.retry_max_seconds,
        )
        source_stats.append(stats)
        print(
            f"[extract] source={source_name} raw={stats.raw_rows} accepted={stats.accepted_rows} "
            f"dropped_invalid={stats.dropped_invalid} dropped_duplicate={stats.dropped_duplicate} "
            f"loaded={stats.loaded} errors={stats.errors}"
        )

    if not master_records:
        raise RuntimeError("No valid sentence pairs extracted from any source.")

    write_jsonl_atomic(output_path, master_records, overwrite=args.overwrite)

    totals = {
        "raw_rows": sum(item.raw_rows for item in source_stats),
        "accepted_rows": sum(item.accepted_rows for item in source_stats),
        "dropped_invalid": sum(item.dropped_invalid for item in source_stats),
        "dropped_duplicate": sum(item.dropped_duplicate for item in source_stats),
        "errors": sum(item.errors for item in source_stats),
    }

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_path": str(output_path),
        "output_rows": len(master_records),
        "schema": {"translation": {"cbk": "string", "en": "string"}},
        "datasets_package": {
            "version": datasets_version,
            "module_path": datasets_module_path,
        },
        "sources": [
            {
                "source_name": item.source_name,
                "loaded": item.loaded,
                "raw_rows": item.raw_rows,
                "accepted_rows": item.accepted_rows,
                "dropped_invalid": item.dropped_invalid,
                "dropped_duplicate": item.dropped_duplicate,
                "errors": item.errors,
            }
            for item in source_stats
        ],
        "totals": totals,
    }
    write_metadata(metadata_path, metadata, overwrite=args.overwrite)

    print("EXTRACTION_COMPLETE")
    print(f"- output_rows={len(master_records)}")
    print(f"- output_path={output_path}")
    print(f"- metadata_path={metadata_path}")


if __name__ == "__main__":
    main()