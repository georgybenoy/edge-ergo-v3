"""Versioned SQLite schema migrations for EdgeErgo local storage.

Guarantees:
- Forward-only, incremental version progression recorded in schema_migrations
- Atomic per-migration transactions
- Verifiable fresh-install and upgrade paths
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from edge_ergo.storage.database import Database

logger = logging.getLogger(__name__)


def _migration_001_initial_schema(cursor: sqlite3.Cursor) -> None:
    """Migration 1: Core tables for settings, identity, telemetry, queue, and state."""
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_identity (
            device_id TEXT PRIMARY KEY,
            public_id TEXT UNIQUE NOT NULL,
            api_base_url TEXT NOT NULL,
            label TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            enrolled_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assessment_events (
            event_id TEXT PRIMARY KEY,
            captured_at TEXT NOT NULL,
            scoring_method TEXT NOT NULL,
            scoring_version TEXT NOT NULL,
            validity TEXT NOT NULL,
            score REAL,
            neck_score INTEGER,
            trunk_score INTEGER,
            upper_arm_score INTEGER,
            postural_features TEXT,
            guidance_codes TEXT NOT NULL,
            software_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sync_queue (
            event_id TEXT PRIMARY KEY REFERENCES assessment_events(event_id) ON DELETE CASCADE,
            state TEXT NOT NULL CHECK(state IN ('pending', 'in_flight', 'acked', 'dead')),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT NOT NULL,
            last_error_code TEXT,
            leased_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_success_at TEXT,
            queue_depth_cache INTEGER NOT NULL DEFAULT 0,
            last_heartbeat_at TEXT
        );

        INSERT OR IGNORE INTO sync_state (id, last_success_at, queue_depth_cache, last_heartbeat_at)
        VALUES (1, NULL, 0, NULL);
    """)


def _migration_002_performance_indexes(cursor: sqlite3.Cursor) -> None:
    """Migration 2: Optimization indexes for queue polling, lease recovery, and retention."""
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_assessment_events_created 
        ON assessment_events(created_at);

        CREATE INDEX IF NOT EXISTS idx_sync_queue_lookup 
        ON sync_queue(state, next_attempt_at);

        CREATE INDEX IF NOT EXISTS idx_sync_queue_leases 
        ON sync_queue(state, leased_at);
    """)


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Cursor], None]]] = [
    (1, "001_initial_schema", _migration_001_initial_schema),
    (2, "002_performance_indexes", _migration_002_performance_indexes),
]


def ensure_migration_table(cursor: sqlite3.Cursor) -> None:
    """Creates the schema_migrations tracking table if it does not exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
    """)


def get_current_schema_version(db: Database) -> int:
    """Returns the highest applied schema version, or 0 if uninitialized."""
    with db.transaction() as cur:
        ensure_migration_table(cur)
        cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations;")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def apply_migrations(db: Database, target_version: int | None = None) -> int:
    """Applies all pending forward-only migrations up to target_version.

    Returns the count of newly applied migrations.
    """
    applied_count = 0

    with db.transaction() as cur:
        ensure_migration_table(cur)
        cur.execute("SELECT version FROM schema_migrations;")
        applied_versions = {row[0] for row in cur.fetchall()}

        for version, name, migration_fn in MIGRATIONS:
            if target_version is not None and version > target_version:
                break

            if version not in applied_versions:
                logger.info("Applying SQLite migration %03d: %s...", version, name)
                migration_fn(cur)
                now_utc = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                    (version, name, now_utc),
                )
                applied_count += 1
                logger.info("Successfully applied SQLite migration %03d.", version)

    return applied_count
