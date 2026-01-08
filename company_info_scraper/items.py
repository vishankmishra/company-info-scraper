# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from typing import List, Dict


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
    
    # Phase 5: Contact & Leadership Discovery
    # Labeled contact info extracted with context
    emails = scrapy.Field()  # List[Dict] e.g., [{'type': 'Sales', 'value': 'sales@example.com'}]
    phones = scrapy.Field()  # List[Dict] e.g., [{'type': 'Support', 'value': '+91...'}]
    # URL identified as the likely "Team" or "About" page
    leadership_url = scrapy.Field()  # str
    # Social media profile links (LinkedIn, Twitter/X, Facebook)
    social_links = scrapy.Field()  # List[str] e.g., ['https://linkedin.com/in/johndoe', ...]
