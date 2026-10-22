"""Row Level Security (RLS) and Schema Constraint Verification Tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import psycopg
import pytest
from psycopg import errors

from app.db.migrations import run_migrations

if TYPE_CHECKING:
    import psycopg


ORG_A_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ORG_B_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

USER_ADMIN_A = "11111111-1111-1111-1111-111111111111"
USER_REVIEWER_A = "22222222-2222-2222-2222-222222222222"
USER_ADMIN_B = "33333333-3333-3333-3333-333333333333"

DEVICE_A_ID = "d1111111-1111-1111-1111-111111111111"


@pytest.fixture
def seeded_db(
    clean_db: psycopg.Connection[tuple[object, ...]],
) -> psycopg.Connection[tuple[object, ...]]:
    """Applies migrations and seeds isolated test organizations, users, and roles."""
    run_migrations(clean_db)

    with clean_db.cursor() as cur:
        # Create Auth Users
        cur.execute(
            """
            INSERT INTO auth.users (id, email) VALUES
                (%s, 'admin_a@example.com'),
                (%s, 'reviewer_a@example.com'),
                (%s, 'admin_b@example.com');
            """,
            (USER_ADMIN_A, USER_REVIEWER_A, USER_ADMIN_B),
        )

        # Update Profiles (automatically created by on_auth_user_created trigger)
        cur.execute(
            """
            INSERT INTO public.profiles (id, display_name) VALUES
                (%s, 'Admin A'),
                (%s, 'Reviewer A'),
                (%s, 'Admin B')
            ON CONFLICT (id) DO UPDATE
            SET display_name = EXCLUDED.display_name;
            """,
            (USER_ADMIN_A, USER_REVIEWER_A, USER_ADMIN_B),
        )

        # Create Organizations
        cur.execute(
            """
            INSERT INTO public.organizations (id, name, slug) VALUES
                (%s, 'Organization A', 'org-a'),
                (%s, 'Organization B', 'org-b');
            """,
            (ORG_A_ID, ORG_B_ID),
        )

        # Add Memberships
        cur.execute(
            """
            INSERT INTO public.organization_members (organization_id, user_id, role) VALUES
                (%s, %s, 'admin'),
                (%s, %s, 'reviewer'),
                (%s, %s, 'admin');
            """,
            (ORG_A_ID, USER_ADMIN_A, ORG_A_ID, USER_REVIEWER_A, ORG_B_ID, USER_ADMIN_B),
        )

        # Seed Device in Org A
        cur.execute(
            """
            INSERT INTO public.devices (
                id, organization_id, label, status, public_id, credential_hash
            ) VALUES (
                %s, %s, 'Workstation A-1', 'active', 'pub_a1', 'sha256_mock_hash'
            );
            """,
            (DEVICE_A_ID, ORG_A_ID),
        )

        # Seed Assessment Event in Org A
        cur.execute(
            """
            INSERT INTO public.assessment_events (
                event_id, device_id, organization_id, captured_at,
                scoring_method, scoring_version, validity, score,
                neck_score, trunk_score, upper_arm_score, software_version
            ) VALUES (
                'e1111111-1111-1111-1111-111111111111', %s, %s, now(),
                'rula_v1_screening', '1.0.0', 'valid', 3.5,
                2, 2, 3, '3.0.0'
            );
            """,
            (DEVICE_A_ID, ORG_A_ID),
        )
    clean_db.commit()
    return clean_db


def set_auth_context(
    conn: psycopg.Connection[tuple[object, ...]],
    role: str = "authenticated",
    user_id: str | None = None,
) -> None:
    """Sets PostgreSQL role and request.jwt.claim context for RLS testing."""
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"SET ROLE {role};")
        if user_id:
            cur.execute(
                "SELECT set_config('request.jwt.claim.sub', %s, false);",
                (user_id,),
            )
            claims = json.dumps({"sub": user_id, "role": role})
            cur.execute(
                "SELECT set_config('request.jwt.claims', %s, false);",
                (claims,),
            )
    conn.commit()


def reset_auth_context(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """Resets role back to postgres superuser."""
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("RESET ROLE;")
        cur.execute("SELECT set_config('request.jwt.claim.sub', '', false);")
        cur.execute("SELECT set_config('request.jwt.claims', '', false);")
    conn.commit()


def test_anon_access_is_denied(seeded_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies that unauthenticated anon role is denied all access."""
    set_auth_context(seeded_db, role="anon")
    try:
        with seeded_db.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("SELECT * FROM public.organizations;")
    finally:
        reset_auth_context(seeded_db)


def test_tenant_isolation_member_reads_only_own_org(
    seeded_db: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Verifies user in Org A sees only Org A, while user in Org B cannot see Org A."""
    # Member in Org A
    set_auth_context(seeded_db, role="authenticated", user_id=USER_ADMIN_A)
    try:
        with seeded_db.cursor() as cur:
            cur.execute("SELECT id FROM public.organizations;")
            org_ids = [str(row[0]) for row in cur.fetchall()]
            assert org_ids == [ORG_A_ID]

            cur.execute("SELECT label FROM public.devices;")
            devices = [row[0] for row in cur.fetchall()]
            assert devices == ["Workstation A-1"]
    finally:
        reset_auth_context(seeded_db)

    # Member in Org B
    set_auth_context(seeded_db, role="authenticated", user_id=USER_ADMIN_B)
    try:
        with seeded_db.cursor() as cur:
            cur.execute("SELECT id FROM public.organizations;")
            org_ids = [str(row[0]) for row in cur.fetchall()]
            assert org_ids == [ORG_B_ID]

            # Cannot see Org A's devices
            cur.execute("SELECT label FROM public.devices;")
            devices = [row[0] for row in cur.fetchall()]
            assert devices == []

            # Cannot see Org A's assessments
            cur.execute("SELECT event_id FROM public.assessment_events;")
            events = [row[0] for row in cur.fetchall()]
            assert events == []
    finally:
        reset_auth_context(seeded_db)


def test_reviewer_cannot_read_credential_hash(
    seeded_db: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Verifies reviewer cannot select credential_hash directly."""
    set_auth_context(seeded_db, role="authenticated", user_id=USER_REVIEWER_A)
    try:
        with seeded_db.cursor() as cur:
            # Querying credential_hash fails with permission denied
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute("SELECT credential_hash FROM public.devices;")
        seeded_db.rollback()

        with seeded_db.cursor() as cur:
            # But reviewer CAN query non-secret columns or devices_public view
            cur.execute("SELECT id, label, public_id FROM public.devices_public;")
            dev_rows = cur.fetchall()
            assert len(dev_rows) == 1
            assert dev_rows[0][1] == "Workstation A-1"
    finally:
        reset_auth_context(seeded_db)


def test_client_cannot_write_protected_tables(
    seeded_db: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Verifies authenticated client role cannot insert into protected tables."""
    set_auth_context(seeded_db, role="authenticated", user_id=USER_ADMIN_A)
    try:
        with seeded_db.cursor() as cur:
            # Inserting devices through client is blocked
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute(
                    """
                    INSERT INTO public.devices (organization_id, label, public_id, credential_hash)
                    VALUES (%s, 'Rogue Device', 'pub_rogue', 'hash');
                    """,
                    (ORG_A_ID,),
                )
    finally:
        reset_auth_context(seeded_db)


def test_client_cannot_escalate_role(seeded_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies reviewer cannot escalate themselves to admin in organization_members."""
    set_auth_context(seeded_db, role="authenticated", user_id=USER_REVIEWER_A)
    try:
        with seeded_db.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                cur.execute(
                    """
                    UPDATE public.organization_members
                    SET role = 'admin'
                    WHERE user_id = %s;
                    """,
                    (USER_REVIEWER_A,),
                )
    finally:
        reset_auth_context(seeded_db)


def test_idempotent_event_ingestion(seeded_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies that inserting the same (device_id, event_id) violates uniqueness constraint."""
    with seeded_db.cursor() as cur:
        with pytest.raises(errors.UniqueViolation):
            cur.execute(
                """
                INSERT INTO public.assessment_events (
                    event_id, device_id, organization_id, captured_at,
                    scoring_method, scoring_version, validity, score, software_version
                ) VALUES (
                    'e1111111-1111-1111-1111-111111111111', %s, %s, now(),
                    'rula_v1_screening', '1.0.0', 'valid', 4.0, '3.0.0'
                );
                """,
                (DEVICE_A_ID, ORG_A_ID),
            )
    seeded_db.rollback()


def test_check_constraints_reject_invalid_data(
    seeded_db: psycopg.Connection[tuple[object, ...]],
) -> None:
    """Verifies CHECK constraints reject out-of-range scores, enums, and secrets in audit."""
    with seeded_db.cursor() as cur:
        # Out-of-range score (> 7.0)
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO public.assessment_events (
                    event_id, device_id, organization_id, captured_at,
                    scoring_method, scoring_version, validity, score, software_version
                ) VALUES (
                    gen_random_uuid(), %s, %s, now(),
                    'rula_v1_screening', '1.0.0', 'valid', 8.5, '3.0.0'
                );
                """,
                (DEVICE_A_ID, ORG_A_ID),
            )
        seeded_db.rollback()

        # Unknown validity status
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO public.assessment_events (
                    event_id, device_id, organization_id, captured_at,
                    scoring_method, scoring_version, validity, score, software_version
                ) VALUES (
                    gen_random_uuid(), %s, %s, now(),
                    'rula_v1_screening', '1.0.0', 'unknown_status', 3.0, '3.0.0'
                );
                """,
                (DEVICE_A_ID, ORG_A_ID),
            )
        seeded_db.rollback()

        # Invalid validity vs score relationship (score without valid observation)
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO public.assessment_events (
                    event_id, device_id, organization_id, captured_at,
                    scoring_method, scoring_version, validity, score, software_version
                ) VALUES (
                    gen_random_uuid(), %s, %s, now(),
                    'rula_v1_screening', '1.0.0', 'insufficient', 4.0, '3.0.0'
                );
                """,
                (DEVICE_A_ID, ORG_A_ID),
            )
        seeded_db.rollback()

        # Secret key inside audit_events.metadata
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO public.audit_events (
                    organization_id, action, target_type, target_id, metadata
                ) VALUES (
                    %s, 'login', 'user', 'usr_1', '{"password": "leaked_secret"}'::jsonb
                );
                """,
                (ORG_A_ID,),
            )
        seeded_db.rollback()


def test_retention_purge_function(seeded_db: psycopg.Connection[tuple[object, ...]]) -> None:
    """Verifies purge_expired_records successfully purges records older than specified retention."""
    with seeded_db.cursor() as cur:
        # Insert old assessment event (captured 400 days ago)
        cur.execute(
            """
            INSERT INTO public.assessment_events (
                event_id, device_id, organization_id, captured_at,
                scoring_method, scoring_version, validity, score, software_version
            ) VALUES (
                gen_random_uuid(), %s, %s, now() - interval '400 days',
                'rula_v1_screening', '1.0.0', 'valid', 2.0, '3.0.0'
            );
            """,
            (DEVICE_A_ID, ORG_A_ID),
        )
        cur.execute("SELECT * FROM public.purge_expired_records(365, 30, 365);")
        row = cur.fetchone()
        assert row is not None
        # deleted_assessments should be at least 1
        deleted_count = int(str(row[0]))
        assert deleted_count >= 1
    seeded_db.commit()
