"""
NLLB-200 Production Pipeline: PDF Dictionary Extraction
========================================================
Purpose: Extract Chavacano lexicon from PDF with high-fidelity text recovery
Target: NLLB-200 vocabulary augmentation and tokenizer training
Author: NLP Data Engineering Team
"""

import pdfplumber
import re
import json
import logging
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set

# ============================================================================
# CONFIGURATION
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Input/Output paths
RAW_DIR = PROJECT_ROOT / "Datasets" / "raw" / "monolingual"
PDF_FILE = RAW_DIR / "ChavacanoIdiomsandDictionary.pdf"

PROCESSED_DIR = PROJECT_ROOT / "Datasets" / "processed" / "001_chavacano"
OUTPUT_JSON = PROCESSED_DIR / "chavacano_lexicon_nllb.json"
LOG_FILE = PROCESSED_DIR / "pdf_extraction.log"

# Dictionary page range (A-Z section)
START_PAGE = 12
END_PAGE = 40

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
    """Normalize Unicode to NFC (composed form) for consistent tokenization."""
    return unicodedata.normalize('NFC', text)

def clean_chavacano_text(text: str) -> str:
    """
    Clean Chavacano text while preserving Spanish-lexified structure.
    - Removes PDF artifacts (headers, footers, page numbers)
    - Normalizes whitespace
    - Preserves Spanish diacritics (á, é, í, ó, ú, ñ)
    """
    if not text:
        return ""
    
    # Normalize Unicode
    text = normalize_unicode(text)
    
    # Remove common PDF artifacts
    text = re.sub(r'--- PAGE \d+ ---', '', text)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    
    # Normalize whitespace (but preserve structure)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def is_valid_word(word: str) -> bool:
    """Validate if extracted word is likely a real Chavacano entry."""
    if not word or len(word) < 2:
        return False
    
    # Must contain at least one alphabetic character
    if not any(c.isalpha() for c in word):
        return False
    
    # Filter out common PDF artifacts
    artifacts = ['page', 'chapter', 'section', '...', '–', '—']
    if any(art in word.lower() for art in artifacts):
        return False
    
    # Reject if too long (likely a sentence fragment)
    if len(word) > 35:
        return False
    
    return True

def is_valid_definition(definition: str) -> bool:
    """Validate if definition meets quality standards."""
    if not definition or len(definition) < 3:
        return False
    
    # Must have substantial content
    if len(definition.split()) < 2:
        return False
    
    return True

# ============================================================================
# EXTRACTION ENGINE
# ============================================================================

class ChavacanoPDFExtractor:
    def __init__(self):
        self.entries: List[Dict] = []
        self.seen_words: Set[str] = set()
        self.stats = {
            'pages_processed': 0,
            'raw_matches': 0,
            'valid_entries': 0,
            'duplicates_removed': 0,
            'errors': 0
        }
    
    def extract(self) -> None:
        """Main extraction pipeline with error handling."""
        logger.info(f"🚀 Starting PDF extraction from: {PDF_FILE}")
        
        if not PDF_FILE.exists():
            logger.error(f"❌ PDF file not found: {PDF_FILE}")
            return
        
        # Regex pattern for dictionary entries
        # Format: word (pos) definition
        entry_pattern = re.compile(
            r"(?P<word>[\w\s\-áéíóúñÁÉÍÓÚÑ()]+?)\s+"
            r"(?P<pos>n\.|v\.|adj\.|adv\.|prep\.|conj\.|interj\.|pron\.)\s+"
            r"(?P<def>.*?)"
            r"(?=\s+[\w\s\-áéíóúñÁÉÍÓÚÑ()]+\s+(?:n\.|v\.|adj\.|adv\.|prep\.|conj\.|interj\.|pron\.)|$)",
            re.IGNORECASE | re.DOTALL
        )
        
        try:
            with pdfplumber.open(PDF_FILE) as pdf:
                total_pages = min(END_PAGE, len(pdf.pages))
                
                for page_num in range(START_PAGE - 1, total_pages):
                    try:
                        page = pdf.pages[page_num]
                        
                        # Extract text with layout preservation
                        text = page.extract_text(layout=True, x_tolerance=2, y_tolerance=3)
                        
                        if not text:
                            logger.debug(f"⚠️ Empty page: {page_num + 1}")
                            continue
                        
                        self._process_page(text, page_num + 1, entry_pattern)
                        self.stats['pages_processed'] += 1
                        
                    except Exception as e:
                        self.stats['errors'] += 1
                        logger.error(f"⚠️ Error on page {page_num + 1}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"❌ Critical error opening PDF: {e}")
            return
        
        self._save_results()
        self._log_statistics()
    
    def _process_page(self, text: str, page_num: int, pattern: re.Pattern) -> None:
        """Process a single page and extract entries."""
        lines = text.split('\n')
        
        for line in lines:
            clean_line = clean_chavacano_text(line)
            
            if not clean_line or len(clean_line) < 5:
                continue
            
            # Find all matches in the line
            matches = pattern.finditer(clean_line)
            
            for match in matches:
                self.stats['raw_matches'] += 1
                
                word = clean_chavacano_text(match.group("word"))
                pos = match.group("pos").strip()
                definition = clean_chavacano_text(match.group("def"))
                
                # Validation
                if not is_valid_word(word) or not is_valid_definition(definition):
                    continue
                
                # Deduplication (case-insensitive)
                word_lower = word.lower()
                if word_lower in self.seen_words:
                    self.stats['duplicates_removed'] += 1
                    continue
                
                self.seen_words.add(word_lower)
                
                # Create NLLB-200 formatted entry
                entry = {
                    "word": word,
                    "pos": pos,
                    "definition": definition,
                    "source": "ChavacanoIdiomsDictionary_2019",
                    "page": page_num,
                    "language": "cbk_Latn",  # ISO 639-3 code for Chavacano
                    "quality_score": self._calculate_quality(word, definition)
                }
                
                self.entries.append(entry)
                self.stats['valid_entries'] += 1
    
    def _calculate_quality(self, word: str, definition: str) -> float:
        """
        Calculate quality score (0.0-1.0) for NLLB-200 filtering.
        Factors:
        - Word length (reasonable range)
        - Definition completeness
        - Character validity
        """
        score = 1.0
        
        # Word length penalty
        if len(word) < 3:
            score -= 0.2
        elif len(word) > 25:
            score -= 0.3
        
        # Definition quality
        def_words = len(definition.split())
        if def_words < 3:
            score -= 0.3
        elif def_words > 30:
            score -= 0.1
        
        # Character ratio check (avoid garbage)
        alpha_ratio = sum(c.isalpha() for c in word) / len(word) if word else 0
        if alpha_ratio < 0.7:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _save_results(self) -> None:
        """Save extracted lexicon to JSON."""
        try:
            with OUTPUT_JSON.open('w', encoding='utf-8') as f:
                json.dump({
                    'metadata': {
                        'source': 'ChavacanoIdiomsandDictionary.pdf',
                        'extraction_date': datetime.now().isoformat(),
                        'language': 'cbk_Latn',
                        'total_entries': len(self.entries),
                        'pages_processed': f"{START_PAGE}-{END_PAGE}",
                        'nllb_200_ready': True
                    },
                    'entries': self.entries
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved to: {OUTPUT_JSON}")
        
        except Exception as e:
            logger.error(f"❌ Error saving results: {e}")
    
    def _log_statistics(self) -> None:
        """Log extraction statistics."""
        logger.info("=" * 60)
        logger.info("📊 EXTRACTION COMPLETE - Statistics:")
        logger.info(f"   Pages Processed:     {self.stats['pages_processed']}")
        logger.info(f"   Raw Regex Matches:   {self.stats['raw_matches']}")
        logger.info(f"   Valid Entries:       {self.stats['valid_entries']}")
        logger.info(f"   Duplicates Removed:  {self.stats['duplicates_removed']}")
        logger.info(f"   Errors Encountered:  {self.stats['errors']}")
        
        # Calculate NLLB-200 readiness score
        if self.stats['raw_matches'] > 0:
            quality_ratio = self.stats['valid_entries'] / self.stats['raw_matches']
            readiness_score = quality_ratio * 100
        else:
            readiness_score = 0.0
        
        logger.info(f"   🎯 NLLB-200 Readiness: {readiness_score:.1f}%")
        logger.info("=" * 60)
        
        # Sample preview
        if self.entries:
            logger.info("\n🔍 Sample Entries:")
            for entry in self.entries[:3]:
                logger.info(f"   {entry['word']} ({entry['pos']}): {entry['definition'][:60]}...")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute the extraction pipeline."""
    extractor = ChavacanoPDFExtractor()
    extractor.extract()

if __name__ == "__main__":
    main()
