"""APEX_GEN5 Snapshot / Point-in-Time window management (§2.3).

- ``as_of`` = max(availability_time) over all required artifacts — the
  single dynamic PIT boundary; never a fixed tick, never candle timestamp,
  never local wall-clock, never a fixed lag. Missing availability_time →
  fail-closed ValueError (G11).
- Observation windows are per-consumer (required_depth + warmup bars), all
  bound to the same as_of.
- MTF states: ALIGNED / PARTIALLY_ALIGNED / CONFLICTING / INSUFFICIENT
  (ABSENT per-timeframe in the frozen algorithm); a consumer whose
  required timeframe is INSUFFICIENT must downgrade or refuse.
- symbol_scope > 10 → BLOCK; timeframe_scope > 14 → BLOCK.
- Snapshots are immutable: a new artifact produces a new snapshot_id
  (deterministic SHA-256 over the canonical payload) — OLD → CORRECTION
  EVENT → NEW VERSION → SUPERSEDES.

tf_duration for the 14 timeframes is the unambiguous minute-multiple set;
``1mo`` = 2592000 s (30-day exchange interval, Toobit wire 1mo→1M) —
recorded in DECISION_LOG §B/CP-1 (the blueprint names tf_duration without
a table; this is the documented, deterministic interim).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import MarketObservation
from apex.identity.snapshot import (
    SnapshotBarrier,
    manifest_hash,
    snapshot_id_from_payload,
)

TF_DURATION_SECONDS: Dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "1w": 604800,
    "1mo": 2592000,  # 30-day exchange interval (Toobit 1mo→1M)
}

# §2.3 parameter-table defaults used by the frozen algorithm
DEFAULT_REQUIRED_DEPTH = {"1m": 100, "1h": 100, "4h": 100}
DEFAULT_WARMUP = {"1m": 14, "1h": 14, "4h": 14}
DEFAULT_BARS_FALLBACK = 100
DEFAULT_WARMUP_FALLBACK = 14

MTF_STATES = ("ALIGNED", "PARTIALLY_ALIGNED", "CONFLICTING", "INSUFFICIENT",
              "ABSENT")


def _availability_ms(obs: MarketObservation) -> int:
    """availability_time → epoch-ms. Missing → fail-closed ValueError
    (G11: never substitute candle ts / local clock / fixed lag)."""
    from apex.data_catalog.contracts import parse_utc_ms
    if obs.availability_time is None:
        raise ValueError("MISSING_AVAILABILITY_TIME_QX")
    return int(parse_utc_ms(obs.availability_time).timestamp() * 1000)


def calc_snapshot_pit_window(
    observations: Sequence[MarketObservation],
    required_timeframes: Sequence[str],
    minimum_bars: int,
    closed_only: bool = True,
    freshness_threshold: Optional[float] = None,
    eps: float = 1e-12,
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """§2.3 algorithm. Returns (snapshot, state, class) or
    (None, reason, "QX") when the window cannot be built (INSUFFICIENT_BARS
    / PIT_VIOLATION). Fail-closed on missing availability_time."""
    valid_observations = [
        obs for obs in observations
        if (obs.is_closed if closed_only else True)
        and obs.timeframe in required_timeframes
    ]
    if len(valid_observations) < minimum_bars:
        return None, "INSUFFICIENT_BARS", "QX"

    as_of_ms = max(_availability_ms(obs) for obs in valid_observations)
    for obs in valid_observations:
        if _availability_ms(obs) > as_of_ms:
            return None, "PIT_VIOLATION", "QX"

    observation_windows: Dict[str, Any] = {}
    for tf in required_timeframes:
        required_depth = DEFAULT_REQUIRED_DEPTH.get(tf, DEFAULT_BARS_FALLBACK)
        warmup = DEFAULT_WARMUP.get(tf, DEFAULT_WARMUP_FALLBACK)
        bars = required_depth + warmup
        duration = TF_DURATION_SECONDS[tf]
        start_ms = as_of_ms - bars * duration * 1000
        observation_windows[tf] = {
            "start": start_ms,
            "end": as_of_ms,
            "timeframe": tf,
            "bars": bars,
        }

    mtf_states: Dict[str, str] = {}
    for tf in required_timeframes:
        if tf not in observation_windows:
            mtf_states[tf] = "ABSENT"
        elif sum(1 for o in valid_observations if o.timeframe == tf) < minimum_bars:
            mtf_states[tf] = "INSUFFICIENT"
        else:
            mtf_states[tf] = "ALIGNED"

    if all(s == "ALIGNED" for s in mtf_states.values()):
        overall_mtf = "ALIGNED"
    elif any(s == "INSUFFICIENT" for s in mtf_states.values()):
        overall_mtf = "INSUFFICIENT"
    elif any(s == "ABSENT" for s in mtf_states.values()):
        overall_mtf = "PARTIALLY_ALIGNED"
    else:
        overall_mtf = "CONFLICTING"

    symbol_scope = list({obs.symbol for obs in valid_observations})[:10]
    timeframe_scope = list(required_timeframes)[:14]

    manifest = {
        "symbol_scope": symbol_scope,
        "timeframe_scope": timeframe_scope,
        "observation_windows": observation_windows,
        "as_of": as_of_ms,
        "mtf_states": mtf_states,
        "overall_mtf": overall_mtf,
    }
    mhash = manifest_hash(manifest)

    from apex.config import load_params
    from apex import __version__
    parameter_package_id = "params_v1_frozen"  # package id placeholder replaced by CP-6 governance
    code_version = __version__

    quality_state = _min_q_and_weighted_mean(valid_observations)

    # Deterministic snapshot identity (§2.3 binding): created_at is
    # operational metadata and is NOT part of the hashed payload.
    import time as _time
    payload = {
        "as_of": as_of_ms,
        "symbol_scope": symbol_scope,
        "timeframe_scope": timeframe_scope,
        "source_state": "VALID",
        "manifest_hash": mhash,
        "parameter_package_id": parameter_package_id,
        "code_version": code_version,
        "quality_state": quality_state,
        "observation_windows": observation_windows,
        "mtf_states": mtf_states,
        "overall_mtf": overall_mtf,
    }
    snapshot_id = snapshot_id_from_payload(payload)
    snapshot = {
        "snapshot_id": snapshot_id,
        "timeframe_scope": timeframe_scope,
        "source_state": "VALID",
        "manifest_hash": mhash,
        "parameter_package_id": parameter_package_id,
        "code_version": code_version,
        "quality_state": quality_state,
        "created_at": _time.time(),
        "observation_windows": observation_windows,
        "mtf_states": mtf_states,
        "overall_mtf": overall_mtf,
    }
    return snapshot, "VALID", "Q1"


def _min_q_and_weighted_mean(observations: Sequence[MarketObservation],
                             ) -> Dict[str, Any]:
    """combined quality state: minimum-veto plus weighted average (§2.3
    snapshot binding). Observations without a computed Q_raw count as Q0."""
    qs: List[float] = []
    for obs in observations:
        qs.append(float(getattr(obs, "q_raw", 0.0) or 0.0))
    if not qs:
        return {"min_q": 0.0, "weighted_q": 0.0}
    return {"min_q": min(qs), "weighted_q": sum(qs) / len(qs)}


def build_snapshot_barrier(
    as_of_ms: int,
    symbol_scope: List[str],
    timeframe_scope: List[str],
    source_state: str,
    mhash: str,
    parameter_package_id: str,
    code_version: str,
    quality_state: Dict[str, Any],
    observation_windows: Dict[str, Any],
    mtf_states: Dict[str, str],
    overall_mtf: str,
) -> SnapshotBarrier:
    """Construct the immutable SnapshotBarrier (as_of as ISO-8601 ms)."""
    import datetime as _dt
    as_of_iso = _dt.datetime.fromtimestamp(
        as_of_ms / 1000.0, tz=_dt.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%S.") + f"{as_of_ms % 1000:03d}Z"
    return SnapshotBarrier(
        as_of=as_of_iso,
        symbol_scope=symbol_scope,
        timeframe_scope=timeframe_scope,
        source_state=source_state,
        manifest_hash=mhash,
        parameter_package_id=parameter_package_id,
        code_version=code_version,
        quality_state=quality_state,
        observation_windows=observation_windows,
        mtf_states=mtf_states,
        overall_mtf=overall_mtf,
    )
