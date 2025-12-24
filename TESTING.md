# Testing Guide

## Overview

Comprehensive test suite for the Company Info Scraper, covering unit tests, integration tests, and end-to-end validation.

## Test Structure

```
tests/
├── test_integration.py      # Core integration tests + edge cases
├── test_e2e_validation.py   # Comprehensive E2E with detailed validation
├── test_e2e_simple.py       # Simple E2E via CLI (no reactor conflicts)
├── test_health.py           # Health check tests
├── test_adk_*.py            # Google ADK tests
└── test_domains.txt         # Test domain list
```

## Quick Start

### 1. Run All Tests
```bash
./run_tests.sh
```

### 2. Unit Tests Only (Fast)
```bash
./run_tests.sh --unit-only
```

### 3. E2E Tests Only
```bash
./run_tests.sh --e2e-only --quick
```

## Test Categories

### Unit Tests
**File**: `test_integration.py --quick`  
**Duration**: ~5 seconds  
**Requirements**: None (no network or Ollama needed)

Tests:
- ✓ Module imports
- ✓ Class initialization
- ✓ Agent registry
- ✓ Workflow configuration

```bash
python tests/test_integration.py --quick
```

### Integration Tests
**File**: `test_integration.py --full`  
**Duration**: ~30-60 seconds  
**Requirements**: Network access + Ollama running

Tests:
- ✓ Site detection (static vs dynamic)
- ✓ Static scraping (httpx + BeautifulSoup)
- ✓ LLM extraction
- ✓ Full workflow execution
- ✓ Batch processing

```bash
python tests/test_integration.py --full
```

### Edge Case Tests
**File**: `test_integration.py` (TestEdgeCases)  
**Duration**: ~20-40 seconds  
**Requirements**: Network + Ollama

Tests:
- ✓ Invalid domain handling
- ✓ Timeout handling
- ✓ Empty content handling
- ✓ Mixed static/dynamic batch processing

```bash
pytest tests/test_integration.py::TestEdgeCases -v
```

### End-to-End Validation
**File**: `test_e2e_simple.py`  
**Duration**: ~60-180 seconds (depends on domain count)  
**Requirements**: Network + Ollama

**Test Domains (5 total):**
1. `example.com` - Simple static baseline
2. `httpbin.org` - Static with product info
3. `stripe.com` - Dynamic FinTech (rich data)
4. `shopify.com` - Enterprise e-commerce
5. `mongodb.com` - Tech company with partnerships

**Success Criteria:**
- Combined success rate >60%
- Success rate = (extraction_success_rate + data_quality_score) / 2
- Data quality = % of records with ≥2 non-N/A fields

```bash
# Full 5-domain test
python tests/test_e2e_simple.py

# Quick 2-domain test
python tests/test_e2e_simple.py --quick

# Custom target success rate
python tests/test_e2e_simple.py --target 70
```

### Health Checks
**File**: `main.py --health`  
**Duration**: ~1-2 seconds

Checks:
- ✓ Ollama connectivity
- ✓ Model availability
- ✓ Dependencies (scrapy, bs4, httpx, yaml, ollama)
- ✓ Configuration validity
- ✓ Disk space
- ✓ Output directory writable

```bash
# Simple health check
python main.py --health

# JSON output
python main.py --health --json

# Detailed verbose output
python main.py --health --health-verbose
```

## Test Runner Script

The `run_tests.sh` script provides a unified test execution interface.

### Options

```bash
./run_tests.sh [OPTIONS]

Options:
  --quick        Run quick tests only (2 domains)
  --unit-only    Run unit tests only (no network/LLM)
  --e2e-only     Run E2E tests only
  --skip-ollama  Skip tests requiring Ollama
  --help         Show help message
```

### Examples

```bash
# Full test suite
./run_tests.sh

# Quick validation (fast, for CI/CD)
./run_tests.sh --quick --unit-only

# Only E2E tests with quick mode
./run_tests.sh --e2e-only --quick

# Skip Ollama-dependent tests
./run_tests.sh --skip-ollama
```

## Output Validation

### CSV Output Validation

Tests validate CSV output quality:

```python
# Validation metrics
stats = {
    'total_records': int,        # Number of scraped records
    'extraction_success': int,   # Successful LLM extractions
    'has_data': int,             # Records with ≥1 non-N/A field
    'rich_data': int,            # Records with ≥2 non-N/A fields
    'success_rate': float,       # % successful extractions
    'data_quality': float        # % with rich data
}
```

### Quality Thresholds

- **Good**: Data quality ≥70%
- **Acceptable**: Data quality ≥60%
- **Poor**: Data quality <60%

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Install Ollama
        run: |
          curl -fsSL https://ollama.ai/install.sh | sh
          ollama serve &
          sleep 5
          ollama pull llama3
      
      - name: Run unit tests
        run: ./run_tests.sh --unit-only
      
      - name: Run E2E tests (quick)
        run: ./run_tests.sh --e2e-only --quick
```

### Docker Testing

```dockerfile
# Dockerfile.test
FROM python:3.11-slim

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY . /app
WORKDIR /app

# Run tests
CMD ["./run_tests.sh", "--quick"]
```

```bash
# Build and run
docker build -f Dockerfile.test -t scraper-tests .
docker run --rm scraper-tests
```

## Troubleshooting

### Ollama Not Available

```bash
# Start Ollama
ollama serve

# Pull required model
ollama pull llama3

# Check if running
curl http://localhost:11434/api/tags
```

### Playwright Issues

```bash
# Install Playwright browsers
playwright install chromium

# Or install with dependencies
playwright install --with-deps chromium
```

### Pytest Not Found

```bash
# Install test dependencies
pip install pytest pytest-asyncio
```

### Twisted Reactor Errors

The `test_e2e_simple.py` test avoids reactor conflicts by running the scraper via CLI subprocess instead of importing directly.

If you encounter reactor errors:
1. Use `test_e2e_simple.py` instead of `test_e2e_validation.py`
2. Run tests in separate processes
3. Avoid mixing asyncio and Twisted in the same process

### Network Timeouts

```bash
# Increase timeout
python tests/test_e2e_simple.py --timeout 180

# Use quick mode for faster tests
python tests/test_e2e_simple.py --quick
```

## Test Maintenance

### Adding New Test Domains

Edit `tests/test_e2e_simple.py`:

```python
TEST_DOMAINS = [
    {
        'url': 'newdomain.com',
        'name': 'New Company',
        'expect_success': True
    },
    # ... existing domains
]
```

### Adjusting Success Thresholds

```bash
# Lower threshold for testing
python tests/test_e2e_simple.py --target 50

# Higher threshold for production
python tests/test_e2e_simple.py --target 80
```

### Adding New Test Cases

1. Add test to appropriate file (`test_integration.py`, `test_e2e_*.py`)
2. Use pytest decorators: `@pytest.mark.asyncio`, `@pytest.mark.slow`
3. Add skip conditions: `skip_if_no_ollama()`, `skip_if_no_network()`
4. Update `run_tests.sh` if needed

Example:

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_new_feature(self):
    """Test new feature."""
    skip_if_no_network()
    
    # Test implementation
    result = await my_feature()
    assert result is not None
```

## Performance Benchmarks

| Test Suite | Duration | Requirements |
|------------|----------|--------------|
| Unit tests | ~5s | None |
| Integration (quick) | ~10s | Network |
| Integration (full) | ~60s | Network + Ollama |
| E2E (2 domains) | ~60s | Network + Ollama |
| E2E (5 domains) | ~180s | Network + Ollama |
| Full suite | ~120s | Network + Ollama |

## Best Practices

1. **Run unit tests frequently** during development
2. **Run E2E tests** before commits
3. **Use quick mode** for fast iteration
4. **Run full suite** before releases
5. **Check health** after environment changes
6. **Monitor success rates** over time
7. **Update test domains** if sites change structure

## Additional Resources

- [README.md](README.md) - Project overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [scraper_plan.md](scraper_plan.md) - Implementation plan

