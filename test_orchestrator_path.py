#!/usr/bin/env python3
"""
Test FullPageSpider through OrchestratorAgent path (same as main.py)
"""

# IMPORTANT: Install asyncio reactor BEFORE any Twisted imports
import sys
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

import logging
from company_info_scraper.agents import OrchestratorAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_orchestrator_path():
    """Test through OrchestratorAgent.execute() - same as main.py"""
    logger.info("=" * 60)
    logger.info("TEST: FullPageSpider through OrchestratorAgent.execute()")
    logger.info("=" * 60)
    
    # Same config as main.py
    agent_config = {
        'project_root': '.',
        'output_file': 'test_output.csv',
        'ollama_model': 'llama3',
        'ollama_timeout': 90,
        'max_text_length': 5000,
        'max_concurrent': 1,
        'auto_detect': False,
        'force_scraper': 'dynamic',
    }
    
    logger.info("Creating OrchestratorAgent...")
    orchestrator = OrchestratorAgent(agent_config)
    
    logger.info("Calling orchestrator.execute() with domain=magiqai.io...")
    logger.info("=" * 60)
    
    try:
        result = orchestrator.execute({
            'domain': 'magiqai.io',
            'scraper_type': 'dynamic'
        })
        
        logger.info("=" * 60)
        logger.info(f"SUCCESS: orchestrator.execute() returned")
        logger.info(f"Result success: {result.get('success')}")
        logger.info(f"Result domain: {result.get('domain')}")
        logger.info(f"Scraping success: {result.get('scraping_result', {}).get('success')}")
        logger.info("=" * 60)
        return result.get('success', False)
    except Exception as e:
        logger.error(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_orchestrator_path()
    sys.exit(0 if success else 1)

