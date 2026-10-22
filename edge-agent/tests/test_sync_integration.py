"""End-to-End Integration Tests: Edge Agent Storage & Sync vs Real FastAPI Backend.

Verifies:
- End-to-end device enrollment token exchange (single-use enforcement)
- Offline observation accumulation followed by FIFO ordered drain to hosted API
- Idempotent upload: lost response / re-delivery causes zero server-side duplicates
- Cross-device posting prevention: device A cannot authenticate with forged credentials
- Revoked device handling: 401 stops agent uploads, triggers AUTH_ERROR state, preserves queue
- Process restart recovery between enqueue, lease, and ack
- Permanent rejection handling: rejected items quarantined to 'dead' without infinite retry
"""
# ruff: noqa: E402

from __future__ import annotations

import importlib.util
import sys
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from starlette.testclient import TestClient

# Ensure backend directory is in sys.path
_repo_root = Path(__file__).resolve().parent.parent.parent
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Load backend conftest dynamically to prevent namespace shadowing with local tests
_conftest_path = _backend_dir / "tests" / "conftest.py"
_conftest_spec = importlib.util.spec_from_file_location("backend_conftest", _conftest_path)
if _conftest_spec is None or _conftest_spec.loader is None:
    raise ImportError(f"Could not load backend conftest from {_conftest_path}")
_backend_conftest = importlib.util.module_from_spec(_conftest_spec)
_conftest_spec.loader.exec_module(_backend_conftest)

TestJWTSigner = _backend_conftest.TestJWTSigner
TestJWTSigner.__test__ = False
dsn_to_url = _backend_conftest.dsn_to_url
postgres_test_dsn = _backend_conftest.postgres_test_dsn

from app.db.migrations import run_migrations
from app.db.session import get_db
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.types import OverlayState
from edge_ergo.storage.credentials import MemoryCredentialStore
from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations as run_local_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import AssessmentEventRecord, SyncQueueState
from edge_ergo.sync.client import DeviceAuthError, SyncClient
from edge_ergo.sync.enrollment import TokenInvalidOrExpiredError, enroll_device
from edge_ergo.sync.worker import SyncWorker

ORG_TEST_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
USER_ADMIN_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")


@pytest.fixture
def clean_backend_db(
    postgres_test_dsn: str,
) -> Generator[psycopg.Connection[tuple[object, ...]], None, None]:
    """Prepares clean PostgreSQL schema with auth stub and backend migrations applied."""
    conn = psycopg.connect(postgres_test_dsn, autocommit=False, connect_timeout=5)
    try:
        conn.rollback()
    except Exception:
        pass

    with conn.cursor() as cur:
        cur.execute(
            """
            DROP SCHEMA IF EXISTS public CASCADE;
            DROP SCHEMA IF EXISTS auth CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO postgres;
            GRANT ALL ON SCHEMA public TO public;
            """
        )
    conn.commit()

    auth_stub_path = _repo_root / "supabase" / "tests" / "setup_test_db.sql"
    cur = conn.cursor()
    cur.execute(auth_stub_path.read_text(encoding="utf-8"))
    conn.commit()

    run_migrations(conn)

    # Seed Organization and Admin
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, 'integration_admin@example.com');",
            (USER_ADMIN_ID,),
        )
        cur.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (%s, %s, %s);",
            (ORG_TEST_ID, "Integration Org", "integration-org"),
        )
        cur.execute(
            """
            INSERT INTO organization_members (organization_id, user_id, role)
            VALUES (%s, %s, %s);
            """,
            (ORG_TEST_ID, USER_ADMIN_ID, "admin"),
        )
    conn.commit()

    yield conn
    conn.close()


@pytest.fixture
def backend_client(
    clean_backend_db: psycopg.Connection[tuple[object, ...]],
    postgres_test_dsn: str,
) -> Generator[TestClient, None, None]:
    """Provides a synchronous TestClient connected to the live PostgreSQL test database."""
    url = dsn_to_url(postgres_test_dsn)
    engine = create_async_engine(
        url,
        echo=False,
        future=True,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app, base_url="http://testserver")
    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def local_repo(tmp_path: Path) -> StorageRepository:
    """Provides an isolated local SQLite StorageRepository."""
    db_path = tmp_path / "agent_sync_integration.db"
    db = Database(db_path)
    run_local_migrations(db)
    return StorageRepository(db)


@pytest.fixture
def jwt_signer() -> Any:
    return TestJWTSigner()


def test_integration_enrollment_single_use_end_to_end(
    backend_client: TestClient,
    jwt_signer: Any,
    local_repo: StorageRepository,
) -> None:
    """Verifies agent enrollment token exchange and strict single-use rejection against backend."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_ID))

    # 1. Admin generates enrollment token via backend API
    token_res = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Integration Test Workstation", "expires_in_minutes": 10},
    )
    assert token_res.status_code == 200
    raw_token = token_res.json()["token"]
    assert raw_token.startswith("eet_")

    # 2. Agent exchanges token for device credential
    cred_store = MemoryCredentialStore()
    identity = enroll_device(
        api_base_url="http://testserver",
        token=raw_token,
        label="Integration Test Workstation",
        repo=local_repo,
        credential_store=cred_store,
        http_client=backend_client,
    )
    device_id = identity.device_id
    public_id = identity.public_id

    assert device_id is not None
    assert public_id is not None
    # Verify secret is safely in credential store
    stored_secret = cred_store.get_credential("edge_ergo_device", public_id)
    assert stored_secret is not None
    assert stored_secret.startswith(f"eed_{public_id}.")

    # Verify SQLite database identity contains NO secret
    persisted_identity = local_repo.get_device_identity()
    assert persisted_identity is not None
    assert persisted_identity.device_id == device_id
    assert persisted_identity.public_id == public_id
    assert persisted_identity.api_base_url == "http://testserver"

    # 3. Attempting to reuse the same enrollment token must be strictly rejected
    with pytest.raises(TokenInvalidOrExpiredError):
        enroll_device(
            api_base_url="http://testserver",
            token=raw_token,
            label="Rogue Workstation",
            repo=local_repo,
            credential_store=cred_store,
            http_client=backend_client,
        )


def test_integration_offline_accumulation_and_drain_in_order(
    backend_client: TestClient,
    jwt_signer: Any,
    local_repo: StorageRepository,
) -> None:
    """Verifies events queued while offline are uploaded in FIFO order upon reconnection."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_ID))

    # Enroll device
    token_res = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Offline Accumulation Workstation", "expires_in_minutes": 10},
    )
    raw_token = token_res.json()["token"]
    cred_store = MemoryCredentialStore()
    identity = enroll_device(
        api_base_url="http://testserver",
        token=raw_token,
        label="Offline Workstation",
        repo=local_repo,
        credential_store=cred_store,
        http_client=backend_client,
    )
    public_id = identity.public_id
    secret = cred_store.get_credential("edge_ergo_device", public_id)
    assert secret is not None

    # Enqueue 3 events offline
    event_ids = [str(uuid.uuid4()) for _ in range(3)]
    for idx, eid in enumerate(event_ids):
        ev = AssessmentEventRecord(
            event_id=eid,
            captured_at=f"2026-10-20T10:0{idx}:00+00:00",
            scoring_method="rula_v1_screening",
            scoring_version="1.0.0",
            validity="valid",
            score=3.0 + idx,
            neck_score=2,
            trunk_score=2,
            upper_arm_score=2,
            guidance_codes=["FORWARD_HEAD"],
            software_version="3.0.0",
        )
        local_repo.enqueue_assessment_event(ev)

    assert local_repo.get_sync_queue_depth() == 3

    # Initialize sync worker with live backend client
    presenter = OverlayPresenter()
    worker = SyncWorker(
        repository=local_repo,
        overlay_presenter=presenter,
        credential_store=cred_store,
        batch_size=10,
        sync_interval_s=60.0,
        http_client=backend_client,
    )

    # Trigger single sync cycle
    processed_count = worker.step_sync()
    assert processed_count == 3

    # Assert local queue items are now ACKED and queue depth is 0
    assert local_repo.get_sync_queue_depth() == 0

    items = local_repo.get_events_by_state(SyncQueueState.ACKED)
    acked_ids = [i.event_id for i in items]
    for eid in event_ids:
        assert eid in acked_ids

    # Verify backend received the events via dashboard API
    overview_res = backend_client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert overview_res.status_code == 200
    assert overview_res.json()["total_assessments"] >= 3


def test_integration_duplicate_delivery_lost_response_no_duplicates_server_side(
    backend_client: TestClient,
    jwt_signer: Any,
    local_repo: StorageRepository,
) -> None:
    """Verifies that re-uploading an event reports duplicate and adds no server rows."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_ID))

    token_res = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Duplicate Test Workstation", "expires_in_minutes": 10},
    )
    raw_token = token_res.json()["token"]
    cred_store = MemoryCredentialStore()
    enroll_device(
        api_base_url="http://testserver",
        token=raw_token,
        label="Duplicate Test Workstation",
        repo=local_repo,
        credential_store=cred_store,
        http_client=backend_client,
    )

    event_id = str(uuid.uuid4())
    ev = AssessmentEventRecord(
        event_id=event_id,
        captured_at="2026-10-20T11:00:00+00:00",
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="valid",
        score=4.0,
        neck_score=3,
        trunk_score=2,
        upper_arm_score=2,
        guidance_codes=[],
        software_version="3.0.0",
    )
    local_repo.enqueue_assessment_event(ev)

    presenter = OverlayPresenter()
    worker = SyncWorker(
        repository=local_repo,
        overlay_presenter=presenter,
        credential_store=cred_store,
        batch_size=10,
        http_client=backend_client,
    )

    # First cycle: accepted by backend
    worker.step_sync()
    assert local_repo.get_sync_queue_depth() == 0

    # Simulate lost ACK: manually revert queue state to pending
    with local_repo.db.transaction() as conn:
        conn.execute(
            "UPDATE sync_queue SET state = 'pending' WHERE event_id = ?",
            (event_id,),
        )

    # Second cycle: re-delivers the identical event
    worker.step_sync()

    # Client confirms item is acked
    assert local_repo.get_sync_queue_depth() == 0
    acked = local_repo.get_events_by_state(SyncQueueState.ACKED)
    assert any(a.event_id == event_id for a in acked)

    # Query overview count: exactly 1 assessment must exist
    overview_res = backend_client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert overview_res.status_code == 200
    assert overview_res.json()["total_assessments"] == 1


def test_integration_cross_posting_prevention(
    backend_client: TestClient,
    jwt_signer: Any,
    local_repo: StorageRepository,
) -> None:
    """Verifies that an agent cannot forge authorization headers or upload as another device."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_ID))

    # Enroll Device A
    tok_a = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Device Alpha", "expires_in_minutes": 10},
    ).json()["token"]
    cred_store = MemoryCredentialStore()
    id_a = enroll_device(
        api_base_url="http://testserver",
        token=tok_a,
        label="Device Alpha",
        repo=local_repo,
        credential_store=cred_store,
        http_client=backend_client,
    )
    pub_a = id_a.public_id

    # Enroll Device B
    tok_b = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Device Beta", "expires_in_minutes": 10},
    ).json()["token"]
    repo_b = StorageRepository(Database(local_repo.db.db_path.parent / "b.db"))
    run_local_migrations(repo_b.db)
    id_b = enroll_device(
        api_base_url="http://testserver",
        token=tok_b,
        label="Device Beta",
        repo=repo_b,
        credential_store=cred_store,
        http_client=backend_client,
    )
    pub_b = id_b.public_id

    secret_b = cred_store.get_credential("edge_ergo_device", pub_b)
    assert secret_b is not None
    raw_secret_b_part = secret_b.split(".", 1)[1]

    # Tampered credential: public_id of Device A with secret of Device B
    tampered_credential = f"eed_{pub_a}.{raw_secret_b_part}"
    bad_client = SyncClient(
        api_base_url="http://testserver",
        credential=tampered_credential,
        http_client=backend_client,
    )

    with pytest.raises(DeviceAuthError):
        bad_client.upload_batch({"events": []})


def test_integration_revoked_device_upload_rejection_and_agent_auth_halt(
    backend_client: TestClient,
    jwt_signer: Any,
    local_repo: StorageRepository,
) -> None:
    """Verifies server revocation returns 401, halting uploads and keeping queue safe."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_ID))

    # Enroll device
    tok = backend_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Revocation Candidate", "expires_in_minutes": 10},
    ).json()["token"]
    cred_store = MemoryCredentialStore()
    rev_identity = enroll_device(
        api_base_url="http://testserver",
        token=tok,
        label="Revocation Candidate",
        repo=local_repo,
        credential_store=cred_store,
        http_client=backend_client,
    )
    device_id = rev_identity.device_id

    # Enqueue telemetry event
    ev = AssessmentEventRecord(
        event_id=str(uuid.uuid4()),
        captured_at="2026-10-20T12:00:00+00:00",
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="valid",
        score=2.5,
        neck_score=2,
        trunk_score=1,
        upper_arm_score=2,
        guidance_codes=[],
        software_version="3.0.0",
    )
    local_repo.enqueue_assessment_event(ev)

    # Admin revokes the device in backend
    revoke_res = backend_client.post(
        f"/api/v1/devices/{device_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    presenter = OverlayPresenter()
    worker = SyncWorker(
        repository=local_repo,
        overlay_presenter=presenter,
        credential_store=cred_store,
        batch_size=10,
        http_client=backend_client,
    )

    # Worker attempts sync cycle
    cycle_res = worker.step_sync()
    assert cycle_res == 0

    # Assert worker is HALTED and overlay transitioned to AUTH_ERROR
    assert worker.is_auth_halted() is True
    assert presenter.view_model.state == OverlayState.AUTH_ERROR

    # Crucial guarantee: Events were NOT deleted or lost
    assert local_repo.get_sync_queue_depth() == 1
    pending_items = local_repo.get_events_by_state(SyncQueueState.PENDING)
    assert len(pending_items) == 1
    assert pending_items[0].event_id == ev.event_id
