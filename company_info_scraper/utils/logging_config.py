"""
Logging Configuration Module (PH6-S3)

Provides structured logging with JSON output support for production monitoring.

Features:
- JSON format for log aggregation (ELK, CloudWatch, etc.)
- Plain text format for development
- Configurable via environment variables and config file
- Automatic context enrichment (timestamp, level, source)

Environment Variables:
- LOG_FORMAT: 'json' or 'text' (default: 'text')
- LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: 'INFO')
- LOG_FILE: Path to log file (optional)

Usage:
    from company_info_scraper.logging_config import setup_logging
    
    # From config
    setup_logging(config={'log_level': 'DEBUG', 'log_format': 'json'})
    
    # From environment
    setup_logging()  # Reads LOG_FORMAT, LOG_LEVEL env vars
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    
    Outputs logs as JSON objects for easy parsing by log aggregation systems.
    """
    
    def __init__(
        self, 
        include_timestamp: bool = True,
        include_source: bool = True,
        include_process: bool = False,
        extra_fields: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_source = include_source
        self.include_process = include_process
        self.extra_fields = extra_fields or {}
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
        }
        
        # Add timestamp
        if self.include_timestamp:
            log_data['timestamp'] = datetime.fromtimestamp(
                record.created, 
                tz=timezone.utc
            ).isoformat()
        
        # Add source information
        if self.include_source:
            log_data['source'] = {
                'file': record.filename,
                'line': record.lineno,
                'function': record.funcName
            }
        
        # Add process/thread info
        if self.include_process:
            log_data['process'] = {
                'id': record.process,
                'name': record.processName,
                'thread': record.thread,
                'thread_name': record.threadName
            }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add any extra fields from the record
        if hasattr(record, 'extra_data'):
            log_data['data'] = record.extra_data
        
        # Add configured extra fields
        log_data.update(self.extra_fields)
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for development.
    
    Adds ANSI colors to log levels for better readability.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def __init__(self, fmt: str = None, use_colors: bool = True):
        super().__init__(fmt or '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with optional colors."""
        if self.use_colors and record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{record.levelname}"
                f"{self.RESET}"
            )
        return super().format(record)


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds context to all log messages.
    
    Usage:
        logger = ContextLogger(logging.getLogger(__name__), {'domain': 'example.com'})
        logger.info("Processing page")  # Includes domain in output
    """
    
    def process(self, msg, kwargs):
        """Add context to log message."""
        extra = kwargs.get('extra', {})
        extra['extra_data'] = {**self.extra, **extra.get('extra_data', {})}
        kwargs['extra'] = extra
        return msg, kwargs


def setup_logging(
    config: Optional[Dict[str, Any]] = None,
    log_format: Optional[str] = None,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    app_name: str = 'company_info_scraper'
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        config: Configuration dict with log settings
        log_format: Override format ('json' or 'text')
        log_level: Override log level
        log_file: Override log file path
        app_name: Application name for logs
        
    Returns:
        Configured root logger
        
    Environment Variables:
        LOG_FORMAT: 'json' or 'text'
        LOG_LEVEL: DEBUG, INFO, WARNING, ERROR
        LOG_FILE: Log file path
    """
    config = config or {}
    
    # Determine format (priority: arg > env > config > default)
    fmt = (
        log_format or 
        os.environ.get('LOG_FORMAT') or 
        config.get('log_format', 'text')
    ).lower()
    
    # Determine level
    level_str = (
        log_level or 
        os.environ.get('LOG_LEVEL') or 
        config.get('log_level', 'INFO')
    ).upper()
    level = getattr(logging, level_str, logging.INFO)
    
    # Determine log file
    file_path = (
        log_file or 
        os.environ.get('LOG_FILE') or 
        config.get('log_file')
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if fmt == 'json':
        console_handler.setFormatter(JSONFormatter(
            extra_fields={'app': app_name}
        ))
    else:
        console_handler.setFormatter(ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            use_colors=True
        ))
    
    root_logger.addHandler(console_handler)
    
    # Create file handler if configured
    if file_path:
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to prevent huge log files
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        # Always use JSON for file logs (easier to parse)
        file_handler.setFormatter(JSONFormatter(
            extra_fields={'app': app_name}
        ))
        
        root_logger.addHandler(file_handler)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging configured: format={fmt}, level={level_str}, "
        f"file={file_path or 'none'}"
    )
    
    return root_logger


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get a logger with optional context.
    
    Args:
        name: Logger name (usually __name__)
        context: Optional context dict to include in all logs
        
    Returns:
        Logger or ContextLogger if context provided
    """
    logger = logging.getLogger(name)
    
    if context:
        return ContextLogger(logger, context)
    
    return logger


def log_exception(logger: logging.Logger, message: str, exc: Exception):
    """
    Log an exception with full context.
    
    Args:
        logger: Logger to use
        message: Context message
        exc: Exception to log
    """
    logger.error(
        message,
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={
            'extra_data': {
                'exception_type': type(exc).__name__,
                'exception_message': str(exc)
            }
        }
    )


# =============================================================================
# Convenience functions for common logging patterns
# =============================================================================

def log_scrape_start(logger: logging.Logger, domain: str, scraper_type: str):
    """Log start of scraping operation."""
    logger.info(
        f"Starting scrape: {domain}",
        extra={'extra_data': {'domain': domain, 'scraper_type': scraper_type}}
    )


def log_scrape_complete(
    logger: logging.Logger, 
    domain: str, 
    success: bool, 
    records: int,
    elapsed_ms: float
):
    """Log completion of scraping operation."""
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"Scrape complete: {domain} - {'success' if success else 'failed'}",
        extra={
            'extra_data': {
                'domain': domain,
                'success': success,
                'records': records,
                'elapsed_ms': elapsed_ms
            }
        }
    )


def log_llm_call(
    logger: logging.Logger,
    url: str,
    success: bool,
    elapsed_ms: float,
    retry_count: int = 0
):
    """Log LLM extraction call."""
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"LLM extraction: {url} - {'success' if success else 'failed'}",
        extra={
            'extra_data': {
                'url': url,
                'success': success,
                'elapsed_ms': elapsed_ms,
                'retries': retry_count
            }
        }
    )


def log_batch_progress(
    logger: logging.Logger,
    current: int,
    total: int,
    domain: str,
    success: bool
):
    """Log batch processing progress."""
    logger.info(
        f"Progress: {current}/{total} ({current*100//total}%) - {domain}",
        extra={
            'extra_data': {
                'progress': {
                    'current': current,
                    'total': total,
                    'percent': current * 100 // total
                },
                'domain': domain,
                'success': success
            }
        }
    )

