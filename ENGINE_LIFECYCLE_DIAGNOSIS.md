# Scrapy Engine Lifecycle Diagnosis

## Test Results Summary

### ✅ Test 1: Minimal Spider (No Playwright)
**File:** `test_minimal_spider.py`
**Result:** **SUCCESS**
- `start_requests()` ✅ CALLED
- `parse()` ✅ CALLED
- Engine lifecycle works perfectly

### ✅ Test 2: Minimal Spider + Playwright
**File:** `test_playwright_init.py`
**Result:** **SUCCESS**
- Browser launches ✅
- Context starts ✅
- `start_requests()` ✅ CALLED
- `parse()` ✅ CALLED
- Playwright initialization does NOT block engine

### ✅ Test 3: FullPageSpider Direct Call
**File:** `test_fullpage_spider.py`
**Result:** **SUCCESS**
- `start_requests()` ✅ CALLED
- Request yielded ✅
- Spider completes ✅
- FullPageSpider works when called directly

### ❌ Test 4: FullPageSpider via OrchestratorAgent
**File:** `test_orchestrator_path.py`
**Result:** **FAILURE**
- `start_requests()` ❌ NOT CALLED
- Hangs/timeouts
- Same code path as `main.py`

## Root Cause Identified

**The Scrapy engine lifecycle is NOT broken.**
**The issue is specific to how OrchestratorAgent/ScrapingAgent calls the crawler.**

### What Works
1. ✅ Scrapy engine lifecycle (verified with minimal spider)
2. ✅ Playwright initialization (verified with Playwright + minimal spider)
3. ✅ FullPageSpider when called directly (verified with direct CrawlerProcess call)

### What Doesn't Work
1. ❌ FullPageSpider when called through `OrchestratorAgent.execute()`
2. ❌ FullPageSpider when called through `ScrapingAgent.execute()`
3. ❌ FullPageSpider when called through `main.py` workflow

## Hypothesis: Reactor/Event Loop Conflict

When called through the orchestrator path:
- Reactor is already installed in `main.py`
- `OrchestratorAgent` is instantiated
- `ScrapingAgent` is instantiated
- `ScrapingAgent._run_crawler()` creates `CrawlerProcess`
- `CrawlerProcess.start()` is called
- **Engine hangs before calling `start_requests()`**

Possible causes:
1. **Reactor already running** - `CrawlerProcess.start()` expects to control reactor lifecycle
2. **Event loop conflict** - Multiple event loops or reactor instances
3. **Signal handler interference** - Something blocking engine startup
4. **Import order** - Reactor state when `scraping_agent.py` imports Twisted

## Key Differences

### Working Path (test_fullpage_spider.py)
```python
# Fresh Python process
# Reactor installed at top level
process = CrawlerProcess(settings)
process.crawl(FullPageSpider, domain='magiqai.io')
process.start()  # ✅ Works
```

### Broken Path (test_orchestrator_path.py / main.py)
```python
# Reactor installed in main.py
orchestrator = OrchestratorAgent(config)  # Creates ScrapingAgent internally
result = orchestrator.execute({'domain': 'magiqai.io'})
  # Calls ScrapingAgent.execute()
    # Calls _run_crawler()
      # Creates CrawlerProcess
      # Calls process.start()  # ❌ Hangs
```

## Next Steps

1. **Check reactor state** - Verify if reactor is already running when `CrawlerProcess.start()` is called
2. **Check event loop** - Verify if there's an event loop conflict
3. **Compare imports** - Check if `scraping_agent.py` imports are interfering
4. **Check signal handlers** - Verify if signal handlers are blocking

## Critical Finding

**The spider code is NOT the problem.**
**The Scrapy engine is NOT the problem.**
**The issue is in the execution context when called through the orchestrator.**

This explains why Phase 3 "worked" before - if Phase 4 changed how the orchestrator calls the scraper, that would break it without touching spider code.

