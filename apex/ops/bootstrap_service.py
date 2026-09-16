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
        try:
            if key not in self._history:
                self._history[key] = self._walk_backward(
                    str(symbol), str(timeframe), int(end_ms))
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
        # Ascending serve: drop anything already behind the durable cursor
        # (resume speed-net) and anything at/after the run end bound. CP-12:
        # the history itself is already venue-hygienic (invalid rows never
        # entered it), so a poisoned bar can never be served to the runner.
        eligible = [
            obs for obs in history
            if cursor <= _iso_to_ms(obs.timestamp) < end
        ]
        chunk = eligible[:page_limit]
        self.pages_served += 1
        self._cell_pages[key] = self._cell_pages.get(key, 0) + 1
        self._cell_bars[key] = self._cell_bars.get(key, 0) + len(chunk)
        if not chunk:
            # Walked history exhausted (or empty venue) → frozen empty-page
            # shape so the runner completes the cell honestly. This stays the
            # ONLY completion signal: a page whose rows were all invalid
            # dropped nothing here and completes no cell by itself.
            self._queue_cell_complete(key, str(symbol), str(timeframe))
            return {"rows": [], "next_cursor_ms": end, "code": None,
                    "oi_available": False}
        last_open_ms = _iso_to_ms(chunk[-1].timestamp)
        step = BootstrapRunner._ms_per_bar(timeframe)
        next_cursor = max(last_open_ms + step, cursor)
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
        walk_start = int(DEEP_START_MS)

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
        when n > 0. The service drains these lines into its owner report.
        """
        dropped = int(self.invalid_by_cell.get(key, 0))
        line = (f"bootstrap Phase 1 cell complete: cell={symbol}:{timeframe} "
                f"pages={self._cell_pages.get(key, 0)} "
                f"bars={self._cell_bars.get(key, 0)} dropped={dropped}")
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
    """

    def __init__(self, checkpoints: ResearchCheckpointStore, canonical_store: Any) -> None:
        self._checkpoints = checkpoints
        self._canonical = canonical_store

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
        await self._checkpoints.save_bootstrap(
            cell_id=cell_id,
            symbol=symbol,
            timeframe=timeframe,
            phase=phase,
            status=status,
            cursor_ms=cursor_ms,
            bars_ingested=bars_ingested,
            oi_available=oi_available,
            payload=payload,
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
        if self._store is not None:
            runner_store: Any = CanonicalMirroredCheckpoints(self._checkpoints, self._store)
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

    # -- status --------------------------------------------------------------
    async def status(self) -> Dict[str, Any]:
        if self.runner is None:
            raise BootstrapServiceError("SERVICE_NOT_OPEN")
        progress = await self.runner.progress_async()
        return {"cells_total": progress["cells_total"],
                "cells_completed": progress["cells_completed"],
                "cells_remaining": progress["cells_remaining"],
                "checkpointed_cells": progress["checkpointed_cells"],
                "current_cell": progress["current_cell"],
                "bars_ingested": progress["bars_ingested"],
                "pages_fetched": progress["pages_fetched"],
                "backoffs": getattr(self.runner.state, "backoffs", 0),
                # CP-12 (ISSUE-CP12-001): venue bars dropped by the hygiene
                # gate. Offline (no source yet) reports 0 — never invented.
                "invalid_bars_dropped": int(
                    getattr(self.source, "invalid_dropped", 0) or 0),
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
                  # CP-12 evidence mirror (the status mirror above carries the
                  # same total so `run_apex.py status` surfaces it offline).
                  "invalid_bars_dropped": int(
                      getattr(self.source, "invalid_dropped", 0) or 0),
                  "invalid_offenders": _offender_rows(self.source),
                  "checkpoint_path": self._checkpoint_path,
                  "raw_store": self._db_path}
        if announce:
            await self.report(_summary_line(result), kind=result["status"])
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
    "AsyncBridge", "BootstrapService", "BootstrapServiceError", "CONTRACT_VERSION",
    "RATE_LIMIT_MARKERS", "SignalingNotifier", "TERMUX_BATTERY_COMMAND",
    "ToobitKlineSource", "free_disk_mb", "ingest_observations", "read_battery",
]
