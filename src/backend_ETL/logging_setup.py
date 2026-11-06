"""Centralised logging setup for the standalone PostgreSQL Backend ETL service.

Configures:
  - A rotating file handler writing to:
      - Env ``BACKEND_LOG_DIR`` if defined
      - On Windows: ``%ProgramData%\\TallyBackendETL\\logs\\<name>.log``
      - On Linux / Unix: ``/var/log/backend_etl/<name>.log`` (falling back to ``logs/<name>.log``)
  - A console (stderr) handler for interactive / server logs
  - A consistent timestamped format matching the Tally replication ecosystem:
      ``%(asctime)s  %(levelname)-8s  %(name)s  %(message)s``

The logs directory is created automatically if it does not exist.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_default_log_dir() -> Path:
    """Returns the default directory for backend ETL logs.

    Resolution order:
    1. Environment variable ``BACKEND_LOG_DIR``
    2. Windows: ``%ProgramData%\\TallyBackendETL\\logs``
    3. Linux / Unix: ``/var/log/backend_etl`` (with fallback to local ``logs/`` if unwritable)
    """
    env_dir = os.environ.get("BACKEND_LOG_DIR")
    if env_dir:
        return Path(env_dir)

    if os.name == "nt" or sys.platform == "win32":
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        return Path(program_data) / "TallyBackendETL" / "logs"

    # Unix / Linux / Container environments
    candidate = Path("/var/log/backend_etl")
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        # Fallback to local logs directory if not running with root/var permissions
        return Path("logs")


def setup_logging(
    process_name: str = "backend_etl",
    log_dir: str | Path | None = None,
    level: int | str = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB per file
    backup_count: int = 5,
) -> logging.Logger:
    """Configures file + console logging for the Backend ETL process.

    Args:
        process_name: Identifier used as the log filename, producing
                      ``<log_dir>/<process_name>.log``.
        log_dir:      Directory for log files. Defaults to ``get_default_log_dir()``.
        level:        Root logging level (default ``INFO``). Can be int or string.
        max_bytes:    Maximum size in bytes before file rotation (default 10 MB).
        backup_count: Number of rotated backups to keep (default 5).

    Returns:
        The configured root :class:`logging.Logger`.
    """
    if isinstance(level, str):
        level_int = getattr(logging, level.upper(), logging.INFO)
    else:
        level_int = level

    log_directory = Path(log_dir) if log_dir is not None else get_default_log_dir()
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Graceful fallback to working directory logs/
        log_directory = Path("logs")
        log_directory.mkdir(parents=True, exist_ok=True)

    log_file = log_directory / f"{process_name}.log"

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level_int)

    # ── Rotating file handler ────────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=False,  # Create the file immediately on startup
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level_int)

    # ── Console (stderr) handler — always present for server visibility ──────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(level_int)

    # Deduplicate handlers if called multiple times
    if not root.handlers:
        root.addHandler(file_handler)
        root.addHandler(console_handler)
    else:
        root.handlers.clear()
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    logger = logging.getLogger(process_name)
    logger.info(
        "Backend ETL logging initialised — file: %s (max %d MB × %d backups, level: %s)",
        log_file,
        max_bytes // (1024 * 1024),
        backup_count,
        logging.getLevelName(level_int),
    )
    return root
