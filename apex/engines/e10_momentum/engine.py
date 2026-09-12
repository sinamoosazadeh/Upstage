"""APEX_GEN5 — E10 Momentum (v4.0.0).

Blueprint: APEX_GEN5.md L10276–11670 (chapter order mirrored: §1 mission →
§2 vocabulary → §3 math framework → §4 algorithms → §5 objects/state/events/
schema → §6 parameters → §7 encyclopedic → §8 validation).

Momentum is **Context, not a Trigger** (§0): this engine never produces a
standalone buy/sell signal (NG1). It quantifies velocity/acceleration with
low-pass EMA smoothing, MomentumZ, MvZ participation integration, the four
corrected reference indicators (Wilder-RMA RSI, ROC, Stochastic %K/%D, full
MACD 12/26/9), symmetric Impulse/Exhaustion, and Divergence by two
complementary methods (Method A OLS slope β, Method B confirmed fractal
pivots with BOTH price and momentum pivots stored) covering the four
normative kinds plus CONVERGENCE and NONE (§3.4, §5.3 EV_MOM_001..008).

Self-sufficiency (§0): no direct calls into E09/E04. Optional versioned
``trend_context`` / ``volatility_context`` projections are consumed through
their frozen v4.0.0 schemas (§1.5 freeze note); an incompatible version
downgrades the Q-tag one level (§5.2). Absent context is permitted (§1.5
``Input.TrendContext?`` optional) and never fabricated.

Logged contradictions (PHASE2_DECISION_LOG §B/CP-5):
  ISSUE-CP5-001 (§6 θ_acc unit "z" + §9 "a_z = a_t/σ_v" vs §4 raw a_t
                comparison) → acceleration normalized to z-scale before
                thresholding.
  ISSUE-CP5-002 (§3.5 "Final" MvZ clauses vs §2/§4/§9 without) → §3.5
                governs when MvZ context is available; pure-state detectors
                evaluate the core condition (GF05/GF06 shape).
  ISSUE-CP5-003 (§6 reference_mode default "velocity" vs §4/§8.1/§9 RSI
                auxiliary) → default "RSI"; all five enum modes wired.
  ISSUE-CP5-004 (§5.1 schema requires ``param_hash`` vs §4 emits
                ``param_fingerprint``) → schema wins: ``param_hash``.
  ISSUE-CP5-005 (§5.1 interval enum 6 TFs vs §9.5-8 universality 14 TFs) →
                the frozen universe (14 TFs) governs; schema enum recorded.
  ISSUE-CP5-006 (EV_MOM_007 "low D_mag" unquantified) → 0.2 derived from
                §7-Ch3-D9 "small D_mag (<0.2) should be filtered out".
  ISSUE-CP5-007 (§3.4 disagreement → Q2 missing from §4 code; ROC index
                off-by-one; duplicate-call rebuild) → §3.4/§2 formulas
                govern; duplicates return the cached state (§4 text).
"""

from __future__ import annotations

import datetime
import hashlib
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
)
from apex.engines.base import EngineBase
from apex.identity.snapshot import canonical_snapshot_id
from apex.identity.uuid_v7 import uuid_v7
from apex.quality.numerical import eps_for_engine

# ---------------------------------------------------------------------------
# Chapter identity
# ---------------------------------------------------------------------------

ENGINE = "E10_Momentum"
CONTRACT_VERSION = "4.0.0"
CONTRACT_LABEL = "E10_Momentum/4.0.0"          # §5.1 pattern ^E10_Momentum/x.y.z$
ANALYST_VERSION = "4.0.0+" + "0" * 40
EPS = float(eps_for_engine("E10"))              # 1e-8 (§4 / frozen §2.2 row)

# §9.5-8 universality: the frozen 14-TF universe (params/universe_v1.yaml)
# governs; the §5.1 schema enum [1m,5m,15m,1h,4h,1d] is a historical subset
# (ISSUE-CP5-005). 1mo uses the 30-day convention for gap arithmetic only.
TF_SECONDS: Dict[str, int] = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "1w": 604800, "1mo": 2592000,
}
INTERVALS = tuple(TF_SECONDS)

Q_TAGS = ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5")
# §5.3 event catalog (001b/002b are the symmetric bearish variants of the
# same code, exactly as the chapter lists them).
EVENT_CATALOG: Dict[str, Dict[str, str]] = {
    "EV_MOM_001": {"name": "Impulse_Bull",
                   "condition": "Mz>=θ_imp ∧ a_z>=θ_acc ∧ MvZ>0"},
    "EV_MOM_001b": {"name": "Impulse_Bear",
                    "condition": "Mz<=-θ_imp ∧ a_z<=-θ_acc ∧ MvZ<0"},
    "EV_MOM_002": {"name": "Exhaustion_Bull",
                   "condition": "Mz>0 ∧ a_z<-θ_acc ∧ |Mz|>=θ_imp ∧ MvZ decr"},
    "EV_MOM_002b": {"name": "Exhaustion_Bear",
                    "condition": "Mz<0 ∧ a_z>+θ_acc ∧ |Mz|>=θ_imp ∧ MvZ incr"},
    "EV_MOM_003": {"name": "Divergence_Regular_Bearish",
                   "condition": "price HH ∧ momentum LH (both pivots)"},
    "EV_MOM_004": {"name": "Divergence_Regular_Bullish",
                   "condition": "price LL ∧ momentum HL (both pivots)"},
    "EV_MOM_005": {"name": "Divergence_Hidden_Bullish",
                   "condition": "price HL ∧ momentum LL (both pivots)"},
    "EV_MOM_006": {"name": "Divergence_Hidden_Bearish",
                   "condition": "price LH ∧ momentum HH (both pivots)"},
    "EV_MOM_007": {"name": "Convergence",
                   "condition": "β same sign ∧ D_mag < convergence_dmag_max"},
    "EV_MOM_008": {"name": "Momentum_Neutral", "condition": "|Mz| < 0.5"},
}
DIVERGENCE_KINDS = ("REGULAR_BEARISH", "REGULAR_BULLISH", "HIDDEN_BEARISH",
                    "HIDDEN_BULLISH", "CONVERGENCE", "NONE")
DIVERGENCE_METHODS = ("OLS", "PIVOT", "BOTH", "NONE")
KIND_TO_EVENT = {"REGULAR_BEARISH": "EV_MOM_003",
                 "REGULAR_BULLISH": "EV_MOM_004",
                 "HIDDEN_BULLISH": "EV_MOM_005",
                 "HIDDEN_BEARISH": "EV_MOM_006",
                 "CONVERGENCE": "EV_MOM_007"}
# §5.2 fate lifecycle labels (§5.3 FATE_*).
FATES = ("FATE_INIT", "FATE_WARMUP", "FATE_Q3_READY",
         "FATE_DIVERGENCE_TRACKING", "FATE_IMPULSE", "FATE_EXHAUSTION",
         "FATE_INVALID")
# §5.1 required top-level MomentumState keys.
MOMENTUM_STATE_REQUIRED = (
    "contract_version", "schema_version", "engine_code", "as_of", "symbol",
    "interval", "snapshot_id", "q_tag", "param_hash", "momentum",
    "volume_context", "indicators", "events", "pit",
)
REFERENCE_MODES = ("RSI", "ROC", "velocity", "participation", "volume")


# ---------------------------------------------------------------------------
# §2 Vocabulary — data objects
# ---------------------------------------------------------------------------


@dataclass
class Candle:
    """§1.5 ``Input.Candle``: PIT-safe OHLCV."""
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: int            # ms epoch UTC
    close_time: int
    is_closed: bool
    symbol: str
    interval: str


@dataclass
class Pivot:
    """§3.4 Method-B pivot; both price and momentum pivots are stored."""
    index: int                # absolute bar index of the pivot bar
    time: int                 # close_time of the pivot bar (ms UTC)
    price: float
    value: float              # indicator value (or price duplicate)
    type: str                 # HIGH | LOW
    indicator: str            # PRICE | RSI | ROC | MOM_Z | MZ | MVZ | VZ ...
    confirmed_at: int         # absolute bar index of confirmation (t+k)


@dataclass
class DivergenceEvent:
    """§3.4 divergence record; ``kind`` per the §5.1 enum."""
    kind: str
    method: str               # OLS | PIVOT | BOTH
    price_pivots: List[Pivot]
    mom_pivots: List[Pivot]
    beta_price: Optional[float]
    beta_mom: Optional[float]
    D_mag: float
    as_of: int
    pit_proof: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# §6 Parameters (values literal from the §6 table; ISSUE-CP2-006 discipline —
# in-package defaults, no new YAML; six-YAML law honoured)
# ---------------------------------------------------------------------------

E10_DEFAULTS: Dict[str, Any] = {
    "mom_window": 14,
    "z_window": 50,
    "ema_vel": 14,
    "ema_acc": 5,
    "impulse_z": 2.0,             # θ_imp
    "accel_threshold": 0.5,       # θ_acc (z-scale — ISSUE-CP5-001)
    "rsi_period": 14,
    "roc_window": 10,
    "stoch_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "pivot_min_bars": 5,          # k
    "divergence_window": 20,      # W_div
    "price_delta_pct": 0.001,     # δ_p
    "mom_delta": 0.5,             # δ_m
    "reference_mode": "RSI",      # ISSUE-CP5-003 (§4/§8.1/§9 auxiliary)
    "corr_window": 20,            # w_corr
    "beta_min": 1e-5,             # β_min
    # derived, documented constant (ISSUE-CP5-006): §7-Ch3-D9 "<0.2".
    "convergence_dmag_max": 0.2,
}


class EngineParams:
    """Frozen §6 surface; unknown keys are rejected (fail-closed)."""

    def __init__(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        values = dict(E10_DEFAULTS)
        for key, val in (overrides or {}).items():
            if key not in E10_DEFAULTS:
                raise ValueError(f"UNKNOWN_E10_PARAM_QX: {key}")
            values[key] = val
        self._v = values
        for name, val in values.items():
            setattr(self, name, val)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._v)

    def get(self, key: str, default: Any = None) -> Any:
        return self._v.get(key, default)


def get_params(overrides: Optional[Dict[str, Any]] = None) -> EngineParams:
    return EngineParams(overrides)


def param_hash(params: Optional[EngineParams] = None) -> str:
    """§5.4 ``param_hash = SHA256(sorted params)[:12]`` (ISSUE-CP5-004:
    schema field name; §4's ``param_fingerprint`` is the same diagnostic)."""
    p = (params or EngineParams()).as_dict()
    blob = hashlib.sha256(
        _canonical_bytes(p)).hexdigest()[:12]
    return blob


def _canonical_bytes(obj: Any) -> bytes:
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------------------
# §3.1/§3.2/§3.3 — streaming smoothers and indicator math
# ---------------------------------------------------------------------------


class EMAState:
    """§2 EMA_n: α = 2/(n+1), first seed = SMA_n (streaming)."""

    def __init__(self, period: int) -> None:
        self.period = int(period)
        self.alpha = 2.0 / (self.period + 1)
        self.value: Optional[float] = None
        self.count = 0
        self._buf: List[float] = []

    def update(self, x: Optional[float]) -> Optional[float]:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return self.value
        self.count += 1
        if self.value is None:
            self._buf.append(float(x))
            if len(self._buf) < self.period:
                return None
            self.value = sum(self._buf) / self.period
            return self.value
        self.value = self.alpha * float(x) + (1 - self.alpha) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None
        self.count = 0
        self._buf = []


class RMAState:
    """§2 Wilder RMA_n: RMA_t = (RMA_{t−1}(n−1) + X_t)/n, seed = SMA_n."""

    def __init__(self, period: int) -> None:
        self.period = int(period)
        self.value: Optional[float] = None
        self.count = 0
        self._buf: List[float] = []

    def update(self, x: Optional[float]) -> Optional[float]:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return self.value
        self.count += 1
        if self.value is None:
            self._buf.append(float(x))
            if len(self._buf) < self.period:
                return None
            self.value = sum(self._buf) / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + float(x)) / self.period
        return self.value

    def reset(self) -> None:
        self.value = None
        self.count = 0
        self._buf = []


def log_return(close: float, prev_close: Optional[float]) -> Optional[float]:
    """§3.1 ℓ_t = ln(C_t/C_{t−1}); undefined for non-positive prices."""
    if prev_close is None:
        return None
    if close <= 0 or prev_close <= 0:
        return None
    if not (math.isfinite(close) and math.isfinite(prev_close)):
        return None
    return math.log(close / prev_close)


def ols_slope(y: Sequence[Optional[float]]) -> Tuple[Optional[float],
                                                     Optional[float]]:
    """§3.4 Method-A β = Cov(i,X)/Var(i) over the relative index; returns
    (beta, stderr); NaN entries are filtered; n<3 ⇒ (None, None)."""
    clean = [(i, float(v)) for i, v in enumerate(y)
             if v is not None and math.isfinite(float(v))]
    if len(clean) < 3:
        return None, None
    xs = [c[0] for c in clean]
    ys = [c[1] for c in clean]
    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_x2 = sum(x * x for x in xs)
    sum_xy = sum(x * y_ for x, y_ in zip(xs, ys))
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < EPS:
        return None, None
    beta = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - beta * sum_x) / n
    rss = sum((y_ - (beta * x + intercept)) ** 2
              for x, y_ in zip(xs, ys))
    var_x = sum((x - sum_x / n) ** 2 for x in xs)
    se: Optional[float] = None
    if n > 2 and var_x > EPS:
        se = math.sqrt(rss / (n - 2)) / math.sqrt(var_x)
    return beta, se


def divergence_mag_ols(beta_x: float, beta_y: float) -> float:
    """§3.4 D_mag,OLS = |β_X − β_Y| / max(|β_X|+|β_Y|, ε) ∈ [0,1]."""
    return abs(beta_x - beta_y) / max(abs(beta_x) + abs(beta_y), EPS)


def divergence_mag_pivot(p1: float, p2: float, m1: float, m2: float) -> float:
    """§3.4 D_mag,pivot = |(P2−P1)/P1 − (M2−M1)/|M1||."""
    if p1 == 0:
        return 0.0
    return abs((p2 - p1) / p1 - (m2 - m1) / max(abs(m1), EPS))


def pearson_corr(a: Sequence[Optional[float]],
                 b: Sequence[Optional[float]]) -> float:
    """§3.6 rolling Pearson correlation; <3 clean pairs or a degenerate
    denominator ⇒ 0.0."""
    if len(a) != len(b) or len(a) < 3:
        return 0.0
    clean = [(float(x), float(y)) for x, y in zip(a, b)
             if x is not None and y is not None
             and math.isfinite(float(x)) and math.isfinite(float(y))]
    if len(clean) < 3:
        return 0.0
    xs, ys = zip(*clean)
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs)
                    * sum((y - my) ** 2 for y in ys))
    if den < EPS:
        return 0.0
    return max(min(num / den, 1.0), -1.0)


def wilson_ci(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """§8.5 Wilson 95% CI."""
    if n <= 0:
        return (0.0, 0.0)
    denom = 1 + z * z / n
    centre = p_hat + z * z / (2 * n)
    delta = z * math.sqrt(max(p_hat * (1 - p_hat) / n + z * z / (4 * n * n),
                              0.0))
    return (max(0.0, (centre - delta) / denom),
            min(1.0, (centre + delta) / denom))


def momentum_z(vel_window: Sequence[float],
               z_window: int) -> Tuple[Optional[float], Optional[float],
                                       Optional[float]]:
    """§3.2 Mz = (v_t − μ_n)/max(σ_n, ε) over the last ``z_window`` smoothed
    velocities (ddof=0). <2 samples ⇒ (None, None, None); σ<ε ⇒ Mz=0."""
    if len(vel_window) < 2:
        return None, None, None
    window = list(vel_window)[-z_window:]
    n = len(window)
    mu = sum(window) / n
    var = sum((x - mu) ** 2 for x in window) / n
    sd = math.sqrt(var) if var > EPS else EPS
    mz = (window[-1] - mu) / max(sd, EPS)
    if sd <= EPS:
        mz = 0.0
    return mz, mu, sd


def volume_features(volumes: Sequence[float], n: int = 20
                    ) -> Tuple[Optional[float], Optional[float],
                               Optional[float]]:
    """§3.6 VR = V/SMA_n(V), Vz = (V−μ)/max(σ,ε); <2 samples ⇒ Nones.
    Edge V=0 ⇒ VR=0 (MvZ=0 downstream)."""
    if len(volumes) < 2:
        return None, None, None
    vols = [float(v) for v in list(volumes)[-n:]]
    mu = sum(vols) / len(vols)
    var = sum((v - mu) ** 2 for v in vols) / len(vols)
    sd = math.sqrt(var) if var > EPS else EPS
    cur = vols[-1]
    vz = (cur - mu) / max(sd, EPS)
    vr = cur / max(mu, EPS)
    return vr, vz, mu


def rsi_series(closes: Sequence[float], n: int = 14,
               method: str = "RMA") -> List[Optional[float]]:
    """§3.3 Wilder RSI via RMA (``method="RMA"`` — the governing formula);
    ``method="SMA"`` exists ONLY as the §8.4 ablation path (2.1-unit RMSE
    bias demonstration). Edges: AL<ε∧AG<ε ⇒ 50; AL<ε<AG ⇒ 100."""
    if method not in ("RMA", "SMA"):
        raise ValueError("UNKNOWN_E10_PARAM_QX: rsi method")
    out: List[Optional[float]] = [None]
    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        d = float(closes[i]) - float(closes[i - 1])
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
        if len(gains) < n:
            out.append(None)
            continue
        if method == "RMA":
            if len(gains) == n:
                ag = sum(gains) / n
                al = sum(losses) / n
            else:
                ag = (ag * (n - 1) + gains[-1]) / n   # type: ignore[possibly-undefined]
                al = (al * (n - 1) + losses[-1]) / n  # type: ignore[possibly-undefined]
        else:  # SMA ablation path
            ag = sum(gains[-n:]) / n
            al = sum(losses[-n:]) / n
        if al < EPS and ag < EPS:
            out.append(50.0)
        elif al < EPS:
            out.append(100.0)
        else:
            rs = ag / max(al, EPS)
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out


def stochastic_kd(highs: Sequence[float], lows: Sequence[float],
                  closes: Sequence[float], n: int = 14
                  ) -> Tuple[Optional[float], Optional[float]]:
    """§3.3 %K = 100(C−LL_n)/max(HH_n−LL_n,ε); %D = SMA_3(%K). Flat market
    (HH−LL<ε) ⇒ %K = 50. Fewer than n bars ⇒ (None, None)."""
    if len(closes) < n or len(highs) < n or len(lows) < n:
        return None, None
    hh = max(float(h) for h in list(highs)[-n:])
    ll = min(float(l) for l in list(lows)[-n:])
    if hh - ll <= EPS:
        return 50.0, None
    k = 100.0 * (float(closes[-1]) - ll) / (hh - ll)
    return k, None


def roc(closes: Sequence[float], n: int = 10) -> Optional[float]:
    """§3.3 ROC_t(n) = (C_t − C_{t−n})/C_{t−n}·100 (index t−n exactly —
    ISSUE-CP5-007 off-by-one fix vs §4's ``candles[-10]``). C_{t−n}<=0 ⇒
    None (invalid)."""
    if len(closes) < n + 1:
        return None
    prev = float(closes[-(n + 1)])
    if prev <= 0:
        return None
    return (float(closes[-1]) - prev) / prev * 100.0


def macd_state(closes: Sequence[float], fast: int = 12, slow: int = 26,
               signal: int = 9) -> Dict[str, Optional[float]]:
    """§3.3 full MACD with SMA-seeded streaming EMAs (batch evaluation of
    the same recursion)."""
    ef, es, eg = EMAState(fast), EMAState(slow), EMAState(signal)
    line: Optional[float] = None
    sig: Optional[float] = None
    hist: Optional[float] = None
    for c in closes:
        f = ef.update(float(c))
        s = es.update(float(c))
        if f is not None and s is not None:
            line = f - s
            sig = eg.update(line)
            if sig is not None:
                hist = line - sig
    return {"ema_fast": ef.value, "ema_slow": es.value, "line": line,
            "signal": sig, "hist": hist}


def classify_pivot_pair(p1: float, p2: float, m1: float, m2: float,
                        side: str, price_delta_pct: float = 0.001,
                        mom_delta: float = 0.5
                        ) -> Tuple[Optional[str], Dict[str, bool]]:
    """§3.4 Method-B classification of two same-side pivots (``side`` =
    HIGH | LOW): the precise Regular/Hidden definitions. Returns
    (kind | None, pit_proof flags)."""
    if side == "HIGH":
        if p2 > p1 * (1 + price_delta_pct) and m2 < m1 - mom_delta:
            return "REGULAR_BEARISH", {"price_HH": True, "mom_LH": True}
        if p2 < p1 * (1 - price_delta_pct) and m2 > m1 + mom_delta:
            return "HIDDEN_BEARISH", {"price_LH": True, "mom_HH": True}
    elif side == "LOW":
        if p2 < p1 * (1 - price_delta_pct) and m2 > m1 + mom_delta:
            return "REGULAR_BULLISH", {"price_LL": True, "mom_HL": True}
        if p2 > p1 * (1 + price_delta_pct) and m2 < m1 - mom_delta:
            return "HIDDEN_BULLISH", {"price_HL": True, "mom_LL": True}
    else:
        raise ValueError("UNKNOWN_E10_PARAM_QX: pivot side")
    return None, {}


def impulse_exhaustion_flags(mz: Optional[float], a_z: Optional[float],
                             th_imp: float, th_acc: float,
                             mvz: Optional[float] = None,
                             mvz_prev: Optional[float] = None,
                             vr: Optional[float] = None,
                             vr_prev: Optional[float] = None
                             ) -> Dict[str, bool]:
    """§3.5 symmetric Impulse/Exhaustion. ``a_z`` is the z-scaled
    acceleration (ISSUE-CP5-001). The §3.5 MvZ clauses are applied when the
    MvZ/VR context is supplied (streaming path); pure-state callers (GF05/
    GF06 shape) evaluate the core condition (ISSUE-CP5-002)."""
    out = {"impulse_bull": False, "impulse_bear": False,
           "exhaustion_bull": False, "exhaustion_bear": False}
    if mz is None or a_z is None:
        return out
    mvz_ctx = mvz is not None
    vr_declining = (vr is not None and vr_prev is not None and vr < vr_prev)
    if mz >= th_imp and a_z >= th_acc and (not mvz_ctx or (mvz or 0.0) > 0):
        out["impulse_bull"] = True
    if mz <= -th_imp and a_z <= -th_acc and (not mvz_ctx or (mvz or 0.0) < 0):
        out["impulse_bear"] = True
    if mz > 0 and a_z < -th_acc and abs(mz) >= th_imp:
        if not mvz_ctx or ((mvz or 0.0) < (mvz_prev or 0.0) and vr_declining):
            out["exhaustion_bull"] = True
    if mz < 0 and a_z > th_acc and abs(mz) >= th_imp:
        if not mvz_ctx or ((mvz or 0.0) > (mvz_prev or 0.0) and vr_declining):
            out["exhaustion_bear"] = True
    return out


# ---------------------------------------------------------------------------
# §4 — streaming engine (idempotent, PIT-safe)
# ---------------------------------------------------------------------------


class MomentumEngine:
    """§4 ``MomentumEngine`` reference implementation (streaming). One
    CLOSED candle per ``update``; idempotent per close_time (a duplicate
    returns the previous state without touching internal buffers — §4
    complexity note; ISSUE-CP5-007)."""

    def __init__(self, params: Optional[EngineParams] = None) -> None:
        self.p = params or EngineParams()
        p = self.p
        self.ema_vel = EMAState(p.ema_vel)
        self.ema_acc = EMAState(p.ema_acc)
        self.ema_fast = EMAState(p.macd_fast)
        self.ema_slow = EMAState(p.macd_slow)
        self.ema_macd_sig = EMAState(p.macd_signal)
        self.rma_gain = RMAState(p.rsi_period)
        self.rma_loss = RMAState(p.rsi_period)
        buf = p.z_window + 100
        self.candles: deque = deque(maxlen=buf)
        self.log_returns: deque = deque(maxlen=200)
        self.vel_smooth: deque = deque(maxlen=200)
        self.acc_smooth: deque = deque(maxlen=200)
        self.mz_hist: deque = deque(maxlen=200)
        self.vz_hist: deque = deque(maxlen=200)
        self.rsi_hist: deque = deque(maxlen=200)
        self.macd_hist_hist: deque = deque(maxlen=200)
        self.stoch_k_hist: deque = deque(maxlen=3)
        self.volume_ma_buf: deque = deque(maxlen=50)
        # aux series aligned 1:1 with self.candles (ISSUE engineering note:
        # the §4 code aligns RSI pivots by tail-slicing; this engine keeps an
        # exact per-bar alignment list — behavior-preserving precision fix).
        self.aux_by_bar: List[Optional[float]] = []
        self.price_high_pivots: List[Pivot] = []
        self.price_low_pivots: List[Pivot] = []
        self.mom_high_pivots: List[Pivot] = []
        self.mom_low_pivots: List[Pivot] = []
        self.last_mz = 0.0
        self.last_mv_z = 0.0
        self.last_vr: Optional[float] = None
        self.last_state: Optional[Dict[str, Any]] = None
        self.bar_index = 0            # count of accepted (valid) candles
        self._phash = param_hash(self.p)

    # -- validation / edges --------------------------------------------------
    def _validate_candle(self, c: Candle) -> Optional[str]:
        if not c.is_closed:
            return "OPEN_CANDLE"
        if c.high < c.low - EPS:
            return "H_LT_L"
        if c.close <= 0 or c.open <= 0:
            return "NONPOSITIVE_PRICE"
        if any(math.isnan(float(x)) for x in (c.close, c.volume, c.high,
                                              c.low, c.open)):
            return "NON_FINITE"
        if c.interval not in TF_SECONDS:
            return "UNKNOWN_INTERVAL_QX"
        return None

    def _gap_break(self, prev: Candle, cur: Candle) -> bool:
        """§3.1 edge: a close_time gap > 1.5× interval ⇒ break ⇒ EMA/RMA
        states reset to their SMA seeds."""
        interval_ms = TF_SECONDS.get(cur.interval, 0) * 1000
        if interval_ms <= 0:
            return False
        return (cur.close_time - prev.close_time) > 1.5 * interval_ms

    def _reset_smoothers(self) -> None:
        for st in (self.ema_vel, self.ema_acc, self.ema_fast, self.ema_slow,
                   self.ema_macd_sig, self.rma_gain, self.rma_loss):
            st.reset()

    # -- pivots (§3.4 Method B) ----------------------------------------------
    @staticmethod
    def _fractal(series: Sequence[Optional[float]], center: int,
                 k: int) -> Optional[str]:
        if center < k or center + k >= len(series):
            return None
        window = series[center - k:center + k + 1]
        if any(v is None for v in window):
            return None
        cv = float(window[k])  # type: ignore[arg-type]
        others = [float(v) for i, v in enumerate(window) if i != k]  # type: ignore[arg-type]
        if cv >= max(others) - EPS and cv >= max(window) - EPS:  # type: ignore[arg-type]
            return "HIGH"
        if cv <= min(others) + EPS and cv <= min(window) + EPS:  # type: ignore[arg-type]
            return "LOW"
        return None

    def _update_pivots(self) -> None:
        k = int(self.p.pivot_min_bars)
        n = len(self.candles)
        if n < 2 * k + 1:
            return
        highs = [c.high for c in self.candles]
        lows = [c.low for c in self.candles]
        times = [c.close_time for c in self.candles]
        center_local = n - k - 1              # latest confirmable center
        center_abs = self.bar_index - k - 1   # absolute index (bar_index-1 is
        confirmed_abs = self.bar_index - 1    # the newest bar = confirmation)
        p_type = self._fractal(highs, center_local, k)
        if p_type == "HIGH":
            piv = Pivot(index=center_abs, time=times[center_local],
                        price=highs[center_local],
                        value=highs[center_local], type="HIGH",
                        indicator="PRICE", confirmed_at=confirmed_abs)
            if not any(pp.index == piv.index
                       for pp in self.price_high_pivots):
                self.price_high_pivots.append(piv)
        else:
            l_type = self._fractal(lows, center_local, k)
            if l_type == "LOW":
                piv = Pivot(index=center_abs, time=times[center_local],
                            price=lows[center_local],
                            value=lows[center_local], type="LOW",
                            indicator="PRICE", confirmed_at=confirmed_abs)
                if not any(pp.index == piv.index
                           for pp in self.price_low_pivots):
                    self.price_low_pivots.append(piv)
        # momentum pivots on the aligned aux series
        aux = self.aux_by_bar[-n:] if len(self.aux_by_bar) >= n \
            else self.aux_by_bar
        if len(aux) >= 2 * k + 1:
            m_type = self._fractal(aux, len(aux) - k - 1, k)
            center_m = len(aux) - k - 1
            mv = aux[center_m]
            if m_type == "HIGH" and mv is not None:
                piv = Pivot(index=center_abs, time=times[center_local],
                            price=self.candles[center_local].close,
                            value=float(mv), type="HIGH",
                            indicator=self.p.reference_mode,
                            confirmed_at=confirmed_abs)
                if not any(pp.index == piv.index
                           for pp in self.mom_high_pivots):
                    self.mom_high_pivots.append(piv)
            elif m_type == "LOW" and mv is not None:
                piv = Pivot(index=center_abs, time=times[center_local],
                            price=self.candles[center_local].close,
                            value=float(mv), type="LOW",
                            indicator=self.p.reference_mode,
                            confirmed_at=confirmed_abs)
                if not any(pp.index == piv.index
                           for pp in self.mom_low_pivots):
                    self.mom_low_pivots.append(piv)

    # -- divergence detectors --------------------------------------------------
    def _aux_value(self) -> Optional[float]:
        mode = str(self.p.reference_mode)
        if mode == "RSI":
            return self.rsi_hist[-1] if self.rsi_hist else None
        if mode == "ROC":
            closes = [c.close for c in self.candles]
            return roc(closes, int(self.p.roc_window))
        if mode == "velocity":
            return self.vel_smooth[-1] if self.vel_smooth else None
        if mode == "participation":
            return self.last_mv_z
        if mode == "volume":
            return self.vz_hist[-1] if self.vz_hist else None
        raise ValueError("UNKNOWN_E10_PARAM_QX: reference_mode")

    def _detect_divergence_ols(self) -> Tuple[Optional[DivergenceEvent],
                                              Optional[DivergenceEvent]]:
        """Returns (divergence, convergence). §3.4 Method A over the shared
        PIT window W; sign mismatch ∧ both |β|>β_min ⇒ divergence; same sign
        ∧ D_mag < convergence_dmag_max ⇒ CONVERGENCE (EV_MOM_007,
        ISSUE-CP5-006)."""
        W = int(self.p.divergence_window)
        aux = self.aux_by_bar[-W:]
        if len(self.candles) < W or len(aux) < W or any(v is None
                                                        for v in aux):
            return None, None
        price_series = [c.close for c in list(self.candles)[-W:]]
        mom_series = [float(v) for v in aux]
        beta_p, _ = ols_slope(price_series)
        beta_m, _ = ols_slope(mom_series)
        if beta_p is None or beta_m is None:
            return None, None
        beta_min = float(self.p.beta_min)
        as_of = self.candles[-1].close_time
        if (math.copysign(1, beta_p) != math.copysign(1, beta_m)
                and abs(beta_p) > beta_min and abs(beta_m) > beta_min):
            dmag = divergence_mag_ols(beta_p, beta_m)
            kind = ("REGULAR_BEARISH" if beta_p > 0 and beta_m < 0
                    else "REGULAR_BULLISH" if beta_p < 0 and beta_m > 0
                    else "NONE")
            if kind == "NONE":
                return None, None
            return DivergenceEvent(
                kind=kind, method="OLS", price_pivots=[], mom_pivots=[],
                beta_price=beta_p, beta_mom=beta_m, D_mag=dmag, as_of=as_of,
                pit_proof={"W": W, "beta_p": beta_p, "beta_m": beta_m,
                           "reference_mode": self.p.reference_mode}), None
        if (math.copysign(1, beta_p) == math.copysign(1, beta_m)
                and abs(beta_p) > beta_min and abs(beta_m) > beta_min):
            dmag = divergence_mag_ols(beta_p, beta_m)
            if dmag < float(self.p.convergence_dmag_max):
                return None, DivergenceEvent(
                    kind="CONVERGENCE", method="OLS", price_pivots=[],
                    mom_pivots=[], beta_price=beta_p, beta_mom=beta_m,
                    D_mag=dmag, as_of=as_of,
                    pit_proof={"W": W, "beta_p": beta_p, "beta_m": beta_m,
                               "same_sign": True})
        return None, None

    def _detect_divergence_pivot(self) -> Optional[DivergenceEvent]:
        """§3.4 Method B over the last two confirmed pivots (both stored)."""
        as_of = self.candles[-1].close_time if self.candles else 0
        for p_pivots, m_pivots, side in (
                (self.price_high_pivots, self.mom_high_pivots, "HIGH"),
                (self.price_low_pivots, self.mom_low_pivots, "LOW")):
            if len(p_pivots) >= 2 and len(m_pivots) >= 2:
                p1, p2 = p_pivots[-2], p_pivots[-1]
                m1, m2 = m_pivots[-2], m_pivots[-1]
                kind, proof = classify_pivot_pair(
                    p1.price, p2.price, m1.value, m2.value, side,
                    float(self.p.price_delta_pct), float(self.p.mom_delta))
                if kind is not None:
                    return DivergenceEvent(
                        kind=kind, method="PIVOT",
                        price_pivots=[p1, p2], mom_pivots=[m1, m2],
                        beta_price=None, beta_mom=None,
                        D_mag=divergence_mag_pivot(p1.price, p2.price,
                                                   m1.value, m2.value),
                        as_of=as_of,
                        pit_proof=dict(proof, p_idx=[p1.index, p2.index],
                                       m_idx=[m1.index, m2.index]))
        return None

    # -- main streaming update -------------------------------------------------
    def update(self, candle: Candle) -> Dict[str, Any]:
        """Streaming, idempotent per close_time, PIT-safe (§4)."""
        # idempotency: a repeated close_time returns the cached previous
        # state, internal buffers untouched (§4 complexity note).
        if self.candles and self.candles[-1].close_time == candle.close_time:
            if self.last_state is not None:
                dup = dict(self.last_state)
                if "pit" in dup and isinstance(dup["pit"], dict):
                    dup["pit"] = dict(dup["pit"])
                    dup["pit"]["duplicate"] = True
                return dup
            return self._build_state(as_of=candle.close_time, duplicate=True)
        reason = self._validate_candle(candle)
        if reason is not None:
            # §3.7: invalid candle ⇒ discard, log, Q0 — buffers untouched.
            return {"quality": "Q0", "reason": reason,
                    "error": "invalid_candle",
                    "as_of": int(candle.close_time or 0)}
        prev = self.candles[-1] if self.candles else None
        if prev is not None and self._gap_break(prev, candle):
            self._reset_smoothers()
        self.candles.append(candle)
        self.bar_index += 1

        lr = log_return(candle.close, prev.close if prev else None)
        if lr is not None:
            self.log_returns.append(lr)
            v_smooth = self.ema_vel.update(lr)
            if v_smooth is not None:
                self.vel_smooth.append(v_smooth)
                if len(self.vel_smooth) >= 2:
                    delta_v = self.vel_smooth[-1] - self.vel_smooth[-2]
                    a_smooth = self.ema_acc.update(delta_v)
                    if a_smooth is not None:
                        self.acc_smooth.append(a_smooth)
                else:
                    self.ema_acc.update(0.0)

        # RSI (Wilder RMA) — §3.3
        rsi_val: Optional[float] = None
        if prev is not None:
            delta_c = candle.close - prev.close
            ag = self.rma_gain.update(max(delta_c, 0.0))
            al = self.rma_loss.update(max(-delta_c, 0.0))
            if ag is not None and al is not None:
                if al < EPS and ag < EPS:
                    rsi_val = 50.0
                elif al < EPS:
                    rsi_val = 100.0
                else:
                    rs = ag / max(al, EPS)
                    rsi_val = 100.0 - 100.0 / (1.0 + rs)
                self.rsi_hist.append(rsi_val)

        # MACD — §3.3
        ef = self.ema_fast.update(candle.close)
        es = self.ema_slow.update(candle.close)
        if ef is not None and es is not None:
            line = ef - es
            sig = self.ema_macd_sig.update(line)
            if sig is not None:
                self.macd_hist_hist.append(line - sig)

        self.volume_ma_buf.append(candle.volume)
        self.aux_by_bar.append(self._aux_value())
        self._update_pivots()
        return self._build_state(as_of=candle.close_time)

    # -- state construction (§5.1 schema) ---------------------------------------
    def _build_state(self, as_of: int, duplicate: bool = False,
                     q_tag: Optional[str] = None,
                     error: Optional[str] = None) -> Dict[str, Any]:
        min_history = max(50, int(self.p.z_window),
                          int(self.p.macd_slow))
        if len(self.candles) < min_history and q_tag is None:
            # §5.2 Q1 warmup: refusal state, never a synthetic neutral value.
            return {"quality": "QX", "reason": "INSUFFICIENT_HISTORY_Q1",
                    "as_of": int(as_of)}
        mz, mu, sd = momentum_z(self.vel_smooth, int(self.p.z_window))
        vr, vz, _vol_mu = volume_features(self.volume_ma_buf)
        corr_w = int(self.p.corr_window)
        corr = (pearson_corr(list(self.mz_hist)[-corr_w:],
                             list(self.vz_hist)[-corr_w:])
                if len(self.mz_hist) >= 5 else 0.0)
        if len(self.vel_smooth) > 0 and mz is not None:
            self.mz_hist.append(mz)
            self.vz_hist.append(vz if vz is not None else 0.0)

        v_t = self.vel_smooth[-1] if self.vel_smooth else 0.0
        a_t = self.acc_smooth[-1] if self.acc_smooth else 0.0
        # ISSUE-CP5-001: θ_acc is z-scale (§6 units; §9 case study) ⇒ a_z.
        sigma_v = sd if (sd is not None and sd > EPS) else EPS
        a_z = a_t / sigma_v if sigma_v else 0.0
        rsi = self.rsi_hist[-1] if self.rsi_hist else 50.0
        macd_hist = self.macd_hist_hist[-1] if self.macd_hist_hist else 0.0

        # Stochastic — §3.3
        n_st = int(self.p.stoch_period)
        stoch_k = 50.0
        stoch_d = 50.0
        if len(self.candles) >= n_st:
            recent = list(self.candles)[-n_st:]
            hh = max(c.high for c in recent)
            ll = min(c.low for c in recent)
            if hh - ll > EPS:
                stoch_k = 100.0 * (self.candles[-1].close - ll) / (hh - ll)
            self.stoch_k_hist.append(stoch_k)
            stoch_d = sum(self.stoch_k_hist) / len(self.stoch_k_hist)

        # MvZ — §3.6 (sign-preserving form used by the §4 reference)
        mvz = 0.0
        if mz is not None and vr is not None:
            mvz = mz * min(vr / 2.0, 1.0) * (abs(corr) if corr != 0 else 1.0)
            if vr == 0.0:
                mvz = 0.0                       # §3.6 edge V=0 ⇒ MvZ=0

        flags = impulse_exhaustion_flags(
            mz, a_z, float(self.p.impulse_z), float(self.p.accel_threshold),
            mvz=mvz if vr is not None else None,
            mvz_prev=self.last_mv_z if vr is not None else None,
            vr=vr, vr_prev=self.last_vr)

        div_ols, conv_ols = self._detect_divergence_ols()
        div_pivot = self._detect_divergence_pivot()
        div_event: Optional[DivergenceEvent] = None
        div_method = "NONE"
        disagreement = False
        if div_ols and div_pivot and div_ols.kind == div_pivot.kind:
            div_event = div_pivot
            div_event.method = "BOTH"
            div_event.beta_price = div_ols.beta_price
            div_event.beta_mom = div_ols.beta_mom
            div_method = "BOTH"
        elif div_ols and div_pivot:
            # §3.4: both fire but disagree ⇒ Q2 (ISSUE-CP5-007); the pivot
            # record (richer, both pivots stored) is the reported event.
            div_event = div_pivot
            div_method = "PIVOT"
            disagreement = True
        elif div_pivot:
            div_event = div_pivot
            div_method = "PIVOT"
        elif div_ols:
            div_event = div_ols
            div_method = "OLS"
        kind = div_event.kind if div_event else "NONE"
        if div_event is None and conv_ols is not None:
            div_event = conv_ols
            div_method = "OLS"
            kind = "CONVERGENCE"

        # Q-tag — §5.2 + §4 reference cascade
        if q_tag is None:
            if error:
                q = "Q0"
            elif len(self.candles) < max(int(self.p.z_window),
                                         int(self.p.macd_slow)):
                q = "Q1"
            elif div_event is not None and div_method == "BOTH":
                q = "Q4" if len(self.candles) >= 100 else "Q3"
            elif len(self.vel_smooth) >= int(self.p.z_window):
                q = "Q3"
            else:
                q = "Q2"
            if disagreement and q in ("Q3", "Q4"):
                q = "Q2"                        # §3.4 disagreement ⇒ Q2
            # §5.2 downgrade rules:
            if vr is not None and float(self.candles[-1].volume) == 0.0 \
                    and q == "Q3":
                q = "Q2"                        # V=0 ⇒ Q3→Q2
        else:
            q = q_tag
        q = self._apply_context_downgrade(q)

        neutral = mz is not None and abs(mz) < 0.5
        core_dict = {
            "v": v_t, "a": a_t, "mz": mz, "mvz": mvz, "rsi": rsi,
            "as_of": int(as_of),
            "symbol": self.candles[-1].symbol if self.candles else "UNKNOWN",
            "interval": self.candles[-1].interval if self.candles else "1h",
            "q": q,
        }
        snapshot = canonical_snapshot_id(ENGINE, CONTRACT_VERSION, core_dict)
        state: Dict[str, Any] = {
            "contract_version": CONTRACT_LABEL,
            "schema_version": CONTRACT_VERSION,
            "engine_code": ENGINE,
            "as_of": int(as_of),
            "symbol": core_dict["symbol"],
            "interval": core_dict["interval"],
            "snapshot_id": snapshot,
            "q_tag": q,
            "param_hash": self._phash,
            "momentum": {
                "velocity_raw": self.log_returns[-1] if self.log_returns
                else 0.0,
                "velocity_smooth_ema14": v_t,
                "acceleration_smooth_ema5": a_t,
                "acceleration_z": a_z,          # ISSUE-CP5-001 (diagnostic)
                "momentum_z": mz,
                "mu_z": mu,
                "sigma_z": sd,
            },
            "volume_context": {
                "volume_ratio": vr,
                "volume_z": vz,
                "mvz": mvz,
                "corr_mz_vz_20": corr,
            },
            "indicators": {
                "rsi_wilder_rma14": rsi,
                "rsi_method": "RMA = (prev*(n-1)+gain)/n",
                "roc_10": (roc([c.close for c in self.candles],
                               int(self.p.roc_window)) or 0.0),
                "stoch_k_14": stoch_k,
                "stoch_d_3": stoch_d,
                "macd": {
                    "ema12": self.ema_fast.value if self.ema_fast.value
                    is not None else 0.0,
                    "ema26": self.ema_slow.value if self.ema_slow.value
                    is not None else 0.0,
                    "line": ((self.ema_fast.value - self.ema_slow.value)
                             if self.ema_fast.value is not None
                             and self.ema_slow.value is not None else 0.0),
                    "signal_ema9": self.ema_macd_sig.value
                    if self.ema_macd_sig.value is not None else 0.0,
                    "hist": macd_hist,
                },
            },
            "events": {
                "impulse_bull": bool(flags["impulse_bull"]),
                "impulse_bear": bool(flags["impulse_bear"]),
                "exhaustion_bull": bool(flags["exhaustion_bull"]),
                "exhaustion_bear": bool(flags["exhaustion_bear"]),
                "momentum_neutral": bool(neutral),
                "divergence": {
                    "present": div_event is not None
                    and kind != "CONVERGENCE",
                    "kind": kind,
                    "method": div_method if div_event is not None else "NONE",
                    "D_mag": div_event.D_mag if div_event else 0.0,
                    "beta_price": div_event.beta_price if div_event else None,
                    "beta_mom": div_event.beta_mom if div_event else None,
                    "price_pivots": ([asdict(pp) for pp
                                      in div_event.price_pivots]
                                     if div_event else []),
                    "mom_pivots": ([asdict(pp) for pp in div_event.mom_pivots]
                                   if div_event else []),
                    "pit_proof": div_event.pit_proof if div_event else {},
                    "ols_disagrees": disagreement,
                },
            },
            "pit": {
                "last_closed": int(as_of),
                "pivot_min_bars": int(self.p.pivot_min_bars),
                "is_pit_safe": True,
                "duplicate": bool(duplicate),
            },
            "error": error,
        }
        self.last_mz = mz if mz is not None else self.last_mz
        self.last_mv_z = mvz
        self.last_vr = vr
        self.last_state = state
        return state

    def _apply_context_downgrade(self, q: str) -> str:
        """§5.2 downgrade rule: an incompatible TrendContext version moves
        the Q-tag one level down (Q4→Q3 etc.). Absent context is permitted
        (§1.5 optional input) and never downgrades."""
        if self._trend_ctx_incompatible:
            order = ["Q0", "Q1", "Q2", "Q3", "Q4", "Q5"]
            if q in order:
                i = order.index(q)
                return order[max(0, i - 1)]
        return q

    _trend_ctx_incompatible: bool = False

    def set_trend_context(self, trend_context: Optional[Dict[str, Any]],
                          ) -> None:
        """§1.5 ``Input.TrendContext?`` — the canonical E09_Trend v4.0.0
        projection. Version check: major must equal 4; absent ⇒ no effect."""
        self._trend_ctx_incompatible = _incompatible_version(trend_context)

    def set_volatility_context(self,
                               volatility_context: Optional[Dict[str, Any]],
                               ) -> None:
        """§1.5 ``Input.VolatilityContext?`` — the canonical E04_Volatility
        v4.0.0 projection (``regime``); consumed as context only."""
        self._vol_ctx_incompatible = _incompatible_version(volatility_context)

    _vol_ctx_incompatible: bool = False


def _incompatible_version(ctx: Optional[Dict[str, Any]]) -> bool:
    if ctx is None:
        return False
    raw = str(ctx.get("contract_version") or ctx.get("version") or "")
    digits = "".join(ch for ch in raw.split("/")[-1] if ch.isdigit() or
                     ch == ".")
    parts = [p for p in digits.split(".") if p]
    if not parts:
        return True                       # unparseable ⇒ fail-closed
    try:
        return int(parts[0]) != 4
    except ValueError:
        return True


# ---------------------------------------------------------------------------
# §1.6 — inter-engine output mapping (consumer: E11 Regime)
# ---------------------------------------------------------------------------


def momentum_state_projection(state: Dict[str, Any]) -> Dict[str, Any]:
    """§1.6 derived view of the frozen MomentumState: ``momentum_state_raw``
    ∈ {IMPULSIVE, NEUTRAL, EXHAUSTED} + ``impulse_score`` ∈ [0,1]. No new
    internal state, no schema change.

    ``impulse_score`` (unspecified formula — ISSUE-CP5-008, deterministic
    derived normalization): ``min(1, |Mz| / (2·θ_imp))`` while an impulse is
    ACTIVE, else 0.0."""
    events = state.get("events", {})
    mz = state.get("momentum", {}).get("momentum_z")
    exhausted = bool(events.get("exhaustion_bull")
                     or events.get("exhaustion_bear"))
    impulsive = bool(events.get("impulse_bull")
                     or events.get("impulse_bear")) and not exhausted
    raw = "EXHAUSTED" if exhausted else ("IMPULSIVE" if impulsive
                                         else "NEUTRAL")
    th_imp = 2.0
    score = 0.0
    if raw == "IMPULSIVE" and mz is not None:
        score = min(1.0, abs(float(mz)) / (2.0 * th_imp))
    return {"momentum_state_raw": raw, "impulse_score": score,
            "as_of": state.get("as_of"),
            "contract_version": CONTRACT_LABEL}


# ---------------------------------------------------------------------------
# §5 schema validation
# ---------------------------------------------------------------------------


def validate_state_schema(state: Dict[str, Any]) -> None:
    """§5.1 MomentumState conformance (required keys, enums, ranges,
    snapshot/param-hash shapes). Raises ValueError on any violation."""
    for key in MOMENTUM_STATE_REQUIRED:
        if key not in state:
            raise ValueError(f"E10_STATE_SCHEMA_QX: missing {key}")
    import re
    if not re.match(r"^E10_Momentum/\d+\.\d+\.\d+$",
                    str(state["contract_version"])):
        raise ValueError("E10_STATE_SCHEMA_QX: contract_version pattern")
    if state["schema_version"] != CONTRACT_VERSION:
        raise ValueError("E10_STATE_SCHEMA_QX: schema_version")
    if state["engine_code"] != ENGINE:
        raise ValueError("E10_STATE_SCHEMA_QX: engine_code")
    if not re.match(r"^[0-9a-f]{64}$", str(state["snapshot_id"])):
        raise ValueError("E10_STATE_SCHEMA_QX: snapshot_id pattern")
    if state["q_tag"] not in Q_TAGS:
        raise ValueError("E10_STATE_SCHEMA_QX: q_tag enum")
    ph = str(state["param_hash"])
    if len(ph) != 12:
        raise ValueError("E10_STATE_SCHEMA_QX: param_hash length 12")
    if state["interval"] not in INTERVALS:
        raise ValueError("E10_STATE_SCHEMA_QX: interval enum (ISSUE-CP5-005:"
                         " the frozen 14-TF universe governs)")
    mom = state["momentum"]
    for key in ("velocity_raw", "velocity_smooth_ema14",
                "acceleration_smooth_ema5", "momentum_z"):
        if key not in mom:
            raise ValueError(f"E10_STATE_SCHEMA_QX: momentum.{key}")
    vc = state["volume_context"]
    for key in ("volume_ratio", "volume_z", "mvz", "corr_mz_vz_20"):
        if key not in vc:
            raise ValueError(f"E10_STATE_SCHEMA_QX: volume_context.{key}")
    if vc["volume_ratio"] is not None and float(vc["volume_ratio"]) < 0:
        raise ValueError("E10_STATE_SCHEMA_QX: volume_ratio minimum 0")
    if not -1.0 <= float(vc["corr_mz_vz_20"]) <= 1.0:
        raise ValueError("E10_STATE_SCHEMA_QX: corr range")
    ind = state["indicators"]
    for key in ("rsi_wilder_rma14", "roc_10", "stoch_k_14", "stoch_d_3",
                "macd"):
        if key not in ind:
            raise ValueError(f"E10_STATE_SCHEMA_QX: indicators.{key}")
    if not 0.0 <= float(ind["rsi_wilder_rma14"]) <= 100.0:
        raise ValueError("E10_STATE_SCHEMA_QX: rsi range")
    for key in ("ema12", "ema26", "line", "signal_ema9", "hist"):
        if key not in ind["macd"]:
            raise ValueError(f"E10_STATE_SCHEMA_QX: macd.{key}")
    ev = state["events"]
    for key in ("impulse_bull", "impulse_bear", "exhaustion_bull",
                "exhaustion_bear", "divergence"):
        if key not in ev:
            raise ValueError(f"E10_STATE_SCHEMA_QX: events.{key}")
    div = ev["divergence"]
    for key in ("present", "kind", "method", "D_mag"):
        if key not in div:
            raise ValueError(f"E10_STATE_SCHEMA_QX: divergence.{key}")
    if div["kind"] not in DIVERGENCE_KINDS:
        raise ValueError("E10_STATE_SCHEMA_QX: divergence.kind enum")
    if div["method"] not in DIVERGENCE_METHODS:
        raise ValueError("E10_STATE_SCHEMA_QX: divergence.method enum")
    if float(div["D_mag"]) < 0:
        raise ValueError("E10_STATE_SCHEMA_QX: D_mag minimum 0")
    if state["pit"].get("is_pit_safe") is not True:
        raise ValueError("E10_STATE_SCHEMA_QX: is_pit_safe const true")


# ---------------------------------------------------------------------------
# §8 validation helpers (battery support — deterministic, no new rules)
# ---------------------------------------------------------------------------


def deterministic_replay_check(candles: Sequence[Candle],
                               params: Optional[EngineParams] = None
                               ) -> bool:
    """§8.2: two from-scratch runs must yield identical snapshot_ids."""
    def run() -> List[Any]:
        eng = MomentumEngine(params)
        return [eng.update(c).get("snapshot_id") for c in candles]
    return run() == run()


def no_future_leak_check(engine: MomentumEngine, state: Dict[str, Any],
                         interval: str) -> bool:
    """§8.3: every confirmed pivot satisfies confirmed_at ≤ as_of bar and
    pivot_time + k·interval_ms ≤ as_of time."""
    interval_ms = TF_SECONDS.get(interval, 3600) * 1000
    k = int(engine.p.pivot_min_bars)
    as_of = int(state.get("as_of", 0))
    for plist in (engine.price_high_pivots, engine.price_low_pivots,
                  engine.mom_high_pivots, engine.mom_low_pivots):
        for piv in plist:
            if piv.confirmed_at > engine.bar_index - 1:
                return False
            if piv.time + k * interval_ms > as_of:
                return False
    return True


def divergence_success(kind: str, bars_after: Sequence[Dict[str, Any]],
                       atr: float, horizon: int = 10) -> Optional[bool]:
    """§8.5 success definitions (Regular Bearish: drop ≥ 0.8·ATR within 10
    candles; Regular Bullish: rise ≥ 0.8·ATR; Hidden Bullish: a higher high
    follows; Hidden Bearish: a lower low follows)."""
    window = list(bars_after)[:horizon]
    if not window or atr <= 0:
        return None
    if kind == "REGULAR_BEARISH":
        entry = float(window[0]["c"])
        return any(float(b["l"]) <= entry - 0.8 * atr for b in window)
    if kind == "REGULAR_BULLISH":
        entry = float(window[0]["c"])
        return any(float(b["h"]) >= entry + 0.8 * atr for b in window)
    if kind == "HIDDEN_BULLISH":
        hh = max(float(b["h"]) for b in window)
        return hh > float(window[0]["h"])
    if kind == "HIDDEN_BEARISH":
        ll = min(float(b["l"]) for b in window)
        return ll < float(window[0]["l"])
    return None


def calibration_report(outcomes: Sequence[Tuple[str, bool]]) -> Dict[str, Any]:
    """§8.5 per-kind n/k/p + Wilson CI."""
    out: Dict[str, Any] = {}
    for kind in ("REGULAR_BEARISH", "REGULAR_BULLISH", "HIDDEN_BULLISH",
                 "HIDDEN_BEARISH"):
        rows = [ok for k, ok in outcomes if k == kind]
        n = len(rows)
        k_hits = sum(1 for ok in rows if ok)
        p = (k_hits / n) if n else None
        out[kind] = {"n": n, "k": k_hits, "p": p,
                     "wilson_ci": wilson_ci(p, n) if n else None}
    return out


def redundancy_report(mz_series: Sequence[float],
                      trend_series: Optional[Sequence[float]] = None,
                      volz_series: Optional[Sequence[float]] = None
                      ) -> Dict[str, Any]:
    """§8.6 numeric redundancy thresholds: |ρ(Mz, TrendScore)| < 0.75 (warn)
    / > 0.85 (Q downgrade); |ρ(Mz, VolatilityZ)| < 0.6 expected."""
    out: Dict[str, Any] = {"rho_trend": None, "rho_volz": None,
                           "redundancy_warning": False,
                           "quality_downgrade": False, "volz_ok": None}
    if trend_series is not None:
        r = abs(pearson_corr(list(mz_series), list(trend_series)))
        out["rho_trend"] = r
        out["redundancy_warning"] = r >= 0.75
        out["quality_downgrade"] = r > 0.85
    if volz_series is not None:
        rz = abs(pearson_corr(list(mz_series), list(volz_series)))
        out["rho_volz"] = rz
        out["volz_ok"] = rz < 0.6
    return out


def load_v3_adapter(payload: Dict[str, Any]) -> Dict[str, Any]:
    """§8.7 read-only research/backtest migration adapter. v3 is NOT a live
    runtime interface; ambiguity or an unknown shape fails closed."""
    version = str(payload.get("version") or payload.get("schema_version")
                  or "")
    if not version.startswith("3."):
        raise ValueError("E10_V3_ADAPTER_QX: not a v3 payload")
    mom = payload.get("momentum")
    if not isinstance(mom, dict) or "momentum_z" not in mom:
        raise ValueError("E10_V3_ADAPTER_QX: ambiguous v3 shape")
    return {"contract_version": CONTRACT_LABEL,
            "schema_version": CONTRACT_VERSION, "engine_code": ENGINE,
            "as_of": int(payload.get("as_of", 0)),
            "momentum": dict(mom),
            "q_tag": "Q1",           # migration emits Q1 pending revalidation
            "migrated_from": version}


# ---------------------------------------------------------------------------
# §4 batch driver + bar helpers
# ---------------------------------------------------------------------------


def candle_from_bar(bar: Dict[str, Any], symbol: str = "UNKNOWN",
                    interval: str = "1h") -> Candle:
    """Bar dict ({ts,o,h,l,c,v[,is_closed,close_time]}) → §1.5 Candle.
    ``close_time`` defaults to ``ts + interval`` when absent."""
    ts = int(bar.get("ts", bar.get("open_time", 0)))
    close_time = int(bar.get("close_time",
                             ts + TF_SECONDS.get(interval, 3600) * 1000))
    return Candle(open=float(bar["o"]), high=float(bar["h"]),
                  low=float(bar["l"]), close=float(bar["c"]),
                  volume=float(bar.get("v", 0.0)), open_time=ts,
                  close_time=close_time,
                  is_closed=bool(bar.get("is_closed", True)),
                  symbol=str(bar.get("symbol", symbol)),
                  interval=str(bar.get("interval", interval)))


def observation_to_bar(obs: MarketObservation,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
    """MarketObservation → the ``{ts,o,h,l,c,v,is_closed}`` bar shape."""
    ts_ms = 0
    try:
        dt = datetime.datetime.fromisoformat(
            str(obs.timestamp).replace("Z", "+00:00"))
        ts_ms = int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        ts_ms = 0
    return {"ts": ts_ms, "o": float(obs.open), "h": float(obs.high),
            "l": float(obs.low), "c": float(obs.close),
            "v": float(obs.volume),
            "is_closed": obs.status == "CLOSED" if obs.status else
            bool(getattr(obs, "is_closed", True)),
            "timeframe": timeframe}


def run_engine(bars: Sequence[Dict[str, Any]],
               params: Optional[Dict[str, Any]] = None,
               symbol: str = "UNKNOWN", interval: str = "1h",
               as_of_ms: Optional[int] = None,
               trend_context: Optional[Dict[str, Any]] = None,
               volatility_context: Optional[Dict[str, Any]] = None
               ) -> Dict[str, Any]:
    """Batch driver over closed-candle dicts → the MomentumState payload for
    the last accepted candle + the §5.3 catalog events fired on it."""
    p = params if isinstance(params, EngineParams) else get_params(params)
    eng = MomentumEngine(p)
    eng.set_trend_context(trend_context)
    eng.set_volatility_context(volatility_context)
    state: Dict[str, Any] = {"quality": "QX",
                             "reason": "INSUFFICIENT_HISTORY_Q1",
                             "as_of": int(as_of_ms or 0)}
    for bar in bars:
        cand = candle_from_bar(bar, symbol=symbol, interval=interval)
        out = eng.update(cand)
        if "snapshot_id" in out:
            state = out
        elif out.get("quality") == "Q0":
            state = out
    if as_of_ms is not None and "as_of" in state:
        state = dict(state)
        state["as_of"] = int(as_of_ms)
    return {"state": state, "events": catalog_events(state),
            "engine": ENGINE, "contract_version": CONTRACT_VERSION,
            "n_bars": int(eng.bar_index)}


def catalog_events(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """§5.3 EV_MOM_xxx list fired by a state (empty for refusal states)."""
    events: List[Dict[str, Any]] = []
    if "events" not in state:
        return events
    ev = state["events"]
    as_of = int(state.get("as_of", 0))
    if ev.get("impulse_bull"):
        events.append({"code": "EV_MOM_001", "as_of": as_of, "state": state})
    if ev.get("impulse_bear"):
        events.append({"code": "EV_MOM_001b", "as_of": as_of, "state": state})
    if ev.get("exhaustion_bull"):
        events.append({"code": "EV_MOM_002", "as_of": as_of, "state": state})
    if ev.get("exhaustion_bear"):
        events.append({"code": "EV_MOM_002b", "as_of": as_of, "state": state})
    div = ev.get("divergence", {})
    code = KIND_TO_EVENT.get(str(div.get("kind", "NONE")))
    if code and (div.get("present") or div.get("kind") == "CONVERGENCE"):
        events.append({"code": code, "as_of": as_of, "state": state,
                       "divergence": div})
    if ev.get("momentum_neutral"):
        events.append({"code": "EV_MOM_008", "as_of": as_of, "state": state})
    return events


def e10_snapshot_id(payload: Dict[str, Any]) -> str:
    """§5.5 canonical snapshot identity (global contract delegation)."""
    return canonical_snapshot_id(ENGINE, CONTRACT_VERSION, payload)


# ---------------------------------------------------------------------------
# EngineBase binding (frozen contract — consumed, never patched)
# ---------------------------------------------------------------------------


class E10MomentumEngine(EngineBase):
    """E10_Momentum on the frozen EngineBase contract (v4.0.0).

    ``compute(symbol, timeframe, as_of, context)``; consumed context keys:
      ``window`` / ``provider`` — closed-candle window (catalog surface)
      ``e10_params``            — §6 overrides (unknown keys rejected)
      ``trend_context``         — optional canonical E09 v4.0.0 projection
                                  (incompatible version ⇒ Q downgrade §5.2)
      ``volatility_context``    — optional canonical E04 v4.0.0 projection
    Emits one ``EvidenceEvent`` per §5.3 catalog event fired on the last
    closed candle, on ``evidence.E10.{condition_state}``. Context only:
    every emission carries ``direction = 0`` (NG1 — momentum is never a
    standalone mandate; the E02 precedent for context engines).
    """

    engine_id = "E10"
    analyst_version = ANALYST_VERSION
    code_revision = "0" * 40

    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None
                ) -> List[EvidenceEvent]:
        context = context or {}
        window_obs = self._resolve_window(symbol, timeframe, as_of, context)
        if not window_obs:
            return []
        bars = [observation_to_bar(o, timeframe) for o in window_obs]
        result = run_engine(
            bars, params=context.get("e10_params"), symbol=symbol,
            interval=timeframe,
            trend_context=context.get("trend_context"),
            volatility_context=context.get("volatility_context"))
        self._last_n_bars = int(result["n_bars"])
        state = result["state"]
        if "snapshot_id" not in state:
            return []                    # QX/Q0 refusal — nothing fabricated
        quality = self._window_quality(window_obs)
        return [self._to_evidence(item, symbol, timeframe, quality, state)
                for item in result["events"]]

    def _resolve_window(self, symbol: str, timeframe: str, as_of: str,
                        context: Dict[str, Any]) -> List[MarketObservation]:
        window = context.get("window")
        if window is not None:
            return list(window)
        provider = context.get("provider")
        if provider is None:
            raise ValueError("MISSING_WINDOW_CONTEXT_QX")
        import asyncio
        import inspect
        bars = context.get("bars", 300)
        result = provider.get_window(symbol, timeframe, as_of, bars)
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return list(asyncio.run(result))
            raise ValueError("MISSING_WINDOW_CONTEXT_QX (async provider "
                             "inside a running loop — pass "
                             "context['window'])")
        return list(result)

    @staticmethod
    def _window_quality(window_obs: Sequence[MarketObservation]) -> float:
        if not window_obs:
            return 0.0
        comps = [float(o.completeness_pct or 0) / 100.0 for o in window_obs]
        return min(1.0, sum(comps) / len(comps))

    _CONF_BY_Q = {"Q4": 0.9, "Q3": 0.7, "Q2": 0.5, "Q1": 0.3, "Q0": 0.0,
                  "Q5": 1.0, "QX": 0.0}

    def _to_evidence(self, item: Dict[str, Any], symbol: str,
                     timeframe: str, quality: float,
                     state: Dict[str, Any]) -> EvidenceEvent:
        code = str(item["code"])
        name = EVENT_CATALOG[code]["name"]
        ts = int(state["as_of"])
        iso = datetime.datetime.fromtimestamp(
            ts / 1000.0, tz=datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.") + f"{ts % 1000:03d}Z"
        q_tag = str(state["q_tag"])
        mz = state["momentum"].get("momentum_z") or 0.0
        div = state["events"]["divergence"]
        if code in KIND_TO_EVENT.values():
            strength = min(1.0, max(0.0, float(div.get("D_mag", 0.0))))
            method = str(div.get("method", "NONE"))
            confidence = {"BOTH": 1.0, "PIVOT": 0.66, "OLS": 0.66,
                          "NONE": 0.5}.get(method, 0.5)
            if div.get("ols_disagrees"):
                confidence = 0.5          # §3.4 disagreement ⇒ Q2 tier
        else:
            strength = min(1.0, abs(float(mz)) / (2.0 *
                                                  float(self.p_impulse())))
            confidence = self._CONF_BY_Q.get(q_tag, 0.3)
        explanation = (f"E10 {code} {name} Mz={float(mz):.4f} "
                       f"q={q_tag} method={div.get('method', 'NONE')} "
                       f"D_mag={float(div.get('D_mag', 0.0)):.4f}")
        return EvidenceEvent(
            evidence_id=uuid_v7(),
            engine_id=self.engine_id,
            analyst_version=self.analyst_version,
            symbol=symbol, timeframe=timeframe,
            snapshot_id=str(state["snapshot_id"]),
            event_time=iso, availability_time=iso,
            observation_window={"interval": state["interval"],
                                "z_window": int(self.p_default().z_window),
                                "as_of_ms": ts},
            feature_snapshot_id=str(state["snapshot_id"]),
            feature_dependencies=("window",
                                  "I_Trend_v4(optional)",
                                  "I_Volatility_v4(optional)"),
            condition_state=f"{code}_{name.upper()}",
            direction=0,                   # context engine (NG1)
            strength=float(strength),
            confidence=float(confidence),
            quality=float(quality),
            validity="VALID" if q_tag in ("Q3", "Q4", "Q5") else "DEGRADED",
            fate_state=LifecycleState.ACTIVE if q_tag in ("Q3", "Q4", "Q5")
            else LifecycleState.CANDIDATE,
            age=float(max(self._last_n_bars, 1)),
            decay=math.exp(-1.0 / max(int(self.p_default().z_window), 1)),
            explanation=explanation[:500],
            parameter_version="E10-MOM-V4.0.0/DEFAULTS-v1",
            lineage=(f"mode_{self.p_default().reference_mode}",
                     f"q_{q_tag}"),
            resolution_class=q_tag,
        )

    _last_n_bars: int = 0

    @staticmethod
    def p_default() -> EngineParams:
        return EngineParams()

    def p_impulse(self) -> float:
        return float(E10_DEFAULTS["impulse_z"])


__all__ = [
    "ANALYST_VERSION", "CONTRACT_LABEL", "CONTRACT_VERSION",
    "DIVERGENCE_KINDS", "DIVERGENCE_METHODS", "E10MomentumEngine",
    "E10_DEFAULTS", "EMAState", "ENGINE", "EPS", "EVENT_CATALOG",
    "EngineParams", "FATES", "INTERVALS", "KIND_TO_EVENT", "MOMENTUM_STATE_REQUIRED",
    "MomentumEngine", "Pivot", "Q_TAGS", "REFERENCE_MODES", "TF_SECONDS",
    "Candle", "DivergenceEvent", "calibration_report", "candle_from_bar",
    "catalog_events", "classify_pivot_pair", "deterministic_replay_check", "divergence_mag_ols",
    "divergence_mag_pivot", "divergence_success", "e10_snapshot_id",
    "get_params", "impulse_exhaustion_flags", "load_v3_adapter",
    "log_return", "macd_state", "momentum_state_projection", "momentum_z",
    "no_future_leak_check", "observation_to_bar", "ols_slope", "param_hash",
    "pearson_corr", "redundancy_report", "roc", "rsi_series", "run_engine",
    "stochastic_kd", "validate_state_schema", "volume_features",
    "wilson_ci",
]
