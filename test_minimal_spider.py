#!/usr/bin/env python3
"""
Test script to verify Scrapy engine lifecycle with minimal spider.
Uses the SAME runner setup as main.py / scraping_agent.py
"""

# IMPORTANT: Install asyncio reactor BEFORE any Twisted imports
# This matches main.py setup
import sys
if 'twisted.internet.reactor' not in sys.modules:
    import asyncio
    from twisted.internet import asyncioreactor
    asyncioreactor.install()

import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from company_info_scraper.spiders.minimal_test import MinimalTestSpider

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_minimal_spider():
    """Test if Scrapy engine calls parse() with minimal spider."""
    logger.info("=" * 60)
    logger.info("TEST: Minimal Spider Engine Lifecycle")
    logger.info("=" * 60)
    
    # Get project settings (same as scraping_agent.py)
    settings = get_project_settings()
    
    # Override settings for test
    settings.set('FEED_URI', None)  # Disable feed export
    settings.set('LOG_LEVEL', 'DEBUG')  # More verbose
    settings.set('ROBOTSTXT_OBEY', False)
    
    # Disable Playwright download handlers for this test
    settings.set('DOWNLOAD_HANDLERS', {
        'http': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
        'https': 'scrapy.core.downloader.handlers.http.HTTPDownloadHandler',
    })
    
    logger.info("Creating CrawlerProcess...")
    process = CrawlerProcess(settings)
    
    # Track if callbacks were called
    callbacks_called = {
        'start_requests': False,
        'parse': False,
        'errback': False
    }
    
    def check_start_requests(spider):
        """Signal handler to verify start_requests was called."""
        logger.info(f"Spider opened: {spider.name}")
        # We can't directly check if start_requests was called here,
        # but we can check logs after
    
    from scrapy import signals
    
    logger.info("Crawling minimal_test spider...")
    process.crawl(MinimalTestSpider)
    
    # Connect signal
    if process.crawlers:
        crawler = list(process.crawlers)[-1]
        crawler.signals.connect(check_start_requests, signal=signals.spider_opened)
    
    logger.info("Starting CrawlerProcess.start()...")
    logger.info("If parse() is called, you should see 'MinimalTestSpider.parse() CALLED'")
    logger.info("=" * 60)
    
    try:
        process.start()  # This blocks until crawling is done
        logger.info("=" * 60)
        logger.info("CrawlerProcess.start() returned")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error during crawl: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = test_minimal_spider()
    sys.exit(0 if success else 1)

