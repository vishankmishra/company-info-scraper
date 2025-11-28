# Company-Info-Scraper Recovery & Implementation Plan

## High-Level Overview

- **Fix critical reliability issues first** — Increase Ollama timeout, add retry logic, prevent silent N/A failures
- **Decouple LLM extraction from Scrapy pipeline** — Move to async post-processing to unblock scraping
- **Implement dual-path scraping** — Add static site detection using HEAD request + heuristics; use requests+BeautifulSoup for static, Playwright only for dynamic
- **Remove subprocess spawning** — Use Scrapy's CrawlerProcess programmatically instead of Popen
- **Add parallel batch processing** — Use asyncio/concurrent.futures for multi-domain scraping
- **Integrate Google ADK properly** — Install actual ADK SDK, wrap agents as ADK-compatible components
- **Optimize for sub-minute performance** — Browser reuse, connection pooling, smart timeouts
- **Production hardening** — Health checks, graceful shutdown, proper monitoring
- **Validate against meeting requirements** — Customers, Partnerships, Case Studies extraction must work reliably

---

## Phase 1: Critical Reliability Fixes

_Fix the immediate crashes and silent failures without major architectural changes._

### PH1-S1: Increase Ollama Timeout

- **Goal**: Prevent LLM timeout failures that cause N/A outputs
- **Files/Modules**: `company_info_scraper/settings.py`, `company_info_scraper/pipelines.py`, `config.yaml`
- **Type of change**: Config update
- **Why**: Audit showed 30s timeout causes failures; LLM needs 45-90s for complex pages
- **Success criteria**: Scraping a complex site (e.g., tasconnect.com) completes LLM extraction without timeout error in logs
- **Dependencies**: None

### PH1-S2: Add Retry Logic for LLM Calls

- **Goal**: Automatically retry failed Ollama calls (up to 3 times with exponential backoff)
- **Files/Modules**: `company_info_scraper/pipelines.py` (LLMExtractionPipeline.process_item)
- **Type of change**: Refactor
- **Why**: Current code catches TimeoutError but doesn't retry, just returns N/A
- **Success criteria**: A transient Ollama failure retries and succeeds; logs show "Retry 1/3" messages
- **Dependencies**: PH1-S1

### PH1-S3: Add Result Validation and Failure Flagging

- **Goal**: Track extraction quality; flag when all fields are N/A as a failure, not success
- **Files/Modules**: `company_info_scraper/pipelines.py`, `validate_output.py`
- **Type of change**: New logic + refactor
- **Why**: System currently treats N/A as success; can't distinguish real failures
- **Success criteria**: Output CSV includes `extraction_status` column; batch summary shows failure count
- **Dependencies**: PH1-S2

### PH1-S4: Fix Deprecated Scrapy APIs

- **Goal**: Replace deprecated `start_requests()` with new `start()` async method
- **Files/Modules**: `company_info_scraper/spiders/scraper.py`
- **Type of change**: Refactor
- **Why**: Logs show ScrapyDeprecationWarning; will break in future Scrapy versions
- **Success criteria**: No deprecation warnings in scrapy crawl output
- **Dependencies**: None

---

## Phase 2: Architecture Decoupling

_Separate scraping from LLM extraction to unblock the pipeline._

### PH2-S1: Create Async LLM Extraction Service

- **Goal**: Move LLM extraction out of Scrapy pipeline into a separate async processor
- **Files/Modules**: New file `company_info_scraper/services/llm_service.py`
- **Type of change**: New module
- **Why**: Current synchronous pipeline blocks all scraping while waiting for Ollama
- **Success criteria**: LLM service can be called independently with `await llm_service.extract(text)`
- **Dependencies**: PH1-S2

### PH2-S2: Refactor Pipeline to Queue Raw Text

- **Goal**: Pipeline saves raw text to temp storage; LLM processing happens after crawl completes
- **Files/Modules**: `company_info_scraper/pipelines.py`, new `company_info_scraper/services/extraction_queue.py`
- **Type of change**: Refactor + new module
- **Why**: Decouples scraping speed from LLM speed
- **Success criteria**: Scrapy crawl finishes in <10s for 4 pages; LLM runs separately
- **Dependencies**: PH2-S1

### PH2-S3: Remove Subprocess.Popen Scrapy Spawning

- **Goal**: Use CrawlerProcess/CrawlerRunner programmatically instead of subprocess
- **Files/Modules**: `company_info_scraper/agents/scraping_agent.py`
- **Type of change**: Refactor
- **Why**: Subprocess spawning loses control, can't share state, wastes resources
- **Success criteria**: ScrapingAgent.execute() runs Scrapy in-process; no subprocess.Popen calls remain
- **Dependencies**: PH2-S2
- **Risk note**: Breaking change to agent interface; test thoroughly

### PH2-S4: Consolidate Duplicate LLM Code

- **Goal**: Remove duplicate extraction logic; single source of truth for LLM prompts/parsing
- **Files/Modules**: `company_info_scraper/agents/llm_extraction_agent.py`, `company_info_scraper/pipelines.py`
- **Type of change**: Refactor + delete
- **Why**: Two near-identical implementations exist; maintenance nightmare
- **Success criteria**: Only one LLM extraction implementation exists; both entry points use it
- **Dependencies**: PH2-S1

---

## Phase 3: Dual-Path Scraping Implementation

_Add static site detection and BeautifulSoup-only path per meeting requirements._

### PH3-S1: Create Static Site Detector

- **Goal**: Detect if a site is static (no JS rendering needed) using HEAD request + content-type + heuristics
- **Files/Modules**: New file `company_info_scraper/services/site_detector.py`
- **Type of change**: New module
- **Why**: Meeting notes require Python/BeautifulSoup for static, Playwright for dynamic
- **Success criteria**: Detector correctly classifies example.com as static, react apps as dynamic
- **Dependencies**: None

### PH3-S2: Create Static Scraper Using Requests + BeautifulSoup

- **Goal**: New spider/scraper that fetches pages via httpx/requests without browser
- **Files/Modules**: New file `company_info_scraper/spiders/static_scraper.py`
- **Type of change**: New module
- **Why**: 10x faster for static sites; no browser overhead
- **Success criteria**: Static scraper fetches and parses example.com in <1 second
- **Dependencies**: PH3-S1

### PH3-S3: Integrate Dual-Path Logic into Orchestrator

- **Goal**: Orchestrator checks site type first, routes to appropriate scraper
- **Files/Modules**: `company_info_scraper/agents/orchestrator_agent.py`, `company_info_scraper/agents/scraping_agent.py`
- **Type of change**: Refactor
- **Why**: Fulfills meeting requirement for intelligent static/dynamic handling
- **Success criteria**: Static sites use static_scraper; dynamic sites use Playwright spider
- **Dependencies**: PH3-S1, PH3-S2

### PH3-S4: Add Browser Context Reuse for Playwright

- **Goal**: Keep browser instance alive across multiple dynamic page requests
- **Files/Modules**: `company_info_scraper/settings.py`, `company_info_scraper/spiders/scraper.py`
- **Type of change**: Config + refactor
- **Why**: Currently launches new browser per request; 3-5s overhead each time
- **Success criteria**: Second dynamic page in same batch loads in <2s (no browser launch)
- **Dependencies**: PH3-S3

---

## Phase 4: Parallel Batch Processing

_Enable concurrent multi-domain scraping for production scale._

### PH4-S1: Implement Async Batch Processor

- **Goal**: Process multiple domains concurrently using asyncio
- **Files/Modules**: `company_info_scraper/agents/orchestrator_agent.py`, new `company_info_scraper/services/batch_processor.py`
- **Type of change**: New module + refactor
- **Why**: Current sequential processing is 30-60s per domain; unacceptable at scale
- **Success criteria**: 5 static domains complete in <30s total (not 150s)
- **Dependencies**: PH3-S3

### PH4-S2: Add Concurrency Limits and Rate Limiting

- **Goal**: Configurable max concurrent requests; per-domain rate limiting
- **Files/Modules**: `config.yaml`, `company_info_scraper/services/batch_processor.py`
- **Type of change**: Config + refactor
- **Why**: Prevent overwhelming target sites or local resources
- **Success criteria**: Config option `max_concurrent: 5` limits parallel requests to 5
- **Dependencies**: PH4-S1

### PH4-S3: Parallel LLM Processing with Worker Pool

- **Goal**: Process LLM extractions in parallel using worker pool (ThreadPoolExecutor or async)
- **Files/Modules**: `company_info_scraper/services/llm_service.py`
- **Type of change**: Refactor
- **Why**: Multiple Ollama calls can run concurrently (if resources allow)
- **Success criteria**: 5 LLM extractions complete in ~60s total (not 150s sequential)
- **Dependencies**: PH2-S1, PH4-S1
- **Risk note**: May need multiple Ollama instances or GPU; test resource usage

---

## Phase 5: Google ADK Integration

_Fulfill the meeting requirement for actual Google ADK orchestration._

### PH5-S1: Add Google ADK SDK Dependency

- **Goal**: Install google-adk package; verify it works with Python environment
- **Files/Modules**: `requirements.txt`, test script
- **Type of change**: Dependency
- **Why**: Meeting explicitly requires Google ADK; currently not installed
- **Success criteria**: `import google.adk` succeeds; ADK example runs
- **Dependencies**: None
- **Risk note**: ADK may have specific Python version or dependency requirements

### PH5-S2: Wrap Agents as ADK-Compatible Components

- **Goal**: Refactor BaseAgent and subclasses to implement ADK agent protocols
- **Files/Modules**: `company_info_scraper/agents/base_agent.py`, all agent files
- **Type of change**: Refactor
- **Why**: Current agents are plain Python classes, not ADK agents
- **Success criteria**: Agents can be registered and invoked via ADK runtime
- **Dependencies**: PH5-S1, PH2-S3

### PH5-S3: Create ADK Orchestration Workflow

- **Goal**: Define ADK workflow that coordinates scraping -> extraction -> output agents
- **Files/Modules**: New file `company_info_scraper/workflows/scrape_workflow.py`
- **Type of change**: New module
- **Why**: ADK provides built-in orchestration, retry, and observability
- **Success criteria**: Full scrape can be triggered via ADK workflow API
- **Dependencies**: PH5-S2

---

## Phase 6: Production Hardening

_Prepare for VM deployment with monitoring, graceful shutdown, and validation._

### PH6-S1: Add Health Check Endpoint

- **Goal**: Simple HTTP endpoint or CLI command that verifies system health
- **Files/Modules**: New file `company_info_scraper/health.py`, `main.py`
- **Type of change**: New module
- **Why**: Deployment docs mention health checks but none exist in code
- **Success criteria**: `python main.py --health` returns 0 if Ollama reachable, 1 otherwise
- **Dependencies**: None

### PH6-S2: Implement Graceful Shutdown Handler

- **Goal**: Handle SIGTERM/SIGINT; complete in-flight requests before exit
- **Files/Modules**: `main.py`, `company_info_scraper/services/batch_processor.py`
- **Type of change**: New logic
- **Why**: Systemd sends SIGTERM; current code may leave zombie processes
- **Success criteria**: Ctrl+C during batch completes current domain, then exits cleanly
- **Dependencies**: PH4-S1

### PH6-S3: Add Structured Logging with JSON Output

- **Goal**: Machine-readable logs for production monitoring
- **Files/Modules**: All files with logging, new `company_info_scraper/logging_config.py`
- **Type of change**: Refactor
- **Why**: Plain text logs hard to parse in production; JSON enables log aggregation
- **Success criteria**: Logs output as JSON when `LOG_FORMAT=json` env var set
- **Dependencies**: None

### PH6-S4: Update Documentation to Match Implementation

- **Goal**: Fix README, DEPLOYMENT.md to accurately reflect actual capabilities
- **Files/Modules**: `README.md`, `DEPLOYMENT.md`, `QUICKSTART.md`
- **Type of change**: Documentation
- **Why**: Current docs claim features (parallel processing) that don't exist
- **Success criteria**: Docs accurately describe dual-path scraping, parallel batch, ADK integration
- **Dependencies**: All previous phases

### PH6-S5: Create End-to-End Integration Test

- **Goal**: Automated test that scrapes 3 known domains and validates output quality
- **Files/Modules**: `tests/test_integration.py`, `tests/test_domains.txt`
- **Type of change**: New test
- **Why**: Need regression test to catch future breakage
- **Success criteria**: `pytest tests/test_integration.py` passes; validates Customers/Partnerships extraction
- **Dependencies**: All previous phases

---

## Recommended Execution Order

1. PH1-S1 (Increase Ollama timeout)
2. PH1-S2 (Add retry logic)
3. PH1-S3 (Result validation)
4. PH1-S4 (Fix deprecated APIs)
5. PH2-S1 (Async LLM service)
6. PH2-S2 (Queue-based pipeline)
7. PH2-S3 (Remove subprocess spawning)
8. PH2-S4 (Consolidate LLM code)
9. PH3-S1 (Static site detector)
10. PH3-S2 (Static scraper)
11. PH3-S3 (Dual-path orchestrator)
12. PH3-S4 (Browser context reuse)
13. PH4-S1 (Async batch processor)
14. PH4-S2 (Concurrency limits)
15. PH4-S3 (Parallel LLM workers)
16. PH5-S1 (ADK dependency)
17. PH5-S2 (ADK agent wrappers)
18. PH5-S3 (ADK workflow)
19. PH6-S1 (Health check)
20. PH6-S2 (Graceful shutdown)
21. PH6-S3 (JSON logging)
22. PH6-S4 (Documentation update)
23. PH6-S5 (Integration test)

---

## Validation Plan

### Functional Validation

- Scrape 5 known test domains (mix of static and dynamic)
- Verify Customers, Partnerships, Case Studies fields are populated (not N/A) for at least 60% of pages
- Confirm dual-path routing works (check logs for "using static scraper" vs "using Playwright")

### Performance Validation

- Single static domain: < 5 seconds end-to-end
- Single dynamic domain: < 30 seconds end-to-end
- Batch of 10 mixed domains: < 3 minutes total (with parallelization)

### Production Readiness Validation

- Health check returns success when Ollama running
- Graceful shutdown completes within 30 seconds
- Systemd service starts, runs batch, and exits cleanly
- Logs are parseable JSON when configured

### Meeting Requirements Validation

- [ ] Google ADK orchestration is functional
- [ ] Static sites use BeautifulSoup path
- [ ] Dynamic sites use Playwright path
- [ ] Ollama LLM extraction works reliably
- [ ] CSV output contains all required fields
- [ ] VM deployment documentation is accurate
