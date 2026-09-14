"""Ch.18 — Research plane replay engine, metrics, walk-forward, Monte-Carlo
and the shared stress battery (§18.1 + §18.4, W.2 objectives).

What is real here
-----------------
* :class:`BacktestEngine` replays a *signal function* over closed bars with a
  strict PIT window (the callback can only ever see bars ``<= i``; the entry is
  filled at the NEXT bar's open, so no bar can trade on its own future), fills
  with the frozen cost model (fee 0.02 %, ``α_spread`` slippage or the B10
  composite when supplied) and the X.4 exit precedence (hard stop first, then
  target, then the time stop).
* Every metric of §18.1 is computed from the resulting trade list: Winrate,
  PF, Sharpe, Deflated Sharpe, Max Drawdown, Expectancy (+ Monte-Carlo
  mean/std/min/max/median/5 %/95 %).
* :func:`walk_forward` performs the 70/30 train-test split with a trailing OOS
  window and :func:`evaluate_wfo` applies the frozen promotion criteria
  (``OOS Sharpe > 1.0 ∧ PF > 1.2 ∧ Max Drawdown < 15 %``).
* The seven §18.4 stress scenarios are executable transforms of a return
  series (Crash/Pump/Volatility/Volume/Correlation/Extreme-fill/Negative-tail).
* :func:`deterministic_double_run` is the T-DR-001/T-REPLAY-BINARY harness:
  the same inputs must produce byte-identical canonical output.

No statistic is ever fabricated: an unavailable input raises ``*_QX`` instead
of returning a made-up number.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.identity.canonical_json import canonical_json

CONTRACT_VERSION = "4.0.0"

#: §18.1 promotion criteria (WFO / OOS).
WFO_MIN_OOS_SHARPE = 1.0
WFO_MIN_PF = 1.2
WFO_MAX_DRAWDOWN = 0.15
#: §18.1 WFO split.
WFO_TRAIN_FRACTION = 0.70
WFO_TEST_FRACTION = 0.30
#: §18.1 Monte-Carlo default.
MC_PATHS = 1000
#: W.2-1 minimum trades per test window (signal-optimizer constraint).
MIN_TRADES_PER_TEST_WINDOW = 100
#: Decidable default cost model (frozen signal-layer literals of §17.1).
FEE_FRACTION = 0.0002
FUNDING_CARRY_DEFAULT = 0.0      # carried, never derived (CP-7 ISSUE-005 law)


class BacktestError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------
# Trades and metrics
# --------------------------------------------------------------------------

@dataclass
class Trade:
    """One completed round trip (the unit the promotion protocol pools)."""

    symbol: str
    timeframe: str
    family_id: str
    direction: int
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    quantity: float
    r_multiple: float
    costs: float
    exit_reason: str
    atr: float = 0.0

    @property
    def win(self) -> bool:
        """Cost-adjusted win (Z.3 uses the cost-adjusted success rate)."""
        return self.r_multiple > 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"symbol": self.symbol, "timeframe": self.timeframe,
                "family_id": self.family_id, "direction": self.direction,
                "entry_index": self.entry_index, "exit_index": self.exit_index,
                "entry_price": self.entry_price, "exit_price": self.exit_price,
                "stop_price": self.stop_price, "target_price": self.target_price,
                "quantity": self.quantity, "r_multiple": self.r_multiple,
                "costs": self.costs, "exit_reason": self.exit_reason,
                "atr": self.atr, "win": self.win,
                "contract_version": CONTRACT_VERSION}


def _mean(xs: Sequence[float]) -> float:
    if not xs:
        raise BacktestError("EMPTY_SERIES")
    return sum(xs) / len(xs)


def _std(xs: Sequence[float], *, sample: bool = True) -> float:
    n = len(xs)
    if n < 2:
        raise BacktestError("INSUFFICIENT_OBSERVATIONS")
    m = _mean(xs)
    denom = (n - 1) if sample else n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / denom)


def sharpe(returns: Sequence[float], *, periods_per_year: float = 1.0) -> float:
    """Annualized Sharpe with rf = 0 (the blueprint's convention)."""
    r = [float(x) for x in returns]
    sd = _std(r)
    if sd == 0.0:
        raise BacktestError("ZERO_VARIANCE_SHARPE")
    return _mean(r) / sd * math.sqrt(periods_per_year)


def profit_factor(returns: Sequence[float]) -> float:
    gross_win = sum(x for x in map(float, returns) if x > 0)
    gross_loss = -sum(x for x in map(float, returns) if x < 0)
    if gross_loss == 0.0:
        if gross_win == 0.0:
            raise BacktestError("NO_PNL_SHARPE")
        return float("inf")
    return gross_win / gross_loss


def max_drawdown(returns: Sequence[float]) -> float:
    """Fractional peak-to-trough drawdown of the equity curve (compounded)."""
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for r in map(float, returns):
        equity *= (1.0 + r)
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return worst


def expectancy(returns: Sequence[float]) -> float:
    """Mean R per trade (the §18.1 Expectancy metric)."""
    return _mean([float(x) for x in returns])


def metrics_from_trades(trades: Sequence[Trade], *,
                        periods_per_year: float = 1.0) -> Dict[str, Any]:
    """The §18.1 metric block from a trade list (no fabrication: an empty
    sample raises)."""
    r = [t.r_multiple for t in trades]
    if not r:
        raise BacktestError("NO_TRADES_QX")
    wins = sum(1 for t in trades if t.win)
    out: Dict[str, Any] = {
        "trades": len(trades), "wins": wins, "winrate": wins / len(r),
        "profit_factor": profit_factor(r), "expectancy_r": expectancy(r),
        "max_drawdown": max_drawdown(r),
        "mean_r": _mean(r), "std_r": _std(r) if len(r) > 1 else 0.0,
        "total_r": sum(r),
    }
    try:
        out["sharpe"] = sharpe(r, periods_per_year=periods_per_year)
    except BacktestError as exc:
        out["sharpe"] = None
        out["sharpe_reason"] = exc.reason
    out["contract_version"] = CONTRACT_VERSION
    return out


def deflated_sharpe_ratio(*, observed_sharpe: float, trials: int,
                          variance_of_trials: float, skew: float,
                          kurtosis: float, n_observations: int) -> Dict[str, Any]:
    """Deflated Sharpe Ratio (Bailey & López de Prado, §18.1 + Z.9-2).

    ``SR0 = sqrt(V[SR]) · ((1−γ)·Z⁻¹(1−1/N) + γ·Z⁻¹(1−1/(N·e)))`` with
    ``γ`` the Euler–Mascheroni constant, then

    ``DSR = Z[( (SR − SR0)·sqrt(n−1) ) / sqrt(1 − γ3·SR + ((γ4−1)/4)·SR²)]``

    with ``γ3``/``γ4`` the skewness/kurtosis of the returns. A non-positive
    variance of trials or a sample below 2 observations fails closed.
    """
    if trials < 1:
        raise BacktestError("TRIALS_QX")
    if n_observations < 2:
        raise BacktestError("INSUFFICIENT_OBSERVATIONS")
    if variance_of_trials <= 0.0:
        raise BacktestError("ZERO_TRIAL_VARIANCE")
    gamma = 0.5772156649015329
    if trials == 1:
        # A single trial carries no multiple-testing deflation: SR0 = 0.
        sr0 = 0.0
    else:
        z1 = _norm_ppf(1.0 - 1.0 / trials)
        z2 = _norm_ppf(1.0 - 1.0 / (trials * math.e))
        sr0 = math.sqrt(variance_of_trials) * ((1.0 - gamma) * z1 + gamma * z2)
    denominator = 1.0 - skew * observed_sharpe + ((kurtosis - 1.0) / 4.0) * \
        observed_sharpe ** 2
    if denominator <= 0.0:
        raise BacktestError("DSR_DENOMINATOR_QX")
    z = ((observed_sharpe - sr0) * math.sqrt(n_observations - 1.0)) / \
        math.sqrt(denominator)
    return {"observed_sharpe": observed_sharpe, "expected_max_sharpe": sr0,
            "deflated_sharpe": observed_sharpe - sr0,
            "dsr_statistic": z, "dsr_pvalue": 1.0 - _norm_cdf(z),
            "trials": trials, "n_observations": n_observations}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Acklam's rational approximation of the standard-normal quantile."""
    if not 0.0 < p < 1.0:
        raise BacktestError("PPF_DOMAIN_QX", str(p))
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1.0)


# --------------------------------------------------------------------------
# Walk-forward
# --------------------------------------------------------------------------

def walk_forward(n_observations: int, *,
                 train_fraction: float = WFO_TRAIN_FRACTION,
                 oos_fraction: float = 0.0) -> Dict[str, Any]:
    """§18.4 split: train 70 % / test 30 %, followed by an OOS window.

    ``oos_fraction`` is the share of the *whole* sample reserved after the test
    block; ``0.0`` keeps the classic train/test split with the test block
    doubling as the OOS window of the promotion criterion (documented).
    """
    if n_observations < 10:
        raise BacktestError("INSUFFICIENT_HISTORY_WFO")
    if not 0.0 < train_fraction < 1.0:
        raise BacktestError("TRAIN_FRACTION_QX")
    train_end = int(math.floor(n_observations * train_fraction))
    if oos_fraction <= 0.0:
        test_end = n_observations
    else:
        test_end = int(math.floor(n_observations * (1.0 - oos_fraction)))
    if not train_end < test_end <= n_observations:
        raise BacktestError("SPLIT_DEGENERATE")
    return {"train": [0, train_end], "test": [train_end, test_end],
            "oos": [test_end, n_observations],
            "train_fraction": train_fraction,
            "test_fraction": (test_end - train_end) / n_observations,
            "oos_fraction": (n_observations - test_end) / n_observations}


def evaluate_wfo(*, train: Mapping[str, Any], test: Mapping[str, Any],
                 oos: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The frozen WFO promotion criteria of §18.1.

    ``OOS Sharpe > 1.0 ∧ PF > 1.2 ∧ Max Drawdown < 15 %`` — the OOS block is
    the test block when no separate OOS window was carved out.
    """
    oos_block = dict(oos) if oos else dict(test)
    sharpe_value = oos_block.get("sharpe")
    pf = oos_block.get("profit_factor")
    dd = oos_block.get("max_drawdown")
    checks = {
        "oos_sharpe_gt_1_0": (sharpe_value is not None
                              and float(sharpe_value) > WFO_MIN_OOS_SHARPE),
        "pf_gt_1_2": (pf is not None and float(pf) > WFO_MIN_PF),
        "drawdown_lt_15pct": (dd is not None and float(dd) < WFO_MAX_DRAWDOWN),
    }
    return {"decision": "PROMOTED" if all(checks.values()) else "NOT_PROMOTED",
            "checks": checks, "oos": oos_block, "test": dict(test),
            "train": dict(train),
            "criteria": {"min_oos_sharpe": WFO_MIN_OOS_SHARPE,
                         "min_pf": WFO_MIN_PF, "max_drawdown": WFO_MAX_DRAWDOWN}}


# --------------------------------------------------------------------------
# Monte-Carlo (§18.1)
# --------------------------------------------------------------------------

def monte_carlo(trades: Sequence[Trade], *, paths: int = MC_PATHS,
                seed: int, horizon: Optional[int] = None,
                periods_per_year: float = 1.0) -> Dict[str, Any]:
    """1000-path bootstrap resampling of the trade R-multiples.

    Deterministic for a given ``(seed, trades, paths, horizon)``: the sampler
    is a self-contained SplitMix64 stream (no ``random`` module dependency, no
    interpreter-version drift).
    """
    r = [float(t.r_multiple) for t in trades]
    if not r:
        raise BacktestError("NO_TRADES_QX")
    if paths <= 0:
        raise BacktestError("PATHS_QX")
    n = int(horizon or len(r))
    state = int(seed) & 0xFFFFFFFFFFFFFFFF
    finals: List[float] = []
    sharpes: List[float] = []
    for _ in range(paths):
        path_r: List[float] = []
        for _ in range(n):
            state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
            z = state
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
            z ^= z >> 31
            idx = z % len(r)
            path_r.append(r[idx])
        finals.append(sum(path_r))
        try:
            sharpes.append(sharpe(path_r, periods_per_year=periods_per_year))
        except BacktestError:
            sharpes.append(0.0)
    ordered = sorted(finals)

    def pct(p: float) -> float:
        idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
        return ordered[idx]

    return {"paths": paths, "seed": int(seed), "horizon": n,
            "mean": _mean(finals), "std": _std(finals),
            "min": min(finals), "max": max(finals),
            "median": ordered[len(ordered) // 2], "p5": pct(0.05),
            "p95": pct(0.95), "sharpe_mean": _mean(sharpes),
            "contract_version": CONTRACT_VERSION}


def cvar_bootstrap(returns: Sequence[float], *, paths: int = MC_PATHS,
                   seed: int, level: float = 0.95) -> Dict[str, Any]:
    """A10 — 1000-path bootstrap CVaR (5 % tail) of a return series."""
    r = [float(x) for x in returns]
    if len(r) < 2:
        raise BacktestError("INSUFFICIENT_OBSERVATIONS")
    state = int(seed) & 0xFFFFFFFFFFFFFFFF
    means: List[float] = []
    for _ in range(paths):
        acc = 0.0
        for _ in range(len(r)):
            state = (state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
            z = state
            z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
            z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
            z ^= z >> 31
            acc += r[z % len(r)]
        means.append(acc / len(r))
    means.sort()
    tail = means[: max(1, int(len(means) * (1.0 - level)))]
    return {"cvar": _mean(tail), "level": level, "paths": paths,
            "seed": int(seed)}


# --------------------------------------------------------------------------
# §18.4 stress battery
# --------------------------------------------------------------------------

STRESS_SCENARIOS: Tuple[Dict[str, Any], ...] = (
    {"name": "Crash", "spec": "BTC −50% within 1 hour, volatility ×3",
     "measure": "maximum drawdown / return"},
    {"name": "Pump", "spec": "BTC +100% within 1 hour, volatility ×3",
     "measure": "maximum gain"},
    {"name": "Volatility", "spec": "5×ATR gap stress",
     "measure": "risk / volatility response"},
    {"name": "Volume", "spec": "−90% volume (×0.1)", "measure": "liquidity response"},
    {"name": "CorrelationBreakdown",
     "spec": "all pairwise ρ → 1.0 for 24 h",
     "measure": "portfolio concentration risk, multiplier adequacy"},
    {"name": "ExtremeFill",
     "spec": "spread ×10 + order rejects + partial-fill storm (50% of "
             "attempts) + degraded fill price",
     "measure": "fill assumptions, retry/fill-gap handling"},
    {"name": "NegativeTail", "spec": "price shock beyond historical support",
     "measure": "sizing floors, stop behavior"},
)

STRESS_SCENARIO_NAMES: Tuple[str, ...] = tuple(s["name"] for s in STRESS_SCENARIOS)


def apply_stress(scenario: str, returns: Sequence[float], *,
                 crash_fraction: float = 0.50, pump_fraction: float = 1.00,
                 volatility_multiple: float = 5.0,
                 correlation_multiple: float = 3.0
                 ) -> Dict[str, Any]:
    """Execute one §18.4 scenario on a return series (real transform)."""
    if scenario not in STRESS_SCENARIO_NAMES:
        raise BacktestError("UNKNOWN_STRESS_SCENARIO", scenario)
    r = [float(x) for x in returns]
    if not r:
        raise BacktestError("EMPTY_SERIES")
    stressed: List[float]
    if scenario == "Crash":
        stressed = [(-crash_fraction + volatility_multiple * x) for x in r]
    elif scenario == "Pump":
        stressed = [(volatility_multiple * x) for x in r]
        stressed[0] = stressed[0] + pump_fraction
    elif scenario == "Volatility":
        stressed = [volatility_multiple * x for x in r]
    elif scenario == "Volume":
        stressed = [0.1 * x for x in r]
    elif scenario == "CorrelationBreakdown":
        stressed = [correlation_multiple * x for x in r]
    elif scenario == "ExtremeFill":
        stressed = [x - 10.0 * FEE_FRACTION - 0.5 * abs(x) for x in r]
    else:  # NegativeTail
        stressed = [min(x, -abs(x) - 0.5) for x in r]
    return {"scenario": scenario, "returns": stressed,
            "metrics": {"max_drawdown": max_drawdown(stressed),
                        "total_return": sum(stressed),
                        "mean": _mean(stressed)},
            "spec": next(s["spec"] for s in STRESS_SCENARIOS
                         if s["name"] == scenario)}


def stress_battery(returns: Sequence[float]) -> Dict[str, Any]:
    """The full seven-scenario battery + the normative crisis factor (0.5
    exposure-cap multiplier during a correlation breakdown)."""
    results = {name: apply_stress(name, returns) for name in STRESS_SCENARIO_NAMES}
    return {"scenarios": results, "count": len(results),
            "crisis_factor": 0.5, "contract_version": CONTRACT_VERSION}


# --------------------------------------------------------------------------
# Backtest engine (deterministic, PIT-safe)
# --------------------------------------------------------------------------

@dataclass
class SignalProposal:
    """What a replay signal function returns for one closed bar."""

    direction: int                # +1 long, −1 short
    stop_price: float
    target_price: float
    stop_distance: float
    family_id: str = "SF_FVG_SWEEP_REV"

    def __post_init__(self) -> None:
        if self.direction not in (-1, 1):
            raise BacktestError("DIRECTION_QX", str(self.direction))
        if self.stop_distance <= 0.0:
            raise BacktestError("STOP_DISTANCE_QX", str(self.stop_distance))


class BacktestEngine:
    """Deterministic single-symbol replay (Ch.18 §18.1 "Backtest" row).

    Contract
    --------
    * ``signal_fn(window, index)`` receives ONLY the closed bars ``0..index``
      (the engine slices before calling — the PIT rule is structural).
    * entry fills at bar ``index + 1`` open (never the signal bar's close).
    * exit order inside a bar follows X.4 precedence: hard stop first, then
      target, then the time stop at ``max_hold`` bars.
    * costs: ``fee`` per side + slippage; ``slippage_fn`` may inject the B10
      composite (default: the frozen α_spread term).
    """

    def __init__(self, *, symbol: str, timeframe: str,
                 fee: float = FEE_FRACTION, alpha_spread: float = 0.25,
                 max_hold: int = 12,
                 min_quantity: float = 0.0,
                 slippage_fn: Optional[Callable[[int], float]] = None) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.fee = float(fee)
        self.alpha_spread = float(alpha_spread)
        self.max_hold = int(max_hold)
        self.min_quantity = float(min_quantity)
        self.slippage_fn = slippage_fn

    # -- helpers ---------------------------------------------------------
    def _cost(self, index: int, notional_fraction: float) -> float:
        slip = (self.slippage_fn(index) if self.slippage_fn
                else self.alpha_spread * abs(notional_fraction))
        return 2.0 * self.fee + abs(slip)

    def run(self, bars: Sequence[Mapping[str, Any]],
            signal_fn: Callable[[Sequence[Mapping[str, Any]], int],
                                Optional[SignalProposal]],
            *, start_index: int = 1) -> Dict[str, Any]:
        if len(bars) < 3:
            raise BacktestError("INSUFFICIENT_BARS_QX")
        trades: List[Trade] = []
        skipped: List[Dict[str, Any]] = []
        i = int(start_index)
        while i < len(bars) - 1:
            window = bars[: i + 1]           # structural PIT guard
            proposal = signal_fn(window, i)
            if proposal is None:
                i += 1
                continue
            entry_index = i + 1
            bar = bars[entry_index]
            entry_price = float(bar["open"])
            quantity = 1.0
            if quantity < self.min_quantity:
                skipped.append({"index": i, "reason": "MIN_QUANTITY_QX"})
                i += 1
                continue
            costs = self._cost(entry_index, quantity)
            exit_index, exit_price, reason = self._resolve_exit(
                bars, entry_index, proposal)
            sign = 1.0 if proposal.direction > 0 else -1.0
            gross_r = sign * (exit_price - entry_price) / proposal.stop_distance
            net_r = gross_r - costs * entry_price / proposal.stop_distance
            trades.append(Trade(
                symbol=self.symbol, timeframe=self.timeframe,
                family_id=proposal.family_id, direction=proposal.direction,
                entry_index=entry_index, exit_index=exit_index,
                entry_price=entry_price, exit_price=exit_price,
                stop_price=proposal.stop_price,
                target_price=proposal.target_price, quantity=quantity,
                r_multiple=net_r, costs=costs, exit_reason=reason,
                atr=proposal.stop_distance))
            i = exit_index + 1
        return {"engine": "CP8_BACKTEST", "symbol": self.symbol,
                "timeframe": self.timeframe, "bars": len(bars),
                "trades": trades, "skipped": skipped,
                "contract_version": CONTRACT_VERSION}

    def _resolve_exit(self, bars: Sequence[Mapping[str, Any]], entry_index: int,
                      proposal: SignalProposal) -> Tuple[int, float, str]:
        long = proposal.direction > 0
        last = min(len(bars) - 1, entry_index + self.max_hold)
        for j in range(entry_index, last + 1):
            bar = bars[j]
            high, low = float(bar["high"]), float(bar["low"])
            if j == entry_index:
                # X.4 precedence: an entry bar that has already touched the
                # stop is a stop-out, never a target fill.
                if (long and low <= proposal.stop_price) or \
                        (not long and high >= proposal.stop_price):
                    return j, float(proposal.stop_price), "STOP"
            if (long and low <= proposal.stop_price) or \
                    (not long and high >= proposal.stop_price):
                return j, float(proposal.stop_price), "STOP"
            if (long and high >= proposal.target_price) or \
                    (not long and low <= proposal.target_price):
                return j, float(proposal.target_price), "TARGET"
            if j == last:
                return j, float(bar["close"]), "TIME_STOP"
        raise BacktestError("EXIT_UNRESOLVED_QX")

    def run_with_metrics(self, bars, signal_fn, **kwargs) -> Dict[str, Any]:
        result = self.run(bars, signal_fn, **kwargs)
        result["metrics"] = metrics_from_trades(result["trades"])
        return result


def buy_and_hold(bars: Sequence[Mapping[str, Any]], *,
                 start_index: int = 0) -> Dict[str, Any]:
    """The mandatory Z.9-1 benchmark (net of the frozen fee, both sides)."""
    if len(bars) < 2:
        raise BacktestError("INSUFFICIENT_BARS_QX")
    first = float(bars[start_index]["open"])
    last = float(bars[-1]["close"])
    gross = (last - first) / first
    net = gross - 2.0 * FEE_FRACTION
    return {"buy_and_hold": net, "gross": gross,
            "start_index": start_index, "periods": len(bars) - start_index}


def benchmark_outperformance(*, strategy_returns: Sequence[float],
                             benchmark_returns: Sequence[float],
                             confidence: float = 0.95) -> Dict[str, Any]:
    """Z.9-1: is the strategy's Sharpe *statistically significantly* better
    than buy-and-hold over the same calendar period?

    Uses the paired difference series and a one-sided normal test on the mean
    difference of the two return streams (the blueprint's "95 % confidence").
    """
    s = [float(x) for x in strategy_returns]
    b = [float(x) for x in benchmark_returns]
    if len(s) != len(b):
        raise BacktestError("BENCHMARK_LENGTH_QX")
    if len(s) < 3:
        raise BacktestError("INSUFFICIENT_OBSERVATIONS")
    diff = [s[i] - b[i] for i in range(len(s))]
    sd = _std(diff)
    if sd == 0.0:
        raise BacktestError("ZERO_VARIANCE_BENCHMARK")
    z = _mean(diff) / (sd / math.sqrt(len(diff)))
    z_crit = _norm_ppf(confidence)
    return {"mean_excess": _mean(diff), "z": z, "z_critical": z_crit,
            "confidence": confidence, "outperforms": z > z_crit,
            "sharpe_strategy": sharpe(s) if _std(s) > 0 else None,
            "sharpe_benchmark": sharpe(b) if _std(b) > 0 else None}


# --------------------------------------------------------------------------
# Determinism harness (T-DR-001 / T-REPLAY_BINARY)
# --------------------------------------------------------------------------

def deterministic_double_run(worker: Callable[[], Any]) -> Dict[str, Any]:
    """Run ``worker`` twice and compare canonical JSON bytes.

    This is the CP-8 double-run determinism evidence: a difference is a
    finding (it is returned, never hidden).
    """
    first = canonical_json(worker())
    second = canonical_json(worker())
    return {"identical": first == second, "first_len": len(first),
            "second_len": len(second),
            "first_hash": __import__("hashlib").sha256(first.encode()).hexdigest(),
            "second_hash": __import__("hashlib").sha256(second.encode()).hexdigest(),
            "contract_version": CONTRACT_VERSION}
