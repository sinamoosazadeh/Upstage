"""Ch.20 — Liquidity Proxy Models: the 38-concept registry (AA.2–AA.4), the six
formal rejections (AA.5) and the formula-bearing Q3 proxies.

Blueprint law
-------------
AA.1  the 38 constituent concepts = 25 pure L1 (A01–A25) + 10 L2-proxy
      (B01–B10) + 3 L3-proxy (D01–D03); the six formal rejections C01–C06 are
      ratified as infeasible without genuine L2/L3 feeds.
AA.2  every L1 concept carries a *disposition*: ``existing-in-frozen``,
      ``registered-new`` or ``research-registered``.
AA.5  the rejections stay rejected: missing data is QX, never estimated
      (no ``L2Snapshot.v1`` consumer may exist while no genuine L2 feed does).
AA.6  the symmetry decree abolishes symbol tiering: every one of the 10
      symbols executes every registered computation at its frequency.
AA.7  every heavy computation stays incremental; **Numba is a Wave-Out item**
      (§9.5-9 / P6) and Float32 is therefore NOT used — the numerical contract
      of Ch.2 §2.2 (Decimal at the store boundary, double precision inside the
      formulas) governs (see ``[ISSUE-CP8-002]``).

Discipline
----------
* Every formula here is Q3-labeled: a best-effort observable proxy, never a
  claim of true L2/L3 data.
* A concept whose formula the blueprint does NOT specify is registered with
  ``status="REGISTERED_OPEN"`` and **no active value** (EC-register discipline,
  Ch.17 §17.1): the dependent path stays conservative instead of a guessed
  implementation being invented (G6 fail-closed).
* Nothing here writes runtime state or parameters.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

CONTRACT_VERSION = "4.0.0"

Q3 = "Q3"                      # best-effort observable proxy (§2.1 Q-class)
DELTA_LABEL = "proxy, not true delta"   # AA.4/D01 mandatory label

#: AA.7-1 incremental-computation law (normative deployment rule).
INCREMENTAL_ONLY = True
#: AA.7-2: Numba is not in the SBOM and is a Wave-Out item — never imported.
NUMBA_USED = False

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# --------------------------------------------------------------------------
# AA.2–AA.4 — the registry of 38 concepts
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ProxyConcept:
    """One registry row of the Ch.20 proxy layer."""

    concept_id: str
    name: str
    layer: str                 # "L1" | "L2P" | "L3P"
    frozen_status: str         # "existing-in-frozen" | "registered-new" | ...
    integration: str           # what the frozen document does with it
    q_label: str               # "Q1" (pure observable) | "Q3" (proxy)
    owner: str                 # module that owns it, or "" when OPEN
    formula: str = ""          # callable name in this module, when implemented
    status: str = "REGISTERED_OPEN"   # IMPLEMENTED | EXISTING_IN_FROZEN | REGISTERED_OPEN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id, "name": self.name, "layer": self.layer,
            "frozen_status": self.frozen_status, "integration": self.integration,
            "q_label": self.q_label, "owner": self.owner, "formula": self.formula,
            "status": self.status, "contract_version": CONTRACT_VERSION,
        }


def _c(cid: str, name: str, layer: str, frozen: str, integration: str,
       q: str, owner: str, formula: str = "",
       status: str = "REGISTERED_OPEN") -> ProxyConcept:
    return ProxyConcept(cid, name, layer, frozen, integration, q, owner,
                        formula, status)


#: AA.2 — L1 concepts A01–A25 (exactly 25 rows).
L1_CONCEPTS: Tuple[ProxyConcept, ...] = (
    _c("A01", "Alpha thesis registry (promotion governance input)", "L1",
       "registered-new", "thesis registry feeding promotion governance",
       "Q1", "apex.research.promotion", "ThesisRegistry",
       "IMPLEMENTED"),
    _c("A02", "Expected-utility decision framework (R-economics)", "L1",
       "existing-in-frozen", "EU_unit = P·RR − (1−P)·1 − C_unit − R_penalty",
       "Q1", "apex.decision.pipeline", "economic_utility", "EXISTING_IN_FROZEN"),
    _c("A03", "Regime detection via HMM", "L1", "existing-in-frozen, upgrade",
       "E11 software + Markov transition + hysteresis",
       "Q1", "apex.engines.e11_regime", "", "EXISTING_IN_FROZEN"),
    _c("A04", "BOCPD regime-shift detection", "L1", "registered-new",
       "registered extension detecting regime failure, complementary to "
       "hysteresis; no active value until its closure record is APPROVED",
       "Q1", "", "", "REGISTERED_OPEN"),
    _c("A05", "Kalman filter for volatility estimation", "L1",
       "existing-in-research",
       "registered as R-ATR-003 | Kalman | OPEN with an open Q,R closure "
       "dependency; no active value while OPEN",
       "Q1", "", "", "REGISTERED_OPEN"),
    _c("A06", "Bayesian update (Beta-Bernoulli win-rate posterior)", "L1",
       "existing-in-frozen", "operational in forecast/posterior components",
       "Q1", "apex.forecast.logistic", "", "EXISTING_IN_FROZEN"),
    _c("A07", "Portfolio construction (correlation + exposure vetoes)", "L1",
       "existing-in-frozen",
       "correlation matrix + exposure vetoes + conflict/redundancy penalties "
       "+ symbol/portfolio ceilings + risk-ladder steps",
       "Q1", "apex.risk.kernel", "", "EXISTING_IN_FROZEN"),
    _c("A08", "Alpha decay (Q_time exponential model)", "L1",
       "existing-in-frozen", "Q_time = exp(−λ·age), λ = 0.1",
       "Q1", "apex.quality.vector", "", "EXISTING_IN_FROZEN"),
    _c("A09", "Information-theoretic entropy / regime quality", "L1",
       "existing-in-frozen", "H = −Σ p ln p in the regime engine",
       "Q1", "apex.engines.e11_regime", "", "EXISTING_IN_FROZEN"),
    _c("A10", "Bootstrap / Monte-Carlo (CVaR battery)", "L1",
       "existing-in-frozen", "1000-path CVaR_95 in the risk kernel",
       "Q1", "apex.risk.kernel", "cvar_bootstrap", "IMPLEMENTED"),
    _c("A11", "Extreme Value Theory (GPD tail risk)", "L1",
       "registered-new, advisory",
       "advisory estimator complementing CVaR_95; advisory ⇒ no active value",
       "Q1", "", "", "REGISTERED_OPEN"),
    _c("A12", "SPRT live-performance monitoring", "L1", "registered-new",
       "live-performance monitor (Z.6); complements the backtest gate",
       "Q1", "apex.research.promotion", "sprt_step", "IMPLEMENTED"),
    _c("A13", "Survival analysis (max_hold calibration)", "L1",
       "existing-in-research", "Q6 research slot; max_hold calibration",
       "Q1", "", "", "REGISTERED_OPEN"),
    _c("A14", "DCC-GARCH dynamic correlation", "L1", "registered-new",
       "nightly-registered dynamic correlation matrix feeding exposure vetoes; "
       "no active value until its closure record is APPROVED",
       "Q1", "", "", "REGISTERED_OPEN"),
    _c("A15", "Adaptive thresholds (dynamic/governed)", "L1",
       "existing-in-frozen",
       "the dynamic/governed class + >10% drift rollback + Q_param monitoring",
       "Q1", "apex.research.governance", "ParameterClass",
       "EXISTING_IN_FROZEN"),
    _c("A16", "MTF memory (multi-timeframe alignment)", "L1",
       "existing-in-frozen", "cross-timeframe alignment in the context fabric",
       "Q1", "apex.fabric.context", "", "EXISTING_IN_FROZEN"),
    _c("A17", "Fractal parent-child structure (Wyckoff)", "L1",
       "existing-in-frozen", "structure points across all timeframes",
       "Q1", "apex.engines.e01_structure", "", "EXISTING_IN_FROZEN"),
    _c("A18", "Wyckoff 8-phase model + OI divergence", "L1",
       "existing-in-frozen", "8-phase probabilistic model + transition matrix",
       "Q1", "apex.engines.e08_wyckoff", "", "EXISTING_IN_FROZEN"),
    _c("A19", "Funding-rate regime (monitoring → input)", "L1",
       "existing-in-frozen, upgrade",
       "funding monitoring + severe-cost alert promoted to a regime input",
       "Q1", "apex.data_catalog.ingest.toobit_public", "funding_alert",
       "EXISTING_IN_FROZEN"),
    _c("A20", "Open-interest divergence (price/OI mismatch)", "L1",
       "existing-in-frozen", "OI/price divergence as a pattern indicator",
       "Q1", "apex.engines.e09_trend", "", "EXISTING_IN_FROZEN"),
    _c("A21", "Taker-volume pressure", "L1", "registered-new, fills formula gap",
       "Pressure = (Buy − Sell)/Total from the Toobit trade feed",
       "Q3", "apex.research.proxies", "taker_pressure", "IMPLEMENTED"),
    _c("A22", "Information ratio (economics reporting)", "L1",
       "registered-new", "complementary reporting metric beside buy-and-hold",
       "Q1", "apex.research.proxies", "information_ratio", "IMPLEMENTED"),
    _c("A23", "Break of Structure / Change of Character (L1 via ATR)", "L1",
       "existing-in-frozen", "structure engine with ATR filtering",
       "Q1", "apex.engines.e01_structure", "", "EXISTING_IN_FROZEN"),
    _c("A24", "Regime duration / memory (stay probability)", "L1",
       "existing-in-frozen, upgrade", "transition matrix persistence",
       "Q1", "apex.engines.e11_regime", "", "EXISTING_IN_FROZEN"),
    _c("A25", "Information diffusion (inter-symbol lag)", "L1",
       "registered-new, research",
       "registered research extension of SMT; research ⇒ no active value",
       "Q1", "", "", "REGISTERED_OPEN"),
)

#: AA.3 — L2-proxy concepts B01–B10 (exactly 10 rows, all Q3-labeled).
L2_PROXY_CONCEPTS: Tuple[ProxyConcept, ...] = (
    _c("B01", "Corwin-Schultz spread estimator (High/Low only)", "L2P",
       "critical gap",
       "OFFICIAL spread estimator feeding half_spread in the execution cost "
       "model (the constant 0.0005 example is superseded)",
       Q3, "apex.research.proxies", "corwin_schultz_spread", "IMPLEMENTED"),
    _c("B02", "Abdi-Ranaldo spread (volatility-normalized)", "L2P",
       "registered-new, cross-check",
       "secondary estimator for B01 health monitoring; |B01−B02| above the "
       "governed threshold raises the spread-quality flag",
       Q3, "apex.research.proxies", "abdi_ranaldo_spread", "IMPLEMENTED"),
    _c("B03", "Roll spread estimator", "L2P", "registered-new, research-only",
       "research/optional estimator from return autocorrelation",
       Q3, "apex.research.proxies", "roll_spread", "IMPLEMENTED"),
    _c("B04", "Order-book imbalance proxy (obi_proxy)", "L2P",
       "critical gap (renamed from order_book_imbalance)",
       "(TakerBuy − TakerSell)/TotalVol from the Toobit trade feed",
       Q3, "apex.research.proxies", "obi_proxy", "IMPLEMENTED"),
    _c("B05", "Probability of Informed Trading (VPIN, BVC)", "L2P",
       "existing-in-frozen, upgrade",
       "E02 computes the time-bucketed BVC VPIN; volume bucketing registered "
       "as an upgrade option (both frozen-compatible)",
       Q3, "apex.engines.e02_liquidity", "", "EXISTING_IN_FROZEN"),
    _c("B06", "Kyle's lambda (price impact)", "L2P", "registered-new",
       "λ = cov(r, v_signed)/var(v_signed) on a rolling 100-candle window; "
       "feeds the slippage model (B10)",
       Q3, "apex.research.proxies", "kyle_lambda", "IMPLEMENTED"),
    _c("B07", "Amihud illiquidity metric", "L2P", "registered-new",
       "amihud_illiquidity_proxy = |return| / volume; feeds liquidity "
       "classification and the position-size ceiling",
       Q3, "apex.research.proxies", "amihud_illiquidity", "IMPLEMENTED"),
    _c("B08", "Liquidity-regime composite", "L2P", "registered-new",
       "composite of Amihud + OBI proxy + Kyle λ feeding context/regime",
       Q3, "apex.research.proxies", "liquidity_regime_composite", "IMPLEMENTED"),
    _c("B09", "Value area / volume profile (VP)", "L2P",
       "existing-in-frozen, frozen-superior",
       "E03 sorted-volume VP is retained; the OHLCV-distributed variant stays "
       "a lightweight fallback for depth-less timeframes",
       Q3, "apex.engines.e03_volume", "", "EXISTING_IN_FROZEN"),
    _c("B10", "Adaptive slippage composite", "L2P", "critical gap",
       "Slippage = f(CorwinSpread, Kyle×size, FlowToxicity) with governed "
       "weights (replacing α_spread·|size/ADV| as the sole term)",
       Q3, "apex.research.proxies", "adaptive_slippage", "IMPLEMENTED"),
)

#: AA.4 — L3-proxy concepts D01–D03 (exactly 3 rows, all Q3-labeled).
L3_PROXY_CONCEPTS: Tuple[ProxyConcept, ...] = (
    _c("D01", "Footprint delta (delta, cvd, footprint fields)", "L3P",
       "critical gap",
       "Delta = TakerBuy − TakerSell per candle, explicitly labeled "
       f"'{DELTA_LABEL}' (E03's prohibition on generating true delta stands)",
       Q3, "apex.research.proxies", "footprint_delta", "IMPLEMENTED"),
    _c("D02", "Liquidation-cascade detector", "L3P",
       "new, highest crypto-specific value",
       "cascade = (count_liq_in_window > threshold) ∧ (|Δprice| > k·ATR) ∧ "
       "(OI_drop > threshold)",
       Q3, "apex.research.proxies", "detect_liquidation_cascade",
       "IMPLEMENTED"),
    _c("D03", "Stop-hunt wick (sweep detection)", "L3P", "existing-in-frozen",
       "E02's five-prerequisite sweep is authoritative",
       Q3, "apex.engines.e02_liquidity", "", "EXISTING_IN_FROZEN"),
)

PROXY_REGISTRY: Tuple[ProxyConcept, ...] = (
    L1_CONCEPTS + L2_PROXY_CONCEPTS + L3_PROXY_CONCEPTS)

REGISTRY_SIZE = 38           # AA.1: "thirty-eight (38) constituent concepts"


# --------------------------------------------------------------------------
# AA.5 — the six formal rejections (C01–C06)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RejectedConcept:
    """One formal rejection; the upgrade contract stays available."""

    concept_id: str
    concept: str
    reason: str
    #: probe tokens that must NEVER appear in the runtime surface: their
    #: presence would mean the rejected concept was implemented anyway.
    probes: Tuple[str, ...] = ()
    upgrade_contract: str = "L2Snapshot.v1"

    def to_dict(self) -> Dict[str, Any]:
        return {"concept_id": self.concept_id, "concept": self.concept,
                "reason": self.reason,
                "upgrade_contract": self.upgrade_contract,
                "status": "REJECTED"}


REJECTED_CONCEPTS: Tuple[RejectedConcept, ...] = (
    RejectedConcept("C01", "Real order-book depth (per price level)",
                    "requires real-time L2 book; Toobit provides aggregate OI "
                    "only", ("per_price_level_depth", "depth_by_price_level")),
    RejectedConcept("C02", "Queue position within a price level",
                    "L2-exclusive; reconstructed depth is unreliable",
                    ("queue_position", "queue_ahead")),
    RejectedConcept("C03", "Iceberg order detection",
                    "requires L2 order-ID matching; impossible from trades "
                    "alone", ("iceberg_order", "iceberg_detect")),
    RejectedConcept("C04", "Precise spoofing identification",
                    "requires L2 book history + signature matching; >90% "
                    "false-positive rate with L1-only",
                    ("spoof_detect", "spoofing_signature")),
    RejectedConcept("C05", "Exact per-price-level footprint",
                    "L3-exclusive; not recoverable from aggregated data",
                    ("footprint_by_price_level", "exact_footprint")),
    RejectedConcept("C06", "Market-maker inventory dynamics",
                    "requires L2 order-ID persistence + MM identification",
                    ("market_maker_inventory", "mm_inventory_model")),
)

REJECTED_SIZE = 6


def registry_rows() -> List[Dict[str, Any]]:
    """The complete 38-row registry as plain dicts (audit surface)."""
    return [c.to_dict() for c in PROXY_REGISTRY]


def rejected_rows() -> List[Dict[str, Any]]:
    return [r.to_dict() for r in REJECTED_CONCEPTS]


def registry_summary() -> Dict[str, Any]:
    """Counts by layer/status — the ``registry-38`` completeness evidence."""
    by_layer: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for row in PROXY_REGISTRY:
        by_layer[row.layer] = by_layer.get(row.layer, 0) + 1
        by_status[row.status] = by_status.get(row.status, 0) + 1
    return {"total": len(PROXY_REGISTRY), "expected_total": REGISTRY_SIZE,
            "by_layer": by_layer, "by_status": by_status,
            "rejected": len(REJECTED_CONCEPTS),
            "complete": len(PROXY_REGISTRY) == REGISTRY_SIZE,
            "rejected_complete": len(REJECTED_CONCEPTS) == REJECTED_SIZE,
            "contract_version": CONTRACT_VERSION}


def assert_registry_complete() -> Dict[str, Any]:
    """Fail-closed completeness check: 25 L1 + 10 L2P + 3 L3P = 38, and the
    six rejections are present with distinct ids."""
    ids = [c.concept_id for c in PROXY_REGISTRY]
    if len(ids) != len(set(ids)):
        raise ValueError("PROXY_REGISTRY_DUPLICATE_ID")
    summary = registry_summary()
    if summary["by_layer"].get("L1") != 25:
        raise ValueError("PROXY_REGISTRY_L1_INCOMPLETE")
    if summary["by_layer"].get("L2P") != 10:
        raise ValueError("PROXY_REGISTRY_L2_INCOMPLETE")
    if summary["by_layer"].get("L3P") != 3:
        raise ValueError("PROXY_REGISTRY_L3_INCOMPLETE")
    if len(REJECTED_CONCEPTS) != REJECTED_SIZE:
        raise ValueError("PROXY_REJECTIONS_INCOMPLETE")
    return summary


def assert_rejected_absent(root: Optional[Path] = None) -> Dict[str, Any]:
    """AA.5 enforcement: no rejected concept may exist in the runtime surface.

    Scans every ``*.py`` file under ``apex/`` (excluding this module, which
    only *names* the rejections) for the probe tokens of C01–C06.
    """
    root = Path(root) if root is not None else REPO_ROOT
    hits: List[Dict[str, str]] = []
    for path in sorted(root.glob("apex/**/*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        for rej in REJECTED_CONCEPTS:
            for probe in rej.probes:
                if probe in text:
                    hits.append({"concept_id": rej.concept_id, "probe": probe,
                                 "file": str(path.relative_to(root))})
    if hits:
        raise ValueError(f"REJECTED_CONCEPT_PRESENT:{hits}")
    return {"scanned_root": str(root), "rejected_absent": True,
            "probes_checked": sum(len(r.probes) for r in REJECTED_CONCEPTS),
            "hits": []}


# --------------------------------------------------------------------------
# Q3 proxy formulas
# --------------------------------------------------------------------------

def _num(x: Any) -> float:
    return float(x)


@dataclass
class SpreadEstimate:
    """One Q3 spread estimate with its label and sample size."""

    estimator: str
    spread: float
    n_pairs: int
    q_label: str = Q3
    clamped: bool = False
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"estimator": self.estimator, "spread": self.spread,
                "n_pairs": self.n_pairs, "q_label": self.q_label,
                "clamped": self.clamped, "note": self.note,
                "contract_version": CONTRACT_VERSION}


def corwin_schultz_spread(bars: Sequence[Mapping[str, Any]]
                          ) -> SpreadEstimate:
    """B01 — Corwin-Schultz (2012) high/low spread estimator.

    β = mean over consecutive pairs of [ln(H_t/L_t)² + ln(H_{t+1}/L_{t+1})²]
    γ = mean over consecutive pairs of [ln(max(H_t,H_{t+1})/min(L_t,L_{t+1}))]²
    α = (√(2β) − √β)/(3 − 2√2) − √(γ/(3 − 2√2))
    S = 2(e^α − 1)/(1 + e^α); the standard negative-spread adjustment clamps
    S to 0 and reports ``clamped=True``.
    """
    if len(bars) < 2:
        raise ValueError("INSUFFICIENT_HISTORY_B01")
    k = 3.0 - 2.0 * math.sqrt(2.0)
    betas: List[float] = []
    gammas: List[float] = []
    for i in range(len(bars) - 1):
        h0, l0 = _num(bars[i]["high"]), _num(bars[i]["low"])
        h1, l1 = _num(bars[i + 1]["high"]), _num(bars[i + 1]["low"])
        if l0 <= 0 or l1 <= 0 or h0 <= 0 or h1 <= 0:
            raise ValueError("NON_POSITIVE_PRICE_B01")
        betas.append(math.log(h0 / l0) ** 2 + math.log(h1 / l1) ** 2)
        gammas.append(math.log(max(h0, h1) / min(l0, l1)) ** 2)
    beta = sum(betas) / len(betas)
    gamma = sum(gammas) / len(gammas)
    alpha = (math.sqrt(2.0 * beta) - math.sqrt(beta)) / k - math.sqrt(gamma / k)
    spread = 2.0 * (math.exp(alpha) - 1.0) / (1.0 + math.exp(alpha))
    clamped = spread < 0.0
    return SpreadEstimate("CORWIN_SCHULTZ", max(spread, 0.0), len(betas),
                          clamped=clamped,
                          note="negative estimate clamped to 0 (CS rule)"
                          if clamped else "")


def abdi_ranaldo_spread(bars: Sequence[Mapping[str, Any]]) -> SpreadEstimate:
    """B02 — Abdi-Ranaldo (2017): S = 2·sqrt(mean((c_t − η_t)²)) with
    c_t = ln(C_t/C_{t-1}) and η_t = mid-log of H,L differenced."""
    if len(bars) < 3:
        raise ValueError("INSUFFICIENT_HISTORY_B02")
    diffs: List[float] = []
    for i in range(1, len(bars)):
        c = math.log(_num(bars[i]["close"]) / _num(bars[i - 1]["close"]))
        eta = (0.5 * (math.log(_num(bars[i]["high"])) +
                      math.log(_num(bars[i]["low"])))
               - 0.5 * (math.log(_num(bars[i - 1]["high"])) +
                        math.log(_num(bars[i - 1]["low"]))))
        diffs.append((c - eta) ** 2)
    mean_sq = sum(diffs) / len(diffs)
    return SpreadEstimate("ABDI_RANALDO", 2.0 * math.sqrt(mean_sq),
                          len(diffs))


def roll_spread(returns: Sequence[float]) -> SpreadEstimate:
    """B03 — Roll (1984): S = 2·sqrt(−cov(r_t, r_{t-1})) when the first-order
    autocovariance is negative, else 0 (research/optional estimator)."""
    r = [float(x) for x in returns]
    if len(r) < 3:
        raise ValueError("INSUFFICIENT_HISTORY_B03")
    n = len(r)
    mean = sum(r) / n
    cov = sum((r[i] - mean) * (r[i - 1] - mean) for i in range(1, n)) / (n - 1)
    clamped = cov >= 0.0
    spread = 0.0 if clamped else 2.0 * math.sqrt(-cov)
    return SpreadEstimate("ROLL", spread, n - 1, clamped=clamped,
                          note="non-negative autocovariance ⇒ S=0"
                          if clamped else "")


def spread_quality_flag(cs: SpreadEstimate, ar: SpreadEstimate, *,
                        threshold: float = 0.5) -> Dict[str, Any]:
    """B02 cross-check: |B01 − B02| above the governed threshold raises the
    spread-quality flag (the flag is informational, never an order gate)."""
    delta = abs(cs.spread - ar.spread)
    return {"b01": cs.spread, "b02": ar.spread, "delta": delta,
            "threshold": float(threshold), "flag": delta > float(threshold),
            "q_label": Q3}


def obi_proxy(*, taker_buy: float, taker_sell: float,
              total_volume: float) -> Dict[str, Any]:
    """B04 — ``obi_proxy = (TakerBuy − TakerSell)/TotalVol`` (Q3)."""
    total = float(total_volume)
    if total <= 0.0:
        raise ValueError("ZERO_TOTAL_VOLUME_B04")
    value = (float(taker_buy) - float(taker_sell)) / total
    return {"obi_proxy": value, "q_label": Q3,
            "inputs": {"taker_buy": float(taker_buy),
                       "taker_sell": float(taker_sell),
                       "total_volume": total}}


def taker_pressure(*, taker_buy: float, taker_sell: float) -> Dict[str, Any]:
    """A21 — ``Pressure = (Buy − Sell)/Total`` over the Toobit trade feed."""
    total = float(taker_buy) + float(taker_sell)
    if total <= 0.0:
        raise ValueError("ZERO_TRADE_FEED_A21")
    value = (float(taker_buy) - float(taker_sell)) / total
    return {"taker_pressure": value, "q_label": Q3, "total": total}


def footprint_delta(*, taker_buy: float, taker_sell: float) -> Dict[str, Any]:
    """D01 — ``Delta = TakerBuy − TakerSell`` per candle, explicitly labeled
    a proxy and never presented as true delta (E03 prohibition)."""
    return {"delta": float(taker_buy) - float(taker_sell),
            "label": DELTA_LABEL, "q_label": Q3,
            "true_delta": False}


def cvd(deltas: Iterable[float], *, start: float = 0.0) -> Dict[str, Any]:
    """D01 — cumulative volume delta over the proxy deltas (Q3)."""
    series: List[float] = []
    running = float(start)
    for d in deltas:
        running += float(d)
        series.append(running)
    return {"cvd": series, "final": running, "label": DELTA_LABEL,
            "q_label": Q3}


def kyle_lambda(*, returns: Sequence[float], signed_volume: Sequence[float],
                window: int = 100) -> Dict[str, Any]:
    """B06 — ``λ = cov(r, v_signed)/var(v_signed)`` on a rolling window."""
    r = [float(x) for x in returns]
    v = [float(x) for x in signed_volume]
    if len(r) != len(v):
        raise ValueError("KYLE_INPUT_LENGTH_QX")
    n = min(len(r), int(window))
    if n < 3:
        raise ValueError("INSUFFICIENT_HISTORY_B06")
    r, v = r[-n:], v[-n:]
    mr = sum(r) / n
    mv = sum(v) / n
    cov = sum((r[i] - mr) * (v[i] - mv) for i in range(n)) / (n - 1)
    var = sum((v[i] - mv) ** 2 for i in range(n)) / (n - 1)
    if var <= 0.0:
        raise ValueError("ZERO_SIGNED_VOLUME_VARIANCE_B06")
    return {"kyle_lambda": cov / var, "window": n, "q_label": Q3}


def amihud_illiquidity(*, returns: Sequence[float],
                       volumes: Sequence[float]) -> Dict[str, Any]:
    """B07 — ``amihud_illiquidity_proxy = |return| / volume`` (mean over the
    window; a zero-volume bar is skipped, never fabricated)."""
    r = [float(x) for x in returns]
    v = [float(x) for x in volumes]
    if len(r) != len(v):
        raise ValueError("AMIHUD_INPUT_LENGTH_QX")
    ratios = [abs(r[i]) / v[i] for i in range(len(r)) if v[i] > 0.0]
    if not ratios:
        raise ValueError("NO_LIQUID_BAR_B07")
    return {"amihud_illiquidity_proxy": sum(ratios) / len(ratios),
            "n": len(ratios), "skipped_zero_volume": len(r) - len(ratios),
            "q_label": Q3}


def _zscore(values: Sequence[float]) -> Tuple[float, float, float]:
    n = len(values)
    if n < 2:
        raise ValueError("INSUFFICIENT_HISTORY_Z")
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    if var <= 0.0:
        raise ValueError("ZERO_VARIANCE_Z")
    return mean, var, math.sqrt(var)


def liquidity_regime_composite(*, amihud: Sequence[float],
                               obi: Sequence[float],
                               kyle: Sequence[float],
                               weights: Optional[Mapping[str, float]] = None
                               ) -> Dict[str, Any]:
    """B08 — composite of Amihud + OBI + Kyle λ feeding E11/E02.

    The three inputs are standardized (z-scores within their own windows) and
    combined with governed weights (default equal thirds); the composite is
    higher = *better* liquidity (Amihud enters with a negative sign, since a
    higher Amihud means a more illiquid market). Missing/insufficient input is
    fail-closed (``*_QX``), never replaced by a default.
    """
    w = {"amihud": 1.0 / 3.0, "obi": 1.0 / 3.0, "kyle": 1.0 / 3.0}
    if weights:
        w.update({k: float(v) for k, v in weights.items()})
    total_w = sum(w.values())
    if total_w <= 0.0:
        raise ValueError("COMPOSITE_WEIGHTS_QX")
    parts: Dict[str, float] = {}
    ma, _, sa = _zscore([float(x) for x in amihud])
    parts["amihud_z"] = (sum(float(x) for x in amihud) / len(amihud) - ma) / sa
    mo, _, so = _zscore([float(x) for x in obi])
    parts["obi_z"] = (sum(float(x) for x in obi) / len(obi) - mo) / so
    mk, _, sk = _zscore([float(x) for x in kyle])
    parts["kyle_z"] = (sum(float(x) for x in kyle) / len(kyle) - mk) / sk
    composite = (w["amihud"] * (-parts["amihud_z"]) + w["obi"] * parts["obi_z"]
                 + w["kyle"] * parts["kyle_z"]) / total_w
    return {"liquidity_regime_composite": composite, "components": parts,
            "weights": w, "q_label": Q3,
            "higher_is_better_liquidity": True}


def adaptive_slippage(*, corwin_spread: float, kyle_lambda_value: float,
                      order_size: float, flow_toxicity: float,
                      weights: Optional[Mapping[str, float]] = None
                      ) -> Dict[str, Any]:
    """B10 — ``Slippage = f(CorwinSpread, Kyle×size, FlowToxicity)``.

    Governed weights (default 0.4 / 0.4 / 0.2) are a *governed default* of the
    research plane; the result is a fractional cost estimate (Q3) that feeds
    the execution-cost model beside the frozen ``α_spread·|size/ADV|`` term.
    """
    w = {"corwin": 0.4, "kyle": 0.4, "toxicity": 0.2}
    if weights:
        w.update({k: float(v) for k, v in weights.items()})
    total = sum(w.values())
    if total <= 0.0:
        raise ValueError("SLIPPAGE_WEIGHTS_QX")
    impact = abs(float(kyle_lambda_value) * float(order_size))
    value = (w["corwin"] * abs(float(corwin_spread)) + w["kyle"] * impact
             + w["toxicity"] * abs(float(flow_toxicity))) / total
    return {"slippage_fraction": value, "weights": w, "q_label": Q3,
            "impact_term": impact}


def detect_liquidation_cascade(*, liq_count_in_window: int,
                               price_change: float, atr: float,
                               oi_drop_fraction: float,
                               count_threshold: int = 10,
                               price_k: float = 3.0,
                               oi_drop_threshold: float = 0.02
                               ) -> Dict[str, Any]:
    """D02 — ``cascade = (count > threshold) ∧ (|Δprice| > k·ATR) ∧
    (OI_drop > threshold)``; all three legs are required (fail-closed)."""
    if float(atr) <= 0.0:
        raise ValueError("ZERO_ATR_D02")
    legs = {
        "count": int(liq_count_in_window) > int(count_threshold),
        "price": abs(float(price_change)) > float(price_k) * float(atr),
        "oi_drop": float(oi_drop_fraction) > float(oi_drop_threshold),
    }
    return {"cascade": all(legs.values()), "legs": legs, "q_label": Q3,
            "thresholds": {"count": int(count_threshold),
                           "price_k": float(price_k),
                           "oi_drop": float(oi_drop_threshold)}}


def information_ratio(*, returns: Sequence[float],
                      benchmark_returns: Sequence[float]) -> Dict[str, Any]:
    """A22 — ``IR = mean(r − b)/std(r − b)`` (economics reporting metric)."""
    r = [float(x) for x in returns]
    b = [float(x) for x in benchmark_returns]
    if len(r) != len(b):
        raise ValueError("IR_INPUT_LENGTH_QX")
    if len(r) < 2:
        raise ValueError("INSUFFICIENT_HISTORY_A22")
    excess = [r[i] - b[i] for i in range(len(r))]
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    if var <= 0.0:
        raise ValueError("ZERO_TRACKING_ERROR_A22")
    return {"information_ratio": mean / math.sqrt(var), "n": len(excess),
            "tracking_error": math.sqrt(var)}


def wilson_lower_bound(k: int, n: int, *, z: float = 1.96) -> float:
    """Z.3 Wilson 95% lower bound (shared with the promotion gate)."""
    if n <= 0:
        raise ValueError("ZERO_SAMPLE_Z3")
    if k < 0 or k > n:
        raise ValueError("INVALID_COUNT_Z3")
    p = k / n
    denom = 1.0 + (z * z) / n
    centre = p + (z * z) / (2.0 * n)
    margin = z * math.sqrt((p * (1.0 - p)) / n + (z * z) / (4.0 * n * n))
    return (centre - margin) / denom


def sample_size_for_half_width(p: float, half_width: float, *,
                               z: float = 1.96) -> int:
    """Wilson-style planning helper used by the bootstrap ETA report."""
    if not 0.0 < float(p) < 1.0:
        raise ValueError("P_OUT_OF_RANGE")
    if float(half_width) <= 0.0:
        raise ValueError("HALF_WIDTH_QX")
    n = (z * z) * float(p) * (1.0 - float(p)) / (float(half_width) ** 2)
    return int(math.ceil(n))
