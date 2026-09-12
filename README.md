# APEX_GEN5

Frozen-blueprint trading system implemented from `APEX_GEN5.md` (sha256
`216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e`).
Phase-2 chain control files: `PHASE2_*` (see `PHASE2_MASTER_PLAN.md`).

## Install

```bash
# Runtime: the locked SBOM (Ch.1 nine pins). pip install without the lock is
# forbidden in LIVE. Dev/test: the [tests] extra adds pytest ONLY (ADR-P2-002).
pip install -r requirements.lock
pip install -e ".[tests]"   # developers only
```

## Test

```bash
./scripts/run_all_tests.sh
```

## Run

The one-command run procedure (environment init → dependency load → runtime
start → Telegram operational) is finalized at CP-7 and verified at CP-8.
Foundation config surface (CP-1): environment names and `.env` parsing are
documented in `apex/config.py`; physical store is SQLite WAL at
`APEX_SQLITE_PATH` (default `data/apex.sqlite3`); parameter values live ONLY
in `params/*.yaml` (code loads, never hardcodes).
