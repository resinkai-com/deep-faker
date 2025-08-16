"""Logging configuration for deep_faker."""

import logging
import sys
from typing import Optional


def setup_logging(level: int = logging.INFO) -> None:
    """Setup default logging configuration for deep_faker."""
    # Only setup if not already configured
    if logging.getLogger().handlers:
        return

    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Prevent duplicate logs from propagating
    root_logger.propagate = False


_setup_logging_done = False


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a logger with default settings.

    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override

    Returns:
        Configured logger instance
    """
    global _setup_logging_done
    if not _setup_logging_done:
        setup_logging()
        _setup_logging_done = True

    logger = logging.getLogger(name)

    if level is not None:
        logger.setLevel(level)

    return logger
