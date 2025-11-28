#!/usr/bin/env python3
"""
Test script for ADK Agent Integration (PH5-S2)

Verifies that agents are properly wrapped for Google ADK compatibility.
Run with: python -m pytest tests/test_adk_agents.py -v
Or directly: python tests/test_adk_agents.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_base_agent_import():
    """Test BaseAgent and utilities can be imported."""
    try:
        from company_info_scraper.agents import (
            BaseAgent,
            AgentToolSpec,
            adk_tool,
            is_adk_available
        )
        print("✓ BaseAgent and utilities imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import BaseAgent: {e}")
        return False


def test_agent_classes_import():
    """Test all agent classes can be imported."""
    try:
        from company_info_scraper.agents import (
            ScrapingAgent,
            AsyncScrapingAgent,
            LLMExtractionAgent,
            OrchestratorAgent
        )
        print("✓ All agent classes imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import agent classes: {e}")
        return False


def test_adk_utilities_import():
    """Test ADK utility functions can be imported."""
    try:
        from company_info_scraper.agents import (
            create_adk_workflow,
            get_all_tools,
            is_adk_available
        )
        print("✓ ADK utility functions imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import ADK utilities: {e}")
        return False


def test_agent_instantiation():
    """Test agents can be instantiated."""
    try:
        from company_info_scraper.agents import (
            ScrapingAgent,
            LLMExtractionAgent,
            OrchestratorAgent
        )
        
        # Test with default config
        scraping = ScrapingAgent()
        llm = LLMExtractionAgent()
        orchestrator = OrchestratorAgent()
        
        print(f"✓ ScrapingAgent instantiated: {scraping.name}")
        print(f"✓ LLMExtractionAgent instantiated: {llm.name}")
        print(f"✓ OrchestratorAgent instantiated: {orchestrator.name}")
        return True
    except Exception as e:
        print(f"✗ Failed to instantiate agents: {e}")
        return False


def test_agent_registry():
    """Test agent registry functionality."""
    try:
        from company_info_scraper.agents import BaseAgent, OrchestratorAgent
        
        # Clear registry first
        BaseAgent.clear_registry()
        
        # Create an agent
        agent = OrchestratorAgent({'test': True})
        
        # Check registry
        registered = BaseAgent.get_agent("OrchestratorAgent")
        assert registered is not None, "Agent not found in registry"
        assert registered is agent, "Registry returned different instance"
        
        # Test get_all_agents
        all_agents = BaseAgent.get_all_agents()
        assert "OrchestratorAgent" in all_agents, "Agent not in all_agents"
        
        print("✓ Agent registry working correctly")
        return True
    except Exception as e:
        print(f"✗ Agent registry test failed: {e}")
        return False


def test_tool_specs():
    """Test tool specification registration."""
    try:
        from company_info_scraper.agents import OrchestratorAgent
        
        agent = OrchestratorAgent()
        
        # Check tool specs are registered
        specs = agent.get_tool_specs()
        assert len(specs) > 0, "No tool specs registered"
        
        # Check tool names
        tool_names = [s.name for s in specs]
        expected_tools = ['scrape_and_extract', 'batch_scrape_and_extract', 'detect_site_type']
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing expected tool: {expected}"
        
        print(f"✓ Tool specs registered: {tool_names}")
        return True
    except Exception as e:
        print(f"✗ Tool specs test failed: {e}")
        return False


def test_adk_availability_check():
    """Test ADK availability checking."""
    try:
        from company_info_scraper.agents import is_adk_available
        
        available = is_adk_available()
        status = "available" if available else "not available"
        print(f"✓ ADK availability check works: ADK is {status}")
        return True
    except Exception as e:
        print(f"✗ ADK availability check failed: {e}")
        return False


def test_adk_tools_generation():
    """Test ADK tools can be generated (graceful fallback if ADK not installed)."""
    try:
        from company_info_scraper.agents import (
            OrchestratorAgent,
            is_adk_available
        )
        
        agent = OrchestratorAgent()
        tools = agent.get_adk_tools()
        
        if is_adk_available():
            assert len(tools) > 0, "No ADK tools generated"
            print(f"✓ Generated {len(tools)} ADK tools")
        else:
            assert len(tools) == 0, "Tools generated without ADK"
            print("✓ Graceful fallback when ADK not installed (empty tools list)")
        
        return True
    except Exception as e:
        print(f"✗ ADK tools generation test failed: {e}")
        return False


def test_adk_workflow_creation():
    """Test ADK workflow creation (graceful fallback if ADK not installed)."""
    try:
        from company_info_scraper.agents import (
            create_adk_workflow,
            is_adk_available
        )
        
        workflow = create_adk_workflow({'auto_detect': True})
        
        if is_adk_available():
            assert workflow is not None, "Workflow not created when ADK available"
            print(f"✓ ADK workflow created successfully")
        else:
            assert workflow is None, "Workflow created without ADK"
            print("✓ Graceful fallback when ADK not installed (None returned)")
        
        return True
    except Exception as e:
        print(f"✗ ADK workflow creation test failed: {e}")
        return False


def test_sub_agents_access():
    """Test sub-agents can be accessed from orchestrator."""
    try:
        from company_info_scraper.agents import OrchestratorAgent
        
        orchestrator = OrchestratorAgent()
        sub_agents = orchestrator.get_sub_agents()
        
        assert 'scraping' in sub_agents, "Scraping agent not found"
        assert 'llm_extraction' in sub_agents, "LLM agent not found"
        
        print(f"✓ Sub-agents accessible: {list(sub_agents.keys())}")
        return True
    except Exception as e:
        print(f"✗ Sub-agents access test failed: {e}")
        return False


def test_agent_execute_validation():
    """Test agent input validation."""
    try:
        from company_info_scraper.agents import LLMExtractionAgent
        
        agent = LLMExtractionAgent()
        
        # Test missing required field
        result = agent.execute({})  # Missing 'text' field
        
        assert result.get('success') == False, "Should fail without required field"
        assert 'error' in result, "Should have error message"
        
        print("✓ Input validation working correctly")
        return True
    except Exception as e:
        print(f"✗ Input validation test failed: {e}")
        return False


def test_async_execute_available():
    """Test async execute method is available."""
    try:
        from company_info_scraper.agents import OrchestratorAgent
        import asyncio
        
        agent = OrchestratorAgent()
        
        # Check execute_async exists and is a coroutine function
        assert hasattr(agent, 'execute_async'), "Missing execute_async method"
        assert asyncio.iscoroutinefunction(agent.execute_async), "execute_async not async"
        
        print("✓ Async execute method available")
        return True
    except Exception as e:
        print(f"✗ Async execute test failed: {e}")
        return False


def print_summary():
    """Print ADK integration summary."""
    from company_info_scraper.agents import is_adk_available, BaseAgent
    
    print("\n" + "="*60)
    print("ADK Agent Integration Summary (PH5-S2)")
    print("="*60)
    
    print(f"\nGoogle ADK installed: {'Yes ✓' if is_adk_available() else 'No (install with: pip install google-adk)'}")
    
    # List registered agents
    agents = BaseAgent.get_all_agents()
    print(f"\nRegistered agents: {len(agents)}")
    for name, agent in agents.items():
        tools = agent.get_tool_specs()
        print(f"  - {name}: {len(tools)} tools")
        for tool in tools:
            print(f"      • {tool.name}")


def main():
    """Run all tests."""
    print("Testing ADK Agent Integration (PH5-S2)")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("BaseAgent Import", test_base_agent_import()))
    results.append(("Agent Classes Import", test_agent_classes_import()))
    results.append(("ADK Utilities Import", test_adk_utilities_import()))
    results.append(("Agent Instantiation", test_agent_instantiation()))
    results.append(("Agent Registry", test_agent_registry()))
    results.append(("Tool Specs", test_tool_specs()))
    results.append(("ADK Availability Check", test_adk_availability_check()))
    results.append(("ADK Tools Generation", test_adk_tools_generation()))
    results.append(("ADK Workflow Creation", test_adk_workflow_creation()))
    results.append(("Sub-Agents Access", test_sub_agents_access()))
    results.append(("Input Validation", test_agent_execute_validation()))
    results.append(("Async Execute", test_async_execute_available()))
    
    # Print summary
    print_summary()
    
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
        print("\n✓ All ADK agent integration tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

