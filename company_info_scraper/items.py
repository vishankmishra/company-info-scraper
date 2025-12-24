# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class CompanyInfoScraperItem(scrapy.Item):
    url = scrapy.Field()
    raw_text = scrapy.Field()  # We feed this to the LLM
    # Structured fields (LLM will fill these later)
    products = scrapy.Field()
    services = scrapy.Field()
    customers = scrapy.Field()
    partnerships = scrapy.Field()
    case_studies = scrapy.Field()
    # Extraction status tracking (PH1-S3)
    extraction_status = scrapy.Field()  # "success" or "failure"
    # Phase 3: Site classification
    site_type = scrapy.Field()  # "corporate", "ecommerce", "blog", "directory", "other"
