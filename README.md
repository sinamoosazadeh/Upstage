# APEX_GEN5

Frozen-blueprint trading system implemented from `APEX_GEN5.md`.

- Frozen blueprint sha256: `216bcc9e5f3e54c7567303bea7b642a9f5ccf482d2282d05dc78c2f7cb0fbd9e` (the pre-implementation freeze; recorded in `docs/APEX_GEN5_frozen_216bcc.md`).
- Working-tree `APEX_GEN5.md` sha256 at CP-14.6-FIX: `493568887acb7164c985a0310809140ef3a6b3651e15d05782708b7f73e98569`.

Phase-2 chain control files: `PHASE2_*` (see `PHASE2_MASTER_PLAN.md`).

Runtime pin: `numpy==1.26.0` (`requirements.lock`). `RUNTIME_ARTIFACTS`: `params/e11_classifier_v1.yaml`, `data/` and train caches are gitignored and never committed. `status` and `serve` print `E11_ARTIFACT` or the loader refusal. A printed artifact name is not LIVE permission.

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

`scripts/run_apex.py` is the CP-7 composition root: ONE event loop, ONE ledger
writer queue, the execution FSM as the only path to the venue, the scheduler as
the only source of cell timing, Telegram as the only display surface
(Ch.23 L18253–18260). Every surface fails closed: missing credentials, an
unmeasurable clock or a missing handler produce a reported refusal, never an
invented result.

### 1. Environment — secrets come from the environment ONLY

The nine frozen env names (`apex/config.py`, no `python-dotenv`):

```bash
export APEX_ENV=PAPER                    # PAPER | LIVE | RESEARCH | BACKTEST (no SHADOW)
export APEX_ALLOW_SIGNED=1               # required for ANY PAPER/LIVE order (Y.1 L17093)
export APEX_ECONOMIC_GATE_SIGNED=0       # LIVE capital lock — CP-7 never sets this
export APEX_SQLITE_PATH=data/apex.sqlite3  # SQLite in WAL mode (default shown)
export TOOBIT_API_KEY=...                # venue credentials (env only, never in git)
export TOOBIT_API_SECRET=...
export TELEGRAM_BOT_TOKEN=...            # unset ⇒ E-TELE-001, no alert is delivered
export TELEGRAM_OWNER_CHAT_ID=-100...    # OWNER role (Ch.21 §6)
export TELEGRAM_WATCHDOG_CHAT_ID=-200... # HOST_DOWN independent channel
```

A `.env` file (git-ignored) may fill any of them; the real process environment
always wins (no shadowing). `--env-file PATH` selects another file explicitly.

### 2. Offline PAPER demo — the whole loop, no network, no capital

```bash
APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 TOOBIT_API_KEY=DEMO TOOBIT_API_SECRET=DEMO \
  python scripts/run_apex.py demo
```

Drives the fake Toobit responder (a test double) on a fixture clock:
`boot_state=READY` → `TRADE_PLAN` → submit `ACKNOWLEDGED` → entry `FILL` →
`PROTECTED` (STOP + LIMIT, GTC, reduceOnly) → `MANAGED` → exit `FILL` →
`CLOSED` + `OUTCOME` → `RECONCILED` (T_MATCH delta 0.00), ledger chain
`intact=True`, `signature violations: 0`, exit code `0`. Without a
`TELEGRAM_BOT_TOKEN` the signaling send is reported as
`REFUSED E-TELE-001` — the trading loop above is unaffected.

### 3. Universe and governed ceilings — read-only, no orders

```bash
python scripts/run_apex.py grid
```

Prints the 140-cell universe (10 Core-10 symbols × 14 timeframes; `3d`
unsupported, monthly is `1mo`), the clock-drift verdict, the last TF closes and
the T_MONOTONE leverage ceilings (min over ALL caps, never last-writer).

### 4. Real boot — reconcile-first against the venue

```bash
python scripts/run_apex.py boot          # add --json for the machine verdict
```

Runs environment init → dependency load (the nine SBOM pins) → SELF_TEST
(schema migrations, clock drift, emergency-ladder state) → RECONCILING
(positions, working orders, recent fills vs the ledger) → verdict.
Exit codes: `0` READY · `2` DEGRADED (or refused) · `3` RECOVERY_REQUIRED ·
`1` unexpected error. Without venue credentials, or when the drift cannot be
measured, the boot is DEGRADED and new trades are blocked — never assumed equal.

### 5. Alert-policy self-check (Ch.23)

```bash
python scripts/run_apex.py alerts
```

Prints the five policy rows verbatim (metric / threshold / alert / channel /
escalation / priority), the 30-minute dedup window with its EXEC_RECOVERY and
CIRCUIT_OPEN exemptions, and refuses with `E-TELE-001` when no bot token is set.

### 6. Tests

```bash
./scripts/run_all_tests.sh -q            # unit + integration (pytest, dev-only)
```

LIVE capital remains locked until `APEX_ECONOMIC_GATE_SIGNED=1` (Y.1 L17093);
CP-7 neither sets nor requires it. Charts are rendered with the Agg backend
in-memory only — zero display calls, nothing written to disk.
