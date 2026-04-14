#!/usr/bin/env python3
"""Download and aggressively clean CCAligned Cebuano-English sentence pairs.

Primary required path:
    load_dataset("ahelk/ccaligned_multilingual", language_code="ceb_XX", ...)

Compatibility path:
    If script-based loading is blocked by the installed datasets version,
    automatically fall back to streaming CCAligned TSV URLs via
    load_dataset("csv", ...), preserving the same cleaning gauntlet.
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
DEFAULT_LANGUAGE_CODE = "ceb_XX"
DEFAULT_SPLIT = "train"
DEFAULT_TARGET_PAIRS = 8000
DEFAULT_PROGRESS_EVERY = 1000
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "datasets" / "raw" / "ceb" / "ccaligned_ceb_en_cleaned_v2.jsonl"
)

# Regex-heavy filtration engine.
URL_REGEX = re.compile(r"(?:https?://|www\.)", flags=re.IGNORECASE)
NUMERIC_SPAM_REGEX = re.compile(r"\d{5,}")
COORDINATE_REGEX = re.compile(r"\b[+-]?\d{1,3}\.\d{4,}\b")
PHONEISH_REGEX = re.compile(r"\b\+?\d(?:[\s().-]*\d){7,}\b")
SYMBOL_OVERLOAD_REGEX = re.compile(r"[@©*%+|\[\]]")
UI_DROPDOWN_REGEX = re.compile(
    r"\b(?:archive|categories|log\s*in|password|cart|ages|download|subscribe|rate\s+this\s+article|sku)\b",
    flags=re.IGNORECASE,
)

# Latin letter-focused tokens to enforce "standard letters" quality.
LATIN_LETTER_REGEX = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")
NON_SPACE_REGEX = re.compile(r"\S")
WORD_REGEX = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ]+)*")


@dataclass
class FilterStats:
    raw_rows_processed: int = 0
    kept_pairs: int = 0

    dropped_schema: int = 0
    dropped_empty: int = 0
    dropped_url: int = 0
    dropped_numeric_spam: int = 0
    dropped_symbol_overload: int = 0
    dropped_ui_dropdown: int = 0
    dropped_alpha_ratio: int = 0
    dropped_word_window: int = 0
    dropped_word_ratio: int = 0
    dropped_duplicate: int = 0

    @property
    def dropped_total(self) -> int:
        return (
            self.dropped_schema
            + self.dropped_empty
            + self.dropped_url
            + self.dropped_numeric_spam
            + self.dropped_symbol_overload
            + self.dropped_ui_dropdown
            + self.dropped_alpha_ratio
            + self.dropped_word_window
            + self.dropped_word_ratio
            + self.dropped_duplicate
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download and aggressively clean CCAligned Cebuano-English data using "
            "regex-based web-garbage filters and strict linguistic constraints."
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
        help=(
            "Requested language code for load_dataset(..., language_code=...). "
            f"Default: {DEFAULT_LANGUAGE_CODE}."
        ),
    )
    parser.add_argument(
        "--split",
        default=DEFAULT_SPLIT,
        help=f"Dataset split to stream (default: {DEFAULT_SPLIT}).",
    )
    parser.add_argument(
        "--target-pairs",
        type=int,
        default=DEFAULT_TARGET_PAIRS,
        help=f"Exact clean pair target (default: {DEFAULT_TARGET_PAIRS}).",
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
        help=f"Progress print frequency in kept rows (default: {DEFAULT_PROGRESS_EVERY}).",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=4,
        help="Minimum words required per side (default: 4).",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=40,
        help="Maximum words allowed per side (default: 40).",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=0.6,
        help="Minimum en/ceb word ratio (default: 0.6).",
    )
    parser.add_argument(
        "--max-ratio",
        type=float,
        default=1.5,
        help="Maximum en/ceb word ratio (default: 1.5).",
    )
    parser.add_argument(
        "--alpha-ratio-threshold",
        type=float,
        default=0.80,
        help="Minimum latin-letter ratio per sentence (default: 0.80).",
    )
    parser.add_argument(
        "--symbol-threshold",
        type=int,
        default=2,
        help=(
            "Drop sentence when targeted noisy symbols appear at least this many times "
            "(default: 2)."
        ),
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
        help="Optional HF token. Falls back to HF_TOKEN env vars.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output path if it exists.",
    )
    parser.add_argument(
        "--disable-url-fallback",
        action="store_true",
        help="Fail immediately if direct HF loading fails.",
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


def normalize_lang_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", tag.casefold())


def language_code_candidates(requested: str) -> list[str]:
    raw = (
        requested,
        requested.strip().lower(),
        "ceb_XX",
        "cx_PH",
        "ceb",
        "cx",
    )
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
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

    # First try exact style requested by user: language_code="ceb_XX".
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

    # Then try builder config names.
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

    # Strong known fallback for Cebuano in CCAligned.
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


def word_count(text: str) -> int:
    return len(WORD_REGEX.findall(text))


def latin_alpha_ratio(text: str) -> float:
    non_space_count = len(NON_SPACE_REGEX.findall(text))
    if non_space_count == 0:
        return 0.0
    letter_count = len(LATIN_LETTER_REGEX.findall(text))
    return letter_count / non_space_count


def has_symbol_overload(text: str, threshold: int) -> bool:
    hits = SYMBOL_OVERLOAD_REGEX.findall(text)
    if len(hits) >= threshold:
        return True

    # Symbol-density guard for short noisy snippets.
    non_space_count = max(1, len(NON_SPACE_REGEX.findall(text)))
    return bool(hits) and (len(hits) / non_space_count) >= 0.08


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

    if en_key is None or ceb_key is None:
        # If exactly two languages exist and one is English, use the other as Cebuano.
        if en_key is not None and len(translation) == 2:
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


def classify_drop_reason(
    *,
    ceb_text: str,
    en_text: str,
    min_words: int,
    max_words: int,
    min_ratio: float,
    max_ratio: float,
    alpha_ratio_threshold: float,
    symbol_threshold: int,
) -> str | None:
    if not ceb_text or not en_text:
        return "empty"

    if URL_REGEX.search(ceb_text) or URL_REGEX.search(en_text):
        return "url"

    if (
        NUMERIC_SPAM_REGEX.search(ceb_text)
        or NUMERIC_SPAM_REGEX.search(en_text)
        or COORDINATE_REGEX.search(ceb_text)
        or COORDINATE_REGEX.search(en_text)
        or PHONEISH_REGEX.search(ceb_text)
        or PHONEISH_REGEX.search(en_text)
    ):
        return "numeric"

    if has_symbol_overload(ceb_text, symbol_threshold) or has_symbol_overload(
        en_text, symbol_threshold
    ):
        return "symbol"

    if UI_DROPDOWN_REGEX.search(ceb_text) or UI_DROPDOWN_REGEX.search(en_text):
        return "ui"

    if (
        latin_alpha_ratio(ceb_text) < alpha_ratio_threshold
        or latin_alpha_ratio(en_text) < alpha_ratio_threshold
    ):
        return "alpha"

    ceb_words = word_count(ceb_text)
    en_words = word_count(en_text)
    if (
        ceb_words < min_words
        or ceb_words > max_words
        or en_words < min_words
        or en_words > max_words
    ):
        return "word_window"

    if ceb_words == 0:
        return "word_window"

    ratio = en_words / ceb_words
    if ratio < min_ratio or ratio > max_ratio:
        return "word_ratio"

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
    if args.min_words <= 0 or args.max_words <= 0 or args.min_words > args.max_words:
        raise ValueError("Invalid word window: require 0 < min-words <= max-words.")
    if args.min_ratio <= 0 or args.max_ratio <= 0 or args.min_ratio > args.max_ratio:
        raise ValueError("Invalid ratio bounds: require 0 < min-ratio <= max-ratio.")
    if not 0 < args.alpha_ratio_threshold <= 1:
        raise ValueError("--alpha-ratio-threshold must be in (0, 1].")
    if args.symbol_threshold <= 0:
        raise ValueError("--symbol-threshold must be greater than 0.")

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

    print("Starting CCAligned Cebuano-English v2 extraction and cleaning...")
    print(f"- dataset_id: {args.dataset_id}")
    print(f"- requested_language_code: {args.language_code}")
    print(f"- language_code_candidates: {language_codes}")
    print(f"- split: {args.split}")
    print(f"- target_pairs: {args.target_pairs}")
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
            "[warning] direct HF dataset loading failed; using URL fallback through "
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
                    min_words=args.min_words,
                    max_words=args.max_words,
                    min_ratio=args.min_ratio,
                    max_ratio=args.max_ratio,
                    alpha_ratio_threshold=args.alpha_ratio_threshold,
                    symbol_threshold=args.symbol_threshold,
                )

                if reason == "empty":
                    stats.dropped_empty += 1
                    continue
                if reason == "url":
                    stats.dropped_url += 1
                    continue
                if reason == "numeric":
                    stats.dropped_numeric_spam += 1
                    continue
                if reason == "symbol":
                    stats.dropped_symbol_overload += 1
                    continue
                if reason == "ui":
                    stats.dropped_ui_dropdown += 1
                    continue
                if reason == "alpha":
                    stats.dropped_alpha_ratio += 1
                    continue
                if reason == "word_window":
                    stats.dropped_word_window += 1
                    continue
                if reason == "word_ratio":
                    stats.dropped_word_ratio += 1
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

    print("CCALIGNED_CEB_DOWNLOAD_AND_CLEAN_V2_COMPLETE")
    print(f"source={source_label}")
    print(f"raw_rows_processed={stats.raw_rows_processed}")
    print(f"dropped_total={stats.dropped_total}")
    print(f"dropped_schema={stats.dropped_schema}")
    print(f"dropped_empty={stats.dropped_empty}")
    print(f"dropped_url={stats.dropped_url}")
    print(f"dropped_numeric_spam={stats.dropped_numeric_spam}")
    print(f"dropped_symbol_overload={stats.dropped_symbol_overload}")
    print(f"dropped_ui_dropdown={stats.dropped_ui_dropdown}")
    print(f"dropped_alpha_ratio={stats.dropped_alpha_ratio}")
    print(f"dropped_word_window={stats.dropped_word_window}")
    print(f"dropped_word_ratio={stats.dropped_word_ratio}")
    print(f"dropped_duplicate={stats.dropped_duplicate}")
    print(f"kept_pairs={stats.kept_pairs}")
    print(f"output_lines={output_lines}")
    print(f"output_path={output_path}")
    print(f"elapsed_seconds={elapsed:.2f}")


if __name__ == "__main__":
    main()