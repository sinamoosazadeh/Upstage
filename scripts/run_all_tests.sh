#!/usr/bin/env bash
# APEX_GEN5 — run the FULL test suite (unit + integration).
# Verified from a clean clone at CP-8 closeout; must keep running everything.
set -euo pipefail
cd "$(dirname "$0")/.."

# Toolchain selection: explicit $PYTHON wins; then an in-repo .venv; else
# the system interpreter (dev environments install pytest via the [tests]
# extra — see README; on-device the frozen Termux toolchain provides it).
if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif [ -x ./.venv/bin/python ]; then
    PY=./.venv/bin/python
else
    PY=python3
fi
"$PY" -m pytest tests/unit tests/integration "$@"
