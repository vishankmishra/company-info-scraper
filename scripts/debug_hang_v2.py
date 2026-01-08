#!/usr/bin/env python3
"""
Diagnostic Script V2: Progressive Context Testing

Purpose:
    Test multiple configurations to find the breaking point:
    1. Minimal prompt + small context (should always work)
    2. Full prompt + small context (tests prompt complexity)
    3. Full prompt + medium context (tests scaling)
    4. Full prompt + large context (original failing scenario)
    
Usage:
    python scripts/debug_hang_v2.py
"""

import json
import time
from pathlib import Path

import ollama


# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL = 'qwen2.5:7b-instruct'
INPUT_FILE = Path(__file__).parent.parent / 'data' / 'phase_a_raw.jsonl'
TARGET_DOMAIN = 'magiqai.io'

# Test scenarios (progressive complexity)
TEST_SCENARIOS = [
    {
        'name': 'Test 1: Minimal (Baseline)',
        'num_ctx': 2048,
        'text_length': 1000,
        'temperature': 0.1,
        'use_simple_prompt': True,
        'timeout': 120,  # 2 minutes
    },
    {
        'name': 'Test 2: Small Context',
        'num_ctx': 2048,
        'text_length': 2000,
        'temperature': 0.1,
        'use_simple_prompt': False,
        'timeout': 180,  # 3 minutes
    },
    {
        'name': 'Test 3: Medium Context',
        'num_ctx': 4096,
        'text_length': 3500,
        'temperature': 0.1,
        'use_simple_prompt': False,
        'timeout': 240,  # 4 minutes
    },
    {
        'name': 'Test 4: Large Context (Original)',
        'num_ctx': 4096,
        'text_length': 7000,
        'temperature': 0.1,
        'use_simple_prompt': False,
        'timeout': 300,  # 5 minutes
    },
    {
        'name': 'Test 5: Extra Large Context',
        'num_ctx': 8192,
        'text_length': 7000,
        'temperature': 0.1,
        'use_simple_prompt': False,
        'timeout': 300,  # 5 minutes
    },
]


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
# BUILD PROMPTS
# ============================================================================

def build_simple_prompt(text: str) -> str:
    """Minimal prompt for baseline test."""
    return f"""Extract company information from this text and return as JSON with these fields: products, services, customers, partnerships, case_studies. Use empty arrays if not found.

Text: {text}

Return only JSON:"""


def build_full_prompt(text: str) -> str:
    """Full extraction prompt (from llm_service.py)."""
    return f"""You are a corporate information extraction specialist. Extract the following fields from the website text.

CRITICAL INSTRUCTIONS:
- Return ONLY a valid JSON object, no explanations
- Use empty array [] if information is not found
- Do NOT guess or hallucinate

EXTRACTION FIELDS:

1. products (array of strings) - Product names, software names
2. services (array of strings) - Consulting, support services
3. customers (array of strings) - ONLY explicitly named customer companies
4. partnerships (array of strings) - Integration partners, strategic alliances
5. case_studies (array of strings) - Named success stories with outcomes

WEBSITE TEXT:
{text}

Return JSON:
{{
    "products": [],
    "services": [],
    "customers": [],
    "partnerships": [],
    "case_studies": []
}}"""


# ============================================================================
# STREAMING TEST
# ============================================================================

def run_test(scenario: dict, text: str) -> dict:
    """Run a single test scenario."""
    
    print("=" * 70)
    print(f"  {scenario['name']}")
    print("=" * 70)
    print(f"  num_ctx: {scenario['num_ctx']}")
    print(f"  text_length: {scenario['text_length']}")
    print(f"  temperature: {scenario['temperature']}")
    print(f"  timeout: {scenario['timeout']}s")
    print("=" * 70)
    
    # Truncate text
    truncated_text = text[:scenario['text_length']]
    
    # Build prompt
    if scenario['use_simple_prompt']:
        prompt = build_simple_prompt(truncated_text)
        print("  Using: SIMPLE prompt")
    else:
        prompt = build_full_prompt(truncated_text)
        print("  Using: FULL prompt")
    
    print(f"  Prompt length: {len(prompt)} characters")
    print()
    print("  🟡 Starting generation...")
    
    # Initialize client
    client = ollama.Client(timeout=scenario['timeout'])
    
    # Timing
    start_time = time.time()
    first_token_time = None
    token_count = 0
    success = False
    error_msg = None
    generated_text = ""
    
    try:
        # Call with streaming
        stream = client.chat(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
            options={
                'num_ctx': scenario['num_ctx'],
                'temperature': scenario['temperature'],
            }
        )
        
        # Process stream
        for chunk in stream:
            # Record first token
            if first_token_time is None:
                first_token_time = time.time()
                elapsed = first_token_time - start_time
                print(f"  ✓ First token after {elapsed:.1f}s")
            
            # Collect content
            content = chunk['message']['content']
            generated_text += content
            token_count += 1
        
        # Completed successfully
        end_time = time.time()
        total_time = end_time - start_time
        generation_time = end_time - first_token_time if first_token_time else 0
        success = True
        
        print(f"  ✅ SUCCESS")
        print(f"     Time to first token: {first_token_time - start_time:.1f}s" if first_token_time else "N/A")
        print(f"     Generation time: {generation_time:.1f}s")
        print(f"     Total time: {total_time:.1f}s")
        print(f"     Tokens: {token_count}")
        print(f"     Speed: {token_count/generation_time:.1f} tokens/s" if generation_time > 0 else "N/A")
        print()
        
        return {
            'success': True,
            'time_to_first_token': first_token_time - start_time if first_token_time else None,
            'generation_time': generation_time,
            'total_time': total_time,
            'token_count': token_count,
            'tokens_per_second': token_count/generation_time if generation_time > 0 else None,
            'generated_length': len(generated_text),
        }
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        elapsed = time.time() - start_time
        
        print(f"  ❌ FAILED: {error_type}")
        print(f"     Error: {error_msg[:100]}")
        print(f"     Time before failure: {elapsed:.1f}s")
        if first_token_time:
            print(f"     Tokens before failure: {token_count}")
        else:
            print(f"     No tokens generated (hung before start)")
        print()
        
        return {
            'success': False,
            'error_type': error_type,
            'error_message': error_msg[:200],
            'time_before_failure': elapsed,
            'first_token_received': first_token_time is not None,
            'tokens_before_failure': token_count,
        }


# ============================================================================
# MAIN
# ============================================================================

def main():
    print()
    print("=" * 70)
    print("PHASE B: PROGRESSIVE CONTEXT DIAGNOSTIC")
    print("=" * 70)
    print()
    print(f"Model: {MODEL}")
    print(f"Target domain: {TARGET_DOMAIN}")
    print(f"Test scenarios: {len(TEST_SCENARIOS)}")
    print()
    
    try:
        # Load domain text
        print("Loading domain text...")
        raw_text = load_domain_text(TARGET_DOMAIN)
        
        if not raw_text or not raw_text.strip():
            print(f"❌ Error: No text found for domain {TARGET_DOMAIN}")
            return
        
        print(f"✓ Loaded {len(raw_text)} characters")
        print()
        
        # Run all tests
        results = []
        
        for i, scenario in enumerate(TEST_SCENARIOS, 1):
            print(f"\n{'█' * 70}")
            print(f"  SCENARIO {i}/{len(TEST_SCENARIOS)}")
            print(f"{'█' * 70}\n")
            
            result = run_test(scenario, raw_text)
            results.append({
                'scenario': scenario['name'],
                **result
            })
            
            # Stop if we find a failure point
            if not result['success']:
                print("⚠️  FAILURE DETECTED - Testing remaining scenarios to confirm pattern")
                print()
            
            # Small delay between tests
            time.sleep(2)
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY: Test Results")
        print("=" * 70)
        print()
        
        for i, result in enumerate(results, 1):
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            scenario_name = result['scenario']
            print(f"{i}. {scenario_name:<40} {status}")
            
            if result['success']:
                ttft = result.get('time_to_first_token', 'N/A')
                total = result.get('total_time', 'N/A')
                if ttft != 'N/A':
                    print(f"   Time to first token: {ttft:.1f}s | Total: {total:.1f}s")
            else:
                error = result.get('error_type', 'Unknown')
                first_token = result.get('first_token_received', False)
                hung_point = "during generation" if first_token else "before start"
                print(f"   Error: {error} | Hung: {hung_point}")
            print()
        
        # Analysis
        print("=" * 70)
        print("ANALYSIS")
        print("=" * 70)
        print()
        
        pass_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - pass_count
        
        if pass_count == 0:
            print("❌ ALL TESTS FAILED")
            print("   Likely cause: Model configuration or Ollama service issue")
        elif fail_count == 0:
            print("✅ ALL TESTS PASSED")
            print("   Issue is likely in experiment_llm.py service layer")
        else:
            # Find breaking point
            first_fail = next((i for i, r in enumerate(results) if not r['success']), None)
            if first_fail is not None:
                if first_fail == 0:
                    print("❌ FAILED ON MINIMAL TEST")
                    print("   Likely cause: Model or Ollama configuration issue")
                else:
                    print(f"⚠️  BREAKING POINT: Test {first_fail + 1}")
                    breaking_scenario = TEST_SCENARIOS[first_fail]
                    print(f"   Context size: {breaking_scenario['num_ctx']}")
                    print(f"   Text length: {breaking_scenario['text_length']}")
                    print()
                    print("   RECOMMENDATION:")
                    if breaking_scenario['text_length'] > 5000:
                        print("   → Reduce MAX_TEXT_LENGTH to 3500 or less")
                    if breaking_scenario['num_ctx'] < 8192:
                        print("   → Increase num_ctx to 8192 (if model supports)")
        
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

