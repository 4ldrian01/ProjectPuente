#!/usr/bin/env python3
"""Download and clean CCAligned Cebuano-English sentence pairs.

Primary path (as required):
    load_dataset("ahelk/ccaligned_multilingual", ...)

Compatibility path:
    If the installed `datasets` package rejects script-based datasets,
    automatically fall back to streaming the official CCAligned TSV URL via
    `load_dataset("csv", ...)` while preserving the same cleaning contract.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_ID = "ahelk/ccaligned_multilingual"
DEFAULT_CONFIG = "sentences-cx_PH"
DEFAULT_SPLIT = "train"
DEFAULT_CEBUANO_CODE = "cx_PH"
DEFAULT_TARGET_PAIRS = 8000
DEFAULT_PROGRESS_EVERY = 1000
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "datasets" / "raw" / "ceb" / "ccaligned_ceb_en_cleaned.jsonl"
)

URL_REGEX = re.compile(r"(https?://|www\.)", flags=re.IGNORECASE)
WORD_REGEX = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", flags=re.UNICODE)

# Required web boilerplate markers from prompt (case-insensitive matching).
BOILERPLATE_MARKERS = (
    "copyright",
    "all rights reserved",
    "click here",
    "read more",
    "menu",
    "log in",
    "sign up",
    "subscribe",
)


@dataclass
class FilterStats:
    raw_rows_processed: int = 0
    kept_pairs: int = 0
    dropped_schema: int = 0
    dropped_empty: int = 0
    dropped_url: int = 0
    dropped_boilerplate: int = 0
    dropped_short: int = 0
    dropped_ratio: int = 0
    dropped_duplicate: int = 0

    @property
    def dropped_total(self) -> int:
        return (
            self.dropped_schema
            + self.dropped_empty
            + self.dropped_url
            + self.dropped_boilerplate
            + self.dropped_short
            + self.dropped_ratio
            + self.dropped_duplicate
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download Cebuano-English CCAligned data, remove web-scrape garbage, "
            "and write strict translation JSONL."
        )
    )
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_DATASET_ID,
        help=f"Hugging Face dataset id (default: {DEFAULT_DATASET_ID}).",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=(
            "Primary Hugging Face config candidate (default: sentences-cx_PH). "
            "The script also tries Cebuano config fallbacks automatically."
        ),
    )
    parser.add_argument(
        "--split",
        default=DEFAULT_SPLIT,
        help=f"Dataset split to stream (default: {DEFAULT_SPLIT}).",
    )
    parser.add_argument(
        "--cebuano-code",
        default=DEFAULT_CEBUANO_CODE,
        help=(
            "CCAligned language code for Cebuano pair discovery (default: cx_PH). "
            "Used for config fallback and URL compatibility mode."
        ),
    )
    parser.add_argument(
        "--target-pairs",
        type=int,
        default=DEFAULT_TARGET_PAIRS,
        help=f"Exact number of clean pairs to keep (default: {DEFAULT_TARGET_PAIRS}).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=(
            "Print progress each time this many clean pairs are retained "
            f"(default: {DEFAULT_PROGRESS_EVERY})."
        ),
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=3,
        help="Drop row if either side has fewer than this many words (default: 3).",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.5,
        help="Minimum allowed en/ceb word ratio (default: 0.5).",
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=2.0,
        help="Maximum allowed en/ceb word ratio (default: 2.0).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional Hugging Face datasets cache directory.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional dataset revision/tag/commit.",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="Optional Hugging Face token. Falls back to HF_TOKEN-style env vars.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output if it already exists.",
    )
    parser.add_argument(
        "--disable-url-fallback",
        action="store_true",
        help="Disable URL fallback mode if HF script loading is unsupported.",
    )
    return parser.parse_args()


def resolve_hf_token(explicit_token: str | None) -> str | None:
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    for env_name in ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_TOKEN"):
        env_value = os.getenv(env_name)
        if env_value and env_value.strip():
            return env_value.strip()

    return None


def import_hf_datasets_load_dataset(project_root: Path):
    """Import datasets.load_dataset safely, avoiding local datasets/ shadowing."""
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
        str(getattr(datasets_mod, "__version__", "unknown")),
        str(getattr(datasets_mod, "__file__", "unknown")),
    )


def call_load_dataset(load_dataset, kwargs: dict[str, Any]):
    """Call load_dataset with compatibility fallback for token arg naming."""
    try:
        return load_dataset(**kwargs)
    except TypeError as exc:
        if "token" not in str(exc):
            raise
        token = kwargs.pop("token", None)
        if token:
            kwargs["use_auth_token"] = token
        return load_dataset(**kwargs)


def build_config_candidates(primary_config: str, cebuano_code: str) -> list[str]:
    raw_candidates: Sequence[str] = (
        primary_config,
        f"sentences-{cebuano_code}",
        f"documents-{cebuano_code}",
        cebuano_code,
        f"sentences-{cebuano_code.casefold()}",
        f"documents-{cebuano_code.casefold()}",
    )

    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_candidates:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def try_load_hf_stream(
    *,
    load_dataset,
    dataset_id: str,
    config_candidates: Sequence[str],
    split: str,
    cache_dir: Path | None,
    revision: str | None,
    hf_token: str | None,
) -> tuple[Iterable[dict[str, Any]], str]:
    errors: list[str] = []

    for config_name in config_candidates:
        kwargs: dict[str, Any] = {
            "path": dataset_id,
            "name": config_name,
            "split": split,
            "streaming": True,
        }
        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)
        if revision:
            kwargs["revision"] = revision
        if hf_token:
            kwargs["token"] = hf_token

        try:
            dataset_stream = call_load_dataset(load_dataset, kwargs)
            print(
                "Source mode: huggingface-dataset "
                f"dataset={dataset_id} config={config_name} split={split}"
            )
            return dataset_stream, config_name
        except Exception as exc:
            errors.append(f"{config_name}: {exc}")
            lowered = str(exc).casefold()
            if "dataset scripts are no longer supported" in lowered:
                # No need to continue trying more configs in this runtime.
                break

    error_preview = "\n  - " + "\n  - ".join(errors[:6]) if errors else ""
    raise RuntimeError(
        "Unable to stream from Hugging Face dataset configs." + error_preview
    )


def try_load_ccaligned_url_stream(
    *,
    load_dataset,
    cebuano_code: str,
    cache_dir: Path | None,
) -> tuple[Iterable[dict[str, Any]], str, str]:
    base = "https://data.statmt.org/cc-aligned/sentence-aligned"
    url_candidates = (
        f"{base}/en_XX-{cebuano_code}.tsv.xz",
        f"{base}/{cebuano_code}-en_XX.tsv.xz",
    )

    errors: list[str] = []
    for url in url_candidates:
        kwargs: dict[str, Any] = {
            "path": "csv",
            "data_files": {"train": url},
            "split": "train",
            "delimiter": "\t",
            "column_names": ["col0", "col1", "laser_similarity"],
            "streaming": True,
        }
        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)

        try:
            stream = call_load_dataset(load_dataset, kwargs)
            iterator = iter(stream)
            first_row = next(iterator)

            def iter_rows() -> Iterable[dict[str, Any]]:
                yield first_row
                for item in iterator:
                    yield item

            mode = "csv_en_first" if "/en_XX-" in url else "csv_ceb_first"
            print(
                "Source mode: ccaligned-url-fallback "
                f"url={url} orientation={mode}"
            )
            return iter_rows(), mode, url
        except StopIteration:
            errors.append(f"{url}: dataset stream is empty")
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    error_preview = "\n  - " + "\n  - ".join(errors[:6]) if errors else ""
    raise RuntimeError(
        "Unable to stream Cebuano CCAligned sentence URL candidates." + error_preview
    )


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(ch for ch in normalized if ch.isprintable() or ch.isspace())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def word_count(text: str) -> int:
    return len(WORD_REGEX.findall(text))


def normalize_lang_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", tag.casefold())


def extract_pair_from_hf_row(
    row: dict[str, Any],
    cebuano_code: str,
) -> tuple[str, str] | None:
    translation = row.get("translation") if isinstance(row, dict) else None
    if not isinstance(translation, dict):
        # Secondary fallback in case fields are flattened.
        en_text = row.get("en") if isinstance(row, dict) else None
        ceb_text = row.get("ceb") if isinstance(row, dict) else None
        if isinstance(en_text, str) and isinstance(ceb_text, str):
            return ceb_text, en_text
        return None

    cebuano_norm = normalize_lang_tag(cebuano_code)
    cebuano_aliases = {
        cebuano_norm,
        "ceb",
        "cebuano",
        "bisaya",
        "cxph",
        "cx",
    }

    en_key: str | None = None
    ceb_key: str | None = None

    for key in translation.keys():
        key_norm = normalize_lang_tag(str(key))
        if en_key is None and key_norm.startswith("en"):
            en_key = str(key)
        if ceb_key is None and key_norm in cebuano_aliases:
            ceb_key = str(key)

    # If there is an English key and only one other key, treat it as paired language.
    if en_key is not None and ceb_key is None and len(translation) == 2:
        for key in translation.keys():
            if str(key) != en_key:
                ceb_key = str(key)
                break

    if en_key is None or ceb_key is None:
        return None

    en_text = translation.get(en_key)
    ceb_text = translation.get(ceb_key)
    if not isinstance(en_text, str) or not isinstance(ceb_text, str):
        return None

    return ceb_text, en_text


def extract_pair(
    row: dict[str, Any],
    *,
    source_mode: str,
    cebuano_code: str,
) -> tuple[str, str] | None:
    if source_mode == "hf":
        return extract_pair_from_hf_row(row, cebuano_code)

    col0 = row.get("col0") if isinstance(row, dict) else None
    col1 = row.get("col1") if isinstance(row, dict) else None
    if not isinstance(col0, str) or not isinstance(col1, str):
        return None

    if source_mode == "csv_en_first":
        return col1, col0
    if source_mode == "csv_ceb_first":
        return col0, col1

    return None


def classify_drop_reason(
    *,
    ceb_text: str,
    en_text: str,
    min_words: int,
    min_ratio: float,
    max_ratio: float,
) -> str | None:
    if not ceb_text or not en_text:
        return "empty"

    if URL_REGEX.search(ceb_text) or URL_REGEX.search(en_text):
        return "url"

    ceb_lower = ceb_text.casefold()
    en_lower = en_text.casefold()
    if any(marker in ceb_lower for marker in BOILERPLATE_MARKERS) or any(
        marker in en_lower for marker in BOILERPLATE_MARKERS
    ):
        return "boilerplate"

    ceb_words = word_count(ceb_text)
    en_words = word_count(en_text)
    if ceb_words < min_words or en_words < min_words:
        return "short"

    if ceb_words == 0:
        return "short"

    ratio = en_words / ceb_words
    if ratio < min_ratio or ratio > max_ratio:
        return "ratio"

    return None


def write_translation_record(handle, ceb_text: str, en_text: str) -> None:
    payload = {"translation": {"ceb": ceb_text, "en": en_text}}
    handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    handle.write("\n")


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main() -> None:
    args = parse_args()

    if args.target_pairs <= 0:
        raise ValueError("--target-pairs must be greater than 0.")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be greater than 0.")
    if args.min_words <= 0:
        raise ValueError("--min-words must be greater than 0.")
    if args.min_ratio <= 0 or args.max_ratio <= 0 or args.min_ratio > args.max_ratio:
        raise ValueError("Invalid ratio bounds: require 0 < min-ratio <= max-ratio.")

    output_path = args.output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --overwrite to replace it."
        )

    hf_token = resolve_hf_token(args.hf_token)

    load_dataset, datasets_version, datasets_module = import_hf_datasets_load_dataset(
        PROJECT_ROOT
    )

    print("Starting CCAligned Cebuano-English extraction and cleaning...")
    print(f"- dataset_id: {args.dataset_id}")
    print(f"- target_pairs: {args.target_pairs}")
    print(f"- output_path: {output_path}")
    print(f"- datasets_version: {datasets_version}")
    print(f"- datasets_module: {datasets_module}")

    config_candidates = build_config_candidates(args.config, args.cebuano_code)
    source_mode = "hf"
    source_label = ""

    try:
        row_stream, used_config = try_load_hf_stream(
            load_dataset=load_dataset,
            dataset_id=args.dataset_id,
            config_candidates=config_candidates,
            split=args.split,
            cache_dir=args.cache_dir,
            revision=args.revision,
            hf_token=hf_token,
        )
        source_mode = "hf"
        source_label = f"config={used_config} split={args.split}"
    except Exception as hf_exc:
        if args.disable_url_fallback:
            raise
        print(
            "[warning] Hugging Face config loading failed. "
            "Switching to CCAligned sentence URL fallback."
        )
        print(f"[warning] root_cause: {hf_exc}")
        row_stream, source_mode, used_url = try_load_ccaligned_url_stream(
            load_dataset=load_dataset,
            cebuano_code=args.cebuano_code,
            cache_dir=args.cache_dir,
        )
        source_label = used_url

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    stats = FilterStats()
    seen_pairs: set[tuple[str, str]] = set()
    started_at = time.time()

    try:
        with tmp_path.open("w", encoding="utf-8") as out_file:
            for row in row_stream:
                stats.raw_rows_processed += 1

                pair = extract_pair(
                    row,
                    source_mode=source_mode,
                    cebuano_code=args.cebuano_code,
                )
                if pair is None:
                    stats.dropped_schema += 1
                    continue

                ceb_text, en_text = pair
                ceb_clean = normalize_text(ceb_text)
                en_clean = normalize_text(en_text)

                reason = classify_drop_reason(
                    ceb_text=ceb_clean,
                    en_text=en_clean,
                    min_words=args.min_words,
                    min_ratio=args.min_ratio,
                    max_ratio=args.max_ratio,
                )

                if reason == "empty":
                    stats.dropped_empty += 1
                    continue
                if reason == "url":
                    stats.dropped_url += 1
                    continue
                if reason == "boilerplate":
                    stats.dropped_boilerplate += 1
                    continue
                if reason == "short":
                    stats.dropped_short += 1
                    continue
                if reason == "ratio":
                    stats.dropped_ratio += 1
                    continue

                pair_key = (ceb_clean.casefold(), en_clean.casefold())
                if pair_key in seen_pairs:
                    stats.dropped_duplicate += 1
                    continue

                seen_pairs.add(pair_key)
                write_translation_record(out_file, ceb_clean, en_clean)
                stats.kept_pairs += 1

                if stats.kept_pairs % args.progress_every == 0:
                    print(
                        f"Filtered {stats.kept_pairs} pairs... "
                        f"raw_processed={stats.raw_rows_processed} "
                        f"dropped={stats.dropped_total}"
                    )

                if stats.kept_pairs >= args.target_pairs:
                    break

        if stats.kept_pairs != args.target_pairs:
            raise RuntimeError(
                "Unable to collect the requested number of clean pairs. "
                f"target={args.target_pairs}, collected={stats.kept_pairs}, "
                f"raw_processed={stats.raw_rows_processed}, dropped={stats.dropped_total}"
            )

        tmp_path.replace(output_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    elapsed = time.time() - started_at
    final_lines = count_lines(output_path)
    if final_lines != stats.kept_pairs:
        raise RuntimeError(
            "Post-write integrity check failed: "
            f"line_count={final_lines}, kept_pairs={stats.kept_pairs}"
        )

    print("CCALIGNED_CEB_DOWNLOAD_AND_CLEAN_COMPLETE")
    print(f"source={source_label}")
    print(f"raw_rows_processed={stats.raw_rows_processed}")
    print(f"dropped_total={stats.dropped_total}")
    print(f"dropped_schema={stats.dropped_schema}")
    print(f"dropped_empty={stats.dropped_empty}")
    print(f"dropped_url={stats.dropped_url}")
    print(f"dropped_boilerplate={stats.dropped_boilerplate}")
    print(f"dropped_short={stats.dropped_short}")
    print(f"dropped_ratio={stats.dropped_ratio}")
    print(f"dropped_duplicate={stats.dropped_duplicate}")
    print(f"kept_pairs={stats.kept_pairs}")
    print(f"output_lines={final_lines}")
    print(f"output_path={output_path}")
    print(f"elapsed_seconds={elapsed:.2f}")


if __name__ == "__main__":
    main()