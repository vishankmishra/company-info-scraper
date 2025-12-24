"""
ADK Workflow Module for Company Info Scraper (PH5-S3)

This module provides Google ADK workflows for orchestrating the scraping pipeline.
Workflows can be executed via ADK runtime for built-in retry, observability, and 
agent coordination.

Example usage:

    # With ADK installed
    from company_info_scraper.workflows import (
        create_scrape_workflow,
        run_scrape_workflow,
        ScrapeWorkflowConfig
    )
    
    # Create and run workflow
    config = ScrapeWorkflowConfig(auto_detect=True, max_concurrent=5)
    result = run_scrape_workflow(['example.com', 'test.com'], config)
    
    # Or get the workflow agent for custom execution
    workflow = create_scrape_workflow(config)
"""

from .scrape_workflow import (
    ScrapeWorkflowConfig,
    ScrapeWorkflowResult,
    ScrapeWorkflow,
    DomainScrapeResult,
    create_scrape_workflow,
    run_scrape_workflow,
    run_scrape_workflow_async,
    create_adk_scrape_agent,
)

__all__ = [
    'ScrapeWorkflowConfig',
    'ScrapeWorkflowResult',
    'ScrapeWorkflow',
    'DomainScrapeResult',
    'create_scrape_workflow',
    'run_scrape_workflow',
    'run_scrape_workflow_async',
    'create_adk_scrape_agent',
]

