"""E12 — Temporal Context Engine (v4.0.0).

Canonical implementation of APEX_GEN5.md ``E12 — Temporal Context Engine``
(§0–§11).  E12 owns the canonical UTC activity-window registry (§3.5) and is
the SOLE runtime source for primary UTC activity-window routing; ``OVERLAP``
is a derived flag and never a mutually exclusive primary window.  E12 outputs
are Context — never signals or permissions (§11 Consumers).

**24/7 invariant (§3.1):** the Toobit crypto-futures market is continuously
tradable; windows, day-types, rollover metadata and calendar events are
analytical context only — never market open/close, weekend closure, or
permission to trade.  **UTC provenance invariant:** all runtime timestamps
are UTC-normalized; no device-local/host/regional wall-clock may alter
routing, gating, replay or execution semantics.

Spec resolutions recorded for PHASE2_DECISION_LOG §B (ISSUE-CP5-020..027):

* **ISSUE-CP5-020** — §8.1 GF10 expects ``rollover_active=true``, but §3.1
  makes rollover an exchange-configured event with NO universal CME schedule
  and the frozen default configuration is empty (⇒ never active).  Resolution:
  ``rollover_windows`` is injected runtime configuration
  (``{"weekdays": [...], "start_h": x, "end_h": y}``); GF10 is verified with
  an explicit Saturday ``[00:00, 01:00)`` configuration.  Default ``[]`` ⇒
  ``rollover_active=False`` always.
* **ISSUE-CP5-021** — §8.1 GF01 (2024-03-15, a Friday) expects
  ``expected_daytype="WEEKDAY"`` while the §4 pseudocode returns ``FRIDAY``
  for ``weekday()==4`` and GF11 (same date) expects ``FRIDAY``.  The
  pseudocode governs; GF01 re-derived to ``FRIDAY``.
* **ISSUE-CP5-022** — §8.1 GF09 expects ``gap=true`` but the §3.1 formula
  (``O_t > H_{t-1}·1.1`` or ``O_t < L_{t-1}·0.9``) gives
  ``71000 ≤ 77000`` ⇒ no gap.  The formula governs; GF09 re-derived to
  ``gap=false`` and the gap flag is separately proven with synthetic
  >10%/<-10% data.
* **ISSUE-CP5-023** — §8.1 GF10 (00:30 UTC) expects ``UTC_W3`` but
  σ(00:30) ∈ [00:00, 07:00) ⇒ ``UTC_W0`` per §3.5/§4.  Re-derived to
  ``UTC_W0``.
* **ISSUE-CP5-024** — §3.2/§11(a): the absolute-value FFF estimator is
  biased and must NEVER be used.  ``fff_seasonal(..., use_sqrt=True)``
  therefore fails closed (``FFF_ABS_ESTIMATOR_FORBIDDEN``) instead of
  silently switching estimators.
* **ISSUE-CP5-025** — §4.2 imports ``scipy.stats``, which is not among the
  nine SBOM pins (requirements.lock).  Kruskal–Wallis (tie-corrected, χ²
  survival via an in-tree regularized incomplete gamma) and Spearman ρ
  (Pearson on mid-ranks) are implemented in-tree (E04 precedent; no
  cross-engine import).  numpy IS an SBOM pin and is used.
* **ISSUE-CP5-026** — §8.1 GF05's ``VR=2.5`` needs a window-volume history;
  a single candle cannot yield it.  Verified by injecting the canonical
  window mean volume (8000) ⇒ ``VR = 20000/8000 = 2.5`` deterministically.
* **ISSUE-CP5-027** — §4 ``on_candle`` emits the minimal state; §5.2
  ``TemporalContextState_v4`` requires ``version``, ``tod_state`` and
  ``rollover_active``.  The §5.2 schema is the canonical artifact: the
  engine state merges both (pseudocode keys ⊂ schema keys), and the hashed
  §5.1 payload binds the complete deterministic state minus ``snapshot_id``.

Wave-Out: none for E12 (no forecast surface is specified).  Fail-closed on
every unspecified input (missing ``availability_time_ms`` ⇒ QX; H<L / V<0 /
NaN ts ⇒ Q0; unmapped hour ⇒ ValueError; degenerate stats ⇒ UNAVAILABLE/Q1).
"""

from __future__ import annotations

import datetime
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from apex.data_catalog.contracts import EvidenceEvent, MarketObservation
from apex.engines.base import EngineBase, LifecycleState
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

# ---------------------------------------------------------------------------
# §2/§3.5 — canonical registry and constants
# ---------------------------------------------------------------------------
ENGINE = "E12_Temporal_Context"
ENGINE_ID = "E12"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = f"{ENGINE}/{CONTRACT_VERSION}"
E07_CONTRACT_LABEL = "E12_Temporal_Context.Contract v4.0.0"
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E12"))       # 1e-12 per Global Contracts §2.2

UTC_ACTIVITY_WINDOWS: Dict[str, Tuple[float, float]] = {
    "UTC_W0": (0.0, 7.0),
    "UTC_W1": (7.0, 12.5),
    "UTC_W2": (12.5, 21.0),
    "UTC_W3": (21.0, 24.0),
}
UTC_CORE_WINDOWS: Dict[str, Tuple[float, float]] = {
    "UTC_W1_CORE": (7.0, 11.0),
    "UTC_W2_CORE": (12.5, 16.0),
}
OVERLAP_WINDOW: Tuple[float, float] = (12.5, 16.0)
OVERLAP_LABEL = "UTC_W1_W2_OVERLAP"      # derived flag label (E07 §3.6)
PRIMARY_WINDOWS: Tuple[str, ...] = ("UTC_W0", "UTC_W1", "UTC_W2", "UTC_W3")
PHASES: Tuple[str, ...] = ("EARLY", "MID", "LATE")
DAY_TYPES: Tuple[str, ...] = ("WEEKDAY", "FRIDAY",
                              "SATURDAY_SUNDAY_CONTEXT", "HIGH_IMPACT")
QUALITY_TAGS: Tuple[str, ...] = ("Q0", "Q1", "Q2", "Q3", "Q4")
FATE_VALUES: Tuple[str, ...] = ("ACTIVE", "SUPERSEDED", "INVALIDATED")
N_BINS_DEFAULT = 48                      # §2 ToD bin: n = floor(h·N/24)
FOURIER_K_DEFAULT = 4                    # §3.2 smoothing
WILSON_Z = 1.96                          # §3.3
CALENDAR_CONFIG_VERSION = "v2024a"       # §6 temporal_window_calendar_version
SEASONAL_CLAMP = (0.1, 10.0)             # §3.2 ŝ clamp
SEASONAL_MEAN_TARGET = 1.0               # (1/N)Σŝ_n = 1

EVENT_CATALOG: Dict[str, Dict[str, str]] = {
    "EV_TMP_001": {"name": "TemporalWindow_Entered"},
    "EV_TMP_002": {"name": "TemporalWindow_Exited"},
    "EV_TMP_003": {"name": "Overlap_Active"},
    "EV_TMP_004": {"name": "Tod_Phase_Changed"},
    "EV_TMP_005": {"name": "DayType_Hypothesis"},
    "EV_TMP_006": {"name": "Profile_Ready"},
    "EV_TMP_007": {"name": "TemporalWindow_Levels_Refreshed"},
    "EV_TMP_008": {"name": "Calendar_Unavailable"},
    "EV_TMP_009": {"name": "InvalidCandle"},
}

E12_DEFAULTS: Dict[str, Any] = {
    # §6 complete parameter table (governed defaults; no runtime YAML file —
    # params/e12_params_v4.yaml does not exist in the frozen config map, so
    # the code defaults ARE the §6 canonical surface).
    "temporal_window_calendar_version": CALENDAR_CONFIG_VERSION,
    "utc_w0_start": 0.0, "utc_w0_end": 7.0,
    "utc_w1_core_start": 7.0, "utc_w1_core_end": 11.0,
    "utc_w2_core_start": 12.5, "utc_w2_core_end": 16.0,
    "utc_w1_ext_start": 7.0, "utc_w1_ext_end": 12.5,
    "utc_w2_ext_start": 12.5, "utc_w2_ext_end": 21.0,
    "utc_overlap_start": 12.5, "utc_overlap_end": 16.0,
    "behavior_window": 180,               # days, 30–365
    "fff_bins": N_BINS_DEFAULT,           # 24–96
    "fff_fourier_K": FOURIER_K_DEFAULT,   # 0–8
    "daytype_min_samples": 30,            # 10–100 (Wilson floor)
    "vol_burst_threshold": 1.5,           # Y_vol = [VR > 1.5]
    "range_z_threshold": 1.5,             # Y_range = [Z_R > 1.5]
    "intraday_horizon": 4,                # candles
    "utc_activity_window_enable": True,
    "econ_calendar_source": "configured_calendar.json",
    "high_impact_currencies": ["USD", "EUR", "GBP", "JPY"],
    "rollback_on_invalid": True,
    "wilson_z": WILSON_Z,
}
_PARAM_RANGES: Dict[str, Tuple[float, float]] = {
    "behavior_window": (30, 365), "fff_bins": (24, 96),
    "fff_fourier_K": (0, 8), "daytype_min_samples": (10, 100),
    "vol_burst_threshold": (1.2, 3.0), "range_z_threshold": (1.0, 2.5),
    "intraday_horizon": (1, 12),
}


class EngineParams:
    """Frozen §6 surface; unknown keys and out-of-range values rejected."""

    def __init__(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        values = dict(E12_DEFAULTS)
        for key, val in (overrides or {}).items():
            if key not in E12_DEFAULTS:
                raise ValueError(f"UNKNOWN_E12_PARAM_QX: {key}")
            values[key] = val
        self._assert_registry(values)
        for name, (lo, hi) in _PARAM_RANGES.items():
            v = float(values[name])
            if not (lo <= v <= hi) or not math.isfinite(v):
                raise ValueError(
                    f"CONFIGURATION_INVALID: {name}={values[name]!r} outside "
                    f"governed §6 range [{lo}, {hi}]")
        if str(values["temporal_window_calendar_version"]).strip() == "":
            raise ValueError("CONFIGURATION_INVALID: empty calendar version")
        self._v = values
        for name, val in values.items():
            setattr(self, name, val)

    @staticmethod
    def _assert_registry(values: Dict[str, Any]) -> None:
        """§3.5 canonical registry is the sole source — assert consistency."""
        checks = (
            (values["utc_w0_start"], UTC_ACTIVITY_WINDOWS["UTC_W0"][0]),
            (values["utc_w0_end"], UTC_ACTIVITY_WINDOWS["UTC_W0"][1]),
            (values["utc_w1_ext_start"], UTC_ACTIVITY_WINDOWS["UTC_W1"][0]),
            (values["utc_w1_ext_end"], UTC_ACTIVITY_WINDOWS["UTC_W1"][1]),
            (values["utc_w2_ext_start"], UTC_ACTIVITY_WINDOWS["UTC_W2"][0]),
            (values["utc_w2_ext_end"], UTC_ACTIVITY_WINDOWS["UTC_W2"][1]),
            (values["utc_w1_core_start"], UTC_CORE_WINDOWS["UTC_W1_CORE"][0]),
            (values["utc_w1_core_end"], UTC_CORE_WINDOWS["UTC_W1_CORE"][1]),
            (values["utc_w2_core_start"], UTC_CORE_WINDOWS["UTC_W2_CORE"][0]),
            (values["utc_w2_core_end"], UTC_CORE_WINDOWS["UTC_W2_CORE"][1]),
            (values["utc_overlap_start"], OVERLAP_WINDOW[0]),
            (values["utc_overlap_end"], OVERLAP_WINDOW[1]),
        )
        for got, want in checks:
            if float(got) != float(want):
                raise ValueError(
                    "CONFIGURATION_INVALID: §3.5 canonical UTC window "
                    f"registry violation ({got} != {want}) — E12 owns the "
                    "registry; windows are not tunable at runtime")

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._v)


def param_hash(params: EngineParams) -> str:
    """Deterministic 12-hex parameter fingerprint."""
    return sha256_hex(canonical_json(params.as_dict()).encode("utf-8"))[:12]


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    if isinstance(overrides, EngineParams):
        return overrides
    return EngineParams(overrides)


# ---------------------------------------------------------------------------
# §3.5/§4.1 — window function σ(t), phases, day type, rollover
# ---------------------------------------------------------------------------
def ts_from_ms(ts_ms: Any) -> datetime.datetime:
    """epoch ms → tz-aware UTC datetime (fail-closed on NaN/invalid)."""
    val = float(ts_ms)
    if not math.isfinite(val):
        raise ValueError("INVALID_TS_QX: non-finite timestamp")
    return datetime.datetime.fromtimestamp(val / 1000.0,
                                           tz=datetime.timezone.utc)


def hour_float(ts_utc: datetime.datetime) -> float:
    """§4.1 ``_hour_float``: fractional UTC hour of ``ts``."""
    if not isinstance(ts_utc, datetime.datetime):
        raise ValueError("ts_utc must be datetime")
    return (ts_utc.hour + ts_utc.minute / 60.0
            + ts_utc.second / 3600.0 + ts_utc.microsecond / 3.6e9)


def rollover_is_active(ts_utc: datetime.datetime,
                       rollover_windows: Optional[Sequence[Dict[str, Any]]]
                       ) -> bool:
    """§3.1 rollover: ONLY when the canonical exchange configuration marks
    the interval.  Default configuration is empty ⇒ never active; no hidden
    CME dependency (ISSUE-CP5-020)."""
    for cfg in (rollover_windows or []):
        weekdays = set(int(w) for w in cfg.get("weekdays", []))
        start_h = float(cfg.get("start_h", 0.0))
        end_h = float(cfg.get("end_h", 0.0))
        if end_h <= start_h:
            raise ValueError(
                f"CONFIGURATION_INVALID: rollover interval [{start_h},"
                f"{end_h}) must be non-empty and ordered")
        if ts_utc.weekday() in weekdays and start_h <= hour_float(ts_utc) < end_h:
            return True
    return False


def utc_activity_window_of(ts_utc: datetime.datetime,
                           rollover_windows: Optional[Sequence[Dict[str, Any]]]
                           = None) -> Dict[str, Any]:
    """§4.1 ``utc_activity_window_of`` — O(1), exact pseudocode semantics.

    Naive datetimes are adopted as UTC; OVERLAP is a derived flag; ROLLOVER
    is orthogonal to primary routing (ISSUE-CP5-020).
    """
    if not isinstance(ts_utc, datetime.datetime):
        raise ValueError("ts_utc must be datetime")
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=datetime.timezone.utc)
    elif ts_utc.utcoffset() != datetime.timedelta(0):
        raise ValueError("NON_UTC_TIMESTAMP_QX: E12 is UTC-only (§3.1)")
    h = hour_float(ts_utc)
    overlap = OVERLAP_WINDOW[0] <= h < OVERLAP_WINDOW[1]
    temporal_window: Optional[str] = None
    for name in PRIMARY_WINDOWS:
        lo, hi = UTC_ACTIVITY_WINDOWS[name]
        if lo <= h < hi:
            temporal_window = name
            break
    if temporal_window is None:
        raise ValueError("UTC_ACTIVITY_WINDOW_UNMAPPED")
    if temporal_window == "UTC_W1":
        sub = "EARLY" if h < 8.0 else ("LATE" if h >= 11.5 else "MID")
    elif temporal_window == "UTC_W2":
        sub = "EARLY" if h < 13.0 else ("LATE" if h >= 20.5 else "MID")
    else:
        sub = "MID"
    return {"temporal_window": temporal_window, "window_phase": sub,
            "is_overlap": overlap,
            "rollover_active": rollover_is_active(ts_utc, rollover_windows)}


def day_type(ts_utc: datetime.datetime,
             econ_calendar_red_days: Optional[Any] = None) -> str:
    """§4.1 ``day_type`` — HIGH_IMPACT > FRIDAY > SATURDAY_SUNDAY_CONTEXT >
    WEEKDAY.  Red days may be ``datetime.date`` or ISO-date strings; the
    calendar is flag-only (§1.4/I-3: content never used for prediction)."""
    d = ts_utc.date()
    if econ_calendar_red_days is not None:
        red = set()
        for item in econ_calendar_red_days:
            if isinstance(item, str):
                red.add(datetime.date.fromisoformat(item.strip()))
            elif isinstance(item, datetime.datetime):
                red.add(item.date())
            elif isinstance(item, datetime.date):
                red.add(item)
            else:
                raise ValueError("CONFIGURATION_INVALID: red-day entries "
                                 "must be date/datetime/ISO-string")
        if d in red:
            return "HIGH_IMPACT"
    wd = ts_utc.weekday()
    if wd == 4:
        return "FRIDAY"
    if wd >= 5:
        return "SATURDAY_SUNDAY_CONTEXT"
    return "WEEKDAY"


def tod_bin(h: float, n_bins: int = N_BINS_DEFAULT) -> int:
    """§2 ToD bin ``n = floor(h·N/24) mod N``."""
    if not (0.0 <= h < 24.0) or not math.isfinite(h):
        raise ValueError(f"INVALID_TOD_BIN_QX: hour {h!r} outside [0, 24)")
    n_bins = int(n_bins)
    if n_bins < 1:
        raise ValueError("CONFIGURATION_INVALID: fff_bins must be >= 1")
    return int(math.floor(h * n_bins / 24.0)) % n_bins


def window_progress(h: float, window: str) -> float:
    """§9 ``utc_window_progress`` ∈ [0, 1]: fraction elapsed inside σ(t)."""
    lo, hi = UTC_ACTIVITY_WINDOWS[window]
    return max(0.0, min(1.0, (h - lo) / (hi - lo)))


def is_core_window(h: float) -> bool:
    """``is_utc_activity_window``: inside UTC_W1_CORE ∪ UTC_W2_CORE (§4.1)."""
    return any(lo <= h < hi for lo, hi in UTC_CORE_WINDOWS.values())


# ---------------------------------------------------------------------------
# §3.2 — FFF seasonal profile (squared-magnitude estimator, corrected)
# ---------------------------------------------------------------------------
def fff_seasonal(returns_by_tod: Dict[int, List[float]],
                 use_sqrt: bool = False) -> Dict[int, float]:
    """§4.1 ``fff_seasonal`` — corrected squared-magnitude estimator:

    ``ŝ_n = mean_r2_n / mean_r2_grand``, clamped to [0.1, 10] and
    renormalized so ``(1/N)Σŝ_n = 1`` (§3.2).  The biased absolute-value
    estimator is forbidden (ISSUE-CP5-024): ``use_sqrt=True`` fails closed.
    """
    if use_sqrt:
        raise ValueError("FFF_ABS_ESTIMATOR_FORBIDDEN: the absolute-value "
                         "seasonal estimator is biased (§3.2/§11(a)) and "
                         "must never be used — squared-magnitude only")
    if not returns_by_tod:
        return {}
    all_r2: List[float] = []
    for rs in returns_by_tod.values():
        all_r2.extend([r * r for r in rs
                       if isinstance(r, (float, int)) and math.isfinite(r)])
    if len(all_r2) < 10:
        return {k: 1.0 for k in returns_by_tod.keys()}
    grand_mean_r2 = sum(all_r2) / len(all_r2)
    if grand_mean_r2 < 1e-12:
        grand_mean_r2 = 1e-12
    out: Dict[int, float] = {}
    for n, rs in returns_by_tod.items():
        valid = [r for r in rs if math.isfinite(r)]
        if len(valid) == 0:
            out[n] = 1.0
            continue
        mean_r2_n = sum(r * r for r in valid) / len(valid)
        s_hat = mean_r2_n / grand_mean_r2
        s_hat = max(SEASONAL_CLAMP[0], min(SEASONAL_CLAMP[1], s_hat))
        out[int(n)] = float(s_hat)
    if out:
        avg = sum(out.values()) / len(out)
        if avg != 0:
            out = {k: v / avg for k, v in out.items()}
    return out


def seasonal_profile_available(returns_by_tod: Dict[int, List[float]]
                               ) -> Tuple[bool, str]:
    """§3.2 PIT edge: ``T < 30`` or ``mean_r2_grand < 1e-12`` ⇒
    ``seasonal_factor = UNAVAILABLE``, quality Q1."""
    if not returns_by_tod:
        return False, "NO_HISTORY"
    lengths = [len([r for r in rs if math.isfinite(r)])
               for rs in returns_by_tod.values()]
    t_days = min(lengths) if lengths else 0
    if t_days < 30:
        return False, "T_BELOW_30"
    all_r2 = [r * r for rs in returns_by_tod.values() for r in rs
              if math.isfinite(r)]
    grand = (sum(all_r2) / len(all_r2)) if all_r2 else 0.0
    if grand < 1e-12:
        return False, "GRAND_MEAN_R2_DEGENERATE"
    return True, "OK"


def deseasonalize(r: float, s_hat: float) -> float:
    """§3.2 ``r* = r / ŝ_n`` (ŝ is clamped ⇒ strictly positive)."""
    s_hat = float(s_hat)
    if not math.isfinite(s_hat) or s_hat <= EPS:
        raise ValueError("INVALID_SEASONAL_FACTOR_QX: ŝ must be finite > 0")
    return float(r) / s_hat


def fourier_smooth_factors(factors: Dict[int, float],
                           n_bins: int = N_BINS_DEFAULT,
                           fourier_k: int = FOURIER_K_DEFAULT
                           ) -> Dict[int, float]:
    """§3.2 FFF flexible-Fourier smoothing
    ``f(θ_n) = μ + Σ_{k=1..K}[λ_k cos kθ_n + δ_k sin kθ_n]``, θ_n = 2πn/N,
    fit by least squares over the bins present in ``factors``."""
    if not factors:
        return {}
    fourier_k = int(fourier_k)
    if fourier_k < 0 or fourier_k > 8:
        raise ValueError("CONFIGURATION_INVALID: fff_fourier_K outside [0,8]")
    bins = sorted(int(b) for b in factors)
    y = np.array([float(factors[b]) for b in bins], dtype=float)
    theta = 2.0 * math.pi * np.array(bins, dtype=float) / float(n_bins)
    cols = [np.ones_like(theta)]
    for k in range(1, fourier_k + 1):
        cols.append(np.cos(k * theta))
        cols.append(np.sin(k * theta))
    design = np.column_stack(cols)
    if len(bins) < design.shape[1]:
        # under-determined ⇒ no smoothing possible; fail closed
        raise ValueError("CONFIGURATION_INVALID: fourier smoothing needs at "
                         f"least {design.shape[1]} populated bins, got "
                         f"{len(bins)}")
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ coef
    return {b: float(v) for b, v in zip(bins, fitted)}


def winsorize(values: Sequence[float], level: float = 0.05) -> List[float]:
    """§3.1 gap edge: FFF winsorizes log-returns at the 5% level."""
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if not vals or not (0.0 < level < 0.5):
        return list(vals)
    lo = float(np.quantile(np.array(vals), level))
    hi = float(np.quantile(np.array(vals), 1.0 - level))
    return [max(lo, min(hi, v)) for v in vals]


# ---------------------------------------------------------------------------
# §3.3 — conditional rates, Wilson CI; §3.4 — intraday momentum beta
# ---------------------------------------------------------------------------
def wilson_ci(k: int, n: int, z: float = WILSON_Z
              ) -> Optional[Tuple[float, float]]:
    """§3.3 Wilson interval; ``n < 30`` ⇒ None (INSUFFICIENT_SAMPLE ⇒ Q1)."""
    k, n = int(k), int(n)
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"INVALID_WILSON_INPUT_QX: k={k}, n={n}")
    if n < 30:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    delta = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return (max(0.0, (centre - delta) / denom),
            min(1.0, (centre + delta) / denom))


def conditional_rate(Y_events: List[bool], keys: List[str], key: str,
                     min_samples: int = 30
                     ) -> Tuple[Optional[float], int,
                                Optional[Tuple[float, float]]]:
    """§4.1 ``conditional_rate`` — exact pseudocode: ``n < min_samples`` ⇒
    ``(None, n, None)`` (rate = null, Q1, INSUFFICIENT_SAMPLE)."""
    if len(Y_events) != len(keys):
        raise ValueError("CONFIGURATION_INVALID: conditional_rate length "
                         "mismatch between Y_events and keys")
    n = sum(1 for k in keys if k == key)
    if n < int(min_samples):
        return None, n, None
    k = sum(1 for i in range(len(keys)) if keys[i] == key and Y_events[i])
    p = k / n if n > 0 else None
    z = WILSON_Z
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    delta = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    lo = (centre - delta) / denom
    hi = (centre + delta) / denom
    return p, n, (max(0.0, lo), min(1.0, hi))


def condition_key(temporal_window: str, bin_id: int, dtype: str) -> str:
    """C = temporal_window ∧ tod_bin ∧ day_type (§3.3)."""
    return f"{temporal_window}|{int(bin_id)}|{dtype}"


def intraday_momentum_beta(open_returns: List[float],
                           fwd_returns: List[float]
                           ) -> Tuple[Optional[float], float]:
    """§4.1 ``intraday_momentum_beta`` — ``β̂ = Cov(r_open, r_fwd)/Var(r_open)``
    fit on past days only; ``< 20`` clean samples ⇒ ``(None, 0.0)``."""
    clean = [(o, f) for o, f in zip(open_returns, fwd_returns)
             if math.isfinite(o) and math.isfinite(f)]
    if len(clean) < 20:
        return None, 0.0
    xs, ys = zip(*clean)
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var = sum((x - mx) ** 2 for x in xs)
    if var < 1e-12:
        return 0.0, 0.0
    return cov / var, var


def vol_ratio(volume: float, window_volumes: Sequence[float]
              ) -> Optional[float]:
    """§2 ``VR = V_t / mean(V_window, 180d)``; V = 0 or empty/degenerate
    history ⇒ ``None`` (⇒ ``vol_ratio = null``, quality Q1, §3.1)."""
    v = float(volume)
    if not math.isfinite(v) or v <= 0.0:
        return None
    hist = [float(x) for x in window_volumes if math.isfinite(float(x))]
    if not hist:
        return None
    mean_v = sum(hist) / len(hist)
    if mean_v <= EPS:
        return None
    return v / mean_v


def range_z(range_t: float, hist_ranges: Sequence[float]
            ) -> Optional[float]:
    """§2 ``Z_R = (Range_t − μ_Range)/σ_Range``; degenerate history ⇒ None."""
    hist = [float(x) for x in hist_ranges if math.isfinite(float(x))]
    if len(hist) < 2 or not math.isfinite(float(range_t)):
        return None
    mu = float(np.mean(hist))
    sd = float(np.std(hist))
    if sd <= EPS:
        return None
    return (float(range_t) - mu) / sd


def y_vol(vr: Optional[float], threshold: float = 1.5) -> bool:
    """§3.3 ``Y_vol = I[VR > 1.5]`` (null VR ⇒ False; §9 step 5: VR = 1.5 is
    NOT > 1.5)."""
    return vr is not None and float(vr) > float(threshold)


def y_range(z_r: Optional[float], threshold: float = 1.5) -> bool:
    """§3.3 ``Y_range = I[Z_Range > 1.5]``."""
    return z_r is not None and float(z_r) > float(threshold)


# ---------------------------------------------------------------------------
# §3.6/§4.2 — Kruskal–Wallis and Spearman, in-tree (ISSUE-CP5-025: scipy is
# not an SBOM pin).  χ² survival via the regularized upper incomplete gamma
# (series for x < a+1, Legendre continued fraction otherwise).
# ---------------------------------------------------------------------------
def _gammq(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x) = 1 − P(a, x), a>0, x≥0."""
    if a <= 0.0 or x < 0.0:
        raise ValueError(f"INVALID_GAMMA_INPUT_QX: a={a}, x={x}")
    if x == 0.0:
        return 1.0
    if x < a + 1.0:                                    # series for P
        ap = a
        total = 1.0 / a
        delta = total
        for _ in range(1000):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-16:
                break
        p = total * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - p))
    # Legendre continued fraction for Q
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return max(0.0, min(1.0, q))


def chi2_sf(x: float, df: int) -> float:
    """χ² survival function P(X > x) = Q(df/2, x/2)."""
    if df < 1:
        raise ValueError(f"INVALID_CHI2_DF_QX: df={df}")
    if not math.isfinite(x) or x < 0.0:
        raise ValueError(f"INVALID_CHI2_INPUT_QX: x={x}")
    return _gammq(df / 2.0, x / 2.0)


def _mid_ranks(values: Sequence[float]) -> List[float]:
    """Average (mid-)ranks with tie handling — 1-based."""
    order = sorted(range(len(values)), key=lambda i: float(values[i]))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while (j + 1 < len(order)
               and float(values[order[j + 1]]) == float(values[order[i]])):
            j += 1
        avg = (i + j) / 2.0 + 1.0                      # 1-based mid-rank
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def kruskal_wallis(groups: List[List[float]]) -> Dict[str, Any]:
    """§3.6 Kruskal–Wallis with tie correction:
    ``H = 12/(N(N+1)) Σ R_k²/n_k − 3(N+1)``, ``H ~ χ²_{K−1}`` under H0."""
    clean = [[float(v) for v in g if math.isfinite(float(v))]
             for g in groups]
    if len(clean) < 2 or any(len(g) == 0 for g in clean):
        raise ValueError("CONFIGURATION_INVALID: kruskal_wallis needs >= 2 "
                         "non-empty groups")
    flat = [v for g in clean for v in g]
    ranks = _mid_ranks(flat)
    n_total = len(flat)
    k_groups = len(clean)
    h = 0.0
    idx = 0
    tie_terms = 0.0
    for g in clean:
        r_k = sum(ranks[idx:idx + len(g)])
        h += r_k * r_k / len(g)
        # tie groups within this slice contribute to the global correction
        idx += len(g)
    h = 12.0 / (n_total * (n_total + 1.0)) * h - 3.0 * (n_total + 1.0)
    # tie correction over the whole pooled sample
    sorted_vals = sorted(flat)
    i = 0
    while i < len(sorted_vals):
        j = i
        while j + 1 < len(sorted_vals) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        t = j - i + 1
        if t > 1:
            tie_terms += t ** 3 - t
        i = j + 1
    denom = 1.0 - tie_terms / (n_total ** 3 - n_total) if n_total > 1 else 1.0
    if denom <= EPS:
        raise ValueError("DEGENERATE_TIE_STRUCTURE_QX: all values identical")
    h /= denom
    df = k_groups - 1
    p = chi2_sf(h, df)
    return {"H": float(h), "p": float(p), "significant": bool(p < 0.05),
            "df": df, "n": n_total}


def test_temporal_window_difference(groups: List[List[float]]
                                    ) -> Dict[str, Any]:
    """§4.2 ``test_temporal_window_difference`` — Kruskal–Wallis wrapper."""
    res = kruskal_wallis(groups)
    return {"H": res["H"], "p": res["p"], "significant": res["significant"]}


def spearman_rho(a: Sequence[float], b: Sequence[float]) -> float:
    """§3.6 Spearman ρ_s — Pearson correlation of mid-ranks (identical to
    ``1 − 6Σd²/(N(N²−1))`` in the tie-free case; ties handled correctly)."""
    if len(a) != len(b):
        raise ValueError("CONFIGURATION_INVALID: spearman length mismatch")
    if len(a) < 2:
        raise ValueError("CONFIGURATION_INVALID: spearman needs >= 2 points")
    ra, rb = _mid_ranks([float(x) for x in a]), _mid_ranks([float(x) for x in b])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va <= EPS or vb <= EPS:
        raise ValueError("DEGENERATE_RANK_STRUCTURE_QX: constant profile")
    return cov / math.sqrt(va * vb)


def profile_stability(profiles: List[Dict[int, float]]) -> Dict[str, Any]:
    """§4.2 ``profile_stability`` — consecutive-profile Spearman ρ list.

    §3.6 stability law: mean ρ_s over rolling windows; ``ρ_s > 0.6`` ⇒
    STABLE, Q3-eligible."""
    rhos: List[float] = []
    for i in range(len(profiles) - 1):
        a_keys = sorted(profiles[i])
        b_keys = sorted(profiles[i + 1])
        if a_keys != b_keys:
            raise ValueError("CONFIGURATION_INVALID: stability profiles must "
                             "cover identical bin sets")
        a = [profiles[i][k] for k in a_keys]
        b = [profiles[i + 1][k] for k in b_keys]
        rhos.append(spearman_rho(a, b))
    return {"mean_spearman": (sum(rhos) / len(rhos)) if rhos else 0.0,
            "rhos": rhos}


# ---------------------------------------------------------------------------
# §5 — identity, quality, profile artifact
# ---------------------------------------------------------------------------
def _canonical_safe(obj: Any) -> Any:
    """canonical_json forbids NaN/Inf; sanitize raw input floats (NaN/Inf ⇒
    None) so Q0 payloads remain hashable and deterministic."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _canonical_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonical_safe(v) for v in obj]
    return obj


def make_snapshot_id(content: Dict[str, Any]) -> str:
    """§4.1/§5.5 canonical E12 snapshot identity (SHA-256 over canonical
    JSON of the governed payload; ``snapshot_id`` itself excluded)."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION,
                                 _canonical_safe(content))


def deterministic_replay_check(build: Any) -> bool:
    """§8.2: rebuilding from the same inputs yields byte-identical output."""
    a = canonical_json(build())
    b = canonical_json(build())
    return a == b


def no_future_leak_check(returns_by_tod: Dict[int, List[float]]) -> bool:
    """§8.3: the seasonal profile depends only on bin membership, never on
    sample ORDER or future timestamps ⇒ order-shuffled inputs must reproduce
    identical factors."""
    base = fff_seasonal(returns_by_tod)
    shuffled = {n: list(rs) for n, rs in returns_by_tod.items()}
    rng = np.random.default_rng(20240315)
    for rs in shuffled.values():
        arr = np.array(rs, dtype=float)
        rng.shuffle(arr)
        rs[:] = [float(x) for x in arr]
    return canonical_json({str(k): round(v, 12) for k, v in base.items()}) \
        == canonical_json({str(k): round(v, 12)
                           for k, v in fff_seasonal(shuffled).items()})


def compute_temporal_profile(returns_by_tod: Dict[int, List[float]],
                             as_of: int,
                             cond_events: Optional[Dict[str, Tuple[List[bool],
                                                                   List[str]]]]
                             = None,
                             open_returns_by_window: Optional[Dict[str,
                                                                   List[float]]]
                             = None,
                             fwd_returns_by_window: Optional[Dict[str,
                                                                  List[float]]]
                             = None,
                             window_groups: Optional[List[List[float]]] = None,
                             profiles_history: Optional[List[Dict[int, float]]]
                             = None,
                             min_samples: int = 30,
                             n_bins: int = N_BINS_DEFAULT,
                             fourier_k: int = FOURIER_K_DEFAULT,
                             params: Optional[EngineParams] = None
                             ) -> Dict[str, Any]:
    """§5.3 ``TemporalProfile_v4`` builder (PIT: inputs are history ≤ t−1).

    Quality ladder (§5.5): UNAVAILABLE ⇒ Q1; profile exists with T ≥ 30 ⇒
    Q2; + Kruskal p < 0.05 + mean Spearman > 0.6 ⇒ Q3; + deterministic
    replay + no-future-leak + every Wilson width < 0.3 ⇒ Q4.
    """
    p = params or EngineParams()
    as_of = int(as_of)
    available, why = seasonal_profile_available(returns_by_tod)
    seasonal: Optional[Dict[int, float]] = None
    smoothed: Optional[Dict[int, float]] = None
    if available:
        seasonal = fff_seasonal(returns_by_tod)
        if len(seasonal) >= 2 * int(fourier_k) + 2:
            smoothed = fourier_smooth_factors(seasonal, n_bins=n_bins,
                                              fourier_k=int(fourier_k))
    rates: Dict[str, Dict[str, Any]] = {}
    for y_name, (events, keys) in (cond_events or {}).items():
        uniq = sorted(set(keys))
        for key in uniq:
            p_hat, n, ci = conditional_rate(list(events), list(keys), key,
                                            min_samples=int(min_samples))
            rates[f"{y_name}|{key}"] = {
                "p": (round(p_hat, 12) if p_hat is not None else None),
                "n": int(n),
                "ci": ([round(ci[0], 12), round(ci[1], 12)] if ci else None),
                "status": ("OK" if p_hat is not None else
                           "INSUFFICIENT_SAMPLE"),
            }
    betas: Dict[str, Optional[float]] = {}
    for window in sorted(set(list(open_returns_by_window or {})
                             + list(fwd_returns_by_window or {}))):
        beta, _var = intraday_momentum_beta(
            list((open_returns_by_window or {}).get(window, [])),
            list((fwd_returns_by_window or {}).get(window, [])))
        betas[window] = (round(beta, 12) if beta is not None else None)
    kruskal_p: Optional[float] = None
    kruskal_h: Optional[float] = None
    if window_groups and len(window_groups) >= 2 \
            and all(len(g) > 0 for g in window_groups):
        res = kruskal_wallis(window_groups)
        kruskal_p, kruskal_h = res["p"], res["H"]
    stab = profile_stability(profiles_history or [])
    mean_rho = float(stab["mean_spearman"])
    if not available:
        quality = "Q1"
    else:
        quality = "Q2"
        if kruskal_p is not None and kruskal_p < 0.05 and mean_rho > 0.6:
            quality = "Q3"
            widths_ok = all(
                (entry["ci"][1] - entry["ci"][0]) < 0.3
                for entry in rates.values() if entry["ci"])
            replay_ok = deterministic_replay_check(
                lambda: {str(k): round(v, 12) for k, v in
                         fff_seasonal(returns_by_tod).items()})
            leak_ok = no_future_leak_check(returns_by_tod)
            if widths_ok and replay_ok and leak_ok:
                quality = "Q4"
    content = {
        "version": CONTRACT_VERSION,
        "as_of": as_of,
        "seasonal_status": ("OK" if available else f"UNAVAILABLE:{why}"),
        "seasonal_factors": ({str(k): round(v, 12) for k, v in seasonal.items()}
                             if seasonal else None),
        "seasonal_factors_smoothed": (
            {str(k): round(v, 12) for k, v in smoothed.items()}
            if smoothed else None),
        "conditional_rates": rates,
        "momentum_betas": betas,
        "stability": {"mean_spearman": round(mean_rho, 12),
                      "kruskal_p": (round(kruskal_p, 12)
                                    if kruskal_p is not None else None),
                      "kruskal_H": (round(kruskal_h, 12)
                                    if kruskal_h is not None else None),
                      "rhos": [round(r, 12) for r in stab["rhos"]]},
        "quality": quality,
        "param_hash": param_hash(p),
    }
    content["snapshot_id"] = make_snapshot_id(
        {"engine": ENGINE_ID, "artifact": "TemporalProfile_v4",
         "content": {k: v for k, v in content.items()}})
    return content


def returns_by_tod_from_candles(candles: Sequence[Dict[str, Any]],
                                n_bins: int = N_BINS_DEFAULT,
                                winsor_level: float = 0.05
                                ) -> Dict[int, List[float]]:
    """History adapter: candle series (``ts``, ``c``) → per-bin log returns,
    winsorized at the 5% level (§3.1 gap edge).  PIT: callers pass history
    ``≤ t−1`` only."""
    ordered = sorted(candles, key=lambda c: float(c["ts"]))
    per_bin: Dict[int, List[float]] = {}
    for prev, cur in zip(ordered, ordered[1:]):
        c_prev = float(prev.get("c", prev.get("C", 0.0)))
        c_cur = float(cur.get("c", cur.get("C", 0.0)))
        if c_prev <= 0.0 or c_cur <= 0.0:
            continue
        r = math.log(c_cur / c_prev)
        ts = ts_from_ms(float(cur["ts"]))
        b = tod_bin(hour_float(ts), n_bins)
        per_bin.setdefault(b, []).append(r)
    return {b: winsorize(rs, winsor_level) for b, rs in per_bin.items()}


def load_v3_temporal_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """§8.7 read-only v3 migration adapter: a v3 payload may be read ONLY
    through this adapter, which emits the canonical v4.0.0 representation.
    Fail-closed on every non-conforming field."""
    if not isinstance(payload, dict):
        return {"quality": "QX", "reason": "V3_PAYLOAD_NOT_OBJECT_QX"}
    window = payload.get("window")
    alias = {"W0": "UTC_W0", "W1": "UTC_W1", "W2": "UTC_W2", "W3": "UTC_W3"}
    window = alias.get(str(window), window)
    if window not in PRIMARY_WINDOWS:
        return {"quality": "QX",
                "reason": f"V3_WINDOW_UNKNOWN_QX:{payload.get('window')!r}"}
    dtype = payload.get("daytype")
    if dtype not in DAY_TYPES:
        return {"quality": "QX",
                "reason": f"V3_DAYTYPE_UNKNOWN_QX:{payload.get('daytype')!r}"}
    snap = str(payload.get("snapshot_id") or "")
    if len(snap) != 64 or any(ch not in "0123456789abcdef" for ch in snap):
        return {"quality": "QX", "reason": "V3_SNAPSHOT_ID_INVALID_QX"}
    try:
        bin_id = int(payload["tod"])
        ts_ms = int(payload["ts"])
    except (KeyError, TypeError, ValueError):
        return {"quality": "QX", "reason": "V3_REQUIRED_FIELD_MISSING_QX"}
    if not (0 <= bin_id <= 95) or not math.isfinite(float(ts_ms)):
        return {"quality": "QX", "reason": "V3_FIELD_RANGE_QX"}
    return {"version": CONTRACT_VERSION, "temporal_window": window,
            "day_type": dtype, "tod_bin": bin_id, "ts_ms": ts_ms,
            "v3_snapshot_id": snap, "migrated": True, "quality": "Q1",
            "reason": "V3_MIGRATED_READ_ONLY"}


STATE_REQUIRED: Tuple[str, ...] = (
    "version", "temporal_window", "window_phase", "day_type", "tod_state",
    "quality", "as_of", "snapshot_id")
TOD_STATE_REQUIRED: Tuple[str, ...] = (
    "hour_utc", "minute", "weekday", "tod_bin", "utc_window_progress")


def validate_state_schema(state: Dict[str, Any]) -> List[str]:
    """§5.2 TemporalContextState_v4 validator → list of violations (empty =
    conforming).  Runtime-only fields (``reason``, ``fate``,
    ``is_overlap``, ``is_utc_activity_window``, ``rollover_active``,
    ``historical_behavior``) are checked when present."""
    errs: List[str] = []
    for key in STATE_REQUIRED:
        if key not in state:
            errs.append(f"missing required key: {key}")
    if errs:
        return errs
    if state["version"] != CONTRACT_VERSION:
        errs.append(f"version must be {CONTRACT_VERSION}")
    if state["temporal_window"] not in PRIMARY_WINDOWS:
        errs.append(f"temporal_window not in registry: "
                    f"{state['temporal_window']!r}")
    if state["window_phase"] not in PHASES:
        errs.append(f"window_phase invalid: {state['window_phase']!r}")
    if state["day_type"] not in DAY_TYPES:
        errs.append(f"day_type invalid: {state['day_type']!r}")
    if state["quality"] not in QUALITY_TAGS:
        errs.append(f"quality invalid: {state['quality']!r}")
    tod = state["tod_state"]
    if not isinstance(tod, dict):
        errs.append("tod_state must be an object")
    else:
        for key in TOD_STATE_REQUIRED:
            if key not in tod:
                errs.append(f"tod_state missing: {key}")
        if not errs:
            if not (0.0 <= float(tod["hour_utc"]) <= 23.999):
                errs.append("hour_utc outside [0, 23.999]")
            if not (0 <= int(tod["minute"]) <= 59):
                errs.append("minute outside [0, 59]")
            if not (0 <= int(tod["weekday"]) <= 6):
                errs.append("weekday outside [0, 6]")
            if not (0 <= int(tod["tod_bin"]) <= 95):
                errs.append("tod_bin outside [0, 95]")
            if not (0.0 <= float(tod["utc_window_progress"]) <= 1.0):
                errs.append("utc_window_progress outside [0, 1]")
    if not isinstance(state["as_of"], int) or state["as_of"] <= 0:
        errs.append("as_of must be a positive epoch-ms integer")
    snap = str(state["snapshot_id"])
    if len(snap) != 64 or any(ch not in "0123456789abcdef" for ch in snap):
        errs.append("snapshot_id must be 64-hex sha256")
    if "fate" in state and state["fate"] not in FATE_VALUES:
        errs.append(f"fate invalid: {state['fate']!r}")
    for flag in ("is_overlap", "is_utc_activity_window", "rollover_active"):
        if flag in state and not isinstance(state[flag], bool):
            errs.append(f"{flag} must be boolean")
    return errs


def serialize_state(state: Dict[str, Any], ndigits: int = 6) -> Dict[str, Any]:
    """Deterministic serialization of a TemporalContextState (floats rounded
    to ``ndigits``; snapshot_id kept full-precision)."""
    def rec(v: Any) -> Any:
        if isinstance(v, float):
            return round(v, ndigits)
        if isinstance(v, dict):
            return {str(k): rec(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [rec(x) for x in v]
        return v
    out = rec(dict(state))
    if "snapshot_id" in state:
        out["snapshot_id"] = str(state["snapshot_id"])
    return out


# ---------------------------------------------------------------------------
# §4.1 — the streaming engine
# ---------------------------------------------------------------------------
class TemporalWindowEngineStream:
    """§4.1 ``TemporalWindowEngineStream`` extended to the full §5.2 state
    (ISSUE-CP5-027) with fate tracking (§5.4) and profile attachment."""

    def __init__(self, behavior_window: int = 180, min_samples: int = 30,
                 params: Optional[EngineParams] = None,
                 rollover_windows: Optional[Sequence[Dict[str, Any]]] = None,
                 n_bins: int = N_BINS_DEFAULT) -> None:
        p = params or EngineParams()
        self.params = p
        self.behavior_window = int(behavior_window)
        if not (30 <= self.behavior_window <= 365):
            raise ValueError("CONFIGURATION_INVALID: behavior_window outside "
                             "§6 range [30, 365]")
        self.min_samples = int(min_samples)
        self.n_bins = int(n_bins)
        self.rollover_windows = list(rollover_windows or [])
        self.buffer: List[Dict[str, Any]] = []
        self.seasonal_cache: Dict[int, float] = {}
        self.last_snapshot: Optional[str] = None
        self.profile: Optional[Dict[str, Any]] = None
        self.levels: Optional[Dict[str, Any]] = None
        self._prev_ts: Optional[int] = None
        self._prev_as_of: Optional[int] = None
        self._prev_state: Optional[Dict[str, Any]] = None

    # -- profile / context attachment -------------------------------------
    def attach_profile(self, profile: Dict[str, Any]) -> None:
        if profile.get("version") != CONTRACT_VERSION:
            raise ValueError("CONTRACT_MISMATCH_QX: profile is not v4.0.0")
        self.profile = profile
        self.seasonal_cache = {
            int(k): float(v)
            for k, v in (profile.get("seasonal_factors") or {}).items()}

    def attach_levels(self, levels: Dict[str, Any]) -> None:
        """E02 ``TemporalWindowLevels_v4`` optional context (§1.5, O-4)."""
        self.levels = dict(levels)

    # -- per-candle core ----------------------------------------------------
    def on_candle(self, candle: Dict[str, Any],
                  econ_calendar: Optional[Any] = None) -> Dict[str, Any]:
        availability_time_ms = candle.get("availability_time_ms")
        if availability_time_ms is None:
            # §5.5: missing required availability metadata is
            # configuration-invalid / fail-closed (no local −1 ms fallback).
            return {"quality": "QX",
                    "reason": "CONFIGURATION_INVALID: missing "
                              "availability_time_ms"}
        as_of = int(availability_time_ms)
        raw_ts = candle.get("ts")
        try:
            ts_val = float(raw_ts)
        except (TypeError, ValueError):
            ts_val = float("nan")
        h_l_invalid = False
        try:
            h_l_invalid = (float(candle["H"]) < float(candle["L"])
                           or float(candle["V"]) < 0)
        except (KeyError, TypeError, ValueError):
            h_l_invalid = True
        if not math.isfinite(ts_val) or h_l_invalid:
            reason = ("INVALID_TS" if not math.isfinite(ts_val)
                      else "INVALID_CANDLE")
            invalid_state = {"quality": "Q0", "reason": reason}
            payload = {"engine": ENGINE_ID,
                       "contract_version": CONTRACT_VERSION,
                       "input": candle, "state": invalid_state}
            snap = make_snapshot_id(payload)
            out = {"version": CONTRACT_VERSION, "quality": "Q0",
                   "reason": reason, "snapshot_id": snap,
                   "fate": "INVALIDATED", "as_of": as_of}
            self.last_snapshot = snap
            return out
        # duplicate (ts, as_of) ⇒ idempotent replay of the prior state
        ts_ms = int(ts_val)
        if (self._prev_ts == ts_ms and self._prev_as_of == as_of
                and self._prev_state is not None):
            return dict(self._prev_state)
        ts = ts_from_ms(ts_ms)
        window_ctx = utc_activity_window_of(ts, self.rollover_windows)
        dtype = day_type(ts, econ_calendar)
        h = hour_float(ts)
        bin_id = tod_bin(h, self.n_bins)
        window = str(window_ctx["temporal_window"])
        prev = self.buffer[-1] if self.buffer else None
        gap = self._gap_detected(candle, prev)
        vr = self._vol_ratio_for(candle, window)
        st: Dict[str, Any] = {
            "version": CONTRACT_VERSION,
            "temporal_window": window,
            "window_phase": window_ctx["window_phase"],
            "tod_state": {
                "hour_utc": round(h, 9),
                "minute": int(ts.minute),
                "weekday": int(ts.weekday()),
                "tod_bin": int(bin_id),
                "utc_window_progress": round(window_progress(h, window), 12),
            },
            "day_type": dtype,
            "is_utc_activity_window": bool(is_core_window(h)),
            "is_overlap": bool(window_ctx["is_overlap"]),
            "rollover_active": bool(window_ctx["rollover_active"]),
            "is_gap": bool(gap),
            "vol_ratio": (round(vr, 12) if vr is not None else None),
            "historical_behavior": self._historical_behavior(window, bin_id,
                                                             dtype),
            "as_of": as_of,
            "quality": self._quality_for(candle, vr),
            "reason": None,
            "fate": "ACTIVE",
        }
        if float(candle["V"]) == 0.0:
            st["reason"] = "V_ZERO"          # §3.1: VolRatio undefined ⇒ Q1
        canonical_snapshot_payload = {
            "engine": ENGINE_ID,
            "contract_version": CONTRACT_VERSION,
            "input": candle,
            "state": st,
        }
        snap = make_snapshot_id(canonical_snapshot_payload)
        st["snapshot_id"] = snap
        self.buffer.append({**candle, **st, "ts_ms": ts_ms,
                            "window": window, "bin": bin_id,
                            "day_type_key": dtype})
        cap = self.behavior_window * self.n_bins
        if len(self.buffer) > cap:
            self.buffer = self.buffer[-cap:]
        if self._prev_state is not None and \
                self._prev_state.get("fate") == "ACTIVE":
            # §5.4 fate transition: the replaced state object itself becomes
            # SUPERSEDED (mutation is post-hash lifecycle metadata; the
            # snapshot binds the state as emitted).
            self._prev_state["fate"] = "SUPERSEDED"
        self._prev_ts, self._prev_as_of = ts_ms, as_of
        self.last_snapshot = snap
        self._prev_state = st
        return st

    # -- internals ----------------------------------------------------------
    def _quality_for(self, candle: Dict[str, Any],
                     vr: Optional[float]) -> str:
        """§5.5 ladder: Q0 handled by caller; V=0 ⇒ Q1 (raw degradation);
        no profile ⇒ Q1; else the profile's calibrated quality."""
        if float(candle["V"]) == 0.0:
            return "Q1"
        if self.profile is None:
            return "Q1"
        pq = str(self.profile.get("quality", "Q1"))
        return pq if pq in ("Q2", "Q3", "Q4") else "Q1"

    def _gap_detected(self, candle: Dict[str, Any],
                      prev: Optional[Dict[str, Any]]) -> bool:
        """§3.1: gap iff ``O_t > H_{t−1}·1.1`` or ``O_t < L_{t−1}·0.9``.
        ``prev_H``/``prev_L`` may be carried on the candle itself (§8.1
        GF09); ``O`` falls back to the candle open proxy ``o``/``O``."""
        open_t = candle.get("O", candle.get("o"))
        if open_t is None:
            return False
        prev_h = candle.get("prev_H", candle.get("prev_h"))
        prev_l = candle.get("prev_L", candle.get("prev_l"))
        if prev is not None:
            prev_h = prev_h if prev_h is not None else prev.get("H",
                                                                prev.get("h"))
            prev_l = prev_l if prev_l is not None else prev.get("L",
                                                                prev.get("l"))
        if prev_h is None or prev_l is None:
            return False
        try:
            o, ph, pl = float(open_t), float(prev_h), float(prev_l)
        except (TypeError, ValueError):
            return False
        return o > ph * 1.1 or o < pl * 0.9

    def _vol_ratio_for(self, candle: Dict[str, Any],
                       window: str) -> Optional[float]:
        v = float(candle["V"])
        hist = [float(e["V"]) for e in self.buffer
                if e.get("window") == window and float(e["V"]) > 0.0]
        return vol_ratio(v, hist)

    def _historical_behavior(self, window: str, bin_id: int,
                             dtype: str) -> Optional[Dict[str, Any]]:
        """§5.2 ``historical_behavior``; None until a profile exists
        (Q1_RAW ⇒ 'no historical_behavior yet', §5.5)."""
        if self.profile is None:
            return None
        key = condition_key(window, bin_id, dtype)
        rates = self.profile.get("conditional_rates") or {}
        bos = rates.get(f"bos|{key}") or {}
        sweep = rates.get(f"sweep|{key}") or {}
        same = [e for e in self.buffer if e.get("window") == window]
        vrs = [float(e["vol_ratio"]) for e in same
               if e.get("vol_ratio") is not None]
        ranges = [float(e["H"]) - float(e["L"]) for e in same
                  if math.isfinite(float(e.get("H", float("nan"))))
                  and math.isfinite(float(e.get("L", float("nan"))))]
        ci = bos.get("ci")
        return {
            "vol_ratio_avg": (round(sum(vrs) / len(vrs), 12)
                              if vrs else None),
            "range_avg": (round(sum(ranges) / len(ranges), 12)
                          if ranges else None),
            "bos_rate": bos.get("p"),
            "sweep_rate": sweep.get("p"),
            "sample_n": int(bos.get("n", 0)),
            "wilson_ci_bos": ([round(float(ci[0]), 12),
                               round(float(ci[1]), 12)] if ci else None),
        }


TemporalContextEngine = TemporalWindowEngineStream   # §5 canonical alias


# ---------------------------------------------------------------------------
# run_engine — batch driver with the §5.4 event journal
# ---------------------------------------------------------------------------
def run_engine(candles: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               econ_calendar: Optional[Any] = None,
               rollover_windows: Optional[Sequence[Dict[str, Any]]] = None,
               temporal_window_levels: Optional[Dict[str, Any]] = None,
               profile: Optional[Dict[str, Any]] = None,
               profile_inputs: Optional[Dict[str, Any]] = None,
               events: Optional[List[Dict[str, Any]]] = None
               ) -> Dict[str, Any]:
    """Stream ``candles`` through E12 and journal every §5.4 event.

    ``econ_calendar=None`` ⇒ HIGH_IMPACT is impossible and EV_TMP_008
    (Calendar_Unavailable) is emitted once — §8.3 conservative flagging.
    ``profile`` (pre-built) or ``profile_inputs`` (kwargs for
    ``compute_temporal_profile``, ``as_of`` filled from the last candle)
    attach the §5.3 profile ⇒ EV_TMP_006."""
    p = get_params(params)
    eng = TemporalWindowEngineStream(behavior_window=int(p.behavior_window),
                                     min_samples=int(p.daytype_min_samples),
                                     params=p,
                                     rollover_windows=rollover_windows,
                                     n_bins=int(p.fff_bins))
    journal: List[Dict[str, Any]] = list(events or [])
    if econ_calendar is None:
        journal.append({"code": "EV_TMP_008", "as_of": 0,
                        "reason": "ECON_CALENDAR_NOT_PROVIDED"})
    if temporal_window_levels is not None:
        eng.attach_levels(temporal_window_levels)
        journal.append({"code": "EV_TMP_007", "as_of": 0,
                        "levels_contract": "TemporalWindowLevels_v4"})
    if profile is not None:
        eng.attach_profile(profile)
        journal.append({"code": "EV_TMP_006",
                        "as_of": int(profile.get("as_of", 0)),
                        "quality": profile.get("quality")})
    prev_window: Optional[str] = None
    prev_phase: Optional[str] = None
    prev_dtype: Optional[str] = None
    prev_overlap = False
    last_state: Optional[Dict[str, Any]] = None
    for candle in candles:
        st = eng.on_candle(candle, econ_calendar)
        as_of = int(st.get("as_of", 0))
        if st["quality"] == "QX":
            last_state = st
            continue
        if st["quality"] == "Q0":
            journal.append({"code": "EV_TMP_009", "as_of": as_of,
                            "reason": st.get("reason"),
                            "snapshot_id": st["snapshot_id"]})
            last_state = st
            continue
        window = st["temporal_window"]
        if prev_window is None:
            journal.append({"code": "EV_TMP_001", "as_of": as_of,
                            "window": window})
        elif window != prev_window:
            journal.append({"code": "EV_TMP_002", "as_of": as_of,
                            "window": prev_window})
            journal.append({"code": "EV_TMP_001", "as_of": as_of,
                            "window": window})
        if st["is_overlap"] and not prev_overlap:
            journal.append({"code": "EV_TMP_003", "as_of": as_of,
                            "window": window})
        if prev_phase is not None and st["window_phase"] != prev_phase:
            journal.append({"code": "EV_TMP_004", "as_of": as_of,
                            "from": prev_phase, "to": st["window_phase"]})
        if prev_dtype is not None and st["day_type"] != prev_dtype:
            journal.append({"code": "EV_TMP_005", "as_of": as_of,
                            "from": prev_dtype, "to": st["day_type"]})
        prev_window, prev_phase = window, st["window_phase"]
        prev_dtype, prev_overlap = st["day_type"], bool(st["is_overlap"])
        last_state = st
    if profile_inputs and profile is None and last_state is not None:
        inputs = dict(profile_inputs)
        inputs.setdefault("as_of", int(last_state.get("as_of", 0)))
        inputs.setdefault("min_samples", int(p.daytype_min_samples))
        inputs.setdefault("n_bins", int(p.fff_bins))
        inputs.setdefault("fourier_k", int(p.fff_fourier_K))
        built = compute_temporal_profile(params=p, **inputs)
        eng.attach_profile(built)
        journal.append({"code": "EV_TMP_006",
                        "as_of": int(built["as_of"]),
                        "quality": built["quality"]})
        profile = built
    return {
        "temporal_state": last_state,
        "temporal_profile": profile,
        "events": journal,
        "engine": ENGINE,
        "contract_version": CONTRACT_VERSION,
        "config_version": str(p.temporal_window_calendar_version),
        "n_candles": len(eng.buffer),
    }


def catalog_events(state: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """§5.4 catalog rows fired by a temporal state (empty for refusals)."""
    events: List[Dict[str, Any]] = []
    if not state or "snapshot_id" not in state or \
            state.get("quality") not in ("Q1", "Q2", "Q3", "Q4"):
        return events
    as_of = int(state.get("as_of", 0))
    events.append({"code": "EV_TMP_001", "as_of": as_of, "state": state,
                   "window": state["temporal_window"]})
    if state.get("is_overlap"):
        events.append({"code": "EV_TMP_003", "as_of": as_of, "state": state})
    return events


def observation_to_candle(obs: MarketObservation,
                          availability_time_ms: Optional[int] = None
                          ) -> Dict[str, Any]:
    """MarketObservation → the §8.1 candle shape (uppercase OHLCV keys)."""
    dt = datetime.datetime.fromisoformat(
        str(obs.timestamp).replace("Z", "+00:00"))
    ts_ms = int(dt.timestamp() * 1000)
    return {"O": float(obs.open), "H": float(obs.high), "L": float(obs.low),
            "C": float(obs.close), "V": float(obs.volume), "ts": ts_ms,
            "availability_time_ms": int(availability_time_ms
                                        if availability_time_ms is not None
                                        else ts_ms),
            "symbol": obs.symbol, "timeframe": obs.timeframe}


# ---------------------------------------------------------------------------
# E07 provider surface — the versioned contract consumed by
# E07 ``utc_activity_window_check`` (ISSUE-CP4-005 resolved branch)
# ---------------------------------------------------------------------------
class E12TemporalProvider:
    """``E12_Temporal_Context.Contract v4.0.0`` provider for E07 §3.6.

    ``temporal_window(ts_ms) -> {"which": [...], "is_overlap": bool,
    "utc_activity_window": str, "config_version": str}`` where ``which`` =
    the primary window plus the derived ``UTC_W1_W2_OVERLAP`` label — the
    same list semantics E07's degraded local branch uses, but authoritative
    (E12 owns the registry).  Matching core windows ride along in the
    separate ``core_windows`` key (E07's degraded branch keeps them separate
    too, so both modes stay comparable)."""

    contract = E07_CONTRACT_LABEL

    def __init__(self, params: Optional[EngineParams] = None,
                 rollover_windows: Optional[Sequence[Dict[str, Any]]] = None,
                 econ_calendar: Optional[Any] = None) -> None:
        self.params = params or EngineParams()
        self.config_version = str(
            self.params.temporal_window_calendar_version)
        self.rollover_windows = list(rollover_windows or [])
        self.econ_calendar = econ_calendar

    def temporal_window(self, ts_ms: Any) -> Dict[str, Any]:
        ts = ts_from_ms(ts_ms)
        ctx = utc_activity_window_of(ts, self.rollover_windows)
        h = hour_float(ts)
        which: List[str] = [ctx["temporal_window"]]
        if ctx["is_overlap"]:
            which.append(OVERLAP_LABEL)
        core = [name for name, (lo, hi) in UTC_CORE_WINDOWS.items()
                if lo <= h < hi]
        return {"which": which,
                "core_windows": core,
                "is_overlap": bool(ctx["is_overlap"]),
                "utc_activity_window": ctx["temporal_window"],
                "window_phase": ctx["window_phase"],
                "day_type": day_type(ts, self.econ_calendar),
                "rollover_active": bool(ctx["rollover_active"]),
                "config_version": self.config_version}


# ---------------------------------------------------------------------------
# EngineBase binding (frozen contract, wave 1)
# ---------------------------------------------------------------------------
class E12TemporalEngine(EngineBase):
    """E12_Temporal_Context on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``candles``    — §8.1 candle dicts (``ts``, ``H/L/C/V``,
                       ``availability_time_ms``) — authoritative
      ``window``/``provider`` — MarketObservation fallback
      ``econ_calendar`` — red-day set (None ⇒ EV_TMP_008, conservative)
      ``rollover_windows``, ``temporal_window_levels``, ``profile``,
      ``profile_inputs``, ``e12_params`` — §6 overrides (unknown rejected)
    Emits one EvidenceEvent per §5.4 catalog row on the final state, on
    ``evidence.E12.{condition_state}``.  Context only: ``direction = 0``
    (NG — E12 outputs are Context, never signals or permissions)."""

    engine_id = ENGINE_ID
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    _CONF_BY_Q = {"Q4": 1.0, "Q3": 0.8, "Q2": 0.6, "Q1": 0.3,
                  "Q0": 0.0, "QX": 0.0}

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        candles = self._resolve_candles(symbol, timeframe, as_of, context)
        if not candles:
            return []
        result = run_engine(
            candles, params=context.get("e12_params"),
            econ_calendar=context.get("econ_calendar"),
            rollover_windows=context.get("rollover_windows"),
            temporal_window_levels=context.get("temporal_window_levels"),
            profile=context.get("profile"),
            profile_inputs=context.get("profile_inputs"))
        self._last_result = result
        state = result["temporal_state"]
        rows = catalog_events(state)
        if not rows:
            return []                        # QX/Q0 refusal — nothing built
        quality = self._window_quality(candles)
        return [self._to_evidence(item, symbol, timeframe, quality, state,
                                  result) for item in rows]

    def _resolve_candles(self, symbol: str, timeframe: str, as_of: str,
                         context: Dict[str, Any]) -> List[Dict[str, Any]]:
        candles = context.get("candles")
        if candles is not None:
            return list(candles)
        window = context.get("window")
        if window is None:
            provider = context.get("provider")
            if provider is None:
                raise ValueError("MISSING_WINDOW_CONTEXT_QX")
            import asyncio
            import inspect
            bars = context.get("bars", 300)
            res = provider.get_window(symbol, timeframe, as_of, bars)
            if inspect.isawaitable(res):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    window = list(asyncio.run(res))
                else:
                    raise ValueError("MISSING_WINDOW_CONTEXT_QX (async "
                                     "provider inside a running loop — pass "
                                     "context['candles'] or "
                                     "context['window'])")
            else:
                window = list(res)
        return [observation_to_candle(obs) for obs in window]

    @staticmethod
    def _window_quality(candles: Sequence[Dict[str, Any]]) -> float:
        if not candles:
            return 0.0
        ok = 0
        for c in candles:
            try:
                if float(c.get("H", 0)) >= float(c.get("L", 0)):
                    ok += 1
            except (TypeError, ValueError):
                continue
        return ok / len(candles)

    def _to_evidence(self, item: Dict[str, Any], symbol: str,
                     timeframe: str, quality: float, state: Dict[str, Any],
                     result: Dict[str, Any]) -> EvidenceEvent:
        code = str(item["code"])
        name = EVENT_CATALOG[code]["name"]
        ts = int(state["as_of"])
        iso = datetime.datetime.fromtimestamp(
            ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts % 1000:03d}Z"
        q = str(state["quality"])
        window = str(state["temporal_window"])
        if code == "EV_TMP_001":
            condition = f"EV_TMP_001_{window}"
            strength = 1.0 if state.get("is_utc_activity_window") else 0.5
        else:
            condition = f"{code}_{name.upper()}"
            strength = 1.0 if state.get("is_overlap") else 0.5
        profile_q = (result.get("temporal_profile") or {}).get("quality")
        explanation = (
            f"E12 {code} {name} window={window} "
            f"phase={state['window_phase']} overlap={state['is_overlap']} "
            f"core={state['is_utc_activity_window']} "
            f"day_type={state['day_type']} "
            f"bin={state['tod_state']['tod_bin']} Q={q} "
            f"profile_Q={profile_q} cfg={result['config_version']}"
        )
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=str(state["snapshot_id"]),
            event_time=iso, availability_time=iso,
            observation_window={"timeframe": timeframe,
                                "temporal_window": window,
                                "as_of_ms": ts},
            feature_snapshot_id=str(state["snapshot_id"]),
            feature_dependencies=("E02_Liquidity.v4(TemporalWindowLevels,"
                                  "optional)",
                                  "E11_Regime.v4(RegimeState,optional)"),
            condition_state=condition,
            direction=0,                     # context engine — never a signal
            strength=float(max(0.0, min(1.0, strength))),
            confidence=float(self._CONF_BY_Q.get(q, 0.3)),
            quality=float(quality),
            validity="VALID" if q in ("Q3", "Q4") else "DEGRADED",
            fate_state=LifecycleState.ACTIVE if q in ("Q2", "Q3", "Q4")
            else LifecycleState.CANDIDATE,
            age=float(max(result.get("n_candles", 1), 1)),
            decay=math.exp(-1.0 / 48.0),
            explanation=explanation[:500],
            parameter_version=f"E12-TMP-V{CONTRACT_VERSION}/"
                              f"{result['config_version']}",
            lineage=(f"cfg_{result['config_version']}", f"q_{q}"),
            resolution_class=q,
        )

    _last_result: Optional[Dict[str, Any]] = None


__all__ = [
    "ANALYST_VERSION", "CALENDAR_CONFIG_VERSION", "CONTRACT_LABEL",
    "CONTRACT_VERSION", "DAY_TYPES", "E07_CONTRACT_LABEL", "E12_DEFAULTS",
    "E12TemporalEngine", "E12TemporalProvider", "ENGINE", "ENGINE_ID",
    "EPS", "EVENT_CATALOG", "EngineParams", "FATE_VALUES",
    "FOURIER_K_DEFAULT", "N_BINS_DEFAULT", "OVERLAP_LABEL", "OVERLAP_WINDOW",
    "PHASES", "PRIMARY_WINDOWS", "QUALITY_TAGS", "STATE_REQUIRED",
    "TemporalContextEngine", "TemporalWindowEngineStream",
    "TOD_STATE_REQUIRED", "UTC_ACTIVITY_WINDOWS", "UTC_CORE_WINDOWS",
    "WILSON_Z", "chi2_sf", "compute_temporal_profile", "condition_key",
    "conditional_rate", "day_type", "deseasonalize",
    "deterministic_replay_check", "fff_seasonal",
    "fourier_smooth_factors", "get_params", "hour_float", "is_core_window",
    "kruskal_wallis", "load_v3_temporal_payload", "make_snapshot_id",
    "no_future_leak_check", "observation_to_candle", "param_hash",
    "profile_stability", "range_z", "returns_by_tod_from_candles",
    "rollover_is_active", "run_engine", "seasonal_profile_available",
    "serialize_state", "spearman_rho", "test_temporal_window_difference",
    "tod_bin", "ts_from_ms", "utc_activity_window_of", "validate_state_schema",
    "vol_ratio", "window_progress", "wilson_ci", "winsorize", "y_range",
    "y_vol", "catalog_events", "intraday_momentum_beta",
]
