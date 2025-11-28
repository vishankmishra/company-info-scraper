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
    """Classification of site rendering type."""
    STATIC = "static"      # Can be scraped with requests + BeautifulSoup
    DYNAMIC = "dynamic"    # Requires JavaScript rendering (Playwright)
    UNKNOWN = "unknown"    # Could not determine


@dataclass
class DetectionResult:
    """Result of site type detection."""
    site_type: SiteType
    confidence: float  # 0.0 to 1.0
    reasons: List[str]
    url: str
    response_time_ms: Optional[float] = None


class SiteDetector:
    """Detects whether a site needs JavaScript rendering.
    
    Usage:
        detector = SiteDetector()
        result = await detector.detect("https://example.com")
        if result.site_type == SiteType.STATIC:
            # Use BeautifulSoup scraper
        else:
            # Use Playwright scraper
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

