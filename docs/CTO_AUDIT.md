## 1. Executive Summary (CTO-Facing | 30–45 seconds read)

- **What this is**: A Python-based internal tool to **scrape corporate websites (depth=1)** and extract **Products, Services, Customers, Partnerships, Case Studies** using a **local LLM via Ollama**.
- **Who it is for**: **Internal data pipeline / automation** (batch runs on a VM) to generate structured inputs for downstream “business report” generation (per meeting notes and repo plan docs).
- **High-level approach**: **Universal Playwright rendering via Scrapy + `scrapy-playwright`**, depth-limited crawling + link prioritization, then **LLM-based structured extraction**. A key architectural choice is **process isolation** (Scrapy runs in a subprocess) to avoid Twisted/asyncio event-loop conflicts.
- **Current status (reality-checked)**: **MVP / experimental**, not production-hardened. Core scraping works and includes health checks and logging, but there are **inconsistencies** between docs vs code paths, and some **implementation risks/bugs** that will matter in production runs.

---

## 2. Problem Statement & Original Intent

- **Original problem** (from meeting notes): Build an in-house “corporate information scraper” to reliably extract **Products, Services, Customers, Partnerships, Case Studies** at **crawl depth=1**, with **batch processing** on a VM, prioritizing **accuracy over speed** (see `.cursor/plans/meeting-notes-raw.txt`).
- **Why this approach** (observable from repo planning + implementation):
  - External scraping tools previously failed at harder categories (customers/partners/case studies) → justification for **browser rendering + LLM extraction** (see `.cursor/plans/research-&-design.plan.md`).
  - The codebase explicitly moved to **universal Playwright** (browser for all sites) to reduce routing errors (see `main.py`, `company_info_scraper/agents/scraping_agent.py`, `company_info_scraper/services/batch_processor.py`).

**Inferred**: The “agentic” framing (Google ADK + multiple agents) is primarily to structure the code and allow future ADK orchestration; the current CLI path operates without requiring ADK (see `company_info_scraper/agents/base_agent.py`, `company_info_scraper/workflows/scrape_workflow.py`).

---

## 3. Tech Stack & Tooling (With Reasoning)

### Language(s)

- **Python** – Primary implementation language for scraping, orchestration, and LLM integration (entry point: `main.py`).

### Frameworks

- **Scrapy** – Crawl orchestration, request scheduling, and spider lifecycle (see `company_info_scraper/spiders/scraper.py`, `company_info_scraper/settings.py`, `scrapy.cfg`).
- **Twisted Asyncio Reactor (`asyncioreactor`)** – Used to align Scrapy/Twisted with asyncio for Playwright integration (installed early in `main.py` and `company_info_scraper/agents/scraping_agent.py`).

### Libraries

- **`scrapy-playwright`** – Browser-based fetching with JavaScript rendering (see `company_info_scraper/settings.py` `DOWNLOAD_HANDLERS`, and spider requests in `company_info_scraper/spiders/scraper.py`).
- **Playwright (Chromium)** – Actual headless browser runtime used by `scrapy-playwright` (configured in `company_info_scraper/settings.py` via `PLAYWRIGHT_BROWSER_TYPE`, `PLAYWRIGHT_*` settings).
- **BeautifulSoup + lxml** – HTML parsing and text extraction / stripping (see `company_info_scraper/spiders/scraper.py`, `company_info_scraper/spiders/static_scraper.py`).
- **httpx** – HTTP client for “site detection” heuristics and static scraping (see `company_info_scraper/services/site_detector.py`, `company_info_scraper/spiders/static_scraper.py`).
- **PyYAML** – Loads runtime config from `config.yaml` (see `main.py`, `company_info_scraper/services/batch_processor.py`).

### Infra / Runtime Expectations

- **Ollama server** – Local LLM runtime reachable at `http://localhost:11434` (health checks in `company_info_scraper/health.py` and model config in `config.yaml`).

### External services / APIs

- **Ollama Python client (`ollama`)** – Used to call local models via `ollama.Client.chat()` (see `company_info_scraper/services/llm_service.py`).

### AI / LLM usage (Reality-checked)

- **LLM extraction** happens via `LLMExtractionService`:
  - Builds a prompt that requests a strict JSON object with keys `products`, `services`, `customers`, `partnerships`, `case_studies` (see `company_info_scraper/services/llm_service.py` `_build_prompt()`).
  - Parses model output using regex-based JSON extraction + `json.loads()` with small fixups (see `_parse_json_response()`).
  - Formats output into **string fields** (lists become `"; "`-joined strings; missing becomes `"N/A"`).

**Unknown / Needs Confirmation**: Whether Ollama JSON mode (`format: json`) is enabled anywhere. The current Ollama calls do **not** set a JSON mode parameter in code (`ollama.Client.chat(...)` is called without a JSON-format enforcement argument).

### Google ADK

- **Google ADK (`google-adk`)** – Present as a dependency and optional integration layer. Code uses defensive imports and can run without ADK (see `company_info_scraper/agents/base_agent.py`, `company_info_scraper/workflows/scrape_workflow.py`, `config.yaml` `adk.enabled: false`).

---

## 4. High-Level Architecture

### Major components (code-backed)

- **CLI / entry point**: `main.py`
- **Orchestration**: `company_info_scraper/agents/orchestrator_agent.py` (`OrchestratorAgent`)
- **Scraping**:
  - Primary (current): `company_info_scraper/spiders/scraper.py` (`FullPageSpider`) with Playwright
  - Legacy/alternate: `company_info_scraper/spiders/static_scraper.py` (`StaticScraper`)
- **Site classification (corporate vs non-corporate)**: `company_info_scraper/services/site_detector.py` (`detect_corporate*`)
- **LLM extraction**: `company_info_scraper/services/llm_service.py` and `company_info_scraper/agents/llm_extraction_agent.py`
- **Batch processing / concurrency**: `company_info_scraper/services/batch_processor.py` (`BatchProcessor`)
- **Deferred extraction queue**: `company_info_scraper/services/extraction_queue.py` (`ExtractionQueue`)
- **Observability**: logging (`company_info_scraper/logging_config.py`) + health checks (`company_info_scraper/health.py`)

### Data flow (actual code path)

```
input domain(s)
  └─> OrchestratorAgent (optional corporate classification + skip)
       └─> ScrapingAgent (runs Scrapy+Playwright in a subprocess)
            └─> FullPageSpider:
                 - fetch homepage via Playwright
                 - extract cleaned text
                 - select up to 4 prioritized internal links (depth=1)
                 - fetch selected links via Playwright
            └─> return raw_data: [{url, raw_text}, ...]
       └─> LLMExtractionAgent -> LLMExtractionService (Ollama) per page
            └─> structured fields + extraction_status
  └─> CSV output (main + per-domain CSV files)
```

### Sync vs async behavior

- **Scrapy + Playwright**: async internals, but the primary `ScrapingAgent.execute()` is called synchronously from the orchestrator/CLI.
- **Critical architectural detail**: Scrapy execution is **process-isolated**:
  - `ScrapingAgent._run_crawler()` spawns a subprocess that runs a small script with its own Twisted reactor and returns scraped items via a `.result.json` file (see `company_info_scraper/agents/scraping_agent.py`).
  - This directly addresses the Twisted “global reactor” / event-loop conflict described in `.cursor/plans/blockers-&-todo.md`.

---

## 5. Detailed Execution Flow (Step-by-Step)

1. **Entry point**
   - `main.py` is the primary CLI entry point (`if __name__ == '__main__': sys.exit(main())`).

2. **Reactor initialization**
   - `main.py` installs Twisted’s asyncio reactor early (`twisted.internet.asyncioreactor.install()`) before any Scrapy imports.

3. **Config load + logging**
   - Loads YAML from `--config` (default `config.yaml`) via `load_config()`.
   - Configures logging via `company_info_scraper/logging_config.py` (`setup_logging()`), supports text or JSON logs.

4. **Mode selection**
   - **Health checks**: `python main.py --health` runs `company_info_scraper/health.py`.
   - **Process queue**: `python main.py --process-queue ...` reads a saved queue and runs LLM extraction (see `main.py` `run_process_queue()` and `company_info_scraper/services/extraction_queue.py`).
   - **Single domain**: `python main.py example.com` → `run_single_mode()`.
   - **Batch**: `python main.py --batch domains.txt [--parallel]` → `run_batch_mode()`.
   - **Deferred LLM**: `--defer-llm` skips extraction and writes queue items to disk (see `main.py` `run_single_mode_deferred()` / `run_batch_mode_deferred()`).

5. **Orchestration and decision points**
   - `OrchestratorAgent.execute()` does **corporate site classification** via `SiteDetector.detect_corporate_sync()` (see `company_info_scraper/agents/orchestrator_agent.py`).
   - If site_type != `corporate`, it returns a single record marked `extraction_status: skipped` and does not scrape further.
   - **Scraper choice**: despite tool/docs saying dual-path, it is currently forced:
     - `OrchestratorAgent` sets `self.force_scraper = 'dynamic'` and `auto_detect = False` (see `company_info_scraper/agents/orchestrator_agent.py`).
     - `main.py` also sets `agent_config['force_scraper'] = 'dynamic'` and `auto_detect: False` regardless of `config.yaml`.

6. **Scraping**
   - `ScrapingAgent.execute()` calls `_run_crawler(domain)` which:
     - Creates a temporary Python script.
     - Runs it via `subprocess.run([sys.executable, script_file])`.
     - The subprocess executes `CrawlerProcess().crawl(FullPageSpider, domain=...)` and collects items from `spider_ref[0].collected_items`.
     - Parent reads `output_file.result.json` and returns `raw_data` to the orchestrator (see `company_info_scraper/agents/scraping_agent.py`).

7. **Spider behavior (depth=1 + prioritization)**
   - `FullPageSpider` (`company_info_scraper/spiders/scraper.py`):
     - Normalizes domain to `https://...` and sets `start_urls` to homepage.
     - Uses Playwright persistent context (`PLAYWRIGHT_DEFAULT_CONTEXT_NAME = 'persistent'`).
     - Extracts text by loading `page.content()`, removing `script/style/nav/footer`, and calling `soup.get_text(...)`.
     - Truncates `raw_text` to 5000 chars.
     - On depth 0, selects up to **4** internal links prioritizing customers/partners/case-studies, and prefers nav links; stops after depth 1.

8. **LLM extraction**
   - For each scraped page, `LLMExtractionAgent.execute()` calls `LLMExtractionService.extract_sync()` (see `company_info_scraper/agents/llm_extraction_agent.py`).
   - The service calls Ollama and attempts to parse strict JSON into fields; it sets `status` to `success` if any field is non-`N/A` (see `company_info_scraper/services/llm_service.py` `_determine_status()`).

9. **Output generation**
   - `main.py` writes:
     - A **main CSV** (append mode)
     - A **domain-specific CSV** (`{domain}_output_data.csv`) (overwrite mode)
   - Implemented in `save_domain_results()` and `save_batch_results()` (see `main.py`).

---

## 6. Key Features Implemented (Reality-Checked)

- **Universal Playwright scraping (implemented)**:
  - Orchestrator and batch processor log “universal Playwright” and force `dynamic` (see `main.py`, `company_info_scraper/agents/orchestrator_agent.py`, `company_info_scraper/services/batch_processor.py`).
  - **Limitation**: README still describes “dual-path” as primary (see `README.md`). Code behavior contradicts that (see “Gaps & Risks”).

- **Depth=1 crawling with smart link prioritization (implemented)**:
  - `FullPageSpider` follows links only when `depth == 0` and sets `depth=depth+1` on follow requests (see `company_info_scraper/spiders/scraper.py`).
  - Prioritizes `/customers`, `/partners`, `/case-studies` patterns and prefers nav links.
  - **Limitation**: skip list includes `/contact`, which may reduce corporate signals / relevant content for some sites.

- **Corporate vs non-corporate site classification (implemented, but not universally applied)**
  - `OrchestratorAgent.execute()` runs `detect_corporate_sync()` and skips non-corporate with `extraction_status=skipped` (see `company_info_scraper/agents/orchestrator_agent.py`).
  - **Partial / Incomplete**: the parallel batch path (`execute_batch_async` via `BatchProcessor`) does **not** call corporate detection before scraping (see `company_info_scraper/services/batch_processor.py`).

- **LLM extraction via local Ollama (implemented)**
  - Prompt-based JSON extraction with retries and formatting (see `company_info_scraper/services/llm_service.py`).
  - **Limitation**: JSON parsing is regex-based and may accept malformed/partial JSON or fail on nested structures.

- **Deferred extraction queue (implemented)**
  - `--defer-llm` writes queue files; `--process-queue` processes them into CSV (see `main.py`, `company_info_scraper/services/extraction_queue.py`).
  - **Limitation / inconsistency**: batch deferred mode uses `StaticScraper` directly (see `main.py` `run_batch_mode_deferred()`), which conflicts with “universal Playwright” intent.

- **Health checks and logging (implemented)**
  - `--health` checks Ollama connectivity/model, imports, config, disk, output dir (see `company_info_scraper/health.py`).
  - Logging supports JSON/text + log file output (see `company_info_scraper/logging_config.py`).

- **Google ADK compatibility hooks (implemented, optional)**
  - Agents expose tools and can be wrapped into ADK `FunctionTool`s if ADK is installed (see `company_info_scraper/agents/base_agent.py`).
  - Workflow runner exists with ADK fallback, but ADK is disabled by default in `config.yaml`.

---

## 7. Configuration & Environment

### Config files

- **Runtime config**: `config.yaml`
  - `ollama_model`, `ollama_timeout`, `max_text_length`, logging settings, batch concurrency/rate limiting, queue dir, ADK flags.
  - **Important reality**: some config flags are ignored by the CLI path:
    - `auto_detect` is described as “ignored” in `config.yaml`, and `main.py` forces `force_scraper='dynamic'`.

- **Scrapy config**: `company_info_scraper/settings.py`
  - Playwright setup, persistent context, resource blocking, depth limit, pipeline selection.

### Environment variables (logging)

- `LOG_FORMAT`, `LOG_LEVEL`, `LOG_FILE` (see `company_info_scraper/logging_config.py`).

### Runtime requirements (local/VM)

- Python dependencies: `requirements.txt` (Scrapy, `scrapy-playwright`, `ollama`, `httpx`, etc.)
- Playwright browsers installed (documented in `README.md` and `RUN_GUIDE.md`).
- Ollama installed and running:
  - helper: `start_ollama.sh`
  - health check: `python main.py --health`

### How to run (repo-backed)

- **Single domain (preferred)**:
  - `python main.py example.com`
- **Batch**:
  - `python main.py --batch domains.txt`
  - `python main.py --batch domains.txt --parallel --max-concurrent 5`
- **Deferred LLM**:
  - `python main.py --batch domains.txt --defer-llm`
  - `python main.py --process-queue /tmp/scraper_queue_*.json --output results.csv`
- **Scrapy direct** (bypasses `main.py` orchestration):
  - `scrapy crawl fullpage -a domain=example.com` (see `RUN_GUIDE.md`, `run_scraper.sh`)

---

## 8. Known Blockers, Gaps & Risks

### Blocker resolved (repo-documented and code-implemented)

- **Twisted reactor / event loop deadlock when embedding Scrapy**  
  - **What**: Scrapy’s reactor lifecycle conflicts with already-running async orchestration; spider can initialize but never schedule requests.
  - **Why it matters**: Silent stalls in production, no output, hard to debug.
  - **Fix implemented**: Run Scrapy crawler in a **subprocess** with isolated interpreter/reactor (see `company_info_scraper/agents/scraping_agent.py` `_run_crawler()`; aligns with `.cursor/plans/blockers-&-todo.md`).

### Gaps / risks (code-backed)

- **Docs vs reality mismatch: “dual-path static/dynamic” vs forced universal Playwright**
  - `README.md` describes auto-detect and dual-path; `main.py` and `OrchestratorAgent` force `dynamic` and disable detection.
  - **Impact**: Confuses operators and reviewers; can lead to incorrect expectations about performance and routing.

- **Parallel batch path bypasses corporate classification**
  - `OrchestratorAgent.execute()` performs corporate skipping.
  - `OrchestratorAgent.execute_batch_async()` delegates to `BatchProcessor`, which currently does **not** run `detect_corporate*` before scraping.
  - **Impact**: In `--parallel` batch runs, non-corporate sites may be scraped/processed, wasting time and polluting output.

- **Potential bug in `BatchProcessor._scrape_dynamic()`**
  - It constructs `ScrapingAgent(config=self.config)`, but `BatchProcessor.__init__` does not define `self.config`.
  - **Impact**: Parallel batch processing may crash at runtime depending on call path (see `company_info_scraper/services/batch_processor.py`).

- **Hardcoded debug logging path inside the spider**
  - `FullPageSpider` writes to `/home/vishank/projects/company-info-scraper/.cursor/debug.log` (see `company_info_scraper/spiders/scraper.py`).
  - **Impact**: Breaks on VMs/other environments, leaks local paths, and may fail with permission errors.

- **Extraction output typing is “stringy”**
  - LLM prompt requests arrays or `"N/A"`, but the service formats lists into a single semicolon-delimited string.
  - **Impact**: Downstream consumers expecting structured arrays must re-parse strings.

- **LLM JSON robustness is limited**
  - Regex-based JSON extraction may behave unpredictably with nested braces or extra commentary.
  - **Impact**: Non-deterministic extraction failures; harder to enforce schema correctness.

- **Deferred batch mode uses static scraper**
  - `run_batch_mode_deferred()` uses `StaticScraper` (see `main.py`), which conflicts with “universal Playwright” intent.
  - **Impact**: Deferred batch mode may miss JS-rendered content, lowering extraction quality for important fields.

---

## 9. Future Work & Recommended Next Steps

### Short-term fixes (1–3 days)

- **Align “what runs” with documentation**
  - Update `README.md` to reflect **forced universal Playwright** in `main.py` (or re-enable true auto-detect if that’s desired).
- **Fix `BatchProcessor` config usage**
  - Ensure `BatchProcessor` can instantiate `ScrapingAgent` with correct config (or avoid agent instantiation and call a stable scraping entry point).
- **Remove hardcoded debug logging path**
  - Replace with standard logging, or gate behind an env var and use relative paths.
- **Ensure corporate classification applies to parallel batch**
  - Apply `detect_corporate` step before scraping in `BatchProcessor` (or in `execute_batch_async` before task scheduling).

### Medium-term improvements

- **Schema enforcement**
  - Add a strict schema layer (e.g., Pydantic) and retries on schema violations; reduce regex parsing reliance.
- **Better “suspicious empty” detection**
  - Distinguish “no data exists” vs “LLM failed / content not captured” (some of this is described in `.cursor/plans/research-&-design.plan.md` but not fully implemented).
- **Operational controls**
  - Per-domain timeouts and better error taxonomy (blocked, timeout, empty, parse error).

### Architectural refactors (if needed)

- **Single-source-of-truth workflow**
  - Consolidate around either:
    - `main.py` + `OrchestratorAgent` as the “production path”, or
    - `workflows/scrape_workflow.py` as the canonical workflow,
  - Then remove/clearly mark legacy paths (static scraper, unused pipelines) to reduce confusion.

---

## 10. Honest Assessment

### What’s solid

- **Correct fix for Scrapy/async conflict** via subprocess isolation (this is a real production-grade pattern).
- **Depth=1 strategy + prioritized link selection** is implemented and aligns with stated requirements.
- **Health checks + structured logging** are present and useful for VM ops.

### What’s fragile

- **Inconsistent behavior across modes** (single vs batch parallel vs deferred) creates correctness risk and makes outcomes hard to reason about.
- **LLM output parsing** is not schema-enforced and may be brittle under real-world variability.
- **Hardcoded local paths** in the spider are a deployment landmine.

### Questions a CTO is likely to ask next (and current answers)

- **“Is this production-ready for 24/7 VM batch runs?”**  
  - **No** (MVP). Core works, but parallel batch correctness and deployment hygiene need tightening.
- **“Do we reliably skip non-corporate sites?”**  
  - **Sometimes**: yes in `OrchestratorAgent.execute()`; **not guaranteed** in parallel batch (`BatchProcessor`) without further work.
- **“How do we prove accuracy?”**  
  - There is a test harness and a CSV validator (see `tests/test_e2e_validation.py`, `validate_output.py`), but accuracy thresholds and stability are not guaranteed without a controlled gold dataset and schema enforcement.


