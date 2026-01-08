#!/usr/bin/env python3
"""
Phase B: Groq API Experimentation Script

Purpose:
    Test multiple Groq models on raw scraped data to compare extraction accuracy.
    Pivot from local Ollama models (too slow/timeouts) to Groq API for faster results.
    
Architecture:
    JSONL (raw_text) → Groq API → Structured JSON → JSONL (results)
    
Models Tested:
    - llama-3.1-70b-versatile (High intelligence)
    - mixtral-8x7b-32768 (Long context)
    - gemma2-9b-it (Efficiency baseline)
    
Output:
    data/experiment_results_groq.jsonl - One line per model+domain combination
    
Usage:
    python scripts/experiment_groq.py
    
Requirements:
    pip install groq
    export GROQ_API_KEY="your-api-key"
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from groq import Groq
except ImportError:
    print("❌ Error: groq package not installed. Run: pip install groq")
    sys.exit(1)

from company_info_scraper.models.extraction_schema import ExtractionSchema


# ============================================================================
# CONFIGURATION
# ============================================================================

MODELS_TO_TEST = [
    'llama-3.3-70b-versatile',                    # Baseline Winner
    'openai/gpt-oss-120b',                        # New "GPT-OSS" Flagship
    'mistral-saba-24b',                           # Mistral's new efficient model
    'qwen/qwen3-32b',                             # Structured Data Specialist
    'meta-llama/llama-4-maverick-17b-128e-instruct', # Llama 4 Preview (Latest)
    'gemma2-9b-it'                                # Google Baseline
]

MAX_DOMAINS_PER_MODEL = 5  # First 5 valid domains per model
RATE_LIMIT_DELAY = 3        # Seconds between requests (avoid 429 errors)
MAX_TEXT_LENGTH = 25000     # Truncate if absolutely huge (Groq handles large contexts well)

INPUT_FILE = project_root / 'data' / 'enterprise_raw.jsonl'
OUTPUT_FILE = project_root / 'data' / 'experiment_results_groq.jsonl'

# System prompt for extraction
SYSTEM_PROMPT = (
    "You are a precise data extraction AI. Extract the following fields from the corporate website text: "
    "products, services, customers, partnerships, case_studies, leadership, emails, phones. "
    "Return ONLY valid JSON matching this structure: "
    '{"products": [], "services": [], "customers": [], "partnerships": [], "case_studies": [], '
    '"leadership": [], "emails": [], "phones": []}. '
    "Each field should be a list of strings. "
    "For leadership, include names with titles (e.g., 'John Doe - CEO'). "
    "For emails and phones, extract contact information found on the page. "
    "If no information is found for any field, use an empty list."
)


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


def truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Truncate text if it exceeds max_length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n[Text truncated for length...]"


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_progress(current: int, total: int, domain: str, status: str = ""):
    """Print progress for current extraction."""
    progress = f"[{current}/{total}]"
    print(f"{progress:>10} {domain:40} {status}")


def smart_merge(scraper_list: List, llm_list: List) -> List[str]:
    """
    Smart merge of scraper-extracted data with LLM-extracted data.
    
    Args:
        scraper_list: List from scraper (may contain dicts with 'value' key or strings)
        llm_list: List from LLM (strings)
    
    Returns:
        Deduplicated list of strings
    """
    merged_set = set()
    
    # Normalize scraper data
    for item in scraper_list:
        if isinstance(item, dict):
            # Extract 'value' key if it's a dict (e.g., {"type": "Generic", "value": "..."})
            value = item.get('value', '')
            if value and isinstance(value, str):
                merged_set.add(value.strip())
        elif isinstance(item, str):
            # If it's already a string, use it directly
            if item.strip():
                merged_set.add(item.strip())
    
    # Add LLM data
    for item in llm_list:
        if isinstance(item, str) and item.strip():
            merged_set.add(item.strip())
    
    # Return sorted list for consistency
    return sorted(list(merged_set))


# ============================================================================
# GROQ API FUNCTIONS
# ============================================================================

def initialize_groq_client() -> Groq:
    """Initialize Groq client with API key from environment."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set. "
            "Please export GROQ_API_KEY='your-api-key'"
        )
    
    return Groq(api_key=api_key)


def extract_with_groq(
    client: Groq,
    model: str,
    raw_text: str,
    domain: str
) -> Dict[str, Any]:
    """
    Extract structured data using Groq API.
    
    Returns:
        Dict with 'extraction' (ExtractionSchema dict), 'status', 'error', 'time_taken'
    """
    start_time = time.time()
    
    # Truncate text if needed
    text_to_process = truncate_text(raw_text)
    
    # Create user prompt
    user_prompt = f"Extract information from this corporate website text:\n\n{text_to_process}"
    
    try:
        # Make API call
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},  # Critical for JSON parsing
            temperature=0.1,  # Low temperature for consistent extraction
        )
        
        # Parse response
        content = response.choices[0].message.content
        extraction_dict = json.loads(content)
        
        # Capture token usage
        usage = response.usage
        token_usage = {
            'input': usage.prompt_tokens,
            'output': usage.completion_tokens,
            'total': usage.total_tokens
        }
        
        # Validate with ExtractionSchema
        try:
            schema = ExtractionSchema(**extraction_dict)
            extraction_result = schema.to_dict()
            status = 'success'
            error = None
        except Exception as validation_error:
            # If validation fails, use raw extraction but mark as warning
            extraction_result = extraction_dict
            status = 'partial'
            error = f"Schema validation warning: {str(validation_error)[:200]}"
        
        time_taken = time.time() - start_time
        
        return {
            'extraction': extraction_result,
            'status': status,
            'error': error,
            'time_taken': round(time_taken, 2),
            'usage': token_usage
        }
    
    except json.JSONDecodeError as e:
        time_taken = time.time() - start_time
        return {
            'extraction': {
                'products': [],
                'services': [],
                'customers': [],
                'partnerships': [],
                'case_studies': []
            },
            'status': 'error',
            'error': f"JSON decode error: {str(e)[:200]}",
            'time_taken': round(time_taken, 2),
            'usage': {'input': 0, 'output': 0, 'total': 0}
        }
    
    except Exception as e:
        time_taken = time.time() - start_time
        return {
            'extraction': {
                'products': [],
                'services': [],
                'customers': [],
                'partnerships': [],
                'case_studies': []
            },
            'status': 'error',
            'error': f"API error: {str(e)[:200]}",
            'time_taken': round(time_taken, 2),
            'usage': {'input': 0, 'output': 0, 'total': 0}
        }


# ============================================================================
# MAIN EXPERIMENT LOGIC
# ============================================================================

def run_experiment_for_model(
    client: Groq,
    model_name: str,
    records: List[Dict[str, Any]],
    output_file: Path
) -> Dict[str, Any]:
    """Run extraction experiment for a single model on all records."""
    
    print_header(f"Testing Model: {model_name}")
    
    # Limit to first N domains
    test_records = records[:MAX_DOMAINS_PER_MODEL]
    total = len(test_records)
    
    print(f"✓ Processing {total} domains (limited to {MAX_DOMAINS_PER_MODEL} per model)")
    print()
    
    results = []
    successful = 0
    failed = 0
    total_tokens = 0
    
    start_time = time.time()
    
    # Process each record
    for idx, record in enumerate(test_records, 1):
        domain = record.get('domain', 'unknown')
        raw_text = record.get('raw_text', '')
        final_url = record.get('final_url', '')
        
        # Get scraper-extracted contact data
        scraper_emails = record.get('emails', [])
        scraper_phones = record.get('phones', [])
        
        print_progress(idx, total, domain, "extracting...")
        
        # Extract with Groq
        result = extract_with_groq(client, model_name, raw_text, domain)
        
        # Get LLM extraction
        llm_extraction = result['extraction']
        
        # Smart merge: Combine scraper data + LLM data
        merged_extraction = llm_extraction.copy()
        merged_extraction['emails'] = smart_merge(
            scraper_emails,
            llm_extraction.get('emails', [])
        )
        merged_extraction['phones'] = smart_merge(
            scraper_phones,
            llm_extraction.get('phones', [])
        )
        
        # Prepare result record
        result_record = {
            'model': model_name,
            'domain': domain,
            'final_url': final_url,
            'extraction': merged_extraction,
            'status': result['status'],
            'error': result.get('error'),
            'time_taken': result['time_taken'],
            'usage': result.get('usage', {'input': 0, 'output': 0, 'total': 0}),
            'text_length': len(raw_text)
        }
        
        results.append(result_record)
        
        # Update stats and token tracking
        usage = result.get('usage', {'input': 0, 'output': 0, 'total': 0})
        total_tokens += usage['total']
        
        if result['status'] == 'success':
            successful += 1
            status_icon = "✓"
            status_msg = f"{status_icon} {result['status']} ({result['time_taken']:.1f}s)"
        else:
            failed += 1
            status_icon = "✗"
            error_msg = result.get('error', 'Unknown error')
            status_msg = f"{status_icon} {result['status']} ({result['time_taken']:.1f}s): {error_msg}"
        
        print_progress(
            idx, total, domain,
            status_msg
        )
        
        # Write result immediately (streaming output)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result_record, ensure_ascii=False) + '\n')
        
        # Rate limiting: sleep between requests (except for last one)
        if idx < total:
            time.sleep(RATE_LIMIT_DELAY)
    
    total_time = time.time() - start_time
    
    # Print summary
    print()
    print(f"{'─' * 70}")
    print(f"  Model: {model_name}")
    print(f"  Total: {total} | Successful: {successful} | Failed: {failed}")
    if total > 0:
        print(f"  Success Rate: {successful/total*100:.1f}%")
        print(f"  Total Time: {total_time:.1f}s | Avg: {total_time/total:.1f}s/domain")
        print(f"  Total Tokens: {total_tokens:,} | Avg: {total_tokens/total:,.0f} tokens/domain")
    print(f"{'─' * 70}")
    
    return {
        'model': model_name,
        'status': 'completed',
        'total': total,
        'successful': successful,
        'failed': failed,
        'success_rate': round(successful / total * 100, 1) if total > 0 else 0,
        'total_time_seconds': round(total_time, 1),
        'avg_time_per_domain': round(total_time / total, 1) if total > 0 else 0,
        'total_tokens': total_tokens,
        'avg_tokens_per_domain': round(total_tokens / total, 0) if total > 0 else 0,
        'extractions': results
    }


def main():
    """Main experiment orchestrator."""
    
    print_header("Phase B: Groq API Experimentation")
    print()
    print("🚀 Testing Groq API models for faster extraction")
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Models: {', '.join(MODELS_TO_TEST)}")
    print(f"Config: max_text_length={MAX_TEXT_LENGTH}, rate_limit={RATE_LIMIT_DELAY}s")
    print()
    
    # Check API key
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY environment variable not set")
        print("   Please export GROQ_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Initialize Groq client
    try:
        client = initialize_groq_client()
        print("✓ Groq client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Groq client: {e}")
        sys.exit(1)
    
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
            summary = run_experiment_for_model(
                client,
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
    print(f"{'─' * 90}")
    print(f"{'Model':<45} {'Success Rate':<15} {'Avg Time':<15} {'Avg Tokens':<15}")
    print(f"{'─' * 90}")
    
    for summary in model_summaries:
        if summary.get('status') == 'completed':
            model_name = summary['model']
            success_rate = f"{summary['success_rate']}%"
            avg_time = f"{summary['avg_time_per_domain']:.1f}s"
            avg_tokens = f"{summary['avg_tokens_per_domain']:,.0f}"
            print(f"{model_name:<45} {success_rate:<15} {avg_time:<15} {avg_tokens:<15}")
        else:
            model_name = summary.get('model', 'unknown')
            print(f"{model_name:<45} {'ERROR':<15} {'N/A':<15} {'N/A':<15}")
    
    print(f"{'─' * 90}")
    print()
    print("✅ Phase B Groq Experiment Complete!")
    print()
    print("Next Steps:")
    print("  1. Review results in: data/experiment_results_groq.jsonl")
    print("  2. Compare with local Ollama results")
    print("  3. Select best model for production")
    print()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

