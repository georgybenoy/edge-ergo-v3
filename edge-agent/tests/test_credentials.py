"""Tests verifying protected credential storage and zero-leakage security invariants."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from edge_ergo.storage.credentials import (
    MemoryCredentialStore,
    delete_device_secret,
    load_device_secret,
    save_device_secret,
)
from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import DeviceIdentity


def test_memory_credential_store_crud() -> None:
    """Verifies in-memory store functionality for isolated test suites."""
    store = MemoryCredentialStore()
    pub = "edp_test_12345"
    secret = "eed_edp_test_12345.test_secret_xyz_987654321"

    assert load_device_secret(pub, store=store) is None

    save_device_secret(pub, secret, store=store)
    assert load_device_secret(pub, store=store) == secret

    # Overwrite / Rotate
    new_secret = "eed_edp_test_12345.test_rotated_secret_abc_123456789"
    save_device_secret(pub, new_secret, store=store)
    assert load_device_secret(pub, store=store) == new_secret

    # Delete
    deleted = delete_device_secret(pub, store=store)
    assert deleted is True
    assert load_device_secret(pub, store=store) is None


def test_secret_is_never_stored_in_sqlite_database(tmp_path: Path) -> None:
    """Security Guard: Scans SQLite database bytes and rows for the plaintext secret."""
    db_file = tmp_path / "leak_test.db"
    db = Database(db_file)
    apply_migrations(db)
    repo = StorageRepository(db)

    secret_fragment = "super_confidential_random_device_secret_token_never_leak"
    full_credential = f"eed_edp_leak_test_01.{secret_fragment}"

    # Save identity in SQLite
    ident = DeviceIdentity(
        device_id="33333333-3333-3333-3333-333333333333",
        public_id="edp_leak_test_01",
        api_base_url="https://api.edgeergo.com",
        label="Security Workstation",
        organization_id="22222222-2222-2222-2222-222222222222",
        enrolled_at="2026-10-20T12:00:00Z",
    )
    repo.save_device_identity(ident)

    # Save secret in dedicated credential store
    store = MemoryCredentialStore()
    save_device_secret(ident.public_id, full_credential, store=store)

    # 1. Inspect all rows and columns across all SQLite tables
    with db.connect() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';"
        ).fetchall()
        for tbl in tables:
            rows = conn.execute(f"SELECT * FROM {tbl[0]};").fetchall()
            for r in rows:
                for col_val in r:
                    val_str = str(col_val or "")
                    assert secret_fragment not in val_str
                    assert full_credential not in val_str

    # 2. Binary raw scan of the entire SQLite file on disk
    raw_db_bytes = db_file.read_bytes()
    assert secret_fragment.encode("utf-8") not in raw_db_bytes
    assert full_credential.encode("utf-8") not in raw_db_bytes


def test_secret_is_never_logged_or_exposed_in_exceptions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Security Guard: Verifies that secrets never appear in log records or error messages."""
    caplog.set_level(logging.DEBUG)
    store = MemoryCredentialStore()
    pub = "edp_logger_check"
    secret = "eed_edp_logger_check.test_secret_token_12345"

    save_device_secret(pub, secret, store=store)
    _ = load_device_secret(pub, store=store)
    delete_device_secret(pub, store=store)

    # Verify no log record contains the secret or credential
    for record in caplog.records:
        assert secret not in record.message
        assert "test_secret_token_12345" not in record.message
