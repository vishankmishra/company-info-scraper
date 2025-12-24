#!/usr/bin/env python3
"""
Test ADK Integration (PH5-S2)

Tests the complete ADK integration including:
- ADK imports with correct paths
- Tool registration
- Agent creation
- Basic workflow execution
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_adk_imports():
    """Test that ADK can be imported with correct paths."""
    print("Testing ADK imports...")
    
    try:
        from google.adk import Agent, Runner
        print("  ✓ google.adk.Agent and Runner imported")
    except ImportError as e:
        print(f"  ✗ Failed to import Agent/Runner: {e}")
        return False
    
    try:
        from google.adk.agents import LlmAgent
        print("  ✓ google.adk.agents.LlmAgent imported")
    except ImportError as e:
        print(f"  ✗ Failed to import LlmAgent: {e}")
        return False
    
    try:
        from google.adk.tools import FunctionTool
        print("  ✓ google.adk.tools.FunctionTool imported")
    except ImportError as e:
        print(f"  ✗ Failed to import FunctionTool: {e}")
        return False
    
    return True


def test_agent_creation():
    """Test creating ADK-wrapped agents."""
    print("\nTesting agent creation...")
    
    try:
        from company_info_scraper.agents import is_adk_available
        
        if not is_adk_available():
            print("  ✗ ADK not available in agents module")
            return False
        
        print("  ✓ ADK is available")
        
        # Test LLM Extraction Agent
        from company_info_scraper.agents import LLMExtractionAgent
        
        agent = LLMExtractionAgent({'model': 'llama3'})
        adk_agent = agent.as_adk_agent(model='gemini-2.0-flash')
        
        if adk_agent is None:
            print("  ✗ Failed to create ADK agent wrapper")
            return False
        
        print(f"  ✓ Created ADK agent: {adk_agent.name}")
        
        # Test getting tools
        tools = agent.get_adk_tools()
        print(f"  ✓ Agent has {len(tools)} ADK tools")
        
        for tool in tools:
            print(f"    - {tool.name}: {tool.description[:60]}...")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_registration():
    """Test that tools are properly registered."""
    print("\nTesting tool registration...")
    
    try:
        from company_info_scraper.agents import OrchestratorAgent
        
        orchestrator = OrchestratorAgent({'auto_detect': True})
        tools = orchestrator.get_adk_tools()
        
        print(f"  ✓ Orchestrator has {len(tools)} tools")
        
        expected_tools = ['scrape_and_extract', 'batch_scrape_and_extract', 'detect_site_type']
        
        tool_names = [t.name for t in tools]
        for expected in expected_tools:
            if expected in tool_names:
                print(f"  ✓ Tool '{expected}' registered")
            else:
                print(f"  ✗ Tool '{expected}' missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Tool registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_creation():
    """Test creating ADK workflow."""
    print("\nTesting workflow creation...")
    
    try:
        from company_info_scraper.workflows import create_adk_scrape_agent
        from company_info_scraper.agents import is_adk_available
        
        if not is_adk_available():
            print("  ⚠ ADK not available, skipping workflow test")
            return True
        
        agent = create_adk_scrape_agent()
        
        if agent is None:
            print("  ✗ Failed to create ADK workflow agent")
            return False
        
        print(f"  ✓ Created ADK workflow agent: {agent.name}")
        print(f"  ✓ Agent has instruction: {agent.instruction[:80]}...")
        
        # Check tools are attached
        if hasattr(agent, 'tools') and agent.tools:
            print(f"  ✓ Workflow agent has {len(agent.tools)} tools")
        else:
            print("  ⚠ Workflow agent has no tools attached")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Workflow creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_runner_initialization():
    """Test ADK Runner can be initialized."""
    print("\nTesting ADK Runner initialization...")
    
    try:
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from company_info_scraper.workflows import create_adk_scrape_agent
        
        agent = create_adk_scrape_agent()
        
        if agent is None:
            print("  ⚠ No agent available, skipping runner test")
            return True
        
        # Create session service (required for Runner in ADK 1.19.0)
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="TestApp",
            agent=agent, 
            session_service=session_service
        )
        print("  ✓ ADK Runner initialized successfully")
        print(f"  ✓ Runner app: {runner.app_name}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Runner initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all ADK integration tests."""
    print("="*60)
    print("ADK Integration Test Suite (PH5-S2)")
    print("="*60)
    
    tests = [
        ("ADK Imports", test_adk_imports),
        ("Agent Creation", test_agent_creation),
        ("Tool Registration", test_tool_registration),
        ("Workflow Creation", test_workflow_creation),
        ("Runner Initialization", test_runner_initialization),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All ADK integration tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

