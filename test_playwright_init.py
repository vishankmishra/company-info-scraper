#!/usr/bin/env python3
"""
Test Playwright initialization with minimal spider.
Same setup as FullPageSpider but minimal logic.
"""

# IMPORTANT: Install asyncio reactor BEFORE any Twisted imports
import sys
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from company_info_scraper.spiders.minimal_test import MinimalTestSpider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_playwright_init():
    """Test if Playwright download handler blocks engine."""
    logger.info("=" * 60)
    logger.info("TEST: Playwright Download Handler Initialization")
    logger.info("=" * 60)
    
    settings = get_project_settings()
    
    # Enable Playwright (same as FullPageSpider)
    settings.set('DOWNLOAD_HANDLERS', {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    })
    settings.set('TWISTED_REACTOR', "twisted.internet.asyncioreactor.AsyncioSelectorReactor")
    settings.set('PLAYWRIGHT_BROWSER_TYPE', "chromium")
    settings.set('PLAYWRIGHT_LAUNCH_OPTIONS', {
        "headless": True,
        "timeout": 15000,
    })
    settings.set('PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT', 10000)
    
    # Use persistent context (same as FullPageSpider)
    settings.set('PLAYWRIGHT_CONTEXTS', {
        "persistent": {
            "viewport": {"width": 1280, "height": 720},
            "ignore_https_errors": True,
            "java_script_enabled": True,
        }
    })
    settings.set('PLAYWRIGHT_DEFAULT_CONTEXT_NAME', 'persistent')
    
    settings.set('FEED_URI', None)
    settings.set('LOG_LEVEL', 'DEBUG')
    settings.set('ROBOTSTXT_OBEY', False)
    
    logger.info("Creating CrawlerProcess with Playwright...")
    process = CrawlerProcess(settings)
    
    logger.info("Crawling minimal_test spider with Playwright...")
    process.crawl(MinimalTestSpider)
    
    logger.info("Starting CrawlerProcess.start()...")
    logger.info("If this hangs, Playwright initialization is blocking the engine")
    logger.info("=" * 60)
    
    try:
        process.start()
        logger.info("=" * 60)
        logger.info("SUCCESS: CrawlerProcess.start() returned")
        logger.info("=" * 60)
        return True
    except Exception as e:
        logger.error(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_playwright_init()
    sys.exit(0 if success else 1)

