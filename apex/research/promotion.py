"""Ch.18 W.5 + Z.1–Z.9 — the promotion gate, the family-pool protocol, SPRT
live monitoring, deflated Sharpe + PBO, and the alpha-thesis registry (A01).

Blueprint law implemented here
------------------------------
Z.1/Z.2  the sampling unit is the **setup family**, pooled over ATR-normalized
         R-multiples across all 10 symbols; without ATR normalization pooling
         would be a statistical violation.
Z.3      Wilson 95 % lower bound of the cost-adjusted success rate must exceed
         the cost-adjusted breakeven rate.
Z.4      absolute floor: 30 pooled trades; below it, no promotion but the
         sample keeps accumulating.
Z.5      small cells are shrunk toward the family base rate with
         ``λ = n_cell / (n_cell + n_family-mean-variance)``.
Z.6      SPRT live monitor with the four halt-and-rollback actions.
Z.8      worked example re-derived from the formulas (never copied).
Z.9      the three retained pre-promotion requirements: BTC buy-and-hold
         benchmark, deflated Sharpe, PBO.
W.5      a candidate package is validated against the RED LINE before any paper
         trial (``apex.research.governance.validate_package``).

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.research.backtest import (Trade, _mean, _std, metrics_from_trades,
                                    deflated_sharpe_ratio)
from apex.research.governance import (ParameterPackage, validate_package)

CONTRACT_VERSION = "4.0.0"

FAMILY_POOL_MIN_TRADES = 30          # Z.4 absolute floor
WILSON_Z = 1.96                      # Z.3 95 % confidence
DEFAULT_BREAKEVEN = 0.48             # Z.3 "typically 48–50 %"
DEFAULT_P_BREAKEVEN_RANGE = (0.48, 0.50)
SPRT_PMIN_GAP = 0.05                 # Z.6 "typically 3–5 percentage points"
SPRT_ALPHA = 0.05
SPRT_BETA = 0.05
DEFLATED_SHARPE_MIN_RANGE = (0.5, 1.0)   # Z.9-2 owner acceptance band
PBO_REJECT_FRACTION = 0.50           # Z.9-3


class PromotionError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------
# A01 — alpha thesis registry (promotion-governance input)
# --------------------------------------------------------------------------

THESIS_FIELDS: Tuple[str, ...] = (
    "thesis_id", "hypothesis", "expected_return", "holding_period",
    "invalidation_condition")


@dataclass(frozen=True)
class ThesisRecord:
    """A01 — ``thesis_id, hypothesis, expected_return, holding_period,
    invalidation_condition`` (AA.2)."""

    thesis_id: str
    hypothesis: str
    expected_return: str
    holding_period: str
    invalidation_condition: str

    def __post_init__(self) -> None:
        if not self.thesis_id.startswith("thesis-"):
            raise PromotionError("THESIS_ID_QX", self.thesis_id)
        for name in THESIS_FIELDS[1:]:
            if not str(getattr(self, name)).strip():
                raise PromotionError("THESIS_FIELD_EMPTY", name)

    def to_dict(self) -> Dict[str, Any]:
        return {f: getattr(self, f) for f in THESIS_FIELDS}


class ThesisRegistry:
    """The registry table ``theses`` of the research plane."""

    def __init__(self) -> None:
        self._rows: Dict[str, ThesisRecord] = {}

    def register(self, record: ThesisRecord) -> ThesisRecord:
        if record.thesis_id in self._rows:
            raise PromotionError("THESIS_DUPLICATE", record.thesis_id)
        self._rows[record.thesis_id] = record
        return record

    def get(self, thesis_id: str) -> ThesisRecord:
        if thesis_id not in self._rows:
            raise PromotionError("THESIS_ABSENT", thesis_id)
        return self._rows[thesis_id]

    def rows(self) -> List[Dict[str, Any]]:
        return [self._rows[k].to_dict() for k in sorted(self._rows)]

    def __len__(self) -> int:
        return len(self._rows)


# --------------------------------------------------------------------------
# Z.2/Z.3/Z.4 — family pool
# --------------------------------------------------------------------------

@dataclass
class FamilyPool:
    """Union of every trade outcome of ONE setup family across the 10 symbols.

    The ATR-normalization prerequisite is *structural* here: pooling accepts
    only trades whose R-unit is positive and ATR-denominated (``atr > 0`` and
    ``stop_price != entry_price``), which is what makes the R-multiples
    scale-invariant across symbols (Z.2).
    """

    family_id: str
    trades: List[Trade] = field(default_factory=list)
    symbols_seen: List[str] = field(default_factory=list)

    def add(self, trade: Trade) -> None:
        if trade.family_id != self.family_id:
            raise PromotionError("FAMILY_ID_MISMATCH", trade.family_id)
        risk_unit = abs(float(trade.entry_price) - float(trade.stop_price))
        if float(trade.atr) <= 0.0 or risk_unit <= 0.0:
            raise PromotionError("ATR_NORMALIZATION_QX", trade.symbol)
        self.trades.append(trade)
        if trade.symbol not in self.symbols_seen:
            self.symbols_seen.append(trade.symbol)

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.win)

    @property
    def success_rate(self) -> float:
        if not self.trades:
            raise PromotionError("EMPTY_POOL")
        return self.wins / self.n

    def per_symbol(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for t in self.trades:
            row = out.setdefault(t.symbol, {"n": 0, "wins": 0})
            row["n"] += 1
            row["wins"] += 1 if t.win else 0
        return out

    def family_variance(self) -> float:
        """Sample variance of the pooled R-multiples (Z.5 denominator term)."""
        return _std([t.r_multiple for t in self.trades]) ** 2 if self.n > 1 \
            else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"family_id": self.family_id, "n": self.n, "wins": self.wins,
                "success_rate": self.success_rate if self.n else None,
                "symbols": list(self.symbols_seen),
                "atr_normalized": all(t.stop_distance > 0.0
                                      for t in self.trades),
                "contract_version": CONTRACT_VERSION}


def wilson_gate(*, n: int, k: int, p_breakeven: float = DEFAULT_BREAKEVEN,
                z: float = WILSON_Z) -> Dict[str, Any]:
    """Z.3 promotion gate: ``p_lower > p_breakeven``."""
    if not 0.0 <= float(p_breakeven) <= 1.0:
        raise PromotionError("BREAKEVEN_RANGE_QX", str(p_breakeven))
    p_hat = k / n if n else 0.0
    denom = 1.0 + (z * z) / n if n else 1.0
    if n:
        centre = p_hat + (z * z) / (2.0 * n)
        margin = z * math.sqrt((p_hat * (1.0 - p_hat)) / n + (z * z) / (4.0 * n * n))
        lower = (centre - margin) / denom
    else:
        lower = 0.0
    return {"n": n, "k": k, "p_hat": p_hat, "wilson_lower": lower,
            "p_breakeven": float(p_breakeven), "z": z,
            "above_breakeven": lower > float(p_breakeven)}


def family_pool_gate(family: FamilyPool, *,
                     p_breakeven: float = DEFAULT_BREAKEVEN) -> Dict[str, Any]:
    """Z.3 + Z.4 in one verdict, floor first (20-trade samples never promote)."""
    gate = wilson_gate(n=family.n, k=family.wins, p_breakeven=p_breakeven)
    floor_ok = family.n >= FAMILY_POOL_MIN_TRADES
    eligible = bool(floor_ok and gate["above_breakeven"])
    if not floor_ok:
        reason = "BELOW_ABSOLUTE_FLOOR_30"
    elif not gate["above_breakeven"]:
        reason = "WILSON_LOWER_BELOW_BREAKEVEN"
    else:
        reason = "PROMOTION_ALLOWED"
    return {**gate, "floor": FAMILY_POOL_MIN_TRADES, "floor_ok": floor_ok,
            "eligible": eligible, "reason": reason,
            "per_symbol": family.per_symbol()}


# --------------------------------------------------------------------------
# Z.5 — Bayesian shrinkage
# --------------------------------------------------------------------------

def shrinkage_factor(*, n_cell: int, family_variance: float) -> Dict[str, Any]:
    """``λ = n_cell / (n_cell + n_family-mean-variance)`` (Z.5)."""
    if n_cell < 0:
        raise PromotionError("N_CELL_QX")
    if family_variance < 0.0:
        raise PromotionError("FAMILY_VARIANCE_QX")
    denominator = n_cell + family_variance
    lam = 1.0 if denominator <= 0.0 else n_cell / denominator
    return {"lambda": lam, "n_cell": n_cell,
            "family_variance": family_variance}


def shrink_cell_rate(*, cell_rate: float, cell_n: int, family_rate: float,
                     family_variance: float) -> Dict[str, Any]:
    """Shrunk cell estimate ``= λ·cell_rate + (1−λ)·family_rate`` (Z.5)."""
    factor = shrinkage_factor(n_cell=cell_n, family_variance=family_variance)
    lam = factor["lambda"]
    shrunk = lam * float(cell_rate) + (1.0 - lam) * float(family_rate)
    return {**factor, "cell_rate": float(cell_rate),
            "family_rate": float(family_rate), "shrunk_rate": shrunk,
            "used_in_isolation": False}


# --------------------------------------------------------------------------
# Z.6 — SPRT live monitoring + halt/rollback
# --------------------------------------------------------------------------

@dataclass
class SPRTState:
    """Sequential Probability Ratio Test state for one live family."""

    p0: float                     # backtest cost-adjusted rate (H0)
    p_min: float                  # H1 rate (p0 − gap)
    alpha: float = SPRT_ALPHA
    beta: float = SPRT_BETA
    llr: float = 0.0
    wins: int = 0
    n: int = 0
    verdict: str = "CONTINUE"

    def __post_init__(self) -> None:
        if not 0.0 < self.p_min < self.p0 < 1.0:
            raise PromotionError("SPRT_RATES_QX",
                                 f"p0={self.p0} p_min={self.p_min}")

    @property
    def upper(self) -> float:
        return math.log((1.0 - self.beta) / self.alpha)

    @property
    def lower(self) -> float:
        return math.log(self.beta / (1.0 - self.alpha))

    def to_dict(self) -> Dict[str, Any]:
        return {"p0": self.p0, "p_min": self.p_min, "alpha": self.alpha,
                "beta": self.beta, "llr": self.llr, "wins": self.wins,
                "n": self.n, "verdict": self.verdict,
                "upper": self.upper, "lower": self.lower,
                "contract_version": CONTRACT_VERSION}


def sprt_step(state: SPRTState, *, win: bool) -> SPRTState:
    """One likelihood-ratio update.

    LR increment for a win: ``ln(p_min/p0)``... The blueprint's H1 is
    "true live success rate ≤ p_min", so a *win* is evidence for H0 and a
    *loss* is evidence for H1:

    * win  → ``+ ln(p0 / p_min)`` (H0 is more likely)
    * loss → ``+ ln((1 − p0) / (1 − p_min))`` (H1 is more likely)

    Stop when the LLR falls below ``ln(β/(1−α))`` ⇒ accept H1 (halt and roll
    back); above ``ln((1−β)/α)`` ⇒ reject H1 (live performance acceptable).
    """
    if win:
        state.llr += math.log(state.p0 / state.p_min)
        state.wins += 1
    else:
        state.llr += math.log((1.0 - state.p0) / (1.0 - state.p_min))
    state.n += 1
    if state.llr <= state.lower:
        state.verdict = "ACCEPT_H1"
    elif state.llr >= state.upper:
        state.verdict = "REJECT_H1"
    else:
        state.verdict = "CONTINUE"
    return state


def sprt_monitor(family_id: str, *, p0: float, gap: float = SPRT_PMIN_GAP,
                 outcomes: Sequence[bool] = ()) -> Dict[str, Any]:
    """Run a live outcome sequence through the SPRT and return the action."""
    state = SPRTState(p0=float(p0), p_min=float(p0) - float(gap))
    trace: List[Dict[str, Any]] = []
    for outcome in outcomes:
        sprt_step(state, win=bool(outcome))
        trace.append({"n": state.n, "llr": state.llr, "verdict": state.verdict})
        if state.verdict != "CONTINUE":
            break
    action = "CONTINUE"
    if state.verdict == "ACCEPT_H1":
        action = "HALT_AND_ROLLBACK"
    elif state.verdict == "REJECT_H1":
        action = "ACCEPT_PERFORMANCE"
    return {"family_id": family_id, "state": state.to_dict(),
            "trace": trace, "action": action,
            "rollback_actions": rollback_actions() if action == "HALT_AND_ROLLBACK"
            else []}


def rollback_actions() -> List[str]:
    """The four Z.6 halt-and-rollback actions, verbatim in substance."""
    return [
        "halt: no new entries for the family",
        "close: all open positions exit at market or via existing stop/target",
        "rollback: family removed from the live playbook, reverting to the "
        "previous validated parameter package or no-trade mode",
        "log: reason + timestamp + SPRT statistics persisted",
    ]


@dataclass
class LiveFamilyMonitor:
    """Per-family live monitor wrapper (SPRT + halt state)."""

    family_id: str
    state: SPRTState
    halted: bool = False
    log: List[Dict[str, Any]] = field(default_factory=list)

    def on_trade(self, *, win: bool, timestamp: str = "") -> Dict[str, Any]:
        sprt_step(self.state, win=win)
        entry = {"timestamp": timestamp, "win": win, "n": self.state.n,
                 "llr": self.state.llr, "verdict": self.state.verdict}
        self.log.append(entry)
        if self.state.verdict == "ACCEPT_H1":
            self.halted = True
        return {"family_id": self.family_id, "halted": self.halted,
                "action": ("HALT_AND_ROLLBACK" if self.halted
                           else "CONTINUE_PERFORMANCE_OK"),
                "sprt": self.state.to_dict(), "entry": entry}


# --------------------------------------------------------------------------
# Z.9-3 — Probability of Backtest Overfitting (combinatorial CV)
# --------------------------------------------------------------------------

def probability_of_backtest_overfitting(performance: Sequence[Sequence[float]],
                                        *, rank_below_median: float = 0.50
                                        ) -> Dict[str, Any]:
    """PBO over a ``folds × combinations`` performance matrix (Z.9-3).

    For every unordered pair of folds ``(S, T)``: take the in-sample winner on
    ``S``, look up its rank on ``T``. The candidate is flagged when the winner
    ranks in the *bottom half* on ``T`` in more than 50 % of the pairs.
    """
    if not performance:
        raise PromotionError("EMPTY_PERFORMANCE_MATRIX")
    rows = [list(map(float, r)) for r in performance]
    n_folds = len(rows)
    n_combos = len(rows[0])
    if n_combos < 2:
        raise PromotionError("PBO_REQUIRES_MULTIPLE_COMBINATIONS")
    if any(len(r) != n_combos for r in rows):
        raise PromotionError("PBO_MATRIX_RAGGED")
    if n_folds < 2:
        raise PromotionError("PBO_REQUIRES_MULTIPLE_FOLDS")
    below = 0
    pairs = 0
    lambdas: List[float] = []
    for a in range(n_folds):
        for b in range(n_folds):
            if a == b:
                continue
            is_row, oos_row = rows[a], rows[b]
            winner = max(range(n_combos), key=lambda c: is_row[c])
            rank = sum(1 for c in range(n_combos)
                       if oos_row[c] <= oos_row[winner])
            relative = rank / n_combos
            pairs += 1
            if relative <= rank_below_median:
                below += 1
            lambdas.append(relative)
    pbo = below / pairs
    return {"pbo": pbo, "pairs": pairs, "combinations": n_combos,
            "folds": n_folds,
            "flagged_high": pbo > PBO_REJECT_FRACTION,
            "threshold": PBO_REJECT_FRACTION,
            "mean_relative_rank": _mean(lambdas),
            "note": "high PBO ⇒ candidate rejected until the search "
                    "methodology is revised"}


def deflated_sharpe_gate(*, observed_sharpe: float, trials: int,
                         variance_of_trials: float, skew: float,
                         kurtosis: float, n_observations: int,
                         threshold: float = 0.5) -> Dict[str, Any]:
    """Z.9-2: the deflated Sharpe must clear the owner's acceptance threshold
    (governed band 0.5 – 1.0)."""
    result = deflated_sharpe_ratio(
        observed_sharpe=observed_sharpe, trials=trials,
        variance_of_trials=variance_of_trials, skew=skew, kurtosis=kurtosis,
        n_observations=n_observations)
    band = DEFLATED_SHARPE_MIN_RANGE
    if not band[0] <= float(threshold) <= band[1]:
        raise PromotionError("DEFLATED_SHARPE_THRESHOLD_QX", str(threshold))
    return {**result, "threshold": float(threshold),
            "threshold_band": list(band),
            "passes": result["deflated_sharpe"] >= float(threshold)}


# --------------------------------------------------------------------------
# Z.8 — worked example, re-derived (never copied)
# --------------------------------------------------------------------------

#: The blueprint words the promotable state as "PROMOTION_ALLOWED" in
#: Scenario A and "PROMOTION_GRANTED" in Scenario B — the same state, two
#: wordings; the harness compares canonical forms and never renames the source.
DECISION_CANON: Dict[str, str] = {
    "PROMOTION_ALLOWED": "PROMOTION_ALLOWED",
    "PROMOTION_GRANTED": "PROMOTION_ALLOWED",
    "NO_PROMOTION_BELOW_FLOOR": "NO_PROMOTION_BELOW_FLOOR",
    "STILL_BLOCKED": "STILL_BLOCKED",
}


def canonical_decision(label: str) -> str:
    return DECISION_CANON.get(label, label)


def z8_scenarios() -> Dict[str, Any]:
    """Re-derive Z.8 Scenario A and B from the Wilson formula.

    The blueprint's quoted bounds (49 %, 39 %, 46 %, 50 %) are reported beside
    the recomputed values so any divergence is visible as ``doc_inconsistency``
    (ADR-P2-007: re-derive, never copy).
    """
    scenarios = {
        "A": {"n": 42, "wins": 27, "cost_adjusted_rate": 0.58,
              "quoted_lower": 0.49, "breakeven": 0.48,
              "quoted_decision": "PROMOTION_ALLOWED"},
        "B_initial": {"n": 18, "wins": 11, "cost_adjusted_rate": 0.56,
                      "quoted_lower": 0.39, "breakeven": 0.48,
                      "quoted_decision": "NO_PROMOTION_BELOW_FLOOR"},
        "B_3months": {"n": 35, "wins": 22, "cost_adjusted_rate": 0.58,
                      "quoted_lower": 0.46, "breakeven": 0.48,
                      "quoted_decision": "STILL_BLOCKED"},
        "B_6months": {"n": 48, "wins": 31, "cost_adjusted_rate": 0.59,
                      "quoted_lower": 0.50, "breakeven": 0.48,
                      "quoted_decision": "PROMOTION_GRANTED"},
    }
    out: Dict[str, Any] = {}
    for name, s in scenarios.items():
        recomputed = wilson_gate(n=s["n"], k=s["wins"],
                                 p_breakeven=s["breakeven"])["wilson_lower"]
        floor_ok = s["n"] >= FAMILY_POOL_MIN_TRADES
        decision = ("PROMOTION_ALLOWED"
                    if floor_ok and recomputed > s["breakeven"]
                    else ("NO_PROMOTION_BELOW_FLOOR" if not floor_ok
                          else "STILL_BLOCKED"))
        out[name] = {
            "n": s["n"], "wins": s["wins"],
            "quoted_lower": s["quoted_lower"],
            "recomputed_lower": recomputed,
            "delta": recomputed - s["quoted_lower"],
            "quoted_decision": s["quoted_decision"],
            "recomputed_decision": decision,
            "consistent": abs(recomputed - s["quoted_lower"]) <= 0.005,
            "decision_consistent": (canonical_decision(decision)
                                    == canonical_decision(s["quoted_decision"])),
        }
    return {"scenarios": out,
            "all_lower_bounds_consistent": all(v["consistent"]
                                               for v in out.values()),
            "all_decisions_consistent": all(v["decision_consistent"]
                                            for v in out.values()),
            "spec": "APEX_GEN5.md L17238-17261 (Z.8)"}


# --------------------------------------------------------------------------
# The promotion decision (W.5 validation → promotion)
# --------------------------------------------------------------------------

@dataclass
class PromotionCandidate:
    """Everything the gate must see; a missing block fails the gate closed."""

    family_id: str
    pool: FamilyPool
    wfo: Mapping[str, Any]
    pbo: Mapping[str, Any]
    deflated_sharpe: Mapping[str, Any]
    benchmark: Optional[Mapping[str, Any]] = None
    breakeven: float = DEFAULT_BREAKEVEN

    def gates(self) -> Dict[str, Any]:
        pool_gate = family_pool_gate(self.pool, p_breakeven=self.breakeven)
        checks = {
            "family_pool": pool_gate["eligible"],
            "wfo": self.wfo.get("decision") == "PROMOTED",
            "pbo": not self.pbo.get("flagged_high", True),
            "deflated_sharpe": bool(self.deflated_sharpe.get("passes", False)),
            "benchmark": bool(self.benchmark is not None
                              and self.benchmark.get("outperforms", False)),
        }
        return {"family_id": self.family_id, "checks": checks,
                "pool_gate": pool_gate,
                "decision": "PROMOTE" if all(checks.values()) else "BLOCK",
                "failed": [k for k, v in checks.items() if not v],
                "contract_version": CONTRACT_VERSION}


def evaluate_promotion(candidate: PromotionCandidate) -> Dict[str, Any]:
    """W.5 validation gate → promotion decision (the pre-paper-trial stop)."""
    verdict = candidate.gates()
    verdict["paper_trial_required"] = verdict["decision"] == "PROMOTE"
    verdict["note"] = ("pre-promotion gates (Z.9) + family-pool protocol "
                       "(Z.3/Z.4) must ALL pass; the package still needs the "
                       "RED LINE validation and the owner's approval (W.5)")
    return verdict


def draft_package(*, candidate: PromotionCandidate, values: Mapping[str, Any],
                  version: str, code_revision: str, feature_version: str,
                  model_version: str, seed: int, reason: str,
                  proposals: Mapping[str, Mapping[str, Any]]
                  ) -> Dict[str, Any]:
    """Turn a TRULY promoted candidate into a parameter package.

    The package is refused unless the promotion gate passed, the RED LINE
    validation is clean and every changed value carries its complete change
    proposal (§17.1). Nothing here writes a file: injection is
    ``apex.research.governance.InjectionLedger`` into
    ``apex/research/params_suggestions/``.
    """
    verdict = evaluate_promotion(candidate)
    if verdict["decision"] != "PROMOTE":
        return {"decision": "REFUSED", "reason": "PROMOTION_GATE_BLOCKED",
                "failed": verdict["failed"]}
    package = ParameterPackage(
        package_id=f"pkg-{candidate.family_id}-{version}",
        version=version, values=dict(values), code_revision=code_revision,
        feature_version=feature_version, model_version=model_version,
        seed=int(seed), reason=reason, environment="RESEARCH")
    validation = validate_package(package, proposals=proposals)
    if validation["decision"] != "VALIDATED":
        return {"decision": "REFUSED", "reason": "PACKAGE_VALIDATION_FAILED",
                "validation": validation}
    return {"decision": "DRAFTED", "package": package,
            "validation": validation,
            "next_step": "paper trial → owner approval → versioned injection"}
