"""
Minimal test spider to verify Scrapy engine lifecycle.
No Playwright, no complex logic - just verify parse() is called.
"""

import scrapy


class MinimalTestSpider(scrapy.Spider):
    """Minimal spider to test if Scrapy engine calls parse()."""
    
    name = "minimal_test"
    start_urls = ["https://example.com"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.info("MinimalTestSpider.__init__() called")
        self.logger.info(f"start_urls = {self.start_urls}")
    
    def start_requests(self):
        """Generate initial requests."""
        self.logger.info("MinimalTestSpider.start_requests() CALLED")
        self.logger.info(f"start_urls = {self.start_urls}")
        for url in self.start_urls:
            self.logger.info(f"Yielding request for: {url}")
            yield scrapy.Request(url, callback=self.parse, errback=self.errback)
    
    def parse(self, response):
        """Parse callback - should be called by engine."""
        self.logger.info(f"MinimalTestSpider.parse() CALLED for {response.url}")
        self.logger.info(f"Response status: {response.status}")
        return {"url": response.url, "status": response.status, "test": "SUCCESS"}
    
    def errback(self, failure):
        """Error callback."""
        self.logger.error(f"MinimalTestSpider.errback() CALLED: {failure}")

