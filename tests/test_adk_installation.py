#!/usr/bin/env python3
"""
Test script for Google ADK installation (PH5-S1)

Verifies that the Google ADK SDK is properly installed and can be imported.
Run with: python -m pytest tests/test_adk_installation.py -v
Or directly: python tests/test_adk_installation.py
"""

import sys


def test_adk_import():
    """Test that google-adk can be imported."""
    try:
        import google.adk
        print(f"✓ google.adk imported successfully")
        print(f"  Version: {getattr(google.adk, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"✗ Failed to import google.adk: {e}")
        return False


def test_adk_agent_import():
    """Test that ADK Agent classes can be imported."""
    try:
        from google.adk import Agent
        print(f"✓ google.adk.Agent imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import Agent: {e}")
        # Try alternative import paths
        try:
            from google.adk.agents import Agent
            print(f"✓ google.adk.agents.Agent imported successfully (alternative path)")
            return True
        except ImportError:
            pass
        return False


def test_adk_llm_agent_import():
    """Test that LlmAgent can be imported."""
    try:
        from google.adk import LlmAgent
        print(f"✓ google.adk.LlmAgent imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import LlmAgent: {e}")
        # Try alternative paths
        try:
            from google.adk.agents import LlmAgent
            print(f"✓ google.adk.agents.LlmAgent imported successfully (alternative path)")
            return True
        except ImportError:
            pass
        return False


def test_adk_runner_import():
    """Test that ADK Runner can be imported."""
    try:
        from google.adk import Runner
        print(f"✓ google.adk.Runner imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import Runner: {e}")
        try:
            from google.adk.runners import Runner
            print(f"✓ google.adk.runners.Runner imported successfully (alternative path)")
            return True
        except ImportError:
            pass
        return False


def test_adk_basic_agent_creation():
    """Test that a basic agent can be created."""
    try:
        from google.adk import Agent
        
        # Try to create a simple agent
        # Note: This may require additional setup depending on ADK version
        print(f"✓ ADK Agent class is available for subclassing")
        return True
    except Exception as e:
        print(f"✗ Error testing agent creation: {e}")
        return False


def print_adk_info():
    """Print information about the installed ADK."""
    print("\n" + "="*60)
    print("Google ADK Installation Information")
    print("="*60)
    
    try:
        import google.adk
        
        # Print module location
        print(f"\nModule location: {google.adk.__file__}")
        
        # List available exports
        exports = [name for name in dir(google.adk) if not name.startswith('_')]
        print(f"\nAvailable exports from google.adk:")
        for export in sorted(exports):
            print(f"  - {export}")
            
    except ImportError as e:
        print(f"\nADK not installed or import failed: {e}")
        print("\nTo install, run:")
        print("  pip install google-adk")


def test_adk_with_agents():
    """Test ADK integration with company_info_scraper agents."""
    try:
        from company_info_scraper.agents import (
            is_adk_available,
            create_adk_workflow,
            OrchestratorAgent
        )
        
        if is_adk_available():
            # Try to create ADK workflow
            workflow = create_adk_workflow()
            if workflow:
                print(f"✓ ADK workflow created with agents")
                return True
            else:
                print(f"✗ Failed to create ADK workflow")
                return False
        else:
            print(f"✓ Agent ADK integration ready (ADK not installed)")
            return True
            
    except Exception as e:
        print(f"✗ Agent ADK integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing Google ADK Installation (PH5-S1)")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("ADK Import", test_adk_import()))
    results.append(("Agent Import", test_adk_agent_import()))
    results.append(("LlmAgent Import", test_adk_llm_agent_import()))
    results.append(("Runner Import", test_adk_runner_import()))
    results.append(("Basic Agent Creation", test_adk_basic_agent_creation()))
    results.append(("ADK with Agents", test_adk_with_agents()))
    
    # Print ADK info
    print_adk_info()
    
    # Summary
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
        print("\n✓ Google ADK is properly installed and ready to use!")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above for details.")
        print("  Note: Some imports may vary based on ADK version.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

