"""PAPER plan bridge: governed engine context through SL-1 … SL-5.

This module is the concrete producer for ``PaperRuntime.plan_provider``.  It
is deliberately a *consumer* of engine output, not a second implementation of
an engine:

    governed engine context / persisted evidence
      → Evidence Fabric + conflict resolution
      → Context Fabric
      → Pattern admission
      → SF_FVG_SWEEP_REV + thirteen gates
      → bootstrap P/U/C forecast
      → StrategyProposal / arbitration
      → fourteen-veto Risk Kernel / TradePlan

The frozen engine contracts do not permit a bridge to invent missing E11
inputs, classifier tensors, probabilities, or setup numbers.  A context source
therefore has to provide the derived engine context (or complete persisted
EvidenceEvent/FabricEvidenceRef records) and the family inputs it owns.  A
normal bootstrap containing only raw candles is useful to the engines, but is
not by itself admissible evidence for this consumer; the bridge returns
``None`` and records a named refusal instead of manufacturing a plan.

The source seam is intentionally small and testable.  A callable supplied as
``context_source`` receives ``(symbol, timeframe, as_of)`` and may return a
mapping or an awaitable mapping.  When omitted, the bridge looks for the
store's explicitly named ``get_bridge_context``/``get_engine_context`` reader
methods.  A reader must return the full, governed context described by
``REQUIRED_CONTEXT_KEYS``; reduced ``evidence_event`` SQL rows are rejected
because the frozen 24-field event loses direction, lifecycle, lineage and
other fields at the DDL boundary.

No execution, ledger, adapter, network, or Telegram module is imported here.
The resulting mapping is consumed by the existing frozen FSM, which remains
the only venue path.  CONTRACT_VERSION is the same frozen v4 surface used by
the predecessor layers.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import inspect
import math
from collections.abc import Mapping as ABCMapping
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.data_catalog.contracts import (
    CORE10_SYMBOLS,
    TIMEFRAMES_14,
    EvidenceEvent,
    LifecycleState,
    MarketObservation,
    parse_utc_ms,
)
from apex.decision.pipeline import (
    arbitrate,
    build_proposal,
    eligibility,
    generate_candidates,
    rank,
    select,
)
from apex.fabric.conflict import (
    disagreement_of,
    quality_asymmetry_of,
    resolve,
    stale_fraction_of,
)
from apex.fabric.context import build_context
from apex.fabric.evidence import (
    EvidenceFabric,
    FabricEvidenceRef,
    EVIDENCE_LIFECYCLE_STATES,
    expiry_age_bars,
    lifecycle_of,
)
from apex.forecast.logistic import ForecastEvent, build_forecast
from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import sha256_hex
from apex.execution.fsm import build_trade_plan
from apex.pattern.detect import CATALOGUE, PatternEntity, assert_scoring_admissible, entity_for
from apex.playbook.pb_fvg_sweep_rev_a import (
    build_stops,
    instantiate_playbook,
)
from apex.risk.kernel import adjudicate
from apex.setup.family_sf_fvg_sweep_rev import (
    EMITTED,
    ENTRY_LOGIC_REF,
    FAMILY_ID,
    HORIZON_BARS,
    PLAYBOOK_ID,
    REQUIRED_EVIDENCE,
    evaluate_cell,
)

CONTRACT_VERSION = "4.0.0"

# A source can put these fields at the top level or under one of the named
# sections (engine_context/setup/forecast/risk/context).  They are not
# defaults: the bridge checks them before it calls a downstream authority.
REQUIRED_CONTEXT_KEYS: Tuple[str, ...] = (
    "events",
    "data_trust",
    "q_raw",
    "market_regime",
    "mtf_state",
    "utc_window_state",
    "is_overlap",
    "volatility_state",
    "structure_state",
    "regime_confidence",
    "regime_uncertainty",
    "divergence_magnitude",
    "temporal_window_validity",
    "atr",
    "fvg_zones",
    "bos",
    "regime_state",
    "e11_context",
    "direction",
    "pattern_id",
    "x",
    "forecast_quality",
    "forecast_rr",
    "forecast_cost_r",
    "window_qualities",
    "temporal_quality",
    "volatility_quality",
    "s_i",
    "q_i",
    "package",
    "p_min_tf",
    "c_min",
    "freshness_ok",
    "risk",
    "risk_state",
    "h_norm",
    "family_status",
    "arbitration",
)

# The risk input is intentionally explicit.  Defaults in risk.kernel are
# useful for its standalone frozen unit surface, but a production bridge must
# not turn a missing account/circuit-breaker measurement into permission.
REQUIRED_RISK_KEYS: Tuple[str, ...] = (
    "capital",
    "portfolio_exposure",
    "proposed_notional",
    "capital_hard_cap",
    "circuit_breaker_engaged",
    "emergency_state",
    "per_symbol_exposure",
    "symbol_cap",
    "portfolio_cap",
    "staleness_seconds",
    "freshness_sla_seconds",
    "oi_lag_seconds",
    "oi_lag_threshold_seconds",
    "is_risk_increase",
    "uncertainty_is_rising",
    "realized_daily_loss_fraction",
    "realized_weekly_loss_fraction",
    "consecutive_losses",
    "time_to_expiry_days",
    "margin_health_fraction",
    "min_quantity",
    "contract_multiplier",
    "risk_state",
)

# Frozen setup DDL columns.  ``family_id`` and gate/pattern detail remain in
# the producer payload/trace as required by AD.1; no frozen column is added.
_SETUP_COLUMNS: Tuple[str, ...] = (
    "setup_id", "timestamp", "symbol", "timeframe", "pattern_ids",
    "direction", "entry_price", "stop_loss", "take_profit", "risk_reward",
    "confidence", "quality", "validity", "snapshot_id", "parent_ids",
    "payload_hash", "regime", "utc_activity_window_id", "lineage",
    "authority", "authority_scope",
)


class BridgeError(RuntimeError):
    """Named fail-closed bridge refusal."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = str(reason)
        self.detail = str(detail)
        super().__init__(f"{self.reason}: {self.detail}" if self.detail else self.reason)


ContextSource = Callable[[str, str, str], Any]


def _iso_from_ms(ms: int) -> str:
    moment = _dt.datetime.fromtimestamp(int(ms) / 1000.0, _dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms) % 1000:03d}Z"


def _as_of_ms(as_of: str) -> int:
    try:
        return int(parse_utc_ms(str(as_of)).timestamp() * 1000)
    except (TypeError, ValueError) as exc:
        raise BridgeError("AS_OF_INVALID", str(exc)) from exc


def _finite_float(value: Any, name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise BridgeError("BRIDGE_INPUT_INVALID", f"{name} is not numeric") from exc
    if not math.isfinite(out):
        raise BridgeError("BRIDGE_INPUT_INVALID", f"{name} is non-finite")
    return out


def _arbitration_measurement(inputs: Mapping[str, Any], weights: Mapping[str, Any], key: str) -> Any:
    """D28 zero-weight UNAVAILABLE survives as a marker, never an imputation."""
    weight = _finite_float(_required(weights, key), "arbitration.weight." + key)
    value = inputs.get(key)
    if value is None or value == "UNAVAILABLE":
        if weight == 0:
            return "UNAVAILABLE"
        raise BridgeError("ARBITRATION_INPUT_UNAVAILABLE", key)
    return _finite_float(value, "arbitration." + key)


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise BridgeError("BRIDGE_CONTEXT_INCOMPLETE", key)
    return mapping[key]


def _flatten_context(raw: Any) -> Dict[str, Any]:
    """Flatten only named producer sections; never fill a missing value."""
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        raw = dataclasses.asdict(raw)
    if hasattr(raw, "to_dict") and not isinstance(raw, Mapping):
        raw = raw.to_dict()
    if not isinstance(raw, Mapping):
        raise BridgeError("ENGINE_CONTEXT_INVALID", type(raw).__name__)
    source = dict(raw)
    out: Dict[str, Any] = {}
    # The order makes a top-level explicit field authoritative over a nested
    # convenience section, while retaining every section for diagnostics.
    for section in ("engine_context", "context", "fabric", "setup", "forecast", "risk"):
        value = source.get(section)
        if isinstance(value, Mapping):
            # Keep the section itself for authorities that consume a complete
            # nested record (notably the Risk Kernel), while also exposing its
            # measured fields to the bridge's flat input contract.
            out.setdefault(section, value)
            for key, item in value.items():
                out.setdefault(str(key), item)
    for key, value in source.items():
        if key not in ("engine_context", "context", "fabric", "setup", "forecast", "risk"):
            out[str(key)] = value
    if "evidence_events" in source and "events" not in out:
        out["events"] = source["evidence_events"]
    if "evidence" in source and "events" not in out:
        out["events"] = source["evidence"]
    if "risk_input" in source and "risk" not in out:
        out["risk"] = source["risk_input"]
    # Preserve the source's named package aliases without interpreting them.
    if "parameter_package" in source and "package" not in out:
        out["package"] = source["parameter_package"]
    return out


def _event_list(value: Any) -> List[Any]:
    if isinstance(value, Mapping):
        flattened: List[Any] = []
        for key in sorted(value, key=str):
            item = value[key]
            if isinstance(item, (list, tuple)):
                flattened.extend(item)
            else:
                flattened.append(item)
        return flattened
    if isinstance(value, (list, tuple)):
        return list(value)
    raise BridgeError("BRIDGE_CONTEXT_INCOMPLETE", "events must be a sequence")


def _state_value(value: Any) -> str:
    if isinstance(value, LifecycleState):
        return value.value
    return str(getattr(value, "value", value))


def _sl14_state(value: Any, evidence_id: str) -> str:
    raw = _state_value(value)
    if raw in EVIDENCE_LIFECYCLE_STATES:
        return raw
    try:
        return lifecycle_of(raw.lower())
    except (KeyError, ValueError):
        raise BridgeError("EVIDENCE_LIFECYCLE_INVALID", evidence_id) from None


def _event_time_ms(value: Any, *, fallback: Optional[int] = None) -> Optional[int]:
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    try:
        return int(parse_utc_ms(text).timestamp() * 1000)
    except ValueError:
        return fallback


def _fabric_ref(event: Any, *, symbol: str, timeframe: str,
                as_of_ms: int) -> FabricEvidenceRef:
    """Adapt a complete event/ref, rejecting the reduced DDL row shape."""
    if isinstance(event, FabricEvidenceRef):
        if event.symbol != symbol or event.timeframe != timeframe:
            raise BridgeError("EVIDENCE_SCOPE_MISMATCH", event.evidence_id)
        return event
    if isinstance(event, EvidenceEvent):
        state = _sl14_state(event.fate_state, event.evidence_id)
        event_as_of = _event_time_ms(event.availability_time, fallback=None)
        if event_as_of is None:
            raise BridgeError("EVIDENCE_AVAILABILITY_UNAVAILABLE", event.evidence_id)
        lineage = tuple(event.lineage)
        if not lineage:
            raise BridgeError("EVIDENCE_LINEAGE_UNRESOLVED", event.evidence_id)
        if event.age is None:
            raise BridgeError("EVIDENCE_AGE_UNAVAILABLE", event.evidence_id)
        return FabricEvidenceRef(
            evidence_id=event.evidence_id, engine_id=event.engine_id,
            symbol=event.symbol, timeframe=event.timeframe, state=state,
            direction=int(event.direction), quality=float(event.quality),
            resolution_class=str(event.resolution_class), age_bars=float(event.age),
            as_of=event_as_of, snapshot_id=event.snapshot_id, lineage=lineage,
            parent_ids=tuple(event.feature_dependencies),
        )
    if not isinstance(event, Mapping):
        raise BridgeError("EVIDENCE_RECORD_INVALID", type(event).__name__)
    required = ("evidence_id", "engine_id", "direction", "quality",
                "resolution_class", "snapshot_id", "lineage", "state",
                "age")
    missing = [key for key in required if key not in event or event[key] in (None, "")]
    if missing:
        # A row returned directly from evidence_event is deliberately refused:
        # it has no direction/fate/complete lineage fields.
        raise BridgeError("PERSISTED_EVIDENCE_INCOMPLETE", ",".join(missing))
    ev_symbol = str(event.get("symbol") or symbol)
    ev_tf = str(event.get("timeframe") or timeframe)
    if (ev_symbol, ev_tf) != (symbol, timeframe):
        raise BridgeError("EVIDENCE_SCOPE_MISMATCH", str(event.get("evidence_id")))
    event_as_of = _event_time_ms(
        event.get("availability_time", event.get("as_of", event.get("event_time"))),
        fallback=None)
    if event_as_of is None:
        raise BridgeError("EVIDENCE_AVAILABILITY_UNAVAILABLE", str(event["evidence_id"]))
    lineage = event["lineage"]
    if isinstance(lineage, str):
        lineage = tuple(x for x in lineage.split(",") if x)
    else:
        lineage = tuple(lineage)
    if not lineage:
        raise BridgeError("EVIDENCE_LINEAGE_UNRESOLVED", str(event["evidence_id"]))
    return FabricEvidenceRef(
        evidence_id=str(event["evidence_id"]), engine_id=str(event["engine_id"]),
        symbol=symbol, timeframe=timeframe,
        state=_sl14_state(event["state"], str(event["evidence_id"])),
        direction=int(event["direction"]), quality=_finite_float(event["quality"], "quality"),
        resolution_class=str(event["resolution_class"]),
        age_bars=_finite_float(event.get("age", 0.0), "age_bars"),
        as_of=event_as_of, snapshot_id=str(event["snapshot_id"]), lineage=lineage,
        parent_ids=tuple(event.get("parent_ids", ())),
    )


def _normalise_bars(value: Any) -> List[Dict[str, float]]:
    if not isinstance(value, (list, tuple)):
        raise BridgeError("BRIDGE_CONTEXT_INCOMPLETE", "bars must be a sequence")
    out: List[Dict[str, float]] = []
    for index, bar in enumerate(value):
        if isinstance(bar, MarketObservation):
            row = {"o": float(bar.open), "h": float(bar.high),
                   "l": float(bar.low), "c": float(bar.close),
                   "v": float(bar.volume), "timestamp": bar.timestamp,
                   "status": bar.status}
        elif isinstance(bar, Mapping):
            def pick(*names: str) -> Any:
                for name in names:
                    if name in bar:
                        return bar[name]
                return None
            row = {"o": _finite_float(pick("o", "O", "open"), f"bars[{index}].open"),
                   "h": _finite_float(pick("h", "H", "high"), f"bars[{index}].high"),
                   "l": _finite_float(pick("l", "L", "low"), f"bars[{index}].low"),
                   "c": _finite_float(pick("c", "C", "close"), f"bars[{index}].close"),
                   "v": _finite_float(pick("v", "V", "volume"), f"bars[{index}].volume")}
            for key in ("timestamp", "ts", "as_of", "status"):
                if key in bar:
                    row[key] = bar[key]
        else:
            raise BridgeError("BRIDGE_BAR_INVALID", f"index={index}")
        if row["h"] < max(row["o"], row["c"]) or row["l"] > min(row["o"], row["c"]):
            raise BridgeError("BRIDGE_BAR_INVALID", f"OHLC bounds index={index}")
        if row["h"] < row["l"] or row["v"] < 0:
            raise BridgeError("BRIDGE_BAR_INVALID", f"OHLCV bounds index={index}")
        out.append(row)
    if not out:
        raise BridgeError("NO_MARKET_DATA", "the governed window is empty")
    return out


def _direction(value: Any) -> int:
    if isinstance(value, str):
        text = value.upper()
        if text in ("LONG", "BULLISH", "+1", "1"):
            return 1
        if text in ("SHORT", "BEARISH", "-1"):
            return -1
    try:
        value_i = int(value)
    except (TypeError, ValueError) as exc:
        raise BridgeError("BRIDGE_DIRECTION_INVALID", str(value)) from exc
    if value_i not in (-1, 1):
        raise BridgeError("BRIDGE_DIRECTION_INVALID", str(value))
    return value_i


def _component_map(value: Any, name: str) -> Dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise BridgeError("BRIDGE_CONTEXT_INCOMPLETE", name)
    return {str(key): _finite_float(item, f"{name}.{key}")
            for key, item in value.items()}


def _lineage(refs: Iterable[FabricEvidenceRef]) -> Tuple[str, ...]:
    values: List[str] = []
    for ref in refs:
        values.extend(str(value) for value in ref.lineage)
    return tuple(dict.fromkeys(values))


def _validate_e11_context(value: Any) -> None:
    """Require the governed E11 producer payload without executing E11 again.

    E11's IC inputs/history and trained ``W=(9,8)``, ``b=(9,)`` tensors are
    authority-owned.  A bridge that sees only a regime label would be able to
    make a plausible but untraceable plan, so the complete payload is a hard
    input requirement even though this consumer uses the already-produced
    ``regime_state``/quality fields downstream.
    """
    if not isinstance(value, Mapping):
        raise BridgeError("E11_CONTEXT_INCOMPLETE", "record is not a mapping")
    required = ("ic_inputs", "history_windows", "classifier_W", "classifier_b",
                "regime_state")
    missing = [key for key in required if key not in value or value[key] is None]
    if missing:
        raise BridgeError("E11_CONTEXT_INCOMPLETE", ",".join(missing))
    if not isinstance(value["ic_inputs"], Mapping) or not value["ic_inputs"]:
        raise BridgeError("E11_CONTEXT_INCOMPLETE", "ic_inputs")
    if not isinstance(value["history_windows"], Mapping):
        raise BridgeError("E11_CONTEXT_INCOMPLETE", "history_windows")
    weights = value["classifier_W"]
    bias = value["classifier_b"]
    if (not isinstance(weights, (list, tuple)) or len(weights) != 9
            or any(not isinstance(row, (list, tuple)) or len(row) != 8
                   for row in weights)):
        raise BridgeError("E11_CONTEXT_INVALID", "classifier_W shape (9,8)")
    if not isinstance(bias, (list, tuple)) or len(bias) != 9:
        raise BridgeError("E11_CONTEXT_INVALID", "classifier_b shape (9,)")
    for row in list(weights) + [bias]:
        for item in row:
            _finite_float(item, "e11_classifier")


def _pattern_entity(pattern_id: Any, supplied: Any = None) -> PatternEntity:
    if isinstance(supplied, PatternEntity):
        entity = supplied
    else:
        pid = str(pattern_id)
        row = next((item for item in CATALOGUE if item.pattern_id == pid), None)
        if row is None:
            raise BridgeError("PATTERN_NOT_ADMITTED", pid)
        entity = entity_for(row)
    try:
        assert_scoring_admissible(entity)
    except Exception as exc:
        raise BridgeError("PATTERN_NOT_ADMITTED", str(exc)) from exc
    return entity


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class PaperPlanBridge:
    """A deterministic PAPER-only provider for the frozen runtime seam."""

    def __init__(self, *, store: Any, environment: str = "PAPER",
                 context_source: Optional[ContextSource] = None,
                 context_preparer: Optional[ContextSource] = None,
                 max_bars: int = 300) -> None:
        self.store = store
        self.environment = str(environment)
        self.context_source = context_source
        self.context_preparer = context_preparer
        self.max_bars = int(max_bars)
        if self.max_bars <= 0:
            raise ValueError("max_bars must be positive")
        self.refusals: Dict[str, Dict[str, str]] = {}
        self.traces: Dict[str, Dict[str, Any]] = {}
        self.plans: Dict[str, Dict[str, Any]] = {}

    async def prepare(self, symbol: str, timeframe: str, as_of: str) -> None:
        """Outside-budget preparation, explicitly bound at composition time.

        Never call the plan builder here: preparation may publish/read
        evidence but cannot materialize a decision or consume a trade slot.
        """
        if self.context_preparer is not None:
            if self.environment != "PAPER":
                raise BridgeError("PAPER_ONLY_EXECUTION", self.environment)
            await _maybe_await(self.context_preparer(symbol, timeframe, as_of))

    async def __call__(self, symbol: str, timeframe: str, as_of: str
                       ) -> Optional[Mapping[str, Any]]:
        key = f"{symbol}:{timeframe}"
        try:
            if self.environment != "PAPER":
                raise BridgeError("PAPER_ONLY_EXECUTION", self.environment)
            if symbol not in CORE10_SYMBOLS or timeframe not in TIMEFRAMES_14:
                raise BridgeError("CELL_OUT_OF_UNIVERSE", key)
            source = await self._source_context(symbol, timeframe, as_of)
            if source is None:
                raise BridgeError(
                    "ENGINE_CONTEXT_UNAVAILABLE",
                    "no governed engine context or complete persisted evidence reader",
                )
            plan = await self._build(source, symbol=symbol, timeframe=timeframe,
                                     as_of=as_of)
            self.refusals.pop(key, None)
            self.plans[key] = dict(plan)
            return plan
        except BridgeError as exc:
            self.refusals[key] = {"reason": exc.reason, "detail": exc.detail}
            return None
        except Exception as exc:
            # A provider exception must not become a guessed plan.  Keep a
            # stable machine reason while retaining the type/detail for audit.
            self.refusals[key] = {
                "reason": "BRIDGE_FAIL_CLOSED",
                "detail": f"{type(exc).__name__}: {exc}",
            }
            return None

    async def _source_context(self, symbol: str, timeframe: str,
                              as_of: str) -> Optional[Mapping[str, Any]]:
        if self.context_source is not None:
            value = self.context_source(symbol, timeframe, as_of)
            return await _maybe_await(value)
        for name in ("get_bridge_context", "get_engine_context",
                     "read_bridge_context", "read_engine_context"):
            reader = getattr(self.store, name, None)
            if reader is None:
                continue
            return await _maybe_await(reader(symbol, timeframe, as_of))
        contexts = getattr(self.store, "bridge_contexts", None)
        if isinstance(contexts, Mapping):
            return contexts.get((symbol, timeframe)) or contexts.get(
                f"{symbol}:{timeframe}")
        return None

    async def _window(self, context: Mapping[str, Any], *, symbol: str,
                      timeframe: str, as_of: str) -> List[Dict[str, float]]:
        supplied = context.get("bars")
        if supplied is None:
            window_bars = context.get("window_bars", self.max_bars)
            try:
                window = await _maybe_await(
                    self.store.get_window(symbol, timeframe, as_of, int(window_bars)))
            except AttributeError as exc:
                raise BridgeError("NO_MARKET_DATA", "store has no PIT window reader") from exc
            supplied = window
        bars = _normalise_bars(supplied)
        for index, bar in enumerate(bars):
            timestamp = bar.get("timestamp", bar.get("as_of"))
            if timestamp is not None:
                stamp_ms = _event_time_ms(timestamp, fallback=None)
                if stamp_ms is not None and stamp_ms > _as_of_ms(as_of):
                    raise BridgeError("BRIDGE_PIT_VIOLATION", f"bar index={index}")
            if bar.get("status") not in (None, "CLOSED"):
                raise BridgeError("DATA_QUALITY_QX", f"bar index={index}")
        return bars

    async def _build(self, raw_context: Mapping[str, Any], *, symbol: str,
                     timeframe: str, as_of: str) -> Mapping[str, Any]:
        context = _flatten_context(raw_context)
        missing_context = [key for key in REQUIRED_CONTEXT_KEYS
                           if key not in context or context[key] is None]
        if missing_context:
            raise BridgeError("BRIDGE_CONTEXT_INCOMPLETE",
                              ",".join(missing_context))
        _validate_e11_context(context["e11_context"])
        # ``events`` is the only evidence path.  A reduced SQL row fails in
        # _fabric_ref rather than being silently upgraded to ACTIVE.
        events = _event_list(_required(context, "events"))
        as_of_ms = _as_of_ms(as_of)
        refs = [_fabric_ref(event, symbol=symbol, timeframe=timeframe,
                            as_of_ms=as_of_ms) for event in events]
        if not refs:
            raise BridgeError("FABRIC_NO_ACTIVE_EVIDENCE", "events is empty")
        data_trust = _finite_float(_required(context, "data_trust"), "data_trust")
        q_raw = _finite_float(_required(context, "q_raw"), "q_raw")
        bars = await self._window(context, symbol=symbol, timeframe=timeframe,
                                  as_of=as_of)
        direction = _direction(_required(context, "direction"))
        package = _required(context, "package")
        if not isinstance(package, Mapping) or not package:
            raise BridgeError("PARAMETER_PACKAGE_INVALID", "package")
        package = dict(package)
        for key in ("package_version", "parameter_package_id"):
            if not package.get(key):
                raise BridgeError("PARAMETER_PACKAGE_INVALID", key)

        # SL-14 admission and conflict policy are both frozen authorities; the
        # bridge only supplies their measured inputs.
        raw_ids = context.get("raw_observation_ids")
        fabric0 = EvidenceFabric.assemble(
            symbol=symbol, timeframe=timeframe, as_of=as_of_ms, evidence=refs,
            data_trust=data_trust, raw_observation_ids=raw_ids)
        if fabric0.is_empty():
            raise BridgeError("FABRIC_NO_ACTIVE_EVIDENCE",
                              str(fabric0.excluded))
        ages = [float(member.age_bars) for member in fabric0.members]
        disagreement = disagreement_of(fabric0.members)
        quality_asymmetry = quality_asymmetry_of(
            [float(member.quality) for member in fabric0.members])
        stale_fraction = stale_fraction_of(
            ages, expiry_age_bars(timeframe))
        package_id = str(package["parameter_package_id"])
        conflict = resolve(
            disagreement=disagreement, data_trust=data_trust, q_raw=q_raw,
            timeframe=timeframe,
            mtf_conflict=str(_required(context, "mtf_state")),
            hard_flags=tuple(context.get("hard_flags", ())),
            uncertainty=_finite_float(context.get("uncertainty", 0.0), "uncertainty"),
            stale_fraction=stale_fraction, redundancy=_finite_float(
                context.get("redundancy", 0.0), "redundancy"),
            quality_asymmetry=quality_asymmetry,
            redundancy_rho=(None if context.get("redundancy_rho") is None else
                            _finite_float(context["redundancy_rho"], "redundancy_rho")),
            regime_state=str(_required(context, "regime_state")),
            conflict_id=str(context.get("conflict_id", "bridge-conflict")),
            package_id=package_id, snapshot_id=fabric0.hash,
            lineage=_lineage(fabric0.members),
        )
        fabric = EvidenceFabric.assemble(
            symbol=symbol, timeframe=timeframe, as_of=as_of_ms,
            evidence=list(fabric0.members), data_trust=data_trust,
            conflict_state=str(conflict["output"]),
            redundancy_state=dict(fabric0.redundancy_state),
            raw_observation_ids=raw_ids)

        # Context confidence is recomputed from the fabric.  A supplied
        # context_confidence is intentionally ignored; confidence is produced,
        # never injected.
        ctx = build_context(
            fabric,
            market_regime=str(_required(context, "market_regime")),
            mtf_state=str(_required(context, "mtf_state")),
            utc_window_state=str(_required(context, "utc_window_state")),
            is_overlap=bool(_required(context, "is_overlap")),
            volatility_state=str(_required(context, "volatility_state")),
            structure_state=str(_required(context, "structure_state")),
            regime_confidence=_finite_float(
                _required(context, "regime_confidence"), "regime_confidence"),
            regime_uncertainty=_finite_float(
                _required(context, "regime_uncertainty"), "regime_uncertainty"),
            divergence_magnitude=_finite_float(
                _required(context, "divergence_magnitude"), "divergence_magnitude"),
            temporal_window_validity=_finite_float(
                _required(context, "temporal_window_validity"),
                "temporal_window_validity"),
            q_raw=q_raw,
            correlation_state=dict(context.get("correlation_state", {})),
            divergence_state=dict(context.get("divergence_state", {})),
            liquidity_state=dict(context.get("liquidity_state", {})),
            portfolio_context=dict(context.get("portfolio_context", {})),
        )
        context_confidence = float(ctx["context_confidence"])
        if not ctx["solvency"]["ok"]:
            raise BridgeError("CONTEXT_SOLVENCY_FAILED", str(ctx["solvency"]))

        entity = _pattern_entity(
            _required(context, "pattern_id"), context.get("pattern_entity"))
        pattern_hit = context.get("pattern_hit")
        if isinstance(pattern_hit, Mapping):
            hit_direction = pattern_hit.get("direction")
            if hit_direction is not None and _direction(hit_direction) != direction:
                raise BridgeError("PATTERN_DIRECTION_MISMATCH", str(hit_direction))
        elif context.get("pattern_detected") is False:
            raise BridgeError("PATTERN_NOT_DETECTED", str(entity.pattern_id))

        # The bootstrap forecast is lawful in PAPER, but its full feature
        # vector and quality inputs still have to come from the producer.
        x = _component_map(_required(context, "x"), "x")
        forecast_uncertainty = context.get("forecast_uncertainty", {})
        if not isinstance(forecast_uncertainty, Mapping):
            raise BridgeError("BRIDGE_CONTEXT_INVALID", "forecast_uncertainty")
        forecast_event = ForecastEvent(
            target_condition=str(context.get(
                "target_condition", f"{PLAYBOOK_ID}:TARGET_3R")),
            stop_condition=str(context.get(
                "stop_condition", f"{ENTRY_LOGIC_REF}:SWEEP_LOW_INVALIDATION")),
            horizon=HORIZON_BARS, entry_ref=ENTRY_LOGIC_REF,
            symbol=symbol, timeframe=timeframe, timestamp=as_of_ms)
        forecast = build_forecast(
            forecast_event, x=x,
            p_hat=context.get("p_hat"),
            uncertainty=forecast_uncertainty,
            q_forecast=context.get("q_forecast"),
            rr=_finite_float(_required(context, "forecast_rr"), "forecast_rr"),
            cost_r=_finite_float(_required(context, "forecast_cost_r"), "forecast_cost_r"),
            risk_state=str(_required(context, "risk_state")),
            spread_available=bool(context.get("spread_available", True)),
            package=context.get("forecast_package"), environment=self.environment,
            age_bars=_finite_float(context.get("forecast_age_bars", 0.0),
                                   "forecast_age_bars"))

        # Pattern/setup family and the thirteen gates.  Inputs such as ATR,
        # E01 BOS and E05 zones are consumed from the engine context; the
        # bridge never recomputes them from OHLCV.
        evaluation = evaluate_cell(
            symbol=symbol, timeframe=timeframe, as_of=as_of_ms, fabric=fabric,
            bars=bars, atr=_finite_float(_required(context, "atr"), "atr"),
            direction=direction,
            fvg_zones=_required(context, "fvg_zones"),
            bos=_required(context, "bos"),
            regime_state=str(_required(context, "regime_state")),
            mtf_state=str(_required(context, "mtf_state")),
            available_closes=context.get("available_closes"),
            window_qualities=_required(context, "window_qualities"),
            temporal_quality=_required(context, "temporal_quality"),
            volatility_quality=_required(context, "volatility_quality"),
            forecast={"quality": _required(context, "forecast_quality"),
                      "h_norm": _finite_float(_required(context, "h_norm"), "h_norm")},
            q_forecast=forecast.q_forecast,
            package=package,
            payload=context.get("setup_payload"),
            lineage=_lineage(fabric.members),
            context_confidence=context_confidence,
            component_series=context.get("component_series"),
            s_i=_component_map(_required(context, "s_i"), "s_i"),
            q_i=_component_map(_required(context, "q_i"), "q_i"),
            environment=self.environment)
        if evaluation.status != EMITTED or not evaluation.gate_block.get("all_pass"):
            raise BridgeError("SETUP_NOT_EMITTED", evaluation.reason)

        # The instantiated playbook owns stop/target construction.  The
        # numeric FVG boundary is an engine-owned context value, not a value
        # inferred from a zone label.
        sweep = evaluation.entry_logic_steps.get("2_3_sweep_reclaim", {})
        sweep_extreme = _finite_float(_required(sweep, "extreme"), "sweep_extreme")
        zones = list(_required(context, "fvg_zones"))
        recent_zone = next((z for z in reversed(zones)
                            if not bool(z.get("filled", False))), None)
        if not isinstance(recent_zone, Mapping):
            raise BridgeError("NO_UNFILLED_FVG", "the family already passed but no zone is numeric")
        fvg_low = recent_zone.get("low", recent_zone.get("lo"))
        fvg_high = recent_zone.get("high", recent_zone.get("hi"))
        if (direction > 0 and fvg_low is None) or (direction < 0 and fvg_high is None):
            raise BridgeError("FVG_PRICE_CONTEXT_UNAVAILABLE", "low/high")
        playbook = instantiate_playbook(
            lifecycle="VALIDATING",
            regime_window=tuple(context.get("regime_window", (str(_required(context, "regime_state")),))))
        stops = build_stops(
            direction=direction, entry=float(evaluation.entry),
            atr=_finite_float(_required(context, "atr"), "atr"),
            sweep_extreme=sweep_extreme,
            fvg_low=None if fvg_low is None else _finite_float(fvg_low, "fvg_low"),
            fvg_high=None if fvg_high is None else _finite_float(fvg_high, "fvg_high"))

        # Eligibility is the frozen eight-condition conjunction.  Gate 10 is
        # also projected here; the decision layer does not replace gates.
        gate_results = evaluation.gate_block["results"]
        gate10_ok = bool(gate_results[10]["passed"])
        elig = eligibility({
            "setup_valid": True, "forecast_quality_ok": gate10_ok,
            "conflict_state": fabric.conflict_state, "q_raw": q_raw,
            "timeframe": timeframe, "freshness_ok": bool(_required(context, "freshness_ok")),
            "data_trust": data_trust, "p": forecast.p_hat,
            "p_min_tf": _finite_float(_required(context, "p_min_tf"), "p_min_tf"),
            "c": forecast.c,
            "c_min": _finite_float(_required(context, "c_min"), "c_min"),
        })
        if not elig["eligible"]:
            raise BridgeError("DECISION_INELIGIBLE", ",".join(elig["failed"]))

        setup_id = evaluation.to_setup_event()["setup_id"]
        setup_for_decision = {
            "setup_id": setup_id, "entry": evaluation.entry,
            "stop": stops["stop"], "target": stops["target"],
            "P": forecast.p_hat, "C": forecast.c, "U_sum": forecast.u,
            "cost_unit": forecast.cost_r, "r_penalty": forecast.r_penalty,
            "is_risk_increase": bool(_required(context, "is_risk_increase")),
            "uncertainty_is_rising": bool(_required(context, "uncertainty_is_rising")),
        }
        candidates = generate_candidates([setup_for_decision])
        ranked = rank(candidates)
        selected = select(candidates, environment=self.environment)
        intended = "LONG" if direction > 0 else "SHORT"
        # Candidate generation deliberately evaluates both sides; the family
        # direction is the engine-produced side the arbitration may select.
        candidate = next((row for row in ranked if row["side"] == intended), None)
        if candidate is None:
            raise BridgeError("DECISION_NO_CANDIDATE", intended)
        arb_input = dict(context.get("arbitration", {}))
        if not isinstance(arb_input, Mapping):
            raise BridgeError("BRIDGE_CONTEXT_INVALID", "arbitration")
        weights = arb_input.get("composite_weights")
        if not isinstance(weights, Mapping):
            raise BridgeError("ARBITRATION_CONTEXT_UNAVAILABLE", "composite_weights")
        arb_candidate = {
            "playbook_id": PLAYBOOK_ID, "family_id": FAMILY_ID,
            "direction": intended,
            "regime_window": tuple(arb_input.get(
                "regime_window", playbook.regime_window)),
            "composite_weights": dict(weights),
            "quality": _finite_float(arb_input.get("quality", evaluation.final_score),
                                     "arbitration.quality"),
            "alignment": _arbitration_measurement(arb_input, weights, "alignment"),
            "recency": _arbitration_measurement(arb_input, weights, "recency"),
        }
        family_status = str(_required(context, "family_status"))
        arb = arbitrate([arb_candidate],
                        regime=str(_required(context, "regime_state")),
                        family_statuses={FAMILY_ID: family_status})
        if arb["proposal"] is None or arb["reason"].get("decision") != "TRADE":
            raise BridgeError("DECISION_NO_TRADE", str(arb["reason"]))
        proposal = build_proposal(
            setup_id=setup_id, direction=intended,
            entry_logic_ref=ENTRY_LOGIC_REF, stop=stops["stop"],
            targets=(stops["target"],), p_hat=forecast.p_hat, u=forecast.u,
            c=forecast.c, conflict_state=fabric.conflict_state,
            snapshot_id=evaluation.fabric_hash, r_penalty=forecast.r_penalty,
            cost_unit=forecast.cost_r, entry=evaluation.entry,
            arbitration_reason=arb["reason"])

        risk = dict(_required(context, "risk"))
        missing_risk = [key for key in REQUIRED_RISK_KEYS if key not in risk]
        if missing_risk:
            raise BridgeError("RISK_CONTEXT_INCOMPLETE", ",".join(missing_risk))
        risk.update({
            "snapshot_id": evaluation.fabric_hash,
            "timeframe": timeframe,
            "q_raw": q_raw,
            "failed_setup_gate": False,
            "pit_violation": any(ref.as_of > as_of_ms for ref in refs),
            "conflict_state": fabric.conflict_state,
            "stop_distance": stops["R"],
            "package": package,
            "risk_state": str(risk["risk_state"]),
        })
        risk_result = adjudicate(risk)
        plan = build_trade_plan(
            proposal=proposal, adjudication=risk_result,
            symbol=symbol, timeframe=timeframe, environment=self.environment,
            as_of=as_of, capital=_finite_float(risk["capital"], "capital"),
            contract_multiplier=_finite_float(risk["contract_multiplier"],
                                              "contract_multiplier"),
            risk_state=risk_result.get("sizing", {}).get(
                "risk_state", risk.get("risk_state")),
            package_version=str(package.get("package_version")),
            created_utc=as_of,
            lineage=str(context.get(
                "plan_lineage", f"setup:{setup_id}|fabric:{evaluation.fabric_hash}")),
        )
        await self._materialize_setup(evaluation.to_setup_event(),
                                       pattern_id=entity.pattern_id,
                                       regime=str(context.get("regime_state", "")))

        trace = {
            "fabric": fabric.to_dict(), "conflict": conflict,
            "context": ctx, "pattern_id": entity.pattern_id,
            "forecast": forecast.to_dict(), "evaluation": evaluation,
            "playbook": playbook.to_dict(), "stops": stops,
            "eligibility": elig, "ranked": ranked, "selected": selected,
            "arbitration": arb, "risk": risk_result, "plan": plan.to_dict(),
        }
        self.traces[f"{symbol}:{timeframe}"] = trace
        return plan.to_dict()

    async def _materialize_setup(self, event: Mapping[str, Any], *,
                                 pattern_id: str, regime: str) -> None:
        """Materialize only the frozen 21 setup columns before FSM admission."""
        inserter = getattr(self.store, "insert_setup_event", None)
        if inserter is not None:
            await _maybe_await(inserter(dict(event)))
            return
        db = getattr(self.store, "db", None)
        if db is None:
            raise BridgeError("SETUP_MATERIALIZATION_UNAVAILABLE",
                              "store exposes neither insert_setup_event nor db")
        values = []
        for column in _SETUP_COLUMNS:
            value = event.get(column)
            if column == "timestamp" and isinstance(value, (int, float)):
                value = _iso_from_ms(int(value))
            if column == "pattern_ids" and not value:
                value = pattern_id
            if column == "regime" and value in (None, ""):
                value = regime
            values.append(value)
        try:
            await db.execute(
                "INSERT OR IGNORE INTO setup_candidate (" + ",".join(_SETUP_COLUMNS)
                + ") VALUES (" + ",".join("?" for _ in _SETUP_COLUMNS) + ")",
                tuple(values))
            await db.commit()
        except Exception as exc:
            raise BridgeError("SETUP_MATERIALIZATION_FAILED", str(exc)) from exc


async def build_paper_plan(*, store: Any, context: Mapping[str, Any],
                           symbol: str, timeframe: str, as_of: str,
                           environment: str = "PAPER") -> Mapping[str, Any]:
    """Convenience one-shot surface used by tests and composition roots."""
    bridge = PaperPlanBridge(store=store, environment=environment,
                             context_source=lambda _s, _t, _a: context)
    result = await bridge(symbol, timeframe, as_of)
    if result is None:
        refusal = bridge.refusals.get(f"{symbol}:{timeframe}",
                                      {"reason": "BRIDGE_FAIL_CLOSED", "detail": ""})
        raise BridgeError(refusal["reason"], refusal["detail"])
    return result


__all__ = [
    "CONTRACT_VERSION", "BridgeError", "PaperPlanBridge",
    "REQUIRED_CONTEXT_KEYS", "REQUIRED_RISK_KEYS", "build_paper_plan",
]
