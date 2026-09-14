"""Ch.18 W.1–W.4 + W.8 — the dual optimizer.

W.1  two optimizers with **disjoint** parameter scopes: the Signal Optimizer
     owns data→signal parameters, the Risk Optimizer owns post-signal
     (sizing/stop/target/trailing/BE/time-stop/cooldown/staged-TP) parameters;
     no parameter belongs to both.
W.2  the two objective functions, with their normative constraints.
W.3  combination generation is a **full exhaustive Cartesian grid** (owner
     decision D3); a budgeted random search with local refinement is legal only
     when the owner explicitly authorizes it — never as a silent default.
W.4  per-cell isolation, the default low-load window 03:00–05:00 UTC
     (owner-configurable, read from ``params/universe_v1.yaml``), the
     immediate halt when a live workload is detected, and the owner-enabled
     continuous-run mode.
W.8  persistent checkpoints (``apex.research.checkpoints``) so a killed run
     resumes at the next uncompleted cell.

Every output of this module is a **suggestion file** under
``apex/research/params_suggestions/``. Writing a live ``params/*.yaml`` raises
:class:`apex.research.governance.ResearchRedLineError` (W.5 / G6).

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.config import load_params
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.research.checkpoints import CheckpointError, ResearchCheckpointStore
from apex.research.governance import (LIVE_PARAMS_DIR, SUGGESTIONS_DIR,
                                      ParameterPackage,
                                      ResearchRedLineError,
                                      assert_live_params_untouched,
                                      validate_package)
from apex.research.proxies import REPO_ROOT

CONTRACT_VERSION = "4.0.0"

SIGNAL_OPTIMIZER = "SIGNAL"
RISK_OPTIMIZER = "RISK"

#: W.1 — the Signal Optimizer's exclusive scope.
SIGNAL_SCOPE: Tuple[str, ...] = (
    "engine_thresholds", "setup_scoring_weights", "gate_thresholds")

#: W.1 — the Risk Optimizer's exclusive scope.
RISK_SCOPE: Tuple[str, ...] = (
    "position_size", "effective_leverage", "stop_distance", "target_distance",
    "trailing_distance", "breakeven_distance", "time_stop_distance", "cooldown",
    "staged_tp_ratios")

#: W.2 — signal-objective constraints.
SIGNAL_MIN_TRADES_PER_WINDOW = 100
SIGNAL_REQUIRES_BENCHMARK = True
#: W.2 — risk-objective constraints.
RISK_LEVERAGE_ADHERENCE = 1.0

#: W.3 — "domain sizes smaller than approximately 500 states" ⇒ full grid; the
#: owner must authorize any random search explicitly.
FULL_GRID_THRESHOLD = 500
#: Default low-load window (W.4) — overridden by the frozen YAML when present.
DEFAULT_WINDOW_UTC = ("03:00", "05:00")
CONTINUOUS_RUN_OWNER_FLAG = "continuous on"


class OptimizerError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def assert_scopes_disjoint() -> Dict[str, Any]:
    """W.1 disjointness proof (a shared parameter would explode the search)."""
    overlap = sorted(set(SIGNAL_SCOPE) & set(RISK_SCOPE))
    if overlap:
        raise OptimizerError("OPTIMIZER_SCOPE_OVERLAP", ",".join(overlap))
    return {"signal_scope": list(SIGNAL_SCOPE), "risk_scope": list(RISK_SCOPE),
            "overlap": overlap, "disjoint": True}


# --------------------------------------------------------------------------
# W.3 — grids
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ParameterRange:
    """One logical range with its discrete step (W.3)."""

    name: str
    minimum: float
    maximum: float
    step: float

    def __post_init__(self) -> None:
        if self.step <= 0.0:
            raise OptimizerError("STEP_QX", self.name)
        if self.maximum < self.minimum:
            raise OptimizerError("RANGE_INVERTED", self.name)

    def states(self) -> List[float]:
        n = int(math.floor((self.maximum - self.minimum) / self.step + 1e-9)) + 1
        return [round(self.minimum + i * self.step, 12) for i in range(n)]

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "min": self.minimum, "max": self.maximum,
                "step": self.step, "states": len(self.states())}


class ParameterGrid:
    """The Cartesian product of per-parameter ranges (W.3 "no state removed")."""

    def __init__(self, ranges: Sequence[ParameterRange]) -> None:
        if not ranges:
            raise OptimizerError("EMPTY_GRID")
        names = [r.name for r in ranges]
        if len(set(names)) != len(names):
            raise OptimizerError("DUPLICATE_RANGE", ",".join(names))
        self.ranges: Tuple[ParameterRange, ...] = tuple(ranges)

    @property
    def size(self) -> int:
        total = 1
        for r in self.ranges:
            total *= len(r.states())
        return total

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(r.name for r in self.ranges)

    def states(self) -> Dict[str, List[float]]:
        return {r.name: r.states() for r in self.ranges}

    def enumerate(self) -> List[Dict[str, float]]:
        keys = self.names
        return [dict(zip(keys, combo))
                for combo in itertools.product(*(r.states() for r in self.ranges))]

    def random_search(self, *, budget: int, seed: int,
                      owner_authorized: bool) -> List[Dict[str, float]]:
        """W.3: budgeted random search is legal ONLY on explicit owner order."""
        if not owner_authorized:
            raise OptimizerError(
                "OWNER_AUTHORIZATION_REQUIRED_D3",
                "full exhaustive grid is the default (owner decision D3)")
        if budget <= 0:
            raise OptimizerError("BUDGET_QX")
        states = self.states()
        keys = self.names
        state = int(seed) & 0xFFFFFFFFFFFFFFFF
        out: List[Dict[str, float]] = []
        for _ in range(budget):
            combo: Dict[str, float] = {}
            for key in keys:
                state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
                z = state
                z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
                z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
                z ^= z >> 31
                pool = states[key]
                combo[key] = pool[z % len(pool)]
            out.append(combo)
        return out

    def generate(self, *, owner_authorized_random: bool = False,
                 budget: Optional[int] = None, seed: int = 0
                 ) -> List[Dict[str, float]]:
        """W.3 decision path: full grid by default, budgeted random only by
        explicit owner authorization *and* only for domains above the
        threshold."""
        if owner_authorized_random and self.size > FULL_GRID_THRESHOLD:
            return self.random_search(budget=int(budget or FULL_GRID_THRESHOLD),
                                      seed=seed, owner_authorized=True)
        return self.enumerate()

    def to_dict(self) -> Dict[str, Any]:
        return {"parameters": [r.to_dict() for r in self.ranges],
                "size": self.size,
                "mode": "FULL_GRID" if self.size <= FULL_GRID_THRESHOLD
                        else "FULL_GRID_LARGE",
                "contract_version": CONTRACT_VERSION}


# --------------------------------------------------------------------------
# W.2 — objectives
# --------------------------------------------------------------------------

def signal_objective(*, deflated_sharpe: float, trades: int,
                     net_return: float, btc_buy_and_hold: float,
                     calibration_error: float, staleness_threshold: float
                     ) -> Dict[str, Any]:
    """W.2 signal objective + its three constraints."""
    constraints = {
        "min_trades_per_window": trades >= SIGNAL_MIN_TRADES_PER_WINDOW,
        "beats_buy_and_hold": net_return > btc_buy_and_hold,
        "calibration_fresh": calibration_error <= staleness_threshold,
    }
    return {"value": float(deflated_sharpe) if all(constraints.values())
            else float("-inf"),
            "objective": "cost_adjusted_deflated_sharpe",
            "constraints": constraints,
            "feasible": all(constraints.values()),
            "trades": trades}


def risk_objective(*, expected_net_r: float, max_drawdown: float,
                   drawdown_limit: float, leverage_adherence: float,
                   per_regime_stability: Mapping[str, float]
                   ) -> Dict[str, Any]:
    """W.2 risk objective: expected net value in R subject to the owner's
    drawdown limit, 100 % leverage/capital adherence and the per-regime
    stability report (all five volatility regimes, reported separately)."""
    required_regimes = ("LOW", "NORMAL", "HIGH", "EXTREME", "CRISIS")
    missing = [r for r in required_regimes if r not in per_regime_stability]
    constraints = {
        "drawdown_within_limit": float(max_drawdown) <= float(drawdown_limit),
        "leverage_adherence_full": math.isclose(float(leverage_adherence),
                                                RISK_LEVERAGE_ADHERENCE,
                                                rel_tol=0.0, abs_tol=1e-12),
        "regimes_reported": not missing,
    }
    return {"value": float(expected_net_r) if all(constraints.values())
            else float("-inf"),
            "objective": "expected_net_value_in_R",
            "constraints": constraints, "feasible": all(constraints.values()),
            "missing_regimes": missing,
            "per_regime_stability": dict(per_regime_stability)}


# --------------------------------------------------------------------------
# W.4 — schedule and live-workload guard
# --------------------------------------------------------------------------

def nightly_window() -> Tuple[str, str]:
    """The default low-load window, read from the frozen universe YAML."""
    universe = load_params().universe()
    window = universe.get("nightly_window_utc") or {}
    start = str(window.get("start", DEFAULT_WINDOW_UTC[0]))
    end = str(window.get("end", DEFAULT_WINDOW_UTC[1]))
    return start, end


def _minutes(hhmm: str) -> int:
    hh, _, mm = hhmm.partition(":")
    value = int(hh) * 60 + int(mm)
    if not 0 <= value < 24 * 60:
        raise OptimizerError("WINDOW_QX", hhmm)
    return value


@dataclass
class OptimizerSchedule:
    """W.4 execution window + the live-workload halt rule."""

    start: str = DEFAULT_WINDOW_UTC[0]
    end: str = DEFAULT_WINDOW_UTC[1]
    continuous: bool = False
    owner_configurable: bool = True

    def __post_init__(self) -> None:
        _minutes(self.start)
        _minutes(self.end)

    def in_window(self, *, utc_hhmm: str) -> bool:
        if self.continuous:
            return True
        now = _minutes(utc_hhmm)
        start, end = _minutes(self.start), _minutes(self.end)
        if start <= end:
            return start <= now < end
        return now >= start or now < end       # wraps midnight

    def may_run(self, *, utc_hhmm: str, live_workload: bool) -> Dict[str, Any]:
        """Optimization immediately halts if any live workload is detected."""
        if live_workload:
            return {"run": False, "reason": "LIVE_WORKLOAD_HALT",
                    "window": [self.start, self.end],
                    "continuous": self.continuous}
        if not self.in_window(utc_hhmm=utc_hhmm):
            return {"run": False, "reason": "OUTSIDE_WINDOW",
                    "window": [self.start, self.end],
                    "continuous": self.continuous}
        return {"run": True, "reason": "WINDOW_OPEN", "window": [self.start, self.end],
                "continuous": self.continuous}

    def set_continuous(self, enabled: bool, *, owner_command: str) -> Dict[str, Any]:
        """W.4/W.6: continuous-run mode is owner-enabled (`continuous on`)."""
        if enabled and owner_command.strip().lower() != CONTINUOUS_RUN_OWNER_FLAG:
            raise OptimizerError("CONTINUOUS_MODE_REQUIRES_OWNER",
                                 "send 'continuous on'")
        self.continuous = bool(enabled)
        return {"continuous": self.continuous,
                "window": [self.start, self.end]}


# --------------------------------------------------------------------------
# The dual optimizer
# --------------------------------------------------------------------------

@dataclass
class CellResult:
    """Result of one symbol×timeframe cell for one optimizer."""

    cell_id: str
    optimizer: str
    combinations_evaluated: int
    best_value: float
    best_params: Dict[str, float]
    feasible_fraction: float
    status: str = "COMPLETE"
    sru_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"cell_id": self.cell_id, "optimizer": self.optimizer,
                "combinations_evaluated": self.combinations_evaluated,
                "best_value": self.best_value, "best_params": self.best_params,
                "feasible_fraction": self.feasible_fraction,
                "status": self.status, "sru_hash": self.sru_hash,
                "contract_version": CONTRACT_VERSION}


class DualOptimizer:
    """Runs the exhaustive grid per cell and writes SUGGESTIONS only.

    ``evaluate(optimizer, params, cell_id) -> Mapping`` is the caller's real
    backtest objective (this module never fabricates a performance number).
    """

    def __init__(self, *, schedule: Optional[OptimizerSchedule] = None,
                 checkpoint_store: Optional[ResearchCheckpointStore] = None,
                 suggestions_dir: Optional[Path] = None) -> None:
        assert_scopes_disjoint()
        self.schedule = schedule or OptimizerSchedule(*nightly_window())
        self.store = checkpoint_store
        self.suggestions_dir = Path(suggestions_dir or SUGGESTIONS_DIR)
        self.results: List[CellResult] = []

    async def run_run(self, *, run_id: str, cells: Sequence[str],
                      grids: Mapping[str, ParameterGrid],
                      evaluate: Callable[[str, Mapping[str, float], str],
                                         Mapping[str, Any]],
                      optimizer: str = SIGNAL_OPTIMIZER,
                      utc_hhmm: str = "03:30", live_workload: bool = False,
                      owner_authorized_random: bool = False,
                      random_budget: Optional[int] = None, seed: int = 0
                      ) -> Dict[str, Any]:
        """Run every cell, checkpointing after each one (W.8-1)."""
        if optimizer not in (SIGNAL_OPTIMIZER, RISK_OPTIMIZER):
            raise OptimizerError("OPTIMIZER_QX", optimizer)
        decision = self.schedule.may_run(utc_hhmm=utc_hhmm,
                                         live_workload=live_workload)
        if not decision["run"]:
            if self.store is not None:
                for cell_id in cells:
                    await self.store.save_optimizer(
                        run_id=run_id, cell_id=cell_id, optimizer=optimizer,
                        status="LIVE_WORKLOAD_HALT" if live_workload
                        else "PAUSED", combination_index=0)
            return {"run_id": run_id, "status": decision["reason"],
                    "completed_cells": [], "pending_cells": list(cells),
                    "schedule": decision}
        completed: List[str] = []
        pending: List[str] = []
        for cell_id in cells:
            grid = grids.get(cell_id)
            if grid is None:
                pending.append(cell_id)
                continue
            state = None
            if self.store is not None:
                state = await self.store.load_optimizer(run_id, cell_id, optimizer)
            if state is not None and state["status"] == "COMPLETE":
                completed.append(cell_id)
                continue
            combos = grid.generate(owner_authorized_random=owner_authorized_random,
                                   budget=random_budget, seed=seed)
            best_value = float("-inf")
            best_params: Dict[str, float] = {}
            feasible = 0
            index = 0
            for combo in combos:
                result = dict(evaluate(optimizer, combo, cell_id))
                index += 1
                if result.get("feasible"):
                    feasible += 1
                value = float(result.get("value", float("-inf")))
                if value > best_value:
                    best_value = value
                    best_params = combo
            cell = CellResult(
                cell_id=cell_id, optimizer=optimizer,
                combinations_evaluated=len(combos),
                best_value=best_value, best_params=best_params,
                feasible_fraction=feasible / len(combos) if combos else 0.0,
                sru_hash=sha256_hex(canonical_json(
                    {"run_id": run_id, "cell": cell_id, "optimizer": optimizer,
                     "combos": len(combos)})))
            self.results.append(cell)
            if self.store is not None:
                await self.store.save_optimizer(
                    run_id=run_id, cell_id=cell_id, optimizer=optimizer,
                    status="COMPLETE", combination_index=len(combos),
                    best_value=(None if best_value == float("-inf")
                                else best_value),
                    best_params=best_params, sru_hash=cell.sru_hash)
            completed.append(cell_id)
        return {"run_id": run_id, "status": "COMPLETE",
                "completed_cells": completed, "pending_cells": pending,
                "results": [r.to_dict() for r in self.results
                            if r.optimizer == optimizer],
                "schedule": decision,
                "checkpointed": self.store is not None}

    # -- suggestion output (never a live parameter file) ------------------
    def write_suggestion(self, *, run_id: str, cell_id: str,
                         optimizer: str, params: Mapping[str, Any],
                         reason: str, package: Optional[ParameterPackage] = None
                         ) -> Dict[str, Any]:
        """Persist one suggestion. The write target is validated against the
        RED LINE before anything touches the disk (W.5 / G6)."""
        target_dir = self.suggestions_dir / run_id
        guard = ParameterPackage(
            package_id="suggestion-guard", version="0.0.0", values={},
            code_revision="0" * 40, feature_version="v4.0.0",
            model_version="v4.0.0", seed=0)
        assert_live_params_untouched(guard, target_dir,
                                     research_root=self.suggestions_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        payload: Dict[str, Any] = {
            "run_id": run_id, "cell_id": cell_id, "optimizer": optimizer,
            "params": dict(params), "reason": reason,
            "note": "SUGGESTION ONLY — never a live parameter value; "
                    "promotion requires W.5 validation + owner approval",
            "contract_version": CONTRACT_VERSION,
        }
        if package is not None:
            validation = validate_package(package)
            payload["package"] = package.to_dict()
            payload["validation"] = validation
        path = target_dir / f"{cell_id}-{optimizer.lower()}.json"
        assert_live_params_untouched(guard, path,
                                     research_root=self.suggestions_dir)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2),
                        encoding="utf-8")
        try:
            written = str(path.relative_to(REPO_ROOT))
        except ValueError:                      # relocated research sandbox
            written = str(path)
        return {"written": written,
                "suggestion_hash": sha256_hex(canonical_json(payload))}


def optimizer_summary() -> Dict[str, Any]:
    return {"scopes": assert_scopes_disjoint(),
            "full_grid_threshold": FULL_GRID_THRESHOLD,
            "default_window": list(nightly_window()),
            "continuous_flag": CONTINUOUS_RUN_OWNER_FLAG,
            "suggestions_dir": str(SUGGESTIONS_DIR.relative_to(REPO_ROOT)),
            "contract_version": CONTRACT_VERSION}
