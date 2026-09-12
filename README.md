# APEX_GEN5 — Phase 2 implementation (frozen blueprint `APEX_GEN5.md`)

Single-device (Termux/Android) crypto-futures system for Toobit, Phase Paper
capabilities. Built stage by stage (CP-1..CP-8) strictly from the frozen
specification; see `PHASE2_MASTER_PLAN.md` and the `PHASE2_*` control files.

## Run procedure (skeleton — CP-1; finalized by CP-7, verified by CP-8)

```bash
# 1. Environment (Python 3.11; Termux: pkg install python)
python -m venv .venv && source .venv/bin/activate

# 2. Dependencies — EXACTLY the locked SBOM (APEX_GEN5.md Ch.1)
pip install -r requirements.lock
pip install -e ".[tests]"        # dev-only: pytest (never a runtime dependency)

# 3. Configuration — copy and fill (names only; values never in git)
#    APEX_ENV, APEX_ALLOW_SIGNED, APEX_ECONOMIC_GATE_SIGNED,
#    TOOBIT_API_KEY, TOOBIT_API_SECRET, TELEGRAM_BOT_TOKEN,
#    TELEGRAM_OWNER_CHAT_ID, TELEGRAM_WATCHDOG_CHAT_ID, APEX_SQLITE_PATH
cat > .env <<'EOF'
APEX_ENV=PAPER
EOF

# 4. Tests (full suite)
bash scripts/run_all_tests.sh
```

Runtime entrypoint (Telegram control plane + PAPER loop) is delivered by
CP-7; until then the runnable surface is the test suite plus the library
packages under `apex/`.

## Repository layout (normative tree — APEX_GEN5.md §9.5, "create every file; do not rename")

- `apex/` — runtime package (config, errors, bus, identity, data_catalog, quality, engines, ...)
- `params/*.yaml` — the six frozen parameter files (code reads, never hardcodes)
- `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- `scripts/run_all_tests.sh` — full-suite runner

## Governance

`APEX_GEN5.md` is the single source of implementation truth; `PROMPT.md` is
the standing Chief-Engineer directive (source-of-record); the `PHASE2_*`
files coordinate the eight isolated implementation stages.
