#!/bin/bash

# Script to run scraper for multiple domains from a file
# Usage: ./batch_scrape.sh domains.txt
# domains.txt should contain one domain per line

if [ -z "$1" ]; then
    echo "Usage: $0 <domains_file>"
    echo "Example: $0 domains.txt"
    exit 1
fi

DOMAINS_FILE="$1"

if [ ! -f "$DOMAINS_FILE" ]; then
    echo "Error: File $DOMAINS_FILE not found"
    exit 1
fi

cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting batch scraping from $DOMAINS_FILE"
echo "=========================================="

while IFS= read -r domain || [ -n "$domain" ]; do
    # Skip empty lines and comments
    domain=$(echo "$domain" | sed 's/#.*//' | xargs)
    if [ -z "$domain" ]; then
        continue
    fi
    
    echo ""
    echo "Processing: $domain"
    echo "----------------------------------------"
    
    scrapy crawl fullpage -a domain="$domain"
    
    # Optional: Add delay between domains
    sleep 2
    
done < "$DOMAINS_FILE"

echo ""
echo "Batch scraping completed!"

