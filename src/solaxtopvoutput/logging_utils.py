"""Logging setup helpers."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_level: str, log_file: Path) -> logging.Logger:
    """Configure application logging."""

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger("solaxtopvoutput")
