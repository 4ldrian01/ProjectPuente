import os
import bz2
import xml.etree.ElementTree as ET
import re

# --- CONFIGURATION ---

# --- PATHS RELATIVE TO THIS SCRIPT ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Path relative to notebooks/scripts/
RAW_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datasets/raw/02_Chavacano"))
WIKI_FILE = os.path.join(RAW_DIR, "cbk_zamwiki-latest-pages-articles.xml.bz2")

PROCESSED_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datasets/processed/02_Chavacano"))
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "wiki_monolingual_cleaned.txt")

# Regex patterns to clean Wiki Markup
# 1. Remove {{templates}}
RE_TEMPLATES = re.compile(r'\{\{.*?\}\}', re.DOTALL)
# 2. Remove [[File:...]] or [[Image:...]]
RE_FILES = re.compile(r'\[\[(File|Image):.*?\]\]', re.IGNORECASE)
# 3. Remove [[Category:...]]
RE_CATEGORIES = re.compile(r'\[\[Category:.*?\]\]', re.IGNORECASE)
# 4. Remove headings == Header ==
RE_HEADERS = re.compile(r'={2,}.*?={2,}')
# 5. Remove HTML tags <ref>...</ref>
RE_HTML = re.compile(r'<.*?>', re.DOTALL)
# 6. Extract link text: [[Page Name|Visible Text]] -> Visible Text
RE_LINKS = re.compile(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]')

def clean_wiki_text(text):
    if not text: return ""
    
    # Apply regex cleaning
    text = RE_HTML.sub('', text)           # Remove HTML/Refs first
    text = RE_TEMPLATES.sub('', text)      # Remove templates
    text = RE_FILES.sub('', text)          # Remove images
    text = RE_CATEGORIES.sub('', text)     # Remove categories
    text = RE_HEADERS.sub('', text)        # Remove headers
    text = RE_LINKS.sub(r'\1', text)       # Keep link text
    
    # Remove excessive whitespace
    lines = []
    for line in text.split('\n'):
        clean = line.strip()
        # Keep lines that are actual sentences (heuristic: longer than 20 chars)
        if clean and len(clean) > 20 and not clean.startswith('|'):
            lines.append(clean)
            
    return "\n".join(lines)

def process_wiki():
    print("📚 STARTING WIKI DUMP EXTRACTION...")
    print(f"📦 Target File: {os.path.abspath(WIKI_FILE)}")
    
    if not os.path.exists(WIKI_FILE):
        print("❌ ERROR: File not found!")
        return

    count = 0
    article_count = 0
    
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    try:
        # Open the BZ2 file directly (no need to unzip manually)
        with bz2.open(WIKI_FILE, 'rt', encoding='utf-8') as source, \
             open(OUTPUT_FILE, 'w', encoding='utf-8') as target:
            
            print("⏳ Parsing XML stream (this might take a minute)...")
            
            # Efficiently parse XML event by event to save memory
            context = ET.iterparse(source, events=("end",))
            
            for event, elem in context:
                # We look for the <text> tag inside each page
                if elem.tag.endswith('text'):
                    raw_text = elem.text
                    clean_text = clean_wiki_text(raw_text)
                    
                    if clean_text:
                        target.write(clean_text + "\n")
                        count += len(clean_text.split('\n'))
                        article_count += 1
                
                # Clear memory
                elem.clear()

        print("\n" + "="*40)
        print(f"✅ SUCCESS!")
        print(f"📄 Articles Processed: {article_count}")
        print(f"📊 Sentences Extracted: {count}")
        print(f"💾 Saved to: {os.path.abspath(OUTPUT_FILE)}")
        print("="*40)

    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    process_wiki()