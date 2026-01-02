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
from pydantic import ValidationError

from company_info_scraper.models.extraction_schema import ExtractionSchema

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
        # Phase 5: Prefer qwen2.5:7b-instruct, fallback gracefully
        self.model = model
        if model == 'llama3':
            # Check if qwen2.5:7b-instruct is available (don't fail if not)
            try:
                test_client = ollama.Client(timeout=2)
                # Just check if model exists, don't actually call it
                models = test_client.list()
                available_models = [m.get('name', '') for m in models.get('models', [])]
                if any('qwen2.5' in m and 'instruct' in m for m in available_models):
                    # Find the exact qwen2.5:7b-instruct model name
                    qwen_model = next((m for m in available_models if 'qwen2.5' in m and 'instruct' in m), None)
                    if qwen_model:
                        self.model = qwen_model
                        logger.info(f"Using {qwen_model} model")
            except Exception:
                logger.info(f"qwen2.5:7b-instruct not available, using {model}")
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_text_length = max_text_length
        self.client = ollama.Client(timeout=timeout)
    
    def _build_prompt(self, text: str, is_retry: bool = False, is_empty_retry: bool = False) -> str:
        """Build the extraction prompt for the LLM (Phase 5: Field-specific instructions)."""
        
        if is_empty_retry:
            retry_instruction = """
CRITICAL: The previous extraction returned no results. Please look more carefully for:
- ANY company names mentioned (potential customers or partners)
- ANY named individuals with company affiliations (testimonials)
- ANY logos or brand mentions
- ANY product or service names

Even partial information is valuable. Only return empty arrays if truly nothing is found.
"""
        elif is_retry:
            retry_instruction = "CRITICAL: Fix the JSON format. Return ONLY valid JSON, no explanations."
        else:
            retry_instruction = ""
        
        return f"""You are a corporate information extraction specialist. Extract the following fields from the website text.

CRITICAL INSTRUCTIONS:
- Return ONLY a valid JSON object, no explanations
- Use empty array [] if information is not found — do NOT use "N/A" for arrays
- Do NOT guess or hallucinate — only extract information that clearly exists in the text

EXTRACTION FIELDS:

1. products (array of strings)
   - Product names, software names, service offerings
   - Include specific product lines, not generic descriptions
   - Example: ["Zoho CRM", "Zoho Books", "Zoho Mail"]

2. services (array of strings)
   - Consulting, support, professional services
   - Different from products — services are things done FOR customers
   - Example: ["Implementation Services", "Technical Support", "Training"]

3. customers (array of strings)
   - ONLY extract explicitly named customer/client companies
   - Look for: "trusted by", "our customers include", "client list", logos with company names
   - Do NOT include: generic terms like "enterprises" or "Fortune 500"
   - Do NOT include: partner names (they go in partnerships)
   - Example: ["Acme Corp", "TechCorp Inc", "Global Industries"]

4. partnerships (array of strings)
   - Integration partners, technology partners, strategic alliances
   - Look for: "partners include", "integrations with", "certified partner"
   - Do NOT include: customer names
   - Example: ["Salesforce", "Microsoft", "Google Cloud"]

5. case_studies (array of strings)
   - Named customer success stories with specific outcomes
   - Format: "Company Name: brief description of what was achieved"
   - Look for: "case study", "success story", "how X achieved Y"
   - Do NOT include: generic testimonials without company names
   - Example: ["Acme Corp: 50% efficiency improvement", "TechCorp: Reduced costs by 30%"]

{retry_instruction}

WEBSITE TEXT:
{text[:self.max_text_length]}

Return JSON:
{{
    "products": [],
    "services": [],
    "customers": [],
    "partnerships": [],
    "case_studies": []
}}"""

    def _call_ollama_sync(self, prompt: str, use_json_mode: bool = True) -> str:
        """Synchronous Ollama call (will be run in thread pool)."""
        # Phase 5: Use JSON mode if available (qwen2.5, llama3.1+)
        options = {}
        if use_json_mode and self.model in ['qwen2.5:7b-instruct', 'llama3.1', 'llama3.2']:
            options['format'] = 'json'
        
        response = self.client.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            options=options if options else None
        )
        return response['message']['content']

    async def _call_ollama_with_retry(self, prompt: str, url: str, use_json_mode: bool = True) -> str:
        """Call Ollama with retry logic and exponential backoff (async).
        
        Phase 5: Reduced retries to 1 (single attempt) to avoid timeout multiplication.
        Validation retries handle errors at a higher level.
        """
        last_exception = None
        # Phase 5: Use only 1 retry to avoid timeout multiplication with validation retries
        max_attempts = min(self.max_retries, 2)  # Max 2 attempts total
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Run blocking Ollama call in thread pool
                content = await asyncio.to_thread(self._call_ollama_sync, prompt, use_json_mode)
                return content
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                last_exception = e
                if attempt < max_attempts:
                    backoff = 2  # Short backoff: 2s
                    logger.warning(
                        f"Ollama retry {attempt}/{max_attempts - 1} for {url} after {type(e).__name__}. "
                        f"Waiting {backoff}s..."
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Ollama failed for {url}: {e}")
        
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
    
    def _validate_extraction(self, extracted_data: dict) -> ExtractionSchema:
        """Validate extraction output against Pydantic schema (Phase 5)."""
        try:
            return ExtractionSchema(**extracted_data)
        except ValidationError as e:
            raise ValueError(f"Validation failed: {e}")

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
        """Determine extraction status based on field values (Phase 5)."""
        fields = [products, services, customers, partnerships, case_studies]
        for value in fields:
            if value and not str(value).startswith('N/A'):
                return 'success'
        return 'failure'  # Keep 'failure' for backward compatibility

    def _call_ollama_with_retry_sync(self, prompt: str, url: str, use_json_mode: bool = True) -> str:
        """Call Ollama with retry logic and exponential backoff (synchronous).
        
        Phase 5: Reduced retries to 1 (single attempt) to avoid timeout multiplication.
        Validation retries handle errors at a higher level.
        """
        last_exception = None
        # Phase 5: Use only 1 retry to avoid timeout multiplication with validation retries
        max_attempts = min(self.max_retries, 2)  # Max 2 attempts total
        
        for attempt in range(1, max_attempts + 1):
            try:
                return self._call_ollama_sync(prompt, use_json_mode)
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                last_exception = e
                if attempt < max_attempts:
                    backoff = 2  # Short backoff: 2s
                    logger.warning(
                        f"Ollama retry {attempt}/{max_attempts - 1} for {url} after {type(e).__name__}. "
                        f"Waiting {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Ollama failed for {url}: {e}")
        
        raise last_exception

    def extract_sync(self, text: str, url: str = "unknown") -> ExtractionResult:
        """Extract structured data from text using LLM (synchronous, Phase 5: with validation)."""
        start_time = time.time()
        
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
                error="Empty text content",
                url=url,
                elapsed_ms=0
            )
        
        text_length = len(text)
        is_empty_retry = False
        
        # Phase 5: Main extraction with validation retry
        for validation_attempt in range(3):  # Max 2 retries = 3 total attempts
            try:
                # Build prompt
                prompt = self._build_prompt(text, is_retry=(validation_attempt > 0), is_empty_retry=is_empty_retry)
                
                # Call Ollama
                ai_content = self._call_ollama_with_retry_sync(prompt, url, use_json_mode=True)
                
                # Parse JSON
                extracted_data = self._parse_json_response(ai_content)
                
                # Phase 5: Validate with Pydantic
                try:
                    validated = self._validate_extraction(extracted_data)
                    validated_dict = validated.to_dict()
                    
                    # Check for suspicious empty results
                    all_empty = all(
                        not validated_dict.get(field) or len(validated_dict.get(field, [])) == 0
                        for field in ['products', 'services', 'customers', 'partnerships', 'case_studies']
                    )
                    
                    if all_empty and text_length > 1000 and not is_empty_retry:
                        logger.warning(f"Suspicious empty extraction for {url} (text length: {text_length}), retrying...")
                        is_empty_retry = True
                        continue
                    
                    # Format fields
                    products = self._format_field(validated_dict.get('products', []))
                    services = self._format_field(validated_dict.get('services', []))
                    customers = self._format_field(validated_dict.get('customers', []))
                    partnerships = self._format_field(validated_dict.get('partnerships', []))
                    case_studies = self._format_field(validated_dict.get('case_studies', []))
                    
                    # Determine status
                    status = 'empty_but_checked' if (all_empty and is_empty_retry) else self._determine_status(
                        products, services, customers, partnerships, case_studies
                    )
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    
                    if status == 'success':
                        logger.info(f"Extracted data for {url}")
                    elif status == 'empty_but_checked':
                        logger.info(f"Empty extraction verified for {url} (checked twice)")
                    
                    return ExtractionResult(
                        products=products,
                        services=services,
                        customers=customers,
                        partnerships=partnerships,
                        case_studies=case_studies,
                        status=status,
                        url=url,
                        elapsed_ms=elapsed_ms
                    )
                    
                except ValueError as ve:
                    # Validation failed - retry with fix JSON prompt
                    if validation_attempt < 2:
                        logger.warning(f"Validation failed for {url}, retry {validation_attempt + 1}/2: {ve}")
                        continue
                    else:
                        logger.error(f"Validation failed after 2 retries for {url}: {ve}")
                        return ExtractionResult(
                            products="N/A",
                            services="N/A",
                            customers="N/A",
                            partnerships="N/A",
                            case_studies="N/A",
                            status="failed",
                            error=f"Validation failed: {str(ve)[:50]}",
                            url=url,
                            elapsed_ms=(time.time() - start_time) * 1000
                        )
                        
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                logger.error(f"Ollama failed for {url}: {e}")
                return ExtractionResult(
                    products="N/A",
                    services="N/A",
                    customers="N/A",
                    partnerships="N/A",
                    case_studies="N/A",
                    status="failed",
                    error=f"Ollama error: {str(e)[:50]}",
                    url=url,
                    elapsed_ms=(time.time() - start_time) * 1000
                )
            except json.JSONDecodeError as e:
                if validation_attempt < 2:
                    logger.warning(f"JSON parse error for {url}, retry {validation_attempt + 1}/2")
                    continue
                logger.error(f"JSON parsing error for {url}: {e}")
                return ExtractionResult(
                    products="N/A",
                    services="N/A",
                    customers="N/A",
                    partnerships="N/A",
                    case_studies="N/A",
                    status="failed",
                    error=f"JSON error: {str(e)[:50]}",
                    url=url,
                    elapsed_ms=(time.time() - start_time) * 1000
                )
        
        # Should not reach here
        return ExtractionResult(
            products="N/A",
            services="N/A",
            customers="N/A",
            partnerships="N/A",
            case_studies="N/A",
            status="failed",
            error="Max retries exceeded",
            url=url,
            elapsed_ms=(time.time() - start_time) * 1000
        )

    async def extract(self, text: str, url: str = "unknown") -> ExtractionResult:
        """Extract structured data from text using LLM (asynchronous, Phase 5: with validation)."""
        start_time = time.time()
        
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
                error="Empty text content",
                url=url,
                elapsed_ms=0
            )
        
        text_length = len(text)
        is_empty_retry = False
        
        # Phase 5: Main extraction with validation retry
        for validation_attempt in range(3):  # Max 2 retries = 3 total attempts
            try:
                # Build prompt (use empty retry prompt if needed)
                prompt = self._build_prompt(text, is_retry=(validation_attempt > 0), is_empty_retry=is_empty_retry)
                
                # Call Ollama
                ai_content = await self._call_ollama_with_retry(prompt, url, use_json_mode=True)
                
                # Parse JSON
                extracted_data = self._parse_json_response(ai_content)
                
                # Phase 5: Validate with Pydantic
                try:
                    validated = self._validate_extraction(extracted_data)
                    validated_dict = validated.to_dict()
                    
                    # Check for suspicious empty results (Phase 5)
                    all_empty = all(
                        not validated_dict.get(field) or len(validated_dict.get(field, [])) == 0
                        for field in ['products', 'services', 'customers', 'partnerships', 'case_studies']
                    )
                    
                    if all_empty and text_length > 1000 and not is_empty_retry:
                        # Suspicious empty result - retry with stronger prompt
                        logger.warning(f"Suspicious empty extraction for {url} (text length: {text_length}), retrying...")
                        is_empty_retry = True
                        continue
                    
                    # Format fields
                    products = self._format_field(validated_dict.get('products', []))
                    services = self._format_field(validated_dict.get('services', []))
                    customers = self._format_field(validated_dict.get('customers', []))
                    partnerships = self._format_field(validated_dict.get('partnerships', []))
                    case_studies = self._format_field(validated_dict.get('case_studies', []))
                    
                    # Determine status
                    status = 'empty_but_checked' if (all_empty and is_empty_retry) else self._determine_status(
                        products, services, customers, partnerships, case_studies
                    )
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    
                    if status == 'success':
                        logger.info(f"Extracted data for {url}")
                    elif status == 'empty_but_checked':
                        logger.info(f"Empty extraction verified for {url} (checked twice)")
                    
                    return ExtractionResult(
                        products=products,
                        services=services,
                        customers=customers,
                        partnerships=partnerships,
                        case_studies=case_studies,
                        status=status,
                        url=url,
                        elapsed_ms=elapsed_ms
                    )
                    
                except ValueError as ve:
                    # Validation failed - retry with fix JSON prompt
                    if validation_attempt < 2:
                        logger.warning(f"Validation failed for {url}, retry {validation_attempt + 1}/2: {ve}")
                        continue
                    else:
                        # Max retries reached
                        logger.error(f"Validation failed after 2 retries for {url}: {ve}")
                        return ExtractionResult(
                            products="N/A",
                            services="N/A",
                            customers="N/A",
                            partnerships="N/A",
                            case_studies="N/A",
                            status="failed",
                            error=f"Validation failed: {str(ve)[:50]}",
                            url=url,
                            elapsed_ms=(time.time() - start_time) * 1000
                        )
                        
            except (TimeoutError, ConnectionError, ollama.ResponseError) as e:
                logger.error(f"Ollama failed for {url}: {e}")
                return ExtractionResult(
                    products="N/A",
                    services="N/A",
                    customers="N/A",
                    partnerships="N/A",
                    case_studies="N/A",
                    status="failed",
                    error=f"Ollama error: {str(e)[:50]}",
                    url=url,
                    elapsed_ms=(time.time() - start_time) * 1000
                )
            except json.JSONDecodeError as e:
                if validation_attempt < 2:
                    logger.warning(f"JSON parse error for {url}, retry {validation_attempt + 1}/2")
                    continue
                logger.error(f"JSON parsing error for {url}: {e}")
                return ExtractionResult(
                    products="N/A",
                    services="N/A",
                    customers="N/A",
                    partnerships="N/A",
                    case_studies="N/A",
                    status="failed",
                    error=f"JSON error: {str(e)[:50]}",
                    url=url,
                    elapsed_ms=(time.time() - start_time) * 1000
                )
        
        # Should not reach here, but handle anyway
        return ExtractionResult(
            products="N/A",
            services="N/A",
            customers="N/A",
            partnerships="N/A",
            case_studies="N/A",
            status="failed",
            error="Max retries exceeded",
            url=url,
            elapsed_ms=(time.time() - start_time) * 1000
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

