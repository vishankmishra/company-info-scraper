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
        
        # #region agent log
        import json
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:__init__","message":"Spider __init__ called","data":{"domain":domain},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H7"}) + '\n')
        # #endregion
        
        # Accept domain via CLI argument: scrapy crawl fullpage -a domain=example.com
        if not domain:
            raise ValueError("Domain is required. Please provide a domain parameter.")
        
        # Normalize domain input
        domain = domain.strip()
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain
        
        # Remove trailing slash
        domain = domain.rstrip('/')
        
        self.start_urls = [domain]
        self.base_domain = urlparse(domain).netloc
        
        # Track page count for logging
        self.pages_scraped = 0
        # Phase 2 Fix: Collect items in memory for direct access (avoid CSV read/write)
        self.collected_items = []
        self.logger.info(f"Starting Playwright scraper for domain: {self.start_urls[0]}")

        # #region agent log
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:__init__:end","message":"Spider __init__ complete","data":{"start_urls":self.start_urls},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H7"}) + '\n')
        # #endregion

    def start_requests(self):
        """Generate initial requests with Playwright enabled."""
        # #region agent log
        import json
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:start_requests:entry","message":"start_requests called","data":{"start_urls":self.start_urls},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H1"}) + '\n')
        # #endregion
        
        self.logger.info(f"start_requests called with start_urls: {self.start_urls}")
        for url in self.start_urls:
            self.logger.info(f"Generating request for: {url}")
            # Enable Playwright with persistent context for browser reuse
            # Context name "persistent" is defined in settings.py PLAYWRIGHT_CONTEXTS
            request = scrapy.Request(
                url, 
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_context="persistent",  # Reuse browser context
                ),
                callback=self.parse,
                errback=self.errback
            )
            self.logger.info(f"Yielding request: {request}")
            
            # #region agent log
            with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location":"scraper.py:start_requests:yield","message":"About to yield request","data":{"url":url,"meta_keys":list(request.meta.keys())},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H2"}) + '\n')
            # #endregion
            
            yield request
    
    def errback(self, failure):
        """Handle request errors."""
        # #region agent log
        import json
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:errback","message":"Request error occurred","data":{"failure_type":str(type(failure.value)),"failure_str":str(failure.value)[:200]},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H5"}) + '\n')
        # #endregion
        
        self.logger.error(f"Request failed: {failure}")
        self.logger.error(f"Failure value: {failure.value}")
        self.logger.error(f"Failure traceback: {failure.getTraceback()}")


    async def parse(self, response):
        # #region agent log
        import json
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:parse:entry","message":"parse callback invoked","data":{"url":str(response.url),"status":response.status},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H2"}) + '\n')
        # #endregion
        
        # Handle non-200 status codes
        if response.status != 200:
            self.logger.error(
                f"Failed to fetch {response.url}: HTTP {response.status}. "
                f"{'Site may be blocking automated access.' if response.status == 403 else ''}"
            )
            # Yield an empty item with error info
            item = CompanyInfoScraperItem()
            item['url'] = response.url
            item['raw_text'] = f"ERROR: HTTP {response.status} - Unable to access page"
            yield item
            return
        
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


        # 3. Follow relevant links (Phase 4: Smart Link Prioritization)
        # Maximum depth of 1: Start from root (depth 0), follow links one level deep (depth 1)
        # Prioritize high-value pages: customers, partners, case-studies
        
        # Only follow links if we're at depth 0 (root page)
        if depth == 0:
            # Phase 4: Priority-based link selection
            # P1 (CRITICAL): customers, clients, case-studies, success-stories, testimonials
            # P2 (HIGH): partners, partnerships, integrations, alliances, ecosystem
            # P3 (MEDIUM): about, about-us, company, who-we-are
            # P4 (MEDIUM): products, services, solutions, offerings
            # P5 (LOW): news, blog, resources
            # SKIP: careers, jobs, legal, privacy, terms, login, signup
            
            p1_patterns = ['/customers', '/clients', '/case-studies', '/case_studies', 
                          '/success-stories', '/success_stories', '/testimonials', 
                          '/our-customers', '/our-clients']
            p2_patterns = ['/partners', '/partnerships', '/integrations', '/alliances', 
                          '/ecosystem', '/technology-partners']
            p3_patterns = ['/about', '/about-us', '/about_us', '/company', '/who-we-are', 
                          '/who_we_are', '/team']
            p4_patterns = ['/products', '/services', '/solutions', '/offerings']
            p5_patterns = ['/news', '/blog', '/resources', '/press']
            skip_patterns = ['/careers', '/jobs', '/legal', '/privacy', '/terms', 
                            '/login', '/signup', '/sign-up', '/register', '/docs', 
                            '/documentation', '/api', '/contact']
            
            # Extract all links and classify them
            all_links = []
            nav_links = set()  # Track navigation links (more valuable)
            
            # First, identify navigation links (in nav, header, or nav class)
            nav_selectors = [
                'nav a::attr(href)',
                'header nav a::attr(href)',
                '.nav a::attr(href)',
                '.navigation a::attr(href)',
                '[role="navigation"] a::attr(href)'
            ]
            for selector in nav_selectors:
                for href in response.css(selector).getall():
                    if href:
                        nav_links.add(href)
            
            # Extract all links from page
            all_raw_hrefs = response.css("a::attr(href)").getall()
            self.logger.debug(f"[Phase 4] Found {len(all_raw_hrefs)} raw hrefs from CSS selector")
            
            for href in all_raw_hrefs:
                if not href:
                    continue
                # Skip non-HTTP links (javascript:, mailto:, tel:, #anchors, etc.)
                href_clean = href.strip()
                if not href_clean.startswith(('http://', 'https://', '/')):
                    self.logger.debug(f"[Phase 4] Skipping non-HTTP link: {href_clean[:50]}")
                    continue
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    absolute_href = urljoin(response.url, href)
                else:
                    absolute_href = href
                
                # Only follow links within the same domain
                parsed_href = urlparse(absolute_href)
                if parsed_href.netloc and parsed_href.netloc != self.base_domain:
                    continue
                
                # Skip fragments and query params for matching
                path = parsed_href.path.lower()
                
                # Check if should skip
                if any(skip in path for skip in skip_patterns):
                    continue
                
                # Determine priority
                priority = None
                if any(p1 in path for p1 in p1_patterns):
                    priority = 1
                elif any(p2 in path for p2 in p2_patterns):
                    priority = 2
                elif any(p3 in path for p3 in p3_patterns):
                    priority = 3
                elif any(p4 in path for p4 in p4_patterns):
                    priority = 4
                elif any(p5 in path for p5 in p5_patterns):
                    priority = 5
                else:
                    priority = 99  # Low priority, only if we have room
                
                is_nav_link = href in nav_links
                all_links.append({
                    'href': absolute_href,
                    'path': path,
                    'priority': priority,
                    'is_nav': is_nav_link
                })
            
            # Sort by priority (lower is better), then prefer nav links
            all_links.sort(key=lambda x: (x['priority'], not x['is_nav']))
            
            # Log discovered links
            self.logger.info(f"[Phase 4] Discovered {len(all_links)} internal links:")
            for link in all_links[:10]:  # Log top 10
                priority_label = f"P{link['priority']}" if link['priority'] < 99 else "LOW"
                nav_label = "NAV" if link['is_nav'] else "body"
                self.logger.info(f"  {priority_label} [{nav_label}] {link['href']}")
            
            # Select links: Guarantee P1 if they exist, then fill up to 4 total
            max_links = 4
            selected_links = []
            p1_links = [l for l in all_links if l['priority'] == 1]
            other_links = [l for l in all_links if l['priority'] > 1 and l['priority'] < 99]
            
            # Strategy: Include all P1 links (up to max), then fill remaining slots
            if p1_links:
                # Include all P1 links (they're critical)
                for link in p1_links[:max_links]:
                    selected_links.append(link)
                self.logger.info(f"[Phase 4] Selected {len(selected_links)} P1 (CRITICAL) links")
            
            # Fill remaining slots with other priorities
            remaining_slots = max_links - len(selected_links)
            if remaining_slots > 0:
                for link in other_links:
                    if len(selected_links) >= max_links:
                        break
                    # Avoid duplicates
                    if link['href'] not in [s['href'] for s in selected_links]:
                        selected_links.append(link)
            
            # Log selected links
            self.logger.info(f"[Phase 4] Selected {len(selected_links)} links to crawl:")
            for link in selected_links:
                priority_label = f"P{link['priority']}" if link['priority'] < 99 else "LOW"
                nav_label = "NAV" if link['is_nav'] else "body"
                self.logger.info(f"  → {priority_label} [{nav_label}] {link['href']}")
            
            # Yield requests for selected links
            for link in selected_links:
                try:
                    yield response.follow(
                        link['href'],
                        self.parse,
                        meta=dict(
                            playwright=True,
                            playwright_include_page=True,
                            playwright_context="persistent",
                            depth=depth + 1
                        )
                    )
                except ValueError as e:
                    self.logger.warning(f"[Phase 4] Skipping invalid URL: {link['href']} - {e}")
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
