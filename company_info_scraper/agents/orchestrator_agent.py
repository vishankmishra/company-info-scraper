"""
Orchestrator Agent - Coordinates the entire scraping workflow (PH4-S1, PH5-S2)

Supports dual-path scraping:
- Detects if site is static or dynamic
- Routes to appropriate scraper (BeautifulSoup or Playwright)
- Coordinates LLM extraction
- Parallel batch processing with configurable concurrency

Compatible with Google ADK architecture.
"""

import asyncio
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent, is_adk_available
from .scraping_agent import ScrapingAgent
from .llm_extraction_agent import LLMExtractionAgent
from company_info_scraper.services import SiteDetector, SiteType, BatchProcessor


class OrchestratorAgent(BaseAgent):
    """
    Main orchestrator agent that coordinates scraping and LLM extraction.
    
    Features:
    - Automatic site type detection (static vs dynamic)
    - Dual-path scraping (BeautifulSoup for static, Playwright for dynamic)
    - LLM extraction coordination
    - Batch processing support
    
    ADK Integration (PH5-S2):
    - Exposes orchestration tools for ADK
    - Can create ADK workflow for end-to-end scraping
    - Coordinates sub-agents via ADK runtime when available
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("OrchestratorAgent", config)
        
        # Initialize sub-agents
        scraping_config = {
            'project_root': self.config.get('project_root'),
            'output_file': self.config.get('output_file', 'output_data.csv')
        }
        self.scraping_agent = ScrapingAgent(scraping_config)
        
        llm_config = {
            'model': self.config.get('ollama_model', 'llama3'),
            'timeout': self.config.get('ollama_timeout', 90),
            'max_retries': self.config.get('max_retries', 3),
            'max_text_length': self.config.get('max_text_length', 5000)
        }
        self.llm_agent = LLMExtractionAgent(llm_config)
        
        # Site detector for dual-path routing
        self.site_detector = SiteDetector()
        
        # Config options
        self.auto_detect = self.config.get('auto_detect', True)  # Auto-detect site type
        self.force_scraper = self.config.get('force_scraper', None)  # 'static' or 'dynamic'
        
        # PH4-S1: Batch processor for parallel processing
        self.max_concurrent = self.config.get('max_concurrent', 5)
        self.batch_processor = None  # Lazily initialized
        
        # Register ADK tools (PH5-S2)
        self._register_adk_tools()
    
    def _register_adk_tools(self):
        """Register orchestration methods as ADK tools."""
        self.register_tool(
            name="scrape_and_extract",
            description=(
                "Complete workflow: scrape a website and extract company information. "
                "Automatically detects if site is static or dynamic and uses the appropriate method. "
                "Returns structured company data including products, customers, partnerships, and case studies."
            ),
            func=self._scrape_and_extract_tool,
            parameters={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain or URL to scrape and extract from"
                    },
                    "scraper_type": {
                        "type": "string",
                        "enum": ["static", "dynamic", "auto"],
                        "description": "Scraper type: 'auto' for automatic detection (recommended)"
                    }
                },
                "required": ["domain"]
            }
        )
        
        self.register_tool(
            name="batch_scrape_and_extract",
            description=(
                "Process multiple domains in parallel. More efficient than calling "
                "scrape_and_extract multiple times. Handles rate limiting and concurrency."
            ),
            func=self._batch_tool,
            parameters={
                "type": "object",
                "properties": {
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of domains to process"
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum parallel processes (default: 5)"
                    }
                },
                "required": ["domains"]
            }
        )
        
        self.register_tool(
            name="detect_site_type",
            description=(
                "Detect if a website is static or dynamic. "
                "Returns 'static' for simple HTML sites, 'dynamic' for JavaScript-heavy sites."
            ),
            func=self._detect_tool,
            parameters={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain to analyze"
                    }
                },
                "required": ["domain"]
            }
        )
    
    def _scrape_and_extract_tool(
        self, 
        domain: str, 
        scraper_type: str = "auto"
    ) -> Dict[str, Any]:
        """ADK tool wrapper for full workflow."""
        return self.execute({'domain': domain, 'scraper_type': scraper_type})
    
    def _batch_tool(
        self, 
        domains: List[str], 
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """ADK tool wrapper for batch processing."""
        return self.execute_batch_parallel(domains, max_concurrent)
    
    def _detect_tool(self, domain: str) -> Dict[str, Any]:
        """ADK tool wrapper for site detection."""
        site_type = self._detect_site_type(domain)
        return {
            'domain': domain,
            'site_type': site_type,
            'recommendation': (
                'Use static scraper for faster processing' 
                if site_type == 'static' 
                else 'Use dynamic scraper for JavaScript content'
            )
        }
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the complete workflow: detect -> scrape -> extract.
        
        Args:
            input_data: Must contain 'domain' key.
                       Optional 'scraper_type': 'static', 'dynamic', or 'auto' (default)
            
        Returns:
            Complete result with scraped and extracted data
        """
        if not self.validate_input(input_data, ['domain']):
            return {
                'success': False,
                'error': 'Missing required field: domain'
            }
        
        domain = input_data['domain']
        requested_scraper = input_data.get('scraper_type', 'auto')
        
        self.logger.info(f"Starting orchestration for domain: {domain}")
        
        # Step 1: Determine scraper type
        if self.force_scraper:
            scraper_type = self.force_scraper
            self.logger.info(f"Using forced scraper type: {scraper_type}")
        elif requested_scraper != 'auto':
            scraper_type = requested_scraper
            self.logger.info(f"Using requested scraper type: {scraper_type}")
        elif self.auto_detect:
            scraper_type = self._detect_site_type(domain)
        else:
            scraper_type = 'dynamic'  # Default to Playwright
        
        # Step 2: Scraping with appropriate scraper
        scraping_result = self.scraping_agent.execute({
            'domain': domain,
            'scraper_type': scraper_type
        })
        
        if not scraping_result.get('success'):
            return {
                'success': False,
                'error': f"Scraping failed: {scraping_result.get('error')}",
                'domain': domain,
                'scraper_type': scraper_type
            }
        
        # Step 3: LLM Extraction (if raw_data available)
        raw_data = scraping_result.get('raw_data', [])
        extracted_results = []
        
        for record in raw_data:
            text_content = record.get('raw_text', '')
            url = record.get('url', 'unknown')
            
            if text_content:
                extraction_result = self.llm_agent.execute({
                    'text': text_content,
                    'url': url
                })
                
                # Merge scraping and extraction results
                merged_result = {
                    **record,
                    **{k: v for k, v in extraction_result.items() if k != 'success' and k != 'url'}
                }
                extracted_results.append(merged_result)
            else:
                # No text content, use original record
                extracted_results.append(record)
        
        self.log_result({
            'domain': domain,
            'scraper_type': scraper_type,
            'records_processed': len(extracted_results),
            'scraping_success': scraping_result.get('success')
        }, success=True)
        
        return {
            'success': True,
            'domain': domain,
            'scraper_type': scraper_type,
            'records': extracted_results,
            'records_count': len(extracted_results),
            'output_file': scraping_result.get('output_file')
        }
    
    async def execute_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute workflow asynchronously.
        
        Args:
            input_data: Must contain 'domain' key.
            
        Returns:
            Complete result with scraped and extracted data
        """
        if not self.validate_input(input_data, ['domain']):
            return {
                'success': False,
                'error': 'Missing required field: domain'
            }
        
        domain = input_data['domain']
        requested_scraper = input_data.get('scraper_type', 'auto')
        
        self.logger.info(f"Starting async orchestration for domain: {domain}")
        
        # Step 1: Determine scraper type
        if self.force_scraper:
            scraper_type = self.force_scraper
        elif requested_scraper != 'auto':
            scraper_type = requested_scraper
        elif self.auto_detect:
            scraper_type = await self._detect_site_type_async(domain)
        else:
            scraper_type = 'dynamic'
        
        self.logger.info(f"Using {scraper_type} scraper for {domain}")
        
        # Step 2: Scraping
        scraping_result = await self.scraping_agent.execute_async({
            'domain': domain,
            'scraper_type': scraper_type
        })
        
        if not scraping_result.get('success'):
            return {
                'success': False,
                'error': f"Scraping failed: {scraping_result.get('error')}",
                'domain': domain,
                'scraper_type': scraper_type
            }
        
        # Step 3: LLM Extraction
        raw_data = scraping_result.get('raw_data', [])
        extracted_results = []
        
        for record in raw_data:
            text_content = record.get('raw_text', '')
            url = record.get('url', 'unknown')
            
            if text_content:
                extraction_result = await self.llm_agent.execute_async({
                    'text': text_content,
                    'url': url
                })
                
                merged_result = {
                    **record,
                    **{k: v for k, v in extraction_result.items() if k != 'success' and k != 'url'}
                }
                extracted_results.append(merged_result)
            else:
                extracted_results.append(record)
        
        return {
            'success': True,
            'domain': domain,
            'scraper_type': scraper_type,
            'records': extracted_results,
            'records_count': len(extracted_results)
        }
    
    def _detect_site_type(self, domain: str) -> str:
        """Detect if site is static or dynamic (synchronous)."""
        try:
            result = self.site_detector.detect_sync(domain)
            
            if result.site_type == SiteType.STATIC:
                self.logger.info(
                    f"Detected STATIC site: {domain} "
                    f"(confidence: {result.confidence:.0%})"
                )
                return 'static'
            else:
                self.logger.info(
                    f"Detected DYNAMIC site: {domain} "
                    f"(confidence: {result.confidence:.0%})"
                )
                return 'dynamic'
        except Exception as e:
            self.logger.warning(f"Site detection failed for {domain}: {e}. Defaulting to dynamic.")
            return 'dynamic'
    
    async def _detect_site_type_async(self, domain: str) -> str:
        """Detect if site is static or dynamic (async)."""
        try:
            result = await self.site_detector.detect(domain)
            
            if result.site_type == SiteType.STATIC:
                self.logger.info(
                    f"Detected STATIC site: {domain} "
                    f"(confidence: {result.confidence:.0%})"
                )
                return 'static'
            else:
                self.logger.info(
                    f"Detected DYNAMIC site: {domain} "
                    f"(confidence: {result.confidence:.0%})"
                )
                return 'dynamic'
        except Exception as e:
            self.logger.warning(f"Site detection failed for {domain}: {e}. Defaulting to dynamic.")
            return 'dynamic'
    
    def execute_batch(self, domains: List[str]) -> Dict[str, Any]:
        """
        Execute workflow for multiple domains.
        
        Args:
            domains: List of domain names/URLs
            
        Returns:
            Batch results with per-domain results
        """
        self.logger.info(f"Starting batch processing for {len(domains)} domains")
        
        results = []
        static_count = 0
        dynamic_count = 0
        
        for domain in domains:
            result = self.execute({'domain': domain})
            results.append(result)
            
            if result.get('scraper_type') == 'static':
                static_count += 1
            else:
                dynamic_count += 1
        
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        
        self.logger.info(
            f"Batch complete: {successful}/{len(domains)} successful. "
            f"Scrapers used: {static_count} static, {dynamic_count} dynamic"
        )
        
        return {
            'success': True,
            'total_domains': len(domains),
            'successful': successful,
            'failed': failed,
            'static_scraped': static_count,
            'dynamic_scraped': dynamic_count,
            'results': results
        }
    
    async def execute_batch_async(
        self, 
        domains: List[str],
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow for multiple domains asynchronously with parallel processing.
        
        PH4-S1: Uses BatchProcessor for concurrent domain processing.
        
        Args:
            domains: List of domain names/URLs
            max_concurrent: Override max concurrent (default: use config)
            
        Returns:
            Batch results with per-domain results
        """
        concurrent = max_concurrent or self.max_concurrent
        
        self.logger.info(
            f"Starting parallel batch processing: {len(domains)} domains, "
            f"max_concurrent={concurrent}"
        )
        
        # Initialize batch processor with config
        processor = BatchProcessor(
            max_concurrent=concurrent,
            auto_detect=self.auto_detect,
            default_scraper=self.force_scraper or 'static',
            llm_timeout=self.config.get('ollama_timeout', 90),
            llm_max_retries=self.config.get('max_retries', 3)
        )
        
        # Process all domains in parallel
        batch_result = await processor.process(domains)
        
        # Convert BatchResult to dict format for compatibility
        results = []
        for dr in batch_result.results:
            results.append({
                'success': dr.success,
                'domain': dr.domain,
                'scraper_type': dr.scraper_type,
                'records': dr.records,
                'records_count': dr.records_count,
                'elapsed_ms': dr.elapsed_ms,
                'error': dr.error
            })
        
        self.logger.info(
            f"Parallel batch complete: {batch_result.successful}/{batch_result.total_domains} "
            f"successful in {batch_result.total_elapsed_ms/1000:.1f}s. "
            f"Avg: {batch_result.avg_time_per_domain_ms/1000:.1f}s/domain"
        )
        
        return {
            'success': True,
            'total_domains': batch_result.total_domains,
            'successful': batch_result.successful,
            'failed': batch_result.failed,
            'static_scraped': batch_result.static_scraped,
            'dynamic_scraped': batch_result.dynamic_scraped,
            'total_elapsed_ms': batch_result.total_elapsed_ms,
            'avg_time_per_domain_ms': batch_result.avg_time_per_domain_ms,
            'results': results
        }
    
    def execute_batch_parallel(
        self,
        domains: List[str],
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for parallel batch processing.
        
        Args:
            domains: List of domain names/URLs
            max_concurrent: Override max concurrent
            
        Returns:
            Batch results with per-domain results
        """
        return asyncio.run(self.execute_batch_async(domains, max_concurrent))
    
    # =========================================================================
    # ADK Integration Methods (PH5-S2)
    # =========================================================================
    
    def get_sub_agents(self) -> Dict[str, BaseAgent]:
        """Get all sub-agents managed by this orchestrator."""
        return {
            'scraping': self.scraping_agent,
            'llm_extraction': self.llm_agent
        }
    
    def create_adk_workflow(self, model: str = "gemini-2.0-flash"):
        """
        Create an ADK workflow for end-to-end company scraping.
        
        This creates a multi-agent workflow where:
        1. OrchestratorAgent coordinates the flow
        2. ScrapingAgent handles web scraping
        3. LLMExtractionAgent handles data extraction
        
        Args:
            model: LLM model for agent reasoning
            
        Returns:
            ADK Agent or None if ADK not available
        """
        if not is_adk_available():
            self.logger.warning("Google ADK not available. Cannot create workflow.")
            return None
        
        try:
            from google.adk import LlmAgent
            
            # Get tools from all agents
            all_tools = []
            all_tools.extend(self.get_adk_tools())
            all_tools.extend(self.scraping_agent.get_adk_tools())
            all_tools.extend(self.llm_agent.get_adk_tools())
            
            # Create orchestrator agent with all tools
            workflow_agent = LlmAgent(
                name="CompanyInfoScraper",
                model=model,
                instruction=self._get_workflow_instruction(),
                tools=all_tools
            )
            
            self.logger.info(
                f"Created ADK workflow with {len(all_tools)} tools "
                f"(model: {model})"
            )
            return workflow_agent
            
        except Exception as e:
            self.logger.error(f"Failed to create ADK workflow: {e}")
            return None
    
    def _get_execute_description(self) -> str:
        """Description for ADK execute tool."""
        return (
            "Execute the complete company info scraping workflow: "
            "detect site type, scrape content, and extract structured data."
        )
    
    def _get_agent_instruction(self) -> str:
        """Instruction for ADK LlmAgent wrapper."""
        return """You are the Orchestrator Agent for company information scraping.

Your role is to coordinate the complete workflow:
1. Detect if a website is static or dynamic
2. Scrape the website using the appropriate method
3. Extract structured company information

For single domains, use the scrape_and_extract tool.
For multiple domains, use batch_scrape_and_extract for efficiency.
To check a site's type before scraping, use detect_site_type.

Always return structured results with company information."""
    
    def _get_workflow_instruction(self) -> str:
        """Instruction for the full ADK workflow agent."""
        return """You are the Company Info Scraper - an intelligent agent that extracts 
structured business information from company websites.

## Capabilities

You can:
1. **Scrape websites** - Extract text content from any website
   - Static sites: Fast HTTP-based scraping
   - Dynamic sites: Browser-based scraping for JavaScript content

2. **Extract company info** - Analyze text to identify:
   - Products and services offered
   - Customer base and target market
   - Business partnerships and integrations
   - Case studies and success stories

3. **Batch processing** - Process multiple domains efficiently in parallel

## Workflow

When given a company domain or URL:
1. Use `detect_site_type` if unsure whether it's static or dynamic
2. Use `scrape_and_extract` for the complete workflow (recommended)
3. For multiple domains, use `batch_scrape_and_extract`

## Output Format

Always return structured JSON with these fields:
- products: Products/services the company offers
- customers: Who uses their products
- partnerships: Business relationships
- case_studies: Success stories and implementations
- extraction_status: 'success' or 'failure'

## Best Practices

- For unknown sites, let auto-detection choose the scraper
- For known static sites (simple HTML), force 'static' mode for speed
- For React/Vue/Angular sites, use 'dynamic' mode
- Process batches in parallel for efficiency"""
