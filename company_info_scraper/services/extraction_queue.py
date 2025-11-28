"""
Extraction Queue Service (PH2-S2)

Stores raw text for deferred LLM processing.
Decouples scraping speed from LLM speed.
"""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, AsyncIterator

from .llm_service import LLMExtractionService, ExtractionResult

logger = logging.getLogger(__name__)


@dataclass
class QueuedItem:
    """Item queued for LLM extraction."""
    url: str
    raw_text: str
    scraped_at: str  # ISO format timestamp
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QueuedItem':
        return cls(**data)


@dataclass
class ProcessedItem:
    """Item after LLM extraction."""
    url: str
    products: str
    customers: str
    partnerships: str
    case_studies: str
    extraction_status: str
    error: Optional[str] = None


class ExtractionQueue:
    """Queue for storing scraped items and processing them with LLM.
    
    Usage:
        # During scraping - add items to queue
        queue = ExtractionQueue()
        queue.add(url, raw_text)
        queue.save()  # Persist to disk
        
        # After scraping - process queue
        queue = ExtractionQueue.load(queue_file)
        results = await queue.process_all()
    """
    
    def __init__(self, queue_file: Optional[str] = None):
        """Initialize queue.
        
        Args:
            queue_file: Path to persist queue. If None, uses temp file.
        """
        self._items: List[QueuedItem] = []
        self._queue_file = queue_file or self._default_queue_file()
    
    @staticmethod
    def _default_queue_file() -> str:
        """Generate default queue file path."""
        return os.path.join(tempfile.gettempdir(), 'scraper_queue.json')
    
    @property
    def queue_file(self) -> str:
        return self._queue_file
    
    def add(self, url: str, raw_text: str) -> None:
        """Add an item to the queue."""
        item = QueuedItem(
            url=url,
            raw_text=raw_text,
            scraped_at=datetime.utcnow().isoformat()
        )
        self._items.append(item)
        logger.debug(f"Queued item for {url}")
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __iter__(self):
        return iter(self._items)
    
    def clear(self) -> None:
        """Clear all items from queue."""
        self._items.clear()
    
    def save(self, filepath: Optional[str] = None) -> str:
        """Save queue to disk.
        
        Args:
            filepath: Optional path override
            
        Returns:
            Path where queue was saved
        """
        save_path = filepath or self._queue_file
        data = {
            'version': 1,
            'saved_at': datetime.utcnow().isoformat(),
            'items': [item.to_dict() for item in self._items]
        }
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self._items)} items to {save_path}")
        return save_path
    
    @classmethod
    def load(cls, filepath: str) -> 'ExtractionQueue':
        """Load queue from disk.
        
        Args:
            filepath: Path to queue file
            
        Returns:
            ExtractionQueue instance with loaded items
        """
        queue = cls(queue_file=filepath)
        
        if not os.path.exists(filepath):
            logger.warning(f"Queue file not found: {filepath}")
            return queue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        queue._items = [QueuedItem.from_dict(item) for item in data.get('items', [])]
        logger.info(f"Loaded {len(queue._items)} items from {filepath}")
        return queue
    
    async def process_all(
        self,
        llm_service: Optional[LLMExtractionService] = None,
        on_progress: Optional[callable] = None
    ) -> List[ProcessedItem]:
        """Process all queued items with LLM extraction.
        
        Args:
            llm_service: LLM service instance (creates default if None)
            on_progress: Optional callback(current, total, url) for progress updates
            
        Returns:
            List of ProcessedItem with extraction results
        """
        if not self._items:
            logger.warning("No items in queue to process")
            return []
        
        service = llm_service or LLMExtractionService()
        results: List[ProcessedItem] = []
        total = len(self._items)
        
        logger.info(f"Processing {total} items from queue...")
        
        for i, item in enumerate(self._items, 1):
            if on_progress:
                on_progress(i, total, item.url)
            
            logger.info(f"Processing [{i}/{total}]: {item.url}")
            
            # Call async LLM service
            extraction = await service.extract(item.raw_text, url=item.url)
            
            results.append(ProcessedItem(
                url=item.url,
                products=extraction.products,
                customers=extraction.customers,
                partnerships=extraction.partnerships,
                case_studies=extraction.case_studies,
                extraction_status=extraction.status,
                error=extraction.error
            ))
        
        # Summary
        success_count = sum(1 for r in results if r.extraction_status == 'success')
        failure_count = total - success_count
        logger.info(f"Processing complete: {success_count} success, {failure_count} failure")
        
        return results
    
    async def process_all_parallel(
        self,
        llm_service: Optional[LLMExtractionService] = None,
        max_concurrent: int = 3
    ) -> List[ProcessedItem]:
        """Process all queued items in parallel (limited concurrency).
        
        Args:
            llm_service: LLM service instance
            max_concurrent: Maximum concurrent LLM calls
            
        Returns:
            List of ProcessedItem with extraction results
        """
        if not self._items:
            return []
        
        service = llm_service or LLMExtractionService()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_one(item: QueuedItem) -> ProcessedItem:
            async with semaphore:
                extraction = await service.extract(item.raw_text, url=item.url)
                return ProcessedItem(
                    url=item.url,
                    products=extraction.products,
                    customers=extraction.customers,
                    partnerships=extraction.partnerships,
                    case_studies=extraction.case_studies,
                    extraction_status=extraction.status,
                    error=extraction.error
                )
        
        logger.info(f"Processing {len(self._items)} items (max {max_concurrent} concurrent)...")
        tasks = [process_one(item) for item in self._items]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r.extraction_status == 'success')
        logger.info(f"Processing complete: {success_count}/{len(results)} success")
        
        return list(results)


# Global queue instance for use in Scrapy pipeline
_global_queue: Optional[ExtractionQueue] = None


def get_global_queue() -> ExtractionQueue:
    """Get or create global queue instance."""
    global _global_queue
    if _global_queue is None:
        _global_queue = ExtractionQueue()
    return _global_queue


def reset_global_queue() -> None:
    """Reset global queue (for testing or new crawl sessions)."""
    global _global_queue
    _global_queue = None

