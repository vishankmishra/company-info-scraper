"""
Static Site Detector (PH3-S1)

Detects if a site is static (no JS rendering needed) using HEAD request + heuristics.
Used to route scraping to either BeautifulSoup (static) or Playwright (dynamic).
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class SiteType(Enum):
    """Classification of site type (Phase 3: Corporate detection)."""
    # Phase 3: Corporate site taxonomy
    CORPORATE = "corporate"    # Company landing page, B2B/B2C business
    ECOMMERCE = "ecommerce"    # Product catalog, shopping cart
    BLOG = "blog"              # Article-centric, timestamped posts
    DIRECTORY = "directory"    # Listings of multiple companies
    OTHER = "other"            # Docs, social, government, etc.
    
    # Legacy (Phase 2 - kept for backward compatibility)
    STATIC = "static"      
    DYNAMIC = "dynamic"    
    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    """Result of site type detection."""
    site_type: SiteType
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    url: str
    response_time_ms: Optional[float] = None
    signal_count: int = 0  # Phase 3: Number of signals matched


class SiteDetector:
    """Detects site type for classification (Phase 3: Corporate detection).
    
    Phase 3: Classifies sites as CORPORATE, ECOMMERCE, BLOG, DIRECTORY, or OTHER.
    Defaults to CORPORATE if uncertain. Requires 3+ signals for confident classification.
    
    Usage:
        detector = SiteDetector()
        result = await detector.detect_corporate("https://example.com")
        if result.site_type == SiteType.CORPORATE:
            # Process corporate site
        else:
            # Skip non-corporate
    """
    
    # JavaScript framework indicators in HTML
    JS_FRAMEWORK_PATTERNS = [
        # React
        (r'<div\s+id=["\']root["\']\s*>\s*</div>', 'React root container'),
        (r'<div\s+id=["\']app["\']\s*>\s*</div>', 'Vue/React app container'),
        (r'_react', 'React internal'),
        (r'__NEXT_DATA__', 'Next.js'),
        (r'__NUXT__', 'Nuxt.js'),
        
        # Angular
        (r'ng-version', 'Angular'),
        (r'<app-root', 'Angular app root'),
        (r'ng-app', 'AngularJS'),
        
        # Vue
        (r'__vue__', 'Vue.js'),
        (r'data-v-[a-f0-9]+', 'Vue scoped styles'),
        
        # Generic SPA indicators
        (r'<noscript>.*?enable\s+javascript', 'NoScript JS warning'),
        (r'<body[^>]*>\s*<script', 'Script-first body'),
        (r'window\.__INITIAL_STATE__', 'SSR state hydration'),
        (r'window\.__PRELOADED_STATE__', 'Redux preloaded state'),
    ]
    
    # Patterns indicating static site
    STATIC_INDICATORS = [
        (r'<article', 'Article element'),
        (r'<main[^>]*>[\s\S]{500,}', 'Substantial main content'),
        (r'<p[^>]*>[\s\S]{100,}</p>', 'Substantial paragraphs'),
        (r'<h[1-6][^>]*>[\s\S]+?</h[1-6]>', 'Heading elements'),
        (r'wordpress', 'WordPress'),
        (r'jekyll', 'Jekyll'),
        (r'hugo', 'Hugo'),
        (r'<meta\s+name=["\']generator["\']\s+content=["\']', 'Static generator meta'),
    ]
    
    # Minimum content length for static classification
    MIN_STATIC_CONTENT_LENGTH = 500
    
    def __init__(
        self,
        timeout: float = 10.0,
        user_agent: str = "Mozilla/5.0 (compatible; CompanyInfoScraper/1.0)"
    ):
        self.timeout = timeout
        self.user_agent = user_agent
    
    async def detect(self, url: str) -> DetectionResult:
        """Detect if a site is static or dynamic.
        
        Args:
            url: The URL to analyze
            
        Returns:
            DetectionResult with site type, confidence, and reasons
        """
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        reasons: List[str] = []
        static_score = 0.0
        dynamic_score = 0.0
        response_time_ms = None
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent}
            ) as client:
                # First, do a HEAD request to check headers
                head_result = await self._check_headers(client, url)
                reasons.extend(head_result[2])
                static_score += head_result[0]
                dynamic_score += head_result[1]
                
                # Then fetch the actual content for analysis
                import time
                start = time.time()
                response = await client.get(url)
                response_time_ms = (time.time() - start) * 1000
                
                # Analyze HTML content
                content = response.text
                content_result = self._analyze_content(content)
                reasons.extend(content_result[2])
                static_score += content_result[0]
                dynamic_score += content_result[1]
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout detecting site type for {url}")
            reasons.append("Request timeout - assuming dynamic")
            dynamic_score += 0.3
        except httpx.RequestError as e:
            logger.warning(f"Request error detecting site type for {url}: {e}")
            reasons.append(f"Request error: {str(e)[:50]}")
            return DetectionResult(
                site_type=SiteType.UNKNOWN,
                confidence=0.0,
                reasons=reasons,
                url=url
            )
        except Exception as e:
            logger.error(f"Error detecting site type for {url}: {e}")
            reasons.append(f"Detection error: {str(e)[:50]}")
            return DetectionResult(
                site_type=SiteType.UNKNOWN,
                confidence=0.0,
                reasons=reasons,
                url=url
            )
        
        # Determine final classification
        total_score = static_score + dynamic_score
        if total_score == 0:
            site_type = SiteType.UNKNOWN
            confidence = 0.0
        elif static_score > dynamic_score:
            site_type = SiteType.STATIC
            confidence = static_score / total_score
        else:
            site_type = SiteType.DYNAMIC
            confidence = dynamic_score / total_score
        
        logger.info(
            f"Site detection for {url}: {site_type.value} "
            f"(confidence: {confidence:.2f}, static: {static_score:.2f}, dynamic: {dynamic_score:.2f})"
        )
        
        return DetectionResult(
            site_type=site_type,
            confidence=confidence,
            reasons=reasons,
            url=url,
            response_time_ms=response_time_ms
        )
    
    async def _check_headers(
        self, 
        client: httpx.AsyncClient, 
        url: str
    ) -> Tuple[float, float, List[str]]:
        """Check HTTP headers for site type indicators.
        
        Returns:
            Tuple of (static_score, dynamic_score, reasons)
        """
        static_score = 0.0
        dynamic_score = 0.0
        reasons = []
        
        try:
            response = await client.head(url)
            headers = response.headers
            
            # Check content-type
            content_type = headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                static_score += 0.1
                reasons.append("Content-Type: text/html")
            
            # Check for CDN/static hosting indicators
            server = headers.get('server', '').lower()
            if any(s in server for s in ['nginx', 'apache', 'cloudflare', 'netlify', 'vercel']):
                # These can serve both, slight static lean
                static_score += 0.05
                reasons.append(f"Server: {server[:30]}")
            
            # Check for caching headers (static sites often have aggressive caching)
            cache_control = headers.get('cache-control', '').lower()
            if 'max-age' in cache_control or 'public' in cache_control:
                static_score += 0.1
                reasons.append("Cache-Control headers present")
            
            # Check X-Powered-By for framework hints
            powered_by = headers.get('x-powered-by', '').lower()
            if powered_by:
                if any(f in powered_by for f in ['next.js', 'nuxt', 'express', 'node']):
                    dynamic_score += 0.2
                    reasons.append(f"X-Powered-By: {powered_by[:30]} (JS framework)")
                elif any(f in powered_by for f in ['php', 'wordpress', 'drupal']):
                    static_score += 0.15
                    reasons.append(f"X-Powered-By: {powered_by[:30]} (traditional CMS)")
                    
        except Exception as e:
            logger.debug(f"HEAD request failed for {url}: {e}")
            reasons.append("HEAD request failed, using GET only")
        
        return static_score, dynamic_score, reasons
    
    def _analyze_content(self, content: str) -> Tuple[float, float, List[str]]:
        """Analyze HTML content for site type indicators.
        
        Returns:
            Tuple of (static_score, dynamic_score, reasons)
        """
        static_score = 0.0
        dynamic_score = 0.0
        reasons = []
        
        if not content:
            reasons.append("Empty response body")
            dynamic_score += 0.5
            return static_score, dynamic_score, reasons
        
        content_lower = content.lower()
        
        # Check content length
        # Very short HTML often indicates client-side rendering
        visible_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', content)
        visible_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', visible_text)
        visible_text = re.sub(r'<[^>]+>', '', visible_text)
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()
        
        if len(visible_text) < self.MIN_STATIC_CONTENT_LENGTH:
            dynamic_score += 0.4
            reasons.append(f"Minimal visible text ({len(visible_text)} chars) - likely JS-rendered")
        else:
            static_score += 0.3
            reasons.append(f"Substantial visible text ({len(visible_text)} chars)")
        
        # Check for JavaScript framework patterns
        for pattern, name in self.JS_FRAMEWORK_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                dynamic_score += 0.25
                reasons.append(f"JS framework indicator: {name}")
                break  # One framework indicator is enough
        
        # Check for static site indicators
        static_matches = 0
        for pattern, name in self.STATIC_INDICATORS:
            if re.search(pattern, content_lower):
                static_matches += 1
                if static_matches <= 3:  # Only report first 3
                    reasons.append(f"Static indicator: {name}")
        
        if static_matches > 0:
            static_score += min(0.3, static_matches * 0.1)
        
        # Check script-to-content ratio
        script_content = ''.join(re.findall(r'<script[^>]*>[\s\S]*?</script>', content))
        if len(content) > 0:
            script_ratio = len(script_content) / len(content)
            if script_ratio > 0.5:
                dynamic_score += 0.3
                reasons.append(f"High script ratio ({script_ratio:.0%})")
            elif script_ratio < 0.2:
                static_score += 0.1
                reasons.append(f"Low script ratio ({script_ratio:.0%})")
        
        # Check for common SPA loading patterns
        if re.search(r'<body[^>]*>\s*<div[^>]*>\s*</div>\s*<script', content, re.IGNORECASE):
            dynamic_score += 0.4
            reasons.append("Empty div + script pattern (SPA)")
        
        return static_score, dynamic_score, reasons
    
    def detect_sync(self, url: str) -> DetectionResult:
        """Synchronous wrapper for detect().
        
        Use this in non-async contexts.
        """
        import asyncio
        return asyncio.run(self.detect(url))
    
    async def detect_corporate(self, url: str) -> DetectionResult:
        """Phase 3: Detect if site is CORPORATE vs other types.
        
        Uses homepage + first-level links to classify site type.
        Requires 3+ signals for confident classification.
        Defaults to CORPORATE if uncertain.
        
        Args:
            url: The URL to analyze
            
        Returns:
            DetectionResult with site_type ∈ {CORPORATE, ECOMMERCE, BLOG, DIRECTORY, OTHER}
        """
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        reasons: List[str] = []
        
        # Signal counters for each category
        corporate_signals = 0
        ecommerce_signals = 0
        blog_signals = 0
        directory_signals = 0
        other_signals = 0
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent}
            ) as client:
                response = await client.get(url)
                content = response.text.lower()
                
                # Extract links for analysis
                links = re.findall(r'href=["\']([^"\']+)["\']', content)
                links_str = ' '.join(links[:50])  # First 50 links
                
                # CORPORATE signals (from research doc)
                if re.search(r'/about|/about-us|/company|/who-we-are', links_str):
                    corporate_signals += 1
                    reasons.append("Has /about or /company link")
                
                if re.search(r'/products|/services|/solutions|/offerings', links_str):
                    corporate_signals += 1
                    reasons.append("Has /products or /services link")
                
                if re.search(r'/contact|/contact-us', links_str):
                    corporate_signals += 1
                    reasons.append("Has /contact link")
                
                if re.search(r'/customers|/clients|/case-studies|/success-stories|/testimonials', links_str):
                    corporate_signals += 1
                    reasons.append("Has /customers or /case-studies link")
                
                if re.search(r'/partners|/partnerships|/integrations|/alliances', links_str):
                    corporate_signals += 1
                    reasons.append("Has /partners link")
                
                if re.search(r'request demo|contact sales|get started|schedule demo', content):
                    corporate_signals += 1
                    reasons.append("Has 'Request Demo' or 'Contact Sales' CTA")
                
                # Check for shopping cart (negative signal for corporate)
                if not re.search(r'/cart|/checkout|/shop|/store|add to cart|buy now', content):
                    corporate_signals += 1
                    reasons.append("No shopping cart detected")
                
                # Check for article timestamps (negative signal for corporate)
                if not re.search(r'posted on|published:|<time |article|<article', content):
                    corporate_signals += 1
                    reasons.append("No article timestamps")
                
                # ECOMMERCE signals
                if re.search(r'/cart|/checkout|/shop|/store', links_str):
                    ecommerce_signals += 1
                    reasons.append("Has /cart or /shop link")
                
                if re.search(r'\$\d+\.?\d*|€\d+|add to cart|buy now|add to basket', content):
                    ecommerce_signals += 1
                    reasons.append("Has price patterns or 'Add to Cart'")
                
                if re.search(r'product|sku|catalog', content):
                    ecommerce_signals += 1
                    reasons.append("Has product/SKU keywords")
                
                # BLOG/NEWS signals
                if re.search(r'/blog|/news|/articles|/posts', links_str):
                    blog_signals += 1
                    reasons.append("Has /blog or /news link")
                
                if re.search(r'posted on|published:|by \w+\s+\w+|<article|<time', content):
                    blog_signals += 1
                    reasons.append("Has article timestamps or bylines")
                
                if re.search(r'read more|continue reading|rss|feed', content):
                    blog_signals += 1
                    reasons.append("Has blog patterns (Read More, RSS)")
                
                # DIRECTORY/MARKETPLACE signals
                if re.search(r'compare|rating|review|filter|search companies', content):
                    directory_signals += 1
                    reasons.append("Has comparison/rating features")
                
                # Count company logos/names (rough heuristic)
                logo_count = content.count('logo') + content.count('brand')
                if logo_count > 10:
                    directory_signals += 1
                    reasons.append(f"Multiple logos/brands detected ({logo_count})")
                
                # OTHER signals (docs, social, etc.)
                if re.search(r'/docs|/documentation|/api|/reference|/wiki', links_str):
                    other_signals += 1
                    reasons.append("Has /docs or /api link")
                
                if re.search(r'\.gov|\.edu|github\.io|readthedocs', url):
                    other_signals += 1
                    reasons.append("Government, education, or docs domain")
                
        except Exception as e:
            logger.warning(f"Error detecting corporate site type for {url}: {e}")
            reasons.append(f"Detection error: {str(e)[:50]}")
            # Default to CORPORATE on error
            return DetectionResult(
                site_type=SiteType.CORPORATE,
                confidence=0.5,
                reasons=reasons + ["Defaulting to CORPORATE (detection error)"],
                url=url,
                signal_count=0
            )
        
        # Classification logic: Require 3+ signals for confident classification
        max_signals = max(corporate_signals, ecommerce_signals, blog_signals, directory_signals, other_signals)
        
        if max_signals < 3:
            # Not enough signals - default to CORPORATE
            logger.info(f"Insufficient signals ({max_signals}) for {url}, defaulting to CORPORATE")
            return DetectionResult(
                site_type=SiteType.CORPORATE,
                confidence=0.6,
                reasons=reasons + ["Insufficient signals - defaulting to CORPORATE"],
                url=url,
                signal_count=max_signals
            )
        
        # Confident classification
        if corporate_signals >= 3 and corporate_signals >= max_signals:
            site_type = SiteType.CORPORATE
            confidence = min(0.95, 0.6 + (corporate_signals * 0.1))
        elif ecommerce_signals >= 3 and ecommerce_signals >= max_signals:
            site_type = SiteType.ECOMMERCE
            confidence = min(0.95, 0.6 + (ecommerce_signals * 0.1))
        elif blog_signals >= 3 and blog_signals >= max_signals:
            site_type = SiteType.BLOG
            confidence = min(0.95, 0.6 + (blog_signals * 0.1))
        elif directory_signals >= 3 and directory_signals >= max_signals:
            site_type = SiteType.DIRECTORY
            confidence = min(0.95, 0.6 + (directory_signals * 0.1))
        elif other_signals >= 3 and other_signals >= max_signals:
            site_type = SiteType.OTHER
            confidence = min(0.95, 0.6 + (other_signals * 0.1))
        else:
            # Tie or unclear - default to CORPORATE
            site_type = SiteType.CORPORATE
            confidence = 0.6
            reasons.append("Ambiguous signals - defaulting to CORPORATE")
        
        logger.info(
            f"Corporate detection for {url}: {site_type.value} "
            f"(confidence: {confidence:.2f}, signals: corp={corporate_signals}, "
            f"ecom={ecommerce_signals}, blog={blog_signals}, dir={directory_signals}, other={other_signals})"
        )
        
        return DetectionResult(
            site_type=site_type,
            confidence=confidence,
            reasons=reasons,
            url=url,
            signal_count=max_signals
        )
    
    def detect_corporate_sync(self, url: str) -> DetectionResult:
        """Synchronous wrapper for detect_corporate()."""
        import asyncio
        return asyncio.run(self.detect_corporate(url))


# Convenience function for quick detection
async def detect_site_type(url: str) -> SiteType:
    """Quick detection of site type.
    
    Args:
        url: URL to check
        
    Returns:
        SiteType.STATIC or SiteType.DYNAMIC
    """
    detector = SiteDetector()
    result = await detector.detect(url)
    return result.site_type


def detect_site_type_sync(url: str) -> SiteType:
    """Synchronous quick detection of site type."""
    detector = SiteDetector()
    return detector.detect_sync(url).site_type

