# Quick Start Guide - Company Info Scraper

## Overview

Get the scraper running in **5 minutes**. You need:
- **Terminal 1**: Ollama server (must stay running)
- **Terminal 2**: Run the scraper

**New in this version:**
- ⚡ Parallel processing (`--parallel`)
- 🔍 Auto-detection of static/dynamic sites
- 🏥 Health checks (`--health`)
- 📊 JSON logging for production

---

## Prerequisites Check

```bash
# Check Python (3.9+ required)
python3 --version

# Check Ollama
ollama --version

# Check if venv exists
ls venv/bin/activate
```

---

## Step-by-Step Instructions

### STEP 1: Start Ollama Server (Terminal 1)

```bash
cd /path/to/company-info-scraper
ollama serve
```

**Keep this terminal open!**

Expected output:
```
time=... level=INFO msg="ollama serving on http://127.0.0.1:11434"
```

---

### STEP 2: Verify Ollama Model

In a new terminal (temporary):
```bash
# Check models
ollama list

# If llama3 missing, pull it:
ollama pull llama3
```

---

### STEP 3: Setup Scraper (Terminal 2)

```bash
cd /path/to/company-info-scraper

# Activate virtual environment
source venv/bin/activate

# Verify (should show venv path)
which python
```

---

### STEP 4: Run Health Check (Recommended First Step!)

```bash
# Quick health check
python main.py --health

# Verbose health check
python main.py --health --health-verbose
```

Expected output:
```
============================================================
Health Check - 2024-11-28T10:00:00
============================================================

Overall Status: ✓ HEALTHY
Summary: 6/6 checks passed
Version: 1.0.0

------------------------------------------------------------
Check Results:
------------------------------------------------------------
  ✓ ollama_connectivity: Ollama server is reachable
  ✓ ollama_model: Model 'llama3' is available
  ✓ imports: All 5 required modules available
  ✓ config: Configuration is valid
  ✓ disk_space: Disk space OK: 50.2GB free
  ✓ output_directory: Output directory is writable
```

---

### STEP 5: Scrape a Single Domain

```bash
# Auto-detect best scraper (recommended)
python main.py example.com

# Force static scraper (fast, for simple sites)
python main.py example.com --scraper static

# Force dynamic scraper (for JavaScript-heavy sites)
python main.py example.com --scraper dynamic
```

Expected output:
```
Processing domain: example.com
2024-11-28 10:00:00 - INFO - Detected STATIC site: example.com (confidence: 85%)
2024-11-28 10:00:02 - INFO - Using static scraper (httpx + BeautifulSoup)
2024-11-28 10:00:05 - INFO - Successfully extracted data

✓ Scraping completed successfully!
  Domain: example.com
  Scraper: static
  Records: 2
  Output: output_data.csv
```

---

### STEP 6: Batch Processing

Create `domains.txt`:
```
example.com
httpbin.org
another-site.com
```

Run batch:
```bash
# Sequential (one at a time)
python main.py --batch domains.txt

# Parallel (much faster!)
python main.py --batch domains.txt --parallel

# Parallel with custom concurrency
python main.py --batch domains.txt --parallel --max-concurrent 10
```

Expected output (parallel):
```
Processing 3 domains...
  Mode: Parallel (max 5 concurrent)

==================================================
Batch Processing Results
==================================================
  Total domains: 3
  Successful: 3
  Failed: 0
  Static scraper: 2
  Dynamic scraper: 1
  Total time: 25.3s
  Avg per domain: 8.4s
==================================================
```

---

## Quick Commands Reference

### Single Domain
```bash
python main.py example.com                    # Auto-detect
python main.py example.com --scraper static   # Force static
python main.py example.com --scraper dynamic  # Force dynamic
```

### Batch Processing
```bash
python main.py --batch domains.txt                        # Sequential
python main.py --batch domains.txt --parallel             # Parallel
python main.py --batch domains.txt --parallel --max-concurrent 10
```

### Health & Monitoring
```bash
python main.py --health                    # Quick health check
python main.py --health --health-verbose   # Detailed check
python main.py --health --json             # JSON output
```

### Logging
```bash
python main.py example.com --verbose              # Debug logging
python main.py example.com --log-format json      # JSON logs
python main.py example.com --log-file scrape.log  # Log to file
```

---

## Graceful Shutdown

During batch processing:
- **Ctrl+C once**: Complete current domain(s), then exit cleanly
- **Ctrl+C twice**: Force immediate exit

```
⚠ Received SIGINT signal. Initiating graceful shutdown...
  Completing current domain(s) before exit...
  (Press Ctrl+C again to force exit)
```

---

## Verify Results

```bash
# View CSV
cat output_data.csv

# Validate quality
python validate_output.py output_data.csv
```

Expected validation output:
```
Output Validation Report
========================
Total records: 5
Field Population:
  Products: 4/5 (80%)
  Customers: 3/5 (60%)
  Partnerships: 3/5 (60%)
  Case Studies: 2/5 (40%)

Extraction Status:
  Success: 4/5 (80%)
  Failure: 1/5 (20%)
```

---

## Troubleshooting Quick Fixes

### "Ollama not available"
```bash
# Terminal 1
ollama serve
```

### "Model not found"
```bash
ollama pull llama3
```

### "Module not found"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Health check fails
```bash
python main.py --health --health-verbose
# Review which checks fail and address them
```

### All results N/A
- Increase timeout: Edit `config.yaml` → `ollama_timeout: 120`
- Try different model: `ollama pull mistral`
- Check if site blocks scrapers

---

## Example: Complete First Run

**Terminal 1:**
```bash
cd /path/to/company-info-scraper
ollama serve
```

**Terminal 2:**
```bash
cd /path/to/company-info-scraper
source venv/bin/activate

# Health check first
python main.py --health

# Single domain test
python main.py example.com

# Batch with parallel processing
echo "example.com" > test_domains.txt
echo "httpbin.org" >> test_domains.txt
python main.py --batch test_domains.txt --parallel

# Validate results
python validate_output.py output_data.csv
```

---

## Summary Checklist

- [ ] Terminal 1: Ollama running (`ollama serve`)
- [ ] Terminal 2: venv activated (`source venv/bin/activate`)
- [ ] Health check passes (`python main.py --health`)
- [ ] Single domain works (`python main.py example.com`)
- [ ] Batch works (`python main.py --batch domains.txt --parallel`)
- [ ] Output validated (`python validate_output.py output_data.csv`)

---

## Next Steps

- **Production deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Full documentation**: See [README.md](README.md)
- **Run tests**: `python tests/test_integration.py --quick`
