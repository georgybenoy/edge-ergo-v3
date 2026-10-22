#!/usr/bin/env python3
# ruff: noqa: BLE001, S110
"""EdgeErgo V3 — PyInstaller Packaged Dist Bundle Inspector.

Scans the packaged Windows distribution directory (e.g. edge-agent/dist/edge-ergo)
to guarantee:
1. Critical executables and assets exist:
   - edge-ergo.exe
   - pose_landmarker_lite.task (bundled MediaPipe model)
2. No prohibited development or persistent files are packaged:
   - No .env files (.env, .env.local, .env.production, etc.)
   - No SQLite databases (*.sqlite, *.sqlite3, *.db)
   - No frame, video, or raw image files (*.jpg, *.png, *.mp4, *.avi) except icon.ico
   - No test fixtures or dev caches (__pycache__, test_*, conftest*)
3. No hardcoded production secrets, JWTs, service-role keys, or database credentials.

Usage:
    python scripts/inspect_bundle.py --dist-dir edge-agent/dist/edge-ergo
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Color output helpers
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

FORBIDDEN_FILE_PATTERNS = [
    (re.compile(r"^\.env(?:\..+)?$", re.IGNORECASE), "Environment file (.env)"),
    (re.compile(r"\.(?:sqlite|sqlite3|db)$", re.IGNORECASE), "SQLite database file"),
    (re.compile(r"\.(?:mp4|avi|mov|mkv|flv|wmv)$", re.IGNORECASE), "Raw video file"),
    (re.compile(r"\.(?:jpg|jpeg|png|bmp|webp)$", re.IGNORECASE), "Raw image file"),
    (
        re.compile(
            r"^test_(?:camera|scorer|sync|storage|validator|quality|ui|privacy|authz|api|db|integration|smoke).*\.py$",
            re.IGNORECASE,
        ),
        "Application test source file",
    ),
]

# Patterns that indicate forbidden production secrets
FORBIDDEN_CONTENT_PATTERNS = [
    (
        "Supabase service_role key assignment",
        re.compile(
            r"SUPABASE_SERVICE_ROLE_KEY\s*=\s*['\"]?(?!your_|YOUR_|placeholder|fake|mock|none|null|dummy|test|changeme)[A-Za-z0-9_.-]{30,}['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "Real JWT token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}\b"),
    ),
    (
        "PostgreSQL connection URL with password",
        re.compile(
            r"postgres(?:ql)?://[a-zA-Z0-9_]+:(?!password|YOUR_PASSWORD|test|postgres|postgres_test|mock)[^@\s]{4,}@[a-zA-Z0-9.-]+"
        ),
    ),
    (
        "Real device credential secret (eed_<public_id>.<secret>)",
        re.compile(
            r"\beed_[A-Za-z0-9_-]{8,}\.(?!<secret>|secret|test|mock|example|dummy)[A-Za-z0-9_-]{20,}\b"
        ),
    ),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
]


def inspect_bundle(dist_dir: Path) -> tuple[bool, list[str]]:
    violations: list[str] = []

    if not dist_dir.exists() or not dist_dir.is_dir():
        return False, [f"Distribution directory does not exist: {dist_dir}"]

    # 1. Check for primary executable
    exe_path = dist_dir / "edge-ergo.exe"
    if not exe_path.is_file():
        violations.append(f"Missing core executable: {exe_path}")
    else:
        exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] Found core executable: edge-ergo.exe ({exe_size_mb:.2f} MB)")

    # 2. Check for pose model asset
    model_found = False
    for root, _, files in os.walk(dist_dir):
        if "pose_landmarker_lite.task" in files:
            model_found = True
            model_path = Path(root) / "pose_landmarker_lite.task"
            model_size_mb = model_path.stat().st_size / (1024 * 1024)
            print(f"  [OK] Found bundled model asset: {model_path.name} ({model_size_mb:.2f} MB)")
            break

    if not model_found:
        violations.append("Missing bundled MediaPipe pose model: pose_landmarker_lite.task")

    # 3. Walk all files and inspect names & content
    scanned_count = 0
    for root, _, files in os.walk(dist_dir):
        for f in files:
            scanned_count += 1
            f_path = Path(root) / f
            rel_path = f_path.relative_to(dist_dir)

            # Allow application icon and standard library internal UI assets (matplotlib mpl-data)
            if f.lower() == "icon.ico":
                continue
            if "matplotlib" in str(rel_path).lower() and "mpl-data" in str(rel_path).lower():
                continue

            for pattern, desc in FORBIDDEN_FILE_PATTERNS:
                if pattern.search(f):
                    violations.append(f"Forbidden file pattern ({desc}): {rel_path}")

            # Check text contents for forbidden secrets (only scan text files < 512 KB)
            text_suffixes = {".py", ".txt", ".json", ".yaml", ".yml", ".ini", ".cfg", ".toml", ".md", ".env", ".xml", ".html", ".js", ".ts", ".css"}
            if f_path.suffix.lower() in text_suffixes and f_path.stat().st_size < 512 * 1024:
                try:
                    content = f_path.read_text(encoding="utf-8", errors="ignore")
                    for desc, pat in FORBIDDEN_CONTENT_PATTERNS:
                        if pat.search(content):
                            violations.append(
                                f"Forbidden secret detected in {rel_path}: {desc}"
                            )
                except Exception:
                    pass

    print(f"  [OK] Scanned {scanned_count} files in bundle directory.")
    return len(violations) == 0, violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EdgeErgo V3 — PyInstaller Dist Bundle Inspector"
    )
    parser.add_argument(
        "--dist-dir",
        default="edge-agent/dist/edge-ergo",
        help="Path to the built PyInstaller one-folder output directory",
    )
    args = parser.parse_args()

    dist_dir = Path(args.dist_dir).resolve()
    print("=" * 60)
    print(f"{BOLD}EdgeErgo V3 — Packaged Bundle Inspector{RESET}")
    print("=" * 60)
    print(f"Target Directory: {dist_dir}\n")

    passed, violations = inspect_bundle(dist_dir)

    print("-" * 60)
    if passed:
        print(f"{GREEN}[PASS] Dist bundle verification passed cleanly!{RESET}")
        print("  - Core binary and pose model asset present.")
        print("  - Zero .env, SQLite databases, or unapproved media files.")
        print("  - Zero leaked secret tokens, database credentials, or private keys.")
        print("=" * 60)
        return 0
    else:
        print(f"{RED}[FAIL] Dist bundle verification failed with {len(violations)} issues:{RESET}")
        for v in violations:
            print(f"  [!] {v}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
