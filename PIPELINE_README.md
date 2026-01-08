# Full Pipeline Orchestration

## Overview

The `scripts/run_full_pipeline.py` script orchestrates the complete data processing pipeline by connecting **Phase A (Web Scraping)** and **Phase B (LLM Experimentation)** into a single automated workflow.

## Pipeline Flow

```
data/domains_phase_a.txt
         ↓
    [Phase A: Scraping]
         ↓
data/enterprise_raw.jsonl
         ↓
    [Phase B: LLM Experiment]
         ↓
data/experiment_results_groq.jsonl
```

## Prerequisites

### 1. Input File
- **Required**: `data/domains_phase_a.txt` must exist
- One domain per line (e.g., `example.com`)
- Lines starting with `#` are treated as comments

### 2. Environment Setup
```bash
# For Phase B (LLM Experimentation)
export GROQ_API_KEY='your-groq-api-key-here'
```

### 3. Python Environment
```bash
# Ensure virtual environment is activated (if using one)
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

## Usage

### Basic Usage (Run Both Phases)
```bash
python scripts/run_full_pipeline.py
```

This will:
1. ✅ Verify `data/domains_phase_a.txt` exists
2. 🕷️ **Phase A**: Scrape all domains → `data/enterprise_raw.jsonl`
3. 🤖 **Phase B**: Test ALL Groq models → `data/experiment_results_groq.jsonl`

### Advanced Options

#### Skip Scraping (Run Only LLM Experiment)
```bash
python scripts/run_full_pipeline.py --skip-scrape
```
Use this if `data/enterprise_raw.jsonl` already exists.

#### Skip LLM Experiment (Run Only Scraping)
```bash
python scripts/run_full_pipeline.py --skip-llm
```
Use this to only scrape domains without running the LLM experiment.

#### Custom Timeout Per Domain
```bash
python scripts/run_full_pipeline.py --timeout 180
```
Default is 120 seconds. Increase for slow-loading websites.

#### Get Help
```bash
python scripts/run_full_pipeline.py --help
```

## What Each Phase Does

### Phase A: Web Scraping
- **Script Used**: `batch_scrape_raw.py`
- **Input**: `data/domains_phase_a.txt`
- **Output**: `data/enterprise_raw.jsonl`
- **Features**:
  - Scrapes each domain using Playwright (handles JavaScript)
  - Extracts raw text, emails, phones, social links
  - Visits team/about pages for leadership info
  - Saves one JSON object per line (JSONL format)
  - Continues on errors (failed domains are logged)

**Output Format** (`enterprise_raw.jsonl`):
```json
{
  "domain": "example.com",
  "final_url": "https://example.com",
  "raw_text": "...",
  "scrape_status": "success",
  "error": "",
  "pages_scraped": 2,
  "scrape_time_seconds": 8.5,
  "emails": [{"type": "sales", "value": "sales@example.com"}],
  "phones": [{"type": "Generic", "value": "+1-234-567-8900"}],
  "social_links": ["https://linkedin.com/company/example"],
  "leadership_url": "https://example.com/team"
}
```

### Phase B: LLM Experimentation
- **Script Used**: `scripts/experiment_groq.py`
- **Input**: `data/enterprise_raw.jsonl`
- **Output**: `data/experiment_results_groq.jsonl`
- **Features**:
  - Tests **ALL 6 Groq models**:
    1. `llama-3.3-70b-versatile`
    2. `openai/gpt-oss-120b`
    3. `mistral-saba-24b`
    4. `qwen/qwen3-32b`
    5. `meta-llama/llama-4-maverick-17b-128e-instruct`
    6. `gemma2-9b-it`
  - Extracts structured data (products, services, customers, etc.)
  - Tests first 5 valid domains per model
  - Smart merge: Combines scraper + LLM extracted contacts
  - Rate limiting: 3s delay between requests

**Output Format** (`experiment_results_groq.jsonl`):
```json
{
  "model": "llama-3.3-70b-versatile",
  "domain": "example.com",
  "final_url": "https://example.com",
  "extraction": {
    "products": ["Product A", "Product B"],
    "services": ["Service X"],
    "customers": ["Customer Corp"],
    "partnerships": [],
    "case_studies": [],
    "leadership": ["John Doe - CEO"],
    "emails": ["sales@example.com"],
    "phones": ["+1-234-567-8900"]
  },
  "status": "success",
  "error": null,
  "time_taken": 4.2,
  "usage": {"input": 8500, "output": 250, "total": 8750},
  "text_length": 12000
}
```

## Timing Estimates

### Phase A (Scraping)
- **~15-20 seconds per domain** (average)
- For 27 domains: **~7-9 minutes**
- Factors: Website speed, JavaScript rendering, network latency

### Phase B (LLM Experiment)
- **~5 seconds per domain per model** + 3s rate limit delay
- 6 models × 5 domains × 8s = **~4 minutes per model**
- Total: **~24-30 minutes for all models**

**Total Pipeline: ~30-40 minutes for 27 domains**

## Error Handling

The pipeline is designed to be resilient:

1. **Scraping Failures**: If some domains fail to scrape, the pipeline continues
2. **Partial Success**: Exit codes indicate partial success (some domains failed but others succeeded)
3. **Stop on Critical Errors**: If Phase A completely fails (no output), Phase B won't run
4. **Resume Capability**: You can re-run with `--skip-scrape` if scraping already succeeded

### Exit Codes
- `0`: Complete success
- `1`: Critical failure (Phase A failed completely)
- `2`: Phase B failed (but Phase A succeeded)
- `130`: User interrupted (Ctrl+C)

## Monitoring Progress

The script provides detailed progress information:

```
🕷️ STEP 1/2: PHASE A - Web Scraping
----------------------------------------------------------------------
✓ Domains file found: /path/to/data/domains_phase_a.txt
✓ Batch scraper script found: /path/to/batch_scrape_raw.py
✓ Found 27 domains to scrape
⏱️  Estimated time: ~6 minutes (405 seconds)

[1/27] Processing: example.com
[example.com] Starting Playwright scraper...
[example.com] ✓ Success: 2 pages, 12,543 chars, 3 emails, 2 phones, 1 socials in 8.5s

...

✅ Phase A Complete!
   - Scraped 27 domains in 7.2 minutes
   - Output: /path/to/data/enterprise_raw.jsonl

🤖 STEP 2/2: PHASE B - LLM Experimentation
----------------------------------------------------------------------
✓ Scraping output (input for LLM) found: /path/to/data/enterprise_raw.jsonl
✓ LLM experiment script found: /path/to/scripts/experiment_groq.py
✓ GROQ_API_KEY is set (gsk_xxxx...yyyy)
✓ Found 27 scraped records to process
⏱️  Estimated time: ~24 minutes (tests ALL models)

...

✅ Phase B Complete!
   - Tested ALL models in 26.3 minutes
   - Output: /path/to/data/experiment_results_groq.jsonl

█████████████████████████████████████████████████████████████████████
  ✅ PIPELINE COMPLETE
█████████████████████████████████████████████████████████████████████

Summary:
  Total time: 33.5 minutes (2010.0 seconds)

  Phase A: ✅ SUCCESS
  Phase B: ✅ SUCCESS

Output Files:
  ✓ data/enterprise_raw.jsonl (2.45 MB)
  ✓ data/experiment_results_groq.jsonl (0.78 MB)

Next Steps:
  1. Review experiment results: data/experiment_results_groq.jsonl
  2. Analyze model performance and select best model
  3. Run production enrichment: python scripts/run_production.py
```

## Troubleshooting

### Problem: "Domains file not found"
**Solution**: Ensure `data/domains_phase_a.txt` exists in the project root
```bash
ls -la data/domains_phase_a.txt
```

### Problem: "GROQ_API_KEY environment variable not set"
**Solution**: Export your Groq API key
```bash
export GROQ_API_KEY='your-api-key-here'
# Verify it's set
echo $GROQ_API_KEY
```

### Problem: "Cannot proceed without batch scraper"
**Solution**: Ensure `batch_scrape_raw.py` exists
```bash
ls -la batch_scrape_raw.py
```

### Problem: Script hangs during scraping
**Solution**: Some websites might be slow or blocking. Use Ctrl+C to stop, then:
```bash
# Increase timeout
python scripts/run_full_pipeline.py --timeout 180

# Or check the failed domain in data/enterprise_raw.jsonl
```

### Problem: Rate limiting errors in Phase B
**Solution**: The script already has 3s delays. If you still hit limits:
1. Wait a few minutes
2. Edit `scripts/experiment_groq.py` to increase `RATE_LIMIT_DELAY`

## After Pipeline Completion

### 1. Review Experiment Results
```bash
# View first few results
head -n 3 data/experiment_results_groq.jsonl | jq .

# Count results per model
cat data/experiment_results_groq.jsonl | jq -r '.model' | sort | uniq -c
```

### 2. Analyze Model Performance
Look at the summary table printed at the end of Phase B to compare:
- Success rate
- Average time per domain
- Average token usage

### 3. Run Production Enrichment
Once you've selected the best model:
```bash
python scripts/run_production.py
```

This will enrich ALL domains using the best-performing model.

## Integration with Existing Workflow

This orchestration script **does not replace** your existing scripts. It simply connects them:

```
BEFORE:
1. python batch_scrape_raw.py --domains-file data/domains_phase_a.txt ...
2. Wait for completion
3. python scripts/experiment_groq.py
4. Wait for completion

AFTER:
1. python scripts/run_full_pipeline.py
   (automatically runs both steps)
```

You can still run each script individually if needed!

## File Locations Quick Reference

| File | Purpose | Created By |
|------|---------|------------|
| `data/domains_phase_a.txt` | Input: List of domains | Manual |
| `data/enterprise_raw.jsonl` | Phase A output | `batch_scrape_raw.py` |
| `data/experiment_results_groq.jsonl` | Phase B output | `experiment_groq.py` |
| `scripts/run_full_pipeline.py` | Orchestrator | This script |
| `batch_scrape_raw.py` | Scraper | Existing |
| `scripts/experiment_groq.py` | LLM tester | Existing |

## Quick Start Checklist

- [ ] `data/domains_phase_a.txt` exists with domains
- [ ] Virtual environment activated (if using one)
- [ ] `GROQ_API_KEY` environment variable set
- [ ] Run: `python scripts/run_full_pipeline.py`
- [ ] Wait ~30-40 minutes
- [ ] Review results in `data/experiment_results_groq.jsonl`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review individual script documentation:
   - `batch_scrape_raw.py` (scraping)
   - `scripts/experiment_groq.py` (LLM experimentation)
3. Check logs and error messages - they're verbose by design!
