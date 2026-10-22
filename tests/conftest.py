"""Root conftest ensuring backend and edge-agent packages are importable."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
_backend_dir = _repo_root / "backend"
_backend_tests = _backend_dir / "tests"
_edge_agent_dir = _repo_root / "edge-agent"

if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

if str(_backend_tests) not in sys.path:
    sys.path.insert(0, str(_backend_tests))

if str(_edge_agent_dir) not in sys.path:
    sys.path.insert(0, str(_edge_agent_dir))

import importlib.util

_conftest_path = _backend_tests / "conftest.py"
_spec = importlib.util.spec_from_file_location("backend_conftest", _conftest_path)
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    TestJWTSigner = _mod.TestJWTSigner
    TestJWTSigner.__test__ = False
    clean_db = _mod.clean_db
    postgres_test_dsn = _mod.postgres_test_dsn
    async_test_session = _mod.async_test_session
    async_client = _mod.async_client
    jwt_signer = _mod.jwt_signer
    dsn_to_url = _mod.dsn_to_url
