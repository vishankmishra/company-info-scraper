#!/usr/bin/env python3
"""
Test FullPageSpider with EXACT same setup as scraping_agent.py
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
from company_info_scraper.spiders.scraper import FullPageSpider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

def test_fullpage_spider():
    """Test FullPageSpider with exact scraping_agent.py setup."""
    logger.info("=" * 60)
    logger.info("TEST: FullPageSpider with scraping_agent.py setup")
    logger.info("=" * 60)
    
    # EXACT same setup as scraping_agent.py._run_crawler()
    settings = get_project_settings()
    
    # Override settings for this run (same as scraping_agent.py)
    settings.set('FEED_URI', None)  # Disable feed export
    settings.set('LOG_LEVEL', 'INFO')
    settings.set('ROBOTSTXT_OBEY', False)
    
    # Use CompanyInfoScraperPipeline (same as scraping_agent.py)
    settings.set('ITEM_PIPELINES', {
        'company_info_scraper.pipelines.CompanyInfoScraperPipeline': 300
    })
    
    logger.info("Creating CrawlerProcess...")
    process = CrawlerProcess(settings)
    
    # Get reference to spider (same pattern as scraping_agent.py)
    spider_ref = [None]
    
    def crawler_started(spider):
        spider_ref[0] = spider
    
    from scrapy import signals
    
    logger.info("Crawling FullPageSpider with domain=magiqai.io...")
    process.crawl(FullPageSpider, domain='magiqai.io')
    
    # Get the crawler that was just added (same as scraping_agent.py)
    if process.crawlers:
        crawler = list(process.crawlers)[-1]
        crawler.signals.connect(crawler_started, signal=signals.spider_opened)
    
    logger.info("Starting CrawlerProcess.start()...")
    logger.info("=" * 60)
    
    try:
        process.start()  # This blocks until crawling is done
        
        logger.info("=" * 60)
        logger.info("SUCCESS: CrawlerProcess.start() returned")
        if spider_ref[0]:
            logger.info(f"Spider reference: {spider_ref[0].name}")
            if hasattr(spider_ref[0], 'collected_items'):
                logger.info(f"Collected items: {len(spider_ref[0].collected_items)}")
        logger.info("=" * 60)
        return True
    except Exception as e:
        logger.error(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_fullpage_spider()
    sys.exit(0 if success else 1)

