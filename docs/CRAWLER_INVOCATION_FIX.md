# Crawler Invocation Architecture Fix

## Problem

`CrawlerProcess.start()` was hanging when called from within `OrchestratorAgent.execute()` → `ScrapingAgent.execute()` → `_run_crawler()`. The spider's `start_requests()` method was never called, causing the crawler to hang indefinitely.

## Root Cause

`CrawlerProcess.start()` expects to exclusively control the Twisted reactor lifecycle. When called from within an agent that's part of a larger application:

1. Reactor is already installed in `main.py` before orchestrator creation
2. `CrawlerProcess.start()` tries to start/control the reactor
3. Conflict occurs because reactor state is already initialized
4. Engine never calls `start_requests()` - hangs before scheduling phase

## Solution

**Changed from `CrawlerProcess` to subprocess-isolated execution.**

The crawler now runs in a completely isolated subprocess with:
- Its own Python interpreter
- Its own reactor instance
- No conflicts with parent process reactor state

## Implementation

### Before (Broken)
```python
def _run_crawler(self, domain: str):
    process = CrawlerProcess(settings)
    process.crawl(FullPageSpider, domain=domain)
    process.start()  # ❌ Hangs - reactor conflict
```

### After (Fixed)
```python
def _run_crawler(self, domain: str):
    # Create temporary Python script
    script_content = '''
    # Install reactor in subprocess
    asyncioreactor.install()
    
    # Create CrawlerProcess in isolated subprocess
    process = CrawlerProcess(settings)
    process.crawl(FullPageSpider, domain=domain)
    process.start()  # ✅ Works - no reactor conflict
    '''
    
    # Run script in subprocess
    subprocess.run([sys.executable, script_file], ...)
    
    # Collect results from subprocess output
```

## Verification

✅ **Test Results:**
- Minimal spider (no Playwright): Works
- Minimal spider + Playwright: Works  
- FullPageSpider direct call: Works
- **FullPageSpider via OrchestratorAgent: NOW WORKS** ✅

## Key Points

1. **Spider code unchanged** - No modifications to `FullPageSpider` or spider logic
2. **Playwright unchanged** - No modifications to Playwright configuration
3. **Phase 4 features untouched** - No changes to Phase 4 functionality
4. **Only crawler invocation changed** - Isolated fix to `_run_crawler()` method

## Trade-offs

**Pros:**
- Complete isolation - no reactor conflicts
- Works reliably from any context
- Clean separation of concerns

**Cons:**
- Slight overhead from subprocess creation (~100-200ms)
- Results passed via JSON file (temporary)
- More complex error handling across process boundary

**Acceptable trade-off** for reliability and correctness.

