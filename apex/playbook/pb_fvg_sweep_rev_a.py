"""APEX_GEN5 — Playbook ``PB_FVG_SWEEP_REV_A`` + position management
(Ch.11 §11.1 AE.1–AE.6 and §11.2 X.1–X.8; blueprint L15533–15750).

"A playbook turns an allowed setup into entry, stop, targets, time-stop, and
management rules. Stops, breakeven, and trail are position management, not a
new veto list." (Ch.11 heading)

Frozen content implemented here
------------------------------
* **AE.1** — the 16-field playbook template is the *sole* normative schema for
  playbook definitions; no playbook may contain hardcoded numeric constants
  outside governance bounds.
* **§10.2 AD.8 / AE.5** — the one instantiated playbook::

      stop_LONG  = min(sweep_low, fvg_low) - 0.25 * atr
      stop_SHORT = max(sweep_high, fvg_high) + 0.25 * atr
      target     = entry ± 3R
      BE_trigger_R = 1.0        BE_offset_R  = 0.10
      trail_after_R = 1.5       trail_atr_mult = 1.0
      max_hold_bars = 16        time_stop = flatten at bar 16 close

  Opposing E01 BOS before target → flatten reduce-only LIMIT+IOC then
  LIMIT+priceType=MARKET (never type=MARKET, never flashClose). Protective
  STOP GTC placed after entry ACK.
* **X.4 exit precedence (normative)** — five items, evaluated in order each
  candle: (1) invalid/quarantined data → immediate market close with
  ``DATA_INVALID``; (2) structural invalidation; (3) stop-loss; (4) target;
  (5) time exit. All fired conditions are recorded; the executed one defines
  ``exit_reason``. BE and trailing are **not** exit conditions — they are stop
  management inside item 3 (X.4), recorded for attribution.
* **X.1 breakeven** — activation at ``entry + BE_factor·R``; the stop moves to
  ``entry + buffer`` where the buffer covers round-trip fee + half the entry
  spread (the "breakeven is real" contract).
* **X.2 trailing** — activates after 1.0R of favorable progress; distance
  ``trail_factor × ATR(tf)``; volatility Extreme disables trailing and reverts
  to the fixed stop.
* **X.3 time stop** — hard ceiling of ``max_hold`` closed candles at the
  position's timeframe; flattens at that candle's close (``TIME_EXIT``).
* **Ch.9 §9.0 position scaling** — scaling-in (pyramiding) is DISABLED; one
  trade plan maps to exactly one position per (symbol, timeframe, direction)
  until CLOSED; scaling-out only through the target ladder, every partial exit
  reduces ``sized_quantity`` and the reserved risk proportionally and the stop
  is never widened.

Extra playbooks are Wave-Out (``extra_playbooks``): they raise, never stub.

Conflict resolution note (ISSUE-CP6-003): where the instantiated AE.5 values
and the governed X.1–X.3 per-timeframe bootstrap tables differ (BE trigger,
trail distance, max_hold), the **instantiated playbook's own values are
applied** and the generic table is reported as the fallback source — the
family-specific text is the narrower, later decree and is never silently
averaged with the generic one.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple,
)

from apex.config import load_params
from apex.errors import wave_out

CONTRACT_VERSION = "4.0.0"

PLAYBOOK_ID = "PB_FVG_SWEEP_REV_A"
PARENT_FAMILY_ID = "SF_FVG_SWEEP_REV"

# AE.1 — the 16-field template, verbatim field list (order matters).
AE1_TEMPLATE_FIELDS: Tuple[str, ...] = (
    "ID", "playbook-name", "parent-setup-ID", "entry-execution-class",
    "entry-target-fill-distance", "entry-trail-policy",
    "position-management-phase", "stop-structure", "take-profit-structure",
    "time-exit-policy", "breakeven-conditions", "anomaly-exit-trigger",
    "scaling-rules", "failure-mode-exit", "lifecycle",
    "research-battery-binding",
)
AE1_FIELD_COUNT = 16

# The instantiated playbook's frozen parameters (Ch.11 AE.5).
PLAYBOOK_PARAMS: Dict[str, Any] = {
    "stop_buffer_atr": 0.25,
    "target_r": 3.0,
    "be_trigger_r": 1.0,
    "be_offset_r": 0.10,
    "trail_after_r": 1.5,
    "trail_atr_mult": 1.0,
    "max_hold_bars": 16,
    "staged_exit_ratios": (1.0,),       # single target: 100 % at 3R
    "reentry": "per-family only (no re-entry ladder is defined in the freeze)",
}

# X.1–X.3 governed bootstrap defaults (fallback tables).
BE_FACTOR_BY_TF_GROUP: Dict[str, float] = {
    "1m": 0.8, "3m": 0.8, "5m": 0.8, "15m": 0.8,
    "30m": 1.0, "1h": 1.0, "2h": 1.0, "4h": 1.0, "8h": 1.0,
    "6h": 1.2, "12h": 1.2, "1d": 1.2, "1w": 1.2, "1mo": 1.2,
}
TRAIL_FACTOR_BY_VOLATILITY: Dict[str, Optional[float]] = {
    "VERY_LOW": 2.0, "LOW": 2.0, "NORMAL": 2.5, "HIGH": 3.0,
    "EXTREME": None,          # trailing DISABLED; fixed stops only
}
MAX_HOLD_BY_TF_GROUP: Dict[str, int] = {
    "1m": 96, "3m": 96, "5m": 96, "15m": 96,
    "30m": 60, "1h": 60, "2h": 60, "4h": 60, "8h": 60,
    "6h": 40, "12h": 40, "1d": 40,
    "1w": 20, "1mo": 20,
}
# X.6 optimizer bounds (recorded so a package outside them is rejected).
PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "be_factor_r": (0.5, 1.5),
    "trail_factor": (1.5, 4.0),
    "max_hold_bars": (10, 200),
    "stop_distance_atr": (0.5, 3.0),
    "target_distance_r": (1.0, 5.0),
}

# AE.3 failure-mode taxonomy → the five exit-precedence items.
EXIT_REASON_BY_FAILURE: Dict[str, str] = {
    "DATA_FAILURE": "DATA_INVALID",
    "CONTEXT_FAILURE": "STRUCTURAL_INVALID",
    "TIME_FAILURE": "TIME_EXIT",
    "EXECUTION_FAILURE": "EXECUTION_FAILED",
    "ECONOMIC_FAILURE": "ECONOMIC_INVALID",
}

# X.4 — the five-item precedence order (frozen; never extended).
EXIT_PRECEDENCE: Tuple[str, ...] = (
    "INVALID_DATA", "STRUCTURAL_INVALIDATION", "STOP_LOSS", "TAKE_PROFIT",
    "TIME_STOP",
)

PB_LIFECYCLE_STATES: Tuple[str, ...] = (
    "DRAFT", "VALIDATING", "ACTIVE", "DEGRADED", "DEPRECATED",
)
# AE.2 transitions (DEPRECATED is terminal).
PB_LIFECYCLE_FORWARD: Dict[str, Tuple[str, ...]] = {
    "DRAFT": ("VALIDATING",),
    "VALIDATING": ("ACTIVE", "DRAFT"),
    "ACTIVE": ("DEGRADED", "DEPRECATED"),
    "DEGRADED": ("ACTIVE", "DEPRECATED"),
    "DEPRECATED": (),
}


class ExitReason(str, enum.Enum):
    """The exit reasons a playbook may record (X.4 + AE.3)."""
    DATA_INVALID = "DATA_INVALID"
    STRUCTURAL_INVALID = "STRUCTURAL_INVALID"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_EXIT = "TIME_EXIT"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    ECONOMIC_INVALID = "ECONOMIC_INVALID"


# ---------------------------------------------------------------------------
# Governed parameter access (defaults in-code per ISSUE-CP2-006 precedent;
# frozen constants that the blueprint puts in the params files are READ)
# ---------------------------------------------------------------------------

def playbook_params(overrides: Optional[Mapping[str, Any]] = None
                    ) -> Dict[str, Any]:
    ov = dict(overrides or {})
    unknown = sorted(set(ov) - set(PLAYBOOK_PARAMS))
    if unknown:
        raise ValueError(f"UNKNOWN_PB_PARAM_QX: {unknown}")
    c = load_params()["setup_weights"]
    base = dict(PLAYBOOK_PARAMS)
    base["family_id"] = c["family_id"]
    base["playbook_id"] = c["playbook_id"]
    return {**base, **ov}


def _assert_bounds(name: str, value: float) -> None:
    lo, hi = PARAM_BOUNDS[name]
    if not (lo <= value <= hi):
        raise ValueError(
            f"PB_PARAM_OUT_OF_BOUNDS::{name}::{value} (governed range "
            f"[{lo}, {hi}] — X.6; a package outside it is rejected at "
            f"validation, never clamped)")


def be_factor_for(timeframe: str, package: Optional[Mapping[str, Any]] = None
                  ) -> Dict[str, Any]:
    """X.1 BE_factor: the optimized package wins, else the frozen bootstrap
    default for the timeframe group (never an invented interpolation)."""
    if timeframe not in BE_FACTOR_BY_TF_GROUP:
        raise ValueError(f"E-VAL-022: timeframe {timeframe!r} not in the 14")
    default = BE_FACTOR_BY_TF_GROUP[timeframe]
    if package and "be_factor" in package:
        v = float(package["be_factor"])
        _assert_bounds("be_factor_r", v)
        return {"be_factor_r": v, "source": "OPTIMIZED_PACKAGE"}
    return {"be_factor_r": default, "source": "FROZEN_BOOTSTRAP_X1"}


def trail_factor_for(volatility_regime: str,
                     package: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """X.2 trail_factor by volatility regime; EXTREME disables trailing."""
    regime = str(volatility_regime).upper()
    if regime not in TRAIL_FACTOR_BY_VOLATILITY:
        raise ValueError(
            f"PB_VOLATILITY_REGIME_QX: {volatility_regime!r} not in "
            f"{sorted(TRAIL_FACTOR_BY_VOLATILITY)}")
    if package and "trail_factor" in package:
        v = float(package["trail_factor"])
        _assert_bounds("trail_factor", v)
        return {"trail_factor": v, "trailing_enabled": regime != "EXTREME",
                "source": "OPTIMIZED_PACKAGE"}
    default = TRAIL_FACTOR_BY_VOLATILITY[regime]
    return {"trail_factor": default, "trailing_enabled": default is not None,
            "source": "FROZEN_BOOTSTRAP_X2"}


def max_hold_for(timeframe: str, package: Optional[Mapping[str, Any]] = None
                 ) -> Dict[str, Any]:
    """X.3 max_hold in closed candles of the position's timeframe."""
    if timeframe not in MAX_HOLD_BY_TF_GROUP:
        raise ValueError(f"E-VAL-022: timeframe {timeframe!r} not in the 14")
    if package and "max_hold_bars" in package:
        v = int(package["max_hold_bars"])
        _assert_bounds("max_hold_bars", v)
        return {"max_hold_bars": v, "source": "OPTIMIZED_PACKAGE"}
    return {"max_hold_bars": MAX_HOLD_BY_TF_GROUP[timeframe],
            "source": "FROZEN_BOOTSTRAP_X3"}


# ---------------------------------------------------------------------------
# The playbook record (AE.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlaybookRecord:
    """One AE.1 playbook: exactly 16 fields, all mandatory, plus the
    instantiation numbers they bind to."""

    record: Mapping[str, Any]
    regime_window: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        missing = [f for f in AE1_TEMPLATE_FIELDS if f not in self.record]
        if missing:
            raise ValueError(
                f"PB_SCHEMA_QX: AE.1 template fields missing {missing} — the "
                f"16-field template is the sole normative schema")
        extra = sorted(set(self.record) - set(AE1_TEMPLATE_FIELDS))
        if extra:
            raise ValueError(
                f"PB_SCHEMA_QX: {extra} are not AE.1 fields (the template is "
                f"the sole schema; no field may be invented)")
        if self.record["parent-setup-ID"] != PARENT_FAMILY_ID:
            raise ValueError(
                f"PB_PARENT_QX: a playbook must belong to a registered setup "
                f"family ({PARENT_FAMILY_ID})")
        if self.record["lifecycle"] not in PB_LIFECYCLE_STATES:
            raise ValueError(f"PB_LIFECYCLE_QX: {self.record['lifecycle']!r}")
        if len(AE1_TEMPLATE_FIELDS) != AE1_FIELD_COUNT:
            raise AssertionError("AE.1 field count drift")

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.record)


def instantiate_playbook(*, name: str = "FVG sweep reclaim — variant A",
                         lifecycle: str = "VALIDATING",
                         regime_window: Sequence[str] = ("TREND",
                                                        "TREND_EXPANSION"),
                         research_battery_binding: Sequence[str] = ("SL-13",),
                         **overrides: Any) -> PlaybookRecord:
    """The frozen instantiated playbook (AE.5) as an AE.1 record."""
    p = playbook_params(overrides.get("params"))
    record: Dict[str, Any] = {
        "ID": p["playbook_id"],
        "playbook-name": name,
        "parent-setup-ID": p["family_id"],
        "entry-execution-class": "LIMIT+IOC at the setup close (0-fill dies; "
                                 "never type=MARKET; never flashClose)",
        "entry-target-fill-distance": {
            "target_r": p["target_r"],
            "staged_exit_ratios": list(p["staged_exit_ratios"]),
            "fill_policy": "no chase",
        },
        "entry-trail-policy": {
            "trail_after_R": p["trail_after_r"],
            "trail_atr_mult": p["trail_atr_mult"],
            "fallback": "X.2 per-regime table (trail_after 1.0R)",
            "fallback_source": "FROZEN_BOOTSTRAP_X2",
        },
        "position-management-phase": "post-entry management only; never a veto "
                                     "and never an order",
        "stop-structure": {
            "stop_LONG": "min(sweep_low, fvg_low) − 0.25·ATR",
            "stop_SHORT": "max(sweep_high, fvg_high) + 0.25·ATR",
            "buffer_atr": p["stop_buffer_atr"],
            "protective_order": "STOP GTC placed after entry ACK",
        },
        "take-profit-structure": {"target": "entry ± 3R",
                                 "ladder": list(p["staged_exit_ratios"])},
        "time-exit-policy": {"max_hold_bars": p["max_hold_bars"],
                             "action": "flatten at bar 16 close",
                             "fallback": "X.3 per-TF table",
                             "fallback_source": "FROZEN_BOOTSTRAP_X3"},
        "breakeven-conditions": {
            "BE_trigger_R": p["be_trigger_r"], "BE_offset_R": p["be_offset_r"],
            "buffer": "round-trip fee + half the entry spread (X.1: breakeven "
                      "is real)",
            "fallback": "X.1 per-TF BE_factor table",
        },
        "anomaly-exit-trigger": {
            "opposing_e01_bos": "flatten: reduce-only LIMIT+IOC, then "
                               "LIMIT priceType=MARKET (never type=MARKET, "
                               "never flashClose)",
            "maps_to_precedence_item": 2,
        },
        "scaling-rules": {"scaling_in": "DISABLED",
                          "scaling_out": "target ladder only",
                          "stop_widening": "NEVER",
                          "one_position_per": ("symbol", "timeframe",
                                               "direction")},
        "failure-mode-exit": {k: v for k, v in EXIT_REASON_BY_FAILURE.items()},
        "lifecycle": lifecycle,
        "research-battery-binding": list(research_battery_binding),
    }
    return PlaybookRecord(record=record, regime_window=tuple(regime_window))


def register_playbook(name: str) -> None:
    """One playbook for the one family, on all 140 cells (AE.5). A second
    playbook is Wave-Out."""
    raise wave_out("extra_playbooks", f"PLAYBOOK_NOT_IN_FREEZE::{name}")


def lifecycle_can_move(src: str, dst: str, *, owner_confirmed: bool = False
                       ) -> bool:
    """AE.2 state machine; DEPRECATED is terminal and requires an explicit
    owner confirmation (no auto-demotion)."""
    if dst not in PB_LIFECYCLE_STATES or src not in PB_LIFECYCLE_STATES:
        raise ValueError(f"PB_LIFECYCLE_QX: {src!r}→{dst!r}")
    if dst not in PB_LIFECYCLE_FORWARD[src]:
        return False
    if dst == "DEPRECATED" and not owner_confirmed:
        raise ValueError(
            "PB_DEPRECATION_OWNER_GATE_QX: DEPRECATED requires explicit owner "
            "confirmation (AE.2)")
    if dst == "ACTIVE" and src != "DEGRADED":
        # AE.2: DEGRADED → ACTIVE is automatic on family recovery; every
        # other entry into ACTIVE belongs to the promotion pipeline, not here.
        raise ValueError(
            "PB_ACTIVE_GATE_QX: a playbook reaches ACTIVE only through the "
            "promotion gates AND a promoted parent family (AE.2) — this layer "
            "cannot self-promote")
    return True


# ---------------------------------------------------------------------------
# Stop construction (AE.5)
# ---------------------------------------------------------------------------

def build_stops(*, direction: int, entry: float, atr: float,
                sweep_extreme: float, fvg_low: Optional[float] = None,
                fvg_high: Optional[float] = None,
                buffer_atr: Optional[float] = None) -> Dict[str, Any]:
    """``stop_LONG = min(sweep_low, fvg_low) − 0.25·ATR`` and the SHORT mirror.

    A non-positive ATR fails closed (no substitute ATR); the risk unit R is
    fixed at inception by the returned ``R`` value.
    """
    if direction not in (-1, 0, 1) or direction == 0:
        raise ValueError("PB_DIRECTION_QX: direction must be ±1")
    if atr is None or atr <= 0 or atr != atr:
        raise ValueError("PB_ATR_QX: a governed positive ATR is mandatory")
    buf = float(PLAYBOOK_PARAMS["stop_buffer_atr"]) if buffer_atr is None \
        else float(buffer_atr)
    if direction > 0:
        base = min(float(sweep_extreme),
                   float(fvg_low) if fvg_low is not None
                   else float("inf"))
        stop = base - buf * atr
        if not stop < entry:
            raise ValueError(
                f"PB_STOP_SIDE_QX: LONG stop {stop} must sit below the entry "
                f"{entry} — a stop on the wrong side never becomes a plan")
    else:
        base = max(float(sweep_extreme),
                   float(fvg_high) if fvg_high is not None
                   else float("-inf"))
        stop = base + buf * atr
        if not stop > entry:
            raise ValueError(
                f"PB_STOP_SIDE_QX: SHORT stop {stop} must sit above the entry "
                f"{entry}")
    r = abs(entry - stop)
    target = entry + (r * PLAYBOOK_PARAMS["target_r"] if direction > 0
                      else -r * PLAYBOOK_PARAMS["target_r"])
    return {"stop": stop, "R": r, "target": target,
            "target_r_multiple": PLAYBOOK_PARAMS["target_r"],
            "buffer_atr": buf, "atr": float(atr)}


# ---------------------------------------------------------------------------
# X.1/X.2/X.3 stop-management operations (NOT exits)
# ---------------------------------------------------------------------------

def breakeven_state(*, entry: float, initial_stop: float, direction: int,
                    current: float, fees_round_trip: float,
                    half_spread: float, be_factor_r: float,
                    be_offset_r: float = 0.10) -> Dict[str, Any]:
    """X.1: activate at ``entry + BE_factor·R``; move the stop to
    ``entry + buffer`` where ``buffer`` recovers the round-trip fee, half the
    spread and the modeled slippage, plus the frozen BE offset.

    Activation is a stop-management instruction, never an exit event (X.4).
    """
    if direction not in (-1, 0, 1) or direction == 0:
        raise ValueError("PB_DIRECTION_QX: direction must be ±1")
    R = abs(entry - initial_stop)
    if R <= 0:
        raise ValueError("PB_RISK_UNIT_QX: R must be > 0 (entry ≠ stop)")
    _assert_bounds("be_factor_r", be_factor_r)
    sign = 1.0 if direction > 0 else -1.0
    progress = sign * (current - entry)
    activated = progress >= be_factor_r * R - 1e-12
    buffer = (abs(fees_round_trip) + abs(half_spread)) * abs(entry) \
        + be_offset_r * R
    # LONG: the stop moves UP to entry + buffer; SHORT: DOWN to entry − buffer
    # (buffer is the recovery amount, so closure there is zero net P&L).
    new_stop = entry + sign * buffer
    return {"activated": bool(activated),
            "be_stop_price": (new_stop if activated else initial_stop),
            "buffer": buffer, "R": R,
            "progress_r": progress / R,
            "counts_as_exit": False,               # X.4 placement
            "record": {"breakeven_activated": bool(activated),
                       "breakeven_stop_price": (new_stop if activated
                                               else initial_stop)}}


def trailing_state(*, entry: float, current_stop: float, direction: int,
                   current: float, atr: float, volatility_regime: str,
                   trail_after_r: float, trail_atr_mult: Optional[float] = None,
                   package: Optional[Mapping[str, Any]] = None,
                   timeframe: Optional[str] = None) -> Dict[str, Any]:
    """X.2: trailing activates after 1.0R of favorable progress, at
    ``trail_factor × ATR(tf)``; Extreme disables it and reverts to the fixed
    stop. The instantiated playbook overrides the generic factors
    (ISSUE-CP6-003)."""
    if direction not in (-1, 0, 1) or direction == 0:
        raise ValueError("PB_DIRECTION_QX: direction must be ±1")
    if atr is None or atr <= 0 or atr != atr:
        raise ValueError("PB_ATR_QX: trailing needs a governed positive ATR")
    R = abs(entry - current_stop) if current_stop else 0.0
    if R <= 0:
        raise ValueError("PB_RISK_UNIT_QX: R is undefined without an initial "
                         "stop — trailing never invents one")
    tf_info = {"trail_factor": None, "trailing_enabled": True,
               "source": "PLAYBOOK_INSTANTIATED"}
    if trail_atr_mult is None:
        regime = (volatility_regime or "NORMAL").upper()
        tf_info = trail_factor_for(regime, package)
    sign = 1.0 if direction > 0 else -1.0
    progress = sign * (current - entry)
    activated = progress >= trail_after_r * R - 1e-12
    enabled = bool(tf_info["trailing_enabled"])
    factor = (trail_atr_mult if trail_atr_mult is not None
              else tf_info["trail_factor"])
    distance = None if factor is None else float(factor) * atr
    if not enabled:
        return {"activated": False, "trailing_disabled_by_regime": True,
                "stop": current_stop, "distance": None,
                "record": {"trailing_activated": False,
                           "trailing_distance_final": None},
                "counts_as_exit": False,
                "reason": "VOLATILITY_EXTREME_FIXED_STOP"}
    if not activated:
        return {"activated": False, "trailing_disabled_by_regime": False,
                "stop": current_stop, "distance": distance,
                "record": {"trailing_activated": False,
                           "trailing_distance_final": None},
                "counts_as_exit": False, "source": tf_info["source"]}
    candidate = current - sign * distance
    # the trail only ratchets in the favourable direction (never widened)
    new_stop = max(current_stop, candidate) if direction > 0 \
        else min(current_stop, candidate)
    return {"activated": True, "trailing_disabled_by_regime": False,
            "stop": new_stop, "distance": distance, "factor": factor,
            "record": {"trailing_activated": True,
                       "trailing_distance_final": abs(entry - new_stop)},
            "counts_as_exit": False, "source": tf_info["source"]}


def time_stop_state(*, bars_held: int, timeframe: str,
                    max_hold_bars: Optional[int] = None,
                    package: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """X.3: the hard ceiling in CLOSED candles; at ``max_hold`` the position
    is flattened at that candle's close and recorded as ``TIME_EXIT``."""
    info = max_hold_for(timeframe, package)
    limit = int(info["max_hold_bars"] if max_hold_bars is None
                else max_hold_bars)
    return {"time_stop_triggered": int(bars_held) >= limit,
            "max_hold_bars": limit, "bars_held": int(bars_held),
            "source": info["source"] if max_hold_bars is None
            else "PLAYBOOK_INSTANTIATED",
            "record": {"time_stop_triggered": int(bars_held) >= limit}}


# ---------------------------------------------------------------------------
# X.4 exit precedence
# ---------------------------------------------------------------------------

def evaluate_exits(*, data_invalid: bool = False,
                   structural_invalidation: bool = False,
                   stop_hit: bool = False, target_hit: bool = False,
                   time_stop: bool = False,
                   stop_price: Optional[float] = None,
                   target_price: Optional[float] = None,
                   current_price: Optional[float] = None) -> Dict[str, Any]:
    """Resolve the exit for one candle using the frozen five-item order.

    All fired conditions are reported; exactly one defines ``exit_reason`` —
    the first in precedence order (X.4 / Ch.9 §9.0 "Exit precedence").
    """
    fired: List[Tuple[int, str, str]] = []
    if data_invalid:
        fired.append((1, "INVALID_DATA", ExitReason.DATA_INVALID.value))
    if structural_invalidation:
        fired.append((2, "STRUCTURAL_INVALIDATION",
                      ExitReason.STRUCTURAL_INVALID.value))
    if stop_hit:
        fired.append((3, "STOP_LOSS", ExitReason.STOP_LOSS.value))
    if target_hit:
        fired.append((4, "TAKE_PROFIT", ExitReason.TAKE_PROFIT.value))
    if time_stop:
        fired.append((5, "TIME_STOP", ExitReason.TIME_EXIT.value))
    if not fired:
        return {"fired": [], "exit_reason": None, "executed_item": None,
                "price": None, "reason": "NO_EXIT"}
    order = sorted(fired)
    item, _name, reason = order[0]
    price = current_price
    if reason == ExitReason.STOP_LOSS.value and stop_price is not None:
        price = stop_price                     # "exit at the stop price"
    elif reason == ExitReason.TAKE_PROFIT.value and target_price is not None:
        price = target_price
    return {"fired": [{"item": i, "condition": n, "reason": r}
                      for i, n, r in order],
            "exit_reason": reason, "executed_item": item, "price": price,
            "reason": "EXIT_RESOLVED_BY_PRECEDENCE"}


def flatten_on_opposing_bos(*, order_builder: Optional[Callable] = None
                            ) -> Dict[str, Any]:
    """AE.5 anomaly path: reduce-only LIMIT+IOC, then LIMIT priceType=MARKET.

    ``order_builder`` is injected by the caller (CP-7 owns order construction);
    this layer only declares the sequence and refuses forbidden order types.
    """
    seq = ("LIMIT+IOC(reduce-only)", "LIMIT priceType=MARKET(reduce-only)")
    forbidden = ("type=MARKET", "flashClose")
    plan = {"sequence": list(seq), "forbidden": list(forbidden),
            "authority": "PLAYBOOK_MANAGEMENT", "counts_as_new_veto": False}
    if order_builder is not None:
        for spec in seq:
            if any(f in spec for f in forbidden):
                raise wave_out("flash_close", "PB_ORDER_TYPE_FORBIDDEN")
            order_builder(spec)
    return plan


# ---------------------------------------------------------------------------
# Position scaling (Ch.9 §9.0 normative)
# ---------------------------------------------------------------------------

def apply_partial_exit(*, sized_quantity: float, reserved_risk: float,
                       ladder_weights: Sequence[float], taken_index: int,
                       current_stop: float, direction: int,
                       proposed_new_stop: Optional[float] = None) -> Dict[str, Any]:
    """A partial take reduces ``sized_quantity`` and the reserved risk
    proportionally; the stop for the remainder is **never widened**."""
    weights = [float(w) for w in ladder_weights]
    if not weights or sum(weights) <= 0:
        raise ValueError("PB_LADDER_QX: the target ladder must be non-empty")
    if taken_index < 0 or taken_index >= len(weights):
        raise ValueError(f"PB_LADDER_INDEX_QX: {taken_index} outside the ladder")
    share = weights[taken_index] / sum(weights)
    if sized_quantity < 0 or reserved_risk < 0:
        raise ValueError("PB_POSITION_QX: quantity and risk must be ≥ 0")
    qty = max(0.0, sized_quantity * (1.0 - share))
    risk = max(0.0, reserved_risk * (1.0 - share))
    stop = current_stop
    if proposed_new_stop is not None:
        if direction > 0:
            stop = max(current_stop, float(proposed_new_stop))
        elif direction < 0:
            stop = min(current_stop, float(proposed_new_stop))
        else:
            raise ValueError("PB_DIRECTION_QX: direction must be ±1")
    return {"sized_quantity": qty, "reserved_risk": risk,
            "closed_fraction": share, "stop": stop, "stop_widened": False,
            "scaling_in_allowed": False}


def pyramiding_policy() -> Dict[str, Any]:
    """Scaling-in (pyramiding) is disabled — one plan, one position per
    (symbol, timeframe, direction) until CLOSED."""
    return {"scaling_in": "DISABLED",
            "one_position_per": ("symbol", "timeframe", "direction"),
            "until": "CLOSED",
            "scaling_out": "playbook target ladder only (partial takes)"}


__all__ = ["AE1_FIELD_COUNT", "AE1_TEMPLATE_FIELDS", "CONTRACT_VERSION",
           "EXIT_PRECEDENCE", "EXIT_REASON_BY_FAILURE", "ExitReason",
           "MAX_HOLD_BY_TF_GROUP", "PB_LIFECYCLE_FORWARD",
           "PB_LIFECYCLE_STATES", "PARAM_BOUNDS", "PARENT_FAMILY_ID",
           "PLAYBOOK_ID", "PLAYBOOK_PARAMS", "PlaybookRecord",
           "TRAIL_FACTOR_BY_VOLATILITY", "apply_partial_exit",
           "be_factor_for", "breakeven_state", "build_stops",
           "evaluate_exits", "flatten_on_opposing_bos", "instantiate_playbook",
           "lifecycle_can_move", "max_hold_for", "playbook_params",
           "pyramiding_policy", "register_playbook", "time_stop_state",
           "trail_factor_for", "trailing_state"]
