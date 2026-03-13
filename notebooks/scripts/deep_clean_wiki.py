import html
import re
from pathlib import Path

# --- CONFIGURATION & ROBUST PATHING ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Candidate inputs (checked in this exact order)
CANDIDATE_INPUT_FILES = [
    PROJECT_ROOT / "Datasets" / "processed" / "01_chavacano" / "wiki_monolingual_cleaned.txt",
    PROJECT_ROOT / "Datasets" / "processed" / "02_Chavacano" / "wiki_monolingual_cleaned.txt",
]

# --- THE CLEANING ARSENAL (REGEX) ---
RE_GARBAGE_START = re.compile(r"^(#|\*|:|\.?\||\{|\}|!|;)")
RE_REDIRECT = re.compile(r"^#\s*REDIRECT|^#\s*REDIRECCI[ÓO]N", re.IGNORECASE)
RE_CATEGORY = re.compile(r"^Categor[ií]a:", re.IGNORECASE)
RE_CODE_JUNK = re.compile(r"invoke:|class=|style=|target=|float:|width:|cellpadding|rowspan|colspan", re.IGNORECASE)

RE_BOLD_ITALIC = re.compile(r"'{2,}")
RE_HTML_TAGS = re.compile(r"<[^>]+>")
RE_CITATIONS = re.compile(r"\[\d+\]")
RE_URLS = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
RE_BRACKETS = re.compile(r"\[|\]")
RE_MULTI_SPACE = re.compile(r"\s+")


def resolve_input_file():
    """Find the real wiki_monolingual_cleaned.txt path without guessing."""
    for candidate in CANDIDATE_INPUT_FILES:
        if candidate.exists():
            return candidate

    processed_root = PROJECT_ROOT / "Datasets" / "processed"
    if processed_root.exists():
        matches = sorted(processed_root.glob("**/wiki_monolingual_cleaned.txt"))
        if matches:
            return matches[0]

    return None


def scrub_line(text):
    clean = html.unescape(text)
    clean = RE_URLS.sub("", clean)
    clean = RE_CITATIONS.sub("", clean)
    clean = RE_BOLD_ITALIC.sub("", clean)
    clean = RE_HTML_TAGS.sub("", clean)
    clean = RE_BRACKETS.sub("", clean)
    clean = RE_MULTI_SPACE.sub(" ", clean).strip(" -–—|\t")
    return clean.strip()


def is_noise_line(text):
    if not text:
        return True

    if RE_GARBAGE_START.match(text):
        return True
    if RE_REDIRECT.match(text):
        return True
    if RE_CATEGORY.match(text):
        return True
    if RE_CODE_JUNK.search(text):
        return True

    symbol_count = sum(1 for ch in text if ch in "[]{}|=<>")
    if symbol_count >= 6:
        return True

    return False


def is_quality_line(text, min_length=30, min_words=5):
    if len(text) < min_length:
        return False

    words = text.split()
    if len(words) < min_words:
        return False

    non_space_chars = [ch for ch in text if not ch.isspace()]
    if not non_space_chars:
        return False

    alpha_count = sum(ch.isalpha() for ch in non_space_chars)
    alpha_ratio = alpha_count / len(non_space_chars)
    if alpha_ratio < 0.60:
        return False

    return True


def deep_clean():
    print("🧽 STARTING ROBUST DEEP CLEAN...")

    input_file = resolve_input_file()
    if not input_file:
        print("❌ ERROR: Input file not found.")
        print("   Checked these candidate paths:")
        for path in CANDIDATE_INPUT_FILES:
            print(f"   - {path}")
        return

    output_file = input_file.with_name("wiki_monolingual_FINAL.txt")

    print(f"📂 Reading from: {input_file}")
    print(f"💾 Writing to:   {output_file}")

    kept_lines = 0
    removed_lines = 0
    duplicate_lines = 0
    last_written = None

    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with input_file.open('r', encoding='utf-8') as f_in, output_file.open('w', encoding='utf-8') as f_out:
            for raw_line in f_in:
                original = raw_line.strip()

                if not original:
                    continue

                # Phase 1: remove obvious junk lines early (fast path)
                if is_noise_line(original):
                    removed_lines += 1
                    continue

                # Phase 2: scrub remaining line
                clean = scrub_line(original)

                # Phase 3: quality checks
                if is_noise_line(clean) or not is_quality_line(clean):
                    removed_lines += 1
                    continue

                # Phase 4: drop direct duplicates
                if clean == last_written:
                    duplicate_lines += 1
                    continue

                f_out.write(clean + "\n")
                kept_lines += 1
                last_written = clean

        print("\n" + "=" * 40)
        print("✨ DEEP CLEAN COMPLETE!")
        print(f"🗑️  Trashed:    {removed_lines} lines (Garbage/Low quality)")
        print(f"♻️  Duplicates: {duplicate_lines} lines")
        print(f"✅ Saved:      {kept_lines} lines (High Quality)")
        print(f"💾 File:       {output_file}")
        print("=" * 40)

        print("🔍 PREVIEW OF FINAL QUALITY:")
        with output_file.open('r', encoding='utf-8') as f:
            shown = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                print(f" > {line}")
                shown += 1
                if shown >= 5:
                    break

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    deep_clean()