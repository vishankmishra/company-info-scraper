#!/bin/bash
# Comprehensive Test Runner for Company Info Scraper
# Runs all test suites: unit, integration, and E2E validation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Parse arguments
QUICK_MODE=false
UNIT_ONLY=false
E2E_ONLY=false
SKIP_OLLAMA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --unit-only)
            UNIT_ONLY=true
            shift
            ;;
        --e2e-only)
            E2E_ONLY=true
            shift
            ;;
        --skip-ollama)
            SKIP_OLLAMA=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick        Run quick tests only (2 domains)"
            echo "  --unit-only    Run unit tests only (no network/LLM)"
            echo "  --e2e-only     Run E2E tests only"
            echo "  --skip-ollama  Skip tests requiring Ollama"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run all tests"
            echo "  $0 --quick            # Quick test run"
            echo "  $0 --unit-only        # Unit tests only"
            echo "  $0 --e2e-only --quick # Quick E2E test"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}Company Info Scraper - Test Suite${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
python3 --version
echo ""

# Check if Ollama is running
OLLAMA_AVAILABLE=false
if python3 -c "from company_info_scraper.health import check_ollama; exit(0 if check_ollama() else 1)" 2>/dev/null; then
    OLLAMA_AVAILABLE=true
    echo -e "${GREEN}✓ Ollama is running${NC}"
else
    echo -e "${RED}✗ Ollama is not running${NC}"
    if [ "$SKIP_OLLAMA" = false ] && [ "$UNIT_ONLY" = false ]; then
        echo "  Tests requiring LLM will be skipped or may fail"
        echo "  Start Ollama: ollama serve && ollama pull llama3"
    fi
fi
echo ""

# Track test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test and track results
run_test() {
    local test_name="$1"
    shift
    local test_cmd="$@"
    
    echo -e "${BLUE}----------------------------------------------------------------------${NC}"
    echo -e "${BLUE}Running: $test_name${NC}"
    echo -e "${BLUE}----------------------------------------------------------------------${NC}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if eval "$test_cmd"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Run tests based on mode
if [ "$UNIT_ONLY" = true ]; then
    echo -e "${YELLOW}Running unit tests only...${NC}"
    echo ""
    
    run_test "Health Checks" "python3 main.py --health --json"
    run_test "Integration Tests (Quick)" "python3 tests/test_integration.py --quick"
    
elif [ "$E2E_ONLY" = true ]; then
    echo -e "${YELLOW}Running E2E tests only...${NC}"
    echo ""
    
    if [ "$QUICK_MODE" = true ]; then
        run_test "E2E Validation (Quick)" "python3 tests/test_e2e_simple.py --quick"
    else
        run_test "E2E Validation (Full)" "python3 tests/test_e2e_simple.py"
    fi
    
else
    # Run all tests
    echo -e "${YELLOW}Running full test suite...${NC}"
    echo ""
    
    # 1. Health checks
    run_test "Health Checks" "python3 main.py --health --json"
    
    # 2. Unit/Integration tests (quick mode)
    run_test "Integration Tests (Quick)" "python3 tests/test_integration.py --quick"
    
    # 3. ADK tests
    if [ -f "tests/test_adk_installation.py" ]; then
        run_test "ADK Installation" "python3 tests/test_adk_installation.py"
    fi
    
    # 4. E2E validation
    if [ "$OLLAMA_AVAILABLE" = true ]; then
        if [ "$QUICK_MODE" = true ]; then
            run_test "E2E Validation (Quick)" "python3 tests/test_e2e_simple.py --quick"
        else
            # For full test, use quick mode by default to keep it fast
            run_test "E2E Validation" "python3 tests/test_e2e_simple.py --quick"
        fi
    else
        echo -e "${YELLOW}⚠ Skipping E2E tests (Ollama not available)${NC}"
    fi
fi

# Print summary
echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo -e "Total tests run: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED_TESTS${NC}"
else
    echo -e "Failed: $FAILED_TESTS"
fi

SUCCESS_RATE=0
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
fi
echo -e "Success rate: ${SUCCESS_RATE}%"

echo -e "${BLUE}======================================================================${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    exit 1
fi

