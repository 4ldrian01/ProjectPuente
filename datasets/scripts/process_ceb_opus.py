#!/usr/bin/env python3
"""Process OPUS Cebuano-English corpora into train/val/test JSONL for NLLB.

This pipeline enforces a canonical folder layout, ingests aligned Moses files
from Tatoeba and TED2020, applies cleaning + deduplication, shuffles with a
fixed seed, and writes 80/10/10 JSONL splits in Hugging Face translation format.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import unicodedata
from dataclasses import dataclass
from itertools import zip_longest
from math import floor
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "datasets"

RAW_CEB_DIR = DATASETS_DIR / "raw" / "ceb"
RAW_TATOEBA_DIR = RAW_CEB_DIR / "tatoeba"
RAW_TED2020_DIR = RAW_CEB_DIR / "ted2020"

PROCESSED_CEB_DIR = DATASETS_DIR / "processed" / "cebuano"

# Compatibility fallback for the currently downloaded corpora layout.
LEGACY_TATOEBA_DIR = DATASETS_DIR / "raw" / "03_Cebuano_Bisaya" / "latest_ceb-en.txt"
LEGACY_TED2020_DIR = DATASETS_DIR / "raw" / "03_Cebuano_Bisaya" / "latest_ceb-en.txt (1)"


@dataclass
class ProcessingStats:
    total_raw_pairs: int = 0
    dropped_unaligned: int = 0
    dropped_empty: int = 0
    dropped_length_mismatch: int = 0
    dropped_duplicates: int = 0

    @property
    def dropped_cleaning(self) -> int:
        return self.dropped_unaligned + self.dropped_empty + self.dropped_length_mismatch

    @property
    def dropped_total(self) -> int:
        return self.dropped_cleaning + self.dropped_duplicates


@dataclass
class DatasetSummary:
    name: str
    ceb_path: Path
    en_path: Path
    raw_pairs: int
    kept_after_cleaning: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract, clean, deduplicate, and split OPUS Cebuano-English corpora "
            "(Tatoeba + TED2020) into NLLB-ready JSONL files."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic shuffling (default: 42).",
    )
    parser.add_argument(
        "--word-ratio-threshold",
        type=float,
        default=3.5,
        help="Drop pair if longer/shorter word-count ratio is too high.",
    )
    parser.add_argument(
        "--min-word-gap",
        type=int,
        default=8,
        help="Require at least this absolute word-count gap before ratio filter applies.",
    )
    parser.add_argument(
        "--char-ratio-threshold",
        type=float,
        default=4.5,
        help="Secondary char-length mismatch ratio filter.",
    )
    parser.add_argument(
        "--no-legacy-stage",
        action="store_true",
        help=(
            "Disable auto-staging from legacy folders under raw/03_Cebuano_Bisaya "
            "to raw/ceb/{tatoeba,ted2020}."
        ),
    )
    return parser.parse_args()


def ensure_required_directories() -> None:
    """Create canonical directories required by the pipeline."""
    RAW_TATOEBA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_TED2020_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_CEB_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_moses_pair(dataset_dir: Path, preferred_stem: str) -> tuple[Path, Path]:
    """Resolve aligned .ceb/.en files from a dataset directory."""
    preferred_ceb = dataset_dir / f"{preferred_stem}.ceb-en.ceb"
    preferred_en = dataset_dir / f"{preferred_stem}.ceb-en.en"
    if preferred_ceb.is_file() and preferred_en.is_file():
        return preferred_ceb, preferred_en

    ceb_files = sorted(dataset_dir.glob("*.ceb"))
    en_files = sorted(dataset_dir.glob("*.en"))

    if len(ceb_files) == 1 and len(en_files) == 1:
        return ceb_files[0], en_files[0]

    ceb_by_stem = {p.name.rsplit(".", 1)[0]: p for p in ceb_files}
    en_by_stem = {p.name.rsplit(".", 1)[0]: p for p in en_files}
    common_stems = sorted(set(ceb_by_stem) & set(en_by_stem))

    if len(common_stems) == 1:
        stem = common_stems[0]
        return ceb_by_stem[stem], en_by_stem[stem]

    available = ", ".join([p.name for p in sorted(dataset_dir.iterdir())])
    raise FileNotFoundError(
        f"Could not resolve a unique .ceb/.en file pair in {dataset_dir}. "
        f"Available entries: [{available}]"
    )


def stage_legacy_dataset_if_needed(
    *,
    canonical_dir: Path,
    canonical_stem: str,
    legacy_dir: Path,
) -> bool:
    """Copy legacy OPUS files into canonical raw/ceb folder if missing."""
    canonical_ceb = canonical_dir / f"{canonical_stem}.ceb-en.ceb"
    canonical_en = canonical_dir / f"{canonical_stem}.ceb-en.en"

    if canonical_ceb.exists() and canonical_en.exists():
        return False

    if not legacy_dir.exists():
        return False

    legacy_ceb, legacy_en = find_moses_pair(legacy_dir, canonical_stem)

    if not canonical_ceb.exists():
        shutil.copy2(legacy_ceb, canonical_ceb)
    if not canonical_en.exists():
        shutil.copy2(legacy_en, canonical_en)

    return True


def word_count(text: str) -> int:
    return len(text.split())


def has_extreme_length_mismatch(
    ceb_text: str,
    en_text: str,
    *,
    word_ratio_threshold: float,
    min_word_gap: int,
    char_ratio_threshold: float,
) -> bool:
    """Reject severely misaligned pairs using word and char length heuristics."""
    ceb_words = word_count(ceb_text)
    en_words = word_count(en_text)

    if ceb_words == 0 or en_words == 0:
        return True

    short_words, long_words = sorted((ceb_words, en_words))
    word_ratio = long_words / short_words

    # Hard guard for pathological short-vs-long mismatches.
    if short_words <= 2 and long_words >= 20:
        return True

    if (long_words - short_words) >= min_word_gap and word_ratio >= word_ratio_threshold:
        return True

    short_chars, long_chars = sorted((len(ceb_text), len(en_text)))
    if short_chars == 0:
        return True

    char_ratio = long_chars / short_chars
    if (long_words - short_words) >= min_word_gap and char_ratio >= char_ratio_threshold:
        return True

    return False


def read_and_clean_pairs(
    *,
    dataset_name: str,
    ceb_path: Path,
    en_path: Path,
    stats: ProcessingStats,
    word_ratio_threshold: float,
    min_word_gap: int,
    char_ratio_threshold: float,
) -> tuple[list[tuple[str, str]], DatasetSummary]:
    """Read aligned lines, apply cleaning filters, and return valid pairs."""
    cleaned_pairs: list[tuple[str, str]] = []
    raw_before = stats.total_raw_pairs

    with ceb_path.open("r", encoding="utf-8", errors="replace") as ceb_file, en_path.open(
        "r", encoding="utf-8", errors="replace"
    ) as en_file:
        for ceb_line, en_line in zip_longest(ceb_file, en_file):
            stats.total_raw_pairs += 1

            if ceb_line is None or en_line is None:
                stats.dropped_unaligned += 1
                continue

            ceb_text = normalize_text(ceb_line)
            en_text = normalize_text(en_line)

            if not ceb_text or not en_text:
                stats.dropped_empty += 1
                continue

            if has_extreme_length_mismatch(
                ceb_text,
                en_text,
                word_ratio_threshold=word_ratio_threshold,
                min_word_gap=min_word_gap,
                char_ratio_threshold=char_ratio_threshold,
            ):
                stats.dropped_length_mismatch += 1
                continue

            cleaned_pairs.append((ceb_text, en_text))

    summary = DatasetSummary(
        name=dataset_name,
        ceb_path=ceb_path,
        en_path=en_path,
        raw_pairs=stats.total_raw_pairs - raw_before,
        kept_after_cleaning=len(cleaned_pairs),
    )
    return cleaned_pairs, summary


def deduplicate_pairs(pairs: list[tuple[str, str]], stats: ProcessingStats) -> list[tuple[str, str]]:
    """Deduplicate by normalized bilingual pair key to prevent evaluation leakage."""
    seen: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[str, str]] = []

    for ceb_text, en_text in pairs:
        pair_key = (ceb_text.casefold(), en_text.casefold())
        if pair_key in seen:
            stats.dropped_duplicates += 1
            continue
        seen.add(pair_key)
        unique_pairs.append((ceb_text, en_text))

    return unique_pairs


def to_translation_record(ceb_text: str, en_text: str) -> dict:
    return {"translation": {"ceb": ceb_text, "en": en_text}}


def split_counts(total: int, ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> tuple[int, int, int]:
    """Compute stable 80/10/10 counts that always sum exactly to total."""
    raw_counts = [total * ratio for ratio in ratios]
    base_counts = [floor(value) for value in raw_counts]

    remainder = total - sum(base_counts)
    ranked = sorted(
        range(len(ratios)),
        key=lambda idx: (raw_counts[idx] - base_counts[idx], -idx),
        reverse=True,
    )

    for idx in ranked[:remainder]:
        base_counts[idx] += 1

    return base_counts[0], base_counts[1], base_counts[2]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def main() -> None:
    args = parse_args()

    ensure_required_directories()

    staged_sources: list[str] = []
    if not args.no_legacy_stage:
        if stage_legacy_dataset_if_needed(
            canonical_dir=RAW_TATOEBA_DIR,
            canonical_stem="Tatoeba",
            legacy_dir=LEGACY_TATOEBA_DIR,
        ):
            staged_sources.append("Tatoeba")

        if stage_legacy_dataset_if_needed(
            canonical_dir=RAW_TED2020_DIR,
            canonical_stem="TED2020",
            legacy_dir=LEGACY_TED2020_DIR,
        ):
            staged_sources.append("TED2020")

    tatoeba_ceb, tatoeba_en = find_moses_pair(RAW_TATOEBA_DIR, "Tatoeba")
    ted_ceb, ted_en = find_moses_pair(RAW_TED2020_DIR, "TED2020")

    stats = ProcessingStats()

    tatoeba_pairs, tatoeba_summary = read_and_clean_pairs(
        dataset_name="Tatoeba",
        ceb_path=tatoeba_ceb,
        en_path=tatoeba_en,
        stats=stats,
        word_ratio_threshold=args.word_ratio_threshold,
        min_word_gap=args.min_word_gap,
        char_ratio_threshold=args.char_ratio_threshold,
    )
    ted_pairs, ted_summary = read_and_clean_pairs(
        dataset_name="TED2020",
        ceb_path=ted_ceb,
        en_path=ted_en,
        stats=stats,
        word_ratio_threshold=args.word_ratio_threshold,
        min_word_gap=args.min_word_gap,
        char_ratio_threshold=args.char_ratio_threshold,
    )

    combined_pairs = tatoeba_pairs + ted_pairs
    unique_pairs = deduplicate_pairs(combined_pairs, stats)
    records = [to_translation_record(ceb_text, en_text) for ceb_text, en_text in unique_pairs]

    rng = random.Random(args.seed)
    rng.shuffle(records)

    train_count, val_count, test_count = split_counts(len(records), ratios=(0.8, 0.1, 0.1))
    train_records = records[:train_count]
    val_records = records[train_count : train_count + val_count]
    test_records = records[train_count + val_count :]

    train_path = PROCESSED_CEB_DIR / "ceb_en_train.jsonl"
    val_path = PROCESSED_CEB_DIR / "ceb_en_val.jsonl"
    test_path = PROCESSED_CEB_DIR / "ceb_en_test.jsonl"

    write_jsonl(train_path, train_records)
    write_jsonl(val_path, val_records)
    write_jsonl(test_path, test_records)

    print("CEB-EN OPUS PREPROCESS COMPLETE")
    print("=" * 58)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Canonical raw dirs: {RAW_TATOEBA_DIR} | {RAW_TED2020_DIR}")
    print(f"Processed dir: {PROCESSED_CEB_DIR}")
    if staged_sources:
        print(f"Legacy datasets auto-staged: {', '.join(staged_sources)}")

    print("\nInput files used:")
    for summary in (tatoeba_summary, ted_summary):
        print(
            f"- {summary.name}: {summary.ceb_path.name} + {summary.en_path.name} "
            f"(raw={summary.raw_pairs}, kept_after_cleaning={summary.kept_after_cleaning})"
        )

    print("\nSummary metrics:")
    print(f"- Total raw sentence pairs processed: {stats.total_raw_pairs}")
    print(f"- Total sentence pairs dropped: {stats.dropped_total}")
    print(f"  - Dropped unaligned line pairs: {stats.dropped_unaligned}")
    print(f"  - Dropped empty/whitespace pairs: {stats.dropped_empty}")
    print(f"  - Dropped extreme length mismatches: {stats.dropped_length_mismatch}")
    print(f"  - Dropped duplicates: {stats.dropped_duplicates}")

    print("\nOutput counts:")
    print(f"- Train (80%): {len(train_records)} -> {train_path}")
    print(f"- Validation (10%): {len(val_records)} -> {val_path}")
    print(f"- Test (10%): {len(test_records)} -> {test_path}")


if __name__ == "__main__":
    main()