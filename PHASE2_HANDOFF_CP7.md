# PHASE2 HANDOFF — CP-7 → consumed by CP-8 (and CP-8 closeout)
Stage: CP-7 — Execution/Ledger/Scheduler (Ch.16,19) + Telegram/Alerts (Ch.21,23)
Rules (PROTOCOL P16): author = CP-7 executor (or its continuation session — state which, first line of STATUS). ≤400 lines, nine headings below in order. Successors read ONLY this file + their own prompt/law/checkpoint sections; interfaces listed here are the public contract they may code against. First STATUS line: `LAW-ACK: G1..G20 + P1..P21 read <UTC>`.

## STATUS
LAW-ACK: G1..G20 + P1..P21 read 2026-09-14T11:07:26Z

- complete — the stage is fully closed; no CONTINUE-NEEDED item.
- Author: the CP-7 **continuation session** (the original CP-7 session's commits were lost to a workspace re-clone; the code, tests and docs were re-derived from the blueprint and re-committed on `arena/01a09b05-upstage`).
- Commits: `8b5db70` (board claim) → `4f9b8c3` map+adapter+ledger → `221f940` FSM → `de3268d` scheduler → `0866ab9` telegram → `4b90913` integration loop → `3b821b3` run_apex + README → docs/closeout commit (this file, MATRIX, board, DECISION_LOG). CP-7 code range = **`4f9b8c3..3b821b3`**.
- Suite: **2185 passed / 0 failed** (`./scripts/run_all_tests.sh -q -p no:warnings`, 68.5 s), of which **635 are CP-7 tests** (221 + 135 + 73 + 173 + 33).
- Environment: CPython 3.11.2 in `.venv/` (re-created this session — `.venv` is not persisted by the sandbox), Linux x86-64, the nine SBOM runtime pins from `requirements.lock`, SQLite WAL, `matplotlib` forced to Agg. No network was used: every venue interaction in the suite goes through `tests/fake_toobit_responder.py` (a test double).
- Budget: this continuation session ended with a green push and an empty remaining-work ledger.

## DELIVERED
| file | purpose | blueprint section | rows into MATRIX Part III |
| --- | --- | --- | --- |
| `apex/execution/toobit_map.py` | wire vocabulary: symbols, intervals, sides, the governed order table, business-code classification, leverage caps, numeric floor, HMAC signing, the five operations × eleven signed paths | Ch.16 L16802, L16843–16910; Y.2 L17405–17423; Y.3 | C7-WIRE&#124;1–7 |
| `apex/execution/toobit_adapter.py` | the ONLY venue contact: exactly five operations, no silent retries, duplicate/lost-ack semantics, immutable adapter-owned state, per-endpoint rate buckets, signed gating, injected transport seam | Ch.16 L16843–16900; AI.3 L18398–18430; AI.8 L18749–18810 | C7-AD&#124;1–12 |
| `apex/execution/fsm.py` | SL-6 canonical FSM + the frozen 52-edge matrix, E-EXEC-001 timeouts, pre-submission validation, protection + stop-gap attribution, reconcile-first, `build_trade_plan`, the Ch.23 boot matrix, the AI.9 seven-check recovery reconciliation | Ch.16 L16745–16921; Ch.23 L18242–18251; AI.4 T-MON-002; AI.9 L18894–18903; Ch.1 L255 | C7-FSM&#124;1–16 |
| `apex/ledger/store.py` | single-writer ledger (grep-enforced), T_LEDGER chain, T-LR-001/002/003, `positions_from_ledger`, TEXT-Decimal money boundary, CP-7 migrations `M101`/`M102` | Ch.5 L14507–14522; Ch.16 L16816–16836 (trade_plan DDL); AI.7 L18715; AI.9 L18825–18845; Ch.23 L18253–18310 | C7-LG&#124;1–10 |
| `apex/scheduler/clock.py` | SystemClock/FixtureClock, the 140-cell universe, nine-stage order, semaphore 4, P0–P3 lanes, drift block, T_MONOTONE min-over-all-caps, HTF last-closed guard, contention serialization | Ch.17 L16990–17011; Ch.23 L18253–18260; §9.5-8/-14; Y.2; Y.3 L17437; AI.12 Phase 3; SL-8/E-PIT-001 | C7-SCH&#124;1–9 |
| `apex/telegram/signaling.py` | the §10 parameter table, token bucket, idempotency registry, retry/backoff, formatting + truncation codes, §8 emission law, §11 message states, Agg-only in-memory charts, the Ch.23 alert policy (five rows + dedup + audit) | Ch.21 §1–§12, §14; Ch.23 L18292–18310 | C7-RATE&#124;1–9, C7-AL&#124;1–8 |
| `apex/telegram/control_plane.py` | the nine screens §5.1–§5.8, OWNER/USER roles (no ADMIN), Busy Guard E-VAL-020, 90 s confirmation nonce, Emergency ratchet L1–L5 + RSK-ERR-506, Panic Lock, `update_id` replay, callback parsing, injected handler seam | Ch.21 §5–§7, §10; Ch.15 §15.1 (CANCEL_ALL ≤12) | C7-TG&#124;1–11 |
| `scripts/run_apex.py` | the runnable increment: `boot` / `grid` / `demo` / `alerts`, one Runtime context manager that closes every resource, documented exit codes, no secret printed | PHASE2_CHECKPOINTS §CP-7 EXIT; Ch.23 boot; §9.5-12/13 | X-13 |
| `README.md` (run section) | FINAL, copy-paste verified this session (six subsections + LIVE-lock and Agg notes) | PHASE2_CHECKPOINTS §CP-7 EXIT | Part I README row |
| `tests/unit/test_toobit_map.py` (84) · `test_toobit_adapter.py` (73) · `test_execution_fsm.py` (135) · `test_ledger_store.py` (64) · `test_scheduler_clock.py` (73) · `test_telegram_signaling.py` (71) · `test_telegram_control_plane.py` (102) | unit proof of every row above | AI.10 id names | Part II CP-7 row |
| `tests/integration/test_cp7_paper_loop.py` (33) | the whole PAPER loop on a fixture clock against the fake responder | PHASE2_CHECKPOINTS §CP-7 (6) | X-12 |
| `tests/fake_toobit_responder.py` · `tests/fixtures/toobit_adapter_conformance.json` (19 cases, `cases_sha256 cd1ba348…29c17`) | the ONLY venue double + the hash-locked conformance fixture CP-8's harness consumes | AI.10 conformance harness | C7-AD&#124;11 |

## INTERFACES
Everything below is the public contract CP-8 may code against. `CONTRACT_VERSION = "4.0.0"` in all seven modules. Nothing is invented: each entry carries its blueprint cite in DELIVERED.

| module | class/function | signature | semantics | version |
| --- | --- | --- | --- | --- |
| `apex.execution.toobit_map` | `to_wire_symbol` / `to_internal_symbol` | `(symbol: str) -> str` | Core-10 ⇄ `<BASE>-SWAP-USDT`; an unlisted symbol raises `ToobitMapError("SYMBOL_UNSUPPORTED")` | 4.0.0 |
| " | `to_wire_interval` | `(interval: str) -> str` | the 14 intervals verbatim, `1mo -> "1M"`; `3d` raises `ToobitMapError("TIMEFRAME_UNSUPPORTED")` (E-VAL-022) | 4.0.0 |
| " | `endpoint_for` / `assert_path_permitted` / `auxiliary_paths_for` | `(operation: str) -> Tuple[str, str]` · `(method, path) -> None` · `(operation) -> Tuple[Tuple[str,str], ...]` | the five operations; a path outside the eleven-path wire list raises `ToobitMapError("PATH_NOT_PERMITTED")`; auxiliary paths are bound to exactly one operation (ISSUE-CP7-002) | 4.0.0 |
| " | `side_for` / `order_defaults` / `assert_order_type_permited` / `assert_account_mode` | `(direction, phase) -> str` · `(kind) -> Dict[str,str]` · `(order_type) -> None` · `(margin_mode, position_mode) -> None` | BUY_OPEN/SELL_CLOSE/SELL_OPEN/BUY_CLOSE; entry LIMIT/IOC/priceType INPUT, stop STOP+priceType MARKET, target LIMIT/GTC; `type=MARKET` raises; account must be ISOLATED + ONE_WAY | 4.0.0 |
| " | `classify_business_code` | `(code: Optional[int], *, operation: str = "", context: Mapping = None) -> Dict[str, Any]` | `{"code", "classification": OK&#124;UNKNOWN&#124;ABORT&#124;BACKOFF&#124;INTERVAL_UNSUPPORTED&#124;RECONCILE&#124;UNMAPPED_CODE, "outcome", "resubmit": False, "reason"}`; −1120 → interval disabled for that (symbol,TF) only; −1021/−2026 → UNMAPPED → UNKNOWN + RECONCILE (ISSUE-CP7-001) | 4.0.0 |
| " | `resolve_leverage` | `(timeframe, *, symbol=None, exchange_max=125.0, owner_cap=None) -> Dict[str, Any]` | `{"leverage", "binding_cap", "caps": {...}}` = **min over ALL caps** (T_MONOTONE), never the last writer | 4.0.0 |
| " | `quantize_price` / `quantize_quantity` / `check_min_notional` | `(symbol, value, *, mode="") -> Decimal` · `(...) -> Dict[str, Any]` | Decimal floor at the wire boundary; a float is converted once and never re-rounded | 4.0.0 |
| " | `build_signed_query` / `signed_request` / `sign_query` | `(params, *, timestamp_ms, recv_window_ms=5000, nonce=None) -> str` | HMAC-SHA256 over the canonical query string; the API key goes in HEADERS, never params | 4.0.0 |
| " | `execution_idempotency_key` / `retry_policy` / `rollover_entry_allowed` / `funding_alert` | `(intent_id, order_id, ...) -> str` · `() -> Dict` · `(days_to_expiry) -> Dict` · `(rate) -> Dict` | TTLs 60 s (submission) / 30 s (position transition) / 86400 s (Telegram); the rollover window vetoes a new entry; funding is carried, never derived | 4.0.0 |
| `apex.execution.toobit_adapter` | `ToobitAdapter.__init__` | `(*, config: Optional[Config] = None, transport: Optional[Callable] = None, clock: Optional[Clock] = None, environment: Optional[str] = None, allow_signed: Optional[bool] = None) -> None` | `transport` is the seam (production `aiohttp_transport(session)`, tests `FakeToobitResponder`); all state is adapter-owned | 4.0.0 |
| " | `submit_order` | `(*, intent_id, symbol, timeframe, direction, quantity, price, phase="entry", kind="entry", order_type=None, reduce_only=False, leverage=None, owner_leverage_cap=None, extra_params=None, timestamp_utc=None, nonce=None) -> AdapterResult` | `intent_id` → `clientOrderId` (mandatory); one POST; duplicate → the ORIGINAL result (`cached=True`), no second order | 4.0.0 |
| " | `cancel_order` | `(*, symbol=None, client_order_id=None, order_id=None, scope="single", cancel_id=None, timestamp_utc=None, nonce=None) -> AdapterResult` | `scope="all"` is the protective CANCEL_ALL batch path (≤12) and is still ONE operation | 4.0.0 |
| " | `query_order_state` | `(*, symbol=None, client_order_id=None, order_id=None, scope="single", timestamp_utc=None, nonce=None) -> AdapterResult` | `scope="open"` → openOrders, `scope="fills"` → userTrades: the reads Ch.23 RECONCILING requires | 4.0.0 |
| " | `query_open_positions` | `(*, symbol=None, timestamp_utc=None, nonce=None) -> AdapterResult` | the exchange side of every reconciliation; `.ok` / `.data` | 4.0.0 |
| " | `query_account_margin_health` | `(*, margin_type_symbols=None, leverage_requests=None, commission_symbols=None, timestamp_utc=None, nonce=None) -> AdapterResult` | balance + ISOLATED/ONE_WAY setup + leverage at min(all caps) + commissionRate **stored, never invented** | 4.0.0 |
| " | `AdapterResult` | dataclass → `.ok .operation .outcome .classification .order_id .client_order_id .status .body .attempts .audit .idempotency_key .reconcile_required .resubmitted .cached .interval_disabled .reason .detail` + `.to_dict()` | outcome ∈ ACKNOWLEDGED / PARTIAL / FILLED / REJECTED / DUPLICATE / UNKNOWN; a lost ack is UNKNOWN with `reconcile_required=True, resubmitted=False` | 4.0.0 |
| " | `state` / `audit_trail()` / `disabled_intervals()` / `is_interval_disabled()` / `rate_bucket_state()` | properties → frozen views | reading is allowed; assigning any adapter-owned attribute raises `AdapterStateMutationError` (`__setattr__` guard) | 4.0.0 |
| " | `AdapterError(reason, detail="")` + `AdapterStateMutationError`, `AdapterTimeout` | `.reason` / `.detail` | refusals: `INTENT_ID_REQUIRED`, `SIGNED_NOT_ALLOWED`, `TOOBIT_CREDENTIALS_MISSING`, `RATE_BUCKET_EXHAUSTED`, `PATH_NOT_PERMITTED` … always raised, never returned as fake data | 4.0.0 |
| `apex.execution.fsm` | `FSM_STATES` / `FSM_TRANSITIONS` / `canonical_state` / `legal_targets` / `is_legal` | `Tuple[str, ...]` · `Dict[(src, trigger), dst]` · `(name) -> str` · `(state) -> Dict[trigger, dst]` · `(src, trigger, dst) -> bool` | the nine SL-6 states + RECOVERY_REQUIRED/REJECTED/CANCELLED; 52 edges; an unknown alias raises `FsmError("NOT_AN_FSM_STATE")` | 4.0.0 |
| " | `ExecutionFSM.__init__` | `(*, intent_id=None, symbol=None, timeframe=None, environment=None, ledger=None, bus=None, adapter=None, clock=None, plan=None) -> None` | loop-bound: create it inside one `asyncio.run()` | 4.0.0 |
| " | `advance` | `(trigger, *, reason="", evidence=None) -> TransitionRecord` | publishes an `FSM_TRANSITION` bus event + a ledger record; an illegal trigger raises `IllegalTransitionError` and writes NOTHING | 4.0.0 |
| " | `submit` / `apply_adapter_result` / `record_fill` / `place_protection` / `activate_management` / `close_position` / `cancel` / `reconcile` / `require_reconciled` | async, see source | each is one governed path: submit materializes the TRADE_PLAN row first; `record_fill(fill_id, price, quantity, *, side, fee="", ts)` is idempotent under `fill_id`; `place_protection(stop_price, target_price, *, ...)` writes both legs reduceOnly; `close_position(...)` appends the OUTCOME only; `reconcile(exchange_position=..., ledger_position=...)` → `{"agree", "state", "delta", "action", "new_entries_blocked", "ledger_id", "rule"}` | 4.0.0 |
| " | `pre_submission_validation` / `check_timeouts` / `apply_timeouts` | `(plan) -> Optional[Dict]` · `(*, now=None) -> Dict` | refusals RISK_REJECT / QUANTITY_ZERO / NO_TRADE_DIRECTION / TF_DISABLED_FOR_SYMBOL / DECISION_QX / ROLLOVER_WINDOW; E-EXEC-001 windows 5 s + 5 s (fill window starts at the FIRST venue response incl. PARTIAL) | 4.0.0 |
| " | `build_trade_plan` | `(*, proposal, adjudication, symbol, timeframe, environment, leverage=None, owner_leverage_cap=None, proposal_id=None, setup_id=None) -> TradePlan` | projects CP-6's shapes onto the frozen Ch.16 columns; DECISION_QX / ENVIRONMENT_QX (no SHADOW) / DIRECTION_QX fail closed; NO_TRADE → FLAT; leverage = min over ALL caps | 4.0.0 |
| " | `StartupReconciliation.__init__` / `run` / `self_test` / `reconcile_boot` / `run_recovery_reconciliation` / `drift_blocks_new_trades` / `ladder_actions_available` | `(*, ledger=None, adapter=None, store=None, config=None, bus=None, environment=None, drift_seconds: Optional[float] = None, now=None)` · async → Dict | boot verdict `{"verdict": READY&#124;DEGRADED&#124;RECOVERY_REQUIRED, "environment", "state", "checks", "reconcile", "reason", "new_trades_blocked"}`; `drift_seconds=None` means UNMEASURABLE → never assumed synchronized; the AI.9 seven checks run in order and a missing provider HALTS with UNAVAILABLE | 4.0.0 |
| `apex.ledger.store` | `LedgerWriter.__init__` / `initialize` / `start` / `stop` | `(store, *, actor="LEDGER", db_path=None)` · async | ONE writer per ledger: a second one on the same store raises `LedgerSingleWriterError`; `initialize()` runs CP-1 migrations + `M101`/`M102` + the CP-6 ladder hook; `stop()` closes the queue AND the aiosqlite connection (an unclosed one hangs the process) | 4.0.0 |
| " | `append` | `(*, event_type, actor=None, intent_id=None, order_id=None, fill_id=None, cancel_id=None, price=None, quantity=None, fee=None, slippage=None, raw=None, payload=None, until=None) -> LedgerEntry` | the ONLY write path; the chain hash + parent linkage are computed inside the writer task | 4.0.0 |
| " | `append_fsm_transition` / `append_fill` / `append_trade_plan` / `append_outcome` / `append_correction` | async | `append_trade_plan(plan)` stores the mapping under key `"trade_plan"`; `append_correction(*, supersedes, reason, ...)` appends, never edits | 4.0.0 |
| " | `verify_chain` | `() -> Dict` | `{"records", "intact": bool, "breaks": [...]}` — detects a covert INSERT (linkage) and a covert MODIFY (hash) | 4.0.0 |
| " | `positions_from_ledger` | `() -> Dict[str, Dict[str, Any]]` | `{"quantity": Decimal-TEXT (signed, `'0.0'` when flat), "entry_price", "fills", ...}` — the VWAP is over OPENING fills only | 4.0.0 |
| " | `require_reconciled` / `reconcile_against_exchange` / `blocked` / `blocked_reason` / `read_ledger` / `find_by_fill` / `find_by_intent` / `trade_plans` / `applied_migrations` | async (first two) | T-LR-002 raises `LedgerNotReconciled` while blocked; T-LR-003 writes CORRECTION_EVENT, blocks new entries beyond ±1 unit and lifts the block with RECONCILE_RESOLVED | 4.0.0 |
| " | `LedgerEntry` | `.ledger_id .intent_id .event_type .payload .parent_ids .payload_hash .price .quantity .fee .slippage .raw .until .timestamp` + `.decision` / `.result` / `.pnl` / `.to_row()` | absent money is `''` in the row and `None` on read (ISSUE-CP7-008) | 4.0.0 |
| `apex.scheduler.clock` | `Clock` / `SystemClock` / `FixtureClock` | `.now_ms() -> int` · `.utc_now() -> str` · `.monotonic() -> float`; `FixtureClock(start="2026-01-01T00:00:00.000Z")` + `.advance(seconds)` / `.advance_to(iso)` / `.advance_to_next_close(tf)` / `.elapsed_seconds()` | UTC only (no local offset/DST); FixtureClock is deterministic and never runs backward | 4.0.0 |
| " | `tf_seconds` / `tf_close_times` / `next_close` / `htf_last_closed_guard` | `(tf) -> int` · `(tf, *, start_ms, end_ms) -> List[int]` · `(tf, *, now_ms) -> int` · `(*, htf_close_ms, current_close_ms) -> Dict` | an unknown TF raises E-VAL-022; an HTF close after the current close is refused as E-PIT-001 | 4.0.0 |
| " | `measure_drift` / `drift_verdict` | `(provider, clock) -> Dict` · `(drift_seconds) -> Dict` | PASS ≤0.5 s · DEGRADED >0.5 s (E12, trading paused) · DEGRADED >5 s (new trades blocked) · UNAVAILABLE when unmeasurable (ISSUE-CP7-004) | 4.0.0 |
| " | `monotone_leverage` / `monotone_check` | `(tf, *, symbol=None, exchange_max=125.0, owner_cap=None) -> Dict` · `(values) -> Dict` | min over ALL caps, order-independent, non-increasing under tightening | 4.0.0 |
| " | `universe_cells` / `BundleCell` / `Scheduler` | `(*, symbols=CORE10_SYMBOLS, timeframes=TIMEFRAMES_14, disabled=None) -> Tuple[BundleCell, ...]` (140) · `.cell_id` / `.tf_seconds` · `(*, clock=None, cells=None, environment=None, bus=None, owner_leverage_cap=None, semaphore=SCHEDULER_SEMAPHORE, stages=PIPELINE_STAGES)` | `Scheduler.register(stage, handler)` · `.due_cells(*, now_ms=None)` · `.run_cell(cell, *, close_ms=None, priority="P2")` · `.run_due(*, now_ms=None, cells=None)` · `.run_burst(cells)` · `.serialized(work)` · `.concurrent_peak` · `.runs()` | 4.0.0 |
| `apex.telegram.signaling` | `SignalingPlane.__init__` | `(*, transport=None, config=None, ledger=None, bus=None, clock=None, chart_backend="Agg") -> None` | no adapter, no ledger write path other than the ALERT audit row: a signaling failure can never block protective execution | 4.0.0 |
| " | `send` / `emit_alert` / `calc_telegram_message` / `bucket_for` / `stats` | `(message, *, chat_id=None, dedup=True) -> SendResult` · `(*, alert, metric, threshold, observed, snapshot_id="", priority=None, dedup=True) -> Dict` · `(message) -> Dict` | `send` applies the §8 emission law, the token bucket, the SHA256 idempotency key (24 h TTL), 3 retries with 1/2/4 s backoff and the durable outbox; `emit_alert` applies the Ch.23 policy rows + the 1800 s dedup with the two exemptions | 4.0.0 |
| " | `check_feed_staleness` / `check_heartbeat` / `check_storage` / `veto_alert_message` / `alert_row` / `dedup_verdict` | async (first three) | policy row 1 (>2× freshness), row 4 (3 missed 60 s heartbeats → the independent channel), row 5 (>0.80); the P1 veto alert keys off CP-6's `fired_numbers` | 4.0.0 |
| " | `render_chart` / `_matplotlib_agg` / `escape_markdown_v2` / `format_markdown_v2` / `format_html` / `format_caption` / `build_inline_keyboard` / `idempotency_key` | `(*, ohlcv, symbol="", timeframe="", layers=(), ...) -> Dict` | Agg before pyplot; the PNG is exactly 1200×800 and stays in memory (never written to disk); Market Profile is always UNAVAILABLE | 4.0.0 |
| " | `MessageTokenBucket` / `IdempotencyRegistry` / `SignalMessage` / `SendResult` / `TelegramTransport` / `AiogramTransport.from_env` | see source | the bucket capacity may not exceed the 30/s provider ceiling; `from_env` reads the token from the environment only (missing → E-TELE-001) | 4.0.0 |
| `apex.telegram.control_plane` | `ControlPlane.__init__` | `(*, signaling=None, access=None, ledger=None, bus=None, clock=None, handlers=None, environment=None) -> None` | every effect is dispatched to an injected handler; a missing handler is refused (`ACTION_HANDLER_UNAVAILABLE`), never faked as done | 4.0.0 |
| " | `render` / `handle_command` / `handle_callback` / `dispatch` / `register` | `(screen, chat_id, **kwargs) -> Dict` · `(chat_id, text, *, update_id=None) -> Dict` · `(chat_id, data, *, update_id=None) -> Dict` · `(action, payload) -> Dict` | screens §5.1–§5.8; `/start /myid /help /lock /unlock`; a replayed `update_id` returns the recorded result; callback data >64 bytes is refused | 4.0.0 |
| " | `AccessControl` / `ConfirmationRegistry` / `BusyGuard` / `UpdateDeduplicator` / `EmergencyRatchet` / `validate_export_request` / `nonce_key` | `.role_of(chat_id) -> "OWNER"&#124;"USER"` · `.check(...) -> AccessVerdict` · `.issue(action, chat_id) -> Nonce` / `.consume(key, *, action, chat_id, choice)` · `.try_acquire(run_id) -> BusyGuardVerdict` / `.release()` · `.is_replay/.record/.replay_of` · `.request(level)` / `.recover(*, role)` · `(*, items, time_range, environment, fmt, path=EXPORT_DEFAULT_PATH) -> Dict` | no ADMIN role exists; an unknown chat_id is a USER; a nonce lives 90 s and is single-use; MAX_CONCURRENT=1 → E-VAL-020 + a Stop button; the ratchet goes UP only (down → RSK-ERR-506, OWNER-only recovery); export is CSV/JSON, ≤25 items | 4.0.0 |
| `scripts/run_apex.py` | `Runtime` (context manager) + `boot` / `grid` / `demo` / `alerts` | `.venv/bin/python scripts/run_apex.py <cmd> [--env-file PATH]` | one `asyncio.run()`; closes store/ledger/bus/adapter in `finally`; exit 0 READY · 2 DEGRADED or refused · 3 RECOVERY_REQUIRED · 1 unexpected error | — |
| `tests/fake_toobit_responder.py` | `FakeToobitResponder` | `(*, symbols=None, verify_signatures=True)`; `.recorded_calls` → `RecordedCall(seq, method, path, params, headers, signature_ok, recv_window_ok, api_key_present, responded, note)`; `.lose_next_ack(n)`; `.order_book()` | the ONLY venue double; HMAC is verified over the RAW query string; arm `lose_next_ack` AFTER boot | 4.0.0 |

CP-8 consumption notes (facts that are easy to get wrong, all verified against source):
1. `LedgerWriter`, the bus and every FSM are **event-loop bound** — build them inside ONE `asyncio.run()` (see the `scenario()` helper in `tests/integration/test_cp7_paper_loop.py`).
2. `adapter.server_time` does not exist; drift is measured by GET `/api/v1/time` through `aiohttp_transport(session)` (`scripts/run_apex.py::_venue_server_time`).
3. `ErrorCode` exposes `.code`, not `.message`. `AdapterError`/`SignalingError` expose `.reason` (+ `.detail`).
4. PAPER orders still need `APEX_ALLOW_SIGNED=1`; `APEX_ENV` is not a capital switch and the economic gate is advisory in PAPER/RESEARCH (binding only in LIVE).
5. The event bus is an in-process `asyncio.Queue`: P0 is inline, P1–P3 need `await bus.start()`.
6. SQLite WAL creates `-shm`/`-wal` side files — treat them as expected in "no file written" assertions.
7. `scheduler.leverage_for()` and `clock.iso()` do not exist — use `monotone_leverage(tf, symbol=...)` and `FixtureClock.utc_now()`.
8. The AI.10 conformance harness (CP-8's scope) should load `tests/fixtures/toobit_adapter_conformance.json` and check `_meta.cases_sha256` before running; CP-7 already asserts all 19 cases against the real adapter.

## DATA-CHANGES
No CP-1 table was altered. Two new tables + two audit triggers, created by CP-7 migrations recorded in CP-1's `schema_migrations` bookkeeping (`apex/ledger/store.py`), plus one reuse of CP-6's hook:

| migration id | object | columns / DDL | source |
| --- | --- | --- | --- |
| `M101_cp7_trade_plan` | table `trade_plan` (21 columns) | `proposal_id TEXT PK, setup_id TEXT NOT NULL, symbol TEXT, timeframe TEXT, direction TEXT CHECK IN ('LONG','SHORT','FLAT'), entry_ref TEXT, stop_price REAL, target_price REAL, sized_quantity REAL NOT NULL, risk_amount REAL, contract_multiplier REAL, decision TEXT CHECK IN ('ALLOW','REDUCE','REJECT'), vetoes_applied TEXT, risk_state TEXT, package_version TEXT, snapshot_id TEXT, as_of TEXT, created_utc TEXT, lineage TEXT, payload_hash TEXT, environment TEXT CHECK IN ('PAPER','LIVE','RESEARCH','BACKTEST')` — **verbatim** from the frozen Ch.16 DDL (L16816–16836), including its REAL columns; the TEXT-Decimal money law is enforced at the `ledger` boundary (Ch.5 DDL), not by re-typing a frozen table | Ch.16 L16816–16836 |
| `M102_cp7_ledger_audit` | table `ledger_audit` (6 columns) + triggers `ledger_audit_no_update` / `ledger_audit_no_delete` (both `RAISE(ABORT,'AUDIT_APPEND_ONLY')`) | `audit_id TEXT PK, ledger_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT, timestamp TEXT NOT NULL` | AI.8 L18806–18810 |
| (reuse) `M100_cp6_ladder_state` | `LedgerWriter.initialize()` invokes CP-6's `apex.risk.kernel.apply_ladder_state_migration(db)` so the boot self-test can read `schema_migrations` + the ladder table | no new DDL | ADR-P2-004 |
| rows only | `ledger` (Ch.5/Ch.4 frozen DDL) | new `event_type` values written through the single writer: `FSM_TRANSITION`, `TRADE_PLAN`, `FILL`, `OUTCOME`, `CORRECTION_EVENT`, `RECONCILE_RESOLVED`, `ALERT`; absent money is stored as `''` because the frozen `CHECK(typeof(price)='text')` rejects NULL (ISSUE-CP7-008) | Ch.5 L14507–14522 |
| none | no `params/*.yaml` file was created or edited | CP-7 constants with no YAML home are frozen in-module with the blueprint line cite (ISSUE-CP7-003) | P2/G4 + the CP-7 write set |

## TESTS
| test file | ids covered | result |
| --- | --- | --- |
| `tests/unit/test_toobit_map.py` (84) | T_MATCH (symbol/interval exactness incl. 1mo→1M, E-VAL-022 on 3d), the five-operation law, the eleven-path wire list + no-unlisted-path, business-code classification (−1120/−1022/−1003/−1021/−2026), T_MONOTONE caps, numeric floor + HMAC signing, rollover/funding | 84 passed |
| `tests/unit/test_toobit_adapter.py` (73) | T_ADAPTER_SUBMIT, T_ADAPTER_DUPLICATE, T_ADAPTER_LOST_ACK, no-silent-retry law, adapter-state protection, signed gating (§9.5-12/13), rate buckets (AI.8), pre-submission refusals, transport seam, Wave-Out surface, the 19-case conformance fixture (hash-locked) | 73 passed |
| `tests/unit/test_ledger_store.py` (64) | T-LR-001, T-LR-002, T-LR-003, T_LEDGER (chain + covert INSERT/MODIFY), single-writer law, positions_from_ledger (VWAP over opening fills), money boundary, trade_plan + outcome materialization, stop gap, audit trail, WAL/read path | 64 passed |
| `tests/unit/test_execution_fsm.py` (135) | the SL-6 canonical list + the frozen 52-edge matrix, Ch.1 aliases, T-MON-002, E-EXEC-001 (submission + fill windows), pre-submission validation, submit/apply_adapter_result/fills, protection + PROTECTION_FAILED escalation, close + stop-gap attribution, cancel (single + scope=all), reconcile (T_MATCH/divergence/terminal), build_trade_plan projection, the Ch.23 boot matrix + four self-test items, AI.9 seven-check recovery reconciliation | 135 passed |
| `tests/unit/test_scheduler_clock.py` (73) | §9.5-14 stage order, §9.5-8 universality (140 cells), FixtureClock determinism/monotonicity, drift measure + drift block, T_MONOTONE, HTF last-closed (E-PIT-001), pipeline order, semaphore 4, P0–P3 lanes, contention serialization, per-cell leverage + lookup | 73 passed |
| `tests/unit/test_telegram_signaling.py` (71) | Ch.21 §10 parameter table, formatting/truncation (E-TELE-003/004/005), idempotency key (E-TELE-007), token bucket vs the 30/s ceiling (E-TELE-006), sending + retry/backoff, §8 emission formula, §11 message state machine, Ch.23 alert policy (5 rows + dedup + exemptions + audit), never-blocks-execution, charts (Agg, 1200×800, no disk write), secrets (E-TELE-001/002) | 71 passed |
| `tests/unit/test_telegram_control_plane.py` (102) | frozen literals, access control (no ADMIN), confirmation nonce (90 s), Busy Guard (E-VAL-020), update dedup, export wizard, emergency ratchet (RSK-ERR-506), screens §5.1–§5.8, commands, callbacks, the full emergency flow, control-plane guardrails | 102 passed |
| `tests/integration/test_cp7_paper_loop.py` (33) | X-12: clean PAPER loop end to end, scheduler in the loop, drift blocks the loop, lost-ack recovery with a P0 alert and ONE submission, control plane in the loop, signaling in the loop, loop determinism (two identical runs) | 33 passed |
| whole suite | CP-1…CP-7 | **2185 passed / 0 failed** (68.5 s) |

## DEVIATIONS
- ADR-P2-015 applied: CP-7 was built from zero against the blueprint (no prior-attempt code was cloned or referenced); the lost commit history was re-created, not resurrected.
- ADR-P2-004 applied: `LedgerWriter.initialize()` calls CP-6's ladder-state migration hook so the boot SELF_TEST can read `ladder_state`; no CP-6 file was edited.
- ADR-P2-001 applied: `apex/config.py` (CP-1) remains the single configuration reader — no CP-7 module re-reads `.env`, and the nine environment names are consumed through `Config` only.
- ADR-P2-002 applied: all money crossing the ledger boundary is TEXT Decimal; the adapter quantizes with `Decimal` and never lets a float reach a signed field.
- ADR-P2-003 applied: the event bus stays an in-process `asyncio.Queue`; no broker, no Postgres, no cross-process queue was introduced.
- Otherwise: none. Every ambiguity found was logged as an ISSUE (below) instead of being silently resolved (G4).

## OPEN-ISSUES
Mirrored verbatim-in-substance to `PHASE2_DECISION_LOG.md` §B/CP-7 (that file carries the full A | B | Rule | Interim | Needs-from-owner form).

- [ISSUE-CP7-001] severity: MAJOR | status: CLOSED | A: the CP-7 RULES require the wire map to carry −1120/−1021/−1022/−1003/−2026 | B: **−1021 and −2026 appear nowhere in the frozen blueprint** (zero occurrences in `APEX_GEN5.md`) and codes may not be invented (G6) | Rule applied: unlisted code ⇒ UNMAPPED ⇒ outcome UNKNOWN ⇒ RECOVERY_REQUIRED + reconcile-before-action (Ch.16 L16861–16863) | Interim behavior: `classify_business_code` returns UNMAPPED_CODE/UNKNOWN/RECONCILE/resubmit=False, pinned by tests + fixture cases C-16/C-17 | Needs from owner: confirm the intended venue semantics of −1021 and −2026 at CP-8 triage.
- [ISSUE-CP7-002] severity: MINOR | status: CLOSED | A: exactly five adapter operations (Ch.16 L16852, AI.3) | B: eleven signed paths (L16884–16895) plus Ch.23 RECONCILING reads, CANCEL_ALL ≤12 and marginType/leverage/commissionRate | Rule applied: the operation surface stays five; each auxiliary path is reachable only INSIDE one named operation | Interim behavior: `OPERATION_AUXILIARY_PATHS` + tests asserting the intersection and the no-unlisted-path guard | Needs from owner: none.
- [ISSUE-CP7-003] severity: MINOR | status: CLOSED | A: P2/G4 — parameter values live only in `params/*.yaml` | B: CP-7 may not write `params/*.yaml` and several CP-7 constants have no YAML home | Rule applied: no invented keys in a file outside the write set; freeze the literal in the owning module with the line cite + a test asserting it literal-by-literal | Interim behavior: module constants + checked views (`TELEGRAM_PARAMS`, FSM timeouts, order table) | Needs from owner: decide at CP-8 triage whether these move into a params file.
- [ISSUE-CP7-004] severity: MINOR | status: CLOSED | A: Ch.17 L16995 `clock_drift_tolerance = 5 s` + Ch.23 L18244 "drift beyond the governed tolerance blocks new trades" | B: AI.7 L18723–18724 NTP within ±100 ms and E12 DEGRADED + trading paused when drift > 500 ms | Rule applied: three numbers, three jobs — ±100 ms is the sync TARGET (reported, not gated), 500 ms is the E12/pause threshold, 5 s is the boot tolerance that blocks new trades | Interim behavior: PASS ≤0.5 s · DEGRADED >0.5 s · DEGRADED >5 s · **UNAVAILABLE when unmeasurable**; `drift_blocks_new_trades` uses 500 ms | Needs from owner: none.
- [ISSUE-CP7-005] severity: MINOR | status: CLOSED | A: Ch.16 L16802 "Stop order | STOP, GTC" / "Target | LIMIT, GTC" | B: the wire block L16899 fixes stop `type=STOP` + `priceType=MARKET` and forbids `type=MARKET`, but is silent on the stop TIF and on per-leg reduceOnly | Rule applied: the specific wire block governs wire fields, the order table governs TIF, both protective legs are reduceOnly | Interim behavior: stop STOP+MARKET priceType+GTC+reduceOnly; target LIMIT+GTC+reduceOnly | Needs from owner: none.
- [ISSUE-CP7-006] severity: MINOR | status: CLOSED | A: Ch.21 §10 chart = 1200×800 px, PNG, quality 90 | B: the §14 snippet calls `savefig(dpi=150)` with a `quality=90` kwarg matplotlib's PNG writer does not accept (PNG is lossless) | Rule applied: the §10 table is normative for the artifact; the snippet is illustrative | Interim behavior: exactly 1200×800 in memory, Agg only, `quality: 90` carried in metadata, IHDR asserted | Needs from owner: none.
- [ISSUE-CP7-007] severity: MINOR | status: CLOSED | A: Ch.21 §5.1 pseudo-render header shows "UTC+3:30" | B: §5.6 mandates UTC for processing AND display; Y.3 L17437 bans local offsets from normative runtime logic | Rule applied: the normative settings law wins over an illustrative render | Interim behavior: `TIMEZONE_DISPLAY = "UTC"`, and a test asserts "UTC+3:30" never appears | Needs from owner: none.
- [ISSUE-CP7-008] severity: MINOR | status: CLOSED | A: the frozen Ch.5 DDL has `CHECK(typeof(price)='text')` / quantity / fee | B: those CHECKs reject NULL while Ch.16 events legitimately carry absent money | Rule applied: the CP-1 DDL is untouchable and NULL is not legal; encode "absent" as `''` at the store boundary | Interim behavior: `to_row()` writes `''`, `_row_to_entry()` reads it back as None | Needs from owner: decide at CP-8 triage whether the DDL should permit NULL (a CP-1-owned migration).
- [ISSUE-CP7-009] severity: MINOR | status: CLOSED | A: Ch.21 §10 caps a keyboard at 8 buttons / 4 rows | B: §5.1 shows eight domain buttons PLUS the global Back/Home controls on every screen | Rule applied: the §10 budget governs DOMAIN buttons; the two global controls form their own final row; overflow is truncated and reported (E-TELE-005 + Q2_DEGRADED), never silently dropped | Interim behavior: `render()` emits domain rows + a global row with `domain_button_count ≤ 8`, `domain_row_count ≤ 4` | Needs from owner: none.

## HOW-TO-RUN
Copy-pasteable; verified this session from the repository root. Nothing below needs a network connection or real credentials.

```bash
cd /home/user/Upstage

# 1. Environment (Python 3.11 + the nine SBOM runtime pins). pytest is dev-only:
#    it is NOT in requirements.lock and is NOT imported by any apex/** runtime module.
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.lock   # the locked SBOM, never "pip install" without it
.venv/bin/python -m pip install -e ".[tests]"          # developers only (pytest)
#    apex_gen5.egg-info/ is a build artifact: never commit it.

# 2. The nine environment names (a .env file is read through APEX_DOTENV_PATH,
#    default ".env"; the PROCESS environment always wins — no shadowing).
export APEX_ENV=PAPER                 # PAPER | LIVE | RESEARCH | BACKTEST
export APEX_ALLOW_SIGNED=1            # required for PAPER orders to reach the venue seam
export TOOBIT_API_KEY=DEMO            # never committed; env only
export TOOBIT_API_SECRET=DEMO         # HMAC-SHA256 signing secret; env only
export APEX_TELEGRAM_BOT_TOKEN=       # empty => alerts/boot report E-TELE-001 and exit 2
export APEX_OWNER_CHAT_ID=            # OWNER role; an unlisted chat id is a USER
export APEX_LEDGER_PATH=apex_ledger.sqlite3
export APEX_WATCHDOG_CHAT_ID=         # the independent HOST_DOWN channel
export APEX_DOTENV_PATH=.env

# 3. Full test suite (68 s): expect "2185 passed".
./scripts/run_all_tests.sh -q -p no:warnings
#    or, per component:
.venv/bin/python -m pytest tests/unit/test_toobit_map.py tests/unit/test_toobit_adapter.py \
    tests/unit/test_execution_fsm.py tests/unit/test_ledger_store.py \
    tests/unit/test_scheduler_clock.py tests/unit/test_telegram_signaling.py \
    tests/unit/test_telegram_control_plane.py tests/integration/test_cp7_paper_loop.py \
    -q -p no:warnings                      # expect "635 passed"

# 4. The 140-cell grid + the per-cell leverage ceiling (min over ALL caps). Exit 0.
.venv/bin/python scripts/run_apex.py grid

# 5. Boot self-check: SELF_TEST (dependencies, schema_version, clock_sync,
#    ladder_state) -> RECONCILING -> READY | DEGRADED | RECOVERY_REQUIRED.
#    Exit 0 READY, 2 DEGRADED (or refused), 3 RECOVERY_REQUIRED, 1 error.
.venv/bin/python scripts/run_apex.py boot
#    With no credentials and no reachable venue this prints DEGRADED with
#    clock_sync UNAVAILABLE and exits 2 - an unmeasurable clock is never
#    assumed synchronized, and no broker call happens before RECONCILING.

# 6. The offline PAPER loop against the in-repo fake Toobit responder:
#    READY -> ACKNOWLEDGED -> PROTECTED -> CLOSED -> OUTCOME -> RECONCILED,
#    then the reconcile agreement and the ledger chain verdict. Exit 0 in ~2.5 s.
APEX_ENV=PAPER APEX_ALLOW_SIGNED=1 TOOBIT_API_KEY=DEMO TOOBIT_API_SECRET=DEMO \
    .venv/bin/python scripts/run_apex.py demo
#    Without credentials the same command refuses and exits 2.

# 7. Alert-policy self-check (the five Ch.23 rows, the 30-minute dedup window and
#    the two dedup-exempt classes). Exit 2 without a bot token (E-TELE-001).
APEX_TELEGRAM_BOT_TOKEN= .venv/bin/python scripts/run_apex.py alerts
```

LIVE lock: nothing in CP-7 places a LIVE order. `APEX_ENV=LIVE` requires the CP-8/owner gate; the adapter refuses signed calls unless `APEX_ALLOW_SIGNED=1`, and the economic gate is binding only in LIVE. Charts: `matplotlib.use("Agg")` is set before pyplot anywhere in `apex/**`; no display call and no chart file is ever produced.

## REMAINING WORK LEDGER
none — stage fully closed. Every CP-7 RULES item and EXIT condition is met: the suite is green (2185 passed), this handoff carries the DATA-CHANGES table diffs and the whole-system HOW-TO-RUN, the MATRIX rows (Part I ×3 + Part II + Part III C7-*/X-12/X-13) are filled, the board boxes are checked, and the commits are pushed to `arena/01a09b05-upstage`. Items deliberately left to CP-8 by checkpoint scope (not CP-7 debt): the AI.10 conformance **harness runner** (CP-7 delivered the hash-locked 19-case fixture and asserts it), the watchdog process that owns the send-only Gmail module (CP-7 routes HOST_DOWN to the independent channel), the LIVE gate, and the clean-clone re-verification of the README commands.
