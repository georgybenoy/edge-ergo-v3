#!/usr/bin/env python3
# ruff: noqa: BLE001
"""EdgeErgo V3 — Secret Pattern Scanner.

Scans the repository to ensure no production secrets, JWTs, service-role keys,
passwords in connection URIs, or device secrets are committed.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    ".idea",
    ".vscode",
    "data_prod_test",
    "data_test",
    "data",
    ".coverage",
}

# Files to ignore (e.g., example files, this checker script itself)
IGNORE_FILE_PATTERNS = [
    r"\.env\.example$",
    r"\.example$",
    r"check_secrets\.py$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.sqlite$",
    r"\.db$",
]

# Patterns that indicate forbidden secrets
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "Supabase service_role key assignment",
        re.compile(r"SUPABASE_SERVICE_ROLE_KEY\s*=\s*['\"]?(?!your_|YOUR_|placeholder|fake|mock|none|null|dummy|test|changeme)[A-Za-z0-9_.-]{30,}['\"]?", re.IGNORECASE),
    ),
    (
        "Real JWT token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]{25,}\b"),
    ),
    (
        "PostgreSQL URI with hardcoded non-placeholder password",
        re.compile(r"postgres(?:ql)?://[a-zA-Z0-9_]+:(?!password|YOUR_PASSWORD|test|postgres|postgres_test|mock)[^@\s]{4,}@[a-zA-Z0-9.-]+"),
    ),
    (
        "Real device credential secret (eed_<public_id>.<secret>)",
        re.compile(r"\beed_[A-Za-z0-9_-]{8,}\.(?!<secret>|secret|test|mock|example|dummy)[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "Private Key Header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
]


def is_ignored(file_path: Path) -> bool:
    for part in file_path.parts:
        if part in IGNORE_DIRS:
            return True
    filename = file_path.name
    for pattern in IGNORE_FILE_PATTERNS:
        if re.search(pattern, filename):
            return True
    return False


def scan_file(file_path: Path) -> list[str]:
    violations: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return [f"Could not read {file_path}: {exc}"]

    for line_idx, line in enumerate(content.splitlines(), start=1):
        # Ignore comments in markdown referencing example schemas
        if "eed_<public_id>.<secret>" in line:
            continue
        for name, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                # Redact matched text for safe reporting
                violations.append(
                    f"{file_path}:{line_idx} — Found prohibited pattern: {name}"
                )
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    all_violations: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            file_path = Path(dirpath) / filename
            if is_ignored(file_path):
                continue
            violations = scan_file(file_path)
            all_violations.extend(violations)

    if all_violations:
        print("=" * 60)
        print("SECRET CHECK FAILED — Prohibited secret patterns found:")
        print("=" * 60)
        for v in all_violations:
            print(f"  [!] {v}")
        print("\nEnsure all secrets use placeholders or environment variables.")
        return 1

    print("Secret check passed: No prohibited secret patterns found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
