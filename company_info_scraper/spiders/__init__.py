# This package will contain the spiders of your Scrapy project
#
# Please refer to the documentation for information on how to create and manage
# your spiders.

from .static_scraper import StaticScraper, ScrapedPage, scrape_static_site

__all__ = ['StaticScraper', 'ScrapedPage', 'scrape_static_site']
