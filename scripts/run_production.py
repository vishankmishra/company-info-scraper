#!/usr/bin/env python3
"""
Production Script: Enterprise Data Enrichment with Groq API

Purpose:
    Enrich scraped enterprise data with LLM-extracted structured information.
    Uses the best performing model (llama-3.3-70b-versatile) from experimentation.
    
Architecture:
    JSONL (raw_text) → Groq API → Structured JSON → JSON Array (enriched)
    
Features:
    - Resume capability: Skips already processed domains
    - Progress bar with tqdm
    - Incremental saves to prevent data loss
    - Smart merge of scraper + LLM extracted data
    
Input:
    data/enterprise_raw.jsonl
    
Output:
    data/enterprise_enriched.json (JSON array format)
    
Usage:
    python scripts/run_production.py
    
Requirements:
    pip install groq tqdm
    export GROQ_API_KEY="your-api-key"
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from groq import Groq
except ImportError:
    print("❌ Error: groq package not installed. Run: pip install groq")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("❌ Error: tqdm package not installed. Run: pip install tqdm")
    sys.exit(1)

from company_info_scraper.models.extraction_schema import ExtractionSchema


# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL_NAME = "llama-3.3-70b-versatile"  # Best performing model from experiments
RATE_LIMIT_DELAY = 3                    # Seconds between requests (avoid 429 errors)
MAX_TEXT_LENGTH = 25000                 # Truncate if absolutely huge

INPUT_FILE = project_root / 'data' / 'enterprise_raw.jsonl'
OUTPUT_FILE = project_root / 'data' / 'enterprise_enriched.json'

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


def load_existing_results(file_path: Path) -> tuple[List[Dict[str, Any]], Set[str]]:
    """
    Load existing enriched results from output file.
    
    Returns:
        Tuple of (results_list, set_of_processed_domains)
    """
    if not file_path.exists():
        return [], set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        # Extract domains that have been processed
        processed_domains = {record.get('domain') for record in results if record.get('domain')}
        
        print(f"✓ Loaded {len(results)} existing results ({len(processed_domains)} unique domains)")
        return results, processed_domains
    
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Warning: Could not parse existing output file: {e}")
        print("   Starting fresh...")
        return [], set()


def save_results(file_path: Path, results: List[Dict[str, Any]]):
    """Save results as a JSON array."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


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
                'case_studies': [],
                'leadership': [],
                'emails': [],
                'phones': []
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
                'case_studies': [],
                'leadership': [],
                'emails': [],
                'phones': []
            },
            'status': 'error',
            'error': f"API error: {str(e)[:200]}",
            'time_taken': round(time_taken, 2),
            'usage': {'input': 0, 'output': 0, 'total': 0}
        }


# ============================================================================
# MAIN PRODUCTION LOGIC
# ============================================================================

def run_production_enrichment(
    client: Groq,
    records: List[Dict[str, Any]],
    existing_results: List[Dict[str, Any]],
    processed_domains: Set[str]
) -> List[Dict[str, Any]]:
    """
    Run production enrichment on all records with resume capability.
    
    Args:
        client: Groq API client
        records: All raw records to process
        existing_results: Previously processed results
        processed_domains: Set of domains already processed
    
    Returns:
        Complete list of enriched results
    """
    # Filter to only unprocessed records
    records_to_process = [
        record for record in records
        if record.get('domain') not in processed_domains
    ]
    
    print(f"\n📊 Processing Status:")
    print(f"   Total records: {len(records)}")
    print(f"   Already processed: {len(processed_domains)}")
    print(f"   To process: {len(records_to_process)}")
    print()
    
    if len(records_to_process) == 0:
        print("✅ All records already processed!")
        return existing_results
    
    # Start with existing results
    all_results = existing_results.copy()
    
    successful = 0
    failed = 0
    total_tokens = 0
    
    # Process each record with progress bar
    for record in tqdm(records_to_process, desc="Enriching data", unit="domain"):
        domain = record.get('domain', 'unknown')
        raw_text = record.get('raw_text', '')
        final_url = record.get('final_url', '')
        
        # Get scraper-extracted contact data
        scraper_emails = record.get('emails', [])
        scraper_phones = record.get('phones', [])
        
        # Extract with Groq
        result = extract_with_groq(client, MODEL_NAME, raw_text, domain)
        
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
        
        # Prepare enriched record
        enriched_record = {
            'domain': domain,
            'final_url': final_url,
            'extraction': merged_extraction,
            'status': result['status'],
            'error': result.get('error'),
            'time_taken': result['time_taken'],
            'usage': result.get('usage', {'input': 0, 'output': 0, 'total': 0}),
            'text_length': len(raw_text),
            'model': MODEL_NAME
        }
        
        all_results.append(enriched_record)
        
        # Update stats
        usage = result.get('usage', {'input': 0, 'output': 0, 'total': 0})
        total_tokens += usage['total']
        
        if result['status'] == 'success':
            successful += 1
        else:
            failed += 1
        
        # Save incrementally every 5 records (prevents data loss)
        if len(all_results) % 5 == 0:
            save_results(OUTPUT_FILE, all_results)
        
        # Rate limiting: sleep between requests
        time.sleep(RATE_LIMIT_DELAY)
    
    # Final save
    save_results(OUTPUT_FILE, all_results)
    
    # Print summary
    print()
    print(f"{'=' * 70}")
    print(f"  PRODUCTION RUN COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Total processed: {len(records_to_process)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    if len(records_to_process) > 0:
        print(f"  Success Rate: {successful/len(records_to_process)*100:.1f}%")
        print(f"  Total Tokens: {total_tokens:,}")
        print(f"  Avg Tokens/Domain: {total_tokens/len(records_to_process):,.0f}")
    print(f"{'=' * 70}")
    
    return all_results


def main():
    """Main production orchestrator."""
    
    print()
    print("=" * 70)
    print("  PRODUCTION: Enterprise Data Enrichment")
    print("=" * 70)
    print()
    print(f"🚀 Model: {MODEL_NAME}")
    print(f"📥 Input:  {INPUT_FILE}")
    print(f"📤 Output: {OUTPUT_FILE}")
    print(f"⚙️  Config: max_text_length={MAX_TEXT_LENGTH}, rate_limit={RATE_LIMIT_DELAY}s")
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
    
    # Load existing results (for resume capability)
    existing_results, processed_domains = load_existing_results(OUTPUT_FILE)
    
    # Load and filter raw data
    print("Loading raw data...")
    all_records = load_raw_data(INPUT_FILE)
    print(f"✓ Loaded {len(all_records)} total records")
    
    valid_records = filter_valid_records(all_records)
    print(f"✓ Filtered to {len(valid_records)} valid records")
    
    if len(valid_records) == 0:
        print("❌ No valid records found. Exiting.")
        sys.exit(1)
    
    # Run production enrichment
    start_time = time.time()
    
    results = run_production_enrichment(
        client,
        valid_records,
        existing_results,
        processed_domains
    )
    
    total_time = time.time() - start_time
    
    # Final summary
    print()
    print("✅ Production enrichment complete!")
    print(f"   Total time: {total_time/60:.1f} minutes")
    print(f"   Results saved to: {OUTPUT_FILE}")
    print(f"   Total enriched records: {len(results)}")
    print()
    print("Next Steps:")
    print("  1. Review enriched data in: data/enterprise_enriched.json")
    print("  2. Analyze extraction quality")
    print("  3. Export to desired format or database")
    print()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Production run interrupted by user")
        print("   Progress has been saved. Run again to resume.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
