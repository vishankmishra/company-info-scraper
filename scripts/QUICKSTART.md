# Quick Start: Full Pipeline

## TL;DR - One Command to Rule Them All

```bash
# Set your API key (one time)
export GROQ_API_KEY='your-groq-api-key-here'

# Run the full pipeline
python scripts/run_full_pipeline.py
```

That's it! The script will:
1. ✅ Scrape all domains from `data/domains_phase_a.txt`
2. ✅ Test ALL 6 Groq models on the scraped data
3. ✅ Generate detailed results

## Commands Reference

### Full Pipeline
```bash
# Run everything (scraping + LLM experiment)
python scripts/run_full_pipeline.py

# Only scrape (skip LLM)
python scripts/run_full_pipeline.py --skip-llm

# Only LLM experiment (skip scraping)
python scripts/run_full_pipeline.py --skip-scrape

# Custom timeout (for slow websites)
python scripts/run_full_pipeline.py --timeout 180
```

### Help
```bash
python scripts/run_full_pipeline.py --help
```

## What Gets Created

| File | Description | Size (approx) |
|------|-------------|---------------|
| `data/enterprise_raw.jsonl` | Scraped website data | ~2-3 MB for 27 domains |
| `data/experiment_results_groq.jsonl` | LLM extraction results | ~0.5-1 MB for 30 records |

## Timing

- **Phase A (Scraping)**: ~7-9 minutes for 27 domains
- **Phase B (LLM Experiment)**: ~24-30 minutes (tests 6 models)
- **Total**: ~30-40 minutes

## Prerequisites Checklist

Before running, ensure:

```bash
# 1. Input file exists
ls data/domains_phase_a.txt

# 2. API key is set
echo $GROQ_API_KEY

# 3. You're in project root
pwd  # Should show /path/to/company-info-scraper
```

## Common Issues

### "Domains file not found"
```bash
# Check if file exists
cat data/domains_phase_a.txt
```

### "GROQ_API_KEY not set"
```bash
export GROQ_API_KEY='your-api-key-here'
```

### Script seems stuck
- It's probably scraping a slow website
- Wait or press Ctrl+C to stop
- Re-run with higher timeout: `--timeout 180`

## What Happens Behind the Scenes

```
Step 1: PHASE A - Web Scraping
-------------------------------
data/domains_phase_a.txt
         ↓
  [Playwright Scraper]
         ↓
data/enterprise_raw.jsonl
  (27 scraped domains with raw text, contacts, etc.)


Step 2: PHASE B - LLM Experimentation
--------------------------------------
data/enterprise_raw.jsonl
         ↓
  [Test 6 Groq Models]
  - llama-3.3-70b-versatile
  - openai/gpt-oss-120b
  - mistral-saba-24b
  - qwen/qwen3-32b
  - llama-4-maverick-17b
  - gemma2-9b-it
         ↓
data/experiment_results_groq.jsonl
  (30 records: 6 models × 5 domains each)
```

## After Pipeline Completes

### View Results
```bash
# View raw scraped data
head -n 1 data/enterprise_raw.jsonl | jq .

# View experiment results
head -n 1 data/experiment_results_groq.jsonl | jq .

# Count results by model
cat data/experiment_results_groq.jsonl | jq -r '.model' | sort | uniq -c
```

### Next Steps
1. Review model comparison table (printed at end)
2. Select best-performing model
3. Run production: `python scripts/run_production.py`

## Full Documentation

For complete documentation, see: [`PIPELINE_README.md`](../PIPELINE_README.md)

## Need Help?

```bash
# Get detailed help
python scripts/run_full_pipeline.py --help

# View what each phase does
cat PIPELINE_README.md
```
