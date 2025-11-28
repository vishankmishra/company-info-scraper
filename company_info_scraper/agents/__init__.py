"""
Google ADK Agent Architecture for Company Info Scraper (PH5-S2)

This module provides agent-based orchestration for the scraping workflow.
Agents are ADK-compatible and can be:
1. Used standalone as Python classes
2. Wrapped as ADK FunctionTools
3. Orchestrated via ADK LlmAgent

Example usage:

    # Standalone usage
    from company_info_scraper.agents import OrchestratorAgent
    
    agent = OrchestratorAgent({'auto_detect': True})
    result = agent.execute({'domain': 'example.com'})
    
    # ADK usage (requires google-adk)
    from company_info_scraper.agents import create_adk_workflow
    
    workflow = create_adk_workflow()
    if workflow:
        # Use ADK runtime to execute
        pass
"""

from .base_agent import (
    BaseAgent, 
    AgentToolSpec, 
    adk_tool, 
    is_adk_available
)
from .scraping_agent import ScrapingAgent, AsyncScrapingAgent
from .llm_extraction_agent import LLMExtractionAgent
from .orchestrator_agent import OrchestratorAgent


def create_adk_workflow(
    config: dict = None,
    model: str = "gemini-2.0-flash"
):
    """
    Create a complete ADK workflow for company scraping.
    
    This is a convenience function that:
    1. Creates an OrchestratorAgent with the given config
    2. Wraps it as an ADK LlmAgent with all tools
    
    Args:
        config: Configuration dict for the orchestrator
        model: LLM model for ADK agent reasoning
        
    Returns:
        ADK LlmAgent or None if ADK not available
        
    Example:
        workflow = create_adk_workflow({'auto_detect': True})
        if workflow:
            # Use with ADK runtime
            from google.adk import Runner
            runner = Runner(agent=workflow)
            result = runner.run("Scrape example.com and extract company info")
    """
    orchestrator = OrchestratorAgent(config or {})
    return orchestrator.create_adk_workflow(model=model)


def get_all_tools(config: dict = None):
    """
    Get all ADK tools from all agents.
    
    Useful for creating custom ADK agents with specific tool combinations.
    
    Args:
        config: Configuration dict for agents
        
    Returns:
        List of ADK FunctionTool objects (empty if ADK not available)
    """
    if not is_adk_available():
        return []
    
    config = config or {}
    
    tools = []
    
    # Create agents and collect their tools
    scraping_agent = ScrapingAgent(config.get('scraping', {}))
    llm_agent = LLMExtractionAgent(config.get('llm', {}))
    orchestrator = OrchestratorAgent(config.get('orchestrator', {}))
    
    tools.extend(scraping_agent.get_adk_tools())
    tools.extend(llm_agent.get_adk_tools())
    tools.extend(orchestrator.get_adk_tools())
    
    return tools


__all__ = [
    # Base classes
    'BaseAgent',
    'AgentToolSpec',
    'adk_tool',
    'is_adk_available',
    
    # Agent classes
    'ScrapingAgent',
    'AsyncScrapingAgent', 
    'LLMExtractionAgent',
    'OrchestratorAgent',
    
    # ADK utilities
    'create_adk_workflow',
    'get_all_tools',
]
