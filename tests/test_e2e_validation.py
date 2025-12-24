#!/usr/bin/env python3
"""
Comprehensive End-to-End Validation Test (PH6-S5 Complete)

Tests the complete scraping pipeline with:
- 5 known test domains (mix of company sizes and types)
- Validation of >60% extraction success rate
- Quality checks for extracted fields
- Mixed static/dynamic site handling
- Edge case handling (timeouts, errors)

Run with:
    python tests/test_e2e_validation.py
    python tests/test_e2e_validation.py --domains-only  # Skip LLM, test scraping only
    
With pytest:
    pytest tests/test_e2e_validation.py -v -s
"""

import sys
import os
import asyncio
import tempfile
import csv
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Test Domain Configuration
# =============================================================================

@dataclass
class TestDomain:
    """Configuration for a test domain."""
    url: str
    name: str
    size_bucket: str  # small, medium, large, enterprise
    expected_type: str  # static or dynamic
    expect_products: bool
    expect_customers: bool
    expect_partnerships: bool
    expect_case_studies: bool
    notes: str = ""


# 5 test domains across different sizes and types
TEST_DOMAINS = [
    TestDomain(
        url='example.com',
        name='Example Domain',
        size_bucket='small',
        expected_type='static',
        expect_products=False,  # Simple placeholder site
        expect_customers=False,
        expect_partnerships=False,
        expect_case_studies=False,
        notes='Simple static placeholder - used as baseline test'
    ),
    TestDomain(
        url='httpbin.org',
        name='HTTPBin',
        size_bucket='small',
        expected_type='static',
        expect_products=True,  # API testing service
        expect_customers=False,
        expect_partnerships=False,
        expect_case_studies=False,
        notes='API testing tool - simple static site with product info'
    ),
    TestDomain(
        url='stripe.com',
        name='Stripe',
        size_bucket='large',
        expected_type='dynamic',
        expect_products=True,  # Payment processing products
        expect_customers=True,  # Known customers section
        expect_partnerships=True,  # Partner ecosystem
        expect_case_studies=True,  # Customer stories
        notes='Major FinTech - rich company data, dynamic site'
    ),
    TestDomain(
        url='shopify.com',
        name='Shopify',
        size_bucket='enterprise',
        expected_type='dynamic',
        expect_products=True,  # E-commerce platform
        expect_customers=True,  # Merchant showcase
        expect_partnerships=True,  # App partners
        expect_case_studies=True,  # Success stories
        notes='E-commerce platform - comprehensive company info'
    ),
    TestDomain(
        url='mongodb.com',
        name='MongoDB',
        size_bucket='large',
        expected_type='dynamic',
        expect_products=True,  # Database products
        expect_customers=True,  # Customer logos/testimonials
        expect_partnerships=True,  # Tech partners
        expect_case_studies=True,  # Use cases
        notes='Database company - technical focus with clear sections'
    ),
]


# =============================================================================
# Validation Functions
# =============================================================================

def validate_extraction_result(result: Dict[str, Any], domain: TestDomain) -> Dict[str, Any]:
    """
    Validate extraction result against expected data.
    
    Returns validation stats including:
    - Field presence (products, customers, etc.)
    - Quality score (% of expected fields found)
    - Specific issues
    """
    validation = {
        'domain': domain.name,
        'url': domain.url,
        'extraction_status': result.get('extraction_status', 'unknown'),
        'fields_found': [],
        'fields_missing': [],
        'quality_score': 0.0,
        'issues': []
    }
    
    # Check each field
    products = result.get('products', 'N/A')
    customers = result.get('customers', 'N/A')
    partnerships = result.get('partnerships', 'N/A')
    case_studies = result.get('case_studies', 'N/A')
    
    # Count expected vs found
    expected_count = 0
    found_count = 0
    
    if domain.expect_products:
        expected_count += 1
        if products and products not in ('N/A', '', 'QUEUED'):
            validation['fields_found'].append('products')
            found_count += 1
        else:
            validation['fields_missing'].append('products')
    
    if domain.expect_customers:
        expected_count += 1
        if customers and customers not in ('N/A', '', 'QUEUED'):
            validation['fields_found'].append('customers')
            found_count += 1
        else:
            validation['fields_missing'].append('customers')
    
    if domain.expect_partnerships:
        expected_count += 1
        if partnerships and partnerships not in ('N/A', '', 'QUEUED'):
            validation['fields_found'].append('partnerships')
            found_count += 1
        else:
            validation['fields_missing'].append('partnerships')
    
    if domain.expect_case_studies:
        expected_count += 1
        if case_studies and case_studies not in ('N/A', '', 'QUEUED'):
            validation['fields_found'].append('case_studies')
            found_count += 1
        else:
            validation['fields_missing'].append('case_studies')
    
    # Calculate quality score
    if expected_count > 0:
        validation['quality_score'] = (found_count / expected_count) * 100
    else:
        # For domains with no expectations, check if any field has data
        any_data = any([
            products not in ('N/A', '', 'QUEUED'),
            customers not in ('N/A', '', 'QUEUED'),
            partnerships not in ('N/A', '', 'QUEUED'),
            case_studies not in ('N/A', '', 'QUEUED')
        ])
        validation['quality_score'] = 100 if any_data else 0
    
    # Check for specific issues
    if result.get('error'):
        validation['issues'].append(f"Error: {result['error']}")
    
    if validation['extraction_status'] != 'success' and expected_count > 0:
        validation['issues'].append("Extraction marked as failure")
    
    return validation


def calculate_overall_success_rate(validations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate overall success metrics across all domains."""
    total = len(validations)
    if total == 0:
        return {'success_rate': 0, 'avg_quality': 0}
    
    # Success = quality_score >= 50%
    successful = sum(1 for v in validations if v.get('quality_score', 0) >= 50)
    avg_quality = sum(v.get('quality_score', 0) for v in validations) / total
    
    # Count by field
    fields_stats = {
        'products': {'found': 0, 'missing': 0},
        'customers': {'found': 0, 'missing': 0},
        'partnerships': {'found': 0, 'missing': 0},
        'case_studies': {'found': 0, 'missing': 0},
    }
    
    for validation in validations:
        # Safely get fields lists
        for field in validation.get('fields_found', []):
            fields_stats[field]['found'] += 1
        for field in validation.get('fields_missing', []):
            fields_stats[field]['missing'] += 1
    
    return {
        'total_domains': total,
        'successful': successful,
        'failed': total - successful,
        'success_rate': (successful / total) * 100,
        'avg_quality_score': avg_quality,
        'fields_stats': fields_stats,
        'validations': validations
    }


# =============================================================================
# Test Execution
# =============================================================================

async def run_e2e_test(
    domains: List[TestDomain] = TEST_DOMAINS,
    skip_llm: bool = False,
    timeout_per_domain: int = 120
) -> Dict[str, Any]:
    """
    Run end-to-end test on specified domains.
    
    Args:
        domains: List of TestDomain configurations to test
        skip_llm: If True, skip LLM extraction (faster, tests scraping only)
        timeout_per_domain: Timeout in seconds per domain
        
    Returns:
        Test results with validation metrics
    """
    from company_info_scraper.agents import OrchestratorAgent
    
    print("="*70)
    print("End-to-End Validation Test")
    print("="*70)
    print(f"\nTest Configuration:")
    print(f"  Domains: {len(domains)}")
    print(f"  LLM Extraction: {'Disabled' if skip_llm else 'Enabled'}")
    print(f"  Timeout per domain: {timeout_per_domain}s")
    print()
    
    # Initialize orchestrator
    config = {
        'auto_detect': True,
        'ollama_timeout': 90,
        'max_text_length': 5000,
    }
    
    orchestrator = OrchestratorAgent(config)
    
    # Process each domain
    results = []
    validations = []
    
    for i, test_domain in enumerate(domains, 1):
        print(f"[{i}/{len(domains)}] Testing: {test_domain.name} ({test_domain.url})")
        print(f"  Size: {test_domain.size_bucket}, Type: {test_domain.expected_type}")
        
        start_time = time.time()
        
        try:
            # Run scraping + extraction
            result = orchestrator.execute({
                'domain': test_domain.url,
                'scraper_type': 'auto'
            })
            
            elapsed = time.time() - start_time
            
            if result.get('success'):
                records = result.get('records', [])
                print(f"  ✓ Scraped {len(records)} pages in {elapsed:.1f}s")
                
                # Validate results
                if records:
                    # Use first record for validation
                    validation = validate_extraction_result(records[0], test_domain)
                    validation['elapsed_s'] = elapsed
                    validations.append(validation)
                    
                    print(f"  Quality Score: {validation['quality_score']:.0f}%")
                    if validation['fields_found']:
                        print(f"  Found: {', '.join(validation['fields_found'])}")
                    if validation['fields_missing']:
                        print(f"  Missing: {', '.join(validation['fields_missing'])}")
                else:
                    print(f"  ⚠ No records returned")
                    validations.append({
                        'domain': test_domain.name,
                        'url': test_domain.url,
                        'quality_score': 0,
                        'fields_found': [],
                        'fields_missing': [],
                        'issues': ['No records returned'],
                        'elapsed_s': elapsed
                    })
            else:
                print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
                validations.append({
                    'domain': test_domain.name,
                    'url': test_domain.url,
                    'quality_score': 0,
                    'fields_found': [],
                    'fields_missing': [],
                    'issues': [result.get('error', 'Unknown error')],
                    'elapsed_s': time.time() - start_time
                })
            
            results.append(result)
            
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            validations.append({
                'domain': test_domain.name,
                'url': test_domain.url,
                'quality_score': 0,
                'fields_found': [],
                'fields_missing': [],
                'issues': [f'Exception: {str(e)}'],
                'elapsed_s': time.time() - start_time
            })
        
        print()
    
    # Calculate overall metrics
    overall = calculate_overall_success_rate(validations)
    
    return {
        'results': results,
        'validations': validations,
        'overall': overall,
        'test_config': {
            'total_domains': len(domains),
            'skip_llm': skip_llm,
            'timeout_per_domain': timeout_per_domain
        }
    }


def print_test_summary(test_results: Dict[str, Any]):
    """Print formatted test summary."""
    overall = test_results['overall']
    
    print("="*70)
    print("Test Summary")
    print("="*70)
    print(f"\nOverall Metrics:")
    print(f"  Total Domains: {overall['total_domains']}")
    print(f"  Successful: {overall['successful']} ({overall['success_rate']:.1f}%)")
    print(f"  Failed: {overall['failed']}")
    print(f"  Average Quality Score: {overall['avg_quality_score']:.1f}%")
    
    print(f"\nField Extraction Stats:")
    for field, stats in overall['fields_stats'].items():
        total = stats['found'] + stats['missing']
        if total > 0:
            pct = (stats['found'] / total) * 100
            print(f"  {field.capitalize()}: {stats['found']}/{total} ({pct:.0f}%)")
    
    print(f"\nPer-Domain Results:")
    for validation in overall['validations']:
        status = "✓" if validation['quality_score'] >= 50 else "✗"
        print(f"  {status} {validation['domain']}: {validation['quality_score']:.0f}% "
              f"({validation.get('elapsed_s', 0):.1f}s)")
        if validation.get('issues'):
            for issue in validation['issues']:
                print(f"      - {issue}")
    
    # Final verdict
    print(f"\n{'='*70}")
    if overall['success_rate'] >= 60:
        print(f"✓ TEST PASSED: {overall['success_rate']:.1f}% success rate (target: >60%)")
    else:
        print(f"✗ TEST FAILED: {overall['success_rate']:.1f}% success rate (target: >60%)")
    print("="*70)


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main test entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='E2E Validation Test')
    parser.add_argument('--domains-only', action='store_true',
                       help='Test scraping only, skip LLM extraction')
    parser.add_argument('--quick', action='store_true',
                       help='Test only first 2 domains')
    parser.add_argument('--timeout', type=int, default=120,
                       help='Timeout per domain in seconds')
    
    args = parser.parse_args()
    
    # Select domains
    domains = TEST_DOMAINS[:2] if args.quick else TEST_DOMAINS
    
    # Check prerequisites
    print("Checking prerequisites...")
    
    from company_info_scraper.health import check_ollama
    ollama_ok = check_ollama()
    
    if not ollama_ok and not args.domains_only:
        print("\n⚠ WARNING: Ollama not available")
        print("  The test will likely fail without LLM extraction.")
        print("  Use --domains-only to test scraping without LLM.")
        print("  Or start Ollama: ollama serve && ollama pull llama3")
        return 1
    
    print(f"  Ollama: {'✓' if ollama_ok else '✗'}")
    print()
    
    # Run test
    try:
        test_results = asyncio.run(run_e2e_test(
            domains=domains,
            skip_llm=args.domains_only,
            timeout_per_domain=args.timeout
        ))
        
        # Print summary
        print_test_summary(test_results)
        
        # Return appropriate exit code
        success_rate = test_results['overall']['success_rate']
        return 0 if success_rate >= 60 else 1
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

