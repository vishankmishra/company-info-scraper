"""
Static Site Scraper (PH3-S2)

Fast scraper for static sites using httpx + BeautifulSoup.
No browser overhead - 10x faster than Playwright for static content.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from company_info_scraper.items import CompanyInfoScraperItem

logger = logging.getLogger(__name__)


@dataclass
class ScrapedPage:
    """Result of scraping a single page."""
    url: str
    raw_text: str
    links: List[str] = field(default_factory=list)
    status_code: int = 200
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class StaticScraper:
    """Fast scraper for static sites using httpx + BeautifulSoup.
    
    Usage:
        scraper = StaticScraper()
        results = await scraper.scrape("https://example.com")
        for item in results:
            print(item['url'], item['raw_text'][:100])
    """
    
    # Priority keywords for link following (same as Playwright spider)
    PRIORITY_KEYWORDS = ['about', 'partner', 'customer', 'case-study', 'case_study', 'client']
    SECONDARY_KEYWORDS = ['product', 'service', 'solution']
    
    # Elements to remove for cleaner text extraction
    REMOVE_ELEMENTS = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']
    
    def __init__(
        self,
        timeout: float = 10.0,
        max_text_length: int = 5000,
        max_depth: int = 1,
        max_links: int = 3,
        user_agent: str = "Mozilla/5.0 (compatible; CompanyInfoScraper/1.0)"
    ):
        """Initialize static scraper.
        
        Args:
            timeout: Request timeout in seconds
            max_text_length: Maximum text length to extract per page
            max_depth: Maximum crawl depth (0 = root only, 1 = root + one level)
            max_links: Maximum links to follow per page
            user_agent: User-Agent header
        """
        self.timeout = timeout
        self.max_text_length = max_text_length
        self.max_depth = max_depth
        self.max_links = max_links
        self.user_agent = user_agent
    
    async def scrape(self, url: str) -> List[CompanyInfoScraperItem]:
        """Scrape a website and return items for pipeline processing.
        
        Args:
            url: Starting URL to scrape
            
        Returns:
            List of CompanyInfoScraperItem ready for LLM extraction
        """
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url = url.rstrip('/')
        
        base_domain = urlparse(url).netloc
        visited: Set[str] = set()
        items: List[CompanyInfoScraperItem] = []
        
        logger.info(f"Starting static scrape for domain: {url}")
        total_start = time.time()
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent}
        ) as client:
            # Scrape root page
            root_page = await self._scrape_page(client, url)
            visited.add(url)
            
            if root_page.raw_text:
                item = CompanyInfoScraperItem()
                item['url'] = root_page.url
                item['raw_text'] = root_page.raw_text[:self.max_text_length]
                items.append(item)
            
            # Follow links if depth allows
            if self.max_depth > 0:
                links_to_follow = self._prioritize_links(
                    root_page.links, 
                    base_domain, 
                    visited
                )
                
                for link in links_to_follow[:self.max_links]:
                    if link in visited:
                        continue
                    
                    visited.add(link)
                    page = await self._scrape_page(client, link)
                    
                    if page.raw_text:
                        item = CompanyInfoScraperItem()
                        item['url'] = page.url
                        item['raw_text'] = page.raw_text[:self.max_text_length]
                        items.append(item)
        
        total_elapsed = (time.time() - total_start) * 1000
        logger.info(
            f"Static scrape complete: {len(items)} pages in {total_elapsed:.0f}ms "
            f"(avg {total_elapsed/max(len(items), 1):.0f}ms/page)"
        )
        
        return items
    
    async def scrape_single(self, url: str) -> ScrapedPage:
        """Scrape a single page without following links.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedPage with extracted content
        """
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent}
        ) as client:
            return await self._scrape_page(client, url)
    
    async def _scrape_page(self, client: httpx.AsyncClient, url: str) -> ScrapedPage:
        """Scrape a single page.
        
        Args:
            client: httpx client
            url: URL to scrape
            
        Returns:
            ScrapedPage with content and links
        """
        start = time.time()
        
        try:
            response = await client.get(url)
            elapsed_ms = (time.time() - start) * 1000
            
            if response.status_code != 200:
                logger.warning(f"Non-200 status for {url}: {response.status_code}")
                return ScrapedPage(
                    url=url,
                    raw_text="",
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}",
                    elapsed_ms=elapsed_ms
                )
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract text
            raw_text = self._extract_text(soup)
            
            # Extract links
            links = self._extract_links(soup, url)
            
            logger.debug(f"Scraped {url} in {elapsed_ms:.0f}ms ({len(raw_text)} chars)")
            
            return ScrapedPage(
                url=str(response.url),  # Use final URL after redirects
                raw_text=raw_text,
                links=links,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms
            )
            
        except httpx.TimeoutException:
            elapsed_ms = (time.time() - start) * 1000
            logger.warning(f"Timeout scraping {url}")
            return ScrapedPage(
                url=url,
                raw_text="",
                error="Timeout",
                elapsed_ms=elapsed_ms
            )
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"Error scraping {url}: {e}")
            return ScrapedPage(
                url=url,
                raw_text="",
                error=str(e)[:100],
                elapsed_ms=elapsed_ms
            )
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from HTML.
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            Cleaned text content
        """
        # Remove unwanted elements
        for element in soup(self.REMOVE_ELEMENTS):
            element.extract()
        
        # Get text with space separator
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract links from HTML.
        
        Args:
            soup: BeautifulSoup parsed HTML
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip non-HTTP links
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Convert to absolute URL
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)
            
            # Clean URL (remove fragments)
            href = href.split('#')[0]
            
            if href and href not in links:
                links.append(href)
        
        return links
    
    def _prioritize_links(
        self, 
        links: List[str], 
        base_domain: str,
        visited: Set[str]
    ) -> List[str]:
        """Prioritize links for crawling.
        
        Args:
            links: All extracted links
            base_domain: Base domain to filter by
            visited: Already visited URLs
            
        Returns:
            Prioritized list of links to follow
        """
        priority_links = []
        secondary_links = []
        
        for link in links:
            # Skip already visited
            if link in visited:
                continue
            
            # Only follow same-domain links
            parsed = urlparse(link)
            if parsed.netloc and parsed.netloc != base_domain:
                continue
            
            link_lower = link.lower()
            
            # Categorize by priority
            if any(kw in link_lower for kw in self.PRIORITY_KEYWORDS):
                priority_links.append(link)
            elif any(kw in link_lower for kw in self.SECONDARY_KEYWORDS):
                secondary_links.append(link)
        
        # Return priority links first, then secondary
        return priority_links + secondary_links
    
    def scrape_sync(self, url: str) -> List[CompanyInfoScraperItem]:
        """Synchronous wrapper for scrape().
        
        Args:
            url: Starting URL
            
        Returns:
            List of scraped items
        """
        import asyncio
        return asyncio.run(self.scrape(url))


# Convenience function for quick scraping
async def scrape_static_site(url: str, max_depth: int = 1) -> List[CompanyInfoScraperItem]:
    """Quick static site scraping.
    
    Args:
        url: URL to scrape
        max_depth: Crawl depth
        
    Returns:
        List of scraped items
    """
    scraper = StaticScraper(max_depth=max_depth)
    return await scraper.scrape(url)

