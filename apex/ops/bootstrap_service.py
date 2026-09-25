"""Ch.18 W.6–W.8 — the RUNNABLE first-run bootstrap service (Phase-1 long run).

`apex/research/bootstrap.py` holds the frozen protocol (hardware preflight, the
paging law, the checkpoint/resume rule, the owner command surface). This module
is the *wiring* that makes it executable on the owner's device:

    ToobitPublicClient (public klines, unsigned)
        → ToobitKlineSource   (sync page call for the frozen runner contract,
                               rate-limit −1003 surfaced as a BACKOFF, never a
                               skip)
        → BootstrapRunner     (W.6 algorithm: 140 cells, 1000-bar pages, durable
                               cursor, resume-never-rewind)
        → SQLiteStore.ingest_raw  (append-only raw store, one transaction per
                               observation, duplicate content_hash = no-op)
        → ResearchCheckpointStore (research_bootstrap_progress, M201)
        → Telegram notifier   (progress / ETA / refusal — never a fabricated
                               number; a missing token is REPORTED, never faked)

Environment gate: W.6 states "no symbol or environment gate is imposed" on
Phase 1, so this service runs in any `APEX_ENV`. It never touches the trading
path: no order, no adapter operation, no ledger write — only the raw store.

Fail-closed rules kept from the frozen stage:

* a venue bar whose OHLC is geometrically impossible (the frozen ``raw_observation``
  DDL CHECK law) is DROPPED in this wiring layer — never repaired, never clipped,
  never silently skipped past — with observable evidence (CP-12, ISSUE-CP12-001);
* a venue bar that has not yet closed at the run's end bound is NEVER served to
  the runner (CP-13 closed-bar law, ISSUE-CP13-001): the venue's tail-aligned
  klines return the currently-open candle as their last row and the frozen
  client labels every row CLOSED, so the wiring serves a walked row only when
  ``close_time_ms(open) <= end_ms`` — an excluded open bar is never counted,
  never stored, and is reported as ``open_excluded=1`` with its open_time;
* the serve decision no longer trusts the durable cursor (CP-13 cursor-trap
  fix): it serves ``open_time > store_frontier AND open_time > served_upto AND
  close_time <= end_ms``, where the frontier is MAX(as_of) read once per run —
  so a bar that was open at the previous run's end is ingested exactly once
  after it closes (no hole, no duplicate) and CURSOR_NOT_ADVANCING stays
  unreachable (``next_cursor_ms`` is always > the incoming cursor);
* a fetch failure that is NOT the venue rate-limit code stops the run with a
  named reason (the durable cursor is the resume point) — it never skips a cell;
* a page budget (`--max-pages`) stops the run *cleanly* with
  ``PAGE_BUDGET_REACHED`` and reports it as resumable, never as complete;
* the OI policy is ``oi_state=MISSING`` (the klines endpoint carries no OI
  series — the value is never invented as 0, T-DC-004/T-OM-001);
* the battery API, when absent, never triggers a skip (W.6).

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import shutil
import subprocess
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from apex.config import Config
from apex.data_catalog.contracts import CORE10_SYMBOLS, TIMEFRAMES_14
from apex.data_catalog.ingest.toobit_public import (
    ToobitPublicClient, ToobitPublicError)
from apex.research.bootstrap import (
    DEEP_START_MS, PAGE_LIMIT, BootstrapError, BootstrapRunner,
    hardware_preflight, parse_battery_json)
from apex.research.checkpoints import ResearchCheckpointStore

CONTRACT_VERSION = "4.0.0"

#: Canonical (Ch.5) status mirrors research status (ISSUE-CP9-002 / W.6).
CANONICAL_PROGRESS_STATUS: Dict[str, str] = {
    "IN_PROGRESS": "RUNNING",
    "PAUSED": "PAUSED",
    "COMPLETE": "DONE",
    "SKIPPED": "ERROR",
}

#: W.6: the venue's rate-limit business code. HTTP 429 is folded into the same
#: signal (both mean "back off, do not skip").
RATE_LIMIT_MARKERS: Tuple[str, ...] = ("-1003", "429")

#: Default bounded exponential backoff for venue −1003/429 *inside* the
#: CP-11 backward walk (never a skip, never a fabricated page).
WALK_BACKOFF_SECONDS: Tuple[float, ...] = (5.0, 15.0, 60.0)

#: Termux battery probe (W.6 names the command; a missing API never skips).
TERMUX_BATTERY_COMMAND: Tuple[str, ...] = ("termux-battery-status",)

#: CP-12 (ISSUE-CP12-001) — venue-data hygiene. The frozen ``raw_observation``
#: DDL CHECK law (``high>=max(open,close) AND low<=min(open,close) AND
#: high>=low``) is enforced at the single wiring boundary BEFORE a walked row
#: can be served to the runner (never in the frozen store, never in the frozen
#: client): Toobit's legacy Huobi-era ``1d`` candles carry geometrically
#: impossible OHLC (owner probe 2026-09-16: ``1m/5m/15m/1h/4h`` violations=0,
#: ``1d`` violations=2 of 1747 rows). Repairing/clipping a venue value is
#: fabrication (forbidden) and silently skipping violates W.6's never-skip law,
#: so the sanctioned interim behavior is DROP WITH OBSERVABLE EVIDENCE.
#:
#: Offender evidence retained per cell (symbol, timeframe, open_time_ms,
#: repr(row) truncated) — the counter itself is never capped.
INVALID_BAR_OFFENDER_RETENTION = 20
INVALID_BAR_ROW_REPR_CHARS = 160

#: Named drop reasons (observable, never a bare count).
REASON_OHLC_NOT_PARSEABLE = "OHLC_NOT_PARSEABLE"
REASON_HIGH_BELOW_MAX_OPEN_CLOSE = "HIGH_BELOW_MAX_OPEN_CLOSE"
REASON_LOW_ABOVE_MIN_OPEN_CLOSE = "LOW_ABOVE_MIN_OPEN_CLOSE"
REASON_HIGH_BELOW_LOW = "HIGH_BELOW_LOW"

#: The four fields the frozen OHLC law measures (never volume/quote/trades).
_OHLC_NAMES: Tuple[str, ...] = ("open", "high", "low", "close")


def _decimal_or_none(value: Any) -> Optional[Decimal]:
    """Tolerant numeric parse for the OHLC law only (``None`` = unparseable)."""
    if isinstance(value, Decimal):
        parsed = value
    else:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if parsed.is_nan() or parsed.is_infinite():
        return None
    return parsed


def _kline_ohlc_fields(row: Any) -> Optional[Tuple[Any, Any, Any, Any]]:
    """``(open, high, low, close)`` of a walked row, as the venue gave them.

    Understands the parsed ``MarketObservation`` (the production shape, since
    the frozen client converts before the source sees the page), a raw wire
    list ``[open_time, open, high, low, close, volume, ...]`` and a raw wire
    dict. ``None`` ⇒ the row carries no OHLC at all and is NOT judged here:
    the frozen client already fails closed on an unexpected shape, and the
    hygiene gate never invents a verdict (a verdict needs a measurement).
    """
    if isinstance(row, Mapping):
        if not any(name in row for name in _OHLC_NAMES):
            return None
        return tuple(row.get(name) for name in _OHLC_NAMES)
    if isinstance(row, (list, tuple)):
        if len(row) < 5:
            return None
        return (row[1], row[2], row[3], row[4])
    present = [name for name in _OHLC_NAMES if hasattr(row, name)]
    if not present:
        return None
    return tuple(getattr(row, name, None) for name in _OHLC_NAMES)


def _ohlc_violation(row: Any) -> Optional[str]:
    """The frozen OHLC law over one venue row; ``None`` when the row is sane.

    Only OHLC is judged — volume/quote-volume/trade-count fields are NEVER a
    drop reason (the frozen client keeps parsing them tolerantly). A row that
    is geometrically impossible is returned with the named reason so the
    caller can drop it with evidence instead of reaching the DDL CHECK.
    """
    fields = _kline_ohlc_fields(row)
    if fields is None:
        return None
    parsed = [_decimal_or_none(value) for value in fields]
    for name, value in zip(_OHLC_NAMES, parsed):
        if value is None:
            return f"{REASON_OHLC_NOT_PARSEABLE}:{name}"
    open_, high, low, close = parsed
    if high < max(open_, close):
        return REASON_HIGH_BELOW_MAX_OPEN_CLOSE
    if low > min(open_, close):
        return REASON_LOW_ABOVE_MIN_OPEN_CLOSE
    if high < low:
        return REASON_HIGH_BELOW_LOW
    return None


#: CP-13 (ISSUE-CP13-001) — fixed bar lengths in milliseconds for the
#: closed-bar law. ``1w`` is exactly 7 days. ``1mo`` is deliberately ABSENT:
#: it is the first instant of the next calendar month in UTC (variable
#: 28–31 days), never the 30-day approximation — see ``close_time_ms``.
#: ``BootstrapRunner._ms_per_bar`` is NOT used here (its ``1mo`` entry is the
#: 30-day approximation, which would misjudge month boundaries).
_CLOSE_FIXED_MS: Dict[str, int] = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000,
}


def close_time_ms(open_ms: int, timeframe: str) -> int:
    """The bar's close instant in ms (CP-13 closed-bar law, wiring layer).

    Fixed intervals add their exact length; ``1w`` adds 7 days; ``1mo`` is
    the first instant of the NEXT CALENDAR MONTH in UTC containing ``open_ms``
    (December rolls to January of the next year; February follows the real
    calendar, leap years included). ``open_ms`` need not be bar-aligned: the
    month is read from the UTC calendar date of ``open_ms`` and the close is
    the next month's ``01T00:00:00.000Z``. Unknown timeframes fail closed with
    ``BootstrapError(\"TIMEFRAME_QX\")``, matching the frozen runner's law.
    """
    tf = str(timeframe)
    if tf in _CLOSE_FIXED_MS:
        return int(open_ms) + _CLOSE_FIXED_MS[tf]
    if tf == "1mo":
        moment = dt.datetime.fromtimestamp(int(open_ms) / 1000,
                                           tz=dt.timezone.utc)
        if moment.month == 12:
            nxt = dt.datetime(moment.year + 1, 1, 1,
                              tzinfo=dt.timezone.utc)
        else:
            nxt = dt.datetime(moment.year, moment.month + 1, 1,
                              tzinfo=dt.timezone.utc)
        return int(nxt.timestamp() * 1000)
    raise BootstrapError("TIMEFRAME_QX", tf)


def latest_close_boundary(now_ms: int, timeframe: str) -> int:
    """Most recent venue boundary. Behaviour lives in the scheduler (D53)."""
    from apex.scheduler.clock import latest_close_boundary as _boundary
    return _boundary(now_ms, timeframe)


class _RateLimitSurfaced(Exception):
    """Internal: bounded walk retries exhausted → surface −1003 to the runner."""


class BootstrapServiceError(RuntimeError):
    """Fail-closed wiring error with a deterministic reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# ---------------------------------------------------------------------------
# The sync ⇄ async bridge (the frozen runner calls ``fetcher`` synchronously)
# ---------------------------------------------------------------------------

class AsyncBridge:
    """A private event-loop thread.

    The frozen ``BootstrapRunner.run_phase1`` is async but calls
    ``fetcher(...)`` **synchronously**; the venue client is async (aiohttp).
    Rather than changing the frozen runner, the async client is driven on its
    own loop thread and the page call blocks the runner thread until the page
    (or the refusal) is ready — one cell, one page, one order, by construction.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    def start(self, *, timeout: float = 10.0) -> "AsyncBridge":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._run, name="apex-async-bridge",
                                        daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise BootstrapServiceError("BRIDGE_START_TIMEOUT")
        return self

    def _run(self) -> None:                     # pragma: no cover - thread body
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    def call(self, coro: Awaitable[Any], *, timeout: float = 60.0) -> Any:
        if self._loop is None:
            raise BootstrapServiceError("BRIDGE_NOT_STARTED")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout)

    def close(self, *, timeout: float = 10.0) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout)
        self._loop = None
        self._thread = None


# ---------------------------------------------------------------------------
# The venue page source (frozen fetcher contract)
# ---------------------------------------------------------------------------

class ToobitKlineSource:
    """``fetcher(symbol, timeframe, start_ms, end_ms, limit)`` for the runner.

    Returns ``{"rows", "next_cursor_ms", "code", "oi_available"}`` exactly as
    the frozen protocol documents. ``code == -1003`` means the venue asked us to
    back off: the runner retries the same cursor and never skips the cell.

    CP-11 venue-adaptive backfill (ISSUE-CP11-001)
    ----------------------------------------------
    Toobit public klines are **tail-aligned**: for any ``[startTime, endTime]``
    window the venue returns the LAST ``limit`` bars at/before ``endTime``
    (``startTime`` ignored). A head-aligned forward page from ``DEEP_START``
    therefore lands in a dead retention window on many intervals and would
    COMPLETE the cell with zero bars under the frozen empty-page law.

    Adaptation (wiring layer only — ``research/bootstrap.py`` is frozen):

    * on the runner's **first** page call for a ``(symbol, timeframe)``, walk
      the venue **backward** from ``end_ms`` (``endTime`` stepping to
      ``oldest_open − 1``), collecting raw rows;
    * stop on any empty page, or when a page re-returns its own first row
      (dedup-guard — venue stuck on the same window);
    * then serve the runner **ascending** chunks of ``limit`` (``PAGE_LIMIT``)
      bars, filtering out any row with ``open_time < cursor`` (``start_ms``);
    * subsequent page calls keep serving the next ascending chunk from the
      walked cache; when exhausted, return the empty-page shape
      (``next_cursor_ms=end_ms``) so the frozen law completes the cell honestly;
    * ``--max-pages`` counts **runner-facing** pages only (walk traffic is free
      against the budget); ``PAGE_BUDGET_REACHED`` semantics are preserved;
    * inside the walk, ``−1003``/``429`` → bounded exponential backoff retries
      (never a skip, never a fabricated page); anything else → named
      fail-closed (``FETCH_FAILED``); the durable cursor stays valid;
    * resume: a forward cursor filters already-collected bars so they are not
      re-ingested (store ``content_hash`` dedup remains the safety net).

    CP-12 venue-data hygiene (ISSUE-CP12-001)
    -----------------------------------------
    Toobit's legacy Huobi-era ``1d`` candles carry geometrically impossible
    OHLC (owner read-only venue probe 2026-09-16, walking every interval
    backward exactly as this source does: ``1m/5m/15m/1h/4h`` violations=0,
    ``1d`` violations=2 of 1747 rows). Such a row aborts the run inside the
    frozen ``raw_observation`` DDL CHECK
    (``high>=max(open,close) AND low<=min(open,close) AND high>=low``).

    The raw store must stay venue-faithful, so repairing/clipping the values is
    fabrication (FORBIDDEN) and silently skipping the row is forbidden by W.6's
    never-skip law. The sanctioned interim behavior is therefore
    **drop-with-observable-evidence**, applied at the single boundary where a
    walked row is appended into the per-cell history (so a fresh walk and a
    cursor-filtered resume pass both pass through it):

    * OHLC must be numeric-parseable and must satisfy the frozen law above;
      volume/quote-volume/trade-count fields are NEVER a drop reason;
    * a failing row never enters the history, so it can never be served to the
      runner and can never reach the store;
    * ``invalid_dropped`` counts every drop, up to
      ``INVALID_BAR_OFFENDER_RETENTION`` offenders per cell are retained as
      ``(symbol, timeframe, open_time_ms, repr(row)[:160])``, the per-cell
      wiring print carries ``dropped=<n>`` plus the offenders summary, and the
      service status mirror carries ``invalid_bars_dropped``;
    * an all-invalid venue page drops its rows but does NOT end the walk and
      does NOT complete a cell early — the empty-page shape stays the only
      completion signal.

    DROPPING IS NOT REPAIRING: no value is altered, no row is re-ordered, and
    nothing is invented — the offender is recorded and reported instead.

    CP-13 closed-bar law + cursor-trap fix (ISSUE-CP13-001)
    -------------------------------------------------------
    The venue's tail-aligned klines return the CURRENTLY OPEN candle as their
    last row and the frozen client labels every row ``status=CLOSED``. Serving
    that snapshot stores a partial bar as an immutable CLOSED row (owner
    measurement 2026-09-16: 91 stored bars differ from the venue's final
    closed bar; every one has ``created_at`` strictly earlier than its bar
    close). The wiring therefore serves a walked row only when
    ``close_time_ms(open) <= end_ms`` (the run's end bound the runner passes
    to the fetcher). Boundary choice: the SERVE boundary in ``__call__``
    (next to the CP-12-hygienic history), NOT the CP-12 append boundary —
    because the decision is TEMPORAL (it depends on the run's ``end_ms``)
    while the history is the venue's retained series (hygiene is a permanent
    data defect, openness is a temporary timing fact). Keeping the still-open
    bar in the history (venue-faithful) and filtering at serve keeps every
    serve decision — frontier, served-upto, close — in one place, uses the
    runner's authoritative per-page ``end_ms`` rather than the walk-time end,
    and stays correct when ``end_ms`` advances within one process (the cached
    history is re-walked on demand so a newly closed bar is always fetched
    fresh — a cached open-bar snapshot is never served as closed).

    THE CURSOR TRAP: the frozen completion signal is the empty page with
    ``next_cursor_ms=end_ms`` and the runner then saves ``cursor=end_ms``. If
    the open bar were merely filtered out, the next run would receive
    ``cursor=previous_end`` and the CP-11 resume filter ``cursor <= open_time``
    would exclude the (now closed) bar whose ``open_time < previous_end``
    forever — a permanent hole — while returning ``next_cursor_ms == cursor``
    is impossible (frozen ``CURSOR_NOT_ADVANCING``). The wiring therefore no
    longer trusts the durable cursor to decide what to serve. It serves bars
    with ``open_time > store_frontier(cell) AND open_time >
    served_upto_this_process(cell) AND close_time <= end_ms``, where
    ``store_frontier`` is ``MAX(as_of)`` of ``raw_observation`` for that cell
    read ONCE by the service at the start of ``run()`` and handed over via
    ``set_frontiers`` (STRICT ``>``: a stored bar, partial or not, is never
    re-served — repairs go only through the governed ``partial_bar_repair``
    path) and ``served_upto`` is this source's own per-cell high-water mark
    of ``open_time`` served in this process (so pages within one run continue
    correctly and a ``--max-pages`` stop resumes correctly). ``next_cursor_ms``
    stays ``max(close_time_ms(last_served_open), cursor + 1)`` — i.e. the
    historical ``max(last_served_open + step, cursor)`` shape with the step
    calendar-aware for ``1mo`` (the frozen ``_ms_per_bar`` 30-day
    approximation would break the guarantee for 31-day months) and hardened
    with ``+ 1`` for the exact-equality edge — and is therefore always
    strictly greater than the incoming cursor in every branch (fresh run,
    resume after completion with a newly closed bar, resume with nothing new
    closed, budget resume), so ``CURSOR_NOT_ADVANCING`` is unreachable. The
    empty-page shape stays the only completion signal. When frontiers were
    never set (direct source use bypassing ``BootstrapService``, as in unit
    tests), the source falls back to the incoming cursor as the frontier so
    those callers keep the pre-CP-13 resume contract; production always sets
    frontiers, so the cursor is never trusted there.
    """

    def __init__(self, *, client: Optional[ToobitPublicClient] = None,
                 bridge: Optional[AsyncBridge] = None,
                 session: Any = None, max_pages: Optional[int] = None,
                 timeout_seconds: float = 60.0,
                 walk_backoff_seconds: Optional[Sequence[float]] = None
                 ) -> None:
        self._bridge = bridge
        self._max_pages = int(max_pages) if max_pages else None
        self._timeout = float(timeout_seconds)
        self._session = session
        # Default empty: first −1003 surfaces to the runner immediately
        # (CP-10 seam). Production BootstrapService injects WALK_BACKOFF_SECONDS
        # so the backward walk itself retries with bounded exponential backoff.
        if walk_backoff_seconds is None:
            self._walk_backoff = ()
        else:
            self._walk_backoff = tuple(float(x) for x in walk_backoff_seconds)
        self.pages_served = 0
        self.rate_limited = 0
        self.walk_pages = 0
        #: CP-12 — venue-data-hygiene evidence (never silent, never capped).
        self.invalid_dropped = 0
        #: Per-cell drop counts (the counter keeps counting past the cap below).
        self.invalid_by_cell: Dict[Tuple[str, str], int] = {}
        #: Per-cell named reasons → how often each one fired.
        self.invalid_reasons: Dict[Tuple[str, str], Dict[str, int]] = {}
        #: Per-cell offenders, capped at INVALID_BAR_OFFENDER_RETENTION:
        #: ``(symbol, timeframe, open_time_ms, repr(row)[:160])``.
        self.invalid_offenders: Dict[Tuple[str, str], List[Tuple[str, str, int, str]]] = {}
        #: Pending CP-12 cell-complete wiring prints (drained by the service).
        self.cell_prints: List[str] = []
        #: Runner-facing bars/pages served per cell (for the wiring print).
        self._cell_bars: Dict[Tuple[str, str], int] = {}
        self._cell_pages: Dict[Tuple[str, str], int] = {}
        #: Per-(symbol, timeframe) ascending history from the backward walk.
        self._history: Dict[Tuple[str, str], List[Any]] = {}
        #: CP-13 — ``end_ms`` each cached walk was taken from. A page call
        #: whose ``end_ms`` advances past it re-walks the venue so newly
        #: closed bars are always fetched fresh (a cached open-bar snapshot
        #: is never served as closed — see the serve-boundary note above).
        self._history_end: Dict[Tuple[str, str], int] = {}
        #: CP-13 — store frontier per cell (``MAX(as_of)`` in ms, ``None`` =
        #: no stored rows). Set once per run via ``set_frontiers``. A missing
        #: key means frontiers were never set (direct source use bypassing
        #: the service) — ``__call__`` then falls back to the cursor.
        self._frontiers: Dict[Tuple[str, str], Optional[int]] = {}
        #: CP-13 — this process's per-cell high-water mark of ``open_time``
        #: served (pages within one run + ``--max-pages`` resume).
        self._served_upto: Dict[Tuple[str, str], int] = {}
        #: CP-13 — per-cell still-open bars excluded on the latest page call
        #: (list of ``open_ms``; 0/1 in practice — bars partition time).
        self._open_excluded: Dict[Tuple[str, str], List[int]] = {}
        #: CP-13 — per-cell open-excluded counts (latest page call).
        self.open_excluded_by_cell: Dict[Tuple[str, str], int] = {}
        #: CP-13 — total open bars excluded (sum of the latest per cell).
        self.open_bars_excluded: int = 0
        if client is not None:
            self._client = client
        else:
            if self._bridge is None:
                raise BootstrapServiceError("SOURCE_NEEDS_BRIDGE_OR_CLIENT")
            self._client = ToobitPublicClient(
                session=self._build_session() if session is None else session)

    # -- construction helpers ------------------------------------------------
    def _build_session(self) -> Any:
        """A session created ON the bridge loop (aiohttp sessions are
        loop-bound). Factories are cheap; the session is reused for the run."""

        async def _factory() -> Any:
            import aiohttp
            return aiohttp.ClientSession()

        return self._bridge.call(_factory(), timeout=self._timeout)

    async def aclose(self) -> None:
        session = getattr(self._client, "_session", None)
        if session is None:
            return
        try:
            await session.close()
        except Exception:                        # pragma: no cover - teardown
            pass

    def begin_catch_up(self, symbol: str, timeframe: str,
                       frontier: Optional[int]) -> None:
        """Reset delivery state to the persisted frontier, including retries.

        A failed ingest must never turn a previously served page into a hole.
        Bootstrap's once-per-run/resume contract is unchanged.
        """
        key = (symbol, timeframe)
        self._frontiers[key] = frontier
        self._served_upto.pop(key, None)
        self._history.pop(key, None)
        self._history_end.pop(key, None)
        if not hasattr(self, "_catch_up_floor"):
            self._catch_up_floor = {}
        self._catch_up_floor[key] = frontier

    # -- CP-13 frontier handoff ----------------------------------------------
    def set_frontiers(self, frontiers: Mapping[Tuple[str, str], Optional[int]]
                      ) -> None:
        """Hand the per-cell store frontier to the source (CP-13).

        ``frontiers[(symbol, timeframe)]`` is ``MAX(as_of)`` of
        ``raw_observation`` for that cell in ms, or ``None`` when the cell
        has no stored rows. Read ONCE by ``BootstrapService.run()`` before
        ``run_phase1``. ``_served_upto`` is deliberately NOT cleared here:
        it is the within-process high-water mark that keeps a
        ``--max-pages`` stop resumable in the same process. History is NOT
        cleared either — ``__call__`` re-walks on demand when ``end_ms``
        advances past the cached walk's end (fresh venue values, never a
        stale open-bar snapshot).
        """
        self._frontiers = {tuple(key): (None if value is None else int(value))
                           for key, value in dict(frontiers).items()}

    # -- the frozen contract -------------------------------------------------
    def __call__(self, symbol: str, timeframe: str, start_ms: int, end_ms: int,
                 limit: int = PAGE_LIMIT) -> Dict[str, Any]:
        if self._max_pages is not None and self.pages_served >= self._max_pages:
            # A budget is a CLEAN stop: the durable cursor is the resume point,
            # so the run is reported resumable — never "complete".
            raise BootstrapError(
                "PAGE_BUDGET_REACHED",
                f"{self.pages_served} pages fetched (--max-pages budget)")
        key = (str(symbol), str(timeframe))
        tf_name = str(timeframe)
        try:
            cached_end = self._history_end.get(key)
            # Re-walk when the run end advances past the cached walk's end so
            # newly closed bars are fetched fresh (never a stale snapshot).
            if key not in self._history or (
                    cached_end is not None and int(end_ms) > int(cached_end)):
                self._history[key] = self._walk_backward(
                    str(symbol), tf_name, int(end_ms))
                self._history_end[key] = int(end_ms)
            elif key not in self._history_end:
                self._history_end[key] = int(end_ms)
        except _RateLimitSurfaced:
            # Bounded walk retries exhausted — same shape the runner already
            # understands: back off, retry the same cursor, never skip.
            return {"rows": [], "next_cursor_ms": None, "code": -1003,
                    "oi_available": False}
        except ToobitPublicError as exc:
            message = f"{exc}"
            if any(marker in message for marker in RATE_LIMIT_MARKERS):
                self.rate_limited += 1
                return {"rows": [], "next_cursor_ms": None, "code": -1003,
                        "oi_available": False}
            raise BootstrapError("FETCH_FAILED", message) from exc
        except BootstrapError:
            raise

        history = self._history[key]
        cursor = int(start_ms)
        end = int(end_ms)
        page_limit = int(limit) if limit else PAGE_LIMIT
        # CP-13 serve boundary (THE single closed-bar boundary — see the
        # class docstring for why serve, not the CP-12 append boundary):
        # serve ``open_time > store_frontier AND open_time > served_upto AND
        # close_time <= end_ms``. CP-12: the history itself is already
        # venue-hygienic (invalid rows never entered it), so a poisoned bar
        # can never be served to the runner. The durable cursor is NOT a
        # serve filter anymore (cursor-trap fix) — it only shapes
        # ``next_cursor_ms`` below. Fallback: when frontiers were never set
        # (direct source use bypassing the service), the cursor stands in as
        # the frontier so those callers keep the pre-CP-13 resume contract.
        if key in self._frontiers:
            frontier_ms: Optional[int] = self._frontiers[key]
        else:
            frontier_ms = cursor - 1
        served_upto = self._served_upto.get(key)
        eligible: List[Any] = []
        excluded_open_ms: List[int] = []
        for obs in history:
            open_ms = _iso_to_ms(obs.timestamp)
            if frontier_ms is not None and open_ms <= frontier_ms:
                continue
            if served_upto is not None and open_ms <= served_upto:
                continue
            if close_time_ms(open_ms, tf_name) <= end:
                eligible.append(obs)
            elif open_ms <= end:
                # Started but not yet closed at the run end — the still-open
                # bar. Future bars (open > end) are ignored, never counted.
                excluded_open_ms.append(open_ms)
        chunk = eligible[:page_limit]
        self.pages_served += 1
        self._cell_pages[key] = self._cell_pages.get(key, 0) + 1
        self._cell_bars[key] = self._cell_bars.get(key, 0) + len(chunk)
        if chunk:
            last_chunk_open = _iso_to_ms(chunk[-1].timestamp)
            prev_upto = self._served_upto.get(key)
            if prev_upto is None or last_chunk_open > prev_upto:
                self._served_upto[key] = last_chunk_open
        # Latest open-exclusion per cell (overwritten every page call; the
        # run end is constant within one run, so this is stable per run).
        self._open_excluded[key] = list(excluded_open_ms)
        self.open_excluded_by_cell[key] = len(excluded_open_ms)
        self.open_bars_excluded = sum(self.open_excluded_by_cell.values())
        if not chunk:
            # Walked history exhausted (or empty venue, or only the still-open
            # bar remains) → frozen empty-page shape so the runner completes
            # the cell honestly. This stays the ONLY completion signal: a page
            # whose rows were all invalid dropped nothing here and completes
            # no cell by itself, and an excluded open bar completes no cell
            # by itself either (it is reported, then served on a later run
            # once closed — no hole thanks to the frontier rule above).
            self._queue_cell_complete(key, str(symbol), tf_name)
            return {"rows": [], "next_cursor_ms": end, "code": None,
                    "oi_available": False}
        last_open_ms = _iso_to_ms(chunk[-1].timestamp)
        # ``next_cursor_ms`` is always STRICTLY greater than the incoming
        # cursor (frozen CURSOR_NOT_ADVANCING stays unreachable): the close
        # is calendar-aware for ``1mo`` (the frozen ``_ms_per_bar`` 30-day
        # approximation would break the guarantee for 31-day months) and the
        # ``+ 1`` hardens the exact-equality edge (close == cursor).
        close_last = close_time_ms(last_open_ms, tf_name)
        next_cursor = close_last if close_last > cursor else cursor + 1
        # oi_available is False by construction: klines carry no OI series and
        # the ingest labels the rows oi_state=MISSING (never a fabricated 0).
        return {"rows": list(chunk), "next_cursor_ms": next_cursor,
                "code": None, "oi_available": False}

    # -- CP-11 backward walk -------------------------------------------------
    def _walk_backward(self, symbol: str, timeframe: str,
                       end_ms: int) -> List[Any]:
        """Collect the venue's full available history for one cell, ascending.

        Walks ``endTime`` backward from ``end_ms``. Dedup-guarded: an empty
        page or a page whose first row repeats the previous page's first row
        ends the walk. Rate-limit errors retry with bounded exponential
        backoff inside the walk; any other venue error fails closed.

        CP-12: the walk ends at the append boundary below — every row that is
        about to become part of the per-cell history passes the frozen OHLC
        law, and a row that fails it is dropped with evidence (never served,
        never stored, never silently skipped). Dropping never ends the walk:
        the stop conditions stay the venue's own (empty page / no new row /
        no backward progress), so a fully poisoned page cannot complete a cell.
        """
        collected: Dict[int, Any] = {}
        # Every open time the venue has returned for this cell, valid or not:
        # the walk's "no new row" stop is about the VENUE repeating itself, so
        # a dropped row still counts as seen (and cannot stop the walk).
        seen_ms: Set[int] = set()
        key = (str(symbol), str(timeframe))
        walk_end = int(end_ms)
        prev_first_ms: Optional[int] = None
        # startTime is ignored by the tail-aligned venue; pass DEEP_START so a
        # head-aligned double (tests) still has a lawful lower bound.
        floor = getattr(self, "_catch_up_floor", {}).get(key)
        walk_start = int(DEEP_START_MS if floor is None else floor)

        while walk_end >= walk_start:
            page = self._get_klines_with_walk_backoff(
                symbol, timeframe, walk_start, walk_end, PAGE_LIMIT)
            self.walk_pages += 1
            if not page:
                break
            first_ms = _iso_to_ms(page[0].timestamp)
            # Dedup-stop: venue re-returned the same window (own first row).
            if prev_first_ms is not None and first_ms == prev_first_ms:
                break
            prev_first_ms = first_ms
            new_any = False
            oldest_ms = first_ms
            for obs in page:
                open_ms = _iso_to_ms(obs.timestamp)
                if open_ms < oldest_ms:
                    oldest_ms = open_ms
                if open_ms not in seen_ms:
                    seen_ms.add(open_ms)
                    new_any = True
                # -- CP-12 hygiene gate: THE single boundary into the history --
                reason = _ohlc_violation(obs)
                if reason is not None:
                    self._record_invalid_bar(key, open_ms, obs, reason)
                    continue
                if open_ms not in collected:
                    collected[open_ms] = obs
            if not new_any:
                break
            # Step endTime to just before the oldest bar of this page.
            next_end = oldest_ms - 1
            if next_end >= walk_end:
                break                            # no backward progress
            walk_end = next_end

        return [collected[k] for k in sorted(collected.keys())]

    # -- CP-12 drop evidence -------------------------------------------------
    def _record_invalid_bar(self, key: Tuple[str, str], open_ms: int,
                            row: Any, reason: str) -> None:
        """Count and retain one dropped venue bar (drops are never silent)."""
        self.invalid_dropped += 1
        self.invalid_by_cell[key] = self.invalid_by_cell.get(key, 0) + 1
        reasons = self.invalid_reasons.setdefault(key, {})
        reasons[reason] = reasons.get(reason, 0) + 1
        offenders = self.invalid_offenders.setdefault(key, [])
        if len(offenders) < INVALID_BAR_OFFENDER_RETENTION:
            offenders.append((key[0], key[1], int(open_ms),
                             repr(row)[:INVALID_BAR_ROW_REPR_CHARS]))

    def _offenders_summary(self, key: Tuple[str, str]) -> str:
        """Compact per-cell offender summary for the wiring print."""
        offenders = self.invalid_offenders.get(key) or []
        if not offenders:
            return ""
        bits = [f"{symbol}:{tf}@{open_ms}"
                for (symbol, tf, open_ms, _row_repr) in offenders[:4]]
        hidden = len(offenders) - len(bits)
        text = "; ".join(bits)
        if hidden > 0:
            text += f"; +{hidden} more"
        reasons = "; ".join(f"{name}={count}" for name, count
                            in sorted((self.invalid_reasons.get(key)
                                       or {}).items()))
        return f" offenders=[{text}] reasons=[{reasons}]"

    def _queue_cell_complete(self, key: Tuple[str, str], symbol: str,
                             timeframe: str) -> None:
        """One wiring print per completed cell, in the existing print style.

        ``dropped=<n>`` is always present; the offender evidence follows only
        when n > 0. CP-13 adds ``open_excluded=<n>`` (always present; 0/1 in
        practice) with the excluded bar's ``open_time`` when n > 0. The
        service drains these lines into its owner report.
        """
        dropped = int(self.invalid_by_cell.get(key, 0))
        open_n = int(self.open_excluded_by_cell.get(key, 0) or 0)
        # The open bar's open_time: the latest excluded list (stable per run).
        open_ms_list = self._open_excluded.get(key) or []
        line = (f"bootstrap Phase 1 cell complete: cell={symbol}:{timeframe} "
                f"pages={self._cell_pages.get(key, 0)} "
                f"bars={self._cell_bars.get(key, 0)} dropped={dropped} "
                f"open_excluded={open_n}")
        if open_n and open_ms_list:
            line += f" open_time={_ms_to_iso(int(open_ms_list[0]))}"
        if dropped:
            line += self._offenders_summary(key)
        self.cell_prints.append(line)

    def drain_cell_complete_prints(self) -> List[str]:
        """Pop the pending per-cell wiring prints (CP-12 drop evidence)."""
        if not self.cell_prints:
            return []
        lines = list(self.cell_prints)
        self.cell_prints.clear()
        return lines


    def _get_klines_with_walk_backoff(self, symbol: str, timeframe: str,
                                      start_ms: int, end_ms: int,
                                      limit: int) -> List[Any]:
        """Venue page fetch with bounded −1003/429 retries (walk-internal).

        ``walk_backoff_seconds=()`` (default) means: surface −1003 to the
        runner on the first rate-limit hit (CP-10 seam). A non-empty sequence
        is the production walk path: one initial try + one retry per slot.
        """
        backoffs = self._walk_backoff            # may be empty — do NOT coerce
        attempts = len(backoffs) + 1             # initial try + one per slot
        last_message = ""
        for attempt in range(attempts):
            try:
                return self._get_klines(symbol, timeframe, start_ms,
                                        end_ms, limit)
            except ToobitPublicError as exc:
                message = f"{exc}"
                if not any(m in message for m in RATE_LIMIT_MARKERS):
                    raise BootstrapError("FETCH_FAILED", message) from exc
                self.rate_limited += 1
                last_message = message
                if attempt >= len(backoffs):
                    break                        # no (more) walk-internal slots
                delay = float(backoffs[attempt])
                if delay > 0:
                    time.sleep(delay)
        # Bounded retries exhausted — surface −1003 to the frozen runner.
        raise _RateLimitSurfaced(last_message)

    def _get_klines(self, symbol: str, timeframe: str, start_ms: int,
                    end_ms: int, limit: int) -> List[Any]:
        if self._bridge is None:
            raise BootstrapServiceError(
                "ASYNC_CLIENT_REQUIRES_BRIDGE",
                "inject a sync client or start an AsyncBridge")
        return self._bridge.call(
            self._client.get_klines(symbol, timeframe, int(start_ms),
                                    int(end_ms), int(limit)),
            timeout=self._timeout)


def _utc_now_iso() -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _ms_to_iso(ms: int) -> str:
    """Fixed-width ISO "YYYY-MM-DDTHH:MM:SS.mmmZ" for MAX(cursor_open_time)."""
    d = dt.datetime.fromtimestamp(int(ms) / 1000, tz=dt.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"


def _iso_to_ms(timestamp: str) -> int:
    parsed = dt.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    return int(parsed.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


async def _canonical_upsert(
    store: Any,
    *,
    symbol: str,
    timeframe: str,
    phase: str,
    cursor_open_time: str,
    status: str,
    bars_written: int,
    last_error: Optional[str],
    updated_at: str,
) -> None:
    await store.db.execute(
        "INSERT INTO bootstrap_progress"
        "(symbol, timeframe, phase, cursor_open_time, status, bars_written, last_error, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(symbol, timeframe, phase) DO UPDATE SET "
        "cursor_open_time=MAX(bootstrap_progress.cursor_open_time, excluded.cursor_open_time), "
        "status=excluded.status, "
        "bars_written=bootstrap_progress.bars_written+excluded.bars_written, "
        "last_error=COALESCE(excluded.last_error, bootstrap_progress.last_error), "
        "updated_at=excluded.updated_at",
        (symbol, timeframe, phase, cursor_open_time, status, int(bars_written), last_error, updated_at),
    )
    await store.db.commit()


async def mirror_bootstrap_progress(
    store: Any,
    *,
    symbol: str,
    timeframe: str,
    phase: int,
    status: str,
    cursor_ms: int,
    bars_ingested: int = 0,
    payload: Optional[Mapping[str, Any]] = None,
) -> None:
    # phase int→'P1' per W.6 / ISSUE-CP9-002; SKIPPED→ERROR+PHASE1_VERIFICATION_SKIPPED
    canonical_status = CANONICAL_PROGRESS_STATUS.get(status, status)
    canonical_phase = "P1"
    cursor_open_time = _ms_to_iso(int(cursor_ms))
    last_error: Optional[str] = None
    if status == "SKIPPED":
        canonical_status = "ERROR"
        last_error = "PHASE1_VERIFICATION_SKIPPED"
    updated_at = _utc_now_iso()
    for attempt in range(6):
        try:
            await _canonical_upsert(
                store,
                symbol=symbol,
                timeframe=timeframe,
                phase=canonical_phase,
                cursor_open_time=cursor_open_time,
                status=canonical_status,
                bars_written=int(bars_ingested),
                last_error=last_error,
                updated_at=updated_at,
            )
            return
        except Exception as exc:
            msg = str(exc).lower()
            if "locked" in msg and attempt < 5:
                await asyncio.sleep(0.05 * (2 ** attempt))
                continue
            raise


class CanonicalMirroredCheckpoints:
    """Delegates to ResearchCheckpointStore and mirrors every save_bootstrap to the canonical table.

    None canonical → pure delegation (keeps offline status working).

    CP-13 (ISSUE-CP13-003): when a cell reaches COMPLETE, the cell's dropped
    count and reasons are merged into the checkpoint ``payload`` mapping (the
    research store already accepts and stores ``payload_json`` — read, not
    changed). ``drop_source`` is the ``ToobitKlineSource`` (or a callable
    returning it) that holds the per-cell ``invalid_by_cell`` evidence; when
    no walk happened for the cell in this process (e.g. a re-run with an
    unchanged end that never calls the fetcher), the previously persisted
    payload is preserved instead of being overwritten with zero.
    """

    def __init__(self, checkpoints: ResearchCheckpointStore, canonical_store: Any,
                 drop_source: Any = None) -> None:
        self._checkpoints = checkpoints
        self._canonical = canonical_store
        self._drop_source = drop_source

    def set_drop_source(self, source: Any) -> None:
        """Point the COMPLETE-payload merge at the live source (CP-13)."""
        self._drop_source = source

    def __getattr__(self, name: str) -> Any:
        return getattr(self._checkpoints, name)

    @property
    def db(self) -> Any:
        return self._checkpoints.db

    async def save_bootstrap(
        self,
        *,
        cell_id: str,
        symbol: str,
        timeframe: str,
        phase: int,
        status: str,
        cursor_ms: int,
        bars_ingested: int = 0,
        oi_available: bool = False,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> None:
        merged: Dict[str, Any] = dict(payload or {})
        if status == "COMPLETE":
            try:
                old_row = await self._checkpoints.load_bootstrap(cell_id)
                old_payload: Dict[str, Any] = dict(
                    (old_row or {}).get("payload") or {})
                old_dropped = int(old_payload.get("invalid_bars_dropped", 0)
                                  or 0)
                old_reasons: Dict[str, int] = dict(
                    old_payload.get("invalid_reasons", {}) or {})
                src = self._drop_source
                if callable(src):
                    try:
                        src = src()
                    except Exception:
                        src = None
                walked = False
                cur_dropped = 0
                cur_reasons: Dict[str, int] = {}
                if src is not None:
                    hist = getattr(src, "_history", None) or {}
                    walked = (str(symbol), str(timeframe)) in hist
                    if walked:
                        by_cell = getattr(src, "invalid_by_cell", None) or {}
                        cur_dropped = int(
                            by_cell.get((str(symbol), str(timeframe)), 0)
                            or 0)
                        reasons = getattr(src, "invalid_reasons", None) or {}
                        cur_reasons = dict(
                            reasons.get((str(symbol), str(timeframe)), {})
                            or {})
                if walked:
                    # The current walk saw the full retained history, so its
                    # count is authoritative — except when retention slid an
                    # old poison bar out of the window (current < old), in
                    # which case the old evidence is preserved (max).
                    if cur_dropped >= old_dropped:
                        new_dropped, new_reasons = cur_dropped, cur_reasons
                    else:
                        new_dropped, new_reasons = old_dropped, old_reasons
                else:
                    new_dropped, new_reasons = old_dropped, old_reasons
                merged = {**old_payload, **merged,
                          "invalid_bars_dropped": int(new_dropped),
                          "invalid_reasons": dict(new_reasons)}
            except Exception:
                pass                           # evidence never breaks a checkpoint
        else:
            # Non-COMPLETE saves carry previously persisted evidence keys
            # forward instead of wiping them: the frozen runner re-saves
            # IN_PROGRESS with ``payload=None`` on every re-run — even for an
            # already-complete cell, immediately before its COMPLETE save —
            # so a pass-through save would destroy the evidence the COMPLETE
            # merge is about to read back as ``old`` (same-end re-run).
            # First-run budget stops are unaffected (no old keys exist yet).
            try:
                old_row = await self._checkpoints.load_bootstrap(cell_id)
                old_payload = dict((old_row or {}).get("payload") or {})
                for key in ("invalid_bars_dropped", "invalid_reasons"):
                    if key not in merged and key in old_payload:
                        merged[key] = old_payload[key]
            except Exception:
                pass                           # evidence never breaks a checkpoint
        await self._checkpoints.save_bootstrap(
            cell_id=cell_id,
            symbol=symbol,
            timeframe=timeframe,
            phase=phase,
            status=status,
            cursor_ms=cursor_ms,
            bars_ingested=bars_ingested,
            oi_available=oi_available,
            payload=merged,
        )
        if self._canonical is None:
            return
        try:
            await mirror_bootstrap_progress(
                self._canonical,
                symbol=symbol,
                timeframe=timeframe,
                phase=phase,
                status=status,
                cursor_ms=cursor_ms,
                bars_ingested=bars_ingested,
                payload=payload,
            )
        except Exception:
            pass



# ---------------------------------------------------------------------------
# Ingest into the raw store (one transaction per observation, append-only)
# ---------------------------------------------------------------------------

async def ingest_observations(store: Any, rows: Sequence[Any], symbol: str,
                              timeframe: str, *, oi_state: str = "MISSING"
                              ) -> Dict[str, Any]:
    """``await store.ingest_raw(obs, oi_state)`` per row.

    APPEND-ONLY: the store deduplicates by ``content_hash`` (a re-run of a page
    that was already ingested is a no-op, not a duplicate row). A row that is
    not a ``MarketObservation`` is refused — the ingest hop never guesses.
    """
    if store is None:
        raise BootstrapServiceError("STORE_REQUIRED")
    for obs in rows:
        if getattr(obs, "symbol", None) != symbol or \
                getattr(obs, "timeframe", None) != timeframe:
            raise BootstrapServiceError(
                "ROW_CELL_MISMATCH",
                f"{getattr(obs, 'symbol', None)}:{getattr(obs, 'timeframe', None)} "
                f"!= {symbol}:{timeframe}")
    before = await _count_raw(store, symbol, timeframe)
    for obs in rows:
        # APPEND-ONLY + idempotent: a repeated page is de-duplicated by
        # content_hash inside the store (no update, no overwrite, no delete).
        await store.ingest_raw(obs, oi_state)
    after = await _count_raw(store, symbol, timeframe)
    inserted = max(0, after - before)
    return {"rows": len(rows), "inserted": inserted,
            "duplicates": max(0, len(rows) - inserted),
            "oi_state": oi_state, "contract_version": CONTRACT_VERSION}


async def _count_raw(store: Any, symbol: str, timeframe: str) -> int:
    cursor = await store.db.execute(
        "SELECT COUNT(*) FROM raw_observation WHERE symbol=? AND timeframe=?",
        (symbol, timeframe))
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Device probes (W.6 hardware preflight inputs)
# ---------------------------------------------------------------------------

def free_disk_mb(path: str = ".") -> float:
    usage = shutil.disk_usage(path)
    return float(usage.free) / (1024.0 * 1024.0)


def read_battery(runner: Optional[Callable[[Sequence[str]], Any]] = None
                 ) -> Optional[Dict[str, Any]]:
    """Termux ``termux-battery-status`` → the parsed mapping.

    Absent binary, non-zero exit, malformed output ⇒ ``None`` — and ``None``
    means "do not skip" (W.6), never an invented percentage.
    """
    if runner is None:
        def runner(cmd: Sequence[str]) -> Any:           # pragma: no cover - host
            return subprocess.run(list(cmd), capture_output=True, text=True,
                                  timeout=10)
    try:
        completed = runner(TERMUX_BATTERY_COMMAND)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None                                      # API absent → no skip
    text = getattr(completed, "stdout", "") or ""
    return parse_battery_json(text)


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------

class BootstrapService:
    """Owns the runner, the raw store and the checkpoint store for one run."""

    def __init__(self, *, config: Optional[Config] = None,
                 store: Any = None,
                 checkpoints: Optional[ResearchCheckpointStore] = None,
                 source: Optional[Callable[..., Mapping[str, Any]]] = None,
                 bridge: Optional[AsyncBridge] = None,
                 client: Optional[ToobitPublicClient] = None,
                 cells: Optional[Sequence[Tuple[str, str]]] = None,
                 notifier: Optional[Callable[[str], Awaitable[Any]]] = None,
                 max_pages: Optional[int] = None,
                 now: Optional[Callable[[], float]] = None,
                 db_path: Optional[str] = None,
                 checkpoint_path: Optional[str] = None) -> None:
        self.config = config or Config()
        self._store = store
        self._owns_store = store is None
        self._checkpoints = checkpoints
        self._owns_checkpoints = checkpoints is None
        self._db_path = db_path or self.config.sqlite_path
        self._checkpoint_path = checkpoint_path or self._db_path
        self._bridge = bridge
        self._owns_bridge = False
        self._client = client
        self._notifier = notifier
        self._closed = False
        self.cells: Tuple[Tuple[str, str], ...] = tuple(
            cells if cells is not None else
            [(symbol, timeframe) for symbol in CORE10_SYMBOLS
             for timeframe in TIMEFRAMES_14])
        if not self.cells:
            raise BootstrapServiceError("NO_CELLS")
        self.source = source
        self._source_factory_args = {
            "max_pages": max_pages,
            "walk_backoff_seconds": WALK_BACKOFF_SECONDS,
        }
        self.runner: Optional[BootstrapRunner] = None
        self.notifications: List[Dict[str, Any]] = []
        self._now = now
        self._catch_up_boundary: Dict[str, int] = {}

    # -- lifecycle -----------------------------------------------------------
    async def open(self) -> "BootstrapService":
        from apex.data_catalog.store import sqlite_store as ss
        if self._store is None:
            self._store = ss.SQLiteStore(self._db_path)
            await self._store.open()
        if self._checkpoints is None:
            self._checkpoints = await ResearchCheckpointStore(
                path=self._checkpoint_path).open()
        # NOTE: the venue source is created lazily (see _ensure_source) so
        # that `status`/owner commands work offline, with no HTTP session.
        # Canonical mirror per W.6 / ISSUE-CP9-002: every research checkpoint
        # is mirrored to bootstrap_progress (phase='P1', MAX cursor, SUM bars).
        # CP-13: the COMPLETE-payload merge reads the live source through a
        # callable, so the lazily created source needs no re-registration.
        if self._store is not None:
            runner_store: Any = CanonicalMirroredCheckpoints(
                self._checkpoints, self._store,
                drop_source=lambda: self.source)
        else:
            runner_store = self._checkpoints
        self.runner = BootstrapRunner(
            fetcher=self._fetch, ingest=self._ingest, store=runner_store,
            cells=self.cells, now=self._now)
        return self

    def _ensure_source(self) -> None:
        """The venue source is created LAZILY: ``status`` must work offline
        (no bridge thread, no HTTP session) — only ``run()`` needs the venue."""
        if self.source is not None:
            return
        self._bridge = self._bridge or AsyncBridge().start()
        self._owns_bridge = True
        self.source = ToobitKlineSource(client=self._client, bridge=self._bridge,
                                        **self._source_factory_args)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if isinstance(self.source, ToobitKlineSource):
            await self.source.aclose()
        if self._owns_bridge and self._bridge is not None:
            self._bridge.close()
        if self._owns_checkpoints and self._checkpoints is not None:
            await self._checkpoints.close()
        if self._owns_store and self._store is not None:
            await self._store.close()

    async def __aenter__(self) -> "BootstrapService":
        return await self.open()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # -- fetch hop -----------------------------------------------------------
    def _fetch(self, symbol: str, timeframe: str, start_ms: int, end_ms: int,
               limit: int = PAGE_LIMIT) -> Dict[str, Any]:
        """Indirection so the venue source (and its bridge/session) is created
        on the first real page — `status` never pays for it."""
        self._ensure_source()
        return self.source(symbol, timeframe, start_ms, end_ms, limit)

    # -- ingest hop ----------------------------------------------------------
    async def _ingest(self, rows: Sequence[Any], symbol: str,
                      timeframe: str) -> Dict[str, Any]:
        result = await ingest_observations(self._store, rows, symbol,
                                           timeframe)
        # CP-12: the per-cell wiring prints (with the `dropped=<n>` evidence)
        # stream out as the run progresses, next to the ingest they describe.
        await self._flush_cell_complete_prints()
        return result

    async def _flush_cell_complete_prints(self) -> None:
        """Publish every pending cell-complete wiring print (CP-12).

        A drop is never silent: the wiring layer reports the cell, the drop
        count and the retained offender evidence on the owner channel.
        """
        drain = getattr(self.source, "drain_cell_complete_prints", None)
        if drain is None:
            return
        for line in drain():
            await self.report(line, kind="CELL_COMPLETE")

    # -- reporting -----------------------------------------------------------
    async def report(self, text: str, *, kind: str = "INFO",
                     force: bool = False) -> Dict[str, Any]:
        """Publish one line to the owner. A missing notifier is a REPORTED
        refusal (never a silent drop, never a fabricated delivery)."""
        record: Dict[str, Any] = {"kind": kind, "text": text, "force": force}
        if self._notifier is None:
            record.update({"delivered": False, "reason": "NO_NOTIFIER"})
            self.notifications.append(record)
            return record
        try:
            result = await self._notifier(text)
            record.update({"delivered": True,
                           "result": _plain(result)})
        except Exception as exc:                       # fail-closed, reported
            record.update({"delivered": False,
                           "reason": f"{type(exc).__name__}: {str(exc)[:200]}"})
        self.notifications.append(record)
        return record

    # -- owner commands (W.8-2) ---------------------------------------------
    async def command(self, text: str, *, caller: str = "OWNER"
                      ) -> Dict[str, Any]:
        """Route one owner word to the frozen command surface and report it."""
        if self.runner is None:
            raise BootstrapServiceError("SERVICE_NOT_OPEN")
        try:
            verdict = self.runner.command(text)
        except BootstrapError as exc:
            verdict = {"accepted": False, "reason": exc.reason,
                       "detail": exc.detail, "command": text}
            await self.report(f"bootstrap: REFUSED {exc.reason} ({text})",
                              kind="REFUSAL")
            return {"caller": caller, **verdict}
        await self.report(_command_line(text, verdict), kind="COMMAND")
        return {"caller": caller, **verdict}

    # -- CP-13 frontier + durable-evidence helpers ------------------------------
    async def _read_frontiers(self) -> Dict[Tuple[str, str], Optional[int]]:
        """MAX(as_of) per cell in ms (None = no stored rows), read ONCE per run.

        CP-13 cursor-trap fix: the source serves ``open_time > frontier``,
        never ``open_time >= cursor``. The query reads the store this service
        already owns; a cell with no rows (or an unreadable store) reports
        ``None`` (fail-open to serve — the store's content_hash dedup stays
        the safety net against duplicates).
        """
        frontiers: Dict[Tuple[str, str], Optional[int]] = {}
        if self._store is None:
            return {cell: None for cell in self.cells}
        for symbol, timeframe in self.cells:
            try:
                cursor = await self._store.db.execute(
                    "SELECT MAX(as_of) FROM raw_observation "
                    "WHERE symbol=? AND timeframe=?",
                    (symbol, timeframe))
                row = await cursor.fetchone()
                max_asof = row[0] if row else None
                frontiers[(symbol, timeframe)] = (
                    None if max_asof is None else _iso_to_ms(str(max_asof)))
            except Exception:
                frontiers[(symbol, timeframe)] = None
        return frontiers

    async def _durable_drop_evidence(self) -> Tuple[int, Dict[str, int]]:
        """Durable drop evidence from checkpoint payloads (CP-13, offline).

        Returns ``(total, by_cell_id)`` parsed from ``payload_json``. A
        missing/unreadable store reports zero — never invented.
        """
        total = 0
        by_cell: Dict[str, int] = {}
        if self._checkpoints is None:
            return total, by_cell
        try:
            rows = await self._checkpoints.bootstrap_rows()
        except Exception:
            return total, by_cell
        for row in rows:
            try:
                raw_payload = row.get("payload_json") or "{}"
                parsed = (json.loads(raw_payload)
                          if isinstance(raw_payload, str)
                          else dict(raw_payload or {}))
                count = int(parsed.get("invalid_bars_dropped", 0) or 0)
            except Exception:
                continue
            if count:
                cell_id = str(row.get("cell_id") or "")
                by_cell[cell_id] = count
                total += count
        return total, by_cell

    async def _complete_cell_ids(self) -> Set[str]:
        """Cell ids whose durable status is COMPLETE (payload authoritative)."""
        if self._checkpoints is None:
            return set()
        try:
            rows = await self._checkpoints.bootstrap_rows()
        except Exception:
            return set()
        return {str(row.get("cell_id"))
                for row in rows if row.get("status") == "COMPLETE"}

    # -- status --------------------------------------------------------------
    async def status(self) -> Dict[str, Any]:
        if self.runner is None:
            raise BootstrapServiceError("SERVICE_NOT_OPEN")
        progress = await self.runner.progress_async()
        # CP-13 (ISSUE-CP13-003): offline-persisted drop evidence. Completed
        # cells read from the durable checkpoint payload (never re-counted
        # from the live source, so a just-completed cell is not doubled);
        # cells not yet COMPLETE read from the live source of this process
        # (their evidence is not durable yet). Offline (no source) the second
        # term is zero and the durable sum stands alone.
        durable_total, _durable_by_cell = await self._durable_drop_evidence()
        complete_ids = await self._complete_cell_ids()
        source_extra = 0
        by_cell = getattr(self.source, "invalid_by_cell", None) or {}
        for (symbol, timeframe), count in dict(by_cell).items():
            if f"{symbol}:{timeframe}" not in complete_ids:
                try:
                    source_extra += int(count or 0)
                except (TypeError, ValueError):
                    continue
        return {"cells_total": progress["cells_total"],
                "cells_completed": progress["cells_completed"],
                "cells_remaining": progress["cells_remaining"],
                "checkpointed_cells": progress["checkpointed_cells"],
                "current_cell": progress["current_cell"],
                "bars_ingested": progress["bars_ingested"],
                "pages_fetched": progress["pages_fetched"],
                "backoffs": getattr(self.runner.state, "backoffs", 0),
                # CP-12 gate total, CP-13 durable: completed cells from the
                # checkpoint payload, incomplete cells from this process.
                "invalid_bars_dropped": int(durable_total + source_extra),
                # CP-13: still-open bars excluded on the latest page per cell
                # (temporal, never persisted — offline reports 0).
                "open_bars_excluded": int(
                    getattr(self.source, "open_bars_excluded", 0) or 0),
                "percent_complete": progress["percent_complete"],
                "state": progress["state"],
                "eta": self.runner.eta(),
                "contract_version": CONTRACT_VERSION}

    # -- the long run --------------------------------------------------------
    async def run(self, *, start_ms: int = DEEP_START_MS,
                  end_ms: Optional[int] = None,
                  phase2_replay: Optional[Callable[[], Mapping[str, Any]]] = None,
                  backoff_seconds: Sequence[float] = (5.0, 15.0, 60.0),
                  announce: bool = True) -> Dict[str, Any]:
        """Execute W.6 Phase 1 for the declared cells; report and return.

        The run is RESUMABLE by construction (the cursor lives in
        ``research_bootstrap_progress``): stopping here loses nothing — deleting
        ``data/apex.sqlite3`` is the only data-loss action.
        """
        if self.runner is None:
            raise BootstrapServiceError("SERVICE_NOT_OPEN")
        self._ensure_source()
        # CP-13: the store frontier is read ONCE per run (async, before the
        # frozen runner starts paging) and handed to the source. Sources that
        # do not implement the frontier handoff (test doubles) keep their own
        # contract — the handoff is best-effort and never breaks them.
        try:
            setter = getattr(self.source, "set_frontiers", None)
            if setter is not None:
                setter(await self._read_frontiers())
        except Exception:
            pass
        battery = read_battery()
        preflight = hardware_preflight(free_disk_mb=free_disk_mb(),
                                       battery=battery,
                                       continuous=self.runner.state.continuous)
        if announce:
            await self.report(
                f"bootstrap Phase 1: {len(self.cells)} cells, "
                f"start={'2020-01-01' if start_ms == DEEP_START_MS else start_ms}, "
                f"preflight={preflight['action']} ({preflight['reason']})",
                kind="START")
        try:
            result = await self.runner.run_phase1(
                start_ms=start_ms, end_ms=end_ms, free_disk_mb=free_disk_mb(),
                battery=battery, backoff_seconds=backoff_seconds)
        except BootstrapError as exc:
            await self._flush_cell_complete_prints()
            # PAGE_BUDGET_REACHED is a CLEAN stop (durable cursor = resume point)
            if exc.reason != "PAGE_BUDGET_REACHED":
                await self.report(f"bootstrap Phase 1 STOPPED: {exc.reason} "
                                  f"({exc.detail})", kind="FAILURE")
                raise
            status = await self.status()
            result = {"phase": 1, "status": "BUDGET_REACHED",
                      "reason": exc.reason, "detail": exc.detail,
                      "resumable": True, **status}
        else:
            await self._flush_cell_complete_prints()
        result = {**result, "preflight": preflight,
                  "source_pages": getattr(self.source, "pages_served", None),
                  "rate_limited": getattr(self.source, "rate_limited", None),
                  # CP-12 evidence mirror (this run's process total; the
                  # status mirror above carries the durable total so
                  # `run_apex.py status` surfaces it offline — CP-13).
                  "invalid_bars_dropped": int(
                      getattr(self.source, "invalid_dropped", 0) or 0),
                  "invalid_offenders": _offender_rows(self.source),
                  # CP-13: still-open bars excluded on the latest page per
                  # cell (temporal, per-run — never persisted).
                  "open_bars_excluded": int(
                      getattr(self.source, "open_bars_excluded", 0) or 0),
                  "checkpoint_path": self._checkpoint_path,
                  "raw_store": self._db_path}
        if announce:
            await self.report(_summary_line(result), kind=result["status"])
        return result

    async def catch_up(self, now_ms: int) -> Dict[str, Any]:
        """D5/D22: due timeframes, fresh per-cell frontiers, isolated failures.

        The source and ingest path are the bootstrap authorities. Only a
        timeframe with all cells successful advances its boundary; otherwise
        it is retried next cycle. No repair is performed here.
        """
        result: Dict[str, Any] = {"cells_checked": 0, "cells_updated": 0,
                                  "bars_ingested": 0, "failures": []}
        for timeframe in dict.fromkeys(tf for _, tf in self.cells):
            boundary = latest_close_boundary(now_ms, timeframe)
            if boundary <= self._catch_up_boundary.get(timeframe, -1):
                continue
            successful = True
            for symbol, tf in self.cells:
                if tf != timeframe:
                    continue
                result["cells_checked"] += 1
                frontier = None
                before = None
                try:
                    row = await (await self._store.db.execute(
                        "SELECT MAX(as_of) FROM raw_observation "
                        "WHERE symbol=? AND timeframe=?", (symbol, tf))).fetchone()
                    frontier = _iso_to_ms(row[0]) if row and row[0] else None
                    before = await _count_raw(self._store, symbol, tf)
                    self._ensure_source()
                    self.source.begin_catch_up(symbol, tf, frontier)
                    cursor = frontier if frontier is not None else DEEP_START_MS
                    while True:
                        page = self.source(symbol, tf, cursor, now_ms, PAGE_LIMIT)
                        code = page.get("code")
                        if code not in (None, 0):
                            raise BootstrapServiceError(str(code))
                        rows = page["rows"]
                        if not rows:
                            await self._flush_cell_complete_prints()
                            break
                        new_hashes = set()
                        if getattr(self.config, "apex_env", "") == "PAPER":
                            for obs in rows:
                                if getattr(obs, "status", None) not in ("CLOSED", "CORRECTED"):
                                    continue
                                prior = await (await self._store.db.execute(
                                    "SELECT 1 FROM raw_observation WHERE content_hash=?",
                                    (obs.content_hash(),))).fetchone()
                                if prior is None:
                                    new_hashes.add(obs.content_hash())
                        await self._ingest(rows, symbol, tf)
                        if new_hashes:
                            import time as _time
                            from apex.ops.engine_context import publish_catch_up_quality
                            receipt = page.get("receipt_time_ms")
                            if receipt is None:
                                receipt = int(_time.time() * 1000)
                            http_status = page.get("http_status")
                            if http_status is None and page.get("code") in (None, 0):
                                http_status = 200
                            try:
                                await publish_catch_up_quality(
                                    self._store, rows, receipt_time_ms=int(receipt),
                                    http_status=http_status, only_hashes=new_hashes)
                            except Exception:
                                # A quality side-effect must not fail an ingest
                                # that already committed, and must not change
                                # the catch_up result shape pinned by D5/D22.
                                pass
                        following = int(page["next_cursor_ms"])
                        if following <= cursor:
                            raise BootstrapServiceError("CURSOR_NOT_ADVANCING")
                        cursor = following
                except Exception as exc:
                    successful = False
                    result["failures"].append({
                        "cell": f"{symbol}:{tf}", "symbol": symbol,
                        "timeframe": tf, "status": "CATCH_UP_FAILED",
                        "error_code": str(getattr(exc, "reason", type(exc).__name__)),
                        "frontier": frontier})
                finally:
                    if before is not None:
                        try:
                            after = await _count_raw(self._store, symbol, tf)
                            inserted = after - before
                            result["bars_ingested"] += inserted
                            result["cells_updated"] += int(inserted > 0)
                        except Exception as exc:
                            successful = False
                            result["failures"].append({
                                "cell": f"{symbol}:{tf}", "symbol": symbol,
                                "timeframe": tf, "status": "CATCH_UP_FAILED",
                                "error_code": str(getattr(exc, "reason", type(exc).__name__)),
                                "frontier": frontier, "phase": "ingest_accounting"})
            if successful:
                self._catch_up_boundary[timeframe] = boundary
        return result

    async def run_phase2(self, *, replay: Optional[Callable[[], Mapping[str, Any]]] = None
                         ) -> Dict[str, Any]:
        """W.6 Phase 2 — frozen-default validation (deterministic replay ×2)."""
        if self.runner is None:
            raise BootstrapServiceError("SERVICE_NOT_OPEN")
        result = await self.runner.run_phase2(replay=replay)
        await self.report(_phase2_line(result), kind=result["status"])
        return result


# ---------------------------------------------------------------------------
# Telegram notifier + message lines
# ---------------------------------------------------------------------------

class SignalingNotifier:
    """Sends owner messages through the CP-7 signaling plane (token bucket,
    idempotency registry, durable outbox). Without a bot token every send is
    refused with ``E-TELE-001`` — the refusal is propagated, never hidden."""

    def __init__(self, plane: Any, *, chat_id: str, utc_now: Callable[[], str],
                 prefix: str = "APEX bootstrap") -> None:
        self.plane = plane
        self.chat_id = chat_id
        self._utc_now = utc_now
        self.prefix = prefix
        self.seq = 0

    async def __call__(self, text: str) -> Dict[str, Any]:
        from apex.bus import Priority
        from apex.telegram.signaling import SignalMessage
        self.seq += 1
        moment = self._utc_now()
        message = SignalMessage(
            signal_id=f"bootstrap-{moment}-{self.seq}",
            chat_id=str(self.chat_id), priority=Priority.P2,
            text=f"{self.prefix}: {text}", timestamp_utc=moment,
            snapshot_id="bootstrap", alert="BOOTSTRAP_PROGRESS",
            metric="bootstrap_progress", threshold="W.6 Phase 1",
            observed=text[:60], lineage="apex.ops.bootstrap_service")
        result = await self.plane.send(message)
        return {"sent": bool(getattr(result, "sent", False)),
                "state": getattr(result, "state", None),
                "reason": getattr(result, "reason", None)}


def _command_line(text: str, verdict: Mapping[str, Any]) -> str:
    state = dict(verdict.get("state") or {})
    bits = [f"command={text}"]
    if "accepted" in verdict:
        bits.append(f"accepted={verdict['accepted']}")
    for key in ("health_recheck", "note", "cells_completed", "cells_total",
                "cells_remaining", "eta_seconds", "bars_ingested",
                "pages_fetched", "percent_complete", "current_cell"):
        if key in verdict:
            bits.append(f"{key}={verdict[key]}")
    if state:
        bits.append(f"paused={state.get('paused')} "
                    f"stopped={state.get('stopped')} "
                    f"continuous={state.get('continuous')}")
    return " ".join(str(b) for b in bits)


def _summary_line(result: Mapping[str, Any]) -> str:
    if result.get("status") == "BUDGET_REACHED":
        return (f"Phase 1 budget reached — RESUMABLE: pages="
                f"{result.get('pages_fetched')} bars="
                f"{result.get('bars_ingested')} remaining="
                f"{result.get('cells_remaining')} (re-run to continue; the "
                f"cursor is durable)")
    return (f"Phase 1 {result.get('status')}: completed="
            f"{len(result.get('completed_cells') or ())} skipped="
            f"{len(result.get('skipped_cells') or ())} pending="
            f"{len(result.get('pending_cells') or ())} pages="
            f"{result.get('pages')} backoffs={result.get('backoffs')} "
            f"bars={result.get('bars_ingested')}")


def _phase2_line(result: Mapping[str, Any]) -> str:
    return (f"Phase 2 {result.get('status')}: deterministic="
            f"{result.get('deterministic')} defaults_active="
            f"{result.get('defaults_active')}")


def _offender_rows(source: Any) -> List[List[Any]]:
    """Flatten the CP-12 per-cell offender evidence for the run report.

    Entries are exactly what the source retained: ``(symbol, timeframe,
    open_time_ms, repr(row)[:160])`` — venue values, never repaired values.
    """
    offenders = getattr(source, "invalid_offenders", None) or {}
    rows: List[List[Any]] = []
    for key in sorted(offenders.keys()):
        rows.extend([list(entry) for entry in offenders[key]])
    return rows


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "AsyncBridge", "BootstrapService", "BootstrapServiceError",
    "CONTRACT_VERSION", "CanonicalMirroredCheckpoints", "RATE_LIMIT_MARKERS",
    "SignalingNotifier", "TERMUX_BATTERY_COMMAND", "ToobitKlineSource",
    "close_time_ms", "free_disk_mb", "ingest_observations", "read_battery",
]
