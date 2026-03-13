import json
import os
import zipfile

# --- CONFIGURATION ---

# --- PATHS RELATIVE TO THIS SCRIPT ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Where is the ZIP file? (Relative to notebooks/scripts/)
RAW_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datasets/raw/02_Chavacano"))
ZIP_FILE = os.path.join(RAW_DIR, "cbk-en.txt.zip")

# 2. Where should we extract it temporarily?
EXTRACT_DIR = os.path.join(RAW_DIR, "tatoeba_extracted")

# 3. Where should the final JSON go?
PROCESSED_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datasets/processed/01_Chavacano"))
OUTPUT_JSON = os.path.join(PROCESSED_DIR, "tatoeba_dataset.json")

def process_pipeline():
    print("🚀 STARTING TATOEBA PIPELINE...")
    print(f"📦 Target Zip: {os.path.abspath(ZIP_FILE)}")

    # --- STEP 1: UNZIP THE FILE ---
    if not os.path.exists(ZIP_FILE):
        print(f"❌ ERROR: Zip file not found at {ZIP_FILE}")
        return

    print("📂 Unzipping files...")
    try:
        with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        print(f"   -> Extracted to: {EXTRACT_DIR}")
    except Exception as e:
        print(f"❌ Error unzipping: {e}")
        return

    # --- STEP 2: LOCATE THE TEXT FILES ---
    # We look for the specific .cbk and .en files inside the extracted folder
    # Note: Sometimes zips have subfolders, so we walk to find them.
    file_cbk = None
    file_en = None

    for root, dirs, files in os.walk(EXTRACT_DIR):
        if "Tatoeba.cbk-en.cbk" in files:
            file_cbk = os.path.join(root, "Tatoeba.cbk-en.cbk")
        if "Tatoeba.cbk-en.en" in files:
            file_en = os.path.join(root, "Tatoeba.cbk-en.en")

    if not file_cbk or not file_en:
        print("❌ ERROR: Could not find 'Tatoeba.cbk-en.cbk' or 'Tatoeba.cbk-en.en' inside the zip.")
        return
    
    print(f"   -> Found Chavacano file: {os.path.basename(file_cbk)}")
    print(f"   -> Found English file:   {os.path.basename(file_en)}")

    # --- STEP 3: PROCESS AND PAIR (The "Zipper" Logic) ---
    print("⚡ Processing text pairs...")
    try:
        with open(file_cbk, 'r', encoding='utf-8') as f_cbk, \
             open(file_en, 'r', encoding='utf-8') as f_en:
            
            cbk_lines = f_cbk.readlines()
            en_lines = f_en.readlines()

            if len(cbk_lines) != len(en_lines):
                print(f"⚠️ WARNING: Line count mismatch ({len(cbk_lines)} vs {len(en_lines)}). Truncating to shorter.")

            tatoeba_data = []
            count = 0
            
            for c, e in zip(cbk_lines, en_lines):
                clean_cbk = c.strip()
                clean_en = e.strip()
                
                if clean_cbk and clean_en:
                    entry = {
                        "chavacano": clean_cbk,
                        "english": clean_en,
                        "type": "sentence",
                        "category": "sentence_pair",
                        "source": "tatoeba"
                    }
                    tatoeba_data.append(entry)
                    count += 1

        # --- STEP 4: SAVE JSON ---
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(tatoeba_data, f, indent=4, ensure_ascii=False)

        print("\n" + "="*40)
        print(f"✅ PIPELINE COMPLETE!")
        print(f"📊 Extracted & Processed: {count} pairs")
        print(f"💾 Saved Final JSON to: {os.path.abspath(OUTPUT_JSON)}")
        print("="*40)

    except Exception as e:
        print(f"❌ CRITICAL ERROR DURING PROCESSING: {e}")

if __name__ == "__main__":
    process_pipeline()