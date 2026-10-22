#!/usr/bin/env python3
"""Local Production-Mode Stack Verification Script.

Spins up:
1. Static SPA HTTP server serving frontend/dist with SPA fallback rewrite (/* -> /index.html)
2. FastAPI backend in strict production mode (APP_ENV=production, ENABLE_API_DOCS=false)
   connected to the local PostgreSQL test database
3. Executes scripts/smoke_test.py against the local production-mode stack
   with authenticated user token and enrolled device credential

Exits with 0 on PASS, 1 on FAIL.
"""

# ruff: noqa: BLE001, S110, S112, I001
from __future__ import annotations

import http.server
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any
import uuid

import httpx
import psycopg
from sqlalchemy.ext.asyncio import create_async_engine
import uvicorn

# Ensure repository paths in sys.path
_repo_root = Path(__file__).resolve().parent.parent
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.smoke_test import SmokeTestRunner

# Dynamically load backend conftest for test fixtures and JWT minting
_conftest_path = _backend_dir / "tests" / "conftest.py"
_conftest_spec = importlib.util.spec_from_file_location(
    "backend_conftest", _conftest_path
)
if _conftest_spec is None or _conftest_spec.loader is None:
    raise ImportError(f"Could not load backend conftest from {_conftest_path}")
_backend_conftest = importlib.util.module_from_spec(_conftest_spec)
_conftest_spec.loader.exec_module(_backend_conftest)

TestJWTSigner = _backend_conftest.TestJWTSigner
TestJWTSigner.__test__ = False
from app.db.migrations import run_migrations


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def ensure_postgres_running() -> tuple[str, str]:
    port = 54329
    dsn = f"host=127.0.0.1 port={port} user=postgres dbname=edgeergo_test connect_timeout=1"
    url = f"postgresql+asyncpg://postgres@127.0.0.1:{port}/edgeergo_test"

    try:
        conn = psycopg.connect(dsn)
        conn.close()
        return dsn, url
    except Exception:
        pass

    pg_bin_dir = Path("C:/Program Files/PostgreSQL/18/bin")
    pg_ctl = pg_bin_dir / "pg_ctl.exe"
    cluster_dir = _repo_root / "scratch" / "test_cluster"
    data_dir = cluster_dir / "data"
    log_file = cluster_dir / "pg.log"

    subprocess.run(
        [
            str(pg_ctl),
            "-D",
            str(data_dir),
            "-l",
            str(log_file),
            "-o",
            f"-p {port}",
            "start",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(25):
        time.sleep(0.5)
        try:
            conn = psycopg.connect(dsn)
            conn.close()
            return dsn, url
        except Exception:
            continue

    raise RuntimeError(
        "Failed to verify or start local PostgreSQL test database on port 54329"
    )


class SpaStaticServer(http.server.SimpleHTTPRequestHandler):
    """Static file server with SPA rewrite fallback to index.html for unknown routes."""

    dist_dir: Path

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(self.dist_dir), **kwargs)

    def do_GET(self) -> None:
        req_path = self.path.split("?")[0].lstrip("/")
        target_file = self.dist_dir / req_path
        if not target_file.exists() or target_file.is_dir():
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def start_spa_server(port: int, dist_dir: Path) -> http.server.HTTPServer:
    SpaStaticServer.dist_dir = dist_dir
    server = http.server.HTTPServer(("127.0.0.1", port), SpaStaticServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def main() -> int:
    dist_dir = _repo_root / "frontend" / "dist"
    if not (dist_dir / "index.html").exists():
        print(
            f"[ERROR] Frontend production build not found at {dist_dir}. Run 'npm run build' first."
        )
        return 1

    spa_port = find_free_port()
    api_port = find_free_port()

    frontend_url = f"http://127.0.0.1:{spa_port}"
    api_url = f"http://127.0.0.1:{api_port}"

    print(f"Starting SPA Static Server at {frontend_url}...")
    spa_server = start_spa_server(spa_port, dist_dir)

    # Ensure PostgreSQL is ready
    print("Connecting to local PostgreSQL instance...")
    postgres_dsn, db_url = ensure_postgres_running()

    # Schema setup & migrations
    conn = psycopg.connect(postgres_dsn, autocommit=True)
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS auth.users (
                id UUID PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    run_migrations(conn)
    conn.close()

    # Seed Admin User and Organization
    user_admin_id = uuid.uuid4()
    org_id = uuid.uuid4()
    unique_suffix = uuid.uuid4().hex[:8]
    org_slug = f"smoke-test-org-{unique_suffix}"
    admin_email = f"smoke_admin_{unique_suffix}@edgeergo.com"

    conn = psycopg.connect(postgres_dsn, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO auth.users (id, email) VALUES (%s, %s);",
            (user_admin_id, admin_email),
        )
        cur.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (%s, %s, %s);",
            (org_id, "Smoke Test Org", org_slug),
        )
        cur.execute(
            "INSERT INTO organization_members (organization_id, user_id, role) VALUES (%s, %s, 'admin');",
            (org_id, user_admin_id),
        )
    conn.close()

    # Configure Environment for Local Production Verification
    os.environ["APP_ENV"] = "production"
    os.environ["ALLOW_LOCAL_PROD_TEST"] = "true"
    os.environ["ENABLE_API_DOCS"] = "false"
    os.environ["FRONTEND_ORIGIN"] = frontend_url
    os.environ["LOG_LEVEL"] = "WARNING"
    os.environ["DATABASE_URL"] = db_url

    # Initialize Backend App with overrides
    from app.core.config import settings

    object.__setattr__(settings, "APP_ENV", "production")
    object.__setattr__(settings, "ALLOW_LOCAL_PROD_TEST", True)
    object.__setattr__(settings, "ENABLE_API_DOCS", False)
    object.__setattr__(settings, "FRONTEND_ORIGIN", frontend_url)
    object.__setattr__(settings, "DATABASE_URL", db_url)

    import app.db.session

    app.db.session.engine = create_async_engine(db_url, echo=False)
    from sqlalchemy.ext.asyncio import async_sessionmaker

    app.db.session.AsyncSessionLocal = async_sessionmaker(
        bind=app.db.session.engine,
        expire_on_commit=False,
    )

    from app.main import create_app

    api_app = create_app()

    config = uvicorn.Config(
        app=api_app,
        host="127.0.0.1",
        port=api_port,
        log_level="warning",
    )
    api_server = uvicorn.Server(config)

    api_thread = threading.Thread(target=api_server.run, daemon=True)
    api_thread.start()

    print(f"Starting FastAPI Production Server at {api_url}...")
    time.sleep(2.0)  # Wait for socket bind

    try:
        # Mint test JWT token for authenticated dashboard checks
        jwt_signer = TestJWTSigner()
        admin_token = jwt_signer.mint_token(user_id=str(user_admin_id))

        # Enroll a test device to verify controlled device upload
        with httpx.Client(timeout=10.0) as client:
            token_res = client.post(
                f"{api_url}/api/v1/devices/enrollment-tokens",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"label": "Smoke Test Workstation", "expires_in_minutes": 15},
            )
            raw_token = token_res.json()["token"]

            enroll_res = client.post(
                f"{api_url}/api/v1/devices/enroll",
                json={
                    "token": raw_token,
                    "label": "Smoke Test Workstation",
                    "agent_version": "3.0.0",
                },
            )
            device_cred = enroll_res.json()["credential"]

        runner = SmokeTestRunner(
            api_url=api_url,
            frontend_url=frontend_url,
            bearer_token=admin_token,
            device_credential=device_cred,
            timeout=10.0,
        )
        passed = runner.run_all()
        return 0 if passed else 1
    finally:
        api_server.should_exit = True
        spa_server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
