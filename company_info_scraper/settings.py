# Scrapy settings for company_info_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "company_info_scraper"

SPIDER_MODULES = ["company_info_scraper.spiders"]
NEWSPIDER_MODULE = "company_info_scraper.spiders"

ADDONS = {}

DEPTH_LIMIT=1  # Only crawl root page (depth 0) and one level deep (depth 1)

# Crawl responsibly by identifying yourself (and your website) on the user-agent
# Use a realistic user agent to avoid bot detection
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Phase 2: Disable robots.txt with universal Playwright (causes hang with scrapy-playwright)
ROBOTSTXT_OBEY = False  # Playwright handler can't handle robots.txt requests properly

# Concurrency and throttling settings
#CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 0.1  # Minimal delay for fast crawling
RANDOMIZE_DOWNLOAD_DELAY = False  # Disable randomization for consistent timing

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers to look more like a real browser
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
SPIDER_MIDDLEWARES = {
    # Disable HttpErrorMiddleware to handle 403 errors gracefully
    'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': None,
}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#DOWNLOADER_MIDDLEWARES = {
#    "company_info_scraper.middlewares.CompanyInfoScraperDownloaderMiddleware": 543,
#}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# Phase 2 Fix: Use CompanyInfoScraperPipeline (pass-through) instead of LLMExtractionPipeline
# This avoids double LLM extraction (pipeline + orchestrator)
# Extraction is now handled ONLY by OrchestratorAgent after scraping completes
ITEM_PIPELINES = {
   "company_info_scraper.pipelines.CompanyInfoScraperPipeline": 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

# ... existing settings ...

# ENABLE PLAYWRIGHT
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Playwright settings - optimized for fast crawling (PH3-S4: Browser context reuse)
PLAYWRIGHT_BROWSER_TYPE = "chromium"  # Use chromium for faster startup

# Browser launch options - browser instance is reused across requests
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "timeout": 15000,  # 15 seconds browser launch timeout
}

# Default navigation timeout for page loads
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 10000  # 10 seconds

# PH3-S4: Persistent browser context for reuse across multiple page requests
# This avoids launching a new browser for each page (saves 3-5s per page)
PLAYWRIGHT_CONTEXTS = {
    "persistent": {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "java_script_enabled": True,
        # User agent for better compatibility
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
}

# Use the persistent context by default
PLAYWRIGHT_DEFAULT_CONTEXT_NAME = "persistent"

# Maximum pages per browser context before recycling (prevents memory leaks)
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 10

# Block unnecessary resources to speed up page loading
# Use PLAYWRIGHT_ABORT_REQUEST for proper resource blocking
def should_abort_request(request):
    """Block images, fonts, stylesheets, media, etc. for faster loading"""
    resource_type = request.resource_type
    return resource_type in ["image", "media", "font", "stylesheet", "websocket", "manifest"]

PLAYWRIGHT_ABORT_REQUEST = should_abort_request

# DATA FORMAT
FEED_FORMAT = "csv"
FEED_URI = "output_data.csv"

# Ollama Configuration (can be overridden via config.yaml or environment variables)
OLLAMA_MODEL = 'llama3'
OLLAMA_TIMEOUT = 30  # 30 seconds - fail fast to avoid blocking pipeline
OLLAMA_MAX_RETRIES = 1  # Single retry to avoid long waits (was 3)
MAX_TEXT_LENGTH = 10000  # Maximum characters to send to LLM per page