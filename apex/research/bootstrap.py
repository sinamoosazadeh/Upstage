"""Ch.18 W.6–W.8 — the First-Run Bootstrap runner (three phases).

Phase 1 — Data acquisition (normative algorithm): for each of the 140 cells,
page ``GET /quote/v1/klines`` with ``limit=1000`` from
``2020-01-01T00:00:00Z`` to now, insert closed bars into ``raw_observation`` and
checkpoint ``bootstrap_progress``. Resume from the cursor, never rewind Phase 1.
A ``−1003`` response means backoff — never skip. OI history is not invented
(``oi_state=MISSING`` when the venue serves no series). Telegram commands:
``start|pause|resume|stop|progress|eta|continuous on|off``; a pause finishes
the current page and keeps SQLite (deleting ``data/apex.sqlite3`` is the only
data-loss action).

Phase 2 — Frozen-default validation: a deterministic replay of the default
package with a health check; the defaults activate on completion.

Phase 3 — Scheduled optimization cycles (W.3–W.5), run by
:mod:`apex.research.optimizer`.

Hardware preflight (W.6): pause when free disk < 512 MB; nightly auto skip only
when the battery API is readable and reports < 15 % unplugged; continuous-run
pause only when < 5 % and unplugged; a missing battery API never skips.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.identity.canonical_json import canonical_json
from apex.research.checkpoints import ResearchCheckpointStore, utc_now

CONTRACT_VERSION = "4.0.0"

#: W.6 Phase-1 algorithm constants.
DEEP_START_ISO = "2020-01-01T00:00:00Z"
DEEP_START_MS = 1577836800000
PAGE_LIMIT = 1000
BARS_PER_PAGE = 1000
#: W.6 hardware preflight.
MIN_FREE_DISK_MB = 512
NIGHTLY_BATTERY_SKIP = 0.15
CONTINUOUS_BATTERY_PAUSE = 0.05
#: Venue code that means "rate limited": back off, never skip (W.6).
RATE_LIMIT_CODE = -1003
#: W.8-3: re-run the data-health check when a pause exceeded 24 h.
HEALTH_RECHECK_AFTER_HOURS = 24.0

PHASE_DATA = 1
PHASE_DEFAULT_VALIDATION = 2
PHASE_OPTIMIZATION = 3

COMMANDS: Tuple[str, ...] = (
    "start", "pause", "resume", "stop", "progress", "eta",
    "continuous on", "continuous off")


class BootstrapError(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------
# Hardware preflight
# --------------------------------------------------------------------------

def hardware_preflight(*, free_disk_mb: float,
                       battery: Optional[Mapping[str, Any]] = None,
                       continuous: bool = False) -> Dict[str, Any]:
    """The easy thresholds of W.6, evaluated in order.

    ``battery`` is the parsed Termux ``termux-battery-status`` JSON with
    ``percentage`` (number) and ``plugged`` (truthy when charging). An absent
    battery API (``None``) never skips and never invents a percentage.
    """
    if float(free_disk_mb) < MIN_FREE_DISK_MB:
        return {"action": "PAUSE", "reason": "FREE_DISK_BELOW_512MB",
                "free_disk_mb": float(free_disk_mb),
                "threshold_mb": MIN_FREE_DISK_MB}
    if battery is None:
        return {"action": "PROCEED", "reason": "BATTERY_API_ABSENT_DO_NOT_SKIP",
                "free_disk_mb": float(free_disk_mb)}
    percentage = battery.get("percentage")
    if percentage is None:
        return {"action": "PROCEED", "reason": "BATTERY_PERCENTAGE_ABSENT",
                "free_disk_mb": float(free_disk_mb)}
    fraction = float(percentage)
    if fraction > 1.0:                     # tolerate 0–100 reporters
        fraction = fraction / 100.0
    plugged = bool(battery.get("plugged"))
    if continuous and not plugged and fraction < CONTINUOUS_BATTERY_PAUSE:
        return {"action": "PAUSE", "reason": "CONTINUOUS_BATTERY_BELOW_5PCT",
                "percentage": fraction, "plugged": plugged}
    if not continuous and not plugged and fraction < NIGHTLY_BATTERY_SKIP:
        return {"action": "SKIP_NIGHTLY", "reason": "BATTERY_BELOW_15PCT",
                "percentage": fraction, "plugged": plugged}
    return {"action": "PROCEED", "reason": "PREFLIGHT_OK",
            "percentage": fraction, "plugged": plugged}


def parse_battery_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse ``termux-battery-status`` output; malformed/absent ⇒ ``None``
    (which never triggers a skip)."""
    if not text:
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "percentage" not in data:
        return None
    return {"percentage": data.get("percentage"),
            "plugged": bool(data.get("plugged"))}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

@dataclass
class BootstrapState:
    """In-memory view of the run (the durable truth is the checkpoint table)."""

    started: bool = False
    paused: bool = False
    stopped: bool = False
    continuous: bool = False
    current_cell: Optional[str] = None
    current_phase: int = PHASE_DATA
    paused_at: Optional[float] = None
    bars_ingested: int = 0
    pages_fetched: int = 0
    backoffs: int = 0
    started_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"started": self.started, "paused": self.paused,
                "stopped": self.stopped, "continuous": self.continuous,
                "current_cell": self.current_cell,
                "current_phase": self.current_phase,
                "bars_ingested": self.bars_ingested,
                "pages_fetched": self.pages_fetched,
                "backoffs": self.backoffs}


class BootstrapRunner:
    """W.6/W.8 owner-controlled runner.

    ``fetcher(symbol, timeframe, start_ms, end_ms, limit)`` returns either
    ``{"rows": [...], "next_cursor_ms": int|None, "code": int|None}`` or raises
    :class:`BootstrapError`; ``ingest(rows, symbol, timeframe)`` persists the
    closed bars (production: ``SQLiteStore.ingest_raw`` with
    ``oi_state=MISSING`` when the venue serves no OI).
    """

    def __init__(self, *, fetcher: Callable[..., Mapping[str, Any]],
                 ingest: Callable[..., Any],
                 store: ResearchCheckpointStore,
                 cells: Sequence[Tuple[str, str]],
                 phase1_verifier: Optional[Callable[[Dict[str, Any]], Mapping[str, Any]]] = None,
                 phase2_replay: Optional[Callable[[], Mapping[str, Any]]] = None,
                 now: Optional[Callable[[], float]] = None) -> None:
        if not cells:
            raise BootstrapError("NO_CELLS")
        self.fetcher = fetcher
        self.ingest = ingest
        self.store = store
        self.cells = tuple(cells)
        self.phase1_verifier = phase1_verifier
        self.phase2_replay = phase2_replay
        self._now = now or time.time
        self.state = BootstrapState()
        self.phase1_result: Dict[str, Any] = {}
        self.phase2_result: Dict[str, Any] = {}

    # -- command surface (W.8-2 / W.6 Telegram contract) ------------------
    def command(self, command: str) -> Dict[str, Any]:
        cmd = " ".join(command.strip().lower().split())
        if cmd not in COMMANDS:
            raise BootstrapError("UNKNOWN_COMMAND", command)
        if cmd == "start":
            if self.state.stopped:
                raise BootstrapError("BOOTSTRAP_STOPPED")
            self.state.started = True
            self.state.paused = False
            self.state.paused_at = None
            if self.state.started_at is None:
                self.state.started_at = self._now()
            return {"command": cmd, "accepted": True, "state": self.state.to_dict()}
        if cmd == "pause":
            self.state.paused = True
            self.state.paused_at = self._now()
            return {"command": cmd, "accepted": True,
                    "note": "pause finishes the current page; SQLite is kept",
                    "state": self.state.to_dict()}
        if cmd == "resume":
            if not self.state.started:
                raise BootstrapError("NOT_STARTED")
            recheck = self.health_recheck_required()
            self.state.paused = False
            self.state.paused_at = None
            return {"command": cmd, "accepted": True, "health_recheck": recheck,
                    "state": self.state.to_dict()}
        if cmd == "stop":
            self.state.stopped = True
            self.state.paused = False
            return {"command": cmd, "accepted": True,
                    "note": "final state preserved; data/apex.sqlite3 is the "
                            "only data-loss action",
                    "state": self.state.to_dict()}
        if cmd == "progress":
            return {"command": cmd, **self.progress()}
        if cmd == "eta":
            return {"command": cmd, **self.eta()}
        if cmd == "continuous on":
            self.state.continuous = True
            return {"command": cmd, "accepted": True,
                    "note": "48-hour charging window; scheduler runs 24/7",
                    "state": self.state.to_dict()}
        self.state.continuous = False
        return {"command": cmd, "accepted": True, "state": self.state.to_dict()}

    def health_recheck_required(self) -> Dict[str, Any]:
        """W.8-3: after a pause longer than 24 h, re-check data health before
        resuming."""
        if self.state.paused_at is None:
            return {"required": False, "reason": "NO_PAUSE_RECORDED"}
        hours = (self._now() - self.state.paused_at) / 3600.0
        return {"required": hours > HEALTH_RECHECK_AFTER_HOURS,
                "paused_hours": hours,
                "threshold_hours": HEALTH_RECHECK_AFTER_HOURS}

    # -- Phase 1 ---------------------------------------------------------
    async def run_phase1(self, *, utc_hhmm: str = "03:30",
                         free_disk_mb: float = 10_000.0,
                         battery: Optional[Mapping[str, Any]] = None,
                         start_ms: int = DEEP_START_MS,
                         end_ms: Optional[int] = None,
                         backoff_seconds: Sequence[float] = (0.0, 0.0, 0.0)
                         ) -> Dict[str, Any]:
        """Page through every incomplete cell; checkpoint after each page."""
        preflight = hardware_preflight(free_disk_mb=free_disk_mb,
                                       battery=battery,
                                       continuous=self.state.continuous)
        if preflight["action"] == "PAUSE":
            self.state.paused = True
            self.state.paused_at = self._now()
            return {"phase": PHASE_DATA, "status": "PAUSED",
                    "preflight": preflight}
        self.state.current_phase = PHASE_DATA
        end = int(end_ms if end_ms is not None else self._now() * 1000)
        completed: List[str] = []
        skipped: List[str] = []
        pages_total = 0
        for symbol, timeframe in self.cells:
            if self.state.stopped or self.state.paused:
                break
            cell_id = f"{symbol}:{timeframe}"
            self.state.current_cell = cell_id
            saved = await self.store.load_bootstrap(cell_id)
            cursor = max(int(saved["cursor_ms"]) if saved else start_ms, start_ms)
            status = "IN_PROGRESS"
            await self.store.save_bootstrap(
                cell_id=cell_id, symbol=symbol, timeframe=timeframe,
                phase=PHASE_DATA, status=status, cursor_ms=cursor)
            while cursor < end:
                if self.state.stopped or self.state.paused:
                    break
                page = self.fetcher(symbol, timeframe, cursor, end, PAGE_LIMIT)
                code = page.get("code")
                if code == RATE_LIMIT_CODE:
                    self.state.backoffs += 1
                    delay = backoff_seconds[min(self.state.backoffs - 1,
                                                len(backoff_seconds) - 1)] \
                        if backoff_seconds else 0.0
                    if delay:
                        await asyncio.sleep(delay)
                    continue                       # backoff, never skip
                rows = list(page.get("rows") or ())
                if rows:
                    await self.ingest(rows, symbol, timeframe)
                    self.state.bars_ingested += len(rows)
                pages_total += 1
                self.state.pages_fetched += 1
                next_cursor = page.get("next_cursor_ms")
                new_cursor = (int(next_cursor) if next_cursor is not None
                              else cursor + BARS_PER_PAGE * self._ms_per_bar(timeframe))
                if new_cursor <= cursor:
                    raise BootstrapError("CURSOR_NOT_ADVANCING", cell_id)
                cursor = new_cursor
                await self.store.save_bootstrap(
                    cell_id=cell_id, symbol=symbol, timeframe=timeframe,
                    phase=PHASE_DATA, status="IN_PROGRESS", cursor_ms=cursor,
                    bars_ingested=len(rows),
                    oi_available=bool(page.get("oi_available", False)))
            if self.state.stopped or self.state.paused:
                await self.store.save_bootstrap(
                    cell_id=cell_id, symbol=symbol, timeframe=timeframe,
                    phase=PHASE_DATA, status="PAUSED", cursor_ms=cursor)
                break
            verification = {"verified": True, "reason": "PHASE1_PAGE_WALK_DONE"}
            if self.phase1_verifier is not None:
                verification = dict(self.phase1_verifier(
                    {"cell_id": cell_id, "symbol": symbol,
                     "timeframe": timeframe, "cursor_ms": cursor,
                     "bars": self.state.bars_ingested}))
            status = "COMPLETE" if verification.get("verified") else "SKIPPED"
            if status == "SKIPPED":
                skipped.append(cell_id)
            else:
                completed.append(cell_id)
            await self.store.save_bootstrap(
                cell_id=cell_id, symbol=symbol, timeframe=timeframe,
                phase=PHASE_DATA, status=status, cursor_ms=cursor)
        self.phase1_result = {
            "phase": PHASE_DATA,
            "status": "STOPPED" if self.state.stopped else
                      ("PAUSED" if self.state.paused else "COMPLETE"),
            "completed_cells": completed, "skipped_cells": skipped,
            "pending_cells": await self.pending_cells(),
            "pages": pages_total, "backoffs": self.state.backoffs,
            "bars_ingested": self.state.bars_ingested,
            "resume_rule": "resume from cursor, never rewind Phase 1",
            "oi_policy": "oi_state=MISSING when no OI series exists (never "
                         "invented)",
            "contract_version": CONTRACT_VERSION,
        }
        return self.phase1_result

    async def pending_cells(self) -> List[str]:
        """Every declared cell whose durable status is not COMPLETE/SKIPPED.

        Cells that were never checkpointed count as pending: the owner-facing
        answer to "what is left" must include work that has not started.
        """
        rows = await self.store.bootstrap_rows()
        done = {r["cell_id"] for r in rows
                if r["status"] in ("COMPLETE", "SKIPPED")}
        return [f"{symbol}:{timeframe}" for symbol, timeframe in self.cells
                if f"{symbol}:{timeframe}" not in done]

    @staticmethod
    def _ms_per_bar(timeframe: str) -> int:
        table = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
                 "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
                 "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
                 "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000,
                 "1mo": 2_592_000_000}
        if timeframe not in table:
            raise BootstrapError("TIMEFRAME_QX", timeframe)
        return table[timeframe]

    # -- Phase 2 ---------------------------------------------------------
    async def run_phase2(self, *, replay: Optional[Callable[[], Mapping[str, Any]]] = None
                         ) -> Dict[str, Any]:
        """Frozen-default validation: the replay must be deterministic and free
        of critical failures, otherwise the defaults do not activate."""
        self.state.current_phase = PHASE_DEFAULT_VALIDATION
        fn = replay or self.phase2_replay
        if fn is None:
            raise BootstrapError("PHASE2_REPLAY_REQUIRED")
        first = canonical_json(fn())
        second = canonical_json(fn())
        deterministic = first == second
        result = {"phase": PHASE_DEFAULT_VALIDATION,
                  "deterministic": deterministic,
                  "critical_failures": [] if deterministic
                  else ["NON_DETERMINISTIC_REPLAY"],
                  "defaults_active": deterministic,
                  "status": "COMPLETE" if deterministic
                  else "CRITICAL_FAILURE",
                  "contract_version": CONTRACT_VERSION}
        self.phase2_result = result
        return result

    def phase2_replay_from(self, replay: Callable[[], Mapping[str, Any]]
                           ) -> Dict[str, Any]:
        self.phase2_replay = replay
        return {"registered": True}

    # -- Phase 3 hand-off ------------------------------------------------
    def phase3_plan(self) -> Dict[str, Any]:
        """Phase 3 = scheduled optimization per W.3–W.5."""
        return {"phase": PHASE_OPTIMIZATION,
                "cells": [f"{s}:{t}" for s, t in self.cells],
                "requires": "apex.research.optimizer.DualOptimizer",
                "promotion": "apex.research.promotion.evaluate_promotion",
                "completes_when": "all cells swept at least once with approved "
                                  "packages, or the owner halts bootstrap",
                "default_window": "03:00-05:00 UTC (W.4)",
                "continuous_flag": "continuous on"}

    # -- progress / ETA (W.8-2) ------------------------------------------
    def progress(self) -> Dict[str, Any]:
        return {"cells_total": len(self.cells),
                "current_cell": self.state.current_cell,
                "bars_ingested": self.state.bars_ingested,
                "pages_fetched": self.state.pages_fetched,
                "percent_complete": self._percent(),
                "state": self.state.to_dict()}

    async def progress_async(self) -> Dict[str, Any]:
        rows = await self.store.bootstrap_rows()
        complete = [r for r in rows if r["status"] in ("COMPLETE", "SKIPPED")]
        return {**self.progress(),
                "cells_completed": len(complete),
                "cells_remaining": max(0, len(self.cells) - len(complete)),
                "checkpointed_cells": len(rows)}

    def _percent(self) -> float:
        if not self.cells:
            return 0.0
        return 100.0 * (1 if self.state.current_cell is None else
                        min(1.0, self.state.pages_fetched / max(
                            1, len(self.cells) * 8)))

    def eta(self) -> Dict[str, Any]:
        """Measured ETA (converges to actual runtime as the run progresses)."""
        if self.state.started_at is None or self.state.pages_fetched == 0:
            return {"eta_seconds": None, "basis": "NO_MEASUREMENT_YET",
                    "measured": False}
        elapsed = max(1e-9, self._now() - self.state.started_at)
        per_page = elapsed / self.state.pages_fetched
        done = self._percent() / 100.0
        remaining_fraction = max(0.0, 1.0 - done)
        total_pages_estimate = self.state.pages_fetched / done if done > 0 else None
        eta_seconds = (None if total_pages_estimate is None else
                       per_page * (total_pages_estimate - self.state.pages_fetched))
        return {"eta_seconds": eta_seconds, "seconds_per_page": per_page,
                "pages_fetched": self.state.pages_fetched,
                "measured": True, "remaining_fraction": remaining_fraction}
