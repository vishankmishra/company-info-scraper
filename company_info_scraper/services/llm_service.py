"""
Async LLM Extraction Service (PH4-S3)

Provides async LLM extraction decoupled from Scrapy pipeline.
Supports parallel batch processing with worker pool.

Can be called independently with:
    await llm_service.extract(text)
    await llm_service.extract_batch(items, max_concurrent=3)
"""

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

import ollama

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of LLM extraction."""
    products: str
    services: str
    customers: str
    partnerships: str
    case_studies: str
    status: str  # 'success' or 'failure'
    error: Optional[str] = None
    url: str = ""
    elapsed_ms: float = 0.0


@dataclass
class BatchExtractionResult:
    """Result of batch LLM extraction."""
    total: int
    successful: int
    failed: int
    results: List[ExtractionResult] = field(default_factory=list)
    total_elapsed_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.successful / max(self.total, 1)
    
    @property
    def avg_time_per_extraction_ms(self) -> float:
        return self.total_elapsed_ms / max(self.total, 1)


class LLMExtractionService:
    """Async service for LLM-based text extraction.
    
    Usage:
        service = LLMExtractionService()
        result = await service.extract(text, url="https://example.com")
    """
    
    def __init__(
        self,
        model: str = 'llama3',
        timeout: int = 90,
        max_retries: int = 3,
        max_text_length: int = 5000
    ):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_text_length = max_text_length
        self.client = ollama.Client(timeout=timeout)
    
    def _build_prompt(self, text: str) -> str:
        """Build the extraction prompt for the LLM."""
        return f"""You are a data extraction specialist. Analyze the following website text and extract structured information.

Extract the following information:

1. **Products**: List all physical or software products mentioned. Include specific product names, product lines, and tangible offerings.

2. **Services**: List all services, consulting offerings, professional services, or intangible solutions mentioned. Include service categories and service types.

3. **Customer Names**: Extract all customer/client names, company names, or testimonials that mention specific customers. Look for phrases like "our clients", "customers include", "trusted by", case studies with customer names, or testimonials.

4. **Partnerships**: Identify all partnerships, strategic alliances, integrations, or collaborations mentioned. Look for partner logos, partner names, integration partners, or strategic alliance announcements.

5. **Case Studies**: Extract case study titles, customer success stories, detailed use cases, or detailed customer examples with outcomes/results.

Website Text:
{text[:self.max_text_length]}

IMPORTANT: Return ONLY a valid JSON object with this exact structure:
{{
    "products": ["product1", "product2"] or "N/A",
    "services": ["service1", "service2"] or "N/A",
    "customers": ["customer1", "customer2"] or "N/A",
    "partnerships": ["partner1", "partner2"] or "N/A",
    "case_studies": ["case study 1", "case study 2"] or "N/A"
}}

Use arrays for multiple items, or "N/A" if no information found. Be thorough and extract all relevant information."""

    def _call_ollama_sync(self, prompt: str) -> str:
        """Synchronous Ollama call (will be run in thread pool)."""
        response = self.client.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']

    async def _call_ollama_with_retry(self, prompt: str, url: str) -> str:
        """Call Ollama with retry logic and exponential backoff (async)."""
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Run blocking Ollama call in thread pool
                content = await asyncio.to_thread(self._call_ollama_sync, prompt)
                return content
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    backoff = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(
                        f"Retry {attempt}/{self.max_retries} for {url} after {type(e).__name__}. "
                        f"Waiting {backoff}s before retry..."
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"All {self.max_retries} retries failed for {url}. Last error: {e}"
                    )
        
        raise last_exception

    def _parse_json_response(self, ai_content: str) -> dict:
        """Parse JSON from LLM response, handling common formatting issues."""
        # Try to find JSON with "products" or "services" key
        json_match = re.search(r'\{[^{}]*"(?:products|services)"[^{}]*\}', ai_content, re.DOTALL)
        if not json_match:
            # Try to find JSON block between ```json and ```
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find any JSON object
                json_match = re.search(r'\{.*\}', ai_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in LLM response")
        else:
            json_str = json_match.group(0)
        
        # Parse JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix common JSON issues
            json_str = json_str.replace("'", '"')  # Replace single quotes
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
            return json.loads(json_str)

    def _format_field(self, field_value) -> str:
        """Format field value for output."""
        if field_value == 'N/A' or field_value is None:
            return "N/A"
        elif isinstance(field_value, list):
            formatted = "; ".join(str(item) for item in field_value if item and item != 'N/A')
            return formatted if formatted else "N/A"
        elif isinstance(field_value, str):
            return field_value
        else:
            return str(field_value)

    def _determine_status(self, products: str, services: str, customers: str, partnerships: str, case_studies: str) -> str:
        """Determine extraction status based on field values."""
        fields = [products, services, customers, partnerships, case_studies]
        for value in fields:
            if value and not str(value).startswith('N/A'):
                return 'success'
        return 'failure'

    def _call_ollama_with_retry_sync(self, prompt: str, url: str) -> str:
        """Call Ollama with retry logic and exponential backoff (synchronous).
        
        Used by extract_sync() for Scrapy pipeline compatibility.
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._call_ollama_sync(prompt)
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    backoff = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(
                        f"Retry {attempt}/{self.max_retries} for {url} after {type(e).__name__}. "
                        f"Waiting {backoff}s before retry..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"All {self.max_retries} retries failed for {url}. Last error: {e}"
                    )
        
        raise last_exception

    def extract_sync(self, text: str, url: str = "unknown") -> ExtractionResult:
        """Extract structured data from text using LLM (synchronous).
        
        Use this method in Scrapy pipelines or other sync contexts
        where asyncio event loop conflicts with Twisted.
        
        Args:
            text: The raw text content to extract from
            url: The source URL (for logging purposes)
            
        Returns:
            ExtractionResult with extracted fields and status
        """
        # Handle empty text
        if not text or not text.strip():
            logger.warning(f"Empty text content for {url}")
            return ExtractionResult(
                products="N/A",
                services="N/A",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error="Empty text content"
            )
        
        prompt = self._build_prompt(text)
        
        try:
            # Call Ollama with sync retry logic
            ai_content = self._call_ollama_with_retry_sync(prompt, url)
            
            # Parse JSON response
            extracted_data = self._parse_json_response(ai_content)
            
            # Format fields
            products = self._format_field(extracted_data.get('products', 'N/A'))
            services = self._format_field(extracted_data.get('services', 'N/A'))
            customers = self._format_field(extracted_data.get('customers', 'N/A'))
            partnerships = self._format_field(extracted_data.get('partnerships', 'N/A'))
            case_studies = self._format_field(extracted_data.get('case_studies', 'N/A'))
            
            # Determine status
            status = self._determine_status(products, services, customers, partnerships, case_studies)
            
            if status == 'success':
                logger.info(f"Successfully extracted data for {url}")
            else:
                logger.warning(f"Extraction failure for {url}: all fields are N/A")
            
            return ExtractionResult(
                products=products,
                services=services,
                customers=customers,
                partnerships=partnerships,
                case_studies=case_studies,
                status=status
            )
            
        except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
            logger.error(f"Ollama failed after {self.max_retries} retries for {url}: {e}")
            return ExtractionResult(
                products="N/A (Timeout)",
                services="N/A (Timeout)",
                customers="N/A (Timeout)",
                partnerships="N/A (Timeout)",
                case_studies="N/A (Timeout)",
                status="failure",
                error=f"Timeout: {str(e)[:50]}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for {url}: {e}")
            return ExtractionResult(
                products="N/A (JSON Error)",
                services="N/A (JSON Error)",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error=f"JSON Error: {str(e)[:50]}"
            )
        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            return ExtractionResult(
                products=f"N/A (Error: {str(e)[:50]})",
                services="N/A",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error=str(e)[:100]
            )

    async def extract(self, text: str, url: str = "unknown") -> ExtractionResult:
        """Extract structured data from text using LLM (asynchronous).
        
        Args:
            text: The raw text content to extract from
            url: The source URL (for logging purposes)
            
        Returns:
            ExtractionResult with extracted fields and status
        """
        # Handle empty text
        if not text or not text.strip():
            logger.warning(f"Empty text content for {url}")
            return ExtractionResult(
                products="N/A",
                services="N/A",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error="Empty text content"
            )
        
        prompt = self._build_prompt(text)
        
        try:
            # Call Ollama with async retry logic
            ai_content = await self._call_ollama_with_retry(prompt, url)
            
            # Parse JSON response
            extracted_data = self._parse_json_response(ai_content)
            
            # Format fields
            products = self._format_field(extracted_data.get('products', 'N/A'))
            services = self._format_field(extracted_data.get('services', 'N/A'))
            customers = self._format_field(extracted_data.get('customers', 'N/A'))
            partnerships = self._format_field(extracted_data.get('partnerships', 'N/A'))
            case_studies = self._format_field(extracted_data.get('case_studies', 'N/A'))
            
            # Determine status
            status = self._determine_status(products, services, customers, partnerships, case_studies)
            
            if status == 'success':
                logger.info(f"Successfully extracted data for {url}")
            else:
                logger.warning(f"Extraction failure for {url}: all fields are N/A")
            
            return ExtractionResult(
                products=products,
                services=services,
                customers=customers,
                partnerships=partnerships,
                case_studies=case_studies,
                status=status
            )
            
        except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
            logger.error(f"Ollama failed after {self.max_retries} retries for {url}: {e}")
            return ExtractionResult(
                products="N/A (Timeout)",
                services="N/A (Timeout)",
                customers="N/A (Timeout)",
                partnerships="N/A (Timeout)",
                case_studies="N/A (Timeout)",
                status="failure",
                error=f"Timeout: {str(e)[:50]}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for {url}: {e}")
            return ExtractionResult(
                products="N/A (JSON Error)",
                services="N/A (JSON Error)",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error=f"JSON Error: {str(e)[:50]}"
            )
        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            return ExtractionResult(
                products=f"N/A (Error: {str(e)[:50]})",
                services="N/A",
                customers="N/A",
                partnerships="N/A",
                case_studies="N/A",
                status="failure",
                error=str(e)[:100]
            )
    
    async def extract_batch(
        self,
        items: List[Dict[str, str]],
        max_concurrent: int = 3,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> BatchExtractionResult:
        """Extract data from multiple texts in parallel (PH4-S3).
        
        Uses asyncio semaphore for controlled parallelism.
        
        Args:
            items: List of dicts with 'text' and optional 'url' keys
            max_concurrent: Maximum concurrent LLM calls (default 3)
            on_progress: Optional callback(current, total, url) for progress
            
        Returns:
            BatchExtractionResult with all results and timing
        """
        if not items:
            return BatchExtractionResult(
                total=0,
                successful=0,
                failed=0,
                results=[],
                total_elapsed_ms=0
            )
        
        total = len(items)
        processed = 0
        
        logger.info(
            f"Starting parallel LLM extraction: {total} items, "
            f"max_concurrent={max_concurrent}"
        )
        
        start_time = time.time()
        
        # Semaphore to control concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def extract_with_semaphore(item: Dict[str, str], index: int) -> ExtractionResult:
            nonlocal processed
            
            async with semaphore:
                text = item.get('text', '')
                url = item.get('url', f'item_{index}')
                
                item_start = time.time()
                result = await self.extract(text, url=url)
                result.url = url
                result.elapsed_ms = (time.time() - item_start) * 1000
                
                processed += 1
                if on_progress:
                    on_progress(processed, total, url)
                
                return result
        
        # Process all items concurrently (limited by semaphore)
        tasks = [
            extract_with_semaphore(item, i)
            for i, item in enumerate(items)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        extraction_results: List[ExtractionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                extraction_results.append(ExtractionResult(
                    products="N/A (Error)",
                    services="N/A (Error)",
                    customers="N/A",
                    partnerships="N/A",
                    case_studies="N/A",
                    status="failure",
                    error=str(result)[:100],
                    url=items[i].get('url', f'item_{i}')
                ))
            else:
                extraction_results.append(result)
        
        total_elapsed = (time.time() - start_time) * 1000
        successful = sum(1 for r in extraction_results if r.status == 'success')
        
        logger.info(
            f"Parallel extraction complete: {successful}/{total} successful "
            f"in {total_elapsed/1000:.1f}s (avg {total_elapsed/total:.0f}ms/item)"
        )
        
        return BatchExtractionResult(
            total=total,
            successful=successful,
            failed=total - successful,
            results=extraction_results,
            total_elapsed_ms=total_elapsed
        )
    
    def extract_batch_sync(
        self,
        items: List[Dict[str, str]],
        max_workers: int = 3,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> BatchExtractionResult:
        """Extract data from multiple texts in parallel (synchronous).
        
        Uses ThreadPoolExecutor for parallel processing in sync context.
        
        Args:
            items: List of dicts with 'text' and optional 'url' keys
            max_workers: Maximum parallel workers (default 3)
            on_progress: Optional callback(current, total, url)
            
        Returns:
            BatchExtractionResult with all results and timing
        """
        if not items:
            return BatchExtractionResult(
                total=0,
                successful=0,
                failed=0,
                results=[],
                total_elapsed_ms=0
            )
        
        total = len(items)
        processed = [0]  # Use list for mutable counter in nested function
        lock = __import__('threading').Lock()
        
        logger.info(
            f"Starting parallel sync LLM extraction: {total} items, "
            f"max_workers={max_workers}"
        )
        
        start_time = time.time()
        
        def extract_item(args):
            index, item = args
            text = item.get('text', '')
            url = item.get('url', f'item_{index}')
            
            item_start = time.time()
            result = self.extract_sync(text, url=url)
            result.url = url
            result.elapsed_ms = (time.time() - item_start) * 1000
            
            with lock:
                processed[0] += 1
                if on_progress:
                    on_progress(processed[0], total, url)
            
            return result
        
        # Process items in parallel using thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(extract_item, enumerate(items)))
        
        total_elapsed = (time.time() - start_time) * 1000
        successful = sum(1 for r in results if r.status == 'success')
        
        logger.info(
            f"Parallel sync extraction complete: {successful}/{total} successful "
            f"in {total_elapsed/1000:.1f}s"
        )
        
        return BatchExtractionResult(
            total=total,
            successful=successful,
            failed=total - successful,
            results=results,
            total_elapsed_ms=total_elapsed
        )


# Convenience function for quick parallel extraction
async def extract_texts_parallel(
    items: List[Dict[str, str]],
    max_concurrent: int = 3,
    model: str = 'llama3',
    timeout: int = 90
) -> BatchExtractionResult:
    """Quick parallel extraction of multiple texts.
    
    Args:
        items: List of dicts with 'text' and optional 'url' keys
        max_concurrent: Maximum concurrent extractions
        model: Ollama model to use
        timeout: Timeout per extraction
        
    Returns:
        BatchExtractionResult with all results
    """
    service = LLMExtractionService(model=model, timeout=timeout)
    return await service.extract_batch(items, max_concurrent=max_concurrent)

