#!/usr/bin/env bash
# EdgeErgo V3 — Developer Script for Linux/macOS/Git Bash
set -euo pipefail

TARGET="${1:-all}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">>> Running EdgeErgo V3 target: ${TARGET}"

run_check_secrets() {
  echo "--- Scanning for secrets ---"
  python "${ROOT_DIR}/scripts/check_secrets.py"
}

run_setup() {
  echo "--- Setting up Backend ---"
  python -m pip install -e "${ROOT_DIR}/backend"
  echo "--- Setting up Edge Agent ---"
  python -m pip install -e "${ROOT_DIR}/edge-agent"
  echo "--- Setting up Frontend ---"
  (cd "${ROOT_DIR}/frontend" && npm install)
}

run_lint() {
  echo "--- Linting Backend ---"
  python -m ruff check "${ROOT_DIR}/backend/app" "${ROOT_DIR}/backend/tests"
  echo "--- Linting Edge Agent ---"
  python -m ruff check "${ROOT_DIR}/edge-agent/edge_ergo" "${ROOT_DIR}/edge-agent/tests"
  echo "--- Linting Frontend ---"
  (cd "${ROOT_DIR}/frontend" && npm run lint)
}

run_typecheck() {
  echo "--- Type checking Backend ---"
  python -m mypy "${ROOT_DIR}/backend/app" "${ROOT_DIR}/backend/tests"
  echo "--- Type checking Edge Agent ---"
  python -m mypy "${ROOT_DIR}/edge-agent/edge_ergo" "${ROOT_DIR}/edge-agent/tests"
  echo "--- Type checking Frontend ---"
  (cd "${ROOT_DIR}/frontend" && npx tsc -b)
}

run_test() {
  echo "--- Testing Backend ---"
  python -m pytest "${ROOT_DIR}/backend/tests"
  echo "--- Testing Edge Agent ---"
  python -m pytest "${ROOT_DIR}/edge-agent/tests"
  echo "--- Testing Frontend ---"
  (cd "${ROOT_DIR}/frontend" && npm run test)
}

run_build() {
  echo "--- Building Frontend ---"
  (cd "${ROOT_DIR}/frontend" && npm run build)
}

case "${TARGET}" in
  setup)
    run_setup
    ;;
  check-secrets)
    run_check_secrets
    ;;
  lint)
    run_lint
    ;;
  typecheck)
    run_typecheck
    ;;
  test)
    run_test
    ;;
  build)
    run_build
    ;;
  all)
    run_check_secrets
    run_lint
    run_typecheck
    run_test
    run_build
    echo ">>> All verification targets PASSED successfully!"
    ;;
  *)
    echo "Unknown target: ${TARGET}"
    exit 1
    ;;
esac
