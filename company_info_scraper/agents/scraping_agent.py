"""
Scraping Agent - Handles web scraping using Scrapy or Static Scraper (PH3-S3, PH5-S2)

Supports dual-path scraping:
- Static sites: Uses httpx + BeautifulSoup (fast)
- Dynamic sites: Uses Playwright via Scrapy (handles JS)

Updated for Google ADK compatibility.
"""

import asyncio
import csv
import os
from typing import Dict, Any, Optional, List

from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor, defer
from twisted.internet.error import ReactorNotRunning

from .base_agent import BaseAgent, adk_tool


class ScrapingAgent(BaseAgent):
    """
    Agent responsible for web scraping with dual-path support.
    
    Supports both static (httpx/BeautifulSoup) and dynamic (Playwright) scraping.
    Use 'scraper_type' in input_data to force a specific scraper, or let the
    orchestrator decide based on site detection.
    
    ADK Integration (PH5-S2):
    - Exposes scrape_website and scrape_static tools
    - Can be wrapped as ADK LlmAgent
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("ScrapingAgent", config)
        self.project_root = self.config.get('project_root', os.getcwd())
        self.output_file = self.config.get('output_file', 'output_data.csv')
        self.use_queue = self.config.get('use_queue', False)  # Use QueueingPipeline
        self._collected_items: List[Dict] = []
        
        # Register ADK tools (PH5-S2)
        self._register_adk_tools()
    
    def _register_adk_tools(self):
        """Register methods as ADK tools."""
        self.register_tool(
            name="scrape_website",
            description=(
                "Scrape a website domain to extract text content. "
                "Automatically chooses between static (fast) and dynamic (JS-enabled) scraping. "
                "Returns raw text content from the website pages."
            ),
            func=self._scrape_tool,
            parameters={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain or URL to scrape (e.g., 'example.com' or 'https://example.com')"
                    },
                    "scraper_type": {
                        "type": "string",
                        "enum": ["static", "dynamic", "auto"],
                        "description": "Type of scraper to use. 'static' for simple sites, 'dynamic' for JS-heavy sites, 'auto' for automatic detection"
                    }
                },
                "required": ["domain"]
            }
        )
        
        self.register_tool(
            name="scrape_static_site",
            description=(
                "Scrape a static website using fast HTTP requests (no browser). "
                "Best for sites that don't require JavaScript rendering."
            ),
            func=self._scrape_static_tool,
            parameters={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain or URL to scrape"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum number of pages to scrape (default: 4)"
                    }
                },
                "required": ["domain"]
            }
        )
    
    def _scrape_tool(self, domain: str, scraper_type: str = "dynamic") -> Dict[str, Any]:
        """ADK tool wrapper for scraping."""
        return self.execute({'domain': domain, 'scraper_type': scraper_type})
    
    def _scrape_static_tool(self, domain: str, max_pages: int = 4) -> Dict[str, Any]:
        """ADK tool wrapper for static scraping."""
        return self.execute({'domain': domain, 'scraper_type': 'static'})
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scraping for a given domain.
        
        Args:
            input_data: Must contain 'domain' key.
                       Optional 'scraper_type': 'static' or 'dynamic' (default: 'dynamic')
            
        Returns:
            Dictionary with 'success', 'domain', 'output_file', 'raw_data', and 'scraper_type'
        """
        if not self.validate_input(input_data, ['domain']):
            return {
                'success': False,
                'error': 'Missing required field: domain'
            }
        
        domain = input_data['domain']
        scraper_type = input_data.get('scraper_type', 'dynamic')
        
        self.logger.info(f"Starting {scraper_type} scraping for domain: {domain}")
        
        try:
            if scraper_type == 'static':
                result = asyncio.run(self._run_static_scraper(domain))
            else:
                result = self._run_crawler(domain)
            
            result['scraper_type'] = scraper_type
            return result
        except Exception as e:
            self.logger.error(f"Scraping error for domain {domain}: {e}")
            return {
                'success': False,
                'error': str(e),
                'domain': domain,
                'scraper_type': scraper_type
            }
    
    async def execute_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute scraping asynchronously.
        
        Args:
            input_data: Must contain 'domain' key.
                       Optional 'scraper_type': 'static' or 'dynamic'
            
        Returns:
            Dictionary with 'success', 'domain', 'output_file', and 'raw_data'
        """
        if not self.validate_input(input_data, ['domain']):
            return {
                'success': False,
                'error': 'Missing required field: domain'
            }
        
        domain = input_data['domain']
        scraper_type = input_data.get('scraper_type', 'dynamic')
        
        self.logger.info(f"Starting async {scraper_type} scraping for domain: {domain}")
        
        try:
            if scraper_type == 'static':
                result = await self._run_static_scraper(domain)
            else:
                result = await asyncio.to_thread(self._run_crawler, domain)
            
            result['scraper_type'] = scraper_type
            return result
        except Exception as e:
            self.logger.error(f"Scraping error for domain {domain}: {e}")
            return {
                'success': False,
                'error': str(e),
                'domain': domain,
                'scraper_type': scraper_type
            }
    
    async def _run_static_scraper(self, domain: str) -> Dict[str, Any]:
        """Run static scraper using httpx + BeautifulSoup."""
        from company_info_scraper.spiders.static_scraper import StaticScraper
        
        self.logger.info(f"Using static scraper (httpx + BeautifulSoup) for {domain}")
        
        scraper = StaticScraper(
            max_depth=1,
            max_links=3,
            max_text_length=5000
        )
        
        items = await scraper.scrape(domain)
        
        # Convert items to raw_data format
        raw_data = []
        for item in items:
            raw_data.append({
                'url': item.get('url', ''),
                'raw_text': item.get('raw_text', '')
            })
        
        self.log_result({
            'domain': domain,
            'records': len(raw_data),
            'scraper': 'static'
        }, success=True)
        
        return {
            'success': True,
            'domain': domain,
            'raw_data': raw_data,
            'records_count': len(raw_data)
        }
    
    def _run_crawler(self, domain: str) -> Dict[str, Any]:
        """Run Scrapy crawler in-process using CrawlerRunner."""
        from company_info_scraper.spiders.scraper import FullPageSpider
        
        # Get project settings
        settings = get_project_settings()
        
        # Override settings for this run
        settings.set('FEED_URI', self.output_file)
        settings.set('FEED_FORMAT', 'csv')
        settings.set('LOG_LEVEL', 'INFO')
        
        # Use QueueingPipeline if configured (fast mode)
        if self.use_queue:
            settings.set('ITEM_PIPELINES', {
                'company_info_scraper.pipelines.QueueingPipeline': 300
            })
            self.logger.info("Using QueueingPipeline for fast scraping")
        
        # Clear any existing output
        self._collected_items.clear()
        
        # Track success/failure
        crawl_success = [False]  # Use list to allow mutation in nested function
        crawl_error = [None]
        
        @defer.inlineCallbacks
        def run_spider():
            try:
                runner = CrawlerRunner(settings)
                yield runner.crawl(FullPageSpider, domain=domain)
                crawl_success[0] = True
            except Exception as e:
                crawl_error[0] = str(e)
                self.logger.error(f"Crawler error: {e}")
            finally:
                # Stop reactor when done
                try:
                    reactor.stop()
                except ReactorNotRunning:
                    pass
        
        # Check if reactor is already running
        if reactor.running:
            # If reactor is running, we need a different approach
            self.logger.warning("Reactor already running - using deferred execution")
            d = run_spider()
            # This case is complex; for now, raise an error
            raise RuntimeError(
                "Cannot run crawler when reactor is already running. "
                "Use execute_async() instead or ensure no other Twisted code is running."
            )
        else:
            # Start reactor and run spider
            reactor.callWhenRunning(run_spider)
            reactor.run(installSignalHandlers=False)
        
        if not crawl_success[0]:
            return {
                'success': False,
                'error': crawl_error[0] or 'Crawler failed',
                'domain': domain
            }
        
        # Read scraped data
        raw_data = self._read_output_file()
        
        self.log_result({
            'domain': domain,
            'output_file': self.output_file,
            'records': len(raw_data) if raw_data else 0
        }, success=True)
        
        return {
            'success': True,
            'domain': domain,
            'output_file': self.output_file,
            'raw_data': raw_data,
            'records_count': len(raw_data) if raw_data else 0
        }
    
    def _read_output_file(self) -> list:
        """Read CSV output file and return as list of dicts."""
        if not os.path.exists(self.output_file):
            self.logger.warning(f"Output file not found: {self.output_file}")
            return []
        
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            self.logger.error(f"Error reading output file: {e}")
            return []
    
    def _get_execute_description(self) -> str:
        """Description for ADK execute tool."""
        return (
            "Scrape a website domain to extract text content. Supports both static "
            "(fast HTTP) and dynamic (Playwright browser) scraping modes."
        )
    
    def _get_agent_instruction(self) -> str:
        """Instruction for ADK LlmAgent wrapper."""
        return """You are the Scraping Agent.

Your role is to scrape websites and extract their text content.
You support two scraping modes:
- Static: Fast HTTP-based scraping for simple websites
- Dynamic: Browser-based scraping for JavaScript-heavy sites

When asked to scrape a website:
1. Use scrape_website tool with the domain
2. For known static sites, specify scraper_type='static' for speed
3. For complex sites with JS, use scraper_type='dynamic'

Return the raw text content extracted from the pages."""


class AsyncScrapingAgent(BaseAgent):
    """
    Async-native scraping agent using CrawlerRunner with asyncio.
    
    This agent is designed for use in async contexts where the Twisted
    reactor may conflict with asyncio. It runs crawls in a controlled manner.
    
    ADK Integration (PH5-S2):
    - Inherits ADK compatibility from BaseAgent
    - Optimized for async workflows
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("AsyncScrapingAgent", config)
        self.output_file = self.config.get('output_file', 'output_data.csv')
        self.use_queue = self.config.get('use_queue', True)  # Default to queue mode
        
        # Register ADK tools
        self._register_adk_tools()
    
    def _register_adk_tools(self):
        """Register async scraping tools."""
        self.register_tool(
            name="async_scrape",
            description="Asynchronously scrape a website domain",
            func=lambda domain: self.execute({'domain': domain}),
            parameters={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain to scrape"}
                },
                "required": ["domain"]
            }
        )
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous execute - runs async version in new event loop."""
        return asyncio.run(self.execute_async(input_data))
    
    async def execute_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scraping asynchronously."""
        if not self.validate_input(input_data, ['domain']):
            return {
                'success': False,
                'error': 'Missing required field: domain'
            }
        
        domain = input_data['domain']
        self.logger.info(f"Starting async scraping for domain: {domain}")
        
        try:
            # Run in thread pool to isolate Twisted reactor
            result = await asyncio.to_thread(
                self._run_in_thread, domain
            )
            return result
        except Exception as e:
            self.logger.error(f"Async scraping error: {e}")
            return {
                'success': False,
                'error': str(e),
                'domain': domain
            }
    
    def _run_in_thread(self, domain: str) -> Dict[str, Any]:
        """Run crawler in isolated thread with its own reactor."""
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
        from company_info_scraper.spiders.scraper import FullPageSpider
        
        settings = get_project_settings()
        settings.set('FEED_URI', self.output_file)
        settings.set('FEED_FORMAT', 'csv')
        settings.set('LOG_LEVEL', 'INFO')
        
        if self.use_queue:
            settings.set('ITEM_PIPELINES', {
                'company_info_scraper.pipelines.QueueingPipeline': 300
            })
        
        try:
            # CrawlerProcess handles reactor lifecycle
            process = CrawlerProcess(settings)
            process.crawl(FullPageSpider, domain=domain)
            process.start()  # Blocks until crawl is done
            
            # Read results
            raw_data = self._read_output()
            
            return {
                'success': True,
                'domain': domain,
                'output_file': self.output_file,
                'raw_data': raw_data,
                'records_count': len(raw_data)
            }
        except Exception as e:
            self.logger.error(f"Crawler process error: {e}")
            return {
                'success': False,
                'error': str(e),
                'domain': domain
            }
    
    def _read_output(self) -> list:
        """Read CSV output file."""
        if not os.path.exists(self.output_file):
            return []
        
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                return list(csv.DictReader(f))
        except Exception as e:
            self.logger.error(f"Error reading output: {e}")
            return []
    
    def _get_agent_instruction(self) -> str:
        """Instruction for ADK LlmAgent wrapper."""
        return """You are the Async Scraping Agent.

Your role is to scrape websites asynchronously for high-throughput scenarios.
Use async_scrape tool to scrape domains without blocking other operations."""
