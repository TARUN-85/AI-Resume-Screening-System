"""
Centralized logging configuration.

Every module gets its logger via get_logger(__name__) so log lines are
traceable to their source module. Resume content itself is never logged
at INFO level -- only metadata (filenames, lengths, scores) -- to avoid
leaking potentially sensitive candidate data into log files.
"""

import logging
import sys

from src.config import LOG_FORMAT, LOG_LEVEL

_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.addHandler(handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    _configure_root_logger()
    return logging.getLogger(name)
