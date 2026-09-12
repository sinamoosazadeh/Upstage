"""APEX_GEN5 ENGINE BASE CONTRACT — FROZEN (CP-1).

Engine stages (CP-2..CP-5) CONSUME this contract, never edit it; a needed
change is a G13 issue in PHASE2_DECISION_LOG, not a commit (PHASE2_
CHECKPOINTS.md cross-stage invariants).

Frozen surface implemented here:
- Versioned interfaces: contract_version v4.0.0 (AI.12 Phase 1: no engine
  may carry another contract_version); analyst_version = SemVer + git40;
  INTERFACE_VERSION constant.
- Lifecycle: AI.4 derived-object state machine CANDIDATE → CONFIRMED →
  ACTIVE → {MITIGATED, INVALIDATED, EXPIRED, SUPERSEDED}; only forward or
  terminal transitions; terminal states never revert.
- Streaming + idempotency: engines run on per-candle windows streamed from
  the catalog; every run computes the AI.3 replay_key and returns the
  cached result (TTL 60–300 s) on identical inputs+code; cached results
  are discarded on code_revision change.
- Emission → 24-field validation: every EvidenceEvent passes
  validate_24_fields() before bus publication; engine_id ∈ E01..E12;
  resolution_class Q0..QX; direction ∈ {-1,0,1}.
- Wave-Out plumbing: WaveOutError is the only lawful handling of any
  Wave-Out item; the Wave-Out list lives in apex.errors.
- Catalog-only data access: engines read features exclusively via
  catalog.get() (self.feature()); direct get_ohlcv outside
  apex/data_catalog is a build-breaking lint rule (Ch.5).
- Per-engine EPS: eps_for_engine() from the frozen §2.2 table.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from apex.config import load_params
from apex.data_catalog.catalog import Catalog, catalog
from apex.data_catalog.contracts import (
    CatalogResult,
    EvidenceEvent,
    LifecycleState,
)
from apex.errors import WaveOutError, wave_out
from apex.identity.hashes import replay_key
from apex.quality.numerical import eps_for_engine

# Versioned interface (frozen)
CONTRACT_VERSION = "v4.0.0"
INTERFACE_VERSION = "v4.0.0"

ENGINE_IDS = tuple(f"E{i:02d}" for i in range(1, 13))

# Replay-cache TTL bounds (AI.3: typically 60–300 s)
REPLAY_TTL_MIN_SECONDS = 60.0
REPLAY_TTL_MAX_SECONDS = 300.0


@dataclass(frozen=True)
class ReplayEntry:
    result: Any
    expires_at: float
    code_revision: str


class EngineStateError(RuntimeError):
    """Illegal lifecycle transition (T-MON-002: never backward)."""


class EngineBase(abc.ABC):
    """Frozen engine base. Concrete engines (CP-2..CP-5) subclass this and
    implement `compute()`; they never reimplement lifecycle, replay
    idempotency, emission validation, or data access."""

    # subclasses override:
    engine_id: str = ""                 # E01..E12
    analyst_version: str = "0.0.0+" + "0" * 40  # SemVer + git40 (CP-2 sets real)
    code_revision: str = "0" * 40

    def __init__(self, catalog_: Optional[Catalog] = None,
                 bus: Any = None, params: Any = None) -> None:
        if self.engine_id not in ENGINE_IDS:
            raise ValueError(
                f"engine_id {self.engine_id!r} not in E01..E12 "
                f"(AI.12: no other engine ids exist)"
            )
        self._catalog = catalog_ if catalog_ is not None else catalog
        self._bus = bus
        self._params = params if params is not None else load_params()
        self._state: LifecycleState = LifecycleState.CANDIDATE
        self._replay_cache: Dict[str, ReplayEntry] = {}
        self._runs: int = 0
        self._eps_tick_size: Any = None
        self._eps_closes_20: Optional[List[Any]] = None

    # -- identity -----------------------------------------------------------
    @property
    def contract_version(self) -> str:
        return CONTRACT_VERSION

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def eps(self) -> Any:
        """Frozen §2.2 per-engine EPS (E01 scaled variant needs tick_size/
        median inputs — callers pass them via set_eps_inputs)."""
        if self.engine_id == "E01":
            tick = self._eps_tick_size
            closes = self._eps_closes_20
            if tick is None or closes is None:
                raise ValueError(
                    "E01 scaled EPS requires tick_size/median_20(close) "
                    "inputs (set_eps_inputs) — MISSING_EPS_INPUTS_QX")
            return eps_for_engine(self.engine_id, tick, closes)
        return eps_for_engine(self.engine_id)

    def set_eps_inputs(self, tick_size: Any = None,
                       closes_20: Optional[List[Any]] = None) -> None:
        self._eps_tick_size = tick_size
        self._eps_closes_20 = closes_20

    # -- lifecycle (AI.4; T-MON-002) ----------------------------------------
    _FORWARD: Dict[LifecycleState, Tuple[LifecycleState, ...]] = {
        LifecycleState.CANDIDATE: (LifecycleState.CONFIRMED,),
        LifecycleState.CONFIRMED: (LifecycleState.ACTIVE,),
        LifecycleState.ACTIVE: (LifecycleState.MITIGATED,
                                LifecycleState.INVALIDATED,
                                LifecycleState.EXPIRED,
                                LifecycleState.SUPERSEDED),
        LifecycleState.MITIGATED: (LifecycleState.INVALIDATED,
                                   LifecycleState.EXPIRED,
                                   LifecycleState.SUPERSEDED),
        LifecycleState.INVALIDATED: (),
        LifecycleState.EXPIRED: (),
        LifecycleState.SUPERSEDED: (),
    }

    def advance_state(self, new_state: LifecycleState) -> None:
        """Only forward or terminal transitions; terminal never reverts;
        anything else raises EngineStateError (fail-closed)."""
        if new_state in self._FORWARD.get(self._state, ()):
            self._state = new_state
            return
        raise EngineStateError(
            f"illegal lifecycle transition {self._state.value} → "
            f"{new_state.value} for {self.engine_id} (T-MON-002)"
        )

    def confirm(self) -> None:
        self.advance_state(LifecycleState.CONFIRMED)

    def activate(self) -> None:
        self.advance_state(LifecycleState.ACTIVE)

    # -- catalog-only data access (Ch.5) ------------------------------------
    async def feature(self, feature_id: str, symbol: str, timeframe: str,
                      as_of: str, lookback: int = 1,
                      context: Optional[Dict[str, Any]] = None) -> CatalogResult:
        """The ONLY data path: catalog.get(). Engines never SQL the
        store and never call get_ohlcv (build-breaking lint rule)."""
        result = self._catalog.get(feature_id, symbol, timeframe, as_of,
                                   lookback=lookback, context=context)
        import inspect
        if inspect.isawaitable(result):
            result = await result
        return result

    # -- streaming + idempotency (AI.3 replay_key; T-PIT-003/T-AD-002) ------
    def build_replay_key(self, symbol: str, timeframe: str, as_of: str,
                         input_hash: str, parameter_package_id: str,
                         canonical_payload: str) -> str:
        return replay_key(
            engine_version=self.analyst_version,
            contract_version=CONTRACT_VERSION,
            symbol=symbol, timeframe=timeframe, as_of_timestamp=as_of,
            input_hash=input_hash, parameter_package_id=parameter_package_id,
            code_revision=self.code_revision,
            canonical_payload=canonical_payload,
        )

    def replay_lookup(self, key: str) -> Optional[Any]:
        """Return the cached result within TTL, else None. Cached results
        are discarded on code_revision change (AI.12)."""
        entry = self._replay_cache.get(key)
        if entry is None:
            return None
        if entry.code_revision != self.code_revision:
            self._replay_cache.pop(key, None)
            return None
        if entry.expires_at < time.time():
            self._replay_cache.pop(key, None)
            return None
        return entry.result

    def replay_store(self, key: str, result: Any,
                     ttl_seconds: float = REPLAY_TTL_MAX_SECONDS) -> None:
        ttl_seconds = max(REPLAY_TTL_MIN_SECONDS,
                          min(REPLAY_TTL_MAX_SECONDS, ttl_seconds))
        self._replay_cache[key] = ReplayEntry(
            result=result, expires_at=time.time() + ttl_seconds,
            code_revision=self.code_revision)

    # -- emission (24-field contract) ----------------------------------------
    async def emit(self, event: EvidenceEvent, bus: Any = None,
                   priority: int = 2) -> None:
        """Validate the frozen 24-field contract, then publish on the bus
        (P2 routine by default; P1/P0 for risk/emergency). Validation
        failure raises — an engine never emits an invalid evidence event."""
        event.validate_24_fields()
        if event.engine_id != self.engine_id:
            raise ValueError(
                f"emission engine_id {event.engine_id!r} != producer "
                f"{self.engine_id} (AI.11: no cross-engine mutation)")
        target_bus = bus if bus is not None else self._bus
        if target_bus is not None:
            from apex.bus import make_event
            await target_bus.publish(make_event(
                priority, f"evidence.{self.engine_id}.{event.condition_state}",
                event))

    def wave_out(self, feature: str, reason: str = "OUT_OF_CONTRACT",
                 ) -> "WaveOutError":
        """Wave-Out plumbing: constructing the raise is the only lawful
        handling of any Wave-Out item (§9.5-9/G6)."""
        return wave_out(feature, reason)

    # -- abstract compute hook ------------------------------------------------
    @abc.abstractmethod
    def compute(self, symbol: str, timeframe: str, as_of: str,
                context: Optional[Dict[str, Any]] = None) -> List[EvidenceEvent]:
        """Engine-specific computation on the frozen interface (CP-2+).
        Implementations read via self.feature() only and return validated
        EvidenceEvents. Missing/insufficient inputs → empty list or QX
        evidence per the engine chapter — never fabricated emissions."""
        raise NotImplementedError  # abstract — concrete engines implement
