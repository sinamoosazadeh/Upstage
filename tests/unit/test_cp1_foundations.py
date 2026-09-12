"""CP-1 packaging/foundation tests.

Covers MATRIX Part I rows:
  pyproject.toml · requirements.lock  -> test_packaging + test_sbom_pins_exact
  .gitignore (ADR-P2-013)             -> hygiene assertions here + test_import_graph
"""
from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# APEX_GEN5.md Ch.1 SBOM — the nine pins, verbatim order. This list is copied
# from the frozen blueprint (L99-L107) and is the reference for the lock file.
SBOM_NINE_PINS = [
    "aiohttp==3.9.5",
    "aiogram==3.7.0",
    "aiosqlite==0.20.0",
    "matplotlib==3.8.4",
    "pandas==2.2.0",
    "numpy==1.26.0",
    "pydantic==2.5.0",
    "python-dateutil==2.8.2",
    "pytz==2024.1",
]


def test_sbom_pins_exact() -> None:
    """requirements.lock IS exactly the nine Ch.1 pins (G15, ADR-P2-002)."""
    lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    pins = [ln.strip() for ln in lock.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert pins == SBOM_NINE_PINS, f"requirements.lock drifted from Ch.1 SBOM: {pins}"
    # pytest must NEVER be in the runtime lock (ADR-P2-002)
    assert not any("pytest" in p for p in pins)


def test_packaging() -> None:
    """pyproject declares the nine pins as runtime deps and pytest ONLY as dev extra."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for pin in SBOM_NINE_PINS:
        assert f'"{pin}"' in text, f"missing runtime pin in pyproject: {pin}"
    # pytest lives only in the tests extra
    assert 'tests = ["pytest>=7,<9"]' in text
    deps_block = text.split("[project.optional-dependencies]")[0]
    deps_code = "\n".join(ln for ln in deps_block.splitlines() if not ln.strip().startswith("#"))
    assert "pytest" not in deps_code, "pytest must not be a runtime dependency"
    # no python-dotenv anywhere (§9.5-12 / G16)
    assert "dotenv" not in text


def test_gitignore_adr_p2_013() -> None:
    gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for token in ("data/", ".env", "__pycache__/", ".pytest_cache/", "dist/", "build/"):
        assert token in gi, f".gitignore missing required entry: {token}"
    assert re.search(r"\*\.sqlite3", gi), ".gitignore must exclude sqlite3 artifacts"


def test_run_all_tests_script_present_and_executable_shape() -> None:
    script = REPO_ROOT / "scripts" / "run_all_tests.sh"
    assert script.exists() and script.stat().st_size > 0
    body = script.read_text(encoding="utf-8")
    assert "python -m pytest tests" in body


# NOTE: the six-params-YAML inventory + literal-value assertions live in
# tests/unit/test_params.py (shipped with the params commit, §CP-1 SEQUENCE).
