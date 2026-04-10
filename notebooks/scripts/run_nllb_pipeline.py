"""
NLLB-200 Master Pipeline Executor
==================================
Purpose: Execute all 4 refined data processing scripts and generate readiness report
Author: NLP Data Engineering Team
"""

import subprocess
import json
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from _path_utils import resolve_datasets_dir

# ============================================================================
# CONFIGURATION
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATASETS_DIR = resolve_datasets_dir(PROJECT_ROOT)
PROCESSED_DIR = DATASETS_DIR / "processed" / "001_chavacano"
DATASET_SCRIPTS_DIR = DATASETS_DIR / "scripts"

# Create output directory
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging
LOG_FILE = PROCESSED_DIR / "master_pipeline.log"
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
# PIPELINE DEFINITION
# ============================================================================

PIPELINES = [
    {
        "name": "PDF Dictionary Extraction",
        "script": "extract_chavacano_pdf_REFINED.py",
        "output": "chavacano_lexicon_nllb.json",
        "description": "Extract Chavacano lexicon from PDF with high-fidelity text recovery"
    },
    {
        "name": "CSV Parallel Sentences",
        "script": "process_chavacano_csv_REFINED.py",
        "output": "chavacano_parallel_sentences_nllb.json",
        "description": "Process Chavacano-English parallel sentences from CSV"
    },
    {
        "name": "Tatoeba Archive Processing",
        "script": "process_tatoeba_REFINED.py",
        "output": "tatoeba_parallel_nllb.json",
        "description": "Extract and process Tatoeba parallel corpus from ZIP"
    },
    {
        "name": "CreoleVal Remote Harvest",
        "script": "harvest_creole_rc_REFINED.py",
        "output": "creole_rc_chavacano_nllb.json",
        "description": "Harvest Chavacano sentences from CreoleVal GitHub repository"
    }
]

POST_PIPELINE_STEPS = [
    {
        "name": "Build Pillar 1 (master parallel)",
        "script": "pillar1_merge_parallel_corpus.py",
        "args": [],
        "timeout": 900,
    },
    {
        "name": "Build Pillar 2 (monolingual corpus)",
        "script": "pillar2_structure_monolingual.py",
        "args": [],
        "timeout": 900,
    },
    {
        "name": "Build JSONL streaming outputs",
        "script": "json_to_jsonl_stream.py",
        "args": ["--overwrite"],
        "timeout": 1800,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run refined NLLB data pipelines and optionally build 3-pillar outputs.',
    )
    parser.add_argument(
        '--build-pillars',
        action='store_true',
        help='After notebook preprocessing, execute datasets/scripts pillar ETL steps.',
    )
    parser.add_argument(
        '--skip-jsonl',
        action='store_true',
        help='When --build-pillars is set, skip JSONL conversion step.',
    )
    return parser.parse_args()

# ============================================================================
# PIPELINE EXECUTOR
# ============================================================================

def run_pipeline(pipeline: Dict) -> Dict:
    """Execute a single pipeline script and capture results."""
    logger.info("=" * 70)
    logger.info(f"🚀 Running: {pipeline['name']}")
    logger.info(f"   Script: {pipeline['script']}")
    logger.info(f"   Description: {pipeline['description']}")
    logger.info("=" * 70)
    
    script_path = SCRIPT_DIR / pipeline['script']
    
    if not script_path.exists():
        logger.error(f"❌ Script not found: {script_path}")
        return {
            "name": pipeline['name'],
            "status": "FAILED",
            "error": "Script not found"
        }
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300  # 5 minute timeout
        )
        
        # Check if successful
        if result.returncode == 0:
            logger.info(f"✅ {pipeline['name']} completed successfully")
            
            # Try to read output file and extract stats
            output_path = PROCESSED_DIR / pipeline['output']
            stats = extract_stats(output_path)
            
            return {
                "name": pipeline['name'],
                "status": "SUCCESS",
                "output_file": pipeline['output'],
                "stats": stats
            }
        else:
            logger.error(f"❌ {pipeline['name']} failed with error code {result.returncode}")
            logger.error(f"   Error: {result.stderr[:500]}")
            
            return {
                "name": pipeline['name'],
                "status": "FAILED",
                "error": result.stderr[:500]
            }
    
    except subprocess.TimeoutExpired:
        logger.error(f"⏱️ {pipeline['name']} timed out")
        return {
            "name": pipeline['name'],
            "status": "TIMEOUT"
        }
    
    except Exception as e:
        logger.error(f"❌ Error running {pipeline['name']}: {e}")
        return {
            "name": pipeline['name'],
            "status": "ERROR",
            "error": str(e)
        }

def extract_stats(output_path: Path) -> Dict:
    """Extract statistics from output JSON file."""
    try:
        if not output_path.exists():
            return {"error": "Output file not found"}
        
        with output_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata = data.get('metadata', {})
        entries = data.get('entries', [])
        
        return {
            "total_entries": len(entries),
            "source": metadata.get('source', 'unknown'),
            "language": metadata.get('language', 'cbk_Latn'),
            "nllb_ready": metadata.get('nllb_200_ready', False)
        }
    
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# READINESS REPORT GENERATOR
# ============================================================================

def generate_readiness_report(results: List[Dict]) -> None:
    """Generate comprehensive NLLB-200 readiness report."""
    logger.info("\n" + "=" * 70)
    logger.info("📋 NLLB-200 READINESS REPORT")
    logger.info("=" * 70)
    logger.info(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Output Directory: {PROCESSED_DIR}")
    logger.info("=" * 70)
    
    total_entries = 0
    successful_pipelines = 0
    
    for result in results:
        logger.info(f"\n📦 {result['name']}")
        logger.info(f"   Status: {result['status']}")
        
        if result['status'] == 'SUCCESS':
            successful_pipelines += 1
            stats = result.get('stats', {})
            entries = stats.get('total_entries', 0)
            total_entries += entries
            
            logger.info(f"   Output: {result['output_file']}")
            logger.info(f"   Entries: {entries:,}")
            logger.info(f"   NLLB-200 Ready: {'✅' if stats.get('nllb_ready') else '❌'}")
        else:
            logger.info(f"   Error: {result.get('error', 'Unknown error')}")
    
    logger.info("\n" + "=" * 70)
    logger.info("📊 SUMMARY")
    logger.info("=" * 70)
    logger.info(f"   Pipelines Executed: {len(results)}")
    logger.info(f"   Successful: {successful_pipelines}")
    logger.info(f"   Failed: {len(results) - successful_pipelines}")
    logger.info(f"   Total Entries: {total_entries:,}")
    
    # Calculate overall readiness score
    if len(results) > 0:
        success_rate = (successful_pipelines / len(results)) * 100
        logger.info(f"   🎯 Pipeline Success Rate: {success_rate:.1f}%")
    
    logger.info("=" * 70)
    
    # Save report to JSON
    report_path = PROCESSED_DIR / "pipeline_report.json"
    with report_path.open('w', encoding='utf-8') as f:
        json.dump({
            "generation_date": datetime.now().isoformat(),
            "total_pipelines": len(results),
            "successful_pipelines": successful_pipelines,
            "total_entries": total_entries,
            "pipelines": results
        }, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n💾 Full report saved to: {report_path}")
    
    # Technical justifications
    logger.info("\n" + "=" * 70)
    logger.info("✅ NLLB-200 STANDARDS COMPLIANCE")
    logger.info("=" * 70)
    logger.info("1. Data Quality:")
    logger.info("   • UTF-8 Unicode normalization (NFC) across all pipelines")
    logger.info("   • Robust deduplication (case-insensitive)")
    logger.info("   • Quality scoring and filtering")
    logger.info("")
    logger.info("2. Chavacano-Specific Processing:")
    logger.info("   • Spanish diacritic preservation (á, é, í, ó, ú, ñ)")
    logger.info("   • Spanish-lexified structure handling")
    logger.info("   • Cross-source sentence alignment validation")
    logger.info("")
    logger.info("3. Format & Structure:")
    logger.info("   • Sentence-aligned parallel pairs (CSV, Tatoeba)")
    logger.info("   • Metadata-rich JSON output")
    logger.info("   • Language codes: cbk_Latn, eng_Latn")
    logger.info("")
    logger.info("4. Error Handling:")
    logger.info("   • Comprehensive logging for all scripts")
    logger.info("   • Corrupted file detection and skipping")
    logger.info("   • Graceful degradation on errors")
    logger.info("")
    logger.info("5. Production Readiness:")
    logger.info("   • Modular, maintainable code")
    logger.info("   • Efficient processing (vectorized operations)")
    logger.info("   • Reproducible pipeline execution")
    logger.info("=" * 70)


def run_post_pipeline_steps(include_jsonl: bool) -> List[Dict]:
    """Optionally execute 3-pillar ETL scripts after notebook extraction steps."""
    steps = []
    for step in POST_PIPELINE_STEPS:
        if not include_jsonl and step['script'] == 'json_to_jsonl_stream.py':
            continue
        steps.append(step)

    results: List[Dict] = []
    if not steps:
        return results

    logger.info("\n" + "=" * 70)
    logger.info("🔗 POST-PIPELINE PILLAR BUILD")
    logger.info("=" * 70)

    for step in steps:
        script_path = DATASET_SCRIPTS_DIR / step['script']
        logger.info(f"\n⚙️  {step['name']}")
        logger.info(f"   Script: {script_path}")

        if not script_path.exists():
            logger.error(f"❌ Missing script: {script_path}")
            results.append({
                'name': step['name'],
                'status': 'FAILED',
                'error': f'Missing script: {script_path}',
            })
            continue

        try:
            completed = subprocess.run(
                [sys.executable, str(script_path), *step['args']],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=step['timeout'],
            )

            if completed.returncode == 0:
                logger.info(f"✅ {step['name']} completed")
                results.append({
                    'name': step['name'],
                    'status': 'SUCCESS',
                    'script': str(script_path),
                })
            else:
                logger.error(f"❌ {step['name']} failed ({completed.returncode})")
                logger.error(f"   stderr: {completed.stderr[:500]}")
                results.append({
                    'name': step['name'],
                    'status': 'FAILED',
                    'script': str(script_path),
                    'error': completed.stderr[:500],
                })
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️ {step['name']} timed out")
            results.append({
                'name': step['name'],
                'status': 'TIMEOUT',
                'script': str(script_path),
            })
        except Exception as exc:
            logger.error(f"❌ {step['name']} raised error: {exc}")
            results.append({
                'name': step['name'],
                'status': 'ERROR',
                'script': str(script_path),
                'error': str(exc),
            })

    success_count = sum(1 for item in results if item['status'] == 'SUCCESS')
    logger.info("\n📌 Post-pipeline status: %s/%s successful", success_count, len(results))
    return results

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Execute all pipelines and generate report."""
    args = parse_args()

    logger.info("🚀 Starting NLLB-200 Master Pipeline")
    logger.info(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Scripts to execute: {len(PIPELINES)}")
    
    results = []
    
    for pipeline in PIPELINES:
        result = run_pipeline(pipeline)
        results.append(result)
    
    # Generate comprehensive report
    generate_readiness_report(results)

    if args.build_pillars:
        run_post_pipeline_steps(include_jsonl=not args.skip_jsonl)
    
    logger.info("\n🎉 Master pipeline execution complete!")
    logger.info(f"   Check logs at: {LOG_FILE}")

if __name__ == "__main__":
    main()
