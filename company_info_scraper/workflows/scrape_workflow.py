"""
ADK Scrape Workflow - Coordinates scraping -> extraction -> output (PH5-S3)

This module defines the main ADK workflow for company information scraping.
It provides:
- ADK-native workflow definition
- Built-in retry and error handling
- Progress tracking and observability
- Both sync and async execution modes

The workflow coordinates:
1. Site type detection (static vs dynamic)
2. Web scraping (BeautifulSoup or Playwright)
3. LLM extraction (products, customers, partnerships, case studies)
4. Output generation (CSV, JSON)
"""

import asyncio
import csv
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union

# ADK imports - graceful fallback
try:
    from google.adk import Agent, Runner
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    Agent = object
    LlmAgent = None
    FunctionTool = None
    Runner = None

from company_info_scraper.agents import (
    OrchestratorAgent,
    ScrapingAgent,
    LLMExtractionAgent,
    is_adk_available,
)
from company_info_scraper.services import (
    SiteDetector,
    SiteType,
    BatchProcessor,
    LLMExtractionService,
)

logger = logging.getLogger(__name__)


@dataclass
class ScrapeWorkflowConfig:
    """Configuration for the scrape workflow."""
    
    # Site detection
    auto_detect: bool = True
    force_scraper: Optional[str] = None  # 'static', 'dynamic', or None
    
    # Concurrency
    max_concurrent: int = 5
    rate_limit_delay: float = 1.0
    
    # LLM settings
    llm_model: str = 'llama3'
    llm_timeout: int = 90
    llm_max_retries: int = 3
    max_text_length: int = 5000
    
    # Output settings
    output_format: str = 'csv'  # 'csv', 'json', or 'both'
    output_dir: str = '.'
    output_prefix: str = 'scrape_results'
    
    # ADK settings
    adk_model: str = 'gemini-2.0-flash'
    use_adk_orchestration: bool = True  # Use ADK if available
    
    # Callbacks
    on_domain_start: Optional[Callable[[str], None]] = None
    on_domain_complete: Optional[Callable[[str, Dict], None]] = None
    on_progress: Optional[Callable[[int, int, str], None]] = None


@dataclass
class DomainScrapeResult:
    """Result for a single domain scrape."""
    domain: str
    success: bool
    scraper_type: str = 'unknown'
    records_count: int = 0
    records: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ScrapeWorkflowResult:
    """Result from the complete workflow execution."""
    total_domains: int
    successful: int
    failed: int
    static_scraped: int
    dynamic_scraped: int
    total_elapsed_ms: float
    avg_time_per_domain_ms: float
    output_files: List[str] = field(default_factory=list)
    results: List[DomainScrapeResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_domains': self.total_domains,
            'successful': self.successful,
            'failed': self.failed,
            'static_scraped': self.static_scraped,
            'dynamic_scraped': self.dynamic_scraped,
            'total_elapsed_ms': self.total_elapsed_ms,
            'avg_time_per_domain_ms': self.avg_time_per_domain_ms,
            'output_files': self.output_files,
            'results': [
                {
                    'domain': r.domain,
                    'success': r.success,
                    'scraper_type': r.scraper_type,
                    'records_count': r.records_count,
                    'elapsed_ms': r.elapsed_ms,
                    'error': r.error
                }
                for r in self.results
            ]
        }


class ScrapeWorkflow:
    """
    ADK Workflow for company information scraping.
    
    This class orchestrates the complete scraping pipeline:
    1. Site detection - Determine if sites are static or dynamic
    2. Scraping - Use appropriate scraper (BeautifulSoup or Playwright)
    3. Extraction - Process text through LLM for structured data
    4. Output - Generate CSV/JSON output files
    
    Can run in two modes:
    - Native mode: Uses internal orchestration (works without ADK)
    - ADK mode: Uses ADK runtime for orchestration (requires google-adk)
    """
    
    def __init__(self, config: Optional[ScrapeWorkflowConfig] = None):
        self.config = config or ScrapeWorkflowConfig()
        self.logger = logging.getLogger(f"{__name__}.ScrapeWorkflow")
        
        # Initialize components
        self.site_detector = SiteDetector()
        self.llm_service = LLMExtractionService(
            model=self.config.llm_model,
            timeout=self.config.llm_timeout,
            max_retries=self.config.llm_max_retries,
            max_text_length=self.config.max_text_length
        )
        
        # Initialize orchestrator agent
        orchestrator_config = {
            'auto_detect': self.config.auto_detect,
            'force_scraper': self.config.force_scraper,
            'max_concurrent': self.config.max_concurrent,
            'ollama_model': self.config.llm_model,
            'ollama_timeout': self.config.llm_timeout,
            'max_retries': self.config.llm_max_retries,
            'max_text_length': self.config.max_text_length,
        }
        self.orchestrator = OrchestratorAgent(orchestrator_config)
        
        # ADK workflow agent (created lazily)
        self._adk_workflow = None
    
    def run(
        self, 
        domains: Union[str, List[str]],
        output_file: Optional[str] = None
    ) -> ScrapeWorkflowResult:
        """
        Run the scrape workflow synchronously.
        
        Args:
            domains: Single domain or list of domains to scrape
            output_file: Optional output file path (overrides config)
            
        Returns:
            ScrapeWorkflowResult with all results and output files
        """
        return asyncio.run(self.run_async(domains, output_file))
    
    async def run_async(
        self,
        domains: Union[str, List[str]],
        output_file: Optional[str] = None
    ) -> ScrapeWorkflowResult:
        """
        Run the scrape workflow asynchronously.
        
        Args:
            domains: Single domain or list of domains to scrape
            output_file: Optional output file path
            
        Returns:
            ScrapeWorkflowResult with all results and output files
        """
        # Normalize domains to list
        if isinstance(domains, str):
            domains = [domains]
        
        self.logger.info(f"Starting scrape workflow for {len(domains)} domains")
        start_time = time.time()
        
        # Choose execution mode
        if self.config.use_adk_orchestration and is_adk_available():
            self.logger.info("Using ADK orchestration mode")
            results = await self._run_with_adk(domains)
        else:
            self.logger.info("Using native orchestration mode")
            results = await self._run_native(domains)
        
        # Generate output files
        output_files = []
        if output_file:
            output_files.extend(self._write_output(results, output_file))
        elif self.config.output_format != 'none':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_path = Path(self.config.output_dir) / f"{self.config.output_prefix}_{timestamp}"
            output_files.extend(self._write_output(results, str(base_path)))
        
        # Calculate statistics
        total_elapsed = (time.time() - start_time) * 1000
        successful = sum(1 for r in results if r.success)
        static_count = sum(1 for r in results if r.scraper_type == 'static')
        dynamic_count = sum(1 for r in results if r.scraper_type == 'dynamic')
        
        workflow_result = ScrapeWorkflowResult(
            total_domains=len(domains),
            successful=successful,
            failed=len(results) - successful,
            static_scraped=static_count,
            dynamic_scraped=dynamic_count,
            total_elapsed_ms=total_elapsed,
            avg_time_per_domain_ms=total_elapsed / max(len(domains), 1),
            output_files=output_files,
            results=results
        )
        
        self.logger.info(
            f"Workflow complete: {successful}/{len(domains)} successful in "
            f"{total_elapsed/1000:.1f}s. Output: {output_files}"
        )
        
        return workflow_result
    
    async def _run_native(self, domains: List[str]) -> List[DomainScrapeResult]:
        """Run workflow using native Python orchestration."""
        results = []
        
        # Use batch processor for parallel execution
        batch_result = await self.orchestrator.execute_batch_async(
            domains,
            max_concurrent=self.config.max_concurrent
        )
        
        # Convert to DomainScrapeResult
        for r in batch_result.get('results', []):
            result = DomainScrapeResult(
                domain=r.get('domain', 'unknown'),
                success=r.get('success', False),
                scraper_type=r.get('scraper_type', 'unknown'),
                records_count=r.get('records_count', 0),
                records=r.get('records', []),
                elapsed_ms=r.get('elapsed_ms', 0),
                error=r.get('error')
            )
            results.append(result)
            
            # Callbacks
            if self.config.on_domain_complete:
                self.config.on_domain_complete(result.domain, r)
        
        return results
    
    async def _run_with_adk(self, domains: List[str]) -> List[DomainScrapeResult]:
        """Run workflow using ADK orchestration (PH5-S2: Complete ADK Runner integration).
        
        This method uses the ADK Runner to execute the workflow with:
        - Full observability and telemetry
        - ADK-native tool calling and orchestration
        - Session management and state tracking
        """
        if not is_adk_available():
            self.logger.warning("ADK not available, falling back to native mode")
            return await self._run_native(domains)
        
        try:
            # Create ADK workflow if not exists
            if self._adk_workflow is None:
                self._adk_workflow = self._create_adk_workflow()
            
            if self._adk_workflow is None:
                self.logger.warning("Failed to create ADK workflow, using native mode")
                return await self._run_native(domains)
            
            self.logger.info(f"Executing ADK workflow for {len(domains)} domains")
            
            # Use ADK Runner for actual execution
            from google.adk import Runner
            from google.adk.sessions import InMemorySessionService
            
            # Create session service for Runner
            session_service = InMemorySessionService()
            runner = Runner(
                app_name="CompanyInfoScraper",
                agent=self._adk_workflow, 
                session_service=session_service
            )
            results = []
            
            # Process each domain through ADK
            for i, domain in enumerate(domains, 1):
                self.logger.info(f"ADK processing [{i}/{len(domains)}]: {domain}")
                
                try:
                    # Create task prompt for ADK agent
                    task = f"Scrape and extract company information from {domain}"
                    
                    # Run through ADK with full orchestration
                    adk_result = runner.run(task)
                    
                    # Parse ADK result and convert to DomainScrapeResult
                    # ADK returns execution results that we need to interpret
                    domain_result = self._parse_adk_result(domain, adk_result)
                    results.append(domain_result)
                    
                    self.logger.info(f"ADK completed {domain}: {domain_result.records_count} records")
                    
                except Exception as e:
                    self.logger.error(f"ADK execution failed for {domain}: {e}")
                    # Create failed result
                    results.append(DomainScrapeResult(
                        domain=domain,
                        success=False,
                        scraper_type='unknown',
                        error=f"ADK execution error: {str(e)}"
                    ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"ADK Runner initialization failed: {e}, falling back to native")
            return await self._run_native(domains)
    
    def _parse_adk_result(self, domain: str, adk_result) -> DomainScrapeResult:
        """Parse ADK Runner result into DomainScrapeResult.
        
        Args:
            domain: The domain that was processed
            adk_result: Result from ADK Runner execution
            
        Returns:
            DomainScrapeResult with extracted data
        """
        try:
            # ADK result structure varies by version
            # Try to extract the result data
            if hasattr(adk_result, 'output'):
                output = adk_result.output
            elif hasattr(adk_result, 'result'):
                output = adk_result.result
            elif isinstance(adk_result, dict):
                output = adk_result
            else:
                output = str(adk_result)
            
            # Parse the output to extract records
            # The output should contain the scraped and extracted data
            import json
            
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except json.JSONDecodeError:
                    pass
            
            # Extract records from output
            records = []
            if isinstance(output, dict):
                if 'records' in output:
                    records = output['records']
                elif 'products' in output or 'customers' in output:
                    # Single record result
                    records = [output]
            
            return DomainScrapeResult(
                domain=domain,
                success=True,
                scraper_type='adk',
                records_count=len(records),
                records=records
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse ADK result for {domain}: {e}")
            return DomainScrapeResult(
                domain=domain,
                success=False,
                scraper_type='adk',
                error=f"Result parsing error: {str(e)}"
            )
    
    def _create_adk_workflow(self):
        """Create an ADK workflow agent."""
        return self.orchestrator.create_adk_workflow(model=self.config.adk_model)
    
    def _write_output(
        self, 
        results: List[DomainScrapeResult],
        base_path: str
    ) -> List[str]:
        """Write results to output files."""
        output_files = []
        
        # Flatten all records
        all_records = []
        for result in results:
            for record in result.records:
                record['source_domain'] = result.domain
                record['scraper_type'] = result.scraper_type
                all_records.append(record)
        
        if not all_records:
            self.logger.warning("No records to write")
            return output_files
        
        # Write CSV
        if self.config.output_format in ('csv', 'both'):
            csv_path = f"{base_path}.csv"
            self._write_csv(all_records, csv_path)
            output_files.append(csv_path)
        
        # Write JSON
        if self.config.output_format in ('json', 'both'):
            json_path = f"{base_path}.json"
            self._write_json(all_records, json_path)
            output_files.append(json_path)
        
        return output_files
    
    def _write_csv(self, records: List[Dict], path: str):
        """Write records to CSV file."""
        if not records:
            return
        
        # Get all unique keys
        fieldnames = set()
        for record in records:
            fieldnames.update(record.keys())
        fieldnames = sorted(fieldnames)
        
        # Ensure important fields come first
        priority_fields = ['url', 'source_domain', 'products', 'services', 'customers', 
                          'partnerships', 'case_studies', 'extraction_status']
        ordered_fields = []
        for f in priority_fields:
            if f in fieldnames:
                ordered_fields.append(f)
                fieldnames.remove(f)
        ordered_fields.extend(sorted(fieldnames))
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)
        
        self.logger.info(f"Wrote {len(records)} records to {path}")
    
    def _write_json(self, records: List[Dict], path: str):
        """Write records to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, default=str)
        
        self.logger.info(f"Wrote {len(records)} records to {path}")
    
    # =========================================================================
    # ADK Tool Methods (for use as tools in ADK agents)
    # =========================================================================
    
    def get_adk_tools(self) -> List[Any]:
        """Get ADK FunctionTool wrappers for workflow methods."""
        if not ADK_AVAILABLE or FunctionTool is None:
            return []
        
        tools = []
        
        try:
            # Create wrapper functions with proper names and docstrings
            def scrape_domain(domain: str) -> Dict[str, Any]:
                """Scrape a single domain and extract company information."""
                return self._tool_scrape_domain(domain)
            
            def batch_scrape(domains: List[str]) -> Dict[str, Any]:
                """Scrape multiple domains in parallel."""
                return self._tool_batch_scrape(domains)
            
            def detect_site(domain: str) -> Dict[str, Any]:
                """Detect if a website is static or dynamic."""
                return self._tool_detect_site(domain)
            
            # Create FunctionTools (ADK 1.19.0 API: only func parameter)
            tools.append(FunctionTool(func=scrape_domain))
            tools.append(FunctionTool(func=batch_scrape))
            tools.append(FunctionTool(func=detect_site))
            
        except Exception as e:
            self.logger.error(f"Failed to create ADK tools: {e}")
        
        return tools
    
    def _tool_scrape_domain(self, domain: str) -> Dict[str, Any]:
        """Tool: Scrape a single domain."""
        result = self.run([domain])
        if result.results:
            return result.results[0].__dict__
        return {'success': False, 'error': 'No result'}
    
    def _tool_batch_scrape(self, domains: List[str]) -> Dict[str, Any]:
        """Tool: Batch scrape multiple domains."""
        result = self.run(domains)
        return result.to_dict()
    
    def _tool_detect_site(self, domain: str) -> Dict[str, Any]:
        """Tool: Detect site type."""
        try:
            result = self.site_detector.detect_sync(domain)
            return {
                'domain': domain,
                'site_type': result.site_type.value,
                'confidence': result.confidence,
                'indicators': result.indicators
            }
        except Exception as e:
            return {'domain': domain, 'error': str(e)}


# =============================================================================
# Convenience Functions
# =============================================================================

def create_scrape_workflow(
    config: Optional[ScrapeWorkflowConfig] = None
) -> ScrapeWorkflow:
    """
    Create a new scrape workflow instance.
    
    Args:
        config: Workflow configuration (uses defaults if not provided)
        
    Returns:
        ScrapeWorkflow instance
    """
    return ScrapeWorkflow(config)


def run_scrape_workflow(
    domains: Union[str, List[str]],
    config: Optional[ScrapeWorkflowConfig] = None,
    output_file: Optional[str] = None
) -> ScrapeWorkflowResult:
    """
    Run the scrape workflow synchronously.
    
    Convenience function that creates a workflow and runs it.
    
    Args:
        domains: Domain(s) to scrape
        config: Workflow configuration
        output_file: Output file path
        
    Returns:
        ScrapeWorkflowResult
        
    Example:
        result = run_scrape_workflow(
            ['example.com', 'test.com'],
            config=ScrapeWorkflowConfig(auto_detect=True),
            output_file='results.csv'
        )
        print(f"Scraped {result.successful}/{result.total_domains} domains")
    """
    workflow = ScrapeWorkflow(config)
    return workflow.run(domains, output_file)


async def run_scrape_workflow_async(
    domains: Union[str, List[str]],
    config: Optional[ScrapeWorkflowConfig] = None,
    output_file: Optional[str] = None
) -> ScrapeWorkflowResult:
    """
    Run the scrape workflow asynchronously.
    
    Args:
        domains: Domain(s) to scrape
        config: Workflow configuration
        output_file: Output file path
        
    Returns:
        ScrapeWorkflowResult
        
    Example:
        result = await run_scrape_workflow_async(
            ['example.com', 'test.com'],
            config=ScrapeWorkflowConfig(max_concurrent=10)
        )
    """
    workflow = ScrapeWorkflow(config)
    return await workflow.run_async(domains, output_file)


# =============================================================================
# ADK Workflow Factory (for ADK runtime integration)
# =============================================================================

def create_adk_scrape_agent(
    config: Optional[ScrapeWorkflowConfig] = None,
    model: str = "gemini-2.0-flash"
):
    """
    Create an ADK LlmAgent for company scraping.
    
    This creates a fully-configured ADK agent that can be used with
    the ADK Runner for orchestrated execution.
    
    Args:
        config: Workflow configuration
        model: LLM model for agent reasoning
        
    Returns:
        ADK LlmAgent or None if ADK not available
        
    Example:
        agent = create_adk_scrape_agent()
        if agent:
            from google.adk import Runner
            runner = Runner(agent=agent)
            result = runner.run("Scrape example.com for company info")
    """
    if not is_adk_available():
        logger.warning("Google ADK not installed. Cannot create ADK agent.")
        return None
    
    try:
        from google.adk.agents import LlmAgent
        
        workflow = ScrapeWorkflow(config)
        tools = workflow.get_adk_tools()
        
        # Add orchestrator tools
        tools.extend(workflow.orchestrator.get_adk_tools())
        
        agent = LlmAgent(
            name="CompanyInfoScraper",
            model=model,
            instruction="""You are a company information scraper agent.

Your job is to scrape websites and extract structured business information:
- Products and services
- Customer base
- Business partnerships
- Case studies and success stories

## Available Tools

1. `scrape_domain` - Scrape a single website and extract info
2. `batch_scrape` - Scrape multiple websites in parallel (more efficient)
3. `detect_site` - Check if a site is static or dynamic before scraping
4. `scrape_and_extract` - Complete workflow for a domain
5. `batch_scrape_and_extract` - Batch workflow for multiple domains

## Best Practices

- For single domains, use `scrape_domain`
- For multiple domains, use `batch_scrape` for efficiency
- Use `detect_site` first if you need to know the site type
- Always return structured JSON results

## Output Format

Return results with these fields:
- products: What the company sells/offers
- customers: Who uses their products
- partnerships: Business relationships
- case_studies: Success stories
- extraction_status: 'success' or 'failure'
""",
            tools=tools
        )
        
        logger.info(f"Created ADK scrape agent with {len(tools)} tools")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create ADK agent: {e}")
        return None

