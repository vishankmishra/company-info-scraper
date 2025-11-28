# 🚀 How to Run the Project - Visual Guide

## 📋 Quick Answer

**You need 2 terminals:**
- **Terminal 1**: Ollama server (keep running)
- **Terminal 2**: Run scraper (with venv activated)

**Always use venv** - it's already set up for you!

---

## 🎯 Step-by-Step Visual Guide

### TERMINAL 1: Start Ollama Server

```
┌─────────────────────────────────────────┐
│ Terminal 1 - Ollama Server              │
├─────────────────────────────────────────┤
│ $ cd /home/vishank/projects/company-   │
│   info-scraper                          │
│                                         │
│ $ ./start_ollama.sh                     │
│                                         │
│ Starting Ollama server...              │
│ Keep this terminal open...              │
│                                         │
│ time=... level=INFO msg="ollama        │
│ serving on http://127.0.0.1:11434"     │
│                                         │
│ ⚠️ LEAVE THIS TERMINAL OPEN! ⚠️         │
└─────────────────────────────────────────┘
```

**Commands:**
```bash
cd /home/vishank/projects/company-info-scraper
./start_ollama.sh
```

**OR manually:**
```bash
cd /home/vishank/projects/company-info-scraper
ollama serve
```

---

### TERMINAL 2: Run the Scraper

```
┌─────────────────────────────────────────┐
│ Terminal 2 - Scraper                   │
├─────────────────────────────────────────┤
│ $ cd /home/vishank/projects/company-   │
│   info-scraper                          │
│                                         │
│ $ source venv/bin/activate             │
│                                         │
│ (venv) $ python main.py example.com    │
│                                         │
│ Processing domain: example.com          │
│ [Scrapy logs appear here...]           │
│                                         │
│ ✅ Scraping completed!                  │
│    Output: output_data.csv              │
└─────────────────────────────────────────┘
```

**Commands (copy-paste ready):**

```bash
# Step 1: Navigate to project
cd /home/vishank/projects/company-info-scraper

# Step 2: Activate virtual environment (IMPORTANT!)
source venv/bin/activate

# Step 3: Run scraper
python main.py example.com
```

---

## 📝 Complete Command Sequence

### First Time Setup (One-Time Only)

**In Terminal 2:**

```bash
cd /home/vishank/projects/company-info-scraper
source venv/bin/activate
pip install -r requirements.txt
playwright install
```

**Verify Ollama model (can run in any terminal):**
```bash
ollama list  # Should show llama3
# If not: ollama pull llama3
```

---

### Every Time You Run

**Terminal 1:**
```bash
cd /home/vishank/projects/company-info-scraper
./start_ollama.sh
# Keep this terminal open!
```

**Terminal 2:**
```bash
cd /home/vishank/projects/company-info-scraper
source venv/bin/activate
python main.py example.com
```

---

## ✅ Verification Steps

### Check 1: Is venv activated?
```bash
# You should see (venv) at the start of your prompt
(venv) vishank@machine:~/projects/company-info-scraper$
```

### Check 2: Is Ollama running?
```bash
# In Terminal 2 (or new terminal)
curl http://localhost:11434/api/tags
# Should return JSON, not "Connection refused"
```

### Check 3: Check output file
```bash
# After scraping completes
ls -lh output_data.csv
cat output_data.csv
```

---

## 🎨 Different Ways to Run

### Method 1: Python Script (Recommended)
```bash
source venv/bin/activate
python main.py example.com
python main.py https://www.example.com
python main.py --batch domains.txt
```

### Method 2: Shell Script
```bash
source venv/bin/activate
./run_scraper.sh example.com
./batch_scrape.sh domains.txt
```

### Method 3: Scrapy Directly
```bash
source venv/bin/activate
scrapy crawl fullpage -a domain=example.com
```

---

## 🔍 What You Should See

### Terminal 1 (Ollama) - Normal Output:
```
Starting Ollama server...
Keep this terminal open while running the scraper
Press Ctrl+C to stop Ollama

time=2024-11-25T10:00:00.000Z level=INFO msg="ollama serving on http://127.0.0.1:11434"
```

### Terminal 2 (Scraper) - Normal Output:
```
(venv) $ python main.py example.com
Processing domain: example.com
2024-11-25 10:00:00 [scrapy.utils.log] INFO: Scrapy 2.11.0 started
2024-11-25 10:00:01 [scrapy.core.engine] INFO: Spider opened
2024-11-25 10:00:02 [scrapy.core.engine] DEBUG: Crawled (200) <GET https://example.com>
2024-11-25 10:00:05 [company_info_scraper.pipelines] INFO: Successfully extracted data for https://example.com
2024-11-25 10:00:10 [scrapy.core.engine] INFO: Closing spider (finished)
2024-11-25 10:00:10 [scrapy.statscollectors] INFO: Dumped Scrapy stats: {'item_scraped_count': 1}

Scraping completed successfully!
  Domain: example.com
  Records: 1
  Output file: output_data.csv
```

---

## ⚠️ Common Mistakes

### ❌ Mistake 1: Not activating venv
```bash
# WRONG:
python main.py example.com  # Uses system Python

# CORRECT:
source venv/bin/activate
python main.py example.com  # Uses venv Python
```

### ❌ Mistake 2: Ollama not running
```bash
# ERROR: Connection refused to Ollama
# SOLUTION: Start Ollama in Terminal 1 first!
```

### ❌ Mistake 3: Running in wrong directory
```bash
# Make sure you're in:
cd /home/vishank/projects/company-info-scraper
```

### ❌ Mistake 4: Closing Terminal 1
```bash
# Ollama MUST stay running!
# If you close Terminal 1, scraper will fail
```

---

## 🛑 Stopping Everything

**To stop Ollama** (Terminal 1):
- Press `Ctrl+C`

**To stop Scraper** (Terminal 2):
- If running, press `Ctrl+C`
- To deactivate venv: `deactivate` (optional)

---

## 📊 Quick Test

Test with a simple domain:

**Terminal 1:**
```bash
cd /home/vishank/projects/company-info-scraper
ollama serve
```

**Terminal 2:**
```bash
cd /home/vishank/projects/company-info-scraper
source venv/bin/activate
python main.py example.com
```

**Check results:**
```bash
cat output_data.csv
python validate_output.py output_data.csv
```

---

## 💡 Pro Tips

1. **Always activate venv first** - You'll see `(venv)` in your prompt
2. **Keep Terminal 1 open** - Ollama must run continuously
3. **Check Terminal 1** - If scraper fails, check Ollama is running
4. **Use simple domains first** - Test with `example.com` before complex sites
5. **Check output file** - Verify `output_data.csv` is created after scraping

---

## 🆘 Still Having Issues?

1. Check `QUICKSTART.md` for detailed troubleshooting
2. Verify Ollama: `ollama list`
3. Verify venv: `which python` (should show venv path)
4. Check logs in Terminal 2 for specific errors
5. Ensure both terminals are in the project directory

---

## 📚 Additional Resources

- `README.md` - Full documentation
- `DEPLOYMENT.md` - VM deployment guide
- `QUICKSTART.md` - Detailed quick start guide

