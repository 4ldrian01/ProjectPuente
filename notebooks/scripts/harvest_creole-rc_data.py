import pandas as pd
import os

# --- CONFIGURATION ---
# 1. THE CORRECT URL (Extracted from creole_rc.py line 37)
# Notice: it is inside 'relation_extraction' folder and uses a hyphen 'cbk-zam'
SOURCE_URL = "https://raw.githubusercontent.com/hclent/CreoleVal/main/nlu/relation_classification/data/relation_extraction/cbk-zam.csv"

# 2. Output File Path
OUTPUT_PATH = "C:/Users/User's/ALL FILES - MACHINE LEARNING/ProjectPuente/Datasets/processed/creole_rc_chavacano_text.txt"

def harvest_creole_rc():
    print(f"🚜 Contacting GitHub to fetch Creole_RC data from:\n   {SOURCE_URL}...")
    
    try:
        # 1. Read the CSV directly from the URL
        # We use 'header=0' because the file has a header row
        df = pd.read_csv(SOURCE_URL, header=0)
        
        # 2. Inspect it (Debug check)
        print(f"   -> Columns found: {df.columns.tolist()}")
        
        # 3. Extract the Chavacano Text
        # The text is in the FIRST column (Index 0)
        chavacano_sentences = df.iloc[:, 0].dropna().tolist()
        
        # 4. Save to a simple Text File
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        
        count = 0
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for sentence in chavacano_sentences:
                # Clean up: remove newlines inside the sentence
                clean_sent = sentence.replace('\n', ' ').strip()
                if len(clean_sent) > 5:  # Skip tiny garbage entries
                    f.write(clean_sent + "\n")
                    count += 1
                
        print("\n" + "="*40)
        print(f"✅ SUCCESS! Extracted {count} sentences.")
        print(f"📂 Saved to: {OUTPUT_PATH}")
        print("="*40)
        
        # Preview
        print("First 3 sentences:")
        for s in chavacano_sentences[:3]:
            print(f" - {s}")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        print("   -> Verify the URL is accessible in your browser.")

if __name__ == "__main__":
    harvest_creole_rc()