"""Logging configuration and utilities."""

import sys
import logging
from pathlib import Path
from typing import Optional
import structlog
from structlog.stdlib import LoggerFactory

from btc_collector.models.config import CollectorConfig


def setup_logging(config: CollectorConfig) -> None:
    """Setup structured logging with the specified configuration."""
    
    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format="%(message)s",
        stream=sys.stdout,
    )
    
    # Create log directory if specified
    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure processors based on format
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if config.log_format.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Setup file logging if specified
    if config.log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            config.log_file,
            maxBytes=config.log_max_size_mb * 1024 * 1024,
            backupCount=config.log_backup_count
        )
        file_handler.setLevel(getattr(logging, config.log_level.upper()))
        
        # Add file handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)