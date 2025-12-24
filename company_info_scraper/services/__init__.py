# Services module for company_info_scraper
# Contains async services decoupled from Scrapy pipeline

from .llm_service import (
    LLMExtractionService,
    ExtractionResult,
    BatchExtractionResult,
    extract_texts_parallel
)
from .extraction_queue import (
    ExtractionQueue,
    QueuedItem,
    ProcessedItem,
    get_global_queue,
    reset_global_queue
)
from .site_detector import (
    SiteDetector,
    SiteType,
    DetectionResult,
    detect_site_type,
    detect_site_type_sync,
    # Phase 3: Corporate detection (kept for backward compatibility)
)
from .batch_processor import (
    BatchProcessor,
    BatchResult,
    DomainResult,
    RateLimiter,
    RateLimitConfig,
    process_domains,
    # Graceful shutdown (PH6-S2)
    request_shutdown,
    reset_shutdown,
    is_shutdown_requested,
    # Domain utilities
    extract_domain_name,
)

__all__ = [
    # LLM Service
    'LLMExtractionService',
    'ExtractionResult',
    'BatchExtractionResult',
    'extract_texts_parallel',
    # Extraction Queue
    'ExtractionQueue',
    'QueuedItem',
    'ProcessedItem',
    'get_global_queue',
    'reset_global_queue',
    # Site Detector
    'SiteDetector',
    'SiteType',
    'DetectionResult',
    'detect_site_type',
    'detect_site_type_sync',
    # Batch Processor
    'BatchProcessor',
    'BatchResult',
    'DomainResult',
    'RateLimiter',
    'RateLimitConfig',
    'process_domains',
    # Graceful Shutdown (PH6-S2)
    'request_shutdown',
    'reset_shutdown',
    'is_shutdown_requested',
    # Domain utilities
    'extract_domain_name',
]

