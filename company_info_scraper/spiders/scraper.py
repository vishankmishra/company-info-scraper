"""
Playwright Spider for Dynamic Sites (PH3-S4)

Uses Playwright with persistent browser context for JavaScript rendering.
Browser context is reused across requests to avoid 3-5s startup per page.
"""

import scrapy
from company_info_scraper.items import CompanyInfoScraperItem
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime


class FullPageSpider(scrapy.Spider):
    """Spider for dynamic sites requiring JavaScript rendering.
    
    Uses Playwright with persistent browser context (PH3-S4) for faster
    subsequent page loads. First page takes 3-5s, subsequent pages <2s.
    """
    
    name = "fullpage"
    
    # Use persistent context for browser reuse (configured in settings.py)
    custom_settings = {
        # Ensure we use the persistent context defined in settings
        'PLAYWRIGHT_DEFAULT_CONTEXT_NAME': 'persistent',
    }
    
    def __init__(self, domain=None, *args, **kwargs):
        super(FullPageSpider, self).__init__(*args, **kwargs)
        
        # Accept domain via CLI argument: scrapy crawl fullpage -a domain=example.com
        if domain:
            # Normalize domain input
            domain = domain.strip()
            if not domain.startswith(('http://', 'https://')):
                domain = 'https://' + domain
            
            # Remove trailing slash
            domain = domain.rstrip('/')
            
            self.start_urls = [domain]
            self.base_domain = urlparse(domain).netloc
        else:
            # Default fallback (for backward compatibility)
            self.start_urls = ['https://www.tasconnect.com/']
            self.base_domain = 'www.tasconnect.com'
        
        # Track page count for logging
        self.pages_scraped = 0
        self.logger.info(f"Starting Playwright scraper for domain: {self.start_urls[0]}")

    async def start(self):
        """Async start method (replaces deprecated start_requests)."""
        for url in self.start_urls:
            # Enable Playwright with persistent context for browser reuse
            # Context name "persistent" is defined in settings.py PLAYWRIGHT_CONTEXTS
            yield scrapy.Request(
                url, 
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_context="persistent",  # Reuse browser context
                ),
                callback=self.parse
            )


    async def parse(self, response):
        page = response.meta["playwright_page"]
        depth = response.meta.get('depth', 0)
        
        start_time = datetime.now()
        self.logger.info(f"Parsing URL (depth {depth}): {response.url} - Started at {start_time.strftime('%H:%M:%S')}")
        
        # Resource blocking is already set up via playwright_page_init_callback
        # No need to set it up again here
        
        try:
            # Don't wait for all resources - just get HTML quickly
            # Wait only for network idle or timeout quickly
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)  # Wait for network to be idle
            except:
                # If network idle times out, just get what we have
                await page.wait_for_load_state('domcontentloaded', timeout=3000)  # Fallback: 3 seconds
            
            # 1. Extract visible text (cleaner than raw HTML)
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            # Remove scripts and styles to save tokens for LLM
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            
            text = soup.get_text(separator=' ', strip=True)
        except Exception as e:
            self.logger.warning(f"Error loading page {response.url}: {e}")
            text = ""  # Continue with empty text


        # 2. Yield item for the Pipeline (LLM)
        item = CompanyInfoScraperItem()
        item['url'] = response.url
        item['raw_text'] = text[:5000]  # Reduced to 5000 chars for faster LLM processing
        
        # Yield item FIRST so LLM processing can happen in parallel
        yield item
        
        # Then handle link following AFTER yielding item


        # 3. Follow relevant links (Depth controlled by settings.py)
        # Maximum depth of 1: Start from root (depth 0), follow links one level deep (depth 1)
        # Limit to most important pages to finish quickly
        
        # Only follow links if we're at depth 0 (root page)
        
        if depth == 0:
            # We're on the root page - follow only the most important links
            # Prioritize: about, partners, customers, case studies
            priority_keywords = ['about', 'partner', 'customer', 'case-study', 'case_study']
            secondary_keywords = ['product', 'service', 'solution']
            
            links_followed = 0
            max_links_to_follow = 3  # Limit to 3 links max for very fast crawling (finish in seconds)
            
            # First pass: priority links
            for href in response.css("a::attr(href)").getall():
                if links_followed >= max_links_to_follow:
                    break
                    
                # Skip non-HTTP links
                if not href or not href.startswith(('http://', 'https://', '/')):
                    continue
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = urljoin(response.url, href)
                
                # Only follow links within the same domain
                parsed_href = urlparse(href)
                if parsed_href.netloc and parsed_href.netloc != self.base_domain:
                    continue
                
                href_lower = href.lower()
                
                # Prioritize important pages
                if any(k in href_lower for k in priority_keywords):
                    try:
                        yield response.follow(
                            href, 
                            self.parse, 
                            meta=dict(
                                playwright=True, 
                                playwright_include_page=True,
                                playwright_context="persistent",  # Reuse browser context
                                depth=depth + 1  # Track depth
                            )
                        )
                        links_followed += 1
                        self.logger.debug(f"Following priority link (depth {depth + 1}): {href}")
                    except ValueError as e:
                        self.logger.warning(f"Skipping invalid URL: {href} - {e}")
                        continue
            
            # Second pass: secondary links if we haven't reached the limit
            if links_followed < max_links_to_follow:
                for href in response.css("a::attr(href)").getall():
                    if links_followed >= max_links_to_follow:
                        break
                    
                    if not href or not href.startswith(('http://', 'https://', '/')):
                        continue
                    
                    if href.startswith('/'):
                        href = urljoin(response.url, href)
                    
                    parsed_href = urlparse(href)
                    if parsed_href.netloc and parsed_href.netloc != self.base_domain:
                        continue
                    
                    href_lower = href.lower()
                    
                    # Skip if already followed (priority links)
                    if any(k in href_lower for k in priority_keywords):
                        continue
                    
                    if any(k in href_lower for k in secondary_keywords):
                        try:
                            yield response.follow(
                                href, 
                                self.parse, 
                                meta=dict(
                                    playwright=True, 
                                    playwright_include_page=True,
                                    playwright_context="persistent",  # Reuse browser context
                                    depth=depth + 1
                                )
                            )
                            links_followed += 1
                            self.logger.debug(f"Following secondary link (depth {depth + 1}): {href}")
                        except ValueError as e:
                            self.logger.warning(f"Skipping invalid URL: {href} - {e}")
                            continue
        else:
            # We're already at depth 1 or deeper - don't follow any more links
            self.logger.debug(f"At depth {depth}, not following additional links")
        
        try:
            await page.close()
            self.pages_scraped += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Log with context reuse info
            if self.pages_scraped == 1:
                self.logger.info(
                    f"Completed URL (depth {depth}): {response.url} - "
                    f"Took {elapsed:.1f}s (first page, includes browser startup)"
                )
            else:
                self.logger.info(
                    f"Completed URL (depth {depth}): {response.url} - "
                    f"Took {elapsed:.1f}s (page {self.pages_scraped}, context reused)"
                )
        except Exception as e:
            self.logger.debug(f"Error closing page: {e}")