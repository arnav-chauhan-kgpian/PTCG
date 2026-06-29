"""
Centralised logging configuration.

Reads two env vars:
    POKEMON_AI_LOG_LEVEL  (default "INFO")
    POKEMON_AI_LOG_FILE   (default unset → stderr only)

Loguru is configured idempotently — calling ``configure()`` more than once
is safe and has no compounding effect (the previous sinks are removed).
"""

from __future__ import annotations

import os
import sys

_CONFIGURED = False


def configure(*, force: bool = False) -> None:
    """Configure the global loguru logger from environment variables.

    Calling this more than once is a no-op unless ``force=True``.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return
    try:
        from loguru import logger
    except ImportError:
        return

    level = os.getenv("POKEMON_AI_LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("POKEMON_AI_LOG_FILE", "").strip()

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>{level: <8}</level> "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )
    if log_file:
        logger.add(
            log_file,
            level=level,
            rotation="50 MB",
            retention="14 days",
            compression="gz",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            serialize=False,
        )
    _CONFIGURED = True
