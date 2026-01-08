#!/bin/bash

# Direct Scrapy command - bypasses agent wrapper for faster debugging
# This shows logs in real-time and is faster than using main.py

if [ -z "$1" ]; then
    echo "Usage: $0 <domain>"
    echo "Example: $0 https://www.grab.com/sg/"
    exit 1
fi

DOMAIN="$1"

cd "$(dirname "$0")"
source venv/bin/activate

echo "=========================================="
echo "Direct Scrapy Scraping (Real-time Logs)"
echo "=========================================="
echo "Domain: $DOMAIN"
echo ""

# Run scrapy directly - logs will show in real-time
scrapy crawl fullpage -a domain="$DOMAIN" -L INFO

echo ""
echo "=========================================="
echo "Scraping completed!"
echo "Check output_data.csv for results"
echo "=========================================="

