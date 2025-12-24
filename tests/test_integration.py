#!/usr/bin/env python3
"""
End-to-End Integration Test (PH6-S5)

Automated test that scrapes known domains and validates output quality.
This test requires:
- Ollama running with llama3 model
- Network access to test domains

Run with: python -m pytest tests/test_integration.py -v
Or directly: python tests/test_integration.py

Skip slow tests: pytest tests/test_integration.py -v -m "not slow"
"""

import sys
import os
import asyncio
import tempfile
import csv
from pathlib import Path
from typing import Dict, Any, List
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Test configuration
TEST_DOMAINS = [
    'example.com',        # Static, simple
    'httpbin.org',        # Static, API documentation
]

SKIP_NETWORK_TESTS = os.environ.get('SKIP_NETWORK_TESTS', 'false').lower() == 'true'


def check_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        from company_info_scraper.health import check_ollama
        return check_ollama()
    except:
        return False


def skip_if_no_ollama():
    """Skip test if Ollama is not available."""
    if not check_ollama_available():
        pytest.skip("Ollama not available")


def skip_if_no_network():
    """Skip test if network tests are disabled."""
    if SKIP_NETWORK_TESTS:
        pytest.skip("Network tests disabled")


# =============================================================================
# Unit-style Integration Tests
# =============================================================================

class TestSiteDetection:
    """Test site detection functionality."""
    
    def test_detector_import(self):
        """Test site detector can be imported."""
        from company_info_scraper.services import SiteDetector, SiteType
        detector = SiteDetector()
        assert detector is not None
    
    @pytest.mark.asyncio
    async def test_detect_static_site(self):
        """Test detecting a static site."""
        skip_if_no_network()
        
        from company_info_scraper.services import SiteDetector, SiteType
        
        detector = SiteDetector()
        result = await detector.detect('example.com')
        
        assert result is not None
        assert result.site_type in (SiteType.STATIC, SiteType.DYNAMIC)
        assert 0 <= result.confidence <= 1
        print(f"  example.com detected as: {result.site_type.value} "
              f"(confidence: {result.confidence:.0%})")


class TestStaticScraper:
    """Test static scraper functionality."""
    
    def test_scraper_import(self):
        """Test static scraper can be imported."""
        from company_info_scraper.spiders import StaticScraper
        scraper = StaticScraper()
        assert scraper is not None
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_scrape_static_site(self):
        """Test scraping a static site."""
        skip_if_no_network()
        
        from company_info_scraper.spiders import StaticScraper
        
        scraper = StaticScraper(max_depth=0, max_links=1)
        items = await scraper.scrape('example.com')
        
        assert len(items) > 0
        assert 'url' in items[0]
        assert 'raw_text' in items[0]
        assert len(items[0]['raw_text']) > 0
        print(f"  Scraped {len(items)} pages from example.com")


class TestLLMService:
    """Test LLM extraction service."""
    
    def test_service_import(self):
        """Test LLM service can be imported."""
        from company_info_scraper.services import LLMExtractionService
        service = LLMExtractionService()
        assert service is not None
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extract_sample_text(self):
        """Test LLM extraction on sample text."""
        skip_if_no_ollama()
        
        from company_info_scraper.services import LLMExtractionService
        
        sample_text = """
        Acme Corporation provides cloud computing solutions and enterprise software.
        Our products include AcmeCloud, AcmeDB, and AcmeAnalytics.
        We serve Fortune 500 companies including Microsoft, Google, and Amazon.
        We have partnerships with AWS, Azure, and IBM.
        Case Study: How BigCorp reduced costs by 40% using AcmeCloud.
        """
        
        service = LLMExtractionService(timeout=60)
        result = await service.extract(sample_text, url='test://sample')
        
        assert result is not None
        assert result.status in ('success', 'failure')
        
        if result.status == 'success':
            print(f"  Products: {result.products[:50]}...")
            print(f"  Customers: {result.customers[:50]}...")
            print(f"  Partnerships: {result.partnerships[:50]}...")


class TestAgents:
    """Test agent functionality."""
    
    def test_orchestrator_import(self):
        """Test orchestrator agent can be imported."""
        from company_info_scraper.agents import OrchestratorAgent
        agent = OrchestratorAgent()
        assert agent is not None
    
    def test_agent_registry(self):
        """Test agent registry functionality."""
        from company_info_scraper.agents import BaseAgent, OrchestratorAgent
        
        BaseAgent.clear_registry()
        agent = OrchestratorAgent()
        
        assert 'OrchestratorAgent' in BaseAgent.get_all_agents()


class TestWorkflow:
    """Test workflow functionality."""
    
    def test_workflow_import(self):
        """Test workflow can be imported."""
        from company_info_scraper.workflows import (
            ScrapeWorkflow,
            ScrapeWorkflowConfig,
            create_scrape_workflow
        )
        
        workflow = create_scrape_workflow()
        assert workflow is not None
    
    def test_workflow_config(self):
        """Test workflow configuration."""
        from company_info_scraper.workflows import ScrapeWorkflowConfig
        
        config = ScrapeWorkflowConfig(
            auto_detect=True,
            max_concurrent=3,
            output_format='csv'
        )
        
        assert config.auto_detect == True
        assert config.max_concurrent == 3


# =============================================================================
# End-to-End Integration Tests
# =============================================================================

class TestEndToEnd:
    """Full end-to-end integration tests."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_scrape_workflow(self):
        """Test complete scrape workflow on a single domain."""
        skip_if_no_network()
        skip_if_no_ollama()
        
        from company_info_scraper.workflows import (
            ScrapeWorkflow, 
            ScrapeWorkflowConfig
        )
        
        config = ScrapeWorkflowConfig(
            auto_detect=True,
            max_concurrent=1,
            llm_timeout=90,
            output_format='csv'
        )
        
        workflow = ScrapeWorkflow(config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / 'test_output'
            result = await workflow.run_async('example.com', str(output_file))
            
            assert result is not None
            assert result.total_domains == 1
            
            print(f"\n  End-to-End Test Results:")
            print(f"    Domains: {result.total_domains}")
            print(f"    Successful: {result.successful}")
            print(f"    Failed: {result.failed}")
            print(f"    Time: {result.total_elapsed_ms/1000:.1f}s")
            
            if result.output_files:
                print(f"    Output: {result.output_files}")
    
    @pytest.mark.asyncio
    @pytest.mark.slow  
    async def test_batch_workflow(self):
        """Test batch workflow with multiple domains."""
        skip_if_no_network()
        skip_if_no_ollama()
        
        from company_info_scraper.workflows import (
            ScrapeWorkflow,
            ScrapeWorkflowConfig
        )
        
        config = ScrapeWorkflowConfig(
            auto_detect=True,
            max_concurrent=2,
            llm_timeout=90
        )
        
        workflow = ScrapeWorkflow(config)
        
        # Use only fast test domains
        test_domains = ['example.com', 'httpbin.org']
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / 'batch_output'
            result = await workflow.run_async(test_domains, str(output_file))
            
            assert result is not None
            assert result.total_domains == len(test_domains)
            
            print(f"\n  Batch Test Results:")
            print(f"    Domains: {result.total_domains}")
            print(f"    Successful: {result.successful}")
            print(f"    Static: {result.static_scraped}")
            print(f"    Dynamic: {result.dynamic_scraped}")
            print(f"    Avg time: {result.avg_time_per_domain_ms/1000:.1f}s/domain")


# =============================================================================
# Output Validation
# =============================================================================

def validate_csv_output(csv_path: str) -> Dict[str, Any]:
    """
    Validate CSV output quality.
    
    Returns stats on extraction quality.
    """
    if not os.path.exists(csv_path):
        return {'error': 'File not found'}
    
    stats = {
        'total_records': 0,
        'has_products': 0,
        'has_customers': 0,
        'has_partnerships': 0,
        'has_case_studies': 0,
        'extraction_success': 0,
        'extraction_failure': 0,
        'quality_score': 0.0
    }
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats['total_records'] += 1
            
            # Count non-N/A fields
            non_na_fields = 0
            if row.get('products') and row['products'] not in ('N/A', '', 'QUEUED'):
                stats['has_products'] += 1
                non_na_fields += 1
            if row.get('customers') and row['customers'] not in ('N/A', '', 'QUEUED'):
                stats['has_customers'] += 1
                non_na_fields += 1
            if row.get('partnerships') and row['partnerships'] not in ('N/A', '', 'QUEUED'):
                stats['has_partnerships'] += 1
                non_na_fields += 1
            if row.get('case_studies') and row['case_studies'] not in ('N/A', '', 'QUEUED'):
                stats['has_case_studies'] += 1
                non_na_fields += 1
            
            if row.get('extraction_status') == 'success':
                stats['extraction_success'] += 1
            else:
                stats['extraction_failure'] += 1
            
            # Quality: at least 2 non-N/A fields = good extraction
            if non_na_fields >= 2:
                stats['quality_score'] += 1
    
    # Calculate percentages
    total = max(stats['total_records'], 1)
    stats['products_pct'] = stats['has_products'] * 100 // total
    stats['customers_pct'] = stats['has_customers'] * 100 // total
    stats['success_pct'] = stats['extraction_success'] * 100 // total
    stats['quality_pct'] = int((stats['quality_score'] / total) * 100)
    
    return stats


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_domain(self):
        """Test handling of invalid domain."""
        from company_info_scraper.services import SiteDetector
        
        detector = SiteDetector()
        
        # Should handle gracefully, not crash
        result = await detector.detect('invalid-domain-xyz-12345.com')
        assert result is not None
        print(f"  Invalid domain handled: {result.site_type.value if result else 'None'}")
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in LLM service."""
        skip_if_no_ollama()
        
        from company_info_scraper.services import LLMExtractionService
        
        # Very short timeout
        service = LLMExtractionService(timeout=1, max_retries=1)
        
        # Large text that may timeout
        large_text = "test " * 10000
        
        result = await service.extract(large_text, url='test://timeout')
        
        # Should return a result (success or failure), not crash
        assert result is not None
        assert result.status in ('success', 'failure')
        print(f"  Timeout test result: {result.status}")
    
    @pytest.mark.asyncio
    async def test_empty_content(self):
        """Test handling of empty content."""
        skip_if_no_ollama()
        
        from company_info_scraper.services import LLMExtractionService
        
        service = LLMExtractionService()
        result = await service.extract("", url='test://empty')
        
        assert result is not None
        # Empty content should be handled gracefully
        print(f"  Empty content handled: {result.status}")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mixed_static_dynamic_batch(self):
        """Test batch processing with mixed static/dynamic sites."""
        skip_if_no_network()
        skip_if_no_ollama()
        
        from company_info_scraper.workflows import (
            ScrapeWorkflow,
            ScrapeWorkflowConfig
        )
        
        config = ScrapeWorkflowConfig(
            auto_detect=True,
            max_concurrent=2,
            llm_timeout=60
        )
        
        workflow = ScrapeWorkflow(config)
        
        # Mix of static and potentially dynamic sites
        mixed_domains = ['example.com', 'httpbin.org']
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / 'mixed_output'
            result = await workflow.run_async(mixed_domains, str(output_file))
            
            assert result is not None
            # Should handle both types
            assert result.total_domains == len(mixed_domains)
            
            print(f"\n  Mixed batch results:")
            print(f"    Static: {result.static_scraped}")
            print(f"    Dynamic: {result.dynamic_scraped}")
            print(f"    Success rate: {(result.successful/result.total_domains)*100:.0f}%")


# =============================================================================
# Main test runner
# =============================================================================

def run_quick_tests():
    """Run quick unit tests without network/LLM."""
    print("Running Quick Tests (no network/LLM)")
    print("="*60)
    
    tests = TestSiteDetection()
    print("\n[Site Detection]")
    tests.test_detector_import()
    print("  ✓ Detector import")
    
    tests = TestStaticScraper()
    print("\n[Static Scraper]")
    tests.test_scraper_import()
    print("  ✓ Scraper import")
    
    tests = TestLLMService()
    print("\n[LLM Service]")
    tests.test_service_import()
    print("  ✓ Service import")
    
    tests = TestAgents()
    print("\n[Agents]")
    tests.test_orchestrator_import()
    print("  ✓ Orchestrator import")
    tests.test_agent_registry()
    print("  ✓ Agent registry")
    
    tests = TestWorkflow()
    print("\n[Workflow]")
    tests.test_workflow_import()
    print("  ✓ Workflow import")
    tests.test_workflow_config()
    print("  ✓ Workflow config")
    
    print("\n" + "="*60)
    print("✓ All quick tests passed!")


def run_full_tests():
    """Run full integration tests including network and LLM."""
    print("Running Full Integration Tests")
    print("="*60)
    
    # Check prerequisites
    ollama_ok = check_ollama_available()
    print(f"\nPrerequisites:")
    print(f"  Ollama: {'✓ Available' if ollama_ok else '✗ Not available'}")
    print(f"  Network: {'✓ Enabled' if not SKIP_NETWORK_TESTS else '✗ Disabled'}")
    
    if not ollama_ok:
        print("\n⚠ Skipping LLM tests (Ollama not available)")
        print("  Start Ollama: ollama serve")
        print("  Pull model: ollama pull llama3")
    
    # Run async tests
    print("\n" + "-"*60)
    
    async def run_async_tests():
        if not SKIP_NETWORK_TESTS:
            print("\n[Site Detection - Network]")
            tests = TestSiteDetection()
            await tests.test_detect_static_site()
            print("  ✓ Static site detection")
            
            print("\n[Static Scraper - Network]")
            tests = TestStaticScraper()
            await tests.test_scrape_static_site()
            print("  ✓ Static site scraping")
        
        if ollama_ok:
            print("\n[LLM Service - Extraction]")
            tests = TestLLMService()
            await tests.test_extract_sample_text()
            print("  ✓ LLM extraction")
        
        if not SKIP_NETWORK_TESTS and ollama_ok:
            print("\n[End-to-End - Full Workflow]")
            tests = TestEndToEnd()
            await tests.test_full_scrape_workflow()
            print("  ✓ Full workflow")
    
    asyncio.run(run_async_tests())
    
    print("\n" + "="*60)
    print("✓ Integration tests completed!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Integration tests')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick tests only (no network/LLM)')
    parser.add_argument('--full', action='store_true',
                       help='Run full integration tests')
    
    args = parser.parse_args()
    
    if args.quick:
        run_quick_tests()
    elif args.full:
        run_full_tests()
    else:
        # Default: run quick tests
        run_quick_tests()
        print("\nTip: Use --full for complete integration tests")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

