#!/bin/bash

# Script to run the scraper with venv activated
# Usage: ./run_scraper.sh [domain]
# Example: ./run_scraper.sh example.com
# Example: ./run_scraper.sh https://www.example.com

cd "$(dirname "$0")"
source venv/bin/activate

DOMAIN="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "Running scraper with default domain..."
    scrapy crawl fullpage
else
    echo "Running scraper for domain: $DOMAIN"
    scrapy crawl fullpage -a domain="$DOMAIN"
fi

