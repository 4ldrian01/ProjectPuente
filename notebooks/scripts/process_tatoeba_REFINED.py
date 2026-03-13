"""
NLLB-200 Production Pipeline: Tatoeba ZIP Archive Processing
=============================================================
Purpose: Extract and process Chavacano-English parallel sentences from Tatoeba
Target: NLLB-200 translation model training
Author: NLP Data Engineering Team
"""

import json
import zipfile
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
ZIP_FILE = RAW_DIR / "cbk-en.txt.zip"
EXTRACT_DIR = RAW_DIR / "tatoeba_extracted"

PROCESSED_DIR = PROJECT_ROOT / "Datasets" / "processed" / "001_chavacano"
OUTPUT_JSON = PROCESSED_DIR / "tatoeba_parallel_nllb.json"
LOG_FILE = PROCESSED_DIR / "tatoeba_extraction.log"

# Quality thresholds
MIN_SENTENCE_LENGTH = 5
MAX_SENTENCE_LENGTH = 300
MIN_WORDS = 2

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
# TEXT CLEANING & VALIDATION
# ============================================================================

def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC for consistent tokenization."""
    return unicodedata.normalize('NFC', text)

def clean_sentence(text: str) -> str:
    """
    Clean Tatoeba sentence.
    - Unicode normalization
    - Remove extra whitespace
    - Remove Tatoeba-specific artifacts (IDs, markers)
    """
    if not text:
        return ""
    
    text = str(text).strip()
    
    # Normalize Unicode
    text = normalize_unicode(text)
    
    # Remove Tatoeba sentence IDs if present (format: #1234567)
    text = re.sub(r'#\d+', '', text)
    
    # Remove tab characters (sometimes used as delimiters)
    text = text.replace('\t', ' ')
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing punctuation artifacts
    text = text.strip(' .,;:-')
    
    return text

def is_valid_sentence(text: str) -> bool:
    """Validate sentence quality for NLLB-200."""
    if not text:
        return False
    
    # Length checks
    if len(text) < MIN_SENTENCE_LENGTH or len(text) > MAX_SENTENCE_LENGTH:
        return False
    
    # Word count check
    words = text.split()
    if len(words) < MIN_WORDS:
        return False
    
    # Must contain letters
    if not any(c.isalpha() for c in text):
        return False
    
    # Reject if mostly non-alphabetic
    alpha_count = sum(c.isalpha() or c.isspace() for c in text)
    alpha_ratio = alpha_count / len(text)
    if alpha_ratio < 0.7:
        return False
    
    return True

def calculate_alignment_quality(source: str, target: str) -> float:
    """Calculate alignment quality score for parallel sentences."""
    if not source or not target:
        return 0.0
    
    score = 1.0
    
    # Length ratio check
    len_ratio = len(target) / len(source) if source else 0
    if len_ratio < 0.5 or len_ratio > 3.0:
        score -= 0.3
    elif len_ratio < 0.7 or len_ratio > 2.0:
        score -= 0.1
    
    # Word count ratio
    src_words = len(source.split())
    tgt_words = len(target.split())
    word_ratio = tgt_words / src_words if src_words > 0 else 0
    if word_ratio < 0.5 or word_ratio > 2.5:
        score -= 0.2
    
    return max(0.0, min(1.0, score))

# ============================================================================
# ZIP EXTRACTION & PROCESSING ENGINE
# ============================================================================

class TatoebaZipProcessor:
    def __init__(self):
        self.entries: List[Dict] = []
        self.seen_pairs: Set[Tuple[str, str]] = set()
        self.stats = {
            'lines_total': 0,
            'lines_valid': 0,
            'lines_skipped': 0,
            'duplicates_removed': 0,
            'misaligned': 0
        }
    
    def process(self) -> None:
        """Main processing pipeline."""
        logger.info(f"🚀 Starting Tatoeba ZIP processing from: {ZIP_FILE}")
        
        if not ZIP_FILE.exists():
            logger.error(f"❌ ZIP file not found: {ZIP_FILE}")
            return
        
        try:
            # Step 1: Extract ZIP
            self._extract_zip()
            
            # Step 2: Locate text files
            cbk_file, en_file = self._locate_text_files()
            
            if not cbk_file or not en_file:
                logger.error("❌ Could not locate required text files in ZIP")
                return
            
            # Step 3: Process parallel files
            self._process_parallel_files(cbk_file, en_file)
            
            # Step 4: Save results
            self._save_results()
            self._log_statistics()
        
        except Exception as e:
            logger.error(f"❌ Critical error: {e}")
    
    def _extract_zip(self) -> None:
        """Extract ZIP archive."""
        logger.info(f"📂 Extracting ZIP to: {EXTRACT_DIR}")
        
        try:
            EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_DIR)
            
            logger.info("✅ ZIP extracted successfully")
        
        except Exception as e:
            logger.error(f"❌ Error extracting ZIP: {e}")
            raise
    
    def _locate_text_files(self) -> Tuple[Path, Path]:
        """Locate Chavacano and English text files within extracted content."""
        logger.info("🔍 Locating text files...")
        
        cbk_file = None
        en_file = None
        
        # Search recursively for the specific files
        for file_path in EXTRACT_DIR.rglob("*"):
            if file_path.is_file():
                if "Tatoeba.cbk-en.cbk" in file_path.name or file_path.name == "cbk-en.cbk":
                    cbk_file = file_path
                    logger.info(f"   Found Chavacano: {cbk_file.name}")
                
                if "Tatoeba.cbk-en.en" in file_path.name or file_path.name == "cbk-en.en":
                    en_file = file_path
                    logger.info(f"   Found English: {en_file.name}")
        
        return cbk_file, en_file
    
    def _process_parallel_files(self, cbk_file: Path, en_file: Path) -> None:
        """Process parallel text files and create aligned pairs."""
        logger.info("⚡ Processing parallel sentences...")
        
        try:
            # Read files with UTF-8 encoding
            with cbk_file.open('r', encoding='utf-8') as f_cbk, \
                 en_file.open('r', encoding='utf-8') as f_en:
                
                cbk_lines = f_cbk.readlines()
                en_lines = f_en.readlines()
                
                self.stats['lines_total'] = len(cbk_lines)
                
                # Check alignment
                if len(cbk_lines) != len(en_lines):
                    logger.warning(
                        f"⚠️ Line count mismatch: {len(cbk_lines)} CBK vs {len(en_lines)} EN. "
                        "Using shorter length."
                    )
                    self.stats['misaligned'] = abs(len(cbk_lines) - len(en_lines))
                
                # Process paired lines
                for idx, (cbk_line, en_line) in enumerate(zip(cbk_lines, en_lines), 1):
                    self._process_pair(cbk_line, en_line, idx)
        
        except Exception as e:
            logger.error(f"❌ Error processing files: {e}")
            raise
    
    def _process_pair(self, cbk_text: str, en_text: str, line_num: int) -> None:
        """Process a single sentence pair."""
        try:
            # Clean sentences
            chavacano = clean_sentence(cbk_text)
            english = clean_sentence(en_text)
            
            # Validation
            if not is_valid_sentence(chavacano) or not is_valid_sentence(english):
                self.stats['lines_skipped'] += 1
                return
            
            # Deduplication
            pair_key = (chavacano.lower(), english.lower())
            if pair_key in self.seen_pairs:
                self.stats['duplicates_removed'] += 1
                return
            
            self.seen_pairs.add(pair_key)
            
            # Calculate quality
            alignment_quality = calculate_alignment_quality(chavacano, english)
            
            # Create NLLB-200 formatted entry
            entry = {
                "chavacano": chavacano,
                "english": english,
                "type": "sentence",
                "category": "sentence_pair",
                "source": "tatoeba",
                "alignment_score": round(alignment_quality, 3),
                "languages": ["cbk_Latn", "eng_Latn"],
                "line_id": line_num
            }
            
            self.entries.append(entry)
            self.stats['lines_valid'] += 1
        
        except Exception as e:
            logger.debug(f"⚠️ Error processing line {line_num}: {e}")
            self.stats['lines_skipped'] += 1
    
    def _save_results(self) -> None:
        """Save processed data to JSON."""
        try:
            with OUTPUT_JSON.open('w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'source': 'Tatoeba Project (cbk-en)',
                        'extraction_date': datetime.now().isoformat(),
                        'language_pair': ['cbk_Latn', 'eng_Latn'],
                        'total_pairs': len(self.entries),
                        'nllb_200_ready': True,
                        'license': 'CC BY 2.0 FR',
                        'url': 'https://tatoeba.org'
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
        logger.info(f"   Total Lines:         {self.stats['lines_total']}")
        logger.info(f"   Valid Pairs:         {self.stats['lines_valid']}")
        logger.info(f"   Skipped (Quality):   {self.stats['lines_skipped']}")
        logger.info(f"   Duplicates Removed:  {self.stats['duplicates_removed']}")
        logger.info(f"   Misaligned Lines:    {self.stats['misaligned']}")
        
        # Calculate NLLB-200 readiness score
        if self.stats['lines_total'] > 0:
            quality_ratio = self.stats['lines_valid'] / self.stats['lines_total']
            alignment_ratio = 1.0 - (self.stats['misaligned'] / self.stats['lines_total'])
            
            # Readiness: quality retention (70%) + alignment (30%)
            readiness_score = (quality_ratio * 0.7 + alignment_ratio * 0.3) * 100
        else:
            readiness_score = 0.0
        
        logger.info(f"   🎯 NLLB-200 Readiness: {readiness_score:.1f}%")
        logger.info("=" * 60)
        
        # Justification
        logger.info("\n✅ NLLB-200 Standards Met:")
        logger.info("   • Sentence-aligned parallel corpus")
        logger.info("   • UTF-8 Unicode normalization (NFC)")
        logger.info("   • Automated ZIP extraction")
        logger.info("   • Quality scoring and deduplication")
        logger.info("   • Tatoeba license compliance (CC BY 2.0 FR)")
        
        # Sample preview
        if self.entries:
            logger.info("\n🔍 Sample Entries:")
            for entry in self.entries[:3]:
                logger.info(f"   CBK: {entry['chavacano']}")
                logger.info(f"   ENG: {entry['english']}")
                logger.info(f"   Score: {entry['alignment_score']}\n")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute the Tatoeba ZIP processing pipeline."""
    processor = TatoebaZipProcessor()
    processor.process()

if __name__ == "__main__":
    main()
