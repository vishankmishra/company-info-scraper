#!/usr/bin/env python3
"""
Simple E2E Integration Test (PH6-S5)

Tests the complete scraping pipeline without Twisted reactor conflicts.
This version runs the scraper via the main.py CLI interface.

Run with:
    python tests/test_e2e_simple.py
    python tests/test_e2e_simple.py --quick  # Test 2 domains only
"""

import sys
import os
import subprocess
import tempfile
import csv
from pathlib import Path
from typing import Dict, Any, List
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Test domains
TEST_DOMAINS = [
    {'url': 'example.com', 'name': 'Example Domain', 'expect_success': True},
    {'url': 'httpbin.org', 'name': 'HTTPBin', 'expect_success': True},
    {'url': 'stripe.com', 'name': 'Stripe', 'expect_success': True},
    {'url': 'shopify.com', 'name': 'Shopify', 'expect_success': True},
    {'url': 'mongodb.com', 'name': 'MongoDB', 'expect_success': True},
]


def validate_csv_output(csv_path: str) -> Dict[str, Any]:
    """Validate CSV output and return quality metrics."""
    if not os.path.exists(csv_path):
        return {'error': 'File not found', 'records': 0}
    
    stats = {
        'total_records': 0,
        'extraction_success': 0,
        'has_data': 0,  # At least 1 non-N/A field
        'rich_data': 0,  # At least 2 non-N/A fields
    }
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats['total_records'] += 1
                
                if row.get('extraction_status') == 'success':
                    stats['extraction_success'] += 1
                
                # Count non-N/A fields
                non_na_count = 0
                for field in ['products', 'services', 'customers', 'partnerships', 'case_studies']:
                    if row.get(field) and row[field] not in ('N/A', '', 'QUEUED'):
                        non_na_count += 1
                
                if non_na_count >= 1:
                    stats['has_data'] += 1
                if non_na_count >= 2:
                    stats['rich_data'] += 1
        
        # Calculate percentages
        if stats['total_records'] > 0:
            stats['success_rate'] = (stats['extraction_success'] / stats['total_records']) * 100
            stats['data_quality'] = (stats['rich_data'] / stats['total_records']) * 100
        else:
            stats['success_rate'] = 0
            stats['data_quality'] = 0
        
        return stats
    
    except Exception as e:
        return {'error': str(e), 'records': 0}


def run_scraper_test(domains: List[Dict[str, Any]], timeout: int = 120) -> Dict[str, Any]:
    """Run the scraper on test domains and validate results."""
    
    print("="*70)
    print("End-to-End Integration Test")
    print("="*70)
    print(f"\nTest Configuration:")
    print(f"  Domains: {len(domains)}")
    print(f"  Timeout per domain: {timeout}s")
    print()
    
    # Check if Ollama is available
    from company_info_scraper.health import check_ollama
    ollama_ok = check_ollama()
    print(f"Prerequisites:")
    print(f"  Ollama: {'✓ Available' if ollama_ok else '✗ Not available'}")
    
    if not ollama_ok:
        print("\n⚠ WARNING: Ollama not available. Test may fail.")
        print("  Start Ollama: ollama serve && ollama pull llama3")
        return {'success': False, 'error': 'Ollama not available'}
    
    print()
    
    # Create temp directory for batch file and output
    with tempfile.TemporaryDirectory() as tmpdir:
        batch_file = Path(tmpdir) / 'test_domains.txt'
        output_file = Path(tmpdir) / 'test_output.csv'
        
        # Write domains to batch file
        with open(batch_file, 'w') as f:
            for domain in domains:
                f.write(f"{domain['url']}\n")
        
        # Run scraper via CLI
        print("Running scraper...")
        start_time = time.time()
        
        # Get the virtual environment python
        python_exe = sys.executable
        main_script = Path(__file__).parent.parent / 'main.py'
        
        cmd = [
            python_exe,
            str(main_script),
            '--batch', str(batch_file),
            '--output', str(output_file),
            '--parallel',
            '--max-concurrent', '3'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout * len(domains),
                capture_output=True,
                text=True
            )
            
            elapsed = time.time() - start_time
            
            print(f"\nScraper completed in {elapsed:.1f}s")
            print(f"Exit code: {result.returncode}")
            
            # Validate output
            if output_file.exists():
                stats = validate_csv_output(str(output_file))
                
                print(f"\nOutput Validation:")
                print(f"  Total records: {stats.get('total_records', 0)}")
                print(f"  Extraction success: {stats.get('extraction_success', 0)} "
                      f"({stats.get('success_rate', 0):.0f}%)")
                print(f"  Rich data quality: {stats.get('rich_data', 0)} "
                      f"({stats.get('data_quality', 0):.0f}%)")
                
                return {
                    'success': True,
                    'exit_code': result.returncode,
                    'elapsed_s': elapsed,
                    'stats': stats
                }
            else:
                print(f"\n✗ Output file not created: {output_file}")
                return {
                    'success': False,
                    'error': 'No output file created',
                    'exit_code': result.returncode
                }
        
        except subprocess.TimeoutExpired:
            print(f"\n✗ Test timed out after {timeout * len(domains)}s")
            return {'success': False, 'error': 'Timeout'}
        
        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            return {'success': False, 'error': str(e)}


def print_test_summary(result: Dict[str, Any], target_success_rate: float = 60.0):
    """Print test summary and determine pass/fail."""
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    if not result.get('success'):
        print(f"\n✗ TEST FAILED: {result.get('error', 'Unknown error')}")
        return False
    
    stats = result.get('stats', {})
    
    # Check if we meet target
    success_rate = stats.get('success_rate', 0)
    data_quality = stats.get('data_quality', 0)
    
    # Combined score: average of success rate and data quality
    combined_score = (success_rate + data_quality) / 2
    
    print(f"\nMetrics:")
    print(f"  Extraction Success Rate: {success_rate:.1f}%")
    print(f"  Data Quality Score: {data_quality:.1f}%")
    print(f"  Combined Score: {combined_score:.1f}%")
    print(f"  Target: >{target_success_rate:.0f}%")
    
    passed = combined_score >= target_success_rate
    
    print(f"\n{'='*70}")
    if passed:
        print(f"✓ TEST PASSED: {combined_score:.1f}% score (target: >{target_success_rate:.0f}%)")
    else:
        print(f"✗ TEST FAILED: {combined_score:.1f}% score (target: >{target_success_rate:.0f}%)")
    print("="*70)
    
    return passed


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple E2E Integration Test')
    parser.add_argument('--quick', action='store_true',
                       help='Test only first 2 domains')
    parser.add_argument('--timeout', type=int, default=120,
                       help='Timeout per domain in seconds')
    parser.add_argument('--target', type=float, default=60.0,
                       help='Target success rate (default: 60%%)')
    
    args = parser.parse_args()
    
    # Select domains
    domains = TEST_DOMAINS[:2] if args.quick else TEST_DOMAINS
    
    # Run test
    try:
        result = run_scraper_test(domains, timeout=args.timeout)
        passed = print_test_summary(result, target_success_rate=args.target)
        
        return 0 if passed else 1
    
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

