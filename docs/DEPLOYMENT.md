# VM Deployment Guide

This guide covers deploying the Company Info Scraper on a Virtual Machine for 24/7 operation with parallel processing, health monitoring, and graceful shutdown support.

## What's New in This Version

- ⚡ **Parallel batch processing** - Process multiple domains concurrently
- 🔍 **Dual-path scraping** - Auto-detects static vs dynamic sites
- 🏥 **Built-in health checks** - `python main.py --health`
- 📊 **JSON logging** - Production-ready log format
- 🛑 **Graceful shutdown** - Complete in-progress work before exit
- 🤖 **Google ADK integration** - Agent orchestration ready

## VM Requirements

### Minimum Specifications

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8GB | 16GB+ |
| Storage | 50GB SSD | 100GB+ SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Network Requirements

- Stable internet (10+ Mbps)
- Outbound HTTPS (port 443)
- SSH access (port 22)

## Step-by-Step VM Setup

### 1. Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y python3 python3-pip python3-venv git curl wget htop

# Install Playwright dependencies
sudo apt install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo-gobject2 \
  libgtk-3-0 libgdk-pixbuf2.0-0
```

### 2. Install Ollama

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull required model
ollama pull llama3

# Verify
ollama list
```

### 3. Clone and Setup Project

```bash
# Create application directory
sudo mkdir -p /opt/company-scraper
sudo chown $USER:$USER /opt/company-scraper
cd /opt/company-scraper

# Clone repository
git clone <repository-url> .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Create directories
mkdir -p logs data output
```

### 4. Configure Application

Create `/opt/company-scraper/config.yaml`:

```yaml
# Ollama Configuration
ollama_model: llama3
ollama_timeout: 90
ollama_max_retries: 3

# Scraping Configuration
max_text_length: 5000
download_delay: 0.5
depth_limit: 1
auto_detect: true  # Auto-detect static/dynamic

# Batch Processing (NEW)
batch:
  max_concurrent: 5        # Parallel domains
  rate_limit_delay: 1.0
  timeout_per_domain: 120
  retry_failed: true
  max_retries: 2

# Rate Limiting (NEW)
rate_limiting:
  enabled: true
  requests_per_second: 2.0
  burst_size: 5
  per_domain_delay: 1.0

# Logging (NEW - JSON for production)
log_level: INFO
log_format: json           # Use JSON for log aggregation
log_file: /opt/company-scraper/logs/scraper.log

# Output
output_file: /opt/company-scraper/output/output_data.csv
```

### 5. Create Systemd Services

#### Ollama Service

Create `/etc/systemd/system/ollama.service`:

```ini
[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
User=ollama
Group=ollama
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5
Environment="OLLAMA_HOST=0.0.0.0"

[Install]
WantedBy=multi-user.target
```

#### Scraper Service (with graceful shutdown)

Create `/etc/systemd/system/company-scraper.service`:

```ini
[Unit]
Description=Company Info Scraper Service
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=scraper
Group=scraper
WorkingDirectory=/opt/company-scraper
Environment="PATH=/opt/company-scraper/venv/bin:/usr/local/bin:/usr/bin:/bin"

# Health check before start
ExecStartPre=/opt/company-scraper/venv/bin/python main.py --health --json

# Main command with parallel processing and JSON logging
ExecStart=/opt/company-scraper/venv/bin/python main.py \
    --batch /opt/company-scraper/data/domains.txt \
    --parallel \
    --max-concurrent 5 \
    --log-format json \
    --log-file /opt/company-scraper/logs/scraper.log

# Graceful shutdown (sends SIGTERM, waits for completion)
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=300  # Wait up to 5 min for graceful shutdown

Restart=on-failure
RestartSec=60

StandardOutput=append:/opt/company-scraper/logs/service.log
StandardError=append:/opt/company-scraper/logs/service.error.log

[Install]
WantedBy=multi-user.target
```

### 6. Create Application User

```bash
# Create scraper user
sudo useradd -r -s /bin/bash -d /opt/company-scraper scraper
sudo chown -R scraper:scraper /opt/company-scraper

# Create Ollama user
sudo useradd -r -s /bin/bash ollama || true
```

### 7. Setup Log Rotation

Create `/etc/logrotate.d/company-scraper`:

```
/opt/company-scraper/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 scraper scraper
    postrotate
        systemctl reload company-scraper.service > /dev/null 2>&1 || true
    endscript
}
```

### 8. Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start Ollama
sudo systemctl enable ollama.service
sudo systemctl start ollama.service

# Enable and start scraper
sudo systemctl enable company-scraper.service
sudo systemctl start company-scraper.service

# Check status
sudo systemctl status ollama.service
sudo systemctl status company-scraper.service
```

## Health Monitoring

### Built-in Health Checks

```bash
# Run health check
/opt/company-scraper/venv/bin/python main.py --health

# JSON output for monitoring systems
/opt/company-scraper/venv/bin/python main.py --health --json

# Example JSON output:
{
  "status": "healthy",
  "healthy": true,
  "timestamp": "2024-11-28T10:00:00",
  "version": "1.0.0",
  "summary": "6/6 checks passed",
  "checks": [
    {"name": "ollama_connectivity", "status": "healthy", ...},
    {"name": "ollama_model", "status": "healthy", ...},
    ...
  ]
}
```

### Cron-based Monitoring

Add to crontab:

```bash
# Health check every 5 minutes
*/5 * * * * /opt/company-scraper/venv/bin/python /opt/company-scraper/main.py --health --json >> /opt/company-scraper/logs/health.json 2>&1

# Alert script every 5 minutes
*/5 * * * * /opt/company-scraper/scripts/alert_check.sh
```

Create `/opt/company-scraper/scripts/alert_check.sh`:

```bash
#!/bin/bash
cd /opt/company-scraper
source venv/bin/activate

# Run health check
RESULT=$(python main.py --health --json 2>/dev/null)
STATUS=$(echo "$RESULT" | jq -r '.status')

if [ "$STATUS" != "healthy" ]; then
    echo "$(date): ALERT - Health check failed: $STATUS" >> logs/alerts.log
    # Add notification (email, Slack, etc.)
    # curl -X POST -H 'Content-type: application/json' \
    #   --data '{"text":"Scraper health check failed!"}' \
    #   YOUR_SLACK_WEBHOOK_URL
fi
```

## Multi-Country Processing

### Parallel Processing Script

Create `/opt/company-scraper/scripts/process_all_countries.sh`:

```bash
#!/bin/bash
cd /opt/company-scraper
source venv/bin/activate

COUNTRIES=("us" "uk" "sg" "au" "de")
DATE=$(date '+%Y%m%d')

for country in "${COUNTRIES[@]}"; do
    echo "$(date): Processing $country..."
    
    python main.py \
        --batch "data/countries/${country}_domains.txt" \
        --parallel \
        --max-concurrent 5 \
        --output "output/${country}_${DATE}.csv" \
        --log-format json \
        --log-file "logs/${country}_${DATE}.log"
    
    echo "$(date): Completed $country"
    sleep 30  # Brief pause between countries
done

echo "$(date): All countries processed"
```

### Scheduled Processing

Add to crontab:

```bash
# Process all countries daily at 2 AM
0 2 * * * /opt/company-scraper/scripts/process_all_countries.sh >> /opt/company-scraper/logs/cron.log 2>&1
```

## Graceful Shutdown

The scraper now supports graceful shutdown:

1. **SIGTERM/SIGINT** triggers graceful shutdown
2. Completes current domain(s) before exiting
3. Saves partial results
4. Logs shutdown status

### Manual Graceful Stop

```bash
# Send SIGTERM (graceful)
sudo systemctl stop company-scraper.service

# Wait for completion (check logs)
tail -f /opt/company-scraper/logs/scraper.log
```

### Emergency Stop

```bash
# Force stop
sudo systemctl kill company-scraper.service
```

## Performance Tuning

### Optimize for High Throughput

```yaml
# config.yaml for high-performance VM
batch:
  max_concurrent: 10        # Increase for more cores
  rate_limit_delay: 0.5     # Reduce delay
  timeout_per_domain: 90    # Reduce timeout

rate_limiting:
  requests_per_second: 5.0  # Increase rate
  burst_size: 10
```

### Resource Limits (systemd)

```ini
[Service]
LimitNOFILE=65536
LimitNPROC=4096
MemoryMax=8G
CPUQuota=80%
```

## Log Analysis

### JSON Log Format

Logs in JSON format can be parsed with `jq`:

```bash
# View recent errors
cat logs/scraper.log | jq 'select(.level == "ERROR")'

# Count extractions by status
cat logs/scraper.log | jq 'select(.message | contains("extraction"))' | jq -r '.data.success' | sort | uniq -c

# Average processing time
cat logs/scraper.log | jq 'select(.data.elapsed_ms) | .data.elapsed_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

### Integration with Log Aggregation

JSON logs work with:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **CloudWatch Logs** (AWS)
- **Stackdriver** (GCP)
- **Datadog**
- **Splunk**

## Backup Strategy

Create `/opt/company-scraper/scripts/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/company-scraper"
DATE=$(date '+%Y%m%d_%H%M%S')

mkdir -p $BACKUP_DIR

# Backup outputs
tar -czf "$BACKUP_DIR/output_$DATE.tar.gz" /opt/company-scraper/output/

# Backup config
cp /opt/company-scraper/config.yaml "$BACKUP_DIR/config_$DATE.yaml"

# Keep last 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.yaml" -mtime +30 -delete

echo "Backup completed: $DATE"
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u company-scraper.service -n 100

# Run health check manually
cd /opt/company-scraper
source venv/bin/activate
python main.py --health --health-verbose
```

### Ollama Not Responding

```bash
# Restart Ollama
sudo systemctl restart ollama.service

# Check status
curl http://localhost:11434/api/tags
```

### High Memory Usage

```bash
# Monitor memory
htop

# Reduce concurrency
# Edit config.yaml: batch.max_concurrent: 3
```

### Slow Processing

1. Check site detection: Static sites should be fast
2. Reduce `max_text_length` in config
3. Use faster model: `ollama pull mistral`
4. Increase `max_concurrent` if resources allow

## Security Checklist

- [ ] Firewall enabled (only SSH)
- [ ] Services run as non-root user
- [ ] Logs don't contain sensitive data
- [ ] Regular system updates
- [ ] SSH key authentication
- [ ] Secrets in environment variables

## Maintenance Schedule

### Daily
- Monitor health check logs
- Review error logs
- Verify output quality

### Weekly
- Review disk space
- Check backup integrity
- Analyze performance metrics

### Monthly
- Update system packages
- Update Python dependencies
- Review and optimize configuration
- Clean old logs and outputs

## Support

1. Run health check: `python main.py --health --health-verbose`
2. Check service logs: `sudo journalctl -u company-scraper.service`
3. Review application logs: `cat logs/scraper.log | jq .`
4. Test manually: `python main.py example.com --verbose`
