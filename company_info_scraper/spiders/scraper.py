"""
Playwright Spider for Dynamic Sites (PH3-S4)

Uses Playwright with persistent browser context for JavaScript rendering.
Browser context is reused across requests to avoid 3-5s startup per page.

Phase 5 (Bulletproof): 
- Contact extraction with word-boundary regex (fixes false positives)
- Social link extraction (LinkedIn, Twitter/X, Facebook)
- Leadership page content preservation (appends to raw_text for LLM)
"""

import scrapy
import re
from company_info_scraper.items import CompanyInfoScraperItem
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional


class FullPageSpider(scrapy.Spider):
    """Spider for dynamic sites requiring JavaScript rendering.
    
    Uses Playwright with persistent browser context (PH3-S4) for faster
    subsequent page loads. First page takes 3-5s, subsequent pages <2s.
    
    Phase 5 Bulletproof Enhancements:
    - Word-boundary regex for contact type labeling (no more "hr" in "hour")
    - Social link extraction (LinkedIn, Twitter/X, Facebook)
    - Leadership page content preservation in raw_text
    """
    
    name = "fullpage"
    
    # Use persistent context for browser reuse (configured in settings.py)
    custom_settings = {
        'PLAYWRIGHT_DEFAULT_CONTEXT_NAME': 'persistent',
    }
    
    # Phase 5 Bulletproof: Context keywords with word boundaries for short terms
    # Format: 'type': [list of patterns] - patterns starting with r'\b' are regex
    CONTACT_TYPE_KEYWORDS = {
        'sales': ['sales', 'sale', 'business', 'enquiry', 'enquiries', 'inquiry', 'inquiries', 'commercial'],
        'support': ['support', 'help', 'helpdesk', 'service', 'customer', 'care', 'assistance', 'technical'],
        # Word boundary patterns for short keywords to avoid false positives
        'hr': [r'\bhr\b', r'\bhuman\s+resources?\b', 'careers', 'jobs', 'recruitment', 'hiring', 'talent'],
        'it': [r'\bit\b', r'\binformation\s+technology\b', 'tech support'],
        'info': [r'\binfo\b', 'general', 'contact us', 'reach us', 'get in touch'],
        'ceo': [r'\bceo\b', 'chief executive', 'founder', 'director', 'managing director', r'\bmd\b', 'president'],
        'cfo': [r'\bcfo\b', 'chief financial', 'finance director'],
        'cto': [r'\bcto\b', 'chief technology', 'technical director', 'tech lead'],
        'coo': [r'\bcoo\b', 'chief operating', 'operations director'],
        'marketing': ['marketing', 'media', 'press', r'\bpr\b', 'communication', 'brand'],
        'admin': ['admin', 'administration', 'office', 'reception', 'front desk'],
        'accounts': ['accounts', 'billing', 'payment', 'invoice', 'finance', 'accounts payable'],
        # Location-based labels
        'mumbai': ['mumbai', 'bombay'],
        'delhi': ['delhi', r'\bncr\b', 'noida', 'gurgaon', 'gurugram'],
        'dubai': ['dubai', r'\buae\b', 'emirates'],
        'bangalore': ['bangalore', 'bengaluru'],
        'chennai': ['chennai', 'madras'],
        'kolkata': ['kolkata', 'calcutta'],
        'hyderabad': ['hyderabad'],
        'pune': ['pune'],
        'usa': [r'\busa\b', r'\bus\b', 'united states', 'america'],
        'uk': [r'\buk\b', 'united kingdom', 'london', 'britain'],
    }
    
    # Phase 5: Leadership/Team page patterns (HIGHEST PRIORITY)
    LEADERSHIP_PATTERNS = [
        '/team', '/our-team', '/the-team', '/meet-the-team', '/meet-team',
        '/leadership', '/leadership-team', '/our-leadership',
        '/about', '/about-us', '/about_us', '/who-we-are', '/who_we_are',
        '/board', '/board-of-directors', '/board-directors',
        '/management', '/management-team', '/our-management',
        '/directors', '/our-directors',
        '/people', '/our-people',
        '/our-story', '/our-journey', '/story',
        '/founders', '/our-founders',
        '/executives', '/executive-team',
        '/staff', '/our-staff',
    ]
    
    # Phase 5 Bulletproof: Social media URL patterns
    SOCIAL_PATTERNS = [
        r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+/?',
        r'https?://(?:www\.)?twitter\.com/[a-zA-Z0-9_]+/?',
        r'https?://(?:www\.)?x\.com/[a-zA-Z0-9_]+/?',
        r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+/?',
        r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+/?',
    ]
    
    def __init__(self, domain=None, *args, **kwargs):
        super(FullPageSpider, self).__init__(*args, **kwargs)
        
        # #region agent log
        import json
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:__init__","message":"Spider __init__ called","data":{"domain":domain},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H7"}) + '\n')
        # #endregion
        
        if not domain:
            raise ValueError("Domain is required. Please provide a domain parameter.")
        
        domain = domain.strip()
        if not domain.startswith(('http://', 'https://')):
            domain = 'https://' + domain
        
        domain = domain.rstrip('/')
        
        self.start_urls = [domain]
        self.base_domain = urlparse(domain).netloc
        
        self.pages_scraped = 0
        self.collected_items = []
        
        # Phase 5 Bulletproof: Aggregate data across pages
        self.leadership_url = None
        self.all_emails: List[Dict] = []
        self.all_phones: List[Dict] = []
        self.all_social_links: Set[str] = set()
        
        # Phase 5 Bulletproof: Collect raw text from ALL pages (especially leadership)
        self.combined_raw_text = ""
        self.leadership_page_text = ""  # Track leadership page content separately
        
        self.logger.info(f"Starting Playwright scraper for domain: {self.start_urls[0]}")

        # #region agent log
        with open('/home/vishank/projects/company-info-scraper/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"location":"scraper.py:__init__:end","message":"Spider __init__ complete","data":{"start_urls":self.start_urls},"timestamp":__import__('time').time()*1000,"sessionId":"debug-session","hypothesisId":"H7"}) + '\n')
        # #endregion

    def _match_keyword(self, context: str, pattern: str) -> bool:
        """
        Match a keyword pattern against context.
        Supports both plain strings and regex patterns (starting with r'\b').
        
        Args:
            context: The text to search in (already lowercased)
            pattern: Either a plain string or a regex pattern
            
        Returns:
            True if pattern matches in context
        """
        if pattern.startswith(r'\b') or '\\b' in pattern:
            # It's a regex pattern with word boundaries
            try:
                return bool(re.search(pattern, context, re.IGNORECASE))
            except re.error:
                # Fallback to plain string match if regex is invalid
                return pattern.replace(r'\b', '').replace('\\b', '') in context
        else:
            # Plain string match
            return pattern in context

    def _extract_emails(self, text: str, html_content: str = "") -> List[Dict]:
        """
        Extract emails with context-aware labeling using word-boundary regex.
        
        Searches for emails in:
        1. Raw text using regex
        2. mailto: links in HTML
        
        For each email found, looks at preceding 50 chars for context keywords.
        Uses word-boundary matching for short keywords to avoid false positives.
        
        Args:
            text: Plain text content
            html_content: Raw HTML for mailto extraction
            
        Returns:
            List of dicts: [{'type': 'Sales', 'value': 'sales@example.com'}, ...]
        """
        emails_found: List[Dict] = []
        seen_emails: Set[str] = set()
        
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # 1. Extract from text with context
        for match in re.finditer(email_pattern, text):
            email = match.group().lower()
            if email in seen_emails:
                continue
            seen_emails.add(email)
            
            # Get preceding context (50 chars before the match)
            start_pos = max(0, match.start() - 50)
            context = text[start_pos:match.start()].lower()
            
            email_type = self._classify_contact_type(context)
            
            emails_found.append({
                'type': email_type,
                'value': email
            })
        
        # 2. Extract from mailto: links
        if html_content:
            mailto_pattern = r'href=["\']mailto:([^"\'?]+)'
            for match in re.finditer(mailto_pattern, html_content, re.IGNORECASE):
                email = match.group(1).lower().strip()
                if email in seen_emails or not re.match(email_pattern, email):
                    continue
                seen_emails.add(email)
                
                start_pos = max(0, match.start() - 100)
                end_pos = min(len(html_content), match.end() + 50)
                context = html_content[start_pos:end_pos].lower()
                
                email_type = self._classify_contact_type(context)
                
                emails_found.append({
                    'type': email_type,
                    'value': email
                })
        
        return emails_found

    def _extract_phones(self, text: str, html_content: str = "") -> List[Dict]:
        """
        Extract phone numbers with context-aware labeling using word-boundary regex.
        
        Uses word-boundary matching for short keywords to avoid false positives
        (e.g., won't match "hr" in "hour").
        
        Args:
            text: Plain text content
            html_content: Raw HTML for tel: extraction
            
        Returns:
            List of dicts: [{'type': 'Support', 'value': '+91-98765-43210'}, ...]
        """
        phones_found: List[Dict] = []
        seen_phones: Set[str] = set()
        
        phone_patterns = [
            r'\+\d{1,3}[-.\s]?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}',
            r'\+91[-.\s]?\d{5}[-.\s]?\d{5}',
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3,5}[-.\s]?\d{3,5}[-.\s]?\d{3,5}',
        ]
        
        combined_pattern = '|'.join(f'({p})' for p in phone_patterns)
        
        # 1. Extract from text with context
        for match in re.finditer(combined_pattern, text):
            phone = match.group().strip()
            phone_normalized = re.sub(r'\s+', ' ', phone)
            
            digits_only = re.sub(r'\D', '', phone)
            if len(digits_only) < 10:
                continue
                
            if phone_normalized in seen_phones:
                continue
            seen_phones.add(phone_normalized)
            
            # Get preceding context (50 chars before the match)
            start_pos = max(0, match.start() - 50)
            context = text[start_pos:match.start()].lower()
            
            phone_type = self._classify_contact_type(context)
            
            phones_found.append({
                'type': phone_type,
                'value': phone_normalized
            })
        
        # 2. Extract from tel: links
        if html_content:
            tel_pattern = r'href=["\']tel:([^"\']+)'
            for match in re.finditer(tel_pattern, html_content, re.IGNORECASE):
                phone = match.group(1).strip()
                phone_normalized = re.sub(r'\s+', ' ', phone)
                
                digits_only = re.sub(r'\D', '', phone)
                if len(digits_only) < 10:
                    continue
                    
                if phone_normalized in seen_phones:
                    continue
                seen_phones.add(phone_normalized)
                
                start_pos = max(0, match.start() - 100)
                end_pos = min(len(html_content), match.end() + 50)
                context = html_content[start_pos:end_pos].lower()
                
                phone_type = self._classify_contact_type(context)
                
                phones_found.append({
                    'type': phone_type,
                    'value': phone_normalized
                })
        
        return phones_found

    def _extract_socials(self, text: str, html_content: str = "") -> List[str]:
        """
        Extract social media profile URLs.
        
        Searches for LinkedIn, Twitter/X, Facebook, Instagram URLs in both
        plain text and HTML href attributes.
        
        Args:
            text: Plain text content
            html_content: Raw HTML for href extraction
            
        Returns:
            List of social profile URLs
        """
        socials_found: Set[str] = set()
        
        # Combined pattern for all social platforms
        combined_pattern = '|'.join(f'({p})' for p in self.SOCIAL_PATTERNS)
        
        # 1. Extract from text
        for match in re.finditer(combined_pattern, text, re.IGNORECASE):
            url = match.group().rstrip('/')
            socials_found.add(url)
        
        # 2. Extract from HTML href attributes
        if html_content:
            href_pattern = r'href=["\']([^"\']+)["\']'
            for match in re.finditer(href_pattern, html_content):
                url = match.group(1)
                for social_pattern in self.SOCIAL_PATTERNS:
                    if re.match(social_pattern, url, re.IGNORECASE):
                        socials_found.add(url.rstrip('/'))
                        break
        
        # Filter out generic company pages (keep personal profiles)
        filtered = []
        for url in socials_found:
            url_lower = url.lower()
            # Keep LinkedIn personal profiles (/in/) and company pages (/company/)
            # Keep Twitter/X profiles
            # Keep Facebook pages
            if '/in/' in url_lower or '/company/' in url_lower or \
               'twitter.com/' in url_lower or 'x.com/' in url_lower or \
               'facebook.com/' in url_lower or 'instagram.com/' in url_lower:
                filtered.append(url)
        
        return sorted(filtered)

    def _classify_contact_type(self, context: str) -> str:
        """
        Classify contact type based on surrounding context.
        Uses word-boundary matching for short keywords to avoid false positives.
        
        Args:
            context: Text surrounding the contact info (50 chars)
            
        Returns:
            Type label: 'Sales', 'Support', 'Hr', etc., or 'Generic' if no match
        """
        context_lower = context.lower()
        
        for contact_type, patterns in self.CONTACT_TYPE_KEYWORDS.items():
            for pattern in patterns:
                if self._match_keyword(context_lower, pattern):
                    return contact_type.title()
        
        return 'Generic'

    def _is_leadership_page(self, path: str) -> bool:
        """Check if a URL path appears to be a leadership/team page."""
        path_lower = path.lower()
        return any(pattern in path_lower for pattern in self.LEADERSHIP_PATTERNS)

    def _filter_links(self, response, depth: int) -> List[Dict]:
        """
        Phase 5: Priority-based link selection with leadership emphasis.
        
        Priority levels:
        - P0 (CRITICAL): Leadership/Team pages
        - P1 (CRITICAL): customers, clients, case-studies, success-stories
        - P2 (HIGH): partners, partnerships, integrations
        - P3 (MEDIUM): about, company (if not already P0)
        - P4 (MEDIUM): products, services, solutions, contact
        - P5 (LOW): news, blog, resources
        - SKIP: careers, jobs, legal, privacy, terms, login
        
        Returns:
            List of link dicts with priority info
        """
        p0_patterns = self.LEADERSHIP_PATTERNS
        
        p1_patterns = ['/customers', '/clients', '/case-studies', '/case_studies', 
                      '/success-stories', '/success_stories', '/testimonials', 
                      '/our-customers', '/our-clients']
        p2_patterns = ['/partners', '/partnerships', '/integrations', '/alliances', 
                      '/ecosystem', '/technology-partners']
        p3_patterns = ['/company', '/who-we-are', '/who_we_are']
        p4_patterns = ['/products', '/services', '/solutions', '/offerings', '/contact', '/contact-us']
        p5_patterns = ['/news', '/blog', '/resources', '/press']
        skip_patterns = ['/careers', '/jobs', '/legal', '/privacy', '/terms', 
                        '/login', '/signup', '/sign-up', '/register', '/docs', 
                        '/documentation', '/api', '/cart', '/checkout', '/account']
        
        all_links = []
        nav_links = set()
        
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
        
        all_raw_hrefs = response.css("a::attr(href)").getall()
        self.logger.debug(f"[Phase 5] Found {len(all_raw_hrefs)} raw hrefs")
        
        for href in all_raw_hrefs:
            if not href:
                continue
            href_clean = href.strip()
            if not href_clean.startswith(('http://', 'https://', '/')):
                continue
            
            if href.startswith('/'):
                absolute_href = urljoin(response.url, href)
            else:
                absolute_href = href
            
            parsed_href = urlparse(absolute_href)
            if parsed_href.netloc and parsed_href.netloc != self.base_domain:
                continue
            
            path = parsed_href.path.lower()
            
            if any(skip in path for skip in skip_patterns):
                continue
            
            priority = None
            is_leadership = False
            
            if any(p0 in path for p0 in p0_patterns):
                priority = 0
                is_leadership = True
                if not self.leadership_url:
                    self.leadership_url = absolute_href
                    self.logger.info(f"[Phase 5] Identified leadership page: {absolute_href}")
            elif any(p1 in path for p1 in p1_patterns):
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
                priority = 99
            
            is_nav_link = href in nav_links
            all_links.append({
                'href': absolute_href,
                'path': path,
                'priority': priority,
                'is_nav': is_nav_link,
                'is_leadership': is_leadership
            })
        
        all_links.sort(key=lambda x: (x['priority'], not x['is_nav']))
        
        return all_links

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
            request = scrapy.Request(
                url, 
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_context="persistent",
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
        
        if response.status != 200:
            self.logger.error(
                f"Failed to fetch {response.url}: HTTP {response.status}. "
                f"{'Site may be blocking automated access.' if response.status == 403 else ''}"
            )
            item = CompanyInfoScraperItem()
            item['url'] = response.url
            item['raw_text'] = f"ERROR: HTTP {response.status} - Unable to access page"
            item['emails'] = []
            item['phones'] = []
            item['social_links'] = []
            item['leadership_url'] = None
            yield item
            return
        
        page = response.meta["playwright_page"]
        depth = response.meta.get('depth', 0)
        is_leadership_page = response.meta.get('is_leadership_page', False)
        
        start_time = datetime.now()
        self.logger.info(f"Parsing URL (depth {depth}): {response.url} - Started at {start_time.strftime('%H:%M:%S')}")
        
        html_content = ""
        text = ""
        full_text_for_contacts = ""
        
        try:
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except:
                await page.wait_for_load_state('domcontentloaded', timeout=3000)
            
            content = await page.content()
            html_content = content
            soup = BeautifulSoup(content, 'lxml')
            
            # Phase 5 Bulletproof: Extract FULL text for contacts BEFORE removing elements
            full_text_for_contacts = soup.get_text(separator=' ', strip=True)
            
            # Extract contacts from full page (including footer)
            page_emails = self._extract_emails(full_text_for_contacts, html_content)
            page_phones = self._extract_phones(full_text_for_contacts, html_content)
            page_socials = self._extract_socials(full_text_for_contacts, html_content)
            
            # Aggregate contacts
            self.all_emails.extend(page_emails)
            self.all_phones.extend(page_phones)
            self.all_social_links.update(page_socials)
            
            if page_emails:
                self.logger.info(f"[Phase 5] Found {len(page_emails)} emails on {response.url}")
                for e in page_emails[:3]:
                    self.logger.info(f"  → Email [{e['type']}]: {e['value']}")
            
            if page_phones:
                self.logger.info(f"[Phase 5] Found {len(page_phones)} phones on {response.url}")
                for p in page_phones[:3]:
                    self.logger.info(f"  → Phone [{p['type']}]: {p['value']}")
            
            if page_socials:
                self.logger.info(f"[Phase 5] Found {len(page_socials)} social links on {response.url}")
                for s in page_socials[:3]:
                    self.logger.info(f"  → Social: {s}")
            
            # Remove scripts/styles for cleaner LLM text
            for script in soup(["script", "style"]):
                script.extract()
            
            # Phase 5 Bulletproof: For leadership pages, KEEP full text (nav/footer have names)
            # For other pages, remove nav/footer to reduce noise
            if is_leadership_page or self._is_leadership_page(urlparse(response.url).path):
                # Leadership page: keep everything for LLM (names/titles often in various sections)
                text = soup.get_text(separator=' ', strip=True)
                self.logger.info(f"[Phase 5] LEADERSHIP PAGE - preserving full text ({len(text)} chars)")
            else:
                # Regular page: remove nav/footer noise
                for element in soup(["nav", "footer", "header"]):
                    element.extract()
                text = soup.get_text(separator=' ', strip=True)
            
        except Exception as e:
            self.logger.warning(f"Error loading page {response.url}: {e}")
            text = ""
            page_emails = []
            page_phones = []
            page_socials = []

        # Phase 5 Bulletproof: Build combined raw_text with page markers
        page_marker = f"\n\n--- PAGE: {response.url} ---\n\n"
        
        if is_leadership_page or self._is_leadership_page(urlparse(response.url).path):
            # Leadership page gets special marker and FULL text preservation
            page_marker = f"\n\n--- LEADERSHIP PAGE CONTENT ({response.url}) ---\n\n"
            self.leadership_page_text = text  # Track separately
            self.logger.info(f"[Phase 5] Appending LEADERSHIP page text: {len(text)} chars")
        
        # Append this page's text to combined (limit per-page to preserve context)
        page_text_limited = text[:8000]  # 8k chars per page max
        self.combined_raw_text += page_marker + page_text_limited

        # 2. Yield item with ALL aggregated data
        item = CompanyInfoScraperItem()
        item['url'] = response.url
        # Phase 5 Bulletproof: Use combined raw_text (includes leadership page content)
        item['raw_text'] = self.combined_raw_text[:50000]  # 50k char limit for LLM
        
        # Phase 5: Deduplicated contact info
        item['emails'] = self._deduplicate_contacts(self.all_emails)
        item['phones'] = self._deduplicate_contacts(self.all_phones)
        item['social_links'] = sorted(list(self.all_social_links))
        item['leadership_url'] = self.leadership_url
        
        yield item

        # 3. Follow relevant links (depth 0 only)
        if depth == 0:
            all_links = self._filter_links(response, depth)
            
            self.logger.info(f"[Phase 5] Discovered {len(all_links)} internal links:")
            for link in all_links[:10]:
                priority_label = f"P{link['priority']}" if link['priority'] < 99 else "LOW"
                nav_label = "NAV" if link['is_nav'] else "body"
                leadership_tag = " [LEADERSHIP]" if link.get('is_leadership') else ""
                self.logger.info(f"  {priority_label} [{nav_label}]{leadership_tag} {link['href']}")
            
            max_links = 5
            selected_links = []
            
            p0_links = [l for l in all_links if l['priority'] == 0]
            p1_links = [l for l in all_links if l['priority'] == 1]
            other_links = [l for l in all_links if l['priority'] > 1 and l['priority'] < 99]
            
            # P0 (Leadership) first - MUST include
            for link in p0_links[:2]:
                selected_links.append(link)
            
            if p0_links:
                self.logger.info(f"[Phase 5] Selected {len(selected_links)} P0 (LEADERSHIP) links - CRITICAL")
            
            remaining_slots = max_links - len(selected_links)
            if remaining_slots > 0 and p1_links:
                for link in p1_links[:remaining_slots]:
                    if link['href'] not in [s['href'] for s in selected_links]:
                        selected_links.append(link)
            
            remaining_slots = max_links - len(selected_links)
            if remaining_slots > 0:
                for link in other_links:
                    if len(selected_links) >= max_links:
                        break
                    if link['href'] not in [s['href'] for s in selected_links]:
                        selected_links.append(link)
            
            self.logger.info(f"[Phase 5] Selected {len(selected_links)} links to crawl:")
            for link in selected_links:
                priority_label = f"P{link['priority']}" if link['priority'] < 99 else "LOW"
                nav_label = "NAV" if link['is_nav'] else "body"
                leadership_tag = " [LEADERSHIP]" if link.get('is_leadership') else ""
                self.logger.info(f"  → {priority_label} [{nav_label}]{leadership_tag} {link['href']}")
            
            for link in selected_links:
                try:
                    # Phase 5 Bulletproof: Leadership pages get highest priority (100)
                    scrapy_priority = 100 if link.get('is_leadership') else 0
                    yield response.follow(
                        link['href'],
                        self.parse,
                        priority=scrapy_priority,
                        meta=dict(
                            playwright=True,
                            playwright_include_page=True,
                            playwright_context="persistent",
                            depth=depth + 1,
                            is_leadership_page=link.get('is_leadership', False)  # Pass flag
                        )
                    )
                except ValueError as e:
                    self.logger.warning(f"[Phase 5] Skipping invalid URL: {link['href']} - {e}")
                    continue
        else:
            self.logger.debug(f"At depth {depth}, not following additional links")
        
        try:
            await page.close()
            self.pages_scraped += 1
            elapsed = (datetime.now() - start_time).total_seconds()
            
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

    def _deduplicate_contacts(self, contacts: List[Dict]) -> List[Dict]:
        """
        Deduplicate contacts, preferring more specific types over 'Generic'.
        
        Args:
            contacts: List of contact dicts with 'type' and 'value' keys
            
        Returns:
            Deduplicated list with best type for each unique value
        """
        best_contacts = {}
        
        for contact in contacts:
            value = contact['value']
            contact_type = contact['type']
            
            if value not in best_contacts:
                best_contacts[value] = contact
            elif contact_type != 'Generic' and best_contacts[value]['type'] == 'Generic':
                best_contacts[value] = contact
        
        return list(best_contacts.values())
