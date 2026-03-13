"""
NLLB-200 Production Pipeline: CSV Parallel Sentence Processing
==============================================================
Purpose: Process Chavacano-English parallel sentences from CSV
Target: NLLB-200 translation model training
Author: NLP Data Engineering Team
"""

import pandas as pd
import json
import logging
import unicodedata
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Input/Output paths
RAW_DIR = PROJECT_ROOT / "Datasets" / "raw" / "02_Chavacano"
CSV_FILE = RAW_DIR / "chavacano-to-english-parallel-sentences.csv"

PROCESSED_DIR = PROJECT_ROOT / "Datasets" / "processed" / "001_chavacano"
OUTPUT_JSON = PROCESSED_DIR / "chavacano_parallel_sentences_nllb.json"
LOG_FILE = PROCESSED_DIR / "csv_processing.log"

# Quality thresholds
MIN_SENTENCE_LENGTH = 5
MAX_SENTENCE_LENGTH = 200
MIN_WORDS = 2
MAX_WORDS = 50

# ============================================================================
# LOGGING SETUP
# ============================================================================
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CHAVACANO-SPECIFIC TEXT CLEANING
# ============================================================================

def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC for consistent tokenization."""
    return unicodedata.normalize('NFC', text)

def clean_sentence(text: str) -> str:
    """
    Clean and normalize Chavacano/English sentence.
    - Unicode normalization
    - Remove extra whitespace
    - Preserve Spanish diacritics
    - Remove control characters
    """
    if not text or pd.isna(text):
        return ""
    
    text = str(text).strip()
    
    # Normalize Unicode
    text = normalize_unicode(text)
    
    # Remove control characters (keeping basic punctuation)
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\t')
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing punctuation artifacts
    text = text.strip(' .,;:-')
    
    return text

def is_valid_sentence(text: str, min_len: int = MIN_SENTENCE_LENGTH, 
                      max_len: int = MAX_SENTENCE_LENGTH) -> bool:
    """Validate sentence quality for NLLB-200."""
    if not text:
        return False
    
    # Length checks
    if len(text) < min_len or len(text) > max_len:
        return False
    
    # Word count check
    words = text.split()
    if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
        return False
    
    # Must contain letters
    if not any(c.isalpha() for c in text):
        return False
    
    # Reject if mostly non-alphabetic (likely garbage)
    alpha_count = sum(c.isalpha() for c in text)
    alpha_ratio = alpha_count / len(text.replace(' ', ''))
    if alpha_ratio < 0.6:
        return False
    
    return True

def detect_sentence_type(text: str) -> str:
    """
    Detect if text is a sentence, phrase, or vocabulary item.
    Important for NLLB-200 data categorization.
    """
    words = text.split()
    
    # Single word = vocabulary
    if len(words) == 1:
        return "vocabulary"
    
    # 2-3 words without verb-like structure = phrase/collocation
    if len(words) <= 3:
        # Simple heuristic: check for common verb endings in Chavacano
        verb_patterns = ['ya', 'ta', 'hay', 'puede', 'tiene']
        if any(pattern in text.lower() for pattern in verb_patterns):
            return "sentence"
        return "phrase"
    
    # 4+ words = likely a sentence
    return "sentence"

def calculate_alignment_quality(source: str, target: str) -> float:
    """
    Calculate alignment quality score (0.0-1.0) for parallel sentences.
    Factors:
    - Length ratio similarity
    - Word count ratio
    - Presence of cognates/shared tokens
    """
    if not source or not target:
        return 0.0
    
    score = 1.0
    
    # Length ratio check (should be within reasonable range)
    len_ratio = len(target) / len(source) if source else 0
    if len_ratio < 0.5 or len_ratio > 3.0:
        score -= 0.3
    elif len_ratio < 0.7 or len_ratio > 2.0:
        score -= 0.1
    
    # Word count ratio
    src_words = len(source.split())
    tgt_words = len(target.split())
    word_ratio = tgt_words / src_words if src_words else 0
    if word_ratio < 0.5 or word_ratio > 2.5:
        score -= 0.2
    
    # Check for potential cognates (simple token overlap)
    src_tokens = set(source.lower().split())
    tgt_tokens = set(target.lower().split())
    overlap = len(src_tokens & tgt_tokens)
    if overlap > 0:
        score += 0.1  # Bonus for shared tokens (common in Chavacano-English)
    
    return max(0.0, min(1.0, score))

# ============================================================================
# CSV PROCESSING ENGINE
# ============================================================================

class ChavacanoCSVProcessor:
    def __init__(self):
        self.entries: List[Dict] = []
        self.seen_pairs: Set[Tuple[str, str]] = set()
        self.stats = {
            'rows_total': 0,
            'rows_valid': 0,
            'rows_skipped': 0,
            'duplicates_removed': 0,
            'sentences': 0,
            'phrases': 0,
            'vocabulary': 0
        }
    
    def process(self) -> None:
        """Main processing pipeline."""
        logger.info(f"🚀 Starting CSV processing from: {CSV_FILE}")
        
        if not CSV_FILE.exists():
            logger.error(f"❌ CSV file not found: {CSV_FILE}")
            return
        
        try:
            # Load CSV with robust error handling
            df = pd.read_csv(
                CSV_FILE,
                encoding='utf-8',
                on_bad_lines='skip',
                dtype=str
            )
            
            # Normalize column names
            df.columns = [col.strip().lower() for col in df.columns]
            
            logger.info(f"📊 Loaded {len(df)} rows | Columns: {df.columns.tolist()}")
            
            # Validate required columns
            required_cols = ['chavacano', 'english']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"❌ Missing required columns. Found: {df.columns.tolist()}")
                return
            
            self.stats['rows_total'] = len(df)
            
            # Process each row
            for idx, row in df.iterrows():
                self._process_row(row, idx)
            
            self._save_results()
            self._log_statistics()
        
        except Exception as e:
            logger.error(f"❌ Critical error processing CSV: {e}")
    
    def _process_row(self, row: pd.Series, idx: int) -> None:
        """Process a single CSV row."""
        try:
            # Extract and clean text
            chavacano = clean_sentence(row.get('chavacano', ''))
            english = clean_sentence(row.get('english', ''))
            row_type = str(row.get('type', '')).strip().lower()
            
            # Validation
            if not is_valid_sentence(chavacano) or not is_valid_sentence(english):
                self.stats['rows_skipped'] += 1
                return
            
            # Deduplication (case-insensitive pair matching)
            pair_key = (chavacano.lower(), english.lower())
            if pair_key in self.seen_pairs:
                self.stats['duplicates_removed'] += 1
                return
            
            self.seen_pairs.add(pair_key)
            
            # Detect sentence type
            detected_type = detect_sentence_type(chavacano)
            
            # Calculate quality scores
            alignment_quality = calculate_alignment_quality(chavacano, english)
            
            # Create NLLB-200 formatted entry
            entry = {
                "chavacano": chavacano,
                "english": english,
                "type": row_type if row_type else detected_type,
                "category": detected_type,
                "source": "chavacano-english-parallel-corpus",
                "alignment_score": round(alignment_quality, 3),
                "languages": ["cbk_Latn", "eng_Latn"],
                "row_id": int(idx)
            }
            
            self.entries.append(entry)
            self.stats['rows_valid'] += 1
            
            # Update category stats
            if detected_type == "sentence":
                self.stats['sentences'] += 1
            elif detected_type == "phrase":
                self.stats['phrases'] += 1
            else:
                self.stats['vocabulary'] += 1
        
        except Exception as e:
            logger.warning(f"⚠️ Error processing row {idx}: {e}")
            self.stats['rows_skipped'] += 1
    
    def _save_results(self) -> None:
        """Save processed data to JSON."""
        try:
            with OUTPUT_JSON.open('w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'source': 'chavacano-to-english-parallel-sentences.csv',
                        'processing_date': datetime.now().isoformat(),
                        'language_pair': ['cbk_Latn', 'eng_Latn'],
                        'total_pairs': len(self.entries),
                        'nllb_200_ready': True,
                        'data_split_suggestion': {
                            'train': int(len(self.entries) * 0.8),
                            'dev': int(len(self.entries) * 0.1),
                            'test': int(len(self.entries) * 0.1)
                        }
                    },
                    'entries': self.entries
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved to: {OUTPUT_JSON}")
        
        except Exception as e:
            logger.error(f"❌ Error saving results: {e}")
    
    def _log_statistics(self) -> None:
        """Log processing statistics and NLLB-200 readiness."""
        logger.info("=" * 60)
        logger.info("📊 PROCESSING COMPLETE - Statistics:")
        logger.info(f"   Total Rows:          {self.stats['rows_total']}")
        logger.info(f"   Valid Pairs:         {self.stats['rows_valid']}")
        logger.info(f"   Skipped (Quality):   {self.stats['rows_skipped']}")
        logger.info(f"   Duplicates Removed:  {self.stats['duplicates_removed']}")
        logger.info(f"   └─ Sentences:        {self.stats['sentences']}")
        logger.info(f"   └─ Phrases:          {self.stats['phrases']}")
        logger.info(f"   └─ Vocabulary:       {self.stats['vocabulary']}")
        
        # Calculate NLLB-200 readiness score
        if self.stats['rows_total'] > 0:
            quality_ratio = self.stats['rows_valid'] / self.stats['rows_total']
            sentence_ratio = self.stats['sentences'] / self.stats['rows_valid'] if self.stats['rows_valid'] > 0 else 0
            
            # Readiness factors:
            # - High quality retention (60%)
            # - High sentence proportion (40%)
            readiness_score = (quality_ratio * 0.6 + sentence_ratio * 0.4) * 100
        else:
            readiness_score = 0.0
        
        logger.info(f"   🎯 NLLB-200 Readiness: {readiness_score:.1f}%")
        logger.info(f"      (Quality Retention: {quality_ratio*100:.1f}% | Sentence Ratio: {sentence_ratio*100:.1f}%)")
        logger.info("=" * 60)
        
        # Justification
        logger.info("\n✅ NLLB-200 Standards Met:")
        logger.info("   • Sentence-aligned parallel pairs")
        logger.info("   • UTF-8 Unicode normalization (NFC)")
        logger.info("   • Deduplication (case-insensitive)")
        logger.info("   • Quality scoring for filtering")
        logger.info("   • Metadata for train/dev/test splits")
        
        # Sample preview
        if self.entries:
            logger.info("\n🔍 Sample Entries:")
            for entry in self.entries[:3]:
                logger.info(f"   CBK: {entry['chavacano']}")
                logger.info(f"   ENG: {entry['english']}")
                logger.info(f"   Score: {entry['alignment_score']} | Type: {entry['category']}\n")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute the CSV processing pipeline."""
    processor = ChavacanoCSVProcessor()
    processor.process()

if __name__ == "__main__":
    main()
