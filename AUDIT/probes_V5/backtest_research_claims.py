"""Read-only synthetic probes of real APEX research APIs for VERIFY_V5.
No repository data, files, network, or credentials are accessed."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from apex.research import backtest as bt
from apex.research import optimizer as opt
from apex.research import promotion as promo
from apex.forecast import logistic as forecast


def trade(*, family="A", symbol="BTCUSDT", r=1.0, entry=100.0,
          exit=101.0, stop=99.0, atr=1.0):
    return bt.Trade(symbol=symbol, timeframe="1h", family_id=family,
        direction=1, entry_index=0, exit_index=1, entry_price=entry,
        exit_price=exit, stop_price=stop, target_price=102.0,
        quantity=1.0, r_multiple=r, costs=0.0, exit_reason="TARGET", atr=atr)


def main():
    out = {}
    eng = bt.BacktestEngine(symbol="X", timeframe="1h", alpha_spread=0.25)
    out["cost"] = {"quantity_1": eng._cost(2, 1.0),
                   "quantity_0_01": eng._cost(2, 0.01)}
    out["drawdown_R"] = bt.metrics_from_trades([trade(r=1), trade(r=-1)])
    gap_bars = [{"open":100,"high":101,"low":99,"close":100},
                {"open":98,"high":100,"low":97,"close":99},
                {"open":96,"high":97,"low":94,"close":95}]
    proposal = bt.SignalProposal(direction=1, stop_price=99, target_price=105,
                                 stop_distance=1)
    out["gap_entry"] = eng._resolve_exit(gap_bars, 1, proposal)
    out["empty_oos"] = bt.evaluate_wfo(train={}, test={"sharpe":2,"profit_factor":2,"max_drawdown":0.01}, oos={})
    out["stress"] = {name: bt.apply_stress(name,[0.1,-0.1])["returns"]
                     for name in ("Volume","CorrelationBreakdown","ExtremeFill")}
    out["benchmark"] = bt.benchmark_outperformance(
        strategy_returns=[.01,.02,.03,.04], benchmark_returns=[.10,.08,.11,.07])

    async def optimizer_probes():
        grid=opt.ParameterGrid([opt.ParameterRange("x",0,1,1)])
        d=opt.DualOptimizer(schedule=opt.OptimizerSchedule(continuous=True))
        out["optimizer_infeasible"] = await d.run_run(
            run_id="r", cells=["BTC-1h"], grids={"BTC-1h":grid},
            evaluate=lambda *_:{"feasible":False,"value":100}, optimizer="SIGNAL")
        # live_workload is an invocation snapshot; this probe does not claim live scheduler behavior.
        d2=opt.DualOptimizer(schedule=opt.OptimizerSchedule(continuous=True))
        out["optimizer_grid_hash_shape"] = []
        for bounds in ((0,1),(10,11)):
            g=opt.ParameterGrid([opt.ParameterRange("x",bounds[0],bounds[1],1)])
            d2.results.clear()
            await d2.run_run(run_id="same",cells=["cell"],grids={"cell":g},
                             evaluate=lambda *_:{"feasible":True,"value":1})
            out["optimizer_grid_hash_shape"].append(d2.results[0].sru_hash)
        out["optimizer_grid_hash_equal"] = out["optimizer_grid_hash_shape"][0] == out["optimizer_grid_hash_shape"][1]
    asyncio.run(optimizer_probes())

    out["risk_missing_value"] = opt.risk_objective(expected_net_r=1,max_drawdown=0,
       drawdown_limit=.1,leverage_adherence=1,
       per_regime_stability={k:0 for k in ("LOW","NORMAL","HIGH","EXTREME","CRISIS")})
    pool=promo.FamilyPool("A")
    for i in range(30): pool.add(trade(family="A",r=1))
    candidate=promo.PromotionCandidate("B",pool,
       {"decision":"PROMOTED"},{"flagged_high":False},{"passes":True},
       {"outperforms":True})
    out["mismatched_candidate_pool"] = candidate.gates()
    out["shrinkage_n0"] = promo.shrink_cell_rate(cell_rate=1,cell_n=0,family_rate=.3,family_variance=0)
    out["family_bad_trade"] = {"wins": pool.wins, "n":pool.n,
                                "eligible":promo.family_pool_gate(pool)["eligible"]}
    try: out["pool_serialization"] = pool.to_dict()
    except Exception as e: out["pool_serialization"] = type(e).__name__ + ": " + str(e)
    out["cvar"] = bt.cvar_bootstrap([-.1,-.1], paths=1000, seed=7)
    out["composite_low_n"] = forecast.composite_estimate(
        {"f": {"p": .99, "n_obs": 1}})
    print(json.dumps(out, sort_keys=True, indent=2, default=str))

if __name__ == "__main__": main()
