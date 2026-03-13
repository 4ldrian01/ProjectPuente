import pdfplumber
import re
import json
import os

# --- CONFIGURATION ---
PDF_PATH = "c:/Users/User's/ALL FILES - MACHINE LEARNING/ProjectPuente/Datasets/raw/monolingual/ChavacanoIdiomsandDictionary.pdf"  # Update path if needed
OUTPUT_PATH = "c:/Users/User's/ALL FILES - MACHINE LEARNING/ProjectPuente/Datasets/processed/chavacano_lexicon.json"

# Page range for the Dictionary Section (A-Z)
START_PAGE = 12
END_PAGE = 40

def extract_dictionary_robust():
    print(f"📖 Opening {PDF_PATH}...")
    
    if not os.path.exists(PDF_PATH):
        print(f"❌ ERROR: File not found at {PDF_PATH}")
        return

    lexicon_data = []
    
    # --- THE FIX: ROBUST REGEX ---
    # This pattern finds a word + POS tag, then captures everything until the NEXT word + POS tag.
    # It handles multiple entries on the same line (Column 1 + Column 2).
    
    # 1. The Word: ([\w\s()-]+?) -> Captures text (non-greedy)
    # 2. The POS: (n\.|v\.|adj\.|adv\.|prep\.|conj\.|interj\.|pron\.) -> The anchor
    # 3. The Definition: (.*?) -> Captures text until...
    # 4. The Stop Condition: (?=\s+[\w\s()-]+\s+(?:n\.|v\.|...)|$) -> Lookahead for the NEXT entry or End of String
    
    entry_pattern = re.compile(
        r"(?P<word>[\w\s()-]+?)\s+(?P<pos>n\.|v\.|adj\.|adv\.|prep\.|conj\.|interj\.|pron\.)\s+(?P<def>.*?)(?=\s+[\w\s()-]+\s+(?:n\.|v\.|adj\.|adv\.|prep\.|conj\.|interj\.|pron\.)|$)",
        re.IGNORECASE
    )

    with pdfplumber.open(PDF_PATH) as pdf:
        count_found = 0
        
        for i in range(START_PAGE - 1, END_PAGE):
            try:
                # Safety check
                if i >= len(pdf.pages): break
                
                page = pdf.pages[i]
                
                # Extract text using 'layout' mode to preserve spacing between columns
                text = page.extract_text(layout=True)
                
                if not text: continue

                lines = text.split('\n')
                
                for line in lines:
                    clean_line = line.strip()
                    
                    # Skip Headers (e.g., "--- PAGE 12 ---")
                    if "--- PAGE" in clean_line or clean_line.isdigit() or len(clean_line) < 3:
                        continue

                    # --- KEY CHANGE: FINDITER INSTEAD OF MATCH ---
                    # 'finditer' finds ALL occurrences in the line, not just the first one.
                    # This solves the "abaja" + "adentro" merge error.
                    matches = entry_pattern.finditer(clean_line)
                    
                    for match in matches:
                        word = match.group("word").strip()
                        definition = match.group("def").strip()
                        
                        # Clean up: Sometimes the regex catches the previous definition's trailing period as part of the new word.
                        # Logic: If 'word' starts with a period or symbols, clean it.
                        word = re.sub(r'^[\.\,\;\-]+\s*', '', word)

                        # Filter out garbage matches (e.g., if regex matched part of a sentence)
                        if len(word) > 30 or len(definition) < 2:
                            continue

                        entry = {
                            "word": word,
                            "pos": match.group("pos").strip(),
                            "definition": definition,
                            "source": "ChavacanoIdiomsDictionary_2019"
                        }
                        lexicon_data.append(entry)
                        count_found += 1

            except Exception as e:
                print(f"⚠️ Error on page {i}: {e}")
                continue

    # --- SAVING ---
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(lexicon_data, f, indent=4, ensure_ascii=False)

    print(f"✅ FIXED! Extracted {count_found} words.")
    print(f"📂 Saved to: {OUTPUT_PATH}")
    
    # Print the first few entries to verify the fix
    if len(lexicon_data) > 0:
        print("\n🔎 VERIFICATION (First 2 Entries):")
        print(json.dumps(lexicon_data[:2], indent=2))

if __name__ == "__main__":
    extract_dictionary_robust()