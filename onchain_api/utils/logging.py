"""Logging configuration for OnChain API."""

import logging
import sys
from typing import Optional
import structlog
from structlog.stdlib import LoggerFactory


def setup_logging(settings) -> None:
    """Setup structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Setup file logging if specified
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setLevel(getattr(logging, settings.log_level.upper()))
        
        if settings.log_format == "json":
            file_handler.setFormatter(logging.Formatter('%(message)s'))
        else:
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
        
        logging.getLogger().addHandler(file_handler)