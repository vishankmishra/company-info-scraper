#!/bin/bash

# Monitoring script for Company Info Scraper
# Run via cron: 0 * * * * /opt/company-scraper/monitor.sh

LOG_FILE="/opt/company-scraper/logs/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Check service status
SERVICE_STATUS=$(systemctl is-active company-scraper.service 2>/dev/null || echo "unknown")
OLLAMA_STATUS=$(systemctl is-active ollama.service 2>/dev/null || echo "unknown")

# Resource usage
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
MEM=$(free -h | awk '/^Mem:/ {print $3}')

# Disk usage
DISK_USAGE=$(df -h /opt/company-scraper 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo "0")

# Check if output file exists and is recent (modified in last 24 hours)
OUTPUT_FILE="/opt/company-scraper/output/output_data.csv"
if [ -f "$OUTPUT_FILE" ]; then
    FILE_AGE=$(( ($(date +%s) - $(stat -c %Y "$OUTPUT_FILE")) / 3600 ))
    if [ $FILE_AGE -lt 24 ]; then
        OUTPUT_STATUS="recent"
    else
        OUTPUT_STATUS="stale ($FILE_AGE hours old)"
    fi
else
    OUTPUT_STATUS="missing"
fi

# Log to file
{
    echo "[$DATE]"
    echo "  Service Status: $SERVICE_STATUS"
    echo "  Ollama Status: $OLLAMA_STATUS"
    echo "  CPU Usage: ${CPU}%"
    echo "  Memory Usage: $MEM"
    echo "  Disk Usage: ${DISK_USAGE}%"
    echo "  Output File: $OUTPUT_STATUS"
    echo ""
} >> "$LOG_FILE"

# Alert if service down
if [ "$SERVICE_STATUS" != "active" ]; then
    echo "[$DATE] ALERT: Scraper service is down!" >> "$LOG_FILE"
    # Add notification here (email, Slack webhook, etc.)
    # Example: curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL -d "{\"text\":\"Scraper service is down!\"}"
fi

# Alert if disk usage high
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "[$DATE] WARNING: Disk usage above 90%!" >> "$LOG_FILE"
fi

# Alert if output file is stale
if [ "$OUTPUT_STATUS" != "recent" ]; then
    echo "[$DATE] WARNING: Output file is $OUTPUT_STATUS" >> "$LOG_FILE"
fi

# Keep log file size manageable (last 1000 lines)
tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"

