# Phase 3 Stability Diagnosis

## Issues Found and Fixed

### 1. Critical Bug: `start_urls` Not Set (FIXED)
**Location:** `company_info_scraper/spiders/scraper.py:40-52`

**Problem:** 
- Normalization code and `self.start_urls` assignment were INSIDE the `if not domain:` block
- When `domain` was provided (normal case), `self.start_urls` was NEVER set
- This caused `AttributeError` when accessing `self.start_urls[0]` on line 58
- `start_requests()` would iterate over empty/undefined `start_urls`

**Fix:** Moved normalization code OUTSIDE the `if not domain:` block

**Code Before:**
```python
if not domain:
    raise ValueError("Domain is required.")
    
    # This code was unreachable when domain IS provided!
    domain = domain.strip()
    ...
    self.start_urls = [domain]
```

**Code After:**
```python
if not domain:
    raise ValueError("Domain is required.")

# Now this runs when domain is provided
domain = domain.strip()
...
self.start_urls = [domain]
```

### 2. Syntax Errors in scraping_agent.py (FIXED)
**Location:** Multiple locations in `company_info_scraper/agents/scraping_agent.py`

**Problems:**
- Line 14: Missing indentation for `import asyncio`
- Line 131: Extra indentation in try block
- Line 164: Extra indentation in async try block

**Fix:** Corrected indentation to match Python syntax requirements

## Current Status: `start_requests()` Not Being Called

### Symptoms
1. Spider initializes successfully (logs show "Starting Playwright scraper")
2. `start_urls` is set correctly (`['https://magiqai.io']`)
3. `start_requests()` method exists and is properly defined
4. **BUT:** `start_requests()` is NEVER called by Scrapy engine
5. Crawler hangs/timeouts waiting for requests

### Evidence
- No log message: "start_requests called with start_urls"
- No log message: "Generating request for: ..."
- No entries in debug.log for `start_requests:entry`
- Crawler times out after 120 seconds without scheduling any requests

### Possible Root Causes

#### Hypothesis 1: Engine Not Starting
- Scrapy engine might be blocked before it can call `start_requests()`
- Playwright download handler initialization might be hanging
- Reactor might not be starting properly

#### Hypothesis 2: Phase 4 Remnants
- Phase 4 changes might have broken request scheduling
- Rollback might not be complete
- Some Phase 4 code might still be interfering

#### Hypothesis 3: Scrapy Lifecycle Issue
- `start_requests()` override might not be recognized by Scrapy
- Class attribute vs instance attribute confusion
- Middleware or extension blocking request generation

## What Phase 4 Likely Changed (Based on Plan)

Phase 4 was "Smart Link Prioritization" which involved:
- Priority-based link selection
- Multi-page text concatenation
- Changes to link following logic

**Potential Phase 4 Changes That Could Break Request Scheduling:**
1. Modified `start_requests()` to do something that breaks it
2. Changed how requests are yielded
3. Modified spider initialization in a way that breaks lifecycle
4. Changed how `start_urls` is handled

## Scrapy Lifecycle Assumptions (CRITICAL - DO NOT VIOLATE)

### What MUST Work
1. **Spider `__init__`** - Sets up spider state, MUST set `self.start_urls`
2. **`start_requests()`** - Called by engine AFTER spider is fully initialized
3. **Request Yielding** - `start_requests()` MUST yield Request objects
4. **Engine Scheduling** - Engine schedules yielded requests automatically

### What MUST NOT Be Changed
1. **Twisted Reactor Setup** - Already configured in `main.py` and `settings.py`
2. **scrapy-playwright Configuration** - Already working in Phase 3
3. **`start_requests()` Signature** - Must remain `def start_requests(self):`
4. **Request Meta** - Playwright meta must be set correctly

### Critical Lifecycle Flow
```
1. CrawlerProcess.start() called
2. Spider.__init__() called → sets self.start_urls
3. Engine starts
4. Engine calls spider.start_requests()
5. start_requests() yields Request objects
6. Engine schedules requests
7. Downloader processes requests
8. parse() callback invoked
```

**Current State:** Flow breaks at step 4 - `start_requests()` never called

## Next Steps

1. **Verify Fix:** Test that `start_urls` is now set correctly
2. **Debug Engine:** Add logging to see if engine is starting
3. **Check Playwright Handler:** Verify Playwright download handler isn't blocking
4. **Minimal Test:** Create minimal spider to isolate issue
5. **Compare with Working Version:** If possible, compare with known-working Phase 3 checkpoint

## Recommendations for Phase 4 Re-implementation

1. **DO NOT modify `start_requests()`** - Keep it simple, just yield initial request
2. **DO link prioritization in `parse()`** - After first page loads
3. **DO test incrementally** - Each change should be testable independently
4. **DO preserve spider lifecycle** - Don't break initialization or request generation
5. **DO use depth tracking** - Already implemented, use it for link following logic

