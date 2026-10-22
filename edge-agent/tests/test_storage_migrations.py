"""Tests for SQLite database schema versioning, fresh install, and upgrade migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import (
    apply_migrations,
    get_current_schema_version,
)


def test_fresh_database_applies_all_migrations(tmp_path: Path) -> None:
    """Verifies that an empty SQLite database applies all forward migrations."""
    db_file = tmp_path / "fresh_edge.db"
    db = Database(db_file)

    # Initially version 0
    assert get_current_schema_version(db) == 0

    # Apply all migrations
    applied = apply_migrations(db)
    assert applied == 2
    assert get_current_schema_version(db) == 2

    # Verify tables exist
    with db.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        }

    expected_tables = {
        "schema_migrations",
        "settings",
        "device_identity",
        "assessment_events",
        "sync_queue",
        "sync_state",
    }
    assert expected_tables.issubset(tables)

    # Calling apply_migrations again is idempotent (0 new migrations)
    applied_again = apply_migrations(db)
    assert applied_again == 0


def test_incremental_upgrade_path(tmp_path: Path) -> None:
    """Verifies upgrading from migration version 1 to version 2."""
    db_file = tmp_path / "upgrade_edge.db"
    db = Database(db_file)

    # 1. Apply only version 1
    applied_v1 = apply_migrations(db, target_version=1)
    assert applied_v1 == 1
    assert get_current_schema_version(db) == 1

    # Verify indexes from v2 do not exist yet
    with db.connect() as conn:
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
    assert "idx_sync_queue_lookup" not in indexes

    # 2. Upgrade to version 2
    applied_v2 = apply_migrations(db, target_version=2)
    assert applied_v2 == 1
    assert get_current_schema_version(db) == 2

    # Verify indexes now exist
    with db.connect() as conn:
        indexes_after = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()
        }
    assert "idx_sync_queue_lookup" in indexes_after
    assert "idx_assessment_events_created" in indexes_after


def test_foreign_key_enforcement(tmp_path: Path) -> None:
    """Verifies SQLite PRAGMA foreign_keys is enforced on sync_queue."""
    db_file = tmp_path / "fk_edge.db"
    db = Database(db_file)
    apply_migrations(db)

    # Inserting into sync_queue with non-existent assessment_event must fail with IntegrityError
    with db.transaction() as cur:
        try:
            cur.execute(
                """
                INSERT INTO sync_queue (event_id, state, attempt_count, next_attempt_at)
                VALUES ('non-existent-uuid', 'pending', 0, '2026-10-20T12:00:00Z');
                """
            )
            raised = False
        except sqlite3.IntegrityError:
            raised = True

    assert raised is True
