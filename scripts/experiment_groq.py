#!/usr/bin/env python3
"""
Groq API Model Experimentation

Tests multiple Groq models on scraped data to evaluate extraction performance.
Outputs structured results for model comparison and selection.

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
from typing import Any, Dict, List, Optional
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from groq import Groq
except ImportError:
    print("❌ Error: groq package not installed. Run: pip install groq")
    sys.exit(1)

from company_info_scraper.models.extraction_schema import ExtractionSchema


MODELS_TO_TEST = [
    'llama-3.3-70b-versatile',                    # Baseline Winner
    'openai/gpt-oss-120b',                        # New "GPT-OSS" Flagship
    'mistral-saba-24b',                           # Mistral's new efficient model
    'qwen/qwen3-32b',                             # Structured Data Specialist
    'meta-llama/llama-4-maverick-17b-128e-instruct', # Llama 4 Preview (Latest)
    'gemma2-9b-it'
]

MAX_DOMAINS_PER_MODEL = 5
RATE_LIMIT_DELAY = 3
MAX_TEXT_LENGTH = 25000

INPUT_FILE = project_root / 'data' / 'enterprise_raw.jsonl'
OUTPUT_FILE = project_root / 'data' / 'experiment_results_groq.jsonl'
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


def load_raw_data(file_path: Path) -> List[Dict[str, Any]]:
    """Load raw scraped data from JSONL."""
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
    """Filter records with valid, extractable content."""
    valid = []
    
    for record in records:
        if record.get('scrape_status') != 'success':
            continue
        
        raw_text = record.get('raw_text', '').strip()
        if not raw_text:
            continue
        
        if 'ERROR:' in raw_text[:100] or 'HTTP 403' in raw_text[:100]:
            continue
        
        valid.append(record)
    
    return valid


def truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Truncate text to max_length if necessary."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n[Text truncated for length...]"


def print_header(text: str):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_progress(current: int, total: int, domain: str, status: str = ""):
    """Display extraction progress."""
    progress = f"[{current}/{total}]"
    print(f"{progress:>10} {domain:40} {status}")


def smart_merge(scraper_list: List, llm_list: List) -> List[str]:
    """Merge and deduplicate scraper and LLM extraction results."""
    merged_set = set()
    
    for item in scraper_list:
        if isinstance(item, dict):
            value = item.get('value', '')
            if value and isinstance(value, str):
                merged_set.add(value.strip())
        elif isinstance(item, str):
            if item.strip():
                merged_set.add(item.strip())
    
    for item in llm_list:
        if isinstance(item, str) and item.strip():
            merged_set.add(item.strip())
    
    return sorted(list(merged_set))


def initialize_groq_client() -> Groq:
    """Initialize Groq client with API key."""
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
    """Extract structured data using Groq API."""
    start_time = time.time()
    text_to_process = truncate_text(raw_text)
    user_prompt = f"Extract information from this corporate website text:\n\n{text_to_process}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        extraction_dict = json.loads(content)
        usage = response.usage
        token_usage = {
            'input': usage.prompt_tokens,
            'output': usage.completion_tokens,
            'total': usage.total_tokens
        }
        
        try:
            schema = ExtractionSchema(**extraction_dict)
            extraction_result = schema.to_dict()
            status = 'success'
            error = None
        except Exception as validation_error:
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


def run_experiment_for_model(
    client: Groq,
    model_name: str,
    records: List[Dict[str, Any]],
    output_file: Path
) -> Dict[str, Any]:
    """Run extraction experiment for a single model."""
    
    print_header(f"Testing Model: {model_name}")
    
    test_records = records[:MAX_DOMAINS_PER_MODEL]
    total = len(test_records)
    
    print(f"✓ Processing {total} domains (limited to {MAX_DOMAINS_PER_MODEL} per model)")
    print()
    
    results = []
    successful = 0
    failed = 0
    total_tokens = 0
    
    start_time = time.time()
    
    for idx, record in enumerate(test_records, 1):
        domain = record.get('domain', 'unknown')
        raw_text = record.get('raw_text', '')
        final_url = record.get('final_url', '')
        
        scraper_emails = record.get('emails', [])
        scraper_phones = record.get('phones', [])
        
        print_progress(idx, total, domain, "extracting...")
        
        result = extract_with_groq(client, model_name, raw_text, domain)
        llm_extraction = result['extraction']
        
        merged_extraction = llm_extraction.copy()
        merged_extraction['emails'] = smart_merge(
            scraper_emails,
            llm_extraction.get('emails', [])
        )
        merged_extraction['phones'] = smart_merge(
            scraper_phones,
            llm_extraction.get('phones', [])
        )
        
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
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(result_record, ensure_ascii=False) + '\n')
        
        if idx < total:
            time.sleep(RATE_LIMIT_DELAY)
    
    total_time = time.time() - start_time
    
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
    """Execute model experimentation pipeline."""
    
    print_header("Phase B: Groq API Experimentation")
    print()
    print("🚀 Testing Groq API models for faster extraction")
    print(f"Input:  {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Models: {', '.join(MODELS_TO_TEST)}")
    print(f"Config: max_text_length={MAX_TEXT_LENGTH}, rate_limit={RATE_LIMIT_DELAY}s")
    print()
    
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY environment variable not set")
        print("   Please export GROQ_API_KEY='your-api-key'")
        sys.exit(1)
    
    try:
        client = initialize_groq_client()
        print("✓ Groq client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Groq client: {e}")
        sys.exit(1)
    
    print("Loading raw data...")
    all_records = load_raw_data(INPUT_FILE)
    print(f"✓ Loaded {len(all_records)} total records")
    
    valid_records = filter_valid_records(all_records)
    print(f"✓ Filtered to {len(valid_records)} valid records")
    
    if len(valid_records) == 0:
        print("❌ No valid records found. Exiting.")
        sys.exit(1)
    
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
        print(f"✓ Cleared existing output file")
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
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

