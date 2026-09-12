#!/usr/bin/env bash
# APEX_GEN5 — Phase 2 full test-suite runner (CP-1 deliverable; §9.5 normative tree).
# Runs everything under tests/ with pytest (dev-only extra; never a runtime dep).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PWD}${PYTHONPATH:+:$PYTHONPATH}"
exec python -m pytest tests -v "$@"
