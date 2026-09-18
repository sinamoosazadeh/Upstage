"""APEX_GEN5 data-catalog contracts.

- AI.4 canonical MarketObservation fields + fail-fast validation order
  (T-DC-001..004).
- §3.12 FeatureID / ValidityPolicy / FeatureContract dataclasses.
- The frozen 24-field Evidence Event contract (Ch.6 §8; mapping at
  APEX_GEN5.md L18185–18205; AI.12 Phase 2/3).
- ``catalog.get`` result shape (Ch.5): status ∈ {OK, MISSING, STALE,
  UNAVAILABLE, INVALID}; unknown feature_id → INVALID; future as_of →
  INVALID (PIT).
- OI availability enum: AVAILABLE / STALE / MISSING / INVALID / DEGRADED
  (AI.6; Q_oi STALE weight = 0.5 — canonical).
"""

from __future__ import annotations

import datetime as _dt
import enum
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from apex.errors import ERROR_REGISTRY
from apex.identity.hashes import sha256_hex

# ---------------------------------------------------------------------------
# Universe constants — mirror of params/universe_v1.yaml; validation uses
# the params file as the single source (loaded by callers), these are the
# document-frozen literals asserted by tests.
CORE10_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
)
TIMEFRAMES_14 = (
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h",
    "6h", "8h", "12h", "1d", "1w", "1mo",
)
CANDLE_STATUSES = ("OPEN", "PARTIAL", "CLOSED")


class OIState(str, enum.Enum):
    """Canonical OI availability states (AI.6)."""
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"
    DEGRADED = "DEGRADED"


class CandleStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"


class CatalogStatus(str, enum.Enum):
    """catalog.get status (Ch.5)."""
    OK = "OK"
    MISSING = "MISSING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


class LifecycleState(str, enum.Enum):
    """Derived-object lifecycle (AI.4): CANDIDATE → CONFIRMED → ACTIVE →
    {MITIGATED, INVALIDATED, EXPIRED, SUPERSEDED}. Terminal states never
    revert."""
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            LifecycleState.INVALIDATED,
            LifecycleState.EXPIRED,
            LifecycleState.SUPERSEDED,
        )


_UTC_MS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


def parse_utc_ms(timestamp: str) -> _dt.datetime:
    """Strict ISO 8601 UTC with millisecond precision (AI.4 step 5)."""
    if not _UTC_MS_RE.match(timestamp):
        raise ValueError(
            "INVALID_UTC_TIMESTAMP: expected YYYY-MM-DDTHH:MM:SS.fffZ"
        )
    return _dt.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=_dt.timezone.utc
    )


# ---------------------------------------------------------------------------
# MarketObservation (AI.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketObservation:
    """Canonical raw observation (AI.4 field table). Prices/volumes are
    Decimals; money stays Decimal/TEXT at the store boundary (§2.2)."""

    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    oi: Optional[Decimal]
    timestamp: str                 # ISO 8601 UTC, ms precision
    sequence: int                  # strictly increasing per symbol+tf
    status: str                    # OPEN / PARTIAL / CLOSED
    # operational/ingest metadata (not part of the AI.4 10-field core):
    source: str = "TOOBIT"
    availability_time: Optional[str] = None   # ISO 8601 UTC ms (PIT)
    oi_timestamp: Optional[str] = None
    oi_lag_seconds: Optional[float] = None    # None ⇒ OI MISSING (never 0)
    source_health: float = 1.0
    gap_count: int = 0
    expected_count: int = 1
    completeness_pct: float = 100.0
    delay_seconds: float = 0.0

    @property
    def is_closed(self) -> bool:
        return self.status == "CLOSED"

    def content_hash(self) -> str:
        """Duplicate-detection hash (AI.4 step 7): canonical over
        (symbol, timeframe, timestamp, open, close, volume)."""
        payload = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "open": self.open,
            "close": self.close,
            "volume": self.volume,
        }
        from apex.identity.hashes import content_id
        return content_id(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "oi": self.oi,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "status": self.status,
            "source": self.source,
            "availability_time": self.availability_time,
            "oi_timestamp": self.oi_timestamp,
            "oi_lag_seconds": self.oi_lag_seconds,
            "source_health": self.source_health,
            "gap_count": self.gap_count,
            "expected_count": self.expected_count,
            "completeness_pct": self.completeness_pct,
            "delay_seconds": self.delay_seconds,
        }


class ValidationError(ValueError):
    """Fail-fast validation rejection carrying the Ch.7 error code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def validate_market_observation(
    obs: MarketObservation,
    prev_sequence: Optional[int] = None,
) -> None:
    """AI.4 validation order (sequential, fail-fast; T-DC-002).

    Steps 1–8 are structural; step 9 (availability vs as_of) is enforced by
    the PIT module; step 10 (source health) is reported via the quality
    vector. Raises ValidationError with the first failing Ch.7 code.
    """
    # 1. schema conformance (T-DC-001: all 10 fields present, typed)
    for name in ("symbol", "timeframe", "timestamp", "status"):
        if not isinstance(getattr(obs, name), str) or not getattr(obs, name):
            raise ValidationError("E-Q-001", f"missing/blank field {name}")
    for name in ("open", "high", "low", "close", "volume"):
        if not isinstance(getattr(obs, name), Decimal):
            raise ValidationError("E-Q-001", f"field {name} not Decimal")
    if not isinstance(obs.sequence, int):
        raise ValidationError("E-Q-001", "sequence not int")
    # 2. finite numerics (NaN/Inf forbidden — never silently dropped)
    for name in ("open", "high", "low", "close", "volume"):
        v = getattr(obs, name)
        if not v.is_finite():
            code = "E-NUM-001" if v.is_nan() else "E-NUM-002"
            raise ValidationError(code, f"{name} non-finite")
    if obs.oi is not None and not obs.oi.is_finite():
        code = "E-NUM-001" if obs.oi.is_nan() else "E-NUM-002"
        raise ValidationError(code, "oi non-finite")
    # 3. OHLC bounds: H >= max(O,C), L <= min(O,C), H >= L, no swaps
    if obs.open < 0 or obs.high < 0 or obs.low < 0 or obs.close < 0:
        raise ValidationError("E-Q-001", "negative OHLC price")
    if obs.high < max(obs.open, obs.close) or obs.low > min(obs.open, obs.close):
        raise ValidationError("QX_INVALID", "OHLC bounds violated (H<max(O,C) or L>min(O,C))")
    if obs.high < obs.low:
        raise ValidationError("QX_INVALID", "High < Low — physically impossible; reject, never swap")
    # 4. volume and OI non-negative; zero volume permitted only for OPEN
    if obs.volume < 0:
        raise ValidationError("QX_INVALID", "negative volume")
    if obs.volume == 0 and obs.status != "OPEN":
        raise ValidationError("E-Q-001", "zero volume only permitted for OPEN status")
    if obs.oi is not None and obs.oi < 0:
        raise ValidationError("QX_INVALID", "negative OI")
    # 5. UTC timestamp format
    try:
        parse_utc_ms(obs.timestamp)
    except ValueError as exc:
        raise ValidationError("E-Q-001", str(exc)) from exc
    # 6. sequence strictly increasing per symbol+timeframe
    if prev_sequence is not None and obs.sequence <= prev_sequence:
        raise ValidationError("E-Q-001",
                              f"sequence {obs.sequence} not strictly increasing "
                              f"after {prev_sequence}")
    # 7. duplicate detection happens against the store's recent ledger
    #    (sqlite_store ingest) using obs.content_hash().
    # 8. closed-only rule for the feature pipeline is enforced by consumers
    #    (quality vector rejects is_closed=False with CANDIDATE).


def oi_state_for(oi: Optional[Decimal], lag_seconds: Optional[float],
                 threshold_seconds: float) -> Tuple[OIState, float]:
    """Canonical OI state + Q_oi (AI.6 + §2.1). Missing OI is NEVER 0
    (T-DC-004). STALE weight = 0.5 (canonical; not 0.9)."""
    if oi is None:
        return OIState.MISSING, 0.0
    if oi < 0:
        return OIState.INVALID, 0.0
    if lag_seconds is None:
        return OIState.MISSING, 0.0
    if lag_seconds <= threshold_seconds:
        return OIState.AVAILABLE, 1.0
    if lag_seconds <= 5 * threshold_seconds:
        return OIState.STALE, 0.5
    return OIState.DEGRADED, 0.2


# ---------------------------------------------------------------------------
# §3.12 feature contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureID:
    full_id: str   # e.g. APEX.L00.ATOM.CNDL.BODY_RATIO.RATIO.V1
    alias: str     # e.g. body_ratio
    super_layer: Literal["ATOM", "MOLE", "ORGN"]
    family: Literal["CNDL", "VOL", "MOM", "STRC", "LIQ", "PTRN", "SEQ", "CTXT"]
    metric: Literal["PCT", "RATIO", "STRENGTH", "PROB", "SCORE", "VALUE",
                    "POS", "SIZE", "BULL", "BEAR"]
    normalization: Literal["RAW", "NORM", "PCTL", "ZSCORE"]
    version: int = 1


@dataclass(frozen=True)
class ValidityPolicy:
    validity_candles: int
    decay_type: Literal["none", "linear", "exponential"]
    decay_formula: str  # e.g. exp(-0.02*age)


@dataclass(frozen=True)
class FeatureContract:
    id: FeatureID
    name: str
    description: str
    formula: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    lookback: int
    warmup: int
    epsilon: Dict[str, Any]
    unit: str
    range: Tuple[float, float]
    tolerance: float
    validity: ValidityPolicy
    stability: Literal["high", "medium", "low"]
    computation_cost: Literal["low", "medium", "high"]
    owner: str
    confidence_equation: str
    version: str = "v5.0.0"


# ---------------------------------------------------------------------------
# 24-field Evidence Event contract (Ch.6 §8 / AI.12; mapping L18185)
# ---------------------------------------------------------------------------

EVIDENCE_EVENT_FIELDS_24: Tuple[str, ...] = (
    "evidence_id",          #  1 UUIDv7 — unique evidence key
    "engine_id",            #  2 E01..E12 — producer
    "analyst_version",      #  3 SemVer + git40 (side-table)
    "symbol",               #  4
    "timeframe",            #  5
    "snapshot_id",          #  6 PIT binding
    "event_time",           #  7 event instant UTC (DDL timestamp_utc)
    "availability_time",    #  8 PIT condition (from snapshot)
    "observation_window",   #  9 (from snapshot)
    "feature_snapshot_id",  # 10 data capture version
    "feature_dependencies", # 11 input dependencies (DDL parent_ids)
    "condition_state",      # 12 preconditions (DDL event_type + validity)
    "direction",            # 13 (from event_type)
    "strength",             # 14 intensity on engine's own scale
    "confidence",           # 15 calibrated statistical confidence
    "quality",              # 16 data quality (zero removes, never permits)
    "validity",             # 17 conditional contract validity
    "fate_state",           # 18 CANDIDATE→CONFIRMED→ACTIVE→{...} (side-table)
    "age",                  # 19 (derivable)
    "decay",                # 20 (derivable, λ=0.1)
    "explanation",          # 21 human-readable (DDL raw)
    "parameter_version",    # 22 parameter class + version (side-table)
    "lineage",              # 23 derivation chain down to observation_id
    "resolution_class",     # 24 cross-engine reference frame Q0..QX (side-table)
)


@dataclass(frozen=True)
class EvidenceEvent:
    """Frozen 24-field evidence event (semantic reference contract)."""

    evidence_id: str
    engine_id: str
    analyst_version: str
    symbol: str
    timeframe: str
    snapshot_id: str
    event_time: str
    availability_time: str
    observation_window: Dict[str, Any]
    feature_snapshot_id: str
    feature_dependencies: Tuple[str, ...]
    condition_state: str
    direction: int                    # -1 / 0 / +1 (Ch.10 conflict law)
    strength: float
    confidence: float
    quality: float
    validity: str
    fate_state: LifecycleState
    age: Optional[float]
    decay: Optional[float]
    explanation: str
    parameter_version: str
    lineage: Tuple[str, ...]
    resolution_class: str             # Q0..QX

    def validate_24_fields(self) -> None:
        """Contract conformance: required non-null fields, engine_id ∈
        E01..E12, resolution_class ∈ Q0..QX, direction ∈ {-1,0,1},
        finite strength/confidence/quality."""
        if not self.evidence_id:
            raise ValueError("evidence_id empty (24-field contract #1)")
        if self.engine_id not in tuple(f"E{i:02d}" for i in range(1, 13)):
            raise ValueError(f"engine_id {self.engine_id!r} not E01..E12")
        if not self.analyst_version:
            raise ValueError("analyst_version empty (contract #3)")
        if not self.snapshot_id:
            raise ValueError("snapshot_id empty (contract #6)")
        if not self.event_time or not self.availability_time:
            raise ValueError("event_time/availability_time empty (#7/#8)")
        if self.direction not in (-1, 0, 1):
            raise ValueError(f"direction {self.direction!r} not in {{-1,0,1}}")
        for name, v in (("strength", self.strength),
                        ("confidence", self.confidence),
                        ("quality", self.quality)):
            if not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
                raise ValueError(f"{name} non-finite (contract #14–16)")
        if self.resolution_class not in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5", "QX"):
            raise ValueError(f"resolution_class {self.resolution_class!r} not Q0..QX")

    def to_ddl_row(self) -> Dict[str, Any]:
        """Map the 24-field contract onto Data-Plane columns (L18185)."""
        return {
            "evidence_id": self.evidence_id,
            "engine_id": self.engine_id,
            "timestamp_utc": self.event_time,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "event_type": self.condition_state,
            "snapshot_id": self.snapshot_id,
            "parent_ids": ",".join(self.feature_dependencies),
            "strength": self.strength,
            "confidence": self.confidence,
            "quality": self.quality,
            "validity": 1 if self.validity not in ("INVALID", "CANDIDATE") else 0,
            "raw": self.explanation,
            "lineage": ",".join(self.lineage),
        }


# ---------------------------------------------------------------------------
# catalog.get result shape (Ch.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogResult:
    feature_id: str
    symbol: str
    timeframe: str
    as_of: str
    value: Any
    q_component: float
    availability_time: Optional[str]
    snapshot_id: Optional[str]
    status: CatalogStatus
    reason: str
