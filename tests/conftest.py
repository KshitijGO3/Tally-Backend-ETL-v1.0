"""Shared test fixtures and configuration for Backend ETL."""

from pathlib import Path

import pytest

try:
    from tally_core.db import DBManager
except ImportError:
    DBManager = None


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    # Treat no tests collected in empty stub suite as clean exit (0)
    if exitstatus == 5:
        session.exitstatus = 0


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Returns path to a freshly written default config.json."""
    cfg = tmp_path / "config.json"
    cfg.write_text(
        '{"tally_ip":"localhost","tally_port":9000,"active_companies":[],'
        '"reconciliation_alert":false,"setup_complete":false}',
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def tmp_db(tmp_path: Path):
    """In-memory or temp-file SQLite DBManager pre-bootstrapped with DDL if available."""
    if DBManager is None:
        pytest.skip("tally_core not installed in standalone Backend ETL environment")
    db_path = tmp_path / "test_warehouse.db"
    mgr = DBManager(str(db_path))
    mgr.bootstrap()
    return mgr
