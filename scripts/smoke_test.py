#!/usr/bin/env python3
"""EdgeErgo V3 — Production Deployment Smoke Test Suite.

Executes black-box acceptance tests against deployed (or locally simulated)
Hosted API and Web Dashboard endpoints.

Verifies:
1. /health/live returns 200 OK
2. /health/ready returns 200 OK with database connection verified
3. Strict API security headers (nosniff, DENY, etc.)
4. Production CORS preflight enforcement (whitelisted origin accepted, unknown origin rejected)
5. Unauthenticated protected routes return HTTP 401
6. Invalid device credential returns HTTP 401
7. API documentation endpoints (/docs, /redoc, /openapi.json) are disabled (404)
8. Frontend index route returns 200
9. Frontend SPA nested route returns 200 (SPA rewrite rule verification)
10. Frontend static assets contain zero embedded secrets, database strings, or service keys
11. (Optional) Authenticated user endpoints (/auth/me, /dashboard/overview, /reports/export)
12. (Optional) Controlled device telemetry upload using provisioned credentials

Usage:
  python scripts/smoke_test.py --api-url https://api.edgeergo.com --frontend-url https://dashboard.edgeergo.com
  API_URL=http://localhost:8000 FRONTEND_URL=http://localhost:5173 python scripts/smoke_test.py
"""

# ruff: noqa: BLE001
from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import urljoin

import httpx

# Color output helpers for terminal reporting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class SmokeTestRunner:
    def __init__(
        self,
        api_url: str,
        frontend_url: str,
        bearer_token: str | None = None,
        device_credential: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/")
        self.bearer_token = bearer_token
        self.device_credential = device_credential
        self.timeout = timeout
        self.results: list[tuple[str, bool, str]] = []

    def record(self, test_name: str, passed: bool, detail: str) -> None:
        self.results.append((test_name, passed, detail))
        status_tag = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  {status_tag} {test_name:<45} {detail}")

    def run_all(self) -> bool:
        print(
            f"\n{BOLD}============================================================{RESET}"
        )
        print(f"{BOLD}EdgeErgo V3 — Deployment Smoke Test Suite{RESET}")
        print(
            f"{BOLD}============================================================{RESET}"
        )
        print(f"  API URL:          {self.api_url}")
        print(f"  Frontend URL:     {self.frontend_url}")
        print(
            f"  User Auth Token:  {'Provided' if self.bearer_token else 'Not provided (skipping auth tests)'}"
        )
        print(
            f"  Device Credential:{'Provided' if self.device_credential else 'Not provided (skipping device upload)'}"
        )
        print(
            f"{BOLD}------------------------------------------------------------{RESET}\n"
        )

        with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
            self._test_health_live(client)
            self._test_health_ready(client)
            self._test_security_headers(client)
            self._test_cors_preflight(client)
            self._test_unauthenticated_protected_route(client)
            self._test_invalid_device_credential(client)
            self._test_docs_disabled(client)
            self._test_frontend_index(client)
            self._test_frontend_nested_route(client)
            self._test_frontend_bundle_secrets(client)

            if self.bearer_token:
                self._test_authenticated_endpoints(client)

            if self.device_credential:
                self._test_device_telemetry_upload(client)

        print(
            f"\n{BOLD}============================================================{RESET}"
        )
        total = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = total - passed

        if failed == 0:
            print(f"{GREEN}{BOLD}ALL {total} SMOKE TESTS PASSED!{RESET}")
            return True
        else:
            print(f"{RED}{BOLD}{failed} OF {total} SMOKE TESTS FAILED!{RESET}")
            return False

    def _test_health_live(self, client: httpx.Client) -> None:
        try:
            res = client.get(f"{self.api_url}/health/live")
            passed = res.status_code == 200 and res.json().get("status") == "ok"
            self.record(
                "API Liveness Probe (/health/live)", passed, f"HTTP {res.status_code}"
            )
        except Exception as exc:
            self.record(
                "API Liveness Probe (/health/live)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_health_ready(self, client: httpx.Client) -> None:
        try:
            res = client.get(f"{self.api_url}/health/ready")
            passed = res.status_code == 200 and res.json().get("status") == "ready"
            self.record(
                "API Readiness Probe (/health/ready)", passed, f"HTTP {res.status_code}"
            )
        except Exception as exc:
            self.record(
                "API Readiness Probe (/health/ready)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_security_headers(self, client: httpx.Client) -> None:
        try:
            res = client.get(f"{self.api_url}/health/live")
            headers = {k.lower(): v for k, v in res.headers.items()}
            has_nosniff = headers.get("x-content-type-options") == "nosniff"
            has_xframe = headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")
            passed = has_nosniff and has_xframe
            detail = f"nosniff={has_nosniff}, x-frame={has_xframe}"
            self.record("API Security Headers Enforcement", passed, detail)
        except Exception as exc:
            self.record(
                "API Security Headers Enforcement",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_cors_preflight(self, client: httpx.Client) -> None:
        try:
            # 1. Allowed origin preflight
            res_allowed = client.options(
                f"{self.api_url}/api/v1/me",
                headers={
                    "Origin": self.frontend_url,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            allow_origin_hdr = res_allowed.headers.get("access-control-allow-origin")
            allowed_origin_ok = (
                res_allowed.status_code == 200 and allow_origin_hdr == self.frontend_url
            )

            # 2. Rogue origin preflight (must not be allowed)
            res_rogue = client.options(
                f"{self.api_url}/api/v1/me",
                headers={
                    "Origin": "https://malicious-attacker-domain.com",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
            rogue_origin_hdr = res_rogue.headers.get("access-control-allow-origin")
            rogue_rejected = rogue_origin_hdr != "https://malicious-attacker-domain.com"

            passed = allowed_origin_ok and rogue_rejected
            detail = (
                f"allowed_origin={allow_origin_hdr}, "
                f"rogue_blocked={'yes' if rogue_rejected else 'no'}"
            )
            self.record("CORS Origin Whitelisting", passed, detail)
        except Exception as exc:
            self.record(
                "CORS Origin Whitelisting", False, f"Exception: {type(exc).__name__}"
            )

    def _test_unauthenticated_protected_route(self, client: httpx.Client) -> None:
        try:
            res = client.get(f"{self.api_url}/api/v1/me")
            body = (
                res.json()
                if res.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            has_error_code = "error" in body and body["error"].get("code") in (
                "UNAUTHORIZED",
                "MISSING_AUTHORIZATION",
            )
            passed = res.status_code == 401 and has_error_code
            self.record(
                "Unauthenticated Route Rejection (/me)",
                passed,
                f"HTTP {res.status_code}",
            )
        except Exception as exc:
            self.record(
                "Unauthenticated Route Rejection (/me)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_invalid_device_credential(self, client: httpx.Client) -> None:
        try:
            res = client.post(
                f"{self.api_url}/api/v1/assessments/batch",
                headers={
                    "Authorization": "Bearer eed_test_device_id.dummy_secret_token"
                },
                json={"events": []},
            )
            passed = res.status_code == 401
            self.record(
                "Invalid Device Credential Rejection", passed, f"HTTP {res.status_code}"
            )
        except Exception as exc:
            self.record(
                "Invalid Device Credential Rejection",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_docs_disabled(self, client: httpx.Client) -> None:
        try:
            res_docs = client.get(f"{self.api_url}/docs")
            res_redoc = client.get(f"{self.api_url}/redoc")
            res_openapi = client.get(f"{self.api_url}/openapi.json")

            passed = (
                res_docs.status_code == 404
                and res_redoc.status_code == 404
                and res_openapi.status_code == 404
            )
            detail = f"/docs={res_docs.status_code}, /redoc={res_redoc.status_code}, /openapi={res_openapi.status_code}"
            self.record("API Docs Disabled in Production (/docs)", passed, detail)
        except Exception as exc:
            self.record(
                "API Docs Disabled in Production (/docs)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_frontend_index(self, client: httpx.Client) -> None:
        try:
            res = client.get(f"{self.frontend_url}/")
            has_html = (
                "<!doctype html>" in res.text.lower() or "<html" in res.text.lower()
            )
            passed = res.status_code == 200 and has_html
            self.record(
                "Frontend Index Page Serving (/)", passed, f"HTTP {res.status_code}"
            )
        except Exception as exc:
            self.record(
                "Frontend Index Page Serving (/)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_frontend_nested_route(self, client: httpx.Client) -> None:
        try:
            # Requests deep route to verify SPA fallback rewrite (/* -> /index.html)
            res = client.get(f"{self.frontend_url}/assessments")
            has_html = (
                "<!doctype html>" in res.text.lower() or "<html" in res.text.lower()
            )
            passed = res.status_code == 200 and has_html
            self.record(
                "Frontend SPA Rewrite Routing (/assessments)",
                passed,
                f"HTTP {res.status_code}",
            )
        except Exception as exc:
            self.record(
                "Frontend SPA Rewrite Routing (/assessments)",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_frontend_bundle_secrets(self, client: httpx.Client) -> None:
        try:
            index_res = client.get(f"{self.frontend_url}/")
            if index_res.status_code != 200:
                self.record(
                    "Frontend Bundle Secret Scan", False, "Could not fetch index.html"
                )
                return

            # Extract script URLs
            script_srcs = re.findall(
                r'<script[^>]+src=["\']([^"\']+)["\']', index_res.text
            )
            if not script_srcs:
                self.record(
                    "Frontend Bundle Secret Scan",
                    False,
                    "No script bundles found in HTML",
                )
                return

            forbidden_patterns = [
                (re.compile(r"postgresql://[^'\"\s]{8,}"), "Postgres URI"),
                (
                    re.compile(r"eyJ[a-zA-Z0-9_-]{25,}\.eyJ[a-zA-Z0-9_-]{25,}"),
                    "JWT token",
                ),
                (
                    re.compile(r"eed_[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{20,}"),
                    "Device secret",
                ),
                (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "Private key"),
            ]

            scanned_files = 0
            violations: list[str] = []

            for src in script_srcs:
                bundle_url = urljoin(f"{self.frontend_url}/", src)
                bundle_res = client.get(bundle_url)
                if bundle_res.status_code != 200:
                    continue
                scanned_files += 1
                content = bundle_res.text

                for pattern, desc in forbidden_patterns:
                    if pattern.search(content):
                        violations.append(f"{desc} in {src}")

            passed = (scanned_files > 0) and len(violations) == 0
            detail = f"Scanned {scanned_files} JS bundles, violations={len(violations)}"
            self.record("Frontend Bundle Secret Scan", passed, detail)
        except Exception as exc:
            self.record(
                "Frontend Bundle Secret Scan", False, f"Exception: {type(exc).__name__}"
            )

    def _test_authenticated_endpoints(self, client: httpx.Client) -> None:
        try:
            auth_header = {"Authorization": f"Bearer {self.bearer_token}"}
            me_res = client.get(f"{self.api_url}/api/v1/me", headers=auth_header)
            summary_res = client.get(
                f"{self.api_url}/api/v1/dashboard/summary", headers=auth_header
            )
            exp_res = client.get(
                f"{self.api_url}/api/v1/reports/assessments.csv", headers=auth_header
            )

            passed = (
                me_res.status_code == 200
                and summary_res.status_code == 200
                and exp_res.status_code in (200, 204)
            )
            detail = f"/me={me_res.status_code}, /summary={summary_res.status_code}, /export={exp_res.status_code}"
            self.record("Authenticated Dashboard Queries", passed, detail)
        except Exception as exc:
            self.record(
                "Authenticated Dashboard Queries",
                False,
                f"Exception: {type(exc).__name__}",
            )

    def _test_device_telemetry_upload(self, client: httpx.Client) -> None:
        try:
            device_header = {"Authorization": f"Bearer {self.device_credential}"}
            upload_res = client.post(
                f"{self.api_url}/api/v1/assessments/batch",
                headers=device_header,
                json={"events": []},
            )
            passed = upload_res.status_code == 200
            self.record(
                "Controlled Device Upload Verification",
                passed,
                f"HTTP {upload_res.status_code}",
            )
        except Exception as exc:
            self.record(
                "Controlled Device Upload Verification",
                False,
                f"Exception: {type(exc).__name__}",
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EdgeErgo V3 Production Deployment Smoke Tests"
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://127.0.0.1:8000"),
        help="Hosted API Base URL (e.g. https://api.edgeergo.com)",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173"),
        help="Web Dashboard Base URL (e.g. https://dashboard.edgeergo.com)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("BEARER_TOKEN"),
        help="Optional Supabase user JWT bearer token for testing authenticated routes",
    )
    parser.add_argument(
        "--device-cred",
        default=os.environ.get("DEVICE_CREDENTIAL"),
        help="Optional device credential (eed_<public_id>.<secret>) for testing device upload",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP request timeout in seconds",
    )
    args = parser.parse_args()

    runner = SmokeTestRunner(
        api_url=args.api_url,
        frontend_url=args.frontend_url,
        bearer_token=args.token,
        device_credential=args.device_cred,
        timeout=args.timeout,
    )

    success = runner.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
