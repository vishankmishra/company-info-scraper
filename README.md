# Company Info Scraper

An agentic AI-powered web scraper that extracts corporate data (Products/Services, Customers, Partnerships, and Case Studies) from company websites using Google ADK-compatible agent orchestration, intelligent dual-path scraping (static + dynamic), and local LLMs via Ollama for intelligent data extraction.

## ✨ Key Features

- **🔍 Dual-Path Scraping**: Automatically detects static vs dynamic sites
  - Static sites → Fast HTTP scraping (BeautifulSoup)
  - Dynamic sites → Browser-based scraping (Playwright)
- **⚡ Parallel Processing**: Process multiple domains concurrently
- **🤖 Google ADK Integration**: Full ADK-compatible agent architecture
- **🔄 Intelligent Retry**: Exponential backoff for LLM calls
- **📊 Production Ready**: Health checks, graceful shutdown, JSON logging
- **🎯 Structured Extraction**: Products, Customers, Partnerships, Case Studies

## Overview

This tool automates the extraction of critical corporate information:
- **Products/Services**: What the company offers
- **Customers**: Client names, testimonials, customer logos
- **Partnerships**: Strategic alliances, integration partners
- **Case Studies**: Customer success stories, implementations

## Architecture

The system uses a multi-agent architecture compatible with Google ADK:

```
┌─────────────────────────────────────────────────────────────┐
│                    OrchestratorAgent                        │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  SiteDetector   │→ │ScrapingAgent │→ │LLMExtraction  │  │
│  │  (static/dyn)   │  │(BS4/Playwright)│ │   Agent       │  │
│  └─────────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │  BatchProcessor │ (parallel domains)
                    └─────────────────┘
```

### Agents

1. **OrchestratorAgent**: Coordinates workflow, handles site detection routing
2. **ScrapingAgent**: Dual-path scraping (static: httpx+BS4, dynamic: Playwright)
3. **LLMExtractionAgent**: Processes text through Ollama with retry logic
4. **SiteDetector**: Analyzes sites to choose optimal scraper

## Prerequisites

- Python 3.9+
- Ollama installed and running locally
- Playwright browsers installed
- Virtual environment (recommended)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd company-info-scraper
```

### 2. Set Up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install
```

### 5. Install and Start Ollama

**Install Ollama:**
- Linux/Mac: `curl https://ollama.ai/install.sh | sh`
- Windows: Download from https://ollama.ai/download

**Start Ollama Server:**
```bash
ollama serve
```

**Pull Required Model:**
```bash
ollama pull llama3
```

## Usage

### Health Check (Verify Setup)

```bash
# Basic health check
python main.py --health

# Verbose with details
python main.py --health --health-verbose

# JSON output (for monitoring)
python main.py --health --json
```

### Single Domain

```bash
# Auto-detect scraper type (recommended)
python main.py example.com

# Force static scraper (fast)
python main.py example.com --scraper static

# Force dynamic scraper (JavaScript sites)
python main.py example.com --scraper dynamic
```

### Batch Processing

```bash
# Sequential processing
python main.py --batch domains.txt

# Parallel processing (faster!)
python main.py --batch domains.txt --parallel

# Parallel with custom concurrency
python main.py --batch domains.txt --parallel --max-concurrent 10
```

Create `domains.txt` with one domain per line:
```
example.com
another-company.com
https://www.third-company.com
```

### JSON Logging (Production)

```bash
# JSON format for log aggregation
python main.py --batch domains.txt --log-format json

# With log file
python main.py example.com --log-format json --log-file logs/scrape.log
```

### Using the Workflow API

```python
from company_info_scraper import run_scrape_workflow, ScrapeWorkflowConfig

# Simple usage
result = run_scrape_workflow('example.com')

# With configuration
config = ScrapeWorkflowConfig(
    auto_detect=True,       # Auto-detect static/dynamic
    max_concurrent=5,       # Parallel domains
    llm_timeout=90,         # LLM timeout in seconds
    output_format='csv'     # Output format
)

result = run_scrape_workflow(
    ['example.com', 'test.com'],
    config=config,
    output_file='results.csv'
)

print(f"Scraped {result.successful}/{result.total_domains} domains")
print(f"Static: {result.static_scraped}, Dynamic: {result.dynamic_scraped}")
```

### Using Google ADK

```python
from company_info_scraper.workflows.scrape_workflow import create_adk_scrape_agent
from company_info_scraper.agents import is_adk_available

if is_adk_available():
    agent = create_adk_scrape_agent()
    
    # Use with ADK Runner
    from google.adk import Runner
    runner = Runner(agent=agent)
    result = runner.run("Scrape example.com for company information")
```

## Configuration

Create `config.yaml` in the project root:

```yaml
# Ollama Configuration
ollama_model: llama3          # Options: llama3, mistral, llama2
ollama_timeout: 90            # Timeout in seconds (90s recommended)
ollama_max_retries: 3         # Retry failed LLM calls

# Scraping Configuration
max_text_length: 5000         # Max characters to send to LLM
download_delay: 0.5           # Delay between requests
depth_limit: 1                # Crawl depth (0 = root only)
auto_detect: true             # Auto-detect static/dynamic sites

# Batch Processing
batch:
  max_concurrent: 5           # Parallel domain processing
  rate_limit_delay: 1.0       # Delay between domain starts
  timeout_per_domain: 120     # Max time per domain
  retry_failed: true          # Retry failed domains
  max_retries: 2              # Max retries per domain

# Rate Limiting
rate_limiting:
  enabled: true
  requests_per_second: 2.0
  burst_size: 5
  per_domain_delay: 1.0

# Logging
log_level: INFO               # DEBUG, INFO, WARNING, ERROR
log_format: text              # text or json
log_file: logs/scraper.log

# Output
output_file: output_data.csv
```

## CLI Options

```
usage: main.py [-h] [--batch FILE] [--parallel] [--max-concurrent N]
               [--scraper {auto,static,dynamic}] [--config CONFIG]
               [--output OUTPUT] [--model MODEL] [--health] [--health-verbose]
               [--json] [--log-format {text,json}] [--log-file LOG_FILE]
               [-v] [-q]
               [domain]

Options:
  domain                Domain or URL to scrape
  --batch FILE          Batch file with domains (one per line)
  --parallel            Enable parallel processing
  --max-concurrent N    Max concurrent domains (default: 5)
  --scraper TYPE        Force scraper: auto, static, dynamic
  --config CONFIG       Config file path (default: config.yaml)
  --output OUTPUT       Output CSV file (default: output_data.csv)
  --model MODEL         Ollama model override
  --health              Run health checks and exit
  --health-verbose      Verbose health check output
  --json                JSON output (for health checks)
  --log-format TYPE     Log format: text or json
  --log-file PATH       Log file path
  -v, --verbose         Enable DEBUG logging
  -q, --quiet           Enable WARNING level only
```

## Output Format

The scraper generates a CSV file with these columns:

| Column | Description |
|--------|-------------|
| `url` | Scraped page URL |
| `products` | Extracted products/services |
| `customers` | Extracted customer names |
| `partnerships` | Extracted partnerships |
| `case_studies` | Extracted case studies |
| `extraction_status` | "success" or "failure" |
| `scraper_type` | "static" or "dynamic" |

## Project Structure

```
company-info-scraper/
├── company_info_scraper/
│   ├── agents/                # Google ADK-compatible agents
│   │   ├── base_agent.py      # ADK base with tool registration
│   │   ├── scraping_agent.py  # Dual-path scraping
│   │   ├── llm_extraction_agent.py
│   │   └── orchestrator_agent.py
│   ├── services/              # Core services
│   │   ├── llm_service.py     # Async LLM with retry
│   │   ├── site_detector.py   # Static/dynamic detection
│   │   ├── batch_processor.py # Parallel processing
│   │   └── extraction_queue.py
│   ├── spiders/
│   │   ├── scraper.py         # Playwright spider
│   │   └── static_scraper.py  # httpx+BeautifulSoup
│   ├── workflows/             # ADK workflows
│   │   └── scrape_workflow.py
│   ├── health.py              # Health checks
│   ├── logging_config.py      # JSON/text logging
│   ├── pipelines.py
│   ├── items.py
│   └── settings.py
├── tests/
│   ├── test_integration.py    # E2E tests
│   ├── test_health.py
│   └── test_adk_*.py
├── main.py                    # CLI entry point
├── config.yaml
└── requirements.txt
```

## Performance

| Scenario | Time | Notes |
|----------|------|-------|
| Single static domain | ~5-10s | Fast HTTP scraping |
| Single dynamic domain | ~20-30s | Browser + JS rendering |
| 5 domains (parallel) | ~30-60s | With auto-detection |
| 10 domains (parallel) | ~60-90s | max_concurrent=5 |
| LLM extraction per page | ~5-15s | Depends on text length |

## Testing

### Run Tests

```bash
# Quick tests (no network/LLM required)
python tests/test_integration.py --quick

# Full integration tests
python tests/test_integration.py --full

# Using pytest
pytest tests/ -v
pytest tests/test_integration.py -v -m "not slow"
```

### Validate Output

```bash
python validate_output.py output_data.csv
```

## Troubleshooting

### Health Check Fails

```bash
# Run verbose health check
python main.py --health --health-verbose

# Common issues:
# - Ollama not running: ollama serve
# - Model not pulled: ollama pull llama3
# - Missing dependencies: pip install -r requirements.txt
```

### Ollama Connection Errors

```bash
# Start Ollama
ollama serve

# Check if running
curl http://localhost:11434/api/tags

# Pull model if missing
ollama pull llama3
```

### All Results Show N/A

1. Increase `ollama_timeout` to 90-120 seconds
2. Check Ollama logs for errors
3. Try a different model: `ollama pull mistral`
4. Verify website has the expected content

### Graceful Shutdown

During batch processing, press `Ctrl+C` once to:
- Complete current domain(s)
- Save partial results
- Exit cleanly

Press `Ctrl+C` twice to force immediate exit.

## Google ADK Integration

The agents are fully ADK-compatible:

```python
from company_info_scraper.agents import (
    OrchestratorAgent,
    create_adk_workflow,
    is_adk_available
)

# Check ADK availability
if is_adk_available():
    # Create ADK workflow with all tools
    workflow = create_adk_workflow({'auto_detect': True})
    
    # Get individual agent tools
    orchestrator = OrchestratorAgent()
    tools = orchestrator.get_adk_tools()
    
    # Tools available:
    # - scrape_and_extract: Complete workflow
    # - batch_scrape_and_extract: Parallel batch
    # - detect_site_type: Site analysis
    # - scrape_website: Web scraping only
    # - extract_company_info: LLM extraction only
```

## License

[Add your license here]

## Support

- Check `--health` output for system status
- Review logs: `logs/scraper.log`
- Run tests: `python tests/test_integration.py --quick`
- See [DEPLOYMENT.md](DEPLOYMENT.md) for VM deployment
- See [QUICKSTART.md](QUICKSTART.md) for quick start guide
