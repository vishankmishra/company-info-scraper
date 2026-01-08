# ✅ Full Pipeline Orchestration - COMPLETE

## What Was Created

A complete orchestration system that connects your Phase A (Scraping) and Phase B (LLM Experimentation) into a single automated workflow.

## 📁 New Files Created

### 1. Main Script
- **`scripts/run_full_pipeline.py`** (380 lines)
  - Orchestrates both phases sequentially
  - Comprehensive error handling
  - Clear progress indicators
  - Flexible command-line options

### 2. Documentation
- **`PIPELINE_README.md`** - Complete documentation (450+ lines)
- **`scripts/QUICKSTART.md`** - Quick reference card
- **`scripts/IMPLEMENTATION_SUMMARY.md`** - Technical details

## 🚀 How to Run

### Simple Command (Run Everything)
```bash
python scripts/run_full_pipeline.py
```

That's it! The script will:
1. ✅ Read domains from `data/domains_phase_a.txt`
2. ✅ Scrape all domains → `data/enterprise_raw.jsonl`
3. ✅ Test ALL 6 Groq models → `data/experiment_results_groq.jsonl`

### Before Running
```bash
# 1. Ensure your API key is set
export GROQ_API_KEY='your-groq-api-key-here'

# 2. Verify input file exists
cat data/domains_phase_a.txt

# 3. Run the pipeline
python scripts/run_full_pipeline.py
```

## ⏱️ Expected Runtime

For 27 domains (from `domains_phase_a.txt`):
- **Phase A (Scraping)**: ~7-9 minutes
- **Phase B (LLM Experiment)**: ~24-30 minutes
- **Total**: ~30-40 minutes

## 📊 What You'll See

```
█████████████████████████████████████████████████████████████████████
  FULL PIPELINE ORCHESTRATION
█████████████████████████████████████████████████████████████████████

🕷️ STEP 1/2: PHASE A - Web Scraping
----------------------------------------------------------------------
✓ Domains file found: data/domains_phase_a.txt
✓ Found 27 domains to scrape
⏱️  Estimated time: ~6 minutes

[1/27] Processing: dduh.in
[dduh.in] ✓ Success: 2 pages, 12,543 chars, 3 emails in 8.5s

...

✅ Phase A Complete!
   - Scraped 27 domains in 7.2 minutes
   - Output: data/enterprise_raw.jsonl

🤖 STEP 2/2: PHASE B - LLM Experimentation
----------------------------------------------------------------------
✓ GROQ_API_KEY is set (gsk_xxxx...yyyy)
✓ Found 27 scraped records to process
⏱️  Estimated time: ~24 minutes (tests ALL models)

Testing Model: llama-3.3-70b-versatile
[1/5] dduh.in ✓ success (4.2s)
...

✅ Phase B Complete!
   - Tested ALL models in 26.3 minutes
   - Output: data/experiment_results_groq.jsonl

█████████████████████████████████████████████████████████████████████
  ✅ PIPELINE COMPLETE
█████████████████████████████████████████████████████████████████████

Summary:
  Total time: 33.5 minutes

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

## 🎯 Command Options

```bash
# Full pipeline (default)
python scripts/run_full_pipeline.py

# Skip scraping (if data already exists)
python scripts/run_full_pipeline.py --skip-scrape

# Only scrape (skip LLM experiment)
python scripts/run_full_pipeline.py --skip-llm

# Custom timeout for slow websites
python scripts/run_full_pipeline.py --timeout 180

# Get help
python scripts/run_full_pipeline.py --help
```

## 📦 Output Files

### Phase A Output: `data/enterprise_raw.jsonl`
One JSON object per line:
```json
{
  "domain": "example.com",
  "final_url": "https://example.com",
  "raw_text": "...",
  "scrape_status": "success",
  "pages_scraped": 2,
  "emails": [{"type": "sales", "value": "sales@example.com"}],
  "phones": [{"type": "Generic", "value": "+1-234-567-8900"}],
  "social_links": ["https://linkedin.com/company/example"],
  "leadership_url": "https://example.com/team"
}
```

### Phase B Output: `data/experiment_results_groq.jsonl`
One JSON object per model+domain combination:
```json
{
  "model": "llama-3.3-70b-versatile",
  "domain": "example.com",
  "extraction": {
    "products": ["Product A"],
    "services": ["Service X"],
    "customers": ["Customer Corp"],
    "partnerships": [],
    "case_studies": [],
    "leadership": ["John Doe - CEO"],
    "emails": ["sales@example.com"],
    "phones": ["+1-234-567-8900"]
  },
  "status": "success",
  "time_taken": 4.2,
  "usage": {"input": 8500, "output": 250, "total": 8750}
}
```

## 🛠️ Architecture

```
┌─────────────────────────────────────────────────┐
│         scripts/run_full_pipeline.py            │
│              (Orchestrator)                     │
└────────────────┬────────────────────────────────┘
                 │
                 ├─── PHASE A: Scraping
                 │    │
                 │    └── batch_scrape_raw.py
                 │        ├─ Input:  data/domains_phase_a.txt
                 │        └─ Output: data/enterprise_raw.jsonl
                 │
                 └─── PHASE B: LLM Experiment
                      │
                      └── scripts/experiment_groq.py
                          ├─ Input:  data/enterprise_raw.jsonl
                          └─ Output: data/experiment_results_groq.jsonl
```

## ✨ Key Features

### Robust Error Handling
- ✅ Stops if Phase A fails completely
- ✅ Continues if some domains fail (logs failures)
- ✅ Verifies output files after each phase
- ✅ Clear error messages with solutions

### User Experience
- ✅ Real-time progress indicators
- ✅ Time estimates for each phase
- ✅ Success/failure statistics
- ✅ Next steps recommendations
- ✅ Emoji indicators for visual clarity

### Flexibility
- ✅ Skip phases independently
- ✅ Configurable timeouts
- ✅ Works with existing scripts (no modifications)
- ✅ Resume capability (via --skip-scrape)

## 📖 Documentation Quick Links

1. **Quick Start**: `scripts/QUICKSTART.md`
   - TL;DR version
   - Common commands
   - Troubleshooting

2. **Full Documentation**: `PIPELINE_README.md`
   - Complete guide
   - Error handling
   - Output formats
   - Timing details

3. **Technical Details**: `scripts/IMPLEMENTATION_SUMMARY.md`
   - Architecture
   - Testing
   - Maintenance

## 🔍 Verification Steps

### 1. Check Script Exists
```bash
ls -lh scripts/run_full_pipeline.py
# Should show: -rwxr-xr-x ... scripts/run_full_pipeline.py
```

### 2. Verify Help Works
```bash
python scripts/run_full_pipeline.py --help
# Should display usage information
```

### 3. Check Input File
```bash
wc -l data/domains_phase_a.txt
# Should show: 27 data/domains_phase_a.txt
```

### 4. Verify API Key
```bash
echo $GROQ_API_KEY
# Should display your API key
```

## 🚨 Troubleshooting

### Problem: "Domains file not found"
**Solution**:
```bash
# Check if file exists
ls data/domains_phase_a.txt

# View contents
cat data/domains_phase_a.txt
```

### Problem: "GROQ_API_KEY environment variable not set"
**Solution**:
```bash
export GROQ_API_KEY='your-api-key-here'
```

### Problem: Script hangs during scraping
**Solution**:
- Some websites are slow or blocking
- Press Ctrl+C to stop
- Run with higher timeout: `--timeout 180`

### Problem: Rate limiting in Phase B
**Solution**:
- The script has built-in 3-second delays
- Wait a few minutes and re-run with `--skip-scrape`

## 📈 After Pipeline Completes

### View Results
```bash
# View first scraped record
head -n 1 data/enterprise_raw.jsonl | jq .

# View first experiment result
head -n 1 data/experiment_results_groq.jsonl | jq .

# Count results per model
cat data/experiment_results_groq.jsonl | jq -r '.model' | sort | uniq -c
```

### Analyze Model Performance
The script prints a comparison table at the end:
```
Model Comparison:
──────────────────────────────────────────────────────────────────────────────────────
Model                                         Success Rate    Avg Time        Avg Tokens       
──────────────────────────────────────────────────────────────────────────────────────
llama-3.3-70b-versatile                       100.0%          4.2s            8,500
openai/gpt-oss-120b                           100.0%          3.8s            7,200
...
```

### Run Production
```bash
# After selecting best model
python scripts/run_production.py
```

## ✅ Requirements Met

All original requirements have been fulfilled:

| Requirement | Status |
|-------------|--------|
| Identify existing scraper | ✅ `batch_scrape_raw.py` |
| Execute programmatically | ✅ Uses `subprocess` |
| Read from domains_phase_a.txt | ✅ Via `--domains-file` flag |
| Save to enterprise_raw.jsonl | ✅ Via `--format jsonl` |
| Trigger experiment_groq.py | ✅ Automatic after scraping |
| Run existing experiment logic | ✅ No modifications |
| Test ALL models | ✅ All 6 models tested |
| Progress indicators | ✅ Emojis, timings, status |
| Stop on scraper failure | ✅ Exit code 1 |
| Verify input file exists | ✅ Pre-flight check |

## 🎉 Ready to Use!

The orchestration system is complete and ready for production use.

### To run now:
```bash
# Set your API key
export GROQ_API_KEY='your-groq-api-key-here'

# Run the full pipeline
python scripts/run_full_pipeline.py
```

### Expected output locations:
- ✅ `data/enterprise_raw.jsonl` (Phase A output)
- ✅ `data/experiment_results_groq.jsonl` (Phase B output)

### Time estimate:
- ⏱️ ~30-40 minutes for 27 domains

---

**Questions or issues?** Check the documentation:
- Quick reference: `scripts/QUICKSTART.md`
- Full guide: `PIPELINE_README.md`
- Technical details: `scripts/IMPLEMENTATION_SUMMARY.md`
