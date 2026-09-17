"""Ch.18 W.6 — governed repair of partial bars stored before close (CP-13).

CP-13 (ISSUE-CP13-001): the venue's tail-aligned ``/quote/v1/klines``
returns the CURRENTLY OPEN candle as its last row, the frozen client labels
every row ``status=CLOSED`` and the pre-CP-13 wiring served it — so every
run stored a snapshot of an open bar as an immutable CLOSED row (owner
measurement 2026-09-16: 91 stored bars differ from the venue's final closed
bar; every one has ``created_at`` strictly earlier than its bar close).
Re-running bootstrap never repairs them (durable cursor already past them,
resume-never-rewind). This module is the governed repair path:

* DETECTION uses only the store: candidates are ``raw_observation`` rows
  whose ``market_observation`` ``candle_status`` is ``'CLOSED'`` (not
  SUPERSEDED, not CORRECTED) and ``created_at < close_time_ms(open) +
  SKEW_MARGIN_SECONDS`` (5 s; a candidate that turns out identical is a
  harmless no-op, so the margin only errs toward checking). Nothing else is
  ever considered.
* For each candidate the venue's closed bar is obtained FIRST LIVE via the
  frozen ``ToobitPublicClient`` (public klines, ``endTime = close_time - 1``,
  limit small; the returned row's ``open_time`` must equal the candidate's
  or it is treated as absent) and, when the venue no longer has the bar,
  from ``--evidence`` JSON files (owner read-only captures, F6) matched by
  ``(symbol, timeframe, open_time)`` and accepted only when the entry's
  ``store`` OHLCV is Decimal-equal to the row now in the database. The
  replacement is parsed with the frozen ``parse_kline_to_observation``
  (never hand-built) and judged by the CP-12 ``_ohlc_violation`` law —
  refused by name when it fails.
* Identical OHLCV → ``VERIFIED_CLOSED`` (no write); different →
  ``store.correct_raw`` (frozen correction path: original raw row immutable,
  new raw row appended, market SUPERSEDED/CORRECTED, ``raw_revision`` +
  ``retention_event`` written) with
  ``reason="PARTIAL_BAR_STORED_BEFORE_CLOSE created_at=<iso>
  close_time=<iso> replacement=VENUE_LIVE|EVIDENCE_FILE:<basename>"`` and
  ``actor="OPS_REPAIR_CP13"``; neither source available →
  ``UNREPAIRABLE_VENUE_WINDOW_PASSED`` (row untouched, listed). Never
  delete, never update in place, never invent a value.
* CLI ``scripts/run_apex.py repair-partial`` defaults to DRY-RUN (prints
  what would happen, writes nothing); ``--apply`` performs corrections.
  Idempotent: a second ``--apply`` is all VERIFIED/no-op.

B4 — direct ``raw_observation`` readers audit (two raw rows for one ``as_of``:
original immutable + correction; frozen ``raw_store_current`` view and
``max_availability_time`` filed, not changed):
* ``sqlite_store.ingest_raw`` — ``SELECT event_id WHERE content_hash=?``
  (dedup): the two rows have different content_hashes (different OHLCV), so
  no collision; unaffected.
* ``sqlite_store._find_by_event`` — ``SELECT ... WHERE event_id=?`` (by
  unique id, not ``as_of``); unaffected.
* ``sqlite_store.max_availability_time`` — ``MAX(availability_time)``: both
  rows carry ``1970-01-01`` (venue ``close_time=0``, frozen parse —
  ISSUE-CP13-002); MAX unchanged; unaffected (FROZEN, filed).
* ``sqlite_store.retention_purge`` — ``SELECT event_id WHERE as_of < ...``
  then governed delete: both rows share the same ``as_of``, so both purge
  together when they age out, each with its own ``retention_event`` row;
  lawful (both are raw rows), count grows by one per correction.
* ``sqlite_store.raw_store_current`` VIEW — ``WHERE status='CLOSED'``: BOTH
  rows appear (original and correction are both ``status='CLOSED'`` in
  ``raw_observation``; SUPERSEDED/CORRECTED live in ``market_observation``
  only), so the view shows two rows for one ``as_of``. FROZEN (filed, not
  changed). No production code queries this view (grep: defined once, read
  nowhere) — engines read via ``get_window`` (``market_observation``,
  ``CLOSED``/``CORRECTED`` only, ``SUPERSEDED`` excluded), which returns
  exactly the corrected bar.
* ``bootstrap_service._count_raw`` — ``COUNT(*) WHERE symbol/tf`` (used by
  ``ingest_observations`` for inserted/duplicates): a corrected cell counts
  +1 (original + correction). Bootstrap ingest never corrects, repair never
  ingests via this path — unaffected in practice; the frontier
  ``MAX(as_of)`` is unchanged (same ``as_of``).
* ``execution.fsm._ai9_raw_hash_chain`` — ``COUNT(*) FROM raw_observation``
  (health-check info line only): count grows by one per correction; still
  PASS (no logic depends on the exact count).
* ``get_window`` / engines / ``paper_loop`` / ``plan_bridge`` — read
  ``market_observation`` only (``CLOSED``/``CORRECTED``); the original is
  ``SUPERSEDED`` (excluded) and the correction is ``CORRECTED`` (included):
  exactly one bar per ``as_of``; unaffected (this is the designed
  correction visibility).

CP-13.1 (ISSUE-CP13-004, CONTRACT_VERSION 4.1.0): the B1 selection
(``created_at < close + skew``) has no guard that the bar has actually
closed — on the owner's 2026-09-17T04:33:03Z dry-run it selected the 20
CURRENTLY OPEN 1w/1mo bars of all ten symbols, and an ``--apply`` run would
have replaced a partial bar with another partial bar (and re-done so on
every subsequent run). The repair loop therefore takes an explicit
``now_ms`` (single wall-clock read at one place; tests inject it) and any
candidate whose ``close_ms > now_ms - SKEW_MARGIN_SECONDS*1000`` is NOT
repaired and NO live fetch is made for it: it is listed with verdict
``SKIPPED_STILL_OPEN``, ``replacement`` null and ``closes_at`` (ISO-8601 UTC
millisecond string of ``close_ms``), counted under
``skipped_still_open`` — never as unrepairable, never as refused, never
degrading the exit code.

CONTRACT_VERSION 4.1.0.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from apex.data_catalog.ingest.toobit_public import (
    ToobitPublicClient, ToobitPublicError, parse_kline_to_observation)
from apex.ops.bootstrap_service import (
    _ms_to_iso, _ohlc_violation, close_time_ms)

CONTRACT_VERSION = "4.1.0"

#: Detection skew margin (B1): a candidate that turns out identical is a
#: harmless no-op, so the margin only errs toward checking.
SKEW_MARGIN_SECONDS = 5

#: Actor recorded in raw_revision/retention_event for every CP-13 correction.
REPAIR_ACTOR = "OPS_REPAIR_CP13"

#: Verdicts (B2/B3).
VERIFIED_CLOSED = "VERIFIED_CLOSED"
CORRECTED = "CORRECTED"
UNREPAIRABLE_VENUE_WINDOW_PASSED = "UNREPAIRABLE_VENUE_WINDOW_PASSED"
REFUSED_OHLC_PREFIX = "REFUSED_OHLC_"
REFUSED_EVIDENCE_MISMATCH = "REFUSED_EVIDENCE_MISMATCH"
REFUSED_PARSE = "REFUSED_PARSE"
#: CP-13.1 (ISSUE-CP13-004) verdict: ``close_ms > now_ms - skew`` — the bar
#: has not closed yet; it is never fetched, never repaired, never counted as
#: unrepairable or refused; the report row carries ``closes_at`` so the
#: owner sees exactly when it becomes repairable.
VERDICT_SKIPPED_STILL_OPEN = "SKIPPED_STILL_OPEN"

#: LIVE fetch limit (B2: "limit small").
LIVE_FETCH_LIMIT = 5


# ---------------------------------------------------------------------------
# ISO helpers (millisecond-exact; the wiring _iso_to_ms %f path is kept for
# open_time only — created_at needs true millisecond parsing here)
# ---------------------------------------------------------------------------

def _parse_iso_ms(timestamp: str) -> int:
    """``YYYY-MM-DDTHH:MM:SS.mmmZ`` → ms since epoch (millisecond-exact)."""
    text = str(timestamp)
    if len(text) < 24 or not text.endswith("Z"):
        raise ValueError(f"bad timestamp {timestamp!r}")
    base = dt.datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=dt.timezone.utc)
    millis = int(text[20:23]) if len(text) >= 24 and text[19] == "." else 0
    return int(base.timestamp() * 1000) + millis


def _dec_or_none(value: Any) -> Optional[Decimal]:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None
    if parsed.is_nan() or parsed.is_infinite():
        return None
    return parsed


# ---------------------------------------------------------------------------
# Evidence files (F6a + F6b)
# ---------------------------------------------------------------------------

def _evidence_entries_from_f6a(data: Mapping[str, Any], basename: str
                               ) -> List[Dict[str, Any]]:
    """``store_vs_venue`` shape: top-level ``differs`` entries."""
    out: List[Dict[str, Any]] = []
    differs = data.get("differs") or []
    if not isinstance(differs, list):
        return out
    for entry in differs:
        if not isinstance(entry, Mapping):
            continue
        try:
            symbol = str(entry["symbol"])
            timeframe = str(entry["timeframe"])
            open_iso = str(entry["open_time"])
            open_ms = _parse_iso_ms(open_iso)
        except (KeyError, ValueError):
            continue
        store = entry.get("store") or {}
        venue = entry.get("venue") or {}
        raw = venue.get("raw") if isinstance(venue, Mapping) else None
        if not isinstance(store, Mapping) or raw is None:
            continue
        out.append({"symbol": symbol, "timeframe": timeframe,
                    "open_ms": open_ms, "open_iso": open_iso,
                    "store": dict(store), "venue_raw": raw,
                    "basename": basename})
    return out


def _evidence_entries_from_f6b(data: Mapping[str, Any], basename: str
                               ) -> List[Dict[str, Any]]:
    """``partial_bar_evidence`` shape: ``rows`` with venue present only for
    DIFFERS/SAME (STILL_OPEN and friends carry no venue row and are skipped).
    """
    out: List[Dict[str, Any]] = []
    rows = data.get("rows") or []
    if not isinstance(rows, list):
        return out
    for entry in rows:
        if not isinstance(entry, Mapping):
            continue
        venue = entry.get("venue")
        if not isinstance(venue, Mapping) or venue.get("raw") is None:
            continue                                  # no venue row → unusable
        try:
            symbol = str(entry["symbol"])
            timeframe = str(entry["timeframe"])
            open_ms: Optional[int] = None
            open_iso = str(entry.get("open_time") or "")
            if open_iso:
                try:
                    open_ms = _parse_iso_ms(open_iso)
                except ValueError:
                    open_ms = None
            if open_ms is None and entry.get("open_ms") is not None:
                open_ms = int(entry["open_ms"])  # type: ignore[arg-type]
            if open_ms is None:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        store = entry.get("store") or {}
        if not isinstance(store, Mapping):
            continue
        out.append({"symbol": symbol, "timeframe": timeframe,
                    "open_ms": int(open_ms), "open_iso": open_iso,
                    "store": dict(store), "venue_raw": entry["venue"]["raw"],
                    "basename": basename,
                    "verdict": str(entry.get("verdict") or "")})
    return out


def load_evidence_files(paths: Sequence[str]
                        ) -> Dict[Tuple[str, str, int], List[Dict[str, Any]]]:
    """Load ``--evidence`` JSON files into an index by ``(symbol, tf, open)``.

    Both F6 shapes are accepted (a file carrying both keys contributes both).
    Only entries with the venue row present are indexed (F6 rule). Missing
    files fail closed (``FileNotFoundError``); malformed JSON fails closed
    (``ValueError``) — evidence is never guessed.
    """
    index: Dict[Tuple[str, str, int], List[Dict[str, Any]]] = {}
    for path in list(paths or []):
        if not os.path.exists(path):
            raise FileNotFoundError(f"evidence file not found: {path}")
        with open(path, "r", encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"evidence file is not JSON: {path}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise ValueError(f"evidence file has no object root: {path}")
        basename = os.path.basename(path)
        entries = _evidence_entries_from_f6a(data, basename)
        entries += _evidence_entries_from_f6b(data, basename)
        for item in entries:
            key = (item["symbol"], item["timeframe"], int(item["open_ms"]))
            index.setdefault(key, []).append(item)
    return index


def _evidence_store_matches(entry_store: Mapping[str, Any],
                            row: Mapping[str, Any]) -> bool:
    """Decimal-equality of ``store`` OHLCV vs the row now in the database."""
    for name in ("open", "high", "low", "close", "volume"):
        want = _dec_or_none(entry_store.get(name))
        have = _dec_or_none(row.get(name))
        if want is None or have is None or want != have:
            return False
    return True


# ---------------------------------------------------------------------------
# Candidates (B1: store only)
# ---------------------------------------------------------------------------

async def find_candidates(store: Any,
                          cells: Optional[Sequence[Tuple[str, str]]] = None
                          ) -> List[Dict[str, Any]]:
    """Rows whose market status is CLOSED and ``created_at < close + skew``.

    ``cells`` optionally restricts to ``[(symbol, timeframe), ...]`` (the
    CLI ``--cells`` filter). Every returned row carries the raw values plus
    ``open_ms`` / ``close_ms`` / ``created_at_ms`` for the repair step.
    """
    wanted = {(str(s), str(t)) for s, t in (cells or [])} if cells else None
    cursor = await store.db.execute(
        "SELECT r.event_id, r.as_of, r.symbol, r.timeframe, r.open, r.high, "
        " r.low, r.close, r.volume, r.created_at, m.candle_status "
        "FROM raw_observation r "
        "JOIN market_observation m "
        "ON m.observation_id = 'obs-' || r.event_id "
        "WHERE m.candle_status = 'CLOSED'")
    rows = await cursor.fetchall()
    out: List[Dict[str, Any]] = []
    for (event_id, as_of, symbol, timeframe, o, h, l, c, v, created_at,
         _status) in rows:
        if wanted is not None and (str(symbol), str(timeframe)) not in wanted:
            continue
        try:
            open_ms = _parse_iso_ms(str(as_of))
            created_ms = _parse_iso_ms(str(created_at))
            close_ms = close_time_ms(open_ms, str(timeframe))
        except (ValueError, RuntimeError):
            continue                                # unparseable → not a candidate
        if created_ms < close_ms + SKEW_MARGIN_SECONDS * 1000:
            out.append({"event_id": str(event_id), "as_of": str(as_of),
                        "symbol": str(symbol), "timeframe": str(timeframe),
                        "open": str(o), "high": str(h), "low": str(l),
                        "close": str(c), "volume": str(v),
                        "created_at": str(created_at),
                        "open_ms": int(open_ms), "close_ms": int(close_ms),
                        "created_at_ms": int(created_ms)})
    out.sort(key=lambda item: (item["symbol"], item["timeframe"],
                               item["open_ms"]))
    return out


# ---------------------------------------------------------------------------
# LIVE fetch (B2: frozen client, endTime = close - 1)
# ---------------------------------------------------------------------------

async def fetch_live_bar(client: Any, symbol: str, timeframe: str,
                         open_ms: int, close_ms: int) -> Optional[Any]:
    """The venue's closed bar for ``open_ms`` or ``None`` when absent.

    ``endTime = close_time - 1`` keeps the wanted bar the newest row at or
    before the bound (the next bar opens exactly at ``close_time``). Any
    venue failure — window passed, rate-limit exhausted, network error — is
    ``None`` (the caller falls back to evidence, then UNREPAIRABLE).
    """
    try:
        rows = await client.get_klines(str(symbol), str(timeframe),
                                       int(open_ms), int(close_ms) - 1,
                                       LIVE_FETCH_LIMIT)
    except (ToobitPublicError, Exception):
        return None
    for obs in list(rows or []):
        try:
            if _parse_iso_ms(str(getattr(obs, "timestamp"))) == int(open_ms):
                return obs
        except (ValueError, TypeError, AttributeError):
            continue
    return None


# ---------------------------------------------------------------------------
# One candidate → verdict (+ optional correction)
# ---------------------------------------------------------------------------

def _ohlcv_equal(left: Mapping[str, Any], right_obs: Any) -> bool:
    for name in ("open", "high", "low", "close", "volume"):
        left_dec = _dec_or_none(left.get(name))
        right_dec = _dec_or_none(getattr(right_obs, name, None))
        if left_dec is None or right_dec is None or left_dec != right_dec:
            return False
    return True


async def repair_one(store: Any, candidate: Mapping[str, Any], *,
                     client: Any,
                     evidence: Mapping[Tuple[str, str, int],
                                       List[Dict[str, Any]]],
                     apply: bool) -> Dict[str, Any]:
    """Repair (or dry-run) one candidate; never raises for data reasons.

    Returns the report row: ``symbol/tf/open_time/created_at/verdict`` plus
    ``store_close/store_volume`` vs ``repl_close/repl_volume`` and the
    ``replacement`` source (``VENUE_LIVE`` / ``EVIDENCE_FILE:<basename>`` /
    ``None``). Data refusals are verdicts, not exceptions; only store I/O
    failures propagate (fail-closed, nothing half-written).
    """
    symbol = str(candidate["symbol"])
    timeframe = str(candidate["timeframe"])
    open_ms = int(candidate["open_ms"])
    close_ms = int(candidate["close_ms"])
    base: Dict[str, Any] = {
        "symbol": symbol, "timeframe": timeframe,
        "open_time": str(candidate["as_of"]),
        "created_at": str(candidate["created_at"]),
        "store_close": str(candidate["close"]),
        "store_volume": str(candidate["volume"]),
        "repl_close": None, "repl_volume": None, "replacement": None,
    }
    replacement = None
    source_name: Optional[str] = None
    # 1. LIVE first.
    live = await fetch_live_bar(client, symbol, timeframe, open_ms, close_ms)
    if live is not None:
        replacement, source_name = live, "VENUE_LIVE"
    else:
        # 2. Evidence fallback (store values must prove equal first).
        key = (symbol, timeframe, open_ms)
        entries = list((evidence or {}).get(key) or [])
        matched: Optional[Dict[str, Any]] = None
        for item in entries:
            if _evidence_store_matches(item.get("store") or {}, candidate):
                matched = item
                break
        if matched is not None:
            try:
                parsed = parse_kline_to_observation(
                    symbol, timeframe, matched["venue_raw"], 0)
            except (ToobitPublicError, Exception) as exc:
                return {**base, "verdict": REFUSED_PARSE,
                        "detail": f"{type(exc).__name__}: {str(exc)[:160]}"}
            try:
                if _parse_iso_ms(str(parsed.timestamp)) != open_ms:
                    return {**base, "verdict": REFUSED_EVIDENCE_MISMATCH,
                            "detail": "venue raw open_time != candidate"}
            except (ValueError, TypeError):
                return {**base, "verdict": REFUSED_EVIDENCE_MISMATCH,
                        "detail": "venue raw open_time unparseable"}
            replacement = parsed
            source_name = f"EVIDENCE_FILE:{matched['basename']}"
        elif entries:
            return {**base, "verdict": REFUSED_EVIDENCE_MISMATCH,
                    "detail": f"{len(entries)} evidence entr(ies), store "
                              "OHLCV differs from the database row"}
    if replacement is None:
        return {**base, "verdict": UNREPAIRABLE_VENUE_WINDOW_PASSED,
                "detail": "venue window passed and no evidence entry"}
    base.update({"repl_close": str(getattr(replacement, "close")),
                 "repl_volume": str(getattr(replacement, "volume")),
                 "replacement": source_name})
    # 3. The CP-12 law judges the replacement (never the stored row).
    violation = _ohlc_violation(replacement)
    if violation is not None:
        return {**base, "verdict": f"{REFUSED_OHLC_PREFIX}{violation}",
                "detail": "replacement violates the frozen OHLC law"}
    # 4. Identical → verified (no write either way).
    if _ohlcv_equal(candidate, replacement):
        return {**base, "verdict": VERIFIED_CLOSED,
                "detail": "identical to the venue's closed bar"}
    # 5. Different → correct (or would-correct in dry-run).
    if not apply:
        return {**base, "verdict": CORRECTED, "dry_run": True,
                "detail": "would correct (dry-run, nothing written)"}
    reason = ("PARTIAL_BAR_STORED_BEFORE_CLOSE "
              f"created_at={candidate['created_at']} "
              f"close_time={_ms_to_iso(close_ms)} "
              f"replacement={source_name}")
    await store.correct_raw(str(candidate["event_id"]), replacement,
                            "MISSING", reason, actor=REPAIR_ACTOR)
    return {**base, "verdict": CORRECTED,
            "detail": f"corrected via {source_name}"}


# ---------------------------------------------------------------------------
# Whole-store run (B3)
# ---------------------------------------------------------------------------

async def run_repair(store: Any, *, client: Any,
                     evidence_paths: Sequence[str] = (),
                     apply: bool = False,
                     cells: Optional[Sequence[Tuple[str, str]]] = None,
                     now_ms: Optional[int] = None
                     ) -> Dict[str, Any]:
    """Find every candidate and repair (or dry-run) it, in open_time order.

    Returns ``{"candidates": [...rows...], "counts": {...}, "apply": ...}``
    with ``counts = {candidates, verified, corrected, unrepairable,
    refused}`` plus ``skipped_still_open`` when any candidate is skipped
    still-open (CP-13.1). ``refused`` groups every ``REFUSED_*``
    verdict. ``now_ms`` (int, UTC epoch milliseconds) is the one and only
    wall-clock read of the repair path: ``None`` resolves to
    ``int(time.time() * 1000)`` here, tests inject it, and no other
    production line reads the clock. A candidate whose bar has not closed by
    ``now_ms - SKEW_MARGIN_SECONDS*1000`` (CP-13.1 / ISSUE-CP13-004) is NOT
    repaired and NO live fetch is made for it — it is listed with verdict
    ``SKIPPED_STILL_OPEN``, ``replacement`` null and ``closes_at`` (the
    ISO-8601 UTC millisecond string of ``close_ms``) and counted under
    ``skipped_still_open`` only. Writes happen only when ``apply`` is true
    (one frozen ``correct_raw`` per corrected row); dry-run writes nothing.
    """
    if now_ms is None:
        now_ms = int(time.time() * 1000)      # the single wall-clock read
    evidence = load_evidence_files(evidence_paths or [])
    found = await find_candidates(store, cells)
    rows: List[Dict[str, Any]] = []
    for candidate in found:
        if int(candidate["close_ms"]) > (int(now_ms)
                                         - SKEW_MARGIN_SECONDS * 1000):
            # CP-13.1 (ISSUE-CP13-004): still open — never fetched, never
            # repaired; listed with closes_at so the owner sees exactly
            # which bars become repairable later, and when.
            rows.append({"symbol": str(candidate["symbol"]),
                         "timeframe": str(candidate["timeframe"]),
                         "open_time": str(candidate["as_of"]),
                         "created_at": str(candidate["created_at"]),
                         "store_close": str(candidate["close"]),
                         "store_volume": str(candidate["volume"]),
                         "repl_close": None, "repl_volume": None,
                         "replacement": None,
                         "closes_at": _ms_to_iso(int(candidate["close_ms"])),
                         "verdict": VERDICT_SKIPPED_STILL_OPEN,
                         "detail": ("bar still open at now_ms; repairable "
                                    "from closes_at + skew onward")})
            continue
        rows.append(await repair_one(store, candidate, client=client,
                                    evidence=evidence, apply=apply))
    counts = {"candidates": len(rows),
              "verified": sum(1 for r in rows
                              if r["verdict"] == VERIFIED_CLOSED),
              "corrected": sum(1 for r in rows
                               if r["verdict"] == CORRECTED),
              "unrepairable": sum(1 for r in rows if r["verdict"] ==
                                   UNREPAIRABLE_VENUE_WINDOW_PASSED),
              "refused": sum(1 for r in rows
                             if str(r["verdict"]).startswith("REFUSED"))}
    skipped = sum(1 for r in rows
                  if r["verdict"] == VERDICT_SKIPPED_STILL_OPEN)
    if skipped:
        # Additive bucket (CP-13.1): present whenever at least one candidate
        # is still open; the printed summary always shows the metric.
        counts["skipped_still_open"] = skipped
    return {"candidates": rows, "counts": counts, "apply": bool(apply),
            "evidence_files": [os.path.basename(p)
                               for p in list(evidence_paths or [])],
            "contract_version": CONTRACT_VERSION}


def report_filename(now_utc: Optional[dt.datetime] = None) -> str:
    """``repair_partial_report_<UTC ts>.json`` leaf name (B3)."""
    moment = now_utc or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    stamp = moment.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"repair_partial_report_{stamp}.json"


__all__ = [
    "CONTRACT_VERSION", "CORRECTED", "LIVE_FETCH_LIMIT",
    "REFUSED_EVIDENCE_MISMATCH", "REFUSED_OHLC_PREFIX", "REFUSED_PARSE",
    "REPAIR_ACTOR", "SKEW_MARGIN_SECONDS",
    "UNREPAIRABLE_VENUE_WINDOW_PASSED", "VERDICT_SKIPPED_STILL_OPEN",
    "VERIFIED_CLOSED",
    "fetch_live_bar", "find_candidates", "load_evidence_files",
    "repair_one", "report_filename", "run_repair",
]
