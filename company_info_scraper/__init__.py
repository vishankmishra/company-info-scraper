"""
Company Info Scraper - Web scraping with LLM-based data extraction

This package provides tools for scraping company websites and extracting
structured business information using LLMs (via Ollama).

## Quick Start

```python
from company_info_scraper.workflows import run_scrape_workflow, ScrapeWorkflowConfig

# Simple usage
result = run_scrape_workflow('example.com')

# With configuration
config = ScrapeWorkflowConfig(
    auto_detect=True,
    max_concurrent=5,
    output_format='csv'
)
result = run_scrape_workflow(['example.com', 'test.com'], config)
```

## Components

- **workflows**: High-level workflow for end-to-end scraping
- **agents**: ADK-compatible agents for scraping, extraction, orchestration
- **services**: Core services (LLM, site detection, batch processing)
- **spiders**: Scrapy spiders for static and dynamic content
"""

__version__ = '1.0.0'

# Expose main workflow functions at package level
from .workflows import (
    ScrapeWorkflowConfig,
    ScrapeWorkflowResult,
    ScrapeWorkflow,
    create_scrape_workflow,
    run_scrape_workflow,
    run_scrape_workflow_async,
)

# Expose agents
from .agents import (
    OrchestratorAgent,
    ScrapingAgent,
    LLMExtractionAgent,
    is_adk_available,
    create_adk_workflow,
)

__all__ = [
    # Version
    '__version__',
    
    # Workflows
    'ScrapeWorkflowConfig',
    'ScrapeWorkflowResult', 
    'ScrapeWorkflow',
    'create_scrape_workflow',
    'run_scrape_workflow',
    'run_scrape_workflow_async',
    
    # Agents
    'OrchestratorAgent',
    'ScrapingAgent',
    'LLMExtractionAgent',
    'is_adk_available',
    'create_adk_workflow',
]

