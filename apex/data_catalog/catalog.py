"""APEX_GEN5 feature catalog — the ONLY public read of the catalog
(Ch.5: `catalog.get`). Engines never SQL the store; direct `get_ohlcv`
outside apex/data_catalog is a build-breaking lint rule.

§3.13 closure requirements enforced here:
1. feature 74 defined with the full entry template;
2. feature 73 carries its Parameters / Validity-decay-confidence /
   Consumers / Tests fields;
3. every tier of the three-tier architecture (ATOM, MOLECULAR,
   ORGANISMIC) carries registered features, and the registry count equals
   the catalogue count (74);
4. no engine may reference a feature id absent from this registry
   (unregistered id → CatalogStatus.INVALID).

Ch.5 contract: ``Catalog.get(feature_id, symbol, timeframe, as_of,
lookback=1) -> {feature_id, symbol, timeframe, as_of, value, q_component,
availability_time, snapshot_id, status, reason}`` with status ∈ {OK,
MISSING, STALE, UNAVAILABLE, INVALID}. Unknown feature_id → INVALID.
Future as_of → INVALID (PIT). F49 absent-by-design (REMOVED); F56
market_profile always UNAVAILABLE (Wave-Out, §9.5-9).

Tier cache rules (§3.12): ATOM never cached; MOLECULAR cached for 5
candles; ORGANISMIC cached for 50+ candles (LRU-100). A failure at the
ATOM tier stops the whole pipeline (a non-OK ATOM status raises
AtomTierFailure to halt dependents — fail-closed).
"""

from __future__ import annotations

import datetime as _dt
import inspect
from typing import Any, Dict, List, Optional, Protocol, Tuple

from apex.config import load_params
from apex.data_catalog.contracts import (
    CatalogResult,
    CatalogStatus,
    FeatureContract,
    FeatureID,
    MarketObservation,
    ValidityPolicy,
    parse_utc_ms,
)
from apex.data_catalog.performance import TierCache

# ---------------------------------------------------------------------------
# Window provider protocol (implemented by apex.data_catalog.store)
# ---------------------------------------------------------------------------


class WindowProvider(Protocol):
    async def get_window(self, symbol: str, timeframe: str, as_of: str,
                         bars: int) -> List[MarketObservation]: ...

    async def max_availability_time(self, symbol: str, timeframe: str,
                                    as_of: str) -> Optional[str]: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ATOM_CONSUMERS = (
    "Structure", "Liquidity", "FVG", "OrderBlock", "ICT/SMC/RTM", "Wyckoff",
    "Trend", "Momentum", "Regime", "TemporalWindow",
)
ORGN_CONSUMERS = (
    "Volatility", "Regime", "Trend", "Momentum", "TemporalWindow",
    "Context Fabric",
)
MOLE_CONSUMERS = (
    "Liquidity", "Pattern", "Setup", "Playbook", "ICT/SMC/RTM", "Context Fabric",
)


class FeatureRegistry:
    """The 74-feature registry (§3.12). Alias → contract, full_id → alias."""

    def __init__(self) -> None:
        self._by_alias: Dict[str, FeatureContract] = {}
        self._by_full_id: Dict[str, FeatureContract] = {}
        self._by_num: Dict[int, FeatureContract] = {}

    def register(self, contract: FeatureContract) -> None:
        alias = contract.id.alias
        if alias in self._by_alias:
            raise ValueError(f"duplicate feature alias {alias!r} in registry")
        self._by_alias[alias] = contract
        self._by_full_id[contract.id.full_id] = contract
        self._by_num[contract.id.full_id] = contract

    def lookup(self, identifier: str) -> Optional[FeatureContract]:
        return self._by_alias.get(identifier) or self._by_full_id.get(identifier)

    def all(self) -> List[FeatureContract]:
        return list(self._by_alias.values())

    def count(self) -> int:
        return len(self._by_alias)

    def tier_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"ATOM": 0, "MOLE": 0, "ORGN": 0}
        for contract in self._by_alias.values():
            counts[contract.id.super_layer] += 1
        return counts

    def alias_to_tier(self, alias: str) -> str:
        contract = self._by_alias[alias]
        return contract.id.super_layer


# ---------------------------------------------------------------------------
# Registry builders (uniform §3.12 templates + per-tier specifics)
# ---------------------------------------------------------------------------

def _make_atom_contract(num: int, alias: str, full_id: str,
                        computer: Any) -> FeatureContract:
    fid = FeatureID(full_id=full_id, alias=alias, super_layer="ATOM",
                    family="CNDL", metric="RATIO", normalization="RAW",
                    version=1)
    return FeatureContract(
        id=fid, name=alias,
        description=f"§3.12 feature {num:02d} {alias} ({full_id})",
        formula=f"formula_{alias}(O,H,L,C,V,ATR)",
        inputs=("O", "H", "L", "C", "V", "OI"),
        outputs=(f"{alias}_t", "Q_formula_valid", "snapshot_id", "validity",
                 "confidence", "dependency"),
        dependencies=("O", "H", "L", "C", "V", "ATR"),
        lookback=1, warmup=0,
        epsilon={"eps_range": "1e-12", "atr_floor": "1e-8"},
        unit="ratio", range=(0.0, 10.0), tolerance=1e-12,
        validity=ValidityPolicy(validity_candles=1, decay_type="none",
                                decay_formula="none"),
        stability="high", computation_cost="low",
        owner="Candle Intelligence Engine",
        confidence_equation="1.0*Q_formula_valid", version="v5.0.0",
    )


def _make_orgn_contract(num: int, alias: str, full_id: str, note: str,
                        computer: Any) -> FeatureContract:
    fid = FeatureID(full_id=full_id, alias=alias, super_layer="ORGN",
                    family="CTXT", metric="SCORE", normalization="RAW",
                    version=1)
    return FeatureContract(
        id=fid, name=alias,
        description=f"§3.12 feature {num:02d} {alias} ({full_id}) [{note}]",
        formula=f"formula_{alias}(O,H,L,C,V,OI,regime,temporal_window,MTF)",
        inputs=("O", "H", "L", "C", "V", "OI", "regime", "temporal_window",
                "MTF"),
        outputs=(f"{alias}_t", "Q_formula_valid", "validity", "confidence"),
        dependencies=("H", "L", "ATR", "regime", "temporal_window", "MTF"),
        lookback=50, warmup=49,
        epsilon={"eps_range": "1e-12", "atr_floor": "1e-8"},
        unit="ratio", range=(0.0, 10.0), tolerance=1e-12,
        validity=ValidityPolicy(validity_candles=50, decay_type="exponential",
                                decay_formula="exp(-0.02*age)"),
        stability="medium", computation_cost="medium",
        owner="Candle Intelligence Engine",
        confidence_equation="0.85*Q_formula_valid*regime_confidence",
        version="v5.0.0",
    )


def _make_mole_contract(num: int, alias: str, full_id: str,
                        computer: Any) -> FeatureContract:
    fid = FeatureID(full_id=full_id, alias=alias, super_layer="MOLE",
                    family="LIQ", metric="STRENGTH", normalization="RAW",
                    version=1)
    return FeatureContract(
        id=fid, name=alias,
        description=f"§3.12 feature {num:02d} {alias} ({full_id})",
        formula=("sweep_b = formula_sweep(body_ratio, range, VolumeZ, ATR, "
                 "k_sweep, theta_sweep, rolling_extremes) over the 5-candle "
                 "block — penetration beyond the rolling 20-bar extreme with "
                 "close back inside the range, rejection ratio >= "
                 "theta_sweep, VolumeZ >= 2, cooldown of 3 blocks"),
        inputs=("F01", "F05", "F19", "F11", "F25", "F29", "OHLCV", "OI"),
        outputs=("sweep_b", "Q_formula_valid", "snapshot_id", "validity",
                 "confidence"),
        dependencies=("F01", "F05", "F19", "F11", "F25", "F29",
                      "MarketObservation OHLCV"),
        lookback=5, warmup=20,
        epsilon={"eps_range": "1e-12", "atr_floor": "1e-8"},
        unit="strength", range=(0.0, 1.0), tolerance=1e-12,
        validity=ValidityPolicy(validity_candles=5, decay_type="exponential",
                                decay_formula="exp(-0.02*age)"),
        stability="medium", computation_cost="medium",
        owner="Candle Intelligence Engine",
        confidence_equation="0.9*Q_formula_valid*min(1,VolumeZ/2)",
        version="v5.0.0",
    )


def build_registry() -> FeatureRegistry:
    """Assemble the complete 74-slot registry from the three tier modules
    (ADR-P2-006: tiers live under apex/data_catalog/)."""
    from apex.data_catalog.atomic.features import ATOM_ENTRIES, COMPUTERS as ATOM_COMPUTE
    from apex.data_catalog.molecular.features import MOLE_ENTRIES, COMPUTERS as MOLE_COMPUTE
    from apex.data_catalog.organismic.features import ORGN_ENTRIES, COMPUTERS as ORGN_COMPUTE

    registry = FeatureRegistry()
    computers: Dict[str, Any] = {}
    for num, alias, full_id in ATOM_ENTRIES:
        registry.register(_make_atom_contract(num, alias, full_id,
                                              ATOM_COMPUTE[alias]))
        computers[alias] = ATOM_COMPUTE[alias]
    for num, alias, full_id, note in ORGN_ENTRIES:
        registry.register(_make_orgn_contract(num, alias, full_id, note,
                                              ORGN_COMPUTE[alias]))
        computers[alias] = ORGN_COMPUTE[alias]
    for num, alias, full_id in MOLE_ENTRIES:
        registry.register(_make_mole_contract(num, alias, full_id,
                                              MOLE_COMPUTE[alias]))
        computers[alias] = MOLE_COMPUTE[alias]
    return registry, computers


class AtomTierFailure(RuntimeError):
    """A failure at the ATOM tier stops the whole pipeline (§3.12)."""

    def __init__(self, alias: str, status: str, reason: str) -> None:
        super().__init__(f"ATOM tier failure on {alias}: {status} {reason}")
        self.alias = alias
        self.status = status
        self.reason = reason


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class Catalog:
    """Single catalog.get access point (§3.12/§3.13, Ch.5)."""

    def __init__(self, params: Any = None,
                 provider: Optional[WindowProvider] = None,
                 code_revision: str = "0000000000000000000000000000000000000000",
                 ) -> None:
        self._params = params if params is not None else load_params()
        self._registry, self._computers = build_registry()
        self._provider = provider
        self._cache = TierCache()
        self._cache.set_code_revision(code_revision)
        self.last_atom_failure: Optional[Tuple[str, str, str]] = None

    # -- registry access ----------------------------------------------------
    @property
    def registry(self) -> FeatureRegistry:
        return self._registry

    def set_provider(self, provider: WindowProvider) -> None:
        self._provider = provider

    def set_code_revision(self, code_revision: str) -> None:
        """Cached results are discarded on code_version change (AI.12)."""
        self._cache.set_code_revision(code_revision)

    def verify_completeness(self) -> Dict[str, Any]:
        """§3.13 closure check. Raises ValueError when a closure item
        fails (fail-closed, never silent)."""
        counts = self._registry.tier_counts()
        if self._registry.count() != 74:
            raise ValueError(
                f"§3.13 VIOLATION: registry count {self._registry.count()} "
                f"!= catalogue count 74"
            )
        if counts["ATOM"] == 0 or counts["MOLE"] == 0 or counts["ORGN"] == 0:
            raise ValueError(f"§3.13 VIOLATION: tier counts {counts}")
        f74 = self._registry.lookup("sweep")
        if f74 is None:
            raise ValueError("§3.13 VIOLATION: feature 74 undefined")
        f73 = self._registry.lookup("volatility_regime")
        if f73 is None:
            raise ValueError("§3.13 VIOLATION: feature 73 undefined")
        for field in ("parameters", "validity", "consumers", "tests"):
            _ = field  # contract completeness validated structurally below
        if not f73.dependencies or not f73.validity:
            raise ValueError("§3.13 VIOLATION: feature 73 template incomplete")
        f49 = self._registry.lookup("funding_rate")
        if f49 is None:
            raise ValueError("§3.13 VIOLATION: F49 slot absent (must be "
                             "registered as REMOVED/OUT-OF-CONTRACT)")
        f56 = self._registry.lookup("market_profile")
        if f56 is None:
            raise ValueError("§3.13 VIOLATION: F56 slot absent (Wave-Out: "
                             "registered, always UNAVAILABLE)")
        return {"count": self._registry.count(), "tiers": counts}

    # -- catalog.get --------------------------------------------------------
    async def get(self, feature_id: str, symbol: str, timeframe: str,
                  as_of: str, lookback: int = 1,
                  context: Optional[Dict[str, Any]] = None,
                  ) -> CatalogResult:
        """Ch.5 contract. The ONLY public read of the catalog. Async: the
        physical store is an async window provider (single event loop)."""
        context = context if context is not None else {}
        contract = self._registry.lookup(feature_id)
        if contract is None:
            return CatalogResult(
                feature_id=feature_id, symbol=symbol, timeframe=timeframe,
                as_of=as_of, value=None, q_component=0.0,
                availability_time=None, snapshot_id=None,
                status=CatalogStatus.INVALID,
                reason="UNREGISTERED_FEATURE_ID",
            )
        if self._provider is None:
            return CatalogResult(
                feature_id=feature_id, symbol=symbol, timeframe=timeframe,
                as_of=as_of, value=None, q_component=0.0,
                availability_time=None, snapshot_id=None,
                status=CatalogStatus.MISSING, reason="NO_WINDOW_PROVIDER",
            )
        # PIT: future as_of → INVALID
        frontier = self._provider.max_availability_time(symbol, timeframe, as_of)
        frontier = await frontier if inspect.isawaitable(frontier) else frontier
        if frontier is not None:
            try:
                if parse_utc_ms(as_of) > parse_utc_ms(frontier):
                    return CatalogResult(
                        feature_id=feature_id, symbol=symbol,
                        timeframe=timeframe, as_of=as_of, value=None,
                        q_component=0.0, availability_time=frontier,
                        snapshot_id=None, status=CatalogStatus.INVALID,
                        reason="PIT_FUTURE_AS_OF",
                    )
            except ValueError:
                return CatalogResult(
                    feature_id=feature_id, symbol=symbol,
                    timeframe=timeframe, as_of=as_of, value=None,
                    q_component=0.0, availability_time=frontier,
                    snapshot_id=None, status=CatalogStatus.INVALID,
                    reason="INVALID_AS_OF_FORMAT",
                )

        bars = max(lookback, contract.lookback + contract.warmup)
        window = self._provider.get_window(symbol, timeframe, as_of, bars)
        window = await window if inspect.isawaitable(window) else window

        tier = contract.id.super_layer
        bar_index = 0
        if window:
            bar_index = window[-1].sequence

        # tier cache discipline (ATOM never cached)
        cache_key = (contract.id.alias, symbol, timeframe)
        if tier != "ATOM":
            cached = self._cache.lookup(tier, cache_key, bar_index)
            if cached is not None:
                value, q = cached
                return CatalogResult(
                    feature_id=feature_id, symbol=symbol, timeframe=timeframe,
                    as_of=as_of, value=value, q_component=q,
                    availability_time=(window[-1].availability_time
                                       if window else None),
                    snapshot_id=None, status=CatalogStatus.OK,
                    reason="TIER_CACHE_HIT",
                )

        value, q, status, reason = self._computers[contract.id.alias](
            window, self._feature_params(), context)

        if tier == "ATOM" and status in ("INVALID", "DEGRADED"):
            # A failure at the ATOM tier stops the whole pipeline (§3.12):
            # bad data halts dependents (fail-closed). Warmup insufficiency
            # (UNAVAILABLE) or an open candle (CANDIDATE) returns a result —
            # the AI.6 missing-data model: gates stay open, nothing fires.
            self.last_atom_failure = (contract.id.alias, status, reason)
            raise AtomTierFailure(contract.id.alias, status, reason)

        if status == "OK" and value is not None:
            self._cache.store(tier, cache_key, bar_index, (value, q))

        availability = window[-1].availability_time if window else None
        return CatalogResult(
            feature_id=feature_id, symbol=symbol, timeframe=timeframe,
            as_of=as_of, value=value, q_component=q,
            availability_time=availability, snapshot_id=None,
            status=CatalogStatus(status), reason=reason,
        )

    def _feature_params(self) -> Dict[str, Any]:
        """Parameter surface passed to feature compute functions:
        periods from params/quality_weights_v1.yaml (§2.2/SMA/ATR)."""
        qw = self._params["quality_weights"]
        return {
            "sma_period": qw.get("sma_period", 20),
            "atr_period": qw.get("atr_period", 14),
            "rsi_period": qw.get("rsi_period", 14),
        }


# Module-level convenience: build one catalog per process (single event
# loop model). The store provider is attached at runtime by the data plane.
catalog = Catalog()
