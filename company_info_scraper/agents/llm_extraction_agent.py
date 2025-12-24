"""
LLM Extraction Agent - Processes text through Ollama for data extraction (PH2-S4, PH5-S2)

Refactored to use LLMExtractionService as single source of truth.
Updated for Google ADK compatibility.
"""

import asyncio
from typing import Dict, Any, Optional

from .base_agent import BaseAgent, adk_tool
from company_info_scraper.services import LLMExtractionService


class LLMExtractionAgent(BaseAgent):
    """
    Agent responsible for LLM-based data extraction.
    
    Uses LLMExtractionService as the single source of truth for
    extraction logic, prompts, and parsing.
    
    ADK Integration (PH5-S2):
    - Exposes extract_company_info tool for ADK orchestration
    - Can be wrapped as ADK LlmAgent
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("LLMExtractionAgent", config)
        
        # Initialize LLM service with config
        self.service = LLMExtractionService(
            model=self.config.get('model', 'llama3'),
            timeout=self.config.get('timeout', 90),
            max_retries=self.config.get('max_retries', 3),
            max_text_length=self.config.get('max_text_length', 5000)
        )
        
        # Register ADK tools (PH5-S2)
        self._register_adk_tools()
    
    def _register_adk_tools(self):
        """Register methods as ADK tools."""
        self.register_tool(
            name="extract_company_info",
            description=(
                "Extract structured company information from website text. "
                "Extracts: products/services, customers, partnerships, and case studies. "
                "Input: text content from a webpage. Output: structured JSON with extracted fields."
            ),
            func=self._extract_tool,
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text content to extract information from"
                    },
                    "url": {
                        "type": "string",
                        "description": "Optional URL of the source page for context"
                    }
                },
                "required": ["text"]
            }
        )
        
        self.register_tool(
            name="extract_batch",
            description=(
                "Extract company information from multiple text sources in parallel. "
                "More efficient than calling extract_company_info multiple times."
            ),
            func=self._extract_batch_tool,
            parameters={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "url": {"type": "string"}
                            },
                            "required": ["text"]
                        },
                        "description": "List of items to extract from"
                    }
                },
                "required": ["items"]
            }
        )
    
    def _extract_tool(self, text: str, url: str = "unknown") -> Dict[str, Any]:
        """ADK tool wrapper for extraction."""
        return self.execute({'text': text, 'url': url})
    
    def _extract_batch_tool(self, items: list) -> Dict[str, Any]:
        """ADK tool wrapper for batch extraction."""
        results = []
        for item in items:
            result = self.execute({
                'text': item.get('text', ''),
                'url': item.get('url', 'unknown')
            })
            results.append(result)
        
        successful = sum(1 for r in results if r.get('success'))
        return {
            'success': True,
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results
        }
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured data from text using LLM (synchronous).
        
        Args:
            input_data: Must contain 'text' key (and optionally 'url')
            
        Returns:
            Dictionary with extracted fields: products, customers, partnerships, case_studies
        """
        if not self.validate_input(input_data, ['text']):
            return {
                'success': False,
                'error': 'Missing required field: text'
            }
        
        text_content = input_data['text']
        url = input_data.get('url', 'unknown')
        
        self.logger.info(f"Extracting data from text (length: {len(text_content)}) for URL: {url}")
        
        # Phase 2 Fix: Use extract_sync() to avoid asyncio.run() blocking
        # asyncio.run() creates a new event loop which can conflict with Twisted
        result = self.service.extract_sync(text_content, url=url)
        
        # Convert ExtractionResult to agent response format
        success = result.status == 'success'
        
        self.log_result({
            'url': url,
            'status': result.status,
            'error': result.error
        }, success=success)
        
        return {
            'success': success,
            'products': result.products,
            'customers': result.customers,
            'partnerships': result.partnerships,
            'case_studies': result.case_studies,
            'extraction_status': result.status,
            'url': url,
            'error': result.error
        }
    
    async def execute_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured data from text using LLM (asynchronous).
        
        Args:
            input_data: Must contain 'text' key (and optionally 'url')
            
        Returns:
            Dictionary with extracted fields
        """
        if not self.validate_input(input_data, ['text']):
            return {
                'success': False,
                'error': 'Missing required field: text'
            }
        
        text_content = input_data['text']
        url = input_data.get('url', 'unknown')
        
        self.logger.info(f"Async extracting data for URL: {url}")
        
        # Call async service directly
        result = await self.service.extract(text_content, url=url)
        
        success = result.status == 'success'
        
        return {
            'success': success,
            'products': result.products,
            'customers': result.customers,
            'partnerships': result.partnerships,
            'case_studies': result.case_studies,
            'extraction_status': result.status,
            'url': url,
            'error': result.error
        }
    
    def _get_execute_description(self) -> str:
        """Description for ADK execute tool."""
        return (
            "Extract structured company information (products, customers, partnerships, "
            "case studies) from the provided text content using LLM analysis."
        )
    
    def _get_agent_instruction(self) -> str:
        """Instruction for ADK LlmAgent wrapper."""
        return """You are the LLM Extraction Agent.

Your role is to extract structured company information from website text content.
You extract the following fields:
- Products/Services: What the company offers
- Customers: Who uses their products/services
- Partnerships: Business relationships and integrations
- Case Studies: Success stories and implementations

When given text content, use the extract_company_info tool to analyze it.
For multiple pages, use extract_batch for better efficiency.
Always return structured JSON results."""
