#!/usr/bin/env python3
"""Build a high-purity Cebuano-English dataset from CCAligned (v3 rules).

Primary required path:
    load_dataset("ahelk/ccaligned_multilingual", language_code="ceb_XX", ...)

Compatibility path:
    Some `datasets` versions reject script-based dataset repos. In that case,
    this script falls back to CCAligned sentence URLs using
    load_dataset("csv", ...), while preserving the exact cleaning rules.
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
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from langdetect import DetectorFactory, LangDetectException, detect
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency: langdetect. Install it with: pip install langdetect"
    ) from exc

# Make language detection reproducible across runs/processes.
DetectorFactory.seed = 0


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATASET_ID = "ahelk/ccaligned_multilingual"
DEFAULT_LANGUAGE_CODE = "ceb_XX"
DEFAULT_SPLIT = "train"
DEFAULT_TARGET_PAIRS = 5000
DEFAULT_PROGRESS_EVERY = 500
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "datasets" / "raw" / "ceb" / "ccaligned_v3_perfect.jsonl"
)

URL_REGEX = re.compile(r"(?:https?://|www\.)", flags=re.IGNORECASE)

# Aggressive numeric detection, including spaced numeric runs.
SPACED_NUMERIC_REGEX = re.compile(r"(?:\d[\s().,\-/]*){6,}\d")

BLOCK_TERMS = (
    "copyright",
    "rights reserved",
    "cookie",
    "login",
    "password",
    "subscribe",
    "category",
    "casino",
)

SYMBOL_BLOCKLIST = {"©", "™", "®", "+", "@", "%", "$", "€", "₽"}


@dataclass
class FilterStats:
    raw_rows_processed: int = 0
    kept_pairs: int = 0

    dropped_schema: int = 0
    dropped_empty: int = 0
    dropped_url: int = 0
    dropped_ui_copyright: int = 0
    dropped_symbol: int = 0
    dropped_digit_density: int = 0
    dropped_numeric_pattern: int = 0
    dropped_language: int = 0
    dropped_duplicate: int = 0

    @property
    def dropped_total(self) -> int:
        return (
            self.dropped_schema
            + self.dropped_empty
            + self.dropped_url
            + self.dropped_ui_copyright
            + self.dropped_symbol
            + self.dropped_digit_density
            + self.dropped_numeric_pattern
            + self.dropped_language
            + self.dropped_duplicate
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stream CCAligned Cebuano-English data and apply v3 ultra-strict "
            "langdetect + regex cleaning rules."
        )
    )
    parser.add_argument(
        "--dataset-id",
        default=DEFAULT_DATASET_ID,
        help=f"Hugging Face dataset id (default: {DEFAULT_DATASET_ID}).",
    )
    parser.add_argument(
        "--language-code",
        default=DEFAULT_LANGUAGE_CODE,
        help=f"Language code for load_dataset(..., language_code=...) (default: {DEFAULT_LANGUAGE_CODE}).",
    )
    parser.add_argument(
        "--split",
        default=DEFAULT_SPLIT,
        help=f"Split name to stream (default: {DEFAULT_SPLIT}).",
    )
    parser.add_argument(
        "--target-pairs",
        type=int,
        default=DEFAULT_TARGET_PAIRS,
        help=f"Exact number of accepted rows (default: {DEFAULT_TARGET_PAIRS}).",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSONL file path.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=f"Progress print interval in accepted rows (default: {DEFAULT_PROGRESS_EVERY}).",
    )
    parser.add_argument(
        "--digit-density-threshold",
        type=float,
        default=0.10,
        help="Drop row if digits exceed this ratio in either sentence (default: 0.10).",
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
        "--hf-token",
        default=None,
        help="Optional Hugging Face token. Falls back to HF_TOKEN-like env vars.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output file if it exists.",
    )
    parser.add_argument(
        "--disable-url-fallback",
        action="store_true",
        help="Disable URL fallback if direct HF dataset loading fails.",
    )
    return parser.parse_args()


def resolve_hf_token(explicit_token: str | None) -> str | None:
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    for env_name in ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()

    return None


def import_hf_datasets_load_dataset(project_root: Path):
    """Import datasets.load_dataset safely, avoiding local folder shadowing."""
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
    """Call load_dataset with compatibility fallback for token arg names."""
    try:
        return load_dataset(**kwargs)
    except TypeError as exc:
        if "token" not in str(exc):
            raise
        token = kwargs.pop("token", None)
        if token:
            kwargs["use_auth_token"] = token
        return load_dataset(**kwargs)


def normalize_lang_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", tag.casefold())


def language_code_candidates(requested: str) -> list[str]:
    raw_candidates = (
        requested,
        requested.strip().lower(),
        "ceb_XX",
        "ceb_xx",
        "cx_PH",
        "cx_ph",
        "ceb",
        "cx",
    )

    out: list[str] = []
    seen: set[str] = set()
    for item in raw_candidates:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def config_candidates(language_codes: Sequence[str]) -> list[str]:
    raw: list[str] = []
    for code in language_codes:
        raw.extend([f"sentences-{code}", f"documents-{code}", code])

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def try_load_hf_stream(
    *,
    load_dataset,
    dataset_id: str,
    split: str,
    language_codes: Sequence[str],
    cache_dir: Path | None,
    revision: str | None,
    hf_token: str | None,
) -> tuple[Iterable[dict[str, Any]], str]:
    errors: list[str] = []

    for code in language_codes:
        kwargs: dict[str, Any] = {
            "path": dataset_id,
            "language_code": code,
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
            stream = call_load_dataset(load_dataset, kwargs)
            label = f"language_code={code}"
            print(f"Source mode: huggingface-dataset {label} split={split}")
            return stream, label
        except Exception as exc:
            errors.append(f"language_code={code}: {exc}")
            if "dataset scripts are no longer supported" in str(exc).casefold():
                break

    for name in config_candidates(language_codes):
        kwargs = {
            "path": dataset_id,
            "name": name,
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
            stream = call_load_dataset(load_dataset, kwargs)
            label = f"name={name}"
            print(f"Source mode: huggingface-dataset {label} split={split}")
            return stream, label
        except Exception as exc:
            errors.append(f"name={name}: {exc}")
            if "dataset scripts are no longer supported" in str(exc).casefold():
                break

    preview = "\n  - " + "\n  - ".join(errors[:8]) if errors else ""
    raise RuntimeError("HF dataset loading attempts failed." + preview)


def try_load_url_fallback(
    *,
    load_dataset,
    language_codes: Sequence[str],
    cache_dir: Path | None,
) -> tuple[Iterable[dict[str, Any]], str, str]:
    base = "https://data.statmt.org/cc-aligned/sentence-aligned"
    urls: list[str] = []

    for code in language_codes:
        urls.append(f"{base}/en_XX-{code}.tsv.xz")
        urls.append(f"{base}/{code}-en_XX.tsv.xz")

    # Known CCAligned Cebuano code.
    urls.append(f"{base}/cx_PH-en_XX.tsv.xz")
    urls.append(f"{base}/en_XX-cx_PH.tsv.xz")

    deduped_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped_urls.append(url)

    errors: list[str] = []
    for url in deduped_urls:
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
            errors.append(f"{url}: empty stream")
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    preview = "\n  - " + "\n  - ".join(errors[:8]) if errors else ""
    raise RuntimeError("URL fallback attempts failed." + preview)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(ch for ch in normalized if ch.isprintable() or ch.isspace())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_pair_from_hf_row(
    row: dict[str, Any],
    language_codes: Sequence[str],
) -> tuple[str, str] | None:
    if not isinstance(row, dict):
        return None

    translation = row.get("translation")
    if not isinstance(translation, dict):
        return None

    norm_candidates = {normalize_lang_tag(code) for code in language_codes}
    norm_candidates.update({"ceb", "cebuano", "bisaya", "cxph", "cx"})

    en_key: str | None = None
    ceb_key: str | None = None
    for key in translation.keys():
        key_text = str(key)
        key_norm = normalize_lang_tag(key_text)
        if en_key is None and key_norm.startswith("en"):
            en_key = key_text
        if ceb_key is None and key_norm in norm_candidates:
            ceb_key = key_text

    if en_key is not None and ceb_key is None and len(translation) == 2:
        for key in translation.keys():
            key_text = str(key)
            if key_text != en_key:
                ceb_key = key_text
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
    language_codes: Sequence[str],
) -> tuple[str, str] | None:
    if source_mode == "hf":
        return extract_pair_from_hf_row(row, language_codes)

    if not isinstance(row, dict):
        return None

    col0 = row.get("col0")
    col1 = row.get("col1")
    if not isinstance(col0, str) or not isinstance(col1, str):
        return None

    if source_mode == "csv_en_first":
        return col1, col0
    if source_mode == "csv_ceb_first":
        return col0, col1

    return None


def contains_block_symbol(text: str) -> bool:
    return any(symbol in text for symbol in SYMBOL_BLOCKLIST)


def digit_density(text: str) -> float:
    if not text:
        return 0.0
    digit_count = sum(1 for ch in text if ch.isdigit())
    return digit_count / len(text)


@lru_cache(maxsize=50000)
def detect_language_cached(text: str) -> str | None:
    """Detect language safely; returns None when detection fails."""
    # Required behavior: wrap detect(...) in try/except and drop on failure.
    try:
        return detect(text)
    except LangDetectException:
        return None
    except Exception:
        return None


def classify_drop_reason(
    *,
    ceb_text: str,
    en_text: str,
    digit_density_threshold: float,
) -> str | None:
    if not ceb_text or not en_text:
        return "empty"

    # Extra defensive URL removal to reduce web garbage.
    if URL_REGEX.search(ceb_text) or URL_REGEX.search(en_text):
        return "url"

    ceb_lower = ceb_text.lower()
    en_lower = en_text.lower()
    if any(term in ceb_lower for term in BLOCK_TERMS) or any(
        term in en_lower for term in BLOCK_TERMS
    ):
        return "ui_copyright"

    if contains_block_symbol(ceb_text) or contains_block_symbol(en_text):
        return "symbol"

    if (
        digit_density(ceb_text) > digit_density_threshold
        or digit_density(en_text) > digit_density_threshold
    ):
        return "digit_density"

    if SPACED_NUMERIC_REGEX.search(ceb_text) or SPACED_NUMERIC_REGEX.search(en_text):
        return "numeric_pattern"

    english_lang = detect_language_cached(en_text)
    if english_lang != "en":
        return "language"

    return None


def write_translation_record(handle, ceb_text: str, en_text: str) -> None:
    record = {"translation": {"ceb": ceb_text, "en": en_text}}
    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
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
    if not 0 < args.digit_density_threshold <= 1:
        raise ValueError("--digit-density-threshold must be in (0, 1].")

    output_path = args.output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --overwrite to replace it."
        )

    language_codes = language_code_candidates(args.language_code)
    hf_token = resolve_hf_token(args.hf_token)

    load_dataset, datasets_version, datasets_module = import_hf_datasets_load_dataset(
        PROJECT_ROOT
    )

    print("Starting CCAligned v3 cleaner...")
    print(f"- dataset_id: {args.dataset_id}")
    print(f"- requested_language_code: {args.language_code}")
    print(f"- language_code_candidates: {language_codes}")
    print(f"- split: {args.split}")
    print(f"- target_pairs: {args.target_pairs}")
    print(f"- digit_density_threshold: {args.digit_density_threshold}")
    print(f"- output_path: {output_path}")
    print(f"- datasets_version: {datasets_version}")
    print(f"- datasets_module: {datasets_module}")

    source_mode = "hf"
    source_label = ""

    try:
        row_stream, source_label = try_load_hf_stream(
            load_dataset=load_dataset,
            dataset_id=args.dataset_id,
            split=args.split,
            language_codes=language_codes,
            cache_dir=args.cache_dir,
            revision=args.revision,
            hf_token=hf_token,
        )
    except Exception as hf_exc:
        if args.disable_url_fallback:
            raise
        print(
            "[warning] direct HF loading failed; switching to URL fallback via "
            "load_dataset('csv', ...)"
        )
        print(f"[warning] root_cause: {hf_exc}")
        row_stream, source_mode, source_label = try_load_url_fallback(
            load_dataset=load_dataset,
            language_codes=language_codes,
            cache_dir=args.cache_dir,
        )

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
                    language_codes=language_codes,
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
                    digit_density_threshold=args.digit_density_threshold,
                )

                if reason == "empty":
                    stats.dropped_empty += 1
                    continue
                if reason == "url":
                    stats.dropped_url += 1
                    continue
                if reason == "ui_copyright":
                    stats.dropped_ui_copyright += 1
                    continue
                if reason == "symbol":
                    stats.dropped_symbol += 1
                    continue
                if reason == "digit_density":
                    stats.dropped_digit_density += 1
                    continue
                if reason == "numeric_pattern":
                    stats.dropped_numeric_pattern += 1
                    continue
                if reason == "language":
                    stats.dropped_language += 1
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
                "Unable to collect requested clean pair volume. "
                f"target={args.target_pairs}, kept={stats.kept_pairs}, "
                f"raw_processed={stats.raw_rows_processed}, dropped={stats.dropped_total}"
            )

        tmp_path.replace(output_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    elapsed = time.time() - started_at
    output_lines = count_lines(output_path)
    if output_lines != stats.kept_pairs:
        raise RuntimeError(
            "Post-write integrity check failed: "
            f"output_lines={output_lines}, kept_pairs={stats.kept_pairs}"
        )

    print("CCALIGNED_V3_CLEAN_COMPLETE")
    print(f"source={source_label}")
    print(f"raw_rows_processed={stats.raw_rows_processed}")
    print(f"dropped_total={stats.dropped_total}")
    print(f"dropped_schema={stats.dropped_schema}")
    print(f"dropped_empty={stats.dropped_empty}")
    print(f"dropped_url={stats.dropped_url}")
    print(f"dropped_ui_copyright={stats.dropped_ui_copyright}")
    print(f"dropped_symbol={stats.dropped_symbol}")
    print(f"dropped_digit_density={stats.dropped_digit_density}")
    print(f"dropped_numeric_pattern={stats.dropped_numeric_pattern}")
    print(f"dropped_language={stats.dropped_language}")
    print(f"dropped_duplicate={stats.dropped_duplicate}")
    print(f"kept_pairs={stats.kept_pairs}")
    print(f"output_lines={output_lines}")
    print(f"output_path={output_path}")
    print(f"elapsed_seconds={elapsed:.2f}")


if __name__ == "__main__":
    main()