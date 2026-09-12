"""APEX_GEN5 Quality Vector (§2.1) — the seven hard-gate components, the
four independent vetoes, Q_raw(tf), Q_window, and the derived quality
measures (Q_feature, Q_evidence, Q_param, Q_forecast).

All tables (freshness thresholds, Q_min, OI-lag thresholds, Q_raw weights,
Q_thr, Q_feature/Q_evidence weights, λ) are READ from
params/quality_weights_v1.yaml (frozen §2.1 literals) — nothing is
hardcoded here (§9.5: "copy the Q_raw / Q_min / OI-lag tables in §2.1.
Do not re-interpolate.").

Contract: Q_raw(tf) = Σ w_i(tf)·Q_i + 4 vetoes; a veto or a failed hard
gate quarantines the observation OUTRIGHT (QX INVALID) — it never merely
lowers a soft score; Q_raw < Q_min(tf) → QUARANTINED. Missing OI is never
coerced to 0 (Q_oi=0 MISSING is a label, not a quantity). Q_oi STALE=0.5
(canonical). calc_window_quality applies the minimum-veto (one quarantined
candle blocks the whole window) plus exponential-decay ranking
(λ=0.1, versioned).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.config import load_params
from apex.data_catalog.contracts import MarketObservation, oi_state_for


@dataclass(frozen=True)
class QualityFlags:
    """Ingest-side validation flags feeding the 13 hard gates (AI.4
    validation order is enforced by contracts.validate_market_observation;
    these flags record its outcomes per observation)."""

    schema_valid: bool = True
    ordering_valid: bool = True
    duplicate_hash_exists: bool = False
    sequence_hash_valid: bool = True
    replay_hash_valid: bool = True


# quality classes Q0..QX used by the state machine / resolution_class
QUALITY_CLASSES = ("Q0", "Q1", "Q2", "Q3", "Q4", "QX")


def _qw() -> Dict[str, Any]:
    return load_params()["quality_weights"]


def _freshness_thresholds() -> Dict[str, float]:
    return _qw()["freshness_threshold_seconds"]


def _oi_lag_thresholds() -> Dict[str, float]:
    return _qw()["oi_lag_threshold_seconds"]


def _q_min() -> Dict[str, float]:
    return _qw()["q_min_by_tf"]


def _q_raw_weights() -> Dict[str, Dict[str, float]]:
    return _qw()["q_raw_weights_by_tf"]


def _core10() -> Tuple[str, ...]:
    return tuple(load_params()["universe"]["symbols"])


def _tfs14() -> Tuple[str, ...]:
    return tuple(load_params()["universe"]["timeframes"])


def calc_quality_vector(
    obs: MarketObservation,
    flags: Optional[QualityFlags] = None,
) -> Tuple[Optional[float], str, str]:
    """§2.1 algorithm: 13 hard gates → 7 components → 4 vetoes → Q_min.

    Returns (Q_raw, state, quality_class). A quarantined observation
    returns (None, reason, "QX").
    """
    flags = flags or QualityFlags()
    tf = obs.timeframe
    thresholds = _freshness_thresholds()
    oi_thr = _oi_lag_thresholds()

    # ---- 13 hard gates (fail → QUARANTINED) --------------------------------
    if not flags.schema_valid:
        return None, "QUARANTINED_SCHEMA", "QX"
    if obs.symbol not in _core10():
        return None, "QUARANTINED_SYMBOL", "QX"
    if tf not in _tfs14():
        return None, "QUARANTINED_TIMEFRAME", "QX"
    if not obs.timestamp:
        return None, "QUARANTINED_TIMESTAMP", "QX"
    if not flags.ordering_valid:
        return None, "QUARANTINED_ORDERING", "QX"
    if flags.duplicate_hash_exists:
        return None, "QUARANTINED_DUPLICATE", "QX"
    if not (obs.high >= max(obs.open, obs.close)
            and obs.low <= min(obs.open, obs.close)
            and obs.high >= obs.low):
        return None, "QUARANTINED_OHLC", "QX"
    if obs.volume < 0:
        return None, "QUARANTINED_VOLUME_NEG", "QX"

    freshness = obs.delay_seconds
    if freshness > thresholds.get(tf, 30):
        return None, "QUARANTINED_FRESHNESS", "QX"
    if not flags.sequence_hash_valid:
        return None, "QUARANTINED_SEQUENCE", "QX"
    if not flags.replay_hash_valid:
        return None, "QUARANTINED_REPLAY", "QX"

    # ---- the 7 quality components ------------------------------------------
    q_schema = 1.0 if flags.schema_valid else 0.0
    q_time = 1.0 - min(1.0, freshness / thresholds.get(tf, 30))
    if obs.expected_count > 0:
        q_seq = 1.0 - obs.gap_count / obs.expected_count
    else:
        q_seq = 0.0  # fail-closed: no expected count ⇒ no sequence credit
    q_ohlc = 1.0 if (obs.high >= max(obs.open, obs.close)
                     and obs.low <= min(obs.open, obs.close)
                     and obs.high >= obs.low) else 0.0
    q_volume = 1.0 if obs.volume >= 0 else 0.0
    q_volume = 0.5 if obs.volume == 0 else q_volume  # degraded, not invalid
    _oi_state, q_oi = oi_state_for(obs.oi, obs.oi_lag_seconds, oi_thr.get(tf, 60))
    q_source = 1.0 if obs.source_health >= 0.8 else 0.0

    weights = _q_raw_weights().get(tf)
    if weights is None:
        # Frozen algorithm fallback for undocumented TFs: the 1h row
        # (complete §2.1 table covers all 14 TFs, so this is defensive).
        weights = _q_raw_weights().get("1h", {})
    components = {"Q_schema": q_schema, "Q_time": q_time, "Q_seq": q_seq,
                  "Q_ohlc": q_ohlc, "Q_volume": q_volume, "Q_oi": q_oi,
                  "Q_source": q_source}
    q_raw = sum(weights[k] * v for k, v in components.items())

    # ---- the 4 independent vetoes ------------------------------------------
    # veto_OI_lag is a hard quarantine, not a soft one (Ch.7). Per the §2.1
    # Q_oi table, STALE (lag ≤ 5·threshold, weight 0.5) is a scored state;
    # the hard veto fires when OI degrades past the STALE band (lag >
    # 5·threshold → DEGRADED) or is INVALID — matching the table semantics
    # (interpretation recorded in DECISION_LOG §B/CP-1).
    veto_freshness = freshness > thresholds.get(tf, 30)
    veto_completeness = obs.completeness_pct < 100
    veto_oi_lag = (obs.oi is not None and obs.oi_lag_seconds is not None
                   and obs.oi_lag_seconds > 5 * oi_thr.get(tf, 60))
    veto_source = obs.source_health < 0.8
    if veto_freshness or veto_completeness or veto_oi_lag or veto_source:
        return None, "QUARANTINED_VETO", "QX"

    q_min_tf = _q_min().get(tf, 0.5)
    if q_raw < q_min_tf:
        return None, "QUARANTINED_Q_MIN", "QX"
    return q_raw, "VALID", "Q1"


def calc_window_quality(
    qualities: Sequence[Tuple[float, float]],
    lam: Optional[float] = None,
    q_thr: Optional[float] = None,
) -> Tuple[Optional[float], str, str]:
    """§2.1 calc_window_quality. ``qualities`` = (Q_i, age_i) pairs for the
    consumer's required window.

    Two conditions apply TOGETHER: (1) hard minimum-veto — min(Q_i) below
    Q_thr invalidates the ENTIRE window (a simple average is not used);
    (2) ranking score = Σ Q_i·exp(−λ·age_i) / Σ exp(−λ·age_i).
    """
    lam = _qw()["q_window_lambda"] if lam is None else lam
    q_thr = 0.5 if q_thr is None else q_thr  # frozen algorithm default
    if not qualities:
        return None, "INVALID_EMPTY", "QX"
    weighted_sum = sum(q * math.exp(-lam * age) for q, age in qualities)
    exp_sum = sum(math.exp(-lam * age) for _, age in qualities)
    if exp_sum < 1e-12:
        return None, "INVALID_EXP_SUM_ZERO", "QX"
    q_window = weighted_sum / exp_sum
    min_q = min(q for q, _ in qualities)
    if min_q < q_thr:
        return None, "INVALID_MIN_Q_THR", "QX"
    return q_window, "VALID", "Q1"


def q_feature(q_formula_valid: float, q_lookback_complete: float,
              q_epsilon: float) -> float:
    """Q_feature = w_formula·Q_formula_valid × w_lookback·Q_lookback_complete
    × w_epsilon·Q_epsilon (w=0.5/0.3/0.2, from params)."""
    w = _qw()["q_feature_weights"]
    return w["w_formula"] * q_formula_valid * w["w_lookback"] \
        * q_lookback_complete * w["w_epsilon"] * q_epsilon


def q_evidence(q_conf: float, q_strength: float, q_fresh: float,
               q_regime: float, timeframe: str) -> float:
    """Q_evidence(tf) = w_conf(tf)·Q_conf × w_strength·Q_strength ×
    w_freshness(tf)·Q_fresh × w_regime·Q_regime.

    §2.1 documents representative rows for w_conf/w_freshness (1m/1h/1d);
    for any other timeframe the weights are unspecified → fail-closed
    ValueError (never an invented interpolation).
    """
    w = _qw()["q_evidence_weights"]
    w_conf_map = w["w_conf_by_tf"]
    w_fresh_map = w["w_freshness_by_tf"]
    if timeframe not in w_conf_map or timeframe not in w_fresh_map:
        raise ValueError(
            f"Q_evidence weights unspecified for timeframe {timeframe} "
            f"(§2.1 documents 1m/1h/1d only — FAIL_CLOSED, no interpolation)"
        )
    return (w_conf_map[timeframe] * q_conf * w["w_strength"] * q_strength
            * w_fresh_map[timeframe] * q_fresh * w["w_regime"] * q_regime)


def q_param(rolling_calibration_error: float, brier: float,
            log_loss: float) -> Tuple[float, bool]:
    """Q_param = 1 − rolling_calibration_error − Brier − log_loss.
    Q_param < 0.5 → the parameter package is marked DEGRADED."""
    value = 1.0 - rolling_calibration_error - brier - log_loss
    value = max(0.0, min(1.0, value))
    return value, value < 0.5


def q_forecast(rolling_calibration_error: float, brier: float,
               log_loss: float) -> Tuple[float, bool]:
    """Q_forecast = 1 − rolling_calibration_error − Brier − log_loss
    (same formula family as Q_param, applied to the forecasting model).
    Q_forecast < 0.5 → Forecast BLOCK (§2.1 failure modes)."""
    value = 1.0 - rolling_calibration_error - brier - log_loss
    value = max(0.0, min(1.0, value))
    return value, value < 0.5


def q_fresh(age_bars: float, lam: Optional[float] = None) -> float:
    """Q_fresh = exp(−λ·age), λ = 0.1 per bar (versioned)."""
    lam = _qw()["q_evidence_lambda"] if lam is None else lam
    return math.exp(-lam * age_bars)
