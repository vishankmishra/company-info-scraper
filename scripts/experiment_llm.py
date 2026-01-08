#!/usr/bin/env python3
"""
Phase B: Offline LLM Experimentation Script

Purpose:
    Test multiple LLM models on raw scraped data to compare extraction accuracy.
    
Architecture:
    JSONL (raw_text) → LLM → Structured JSON → JSONL (results)
    
Models Tested:
    - qwen2.5:7b-instruct (Primary - recommended in implementation plan)
    - gemma:7b (Google's Gemma)
    - glm4:9b (ChatGLM)
    
Output:
    data/experiment_results.jsonl - One line per model+domain combination
    
Usage:
    python scripts/experiment_llm.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from company_info_scraper.services.llm_service import LLMExtractionService


# ============================================================================
# CONFIGURATION
# ============================================================================

MODELS_TO_TEST = [
    'llama3.2:1b',           # Fast on CPU! (7B models too slow without GPU)
    # 'qwen2.5:7b-instruct', # Too slow on CPU (20-60min per domain)
    # 'gemma:7b',            # Too slow on CPU
]

MAX_TEXT_LENGTH = 7000   # Reduced from 10000 for better performance
TIMEOUT = 60             # 1 minute (1B model is fast on CPU!)
MAX_DOMAINS_PER_MODEL = 10  # Increased to 10 (much faster now)

INPUT_FILE = project_root / 'data' / 'phase_a_raw.jsonl'
OUTPUT_FILE = project_root / 'data' / 'experiment_results.jsonl'


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_raw_data(file_path: Path) -> List[Dict[str, Any]]:
    """Load raw scraped data from JSONL file."""
    records = []
    
    if not file_path.exists():
        print(f"❌ Error: Input file not found: {file_path}")
        sys.exit(1)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Skipping invalid JSON on line {line_num}: {e}")
    
    return records


def filter_valid_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter records with valid content for extraction."""
    valid = []
    
    for record in records:
        # Check if scrape was successful
        if record.get('scrape_status') != 'success':
            continue
        
        # Check if raw_text exists and is not empty/error
        raw_text = record.get('raw_text', '').strip()
        if not raw_text:
            continue
        
        # Skip error pages
        if 'ERROR:' in raw_text[:100] or 'HTTP 403' in raw_text[:100]:
            continue
        
        valid.append(record)
    
    return valid


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_progress(current: int, total: int, domain: str, status: str = ""):
    """Print progress for current extraction."""
    progress = f"[{current}/{total}]"
    print(f"{progress:>10} {domain:40} {status}")


# ============================================================================
# MAIN EXPERIMENT LOGIC
# ============================================================================

async def run_experiment_for_model(
    model_name: str,
    records: List[Dict[str, Any]],
    output_file: Path
) -> Dict[str, Any]:
    """Run extraction experiment for a single model on all records."""
    
    print_header(f"Testing Model: {model_name}")
    
    # Initialize service with current model
    try:
        service = LLMExtractionService(
            model=model_name,
            timeout=TIMEOUT,
            max_text_length=MAX_TEXT_LENGTH
        )
        print(f"✓ Initialized LLM service with model: {model_name}")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return {
            'model': model_name,
            'status': 'failed',
            'error': str(e),
            'extractions': []
        }
    
    # Limit to first N domains for dev phase
    test_records = records[:MAX_DOMAINS_PER_MODEL]
    total = len(test_records)
    
    print(f"✓ Processing {total} domains (limited to {MAX_DOMAINS_PER_MODEL} for dev phase)")
    print()
    
    results = []
    successful = 0
    failed = 0
    
    start_time = time.time()
    
    # Process each record
    for idx, record in enumerate(test_records, 1):
        domain = record.get('domain', 'unknown')
        raw_text = record.get('raw_text', '')
        final_url = record.get('final_url', '')
        
        print_progress(idx, total, domain, "extracting...")
        
        try:
            # Run extraction
            extraction_start = time.time()
            result = await service.extract(raw_text, url=final_url or domain)
            extraction_time = time.time() - extraction_start
            
            # Prepare result record
            result_record = {
                'model': model_name,
                'domain': domain,
                'final_url': final_url,
                'extraction': {
                    'products': result.products,
                    'services': result.services,
                    'customers': result.customers,
                    'partnerships': result.partnerships,
                    'case_studies': result.case_studies,
                    'status': result.status,
                    'error': result.error
                },
                'extraction_time_seconds': round(extraction_time, 2),
                'text_length': len(raw_text)
            }
            
            results.append(result_record)
            
            # Update stats
            if result.status == 'success':
                successful += 1
                status_icon = "✓"
            else:
                failed += 1
                status_icon = "✗"
            
            print_progress(
                idx, total, domain,
                f"{status_icon} {result.status} ({extraction_time:.1f}s)"
            )
            
            # Write result immediately (streaming output)
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(result_record, ensure_ascii=False) + '\n')
        
        except Exception as e:
            failed += 1
            error_msg = str(e)[:100]
            print_progress(idx, total, domain, f"✗ ERROR: {error_msg}")
            
            # Write error result
            error_record = {
                'model': model_name,
                'domain': domain,
                'final_url': final_url,
                'extraction': {
                    'products': 'N/A',
                    'services': 'N/A',
                    'customers': 'N/A',
                    'partnerships': 'N/A',
                    'case_studies': 'N/A',
                    'status': 'error',
                    'error': error_msg
                },
                'extraction_time_seconds': 0,
                'text_length': len(raw_text)
            }
            results.append(error_record)
            
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_record, ensure_ascii=False) + '\n')
    
    total_time = time.time() - start_time
    
    # Print summary
    print()
    print(f"{'─' * 70}")
    print(f"  Model: {model_name}")
    print(f"  Total: {total} | Successful: {successful} | Failed: {failed}")
    print(f"  Success Rate: {successful/total*100:.1f}%")
    print(f"  Total Time: {total_time:.1f}s | Avg: {total_time/total:.1f}s/domain")
    print(f"{'─' * 70}")
    
    return {
        'model': model_name,
        'status': 'completed',
        'total': total,
        'successful': successful,
        'failed': failed,
        'success_rate': round(successful / total * 100, 1),
        'total_time_seconds': round(total_time, 1),
        'avg_time_per_domain': round(total_time / total, 1),
        'extractions': results
    }


async def main():
    """Main experiment orchestrator."""
    
    print_header("Phase B: Offline LLM Experimentation")
    print()
    print("🚀 DEBUG: Using llama3.2:1b (fast on CPU). 7B models too slow without GPU.")
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Models: {', '.join(MODELS_TO_TEST)}")
    print(f"Config: max_text_length={MAX_TEXT_LENGTH}, timeout={TIMEOUT}s")
    print(f"DEBUG: Using timeout={TIMEOUT}s and max_length={MAX_TEXT_LENGTH}")
    print()
    
    # Load and filter data
    print("Loading raw data...")
    all_records = load_raw_data(INPUT_FILE)
    print(f"✓ Loaded {len(all_records)} total records")
    
    valid_records = filter_valid_records(all_records)
    print(f"✓ Filtered to {len(valid_records)} valid records")
    
    if len(valid_records) == 0:
        print("❌ No valid records found. Exiting.")
        sys.exit(1)
    
    # Clear output file
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
        print(f"✓ Cleared existing output file")
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Run experiment for each model
    experiment_start = time.time()
    model_summaries = []
    
    for model_idx, model_name in enumerate(MODELS_TO_TEST, 1):
        print()
        print(f"\n{'█' * 70}")
        print(f"  MODEL {model_idx}/{len(MODELS_TO_TEST)}: {model_name}")
        print(f"{'█' * 70}")
        
        try:
            summary = await run_experiment_for_model(
                model_name,
                valid_records,
                OUTPUT_FILE
            )
            model_summaries.append(summary)
        except Exception as e:
            print(f"\n❌ Fatal error testing {model_name}: {e}")
            model_summaries.append({
                'model': model_name,
                'status': 'fatal_error',
                'error': str(e)
            })
    
    # Print final summary
    total_experiment_time = time.time() - experiment_start
    
    print_header("EXPERIMENT COMPLETE")
    print()
    print(f"Total Experiment Time: {total_experiment_time/60:.1f} minutes")
    print(f"Results saved to: {OUTPUT_FILE}")
    print()
    print("Model Comparison:")
    print(f"{'─' * 70}")
    print(f"{'Model':<30} {'Success Rate':<15} {'Avg Time':<15}")
    print(f"{'─' * 70}")
    
    for summary in model_summaries:
        if summary['status'] == 'completed':
            model_name = summary['model']
            success_rate = f"{summary['success_rate']}%"
            avg_time = f"{summary['avg_time_per_domain']:.1f}s"
            print(f"{model_name:<30} {success_rate:<15} {avg_time:<15}")
        else:
            model_name = summary['model']
            print(f"{model_name:<30} {'ERROR':<15} {'N/A':<15}")
    
    print(f"{'─' * 70}")
    print()
    print("✅ Phase B Experiment Complete!")
    print()
    print("Next Steps:")
    print("  1. Review results in: data/experiment_results.jsonl")
    print("  2. Create gold dataset for evaluation")
    print("  3. Run evaluation metrics (Precision, Recall, F1)")
    print()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

