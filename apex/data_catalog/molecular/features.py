"""APEX_GEN5 MOLECULAR feature tier — feature 74 `sweep` of the 74-feature
registry (§3.12). Computed from ATOM-tier features every 5 closed candles;
cached for 5 candles; validity 5–20 candles, decay exp(-0.02*age);
confidence = 0.9*Q_formula_valid*min(1, VolumeZ/2). Unit: strength, range
[0,1].

§3.12 definition implemented exactly as written:
    sweep_b = penetration beyond the rolling 20-bar extreme with close back
    inside the range, rejection ratio >= theta_sweep, VolumeZ >= 2 at the
    penetration candle, cooldown of 3 blocks since the last sweep of the
    same extreme — computed when the 5-candle block is CLOSED.

Rejection ratio (recovery / penetration depth) is the ratio of the close's
return inside the range to the depth of the penetration; theta_sweep is an
E02-owned parameter (UNAVAILABLE at CP-1) so the gate is evaluated with the
parameter when provided via `context['theta_sweep']`, else the raw
strength is returned with reason THETA_SWEEP_UNAVAILABLE (no invented
threshold). Interpretation recorded in DECISION_LOG §B/CP-1; E02 (CP-2)
owns the canonical re-assert.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from apex.data_catalog.contracts import MarketObservation

ComputeFn = Callable[
    [List[MarketObservation], Dict[str, Any], Dict[str, Any]],
    Tuple[Optional[Any], float, str, str],
]

BLOCK = 5               # 5-candle block, recomputed every 5 candles
EXTREME_WINDOW = 20     # rolling 20-bar extreme
COOLDOWN_BLOCKS = 3     # 3 blocks since last sweep of the same extreme
VOLUMEZ_GATE = Decimal(2)


def compute_sweep(
    window: List[MarketObservation],
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Tuple[Optional[Any], float, str, str]:
    """Compute F74 sweep for the last CLOSED 5-candle block of `window`.

    Requires at least EXTREME_WINDOW + BLOCK closed bars. The rolling
    extreme is the 20-bar high/low strictly BEFORE the block (no future
    leak). Returns (strength, q_formula_valid, status, reason).
    """
    need = EXTREME_WINDOW + BLOCK
    if len(window) < need:
        return None, 0.0, "UNAVAILABLE", "INSUFFICIENT_BARS_QX"
    block = window[-BLOCK:]
    prior = window[-(EXTREME_WINDOW + BLOCK):-BLOCK]
    if any(o.status != "CLOSED" for o in block):
        return None, 0.0, "CANDIDATE", "BLOCK_NOT_CLOSED"
    if any(o.high < o.low for o in block):
        return None, 0.0, "INVALID", "H_LT_L_QX"

    rolling_high = max(o.high for o in prior)
    rolling_low = min(o.low for o in prior)

    # Penetration: a candle in the block breaks the extreme and closes back
    # inside the range, with VolumeZ >= 2 at the penetration candle.
    sweep_kind = None  # 'LONG' (bearish sweep of low) or 'SHORT'
    for idx, obs in enumerate(block):
        vol_z = _volume_z(prior, obs)
        if vol_z < VOLUMEZ_GATE:
            continue
        if obs.low < rolling_low and obs.close > rolling_low:
            sweep_kind = "LONG"
            penetration = rolling_low - obs.low
            recovery = obs.close - rolling_low
            pen_obs = obs
            break
        if obs.high > rolling_high and obs.close < rolling_high:
            sweep_kind = "SHORT"
            penetration = obs.high - rolling_high
            recovery = rolling_high - obs.close
            pen_obs = obs
            break
    if sweep_kind is None:
        return Decimal(0), 1.0, "OK", "NO_SWEEP_IN_BLOCK"

    if penetration <= 0:
        return None, 0.0, "DEGRADED", "PENETRATION_BELOW_EPS_Q2"
    rejection_ratio = recovery / penetration

    # Cooldown of 3 blocks since the last sweep of the same extreme:
    # enforced by the caller's cache/last-sweep tracking when provided.
    last = context.get("last_sweep_block_index")
    current = context.get("current_block_index")
    if last is not None and current is not None and (current - last) <= COOLDOWN_BLOCKS:
        return None, 0.0, "OK", "COOLDOWN_ACTIVE"

    theta_sweep = context.get("theta_sweep")
    if theta_sweep is not None and rejection_ratio < Decimal(str(theta_sweep)):
        return None, 0.0, "OK", "REJECTION_BELOW_THETA_SWEEP"

    strength = max(Decimal(0), min(Decimal(1), rejection_ratio))
    reason = "" if theta_sweep is not None else "THETA_SWEEP_UNAVAILABLE_GATE_SKIPPED"
    status = "OK"
    q = 1.0
    return {"kind": sweep_kind, "strength": strength}, q, status, reason


def _volume_z(prior: List[MarketObservation], obs: MarketObservation) -> Decimal:
    from apex.data_catalog import math as m
    vols = [o.volume for o in prior] + [obs.volume]
    if len(vols) < 20:
        return Decimal(0)
    value = m.zscore(vols, 20)
    return value


COMPUTERS: Dict[str, ComputeFn] = {"sweep": compute_sweep}

MOLE_ENTRIES = [
    (74, "sweep", "APEX.L00.MOLE.LIQ.SWEEP.STRENGTH.V1"),
]

assert len(MOLE_ENTRIES) == 1
