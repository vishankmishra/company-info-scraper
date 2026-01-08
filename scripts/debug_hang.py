#!/usr/bin/env python3
"""
Diagnostic Script: Debug LLM Hang Issue

Purpose:
    Make the failure VISIBLE by streaming LLM output token-by-token.
    This will show us exactly WHERE it hangs:
    - Before generation starts (no output at all)
    - During generation (slow token generation)
    - Repeating text infinitely (stuck in loop)
    
Usage:
    python scripts/debug_hang.py
"""

import json
import time
from pathlib import Path

import ollama


# ============================================================================
# CONFIGURATION (Match experiment_llm.py exactly)
# ============================================================================

MODEL = 'qwen2.5:7b-instruct'
NUM_CTX = 4096
TEMPERATURE = 0.1
MAX_TEXT_LENGTH = 7000

INPUT_FILE = Path(__file__).parent.parent / 'data' / 'phase_a_raw.jsonl'
TARGET_DOMAIN = 'magiqai.io'  # The first domain that consistently fails


# ============================================================================
# LOAD TEST DATA
# ============================================================================

def load_domain_text(domain: str) -> str:
    """Load raw_text for specific domain from JSONL."""
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get('domain') == domain:
                return record.get('raw_text', '')
    raise ValueError(f"Domain {domain} not found in {INPUT_FILE}")


# ============================================================================
# BUILD EXTRACTION PROMPT
# ============================================================================

def build_prompt(text: str) -> str:
    """Build the extraction prompt (simplified version from llm_service.py)."""
    return f"""You are a corporate information extraction specialist. Extract the following fields from the website text.

CRITICAL INSTRUCTIONS:
- Return ONLY a valid JSON object, no explanations
- Use empty array [] if information is not found — do NOT use "N/A" for arrays
- Do NOT guess or hallucinate — only extract information that clearly exists in the text

EXTRACTION FIELDS:

1. products (array of strings)
   - Product names, software names, service offerings
   - Include specific product lines, not generic descriptions
   - Example: ["Zoho CRM", "Zoho Books", "Zoho Mail"]

2. services (array of strings)
   - Consulting, support, professional services
   - Different from products — services are things done FOR customers
   - Example: ["Implementation Services", "Technical Support", "Training"]

3. customers (array of strings)
   - ONLY extract explicitly named customer/client companies
   - Look for: "trusted by", "our customers include", "client list", logos with company names
   - Do NOT include: generic terms like "enterprises" or "Fortune 500"
   - Do NOT include: partner names (they go in partnerships)
   - Example: ["Acme Corp", "TechCorp Inc", "Global Industries"]

4. partnerships (array of strings)
   - Integration partners, technology partners, strategic alliances
   - Look for: "partners include", "integrations with", "certified partner"
   - Do NOT include: customer names
   - Example: ["Salesforce", "Microsoft", "Google Cloud"]

5. case_studies (array of strings)
   - Named customer success stories with specific outcomes
   - Format: "Company Name: brief description of what was achieved"
   - Look for: "case study", "success story", "how X achieved Y"
   - Do NOT include: generic testimonials without company names
   - Example: ["Acme Corp: 50% efficiency improvement", "TechCorp: Reduced costs by 30%"]

WEBSITE TEXT:
{text[:MAX_TEXT_LENGTH]}

Return JSON:
{{
    "products": [],
    "services": [],
    "customers": [],
    "partnerships": [],
    "case_studies": []
}}"""


# ============================================================================
# STREAMING DIAGNOSTIC
# ============================================================================

def run_streaming_extraction(text: str):
    """Run extraction with streaming enabled to see token-by-token output."""
    
    print("=" * 70)
    print("DIAGNOSTIC: LLM Streaming Test")
    print("=" * 70)
    print()
    print(f"Model: {MODEL}")
    print(f"Config: num_ctx={NUM_CTX}, temperature={TEMPERATURE}")
    print(f"Text Length: {len(text)} characters (truncated to {MAX_TEXT_LENGTH})")
    print()
    print("=" * 70)
    print("WAITING FOR FIRST TOKEN...")
    print("=" * 70)
    print()
    
    # Build prompt
    prompt = build_prompt(text)
    
    # Initialize client
    client = ollama.Client()
    
    # Timing measurements
    start_time = time.time()
    first_token_time = None
    token_count = 0
    
    try:
        # Call with streaming enabled
        stream = client.chat(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
            options={
                'num_ctx': NUM_CTX,
                'temperature': TEMPERATURE,
            }
        )
        
        print("🟢 STREAM STARTED - Printing tokens as they arrive:")
        print("-" * 70)
        
        # Process stream
        for chunk in stream:
            # Record first token time
            if first_token_time is None:
                first_token_time = time.time()
                elapsed = first_token_time - start_time
                print(f"\n⏱️  FIRST TOKEN RECEIVED after {elapsed:.1f}s\n")
                print("-" * 70)
            
            # Print token immediately
            content = chunk['message']['content']
            print(content, end='', flush=True)
            token_count += 1
        
        # Final timing
        end_time = time.time()
        total_time = end_time - start_time
        generation_time = end_time - first_token_time if first_token_time else 0
        
        print("\n")
        print("-" * 70)
        print("✅ GENERATION COMPLETE")
        print("-" * 70)
        print(f"Time to First Token: {first_token_time - start_time:.1f}s" if first_token_time else "N/A")
        print(f"Generation Time: {generation_time:.1f}s")
        print(f"Total Time: {total_time:.1f}s")
        print(f"Approximate Tokens: {token_count}")
        print(f"Tokens/Second: {token_count/generation_time:.1f}" if generation_time > 0 else "N/A")
        print()
        
    except TimeoutError as e:
        print("\n")
        print("❌ TIMEOUT ERROR")
        print(f"Error: {e}")
        if first_token_time:
            print(f"Tokens received before timeout: {token_count}")
            print(f"Time to first token: {first_token_time - start_time:.1f}s")
        else:
            print("No tokens received - hang occurred BEFORE generation started")
    except Exception as e:
        print("\n")
        print("❌ ERROR")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print()
    print("=" * 70)
    print("PHASE B: LLM HANG DIAGNOSTIC")
    print("=" * 70)
    print()
    print(f"Loading domain: {TARGET_DOMAIN}")
    
    try:
        # Load failing domain text
        raw_text = load_domain_text(TARGET_DOMAIN)
        
        if not raw_text or not raw_text.strip():
            print(f"❌ Error: No text found for domain {TARGET_DOMAIN}")
            return
        
        print(f"✓ Loaded {len(raw_text)} characters")
        print()
        
        # Show sample of text
        print("Sample of raw text:")
        print("-" * 70)
        print(raw_text[:500])
        print("...")
        print("-" * 70)
        print()
        
        input("Press Enter to start streaming extraction (or Ctrl+C to cancel)...")
        print()
        
        # Run diagnostic
        run_streaming_extraction(raw_text)
        
        print()
        print("=" * 70)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 70)
        print()
        print("INTERPRETATION:")
        print("  - If you saw tokens streaming: Model is working, just slow")
        print("  - If no tokens appeared: Hang before generation (config issue)")
        print("  - If tokens repeat forever: Stuck in generation loop")
        print()
        
    except ValueError as e:
        print(f"❌ Error: {e}")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

