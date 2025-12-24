#!/usr/bin/env python3
"""
Google ADK Workflow Example (PH5-S2 Complete)

This example demonstrates using the Company Info Scraper with Google ADK orchestration.

Requirements:
- google-adk installed (pip install google-adk)
- Ollama running with a model pulled (e.g., ollama pull llama3)

Usage:
    python examples/adk_workflow_example.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def example_1_check_adk_availability():
    """Example 1: Check if ADK is available and properly configured."""
    print("="*60)
    print("Example 1: Check ADK Availability")
    print("="*60)
    
    from company_info_scraper.agents import is_adk_available
    
    if is_adk_available():
        print("✓ Google ADK is installed and available")
        
        try:
            from google.adk import __version__
            print(f"  ADK Version: {__version__}")
        except:
            print("  ADK Version: unknown")
    else:
        print("✗ Google ADK is not installed")
        print("  Install with: pip install google-adk")
        return False
    
    return True


def example_2_create_adk_agent():
    """Example 2: Create an ADK-wrapped agent."""
    print("\n" + "="*60)
    print("Example 2: Create ADK-Wrapped Agent")
    print("="*60)
    
    from company_info_scraper.agents import LLMExtractionAgent
    
    # Create a regular agent
    agent = LLMExtractionAgent({'model': 'llama3'})
    print(f"Created agent: {agent.name}")
    
    # Wrap it as an ADK agent
    adk_agent = agent.as_adk_agent(model='gemini-2.0-flash')
    
    if adk_agent:
        print(f"✓ ADK agent created: {adk_agent.name}")
        print(f"  Instruction: {adk_agent.instruction[:100]}...")
        
        # Show tools
        tools = agent.get_adk_tools()
        print(f"  Tools available: {len(tools)}")
        for tool in tools:
            print(f"    - {tool.func.__name__}: {tool.func.__doc__[:60] if tool.func.__doc__ else 'No description'}...")
    else:
        print("✗ Failed to create ADK agent")
    
    return adk_agent is not None


def example_3_create_workflow():
    """Example 3: Create a complete ADK workflow."""
    print("\n" + "="*60)
    print("Example 3: Create ADK Workflow")
    print("="*60)
    
    from company_info_scraper.workflows import create_adk_scrape_agent
    
    # Create workflow agent with all tools
    workflow_agent = create_adk_scrape_agent()
    
    if workflow_agent:
        print(f"✓ Workflow agent created: {workflow_agent.name}")
        print(f"  Instruction: {workflow_agent.instruction[:100]}...")
        
        if hasattr(workflow_agent, 'tools') and workflow_agent.tools:
            print(f"  Workflow has {len(workflow_agent.tools)} tools")
    else:
        print("✗ Failed to create workflow agent")
    
    return workflow_agent


def example_4_use_adk_runner():
    """Example 4: Use ADK Runner to execute workflow."""
    print("\n" + "="*60)
    print("Example 4: Execute with ADK Runner")
    print("="*60)
    
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from company_info_scraper.workflows import create_adk_scrape_agent
    
    # Create workflow
    workflow_agent = create_adk_scrape_agent()
    
    if not workflow_agent:
        print("✗ No workflow agent available")
        return False
    
    # Create Runner with session service
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="CompanyInfoScraperDemo",
        agent=workflow_agent,
        session_service=session_service
    )
    
    print(f"✓ ADK Runner initialized")
    print(f"  App: {runner.app_name}")
    print(f"  Agent: {workflow_agent.name}")
    
    # NOTE: Actual execution would be:
    # result = runner.run("Scrape example.com for company information")
    # However, this requires:
    # 1. Ollama running
    # 2. Network access
    # 3. Time to complete
    
    print("\nTo execute the workflow:")
    print("  result = runner.run('Scrape example.com for company information')")
    print("  print(result)")
    
    return True


def example_5_native_workflow():
    """Example 5: Use native workflow (without ADK Runner)."""
    print("\n" + "="*60)
    print("Example 5: Native Workflow Execution")
    print("="*60)
    
    from company_info_scraper.workflows import ScrapeWorkflowConfig, create_scrape_workflow
    
    # Create workflow with configuration
    config = ScrapeWorkflowConfig(
        auto_detect=True,           # Auto-detect static vs dynamic
        max_concurrent=5,           # Parallel processing
        llm_model='llama3',         # LLM for extraction
        use_adk_orchestration=False # Use native mode
    )
    
    workflow = create_scrape_workflow(config)
    print(f"✓ Native workflow created")
    print(f"  Auto-detect: {config.auto_detect}")
    print(f"  Max concurrent: {config.max_concurrent}")
    print(f"  LLM model: {config.llm_model}")
    
    print("\nTo run the workflow:")
    print("  result = workflow.run(['example.com'])")
    print("  print(f'Success: {result.successful}/{result.total_domains}')")
    
    return True


def example_6_compare_modes():
    """Example 6: Compare ADK vs Native orchestration."""
    print("\n" + "="*60)
    print("Example 6: ADK vs Native Orchestration")
    print("="*60)
    
    print("\nADK Orchestration Mode:")
    print("  Pros:")
    print("    - Built-in observability and telemetry")
    print("    - Session management and state tracking")
    print("    - Standardized agent interfaces")
    print("    - Integrated with Google Cloud services")
    print("  Cons:")
    print("    - Requires google-adk package")
    print("    - Additional configuration complexity")
    print("    - May require cloud credentials")
    
    print("\nNative Orchestration Mode:")
    print("  Pros:")
    print("    - No external dependencies beyond core packages")
    print("    - Full control over execution flow")
    print("    - Optimized for local Ollama usage")
    print("    - Simpler deployment")
    print("  Cons:")
    print("    - Manual observability implementation")
    print("    - Custom session/state management")
    
    print("\nRecommendation:")
    print("  - Use ADK mode for production with cloud integration")
    print("  - Use native mode for local development and simple deployments")
    
    return True


def main():
    """Run all examples."""
    print("Google ADK Workflow Examples")
    print("Company Info Scraper - PH5-S2 Complete")
    print()
    
    examples = [
        example_1_check_adk_availability,
        example_2_create_adk_agent,
        example_3_create_workflow,
        example_4_use_adk_runner,
        example_5_native_workflow,
        example_6_compare_modes,
    ]
    
    try:
        for example in examples:
            if not example():
                print(f"\n⚠ Example {example.__name__} indicated an issue")
                print("  Continuing with remaining examples...")
    except Exception as e:
        print(f"\n✗ Example failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Review the examples above")
    print("  2. Try running with actual domains (requires Ollama)")
    print("  3. Check test_adk_integration.py for more tests")
    print("  4. See DEPLOYMENT.md for production setup")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

