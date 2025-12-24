# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

# PH2-S4: Consolidated to use LLMExtractionService as single source of truth

from itemadapter import ItemAdapter

from company_info_scraper.services.extraction_queue import get_global_queue, reset_global_queue
from company_info_scraper.services.llm_service import LLMExtractionService


class CompanyInfoScraperPipeline:
    """Pass-through pipeline that collects items in spider for in-memory access."""
    
    def process_item(self, item, spider):
        # Collect item in spider's memory for direct access (Phase 2 fix)
        if hasattr(spider, 'collected_items'):
            from itemadapter import ItemAdapter
            spider.collected_items.append(dict(ItemAdapter(item)))
        return item


class QueueingPipeline:
    """Pipeline that queues items for deferred LLM processing (PH2-S2).
    
    Use this pipeline for fast scraping. Items are saved to a queue
    and can be processed later with LLM extraction.
    
    To use: Set ITEM_PIPELINES in settings.py to use QueueingPipeline
    instead of LLMExtractionPipeline.
    """
    
    def __init__(self):
        self.queue = None
        self.queue_file = None
    
    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.queue_file = crawler.settings.get('EXTRACTION_QUEUE_FILE', None)
        return pipeline
    
    def open_spider(self, spider):
        """Initialize queue when spider opens."""
        reset_global_queue()  # Start fresh for each crawl
        self.queue = get_global_queue()
        spider.logger.info("QueueingPipeline initialized - items will be queued for later LLM processing")
    
    def close_spider(self, spider):
        """Save queue when spider closes."""
        if self.queue and len(self.queue) > 0:
            save_path = self.queue.save(self.queue_file)
            spider.logger.info(f"Queued {len(self.queue)} items for LLM processing. Queue saved to: {save_path}")
    
    def process_item(self, item, spider):
        """Queue item for later processing instead of inline LLM extraction."""
        adapter = ItemAdapter(item)
        url = adapter.get('url', 'unknown')
        raw_text = adapter.get('raw_text', '')
        
        if raw_text:
            self.queue.add(url, raw_text)
            spider.logger.debug(f"Queued: {url}")
        
        # Set placeholder values (actual extraction happens later)
        adapter['products'] = "QUEUED"
        adapter['services'] = "QUEUED"
        adapter['customers'] = "QUEUED"
        adapter['partnerships'] = "QUEUED"
        adapter['case_studies'] = "QUEUED"
        adapter['extraction_status'] = "queued"
        
        return item


class LLMExtractionPipeline:
    """
    Pipeline that performs inline LLM extraction using LLMExtractionService.
    updated to be async to prevent event loop deadlocks.
    """
    
    def __init__(self):
        self.service = None
    
    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        pipeline.service = LLMExtractionService(
            model=crawler.settings.get('OLLAMA_MODEL', 'llama3'),
            timeout=crawler.settings.get('OLLAMA_TIMEOUT', 90),
            max_retries=crawler.settings.get('OLLAMA_MAX_RETRIES', 3),
            max_text_length=crawler.settings.get('MAX_TEXT_LENGTH', 5000)
        )
        return pipeline
    
    # CHANGED: Added 'async' keyword
    async def process_item(self, item, spider):
        """Extract data from item using LLMExtractionService asynchronously."""
        adapter = ItemAdapter(item)
        url = adapter.get('url', 'unknown')
        text_content = adapter.get('raw_text', '')
        
        # CHANGED: Await the async method directly. 
        # Do NOT use extract_sync().
        result = await self.service.extract(text_content, url=url)
        
        # Apply results to item
        adapter['products'] = result.products
        adapter['services'] = result.services
        adapter['customers'] = result.customers
        adapter['partnerships'] = result.partnerships
        adapter['case_studies'] = result.case_studies
        adapter['extraction_status'] = result.status
        
        if result.status == 'success':
            spider.logger.info(f"Successfully extracted data for {url}")
        else:
            spider.logger.warning(f"Extraction failure for {url}: {result.error or 'all fields are N/A'}")
        
        return item
