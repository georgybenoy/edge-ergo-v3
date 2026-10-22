"""Tests for Supabase SQL migration execution and upgrade paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.migrations import (
    apply_migration_file,
    get_applied_migrations,
    get_migrations_dir,
    run_migrations,
)

if TYPE_CHECKING:
    import psycopg


def test_migrations_apply_cleanly(clean_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies all migrations in supabase/migrations/ apply without error to an empty DB."""
    applied = run_migrations(clean_db)
    assert len(applied) >= 2, "Expected at least 2 migrations to apply"

    # Verify tables exist
    with clean_db.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
            """
        )
        tables = {row[0] for row in cur.fetchall()}

    expected_tables = {
        "organizations",
        "profiles",
        "organization_members",
        "devices",
        "device_enrollment_tokens",
        "assessment_events",
        "device_heartbeats",
        "audit_events",
        "schema_migrations",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_reapplying_migrations_is_idempotent(
    clean_db: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Verifies that re-running migrations does not re-apply already applied migrations."""
    first_run = run_migrations(clean_db)
    assert len(first_run) >= 2

    second_run = run_migrations(clean_db)
    assert second_run == [], "Second run should apply 0 migrations"

    applied_set = get_applied_migrations(clean_db)
    assert set(first_run) == applied_set


def test_migration_upgrade_path(clean_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies upgrade path: apply migration 1, insert valid data, apply migration 2."""
    migrations_dir = get_migrations_dir()
    migration_files = sorted(migrations_dir.glob("*.sql"))
    assert len(migration_files) >= 2, "Upgrade test requires at least 2 migration files"

    mig1 = migration_files[0]
    mig2 = migration_files[1]

    # Apply Migration 1 (Core Schema)
    apply_migration_file(clean_db, mig1)

    # Insert test organization and device under Migration 1
    with clean_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.organizations (id, name, slug)
            VALUES ('11111111-1111-1111-1111-111111111111', 'Acme Corp', 'acme-corp')
            RETURNING id;
            """
        )
        cur.execute(
            """
            INSERT INTO public.devices (id, organization_id, label, public_id, credential_hash)
            VALUES (
                '22222222-2222-2222-2222-222222222222',
                '11111111-1111-1111-1111-111111111111',
                'Station 1',
                'stn_001',
                'dummy_hash_for_test'
            );
            """
        )
    clean_db.commit()

    # Apply Migration 2 (Functions, Views, RLS)
    apply_migration_file(clean_db, mig2)

    # Verify data in organizations and devices was preserved through migration 2
    with clean_db.cursor() as cur:
        cur.execute(
            "SELECT name FROM public.organizations "
            "WHERE id = '11111111-1111-1111-1111-111111111111';"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Acme Corp"

        # Verify new view devices_public exists and accesses preserved row
        cur.execute(
            "SELECT label, public_id FROM public.devices_public "
            "WHERE id = '22222222-2222-2222-2222-222222222222';"
        )
        dev_row = cur.fetchone()
        assert dev_row is not None
        assert dev_row[0] == "Station 1"
        assert dev_row[1] == "stn_001"
