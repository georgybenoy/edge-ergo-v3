"""SQLite database connection and lifecycle manager for EdgeErgo V3.

Enforces:
- Write-Ahead Logging (WAL) for high concurrency
- Foreign key constraints enforcement
- Atomic transactions with immediate locking
- Safe data directory resolution under %LOCALAPPDATA%
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


def get_default_data_dir() -> Path:
    """Returns the platform-appropriate data directory for EdgeErgo local storage."""
    # 1. Environment variable override
    env_dir = os.environ.get("EDGE_ERGO_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. Windows %LOCALAPPDATA% (Default: C:\\Users\\<user>\\AppData\\Local\\EdgeErgo)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        p = Path(local_app_data) / "EdgeErgo"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 3. Fallback to user home directory
    p = Path.home() / ".edge_ergo"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_default_db_path() -> Path:
    """Returns the default SQLite database path."""
    return get_default_data_dir() / "edge_ergo.db"


class Database:
    """Thread-safe SQLite database manager enforcing WAL mode and foreign keys."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_connection()

    def _init_connection(self) -> None:
        """Applies essential PRAGMA settings on the SQLite connection."""
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
        finally:
            conn.close()
        logger.debug("Initialized SQLite connection at %s (WAL=ON, FK=ON)", self.db_path)

    def connect(self) -> sqlite3.Connection:
        """Creates a new SQLite connection with foreign keys and dict-like row access."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Provides an atomic transaction scope with BEGIN IMMEDIATE."""
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Executes a single query and commits immediately."""
        with self.transaction() as cur:
            cur.execute(query, params)
            return cur

    def fetchone(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        """Executes a read query returning a single row."""
        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return cast(sqlite3.Row | None, row)
        finally:
            conn.close()

    def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Executes a read query returning all matching rows."""
        conn = self.connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return list(cur.fetchall())
        finally:
            conn.close()
