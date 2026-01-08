#!/usr/bin/env python3
"""
Full Pipeline Orchestration Script
Connects Phase A (Scraping) and Phase B (LLM Experimentation)

This script automates the complete data processing pipeline:
1. Phase A: Scrape domains from data/domains_phase_a.txt → data/enterprise_raw.jsonl
2. Phase B: Run LLM experiments on enterprise_raw.jsonl → data/experiment_results_groq.jsonl

Usage:
    python scripts/run_full_pipeline.py
    python scripts/run_full_pipeline.py --skip-scrape  # Skip scraping if already done
    python scripts/run_full_pipeline.py --skip-llm     # Only run scraping
    python scripts/run_full_pipeline.py --timeout 180  # Custom timeout per domain

Requirements:
    - data/domains_phase_a.txt must exist
    - GROQ_API_KEY environment variable must be set for Phase B
"""

import sys
import os
import subprocess
import argparse
import time
from pathlib import Path
from typing import Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DOMAINS_FILE = PROJECT_ROOT / 'data' / 'domains_phase_a.txt'
OUTPUT_JSONL = PROJECT_ROOT / 'data' / 'enterprise_raw.jsonl'
EXPERIMENT_OUTPUT = PROJECT_ROOT / 'data' / 'experiment_results_groq.jsonl'
BATCH_SCRAPER = PROJECT_ROOT / 'batch_scrape_raw.py'
EXPERIMENT_SCRIPT = PROJECT_ROOT / 'scripts' / 'experiment_groq.py'


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    width = 70
    print()
    print(char * width)
    print(f"  {text}")
    print(char * width)
    print()


def print_step(step_num: int, total_steps: int, title: str, emoji: str = "🚀"):
    """Print a step header."""
    print()
    print(f"{emoji} STEP {step_num}/{total_steps}: {title}")
    print("-" * 70)


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists and print result."""
    if file_path.exists():
        print(f"✓ {description} found: {file_path}")
        return True
    else:
        print(f"✗ {description} not found: {file_path}")
        return False


def count_domains(domains_file: Path) -> int:
    """Count the number of valid domains in the file."""
    try:
        with open(domains_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return len(domains)
    except Exception as e:
        print(f"⚠️  Error reading domains file: {e}")
        return 0


def run_command(
    command: list,
    description: str,
    timeout: Optional[int] = None,
    check: bool = True
) -> subprocess.CompletedProcess:
    """
    Run a command with proper error handling.
    
    Args:
        command: Command to run as list of strings
        description: Human-readable description of the command
        timeout: Optional timeout in seconds
        check: If True, raise exception on non-zero exit code
        
    Returns:
        CompletedProcess result
        
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        subprocess.TimeoutExpired: If timeout is exceeded
    """
    print(f"\n⏳ Running: {description}...")
    print(f"   Command: {' '.join(str(c) for c in command)}")
    print()
    
    try:
        result = subprocess.run(
            command,
            check=check,
            timeout=timeout,
            cwd=PROJECT_ROOT
        )
        
        if result.returncode == 0:
            print(f"\n✅ {description} completed successfully!")
        else:
            print(f"\n⚠️  {description} completed with warnings (exit code: {result.returncode})")
        
        return result
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code: {e.returncode}")
        raise
    except subprocess.TimeoutExpired as e:
        print(f"\n❌ {description} timed out after {timeout} seconds")
        raise


def verify_scrape_output() -> tuple[bool, int]:
    """
    Verify that the scraper produced valid output.
    
    Returns:
        Tuple of (success: bool, record_count: int)
    """
    if not OUTPUT_JSONL.exists():
        print(f"✗ Output file not found: {OUTPUT_JSONL}")
        return False, 0
    
    try:
        import json
        record_count = 0
        valid_records = 0
        
        with open(OUTPUT_JSONL, 'r') as f:
            for line in f:
                if line.strip():
                    record_count += 1
                    try:
                        record = json.loads(line)
                        if record.get('scrape_status') == 'success':
                            valid_records += 1
                    except json.JSONDecodeError:
                        pass
        
        print(f"✓ Output file verified: {record_count} records ({valid_records} successful)")
        return record_count > 0, record_count
        
    except Exception as e:
        print(f"✗ Error verifying output: {e}")
        return False, 0


def run_phase_a_scraping(timeout_per_domain: int = 120) -> bool:
    """
    Run Phase A: Scraping.
    
    Args:
        timeout_per_domain: Timeout in seconds for each domain
        
    Returns:
        True if scraping succeeded, False otherwise
    """
    print_step(1, 2, "PHASE A - Web Scraping", "🕷️")
    
    # Check prerequisites
    if not check_file_exists(DOMAINS_FILE, "Domains file"):
        print("\n❌ Cannot proceed without domains file!")
        return False
    
    if not check_file_exists(BATCH_SCRAPER, "Batch scraper script"):
        print("\n❌ Cannot proceed without batch scraper!")
        return False
    
    domain_count = count_domains(DOMAINS_FILE)
    print(f"✓ Found {domain_count} domains to scrape")
    
    if domain_count == 0:
        print("\n❌ No domains to scrape!")
        return False
    
    # Estimate time
    estimated_time = domain_count * 15  # ~15 seconds average per domain
    print(f"⏱️  Estimated time: ~{estimated_time // 60} minutes ({estimated_time} seconds)")
    
    # Run the scraper
    scraper_start = time.time()
    
    try:
        result = run_command(
            command=[
                sys.executable,
                str(BATCH_SCRAPER),
                '--domains-file', str(DOMAINS_FILE),
                '--format', 'jsonl',
                '--output', str(OUTPUT_JSONL),
                '--timeout', str(timeout_per_domain)
            ],
            description="Batch scraping",
            timeout=None,  # Let the scraper handle per-domain timeouts
            check=False    # Don't fail if some domains fail (exit code 2)
        )
        
        scraper_elapsed = time.time() - scraper_start
        
        # Verify output
        success, record_count = verify_scrape_output()
        
        if not success:
            print("\n❌ Scraping failed - no valid output produced")
            return False
        
        print(f"\n✅ Phase A Complete!")
        print(f"   - Scraped {record_count} domains in {scraper_elapsed/60:.1f} minutes")
        print(f"   - Output: {OUTPUT_JSONL}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Scraping failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Scraping failed with error: {e}")
        return False


def run_phase_b_llm_experiment() -> bool:
    """
    Run Phase B: LLM Experimentation.
    
    Returns:
        True if experiment succeeded, False otherwise
    """
    print_step(2, 2, "PHASE B - LLM Experimentation", "🤖")
    
    # Check prerequisites
    if not check_file_exists(OUTPUT_JSONL, "Scraping output (input for LLM)"):
        print("\n❌ Cannot run LLM experiment without scraped data!")
        print("   Run Phase A first or ensure enterprise_raw.jsonl exists.")
        return False
    
    if not check_file_exists(EXPERIMENT_SCRIPT, "LLM experiment script"):
        print("\n❌ Cannot proceed without experiment script!")
        return False
    
    # Check API key
    if not os.environ.get('GROQ_API_KEY'):
        print("\n❌ GROQ_API_KEY environment variable not set!")
        print("   Please run: export GROQ_API_KEY='your-api-key'")
        return False
    else:
        api_key = os.environ.get('GROQ_API_KEY')
        print(f"✓ GROQ_API_KEY is set ({api_key[:8]}...{api_key[-4:]})")
    
    # Count input records
    try:
        import json
        record_count = 0
        with open(OUTPUT_JSONL, 'r') as f:
            for line in f:
                if line.strip():
                    record_count += 1
        print(f"✓ Found {record_count} scraped records to process")
    except Exception as e:
        print(f"⚠️  Could not count records: {e}")
        record_count = 0
    
    # Estimate time (experiment tests multiple models, ~5 domains per model)
    # With 6 models and ~5s per domain + 3s delay = ~240s per model
    estimated_time = 6 * 240  # ~24 minutes for full experiment
    print(f"⏱️  Estimated time: ~{estimated_time // 60} minutes (tests ALL models)")
    
    # Run the experiment
    experiment_start = time.time()
    
    try:
        result = run_command(
            command=[
                sys.executable,
                str(EXPERIMENT_SCRIPT)
            ],
            description="LLM experiment (ALL models)",
            timeout=None,  # Let it run (could take 20-30 minutes)
            check=True
        )
        
        experiment_elapsed = time.time() - experiment_start
        
        # Verify output
        if not EXPERIMENT_OUTPUT.exists():
            print(f"\n⚠️  Expected output file not found: {EXPERIMENT_OUTPUT}")
            return False
        
        # Count experiment results
        try:
            import json
            result_count = 0
            with open(EXPERIMENT_OUTPUT, 'r') as f:
                for line in f:
                    if line.strip():
                        result_count += 1
            print(f"✓ Generated {result_count} experiment results")
        except Exception:
            pass
        
        print(f"\n✅ Phase B Complete!")
        print(f"   - Tested ALL models in {experiment_elapsed/60:.1f} minutes")
        print(f"   - Output: {EXPERIMENT_OUTPUT}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ LLM experiment failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ LLM experiment failed with error: {e}")
        return False


def main():
    """Main orchestration function."""
    parser = argparse.ArgumentParser(
        description='Full Pipeline: Phase A (Scraping) + Phase B (LLM Experimentation)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_full_pipeline.py
    python scripts/run_full_pipeline.py --skip-scrape
    python scripts/run_full_pipeline.py --skip-llm
    python scripts/run_full_pipeline.py --timeout 180

Notes:
    - Phase A reads from: data/domains_phase_a.txt
    - Phase A outputs to: data/enterprise_raw.jsonl
    - Phase B reads from: data/enterprise_raw.jsonl
    - Phase B outputs to: data/experiment_results_groq.jsonl
    - Requires GROQ_API_KEY environment variable for Phase B
"""
    )
    
    parser.add_argument(
        '--skip-scrape',
        action='store_true',
        help='Skip Phase A (scraping) and go directly to Phase B'
    )
    
    parser.add_argument(
        '--skip-llm',
        action='store_true',
        help='Only run Phase A (scraping), skip Phase B'
    )
    
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=120,
        help='Timeout per domain for scraping in seconds (default: 120)'
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_header("FULL PIPELINE ORCHESTRATION", "█")
    print("This script runs:")
    print("  Phase A: Web Scraping (domains_phase_a.txt → enterprise_raw.jsonl)")
    print("  Phase B: LLM Experimentation (enterprise_raw.jsonl → experiment_results_groq.jsonl)")
    print()
    
    pipeline_start = time.time()
    phase_results = {}
    
    # Phase A: Scraping
    if not args.skip_scrape:
        scrape_success = run_phase_a_scraping(timeout_per_domain=args.timeout)
        phase_results['Phase A'] = scrape_success
        
        if not scrape_success:
            print_header("❌ PIPELINE FAILED - Phase A (Scraping) Failed", "✗")
            print("Cannot proceed to Phase B without scraped data.")
            print("Please fix the issues above and try again.")
            return 1
    else:
        print_step(1, 2, "PHASE A - Web Scraping", "🕷️")
        print("⏭️  Skipping Phase A (--skip-scrape flag)")
        
        # Verify input file exists
        if not check_file_exists(OUTPUT_JSONL, "Scraping output"):
            print("\n❌ Cannot skip scraping - no existing data found!")
            print(f"   Please run Phase A first or remove --skip-scrape flag.")
            return 1
        
        phase_results['Phase A'] = 'skipped'
    
    # Phase B: LLM Experiment
    if not args.skip_llm:
        llm_success = run_phase_b_llm_experiment()
        phase_results['Phase B'] = llm_success
        
        if not llm_success:
            print_header("❌ PIPELINE FAILED - Phase B (LLM Experiment) Failed", "✗")
            print("Phase A completed successfully, but Phase B failed.")
            print("Please fix the issues above and run Phase B separately if needed.")
            return 2
    else:
        print_step(2, 2, "PHASE B - LLM Experimentation", "🤖")
        print("⏭️  Skipping Phase B (--skip-llm flag)")
        phase_results['Phase B'] = 'skipped'
    
    # Final summary
    pipeline_elapsed = time.time() - pipeline_start
    
    print_header("✅ PIPELINE COMPLETE", "█")
    print("Summary:")
    print(f"  Total time: {pipeline_elapsed/60:.1f} minutes ({pipeline_elapsed:.1f} seconds)")
    print()
    
    for phase, result in phase_results.items():
        if result == 'skipped':
            status = "⏭️  SKIPPED"
        elif result:
            status = "✅ SUCCESS"
        else:
            status = "❌ FAILED"
        print(f"  {phase}: {status}")
    
    print()
    print("Output Files:")
    if OUTPUT_JSONL.exists():
        size_mb = OUTPUT_JSONL.stat().st_size / (1024 * 1024)
        print(f"  ✓ {OUTPUT_JSONL} ({size_mb:.2f} MB)")
    if EXPERIMENT_OUTPUT.exists():
        size_mb = EXPERIMENT_OUTPUT.stat().st_size / (1024 * 1024)
        print(f"  ✓ {EXPERIMENT_OUTPUT} ({size_mb:.2f} MB)")
    
    print()
    print("Next Steps:")
    print("  1. Review experiment results: data/experiment_results_groq.jsonl")
    print("  2. Analyze model performance and select best model")
    print("  3. Run production enrichment: python scripts/run_production.py")
    print()
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user (Ctrl+C)")
        print("   Progress may have been saved. Check output files.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
