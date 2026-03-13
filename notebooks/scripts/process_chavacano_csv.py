import pandas as pd
import json
import os

# --- CONFIGURATION ---
# 1. The NEW Input Filename you specified
INPUT_CSV_PATH = "C:\\Users\\User's\\ALL FILES - MACHINE LEARNING\\ProjectPuente\\Datasets\\raw\\02_Chavacano\\chavacano-to-english-parallel-sentences.csv"

# 2. The Output File (We will save this as a Cleaned JSON)
OUTPUT_JSON_PATH = "c:/Users/User's/ALL FILES - MACHINE LEARNING/ProjectPuente/Datasets/processed/new_chavacano_master_dataset.json"

def process_chavacano_data():
    print(f"📖 Reading file: {INPUT_CSV_PATH}...")
    
    # 1. Check if file exists
    if not os.path.exists(INPUT_CSV_PATH):
        print(f"❌ ERROR: File not found at {INPUT_CSV_PATH}")
        print("   -> Did you rename the file in your folder yet?")
        print("   -> Please check the spelling carefully.")
        return

    # 2. Load the CSV (Robust loading)
    try:
        # on_bad_lines='skip' helps if there are messy comma errors in the file
        df = pd.read_csv(INPUT_CSV_PATH, on_bad_lines='skip')
        
        # Clean column names (strip spaces just in case: " type " -> "type")
        df.columns = [c.strip().lower() for c in df.columns]
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR reading CSV: {e}")
        return

    # 3. Verify Columns
    # Your CSV has: 'chavacano', 'type', 'english'
    required_cols = ['chavacano', 'type', 'english']
    if not all(col in df.columns for col in required_cols):
        print(f"❌ ERROR: Columns do not match! Found: {df.columns.tolist()}")
        print(f"   -> Expected: {required_cols}")
        return

    processed_data = []
    stats = {"words": 0, "sentences": 0}

    print("⚙️  Processing rows...")

    for index, row in df.iterrows():
        # Get values and clean strings
        source_text = str(row['chavacano']).strip()
        target_text = str(row['english']).strip()
        row_type = str(row['type']).strip().lower()

        # Skip empty rows or garbage data
        if not source_text or not target_text or source_text.lower() == "nan":
            continue

        # --- SMART CLASSIFICATION ---
        # If the type is 'phrase' or 'idiomatic expression', treat as a SENTENCE.
        # Otherwise (noun, verb, adj), treat as a VOCAB WORD.
        
        is_sentence = "phrase" in row_type or "idiomatic" in row_type or len(source_text.split()) > 3
        
        category = "sentence_pair" if is_sentence else "vocabulary"

        entry = {
            "chavacano": source_text,
            "english": target_text,
            "type": row_type,      # e.g., "verb", "phrase"
            "category": category,  # "vocabulary" or "sentence_pair"
            "source": "chavacano-to-english-parallel-sentences"
        }
        
        processed_data.append(entry)
        
        if category == "sentence_pair":
            stats["sentences"] += 1
        else:
            stats["words"] += 1

    # 4. Save to JSON
    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    
    with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=4, ensure_ascii=False)

    # 5. Final Report
    print("\n" + "="*40)
    print("✅ SUCCESS! Data Cleaning Complete.")
    print("="*40)
    print(f"📂 Input:  {INPUT_CSV_PATH}")
    print(f"📂 Output: {OUTPUT_JSON_PATH}")
    print(f"📊 Stats:")
    print(f"   - Total Entries:     {len(processed_data)}")
    print(f"   - Vocabulary Words:  {stats['words']} (For Tokenizer)")
    print(f"   - Parallel Sentences:{stats['sentences']} (For Translation Model)")
    print("="*40)
    
    # Show a sample
    if processed_data:
        print("\n🔍 Sample Entry:")
        print(json.dumps(processed_data[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    process_chavacano_data()