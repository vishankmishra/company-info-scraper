#!/usr/bin/env python3
"""
Test script for ADK Workflow (PH5-S3)

Verifies that the scrape workflow is properly implemented and can be
executed both in native and ADK modes.

Run with: python -m pytest tests/test_adk_workflow.py -v
Or directly: python tests/test_adk_workflow.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_workflow_imports():
    """Test workflow module can be imported."""
    try:
        from company_info_scraper.workflows import (
            ScrapeWorkflowConfig,
            ScrapeWorkflowResult,
            ScrapeWorkflow,
            create_scrape_workflow,
            run_scrape_workflow,
            run_scrape_workflow_async,
        )
        print("✓ Workflow module imports successful")
        return True
    except ImportError as e:
        print(f"✗ Failed to import workflow module: {e}")
        return False


def test_workflow_config():
    """Test workflow configuration dataclass."""
    try:
        from company_info_scraper.workflows import ScrapeWorkflowConfig
        
        # Test default config
        config = ScrapeWorkflowConfig()
        assert config.auto_detect == True
        assert config.max_concurrent == 5
        assert config.llm_model == 'llama3'
        assert config.output_format == 'csv'
        
        # Test custom config
        config = ScrapeWorkflowConfig(
            auto_detect=False,
            force_scraper='static',
            max_concurrent=10,
            llm_timeout=120
        )
        assert config.auto_detect == False
        assert config.force_scraper == 'static'
        assert config.max_concurrent == 10
        assert config.llm_timeout == 120
        
        print("✓ Workflow config working correctly")
        return True
    except Exception as e:
        print(f"✗ Workflow config test failed: {e}")
        return False


def test_workflow_result():
    """Test workflow result dataclass."""
    try:
        from company_info_scraper.workflows.scrape_workflow import (
            ScrapeWorkflowResult,
            DomainScrapeResult
        )
        
        # Create sample results
        domain_result = DomainScrapeResult(
            domain='example.com',
            success=True,
            scraper_type='static',
            records_count=3,
            elapsed_ms=1500.0
        )
        
        result = ScrapeWorkflowResult(
            total_domains=1,
            successful=1,
            failed=0,
            static_scraped=1,
            dynamic_scraped=0,
            total_elapsed_ms=1500.0,
            avg_time_per_domain_ms=1500.0,
            output_files=['test.csv'],
            results=[domain_result]
        )
        
        # Test to_dict
        result_dict = result.to_dict()
        assert result_dict['total_domains'] == 1
        assert result_dict['successful'] == 1
        assert len(result_dict['results']) == 1
        
        print("✓ Workflow result dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ Workflow result test failed: {e}")
        return False


def test_workflow_instantiation():
    """Test workflow can be instantiated."""
    try:
        from company_info_scraper.workflows import (
            ScrapeWorkflow,
            ScrapeWorkflowConfig,
            create_scrape_workflow
        )
        
        # Test direct instantiation
        workflow = ScrapeWorkflow()
        assert workflow.config is not None
        assert workflow.orchestrator is not None
        
        # Test with config
        config = ScrapeWorkflowConfig(max_concurrent=3)
        workflow = ScrapeWorkflow(config)
        assert workflow.config.max_concurrent == 3
        
        # Test factory function
        workflow = create_scrape_workflow(config)
        assert workflow is not None
        
        print("✓ Workflow instantiation successful")
        return True
    except Exception as e:
        print(f"✗ Workflow instantiation failed: {e}")
        return False


def test_workflow_adk_tools():
    """Test workflow ADK tools generation."""
    try:
        from company_info_scraper.workflows import ScrapeWorkflow
        from company_info_scraper.agents import is_adk_available
        
        workflow = ScrapeWorkflow()
        tools = workflow.get_adk_tools()
        
        if is_adk_available():
            assert len(tools) > 0, "No tools generated when ADK available"
            print(f"✓ Generated {len(tools)} ADK workflow tools")
        else:
            assert len(tools) == 0, "Tools generated without ADK"
            print("✓ Graceful fallback when ADK not installed")
        
        return True
    except Exception as e:
        print(f"✗ Workflow ADK tools test failed: {e}")
        return False


def test_adk_agent_creation():
    """Test ADK agent creation from workflow."""
    try:
        from company_info_scraper.workflows.scrape_workflow import create_adk_scrape_agent
        from company_info_scraper.agents import is_adk_available
        
        agent = create_adk_scrape_agent()
        
        if is_adk_available():
            assert agent is not None, "Agent not created when ADK available"
            print("✓ ADK scrape agent created successfully")
        else:
            assert agent is None, "Agent created without ADK"
            print("✓ Graceful fallback when ADK not installed")
        
        return True
    except Exception as e:
        print(f"✗ ADK agent creation test failed: {e}")
        return False


def test_workflow_callbacks():
    """Test workflow callback configuration."""
    try:
        from company_info_scraper.workflows import ScrapeWorkflowConfig
        
        callback_calls = []
        
        def on_start(domain):
            callback_calls.append(('start', domain))
        
        def on_complete(domain, result):
            callback_calls.append(('complete', domain))
        
        def on_progress(current, total, domain):
            callback_calls.append(('progress', current, total))
        
        config = ScrapeWorkflowConfig(
            on_domain_start=on_start,
            on_domain_complete=on_complete,
            on_progress=on_progress
        )
        
        assert config.on_domain_start is not None
        assert config.on_domain_complete is not None
        assert config.on_progress is not None
        
        print("✓ Workflow callbacks configured correctly")
        return True
    except Exception as e:
        print(f"✗ Workflow callbacks test failed: {e}")
        return False


def test_workflow_output_formats():
    """Test workflow supports different output formats."""
    try:
        from company_info_scraper.workflows import ScrapeWorkflowConfig
        
        # Test CSV format
        config = ScrapeWorkflowConfig(output_format='csv')
        assert config.output_format == 'csv'
        
        # Test JSON format
        config = ScrapeWorkflowConfig(output_format='json')
        assert config.output_format == 'json'
        
        # Test both formats
        config = ScrapeWorkflowConfig(output_format='both')
        assert config.output_format == 'both'
        
        print("✓ Workflow supports all output formats")
        return True
    except Exception as e:
        print(f"✗ Output formats test failed: {e}")
        return False


def test_convenience_functions():
    """Test convenience functions exist and are callable."""
    try:
        from company_info_scraper.workflows import (
            run_scrape_workflow,
            run_scrape_workflow_async
        )
        import asyncio
        
        # Check functions exist
        assert callable(run_scrape_workflow)
        assert asyncio.iscoroutinefunction(run_scrape_workflow_async)
        
        print("✓ Convenience functions available")
        return True
    except Exception as e:
        print(f"✗ Convenience functions test failed: {e}")
        return False


def print_workflow_summary():
    """Print workflow capabilities summary."""
    from company_info_scraper.workflows import ScrapeWorkflow, ScrapeWorkflowConfig
    from company_info_scraper.agents import is_adk_available
    
    print("\n" + "="*60)
    print("ADK Workflow Summary (PH5-S3)")
    print("="*60)
    
    print(f"\nADK available: {'Yes ✓' if is_adk_available() else 'No (native mode only)'}")
    
    config = ScrapeWorkflowConfig()
    print(f"\nDefault configuration:")
    print(f"  - Auto-detect: {config.auto_detect}")
    print(f"  - Max concurrent: {config.max_concurrent}")
    print(f"  - LLM model: {config.llm_model}")
    print(f"  - LLM timeout: {config.llm_timeout}s")
    print(f"  - Output format: {config.output_format}")
    
    workflow = ScrapeWorkflow()
    tools = workflow.get_adk_tools()
    print(f"\nWorkflow tools: {len(tools)}")
    
    print(f"\nWorkflow modes:")
    print(f"  - Native mode: Always available")
    print(f"  - ADK mode: {'Available' if is_adk_available() else 'Requires google-adk'}")


def main():
    """Run all tests."""
    print("Testing ADK Workflow (PH5-S3)")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Workflow Imports", test_workflow_imports()))
    results.append(("Workflow Config", test_workflow_config()))
    results.append(("Workflow Result", test_workflow_result()))
    results.append(("Workflow Instantiation", test_workflow_instantiation()))
    results.append(("ADK Tools", test_workflow_adk_tools()))
    results.append(("ADK Agent Creation", test_adk_agent_creation()))
    results.append(("Callbacks", test_workflow_callbacks()))
    results.append(("Output Formats", test_workflow_output_formats()))
    results.append(("Convenience Functions", test_convenience_functions()))
    
    # Print summary
    print_workflow_summary()
    
    # Test results
    print("\n" + "="*60)
    print("Test Results")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All ADK workflow tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

