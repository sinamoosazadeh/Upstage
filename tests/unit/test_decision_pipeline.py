"""CP-6 battery — Decision Engine (Ch.14 §14.1) and Strategy Arbitration
(Ch.12 AF.1–AF.5), including the CP-6 seam test: the arbitration/decision layer
never imports or calls execution.
"""

from __future__ import annotations

import ast
import math
import pathlib

import pytest

from apex.config import load_params
from apex.decision.pipeline import (
    ARBITRATION_REASON_FIELDS,
    INELIGIBLE_FAMILIES,
    MIN_RR,
    NO_TRADE,
    PORTFOLIO_PROPOSAL_FIELDS,
    StrategyProposal,
    DecisionError,
    arbitrate,
    build_proposal,
    composite_rank_score,
    economic_utility,
    eligibility,
    eu_dollar,
    family_status_ok,
    generate_candidates,
    governed_limits,
    rank,
    regime_window_ok,
    select,
    slippage_model,
    units_of_r,
)

CAND = {
    "setup_id": "setup-1", "entry": 100.0, "stop": 97.0, "target": 109.0,
    "P": 0.6, "C": 0.7, "U_sum": 0.2, "cost_unit": 0.02, "r_penalty": 0.0,
    "is_risk_increase": False, "uncertainty_is_rising": False,
}


class TestUnitsAndCosts:
    def test_R_and_RR_definition(self):
        u = units_of_r(entry=100.0, stop=97.0, target=109.0)
        assert u["R"] == pytest.approx(3.0)
        assert u["RR"] == pytest.approx(3.0)          # 9/3
        assert u["G"] == pytest.approx(9.0)           # RR·R
        assert u["L"] == pytest.approx(3.0)
        # units must be consistent: G/L == RR
        assert u["G"] / u["L"] == pytest.approx(u["RR"])

    def test_RR_is_floored_at_half(self):
        u = units_of_r(entry=100.0, stop=98.0, target=99.0)   # 1/2 = 0.5
        assert u["RR"] == MIN_RR == 0.5
        u2 = units_of_r(entry=100.0, stop=98.0, target=99.0)   # 1/2 = 0.5
        assert u2["RR"] == 0.5
        u3 = units_of_r(entry=100.0, stop=99.5, target=100.1)  # 0.1 → floored
        assert u3["RR"] == 0.5
        assert u3["target_distance"] == pytest.approx(0.1)

    def test_zero_risk_unit_fails_closed(self):
        with pytest.raises(DecisionError, match="RISK_UNIT_QX"):
            units_of_r(entry=100.0, stop=100.0, target=110.0)

    def test_eu_formula_in_units_of_R(self):
        eu = economic_utility(p=0.6, rr=3.0, cost_unit=0.02, r_penalty=0.1)
        assert eu == pytest.approx(0.6 * 3.0 - 0.4 * 1.0 - 0.02 - 0.1)
        assert economic_utility(p=0.5, rr=1.0, cost_unit=0.0,
                               r_penalty=math.inf) == -math.inf

    def test_eu_dollar_uses_multiplier_and_price_scale(self):
        got = eu_dollar(eu_unit=1.08, sized_quantity=2.0,
                       contract_multiplier=0.001, price_scale=1000.0)
        assert got == pytest.approx(1.08 * 2.0 * 0.001 * 1000.0)
        assert math.isinf(eu_dollar(eu_unit=-math.inf, sized_quantity=1.0))

    def test_execution_layer_cost_model(self):
        r = load_params()["risk_defaults"]
        assert governed_limits()["cost_R_floor"] == r["cost_R_floor"] == 0.05
        got = slippage_model(order_size=50.0, adv=1000.0, alpha_spread=0.2)
        assert got["slippage"] == pytest.approx(0.2 * 0.05)
        assert got["impact"] == pytest.approx(0.05)
        missing = slippage_model(order_size=50.0, adv=None, alpha_spread=0.2)
        assert missing["available"] is False
        assert missing["slippage"] is None          # never fabricated as 0
        assert missing["reason"] == "SLIPPAGE_MODEL_UNAVAILABLE"
        with pytest.raises(DecisionError, match="ORDER_SIZE_QX"):
            slippage_model(order_size=-1.0, adv=100.0, alpha_spread=0.1)


class TestEligibility:
    def check(self, **over):
        base = dict(setup_valid=True, forecast_quality_ok=True,
                    conflict_state="CONSENSUS", q_raw=0.9, timeframe="1h",
                    freshness_ok=True, data_trust=0.9, p=0.6, p_min_tf=0.5,
                    c=0.7, c_min=0.4)
        base.update(over)
        return eligibility(base)

    def test_all_conditions_held(self):
        got = self.check()
        assert got["eligible"] is True and got["verdict"] == "ELIGIBLE"
        assert got["failed"] == []
        assert got["q_min_tf"] == 0.50

    def test_each_condition_can_block(self):
        for key, val in (("setup_valid", False), ("forecast_quality_ok", False),
                        ("conflict_state", "HARD_CONFLICT"), ("q_raw", 0.49),
                        ("freshness_ok", False), ("data_trust", 0.29),
                        ("p", 0.49), ("c", 0.39)):
            got = self.check(**{key: val})
            assert got["eligible"] is False, key
            assert got["failed"], key

    def test_p_or_c_shortfall_is_insufficient_evidence(self):
        assert self.check(p=0.49)["verdict"] == "INSUFFICIENT_EVIDENCE"
        assert self.check(c=0.39)["verdict"] == "INSUFFICIENT_EVIDENCE"
        assert self.check(setup_valid=False)["verdict"] == "INELIGIBLE"

    def test_boundaries_are_inclusive_where_the_law_says_so(self):
        assert self.check(q_raw=0.50)["eligible"] is True      # ≥ Q_min(1h)
        assert self.check(data_trust=0.30)["eligible"] is True  # ≥ 0.30
        assert self.check(p=0.50, p_min_tf=0.50)["eligible"] is True
        assert self.check(conflict_state="MATERIAL_CONFLICT")["eligible"] is True

    def test_missing_input_fails_closed(self):
        with pytest.raises(DecisionError, match="ELIGIBILITY_INPUT_QX"):
            eligibility({"setup_valid": True})
        with pytest.raises(ValueError, match="E-VAL-022"):
            self.check(timeframe="5s")


class TestRanking:
    def test_candidates_are_generated_for_both_sides(self):
        got = generate_candidates([CAND])
        assert [c["side"] for c in got] == ["LONG", "SHORT"]
        assert all(c["EU"] > 0 for c in got)

    def test_monotonicity_check_runs_before_ranking(self):
        blocked = generate_candidates([dict(CAND, is_risk_increase=True,
                                           uncertainty_is_rising=True)])
        assert blocked == []           # SL-2: refused, never ranked
        allowed = generate_candidates([dict(CAND, is_risk_increase=True,
                                           uncertainty_is_rising=False)])
        assert len(allowed) == 2

    def test_rank_ordering_and_tie_breakers(self):
        a = {"EU": 1.0, "P": 0.6, "C": 0.7, "U_sum": 0.2, "RR": 3.0, "x": "a"}
        b = {"EU": 1.0, "P": 0.7, "C": 0.1, "U_sum": 0.9, "RR": 2.0, "x": "b"}
        c = {"EU": 1.2, "P": 0.1, "C": 0.1, "U_sum": 0.1, "RR": 1.0, "x": "c"}
        assert [r["x"] for r in rank([a, b, c])] == ["c", "b", "a"]
        # equal EU and P → higher C
        d1 = {"EU": 1.0, "P": 0.6, "C": 0.9, "U_sum": 0.2, "RR": 3.0, "x": "d"}
        d2 = {"EU": 1.0, "P": 0.6, "C": 0.5, "U_sum": 0.0, "RR": 1.0, "x": "e"}
        assert [r["x"] for r in rank([d2, d1])] == ["d", "e"]
        # equal EU/P/C → lower U
        e1 = {"EU": 1.0, "P": 0.6, "C": 0.5, "U_sum": 0.4, "RR": 1.0, "x": "u"}
        e2 = {"EU": 1.0, "P": 0.6, "C": 0.5, "U_sum": 0.1, "RR": 3.0, "x": "v"}
        assert [r["x"] for r in rank([e1, e2])] == ["v", "u"]
        # final tie → lower RR
        f1 = {"EU": 1.0, "P": 0.6, "C": 0.5, "U_sum": 0.1, "RR": 3.0, "x": "hi"}
        f2 = {"EU": 1.0, "P": 0.6, "C": 0.5, "U_sum": 0.1, "RR": 1.5, "x": "lo"}
        assert [r["x"] for r in rank([f1, f2])] == ["lo", "hi"]

    def test_selection_is_capped_and_never_bypasses_risk(self):
        cands = [{"EU": float(5 - i), "P": 0.5, "C": 0.5, "U_sum": 0.0,
                  "RR": 2.0, "x": i} for i in range(6)]
        got = select(cands)
        assert len(got["selected"]) == 3
        assert got["max_candidates"] == 3
        assert [s["x"] for s in got["selected"]] == [0, 1, 2]
        assert "Risk Kernel unbypassed" in got["authority_note"]
        assert got["considered"] == 6


class TestArbitration:
    def cand(self, pid, direction, quality, *, family="SF_FVG_SWEEP_REV",
             window=("TREND",), weights=None):
        return {"playbook_id": pid, "family_id": family, "direction": direction,
                "regime_window": list(window),
                "composite_weights": weights or {"quality": 0.4,
                                                 "alignment": 0.3,
                                                 "recency": 0.3},
                "quality": quality, "alignment": 0.5, "recency": 0.5}

    def test_regime_window_is_a_hard_boundary(self):
        assert regime_window_ok(self.cand("pb1", "LONG", 0.9), "TREND") is True
        assert regime_window_ok(self.cand("pb1", "LONG", 0.9), "SHOCK") is False
        with pytest.raises(DecisionError, match="ARBITRATION_WINDOW_QX"):
            regime_window_ok({"playbook_id": "pb1"}, "TREND")

    def test_family_status_gate(self):
        assert INELIGIBLE_FAMILIES == ("DEGRADING", "DEMOTED")
        assert family_status_ok("PROMOTED") is True
        assert family_status_ok("ACCUMULATING") is True
        assert family_status_ok("DEGRADING") is False
        assert family_status_ok("DEMOTED") is False

    def test_composite_rank_alignment_is_capped(self):
        cap = governed_limits()["correlation_cap"]
        got = composite_rank_score(self.cand("pb1", "LONG", 1.0,
                                            weights={"quality": 1.0,
                                                     "alignment": 1.0,
                                                     "recency": 1.0}))
        assert got["correlation_cap"] == cap
        assert got["capped_alignment"] <= 1.0
        over = self.cand("pb1", "LONG", 1.0)
        over["alignment"] = 10.0
        assert composite_rank_score(over)["capped_alignment"] == pytest.approx(1.0)
        with pytest.raises(DecisionError, match="ARBITRATION_WEIGHTS_QX"):
            composite_rank_score({"quality": 1.0})
        with pytest.raises(DecisionError, match="ARBITRATION_WEIGHT_KEYS_QX"):
            composite_rank_score(self.cand("p", "LONG", 1.0,
                                          weights={"quality": 1.0}))

    def test_same_direction_advisory_ranking(self):
        got = arbitrate([self.cand("pb-low", "LONG", 0.4),
                        self.cand("pb-high", "LONG", 0.9)],
                        regime="TREND", family_statuses={})
        assert got["reason"]["decision"] == "TRADE"
        assert got["reason"]["top_candidate"] == "pb-high"
        assert got["reason"]["conflict_type"] == "NONE"
        # ranking only: nothing is allocated here
        assert got["proposal"]["allocates_capital"] is False
        assert got["proposal"]["is_order"] is False

    def test_opposite_direction_defaults_to_no_trade(self):
        got = arbitrate([self.cand("pb-long", "LONG", 0.70),
                        self.cand("pb-short", "SHORT", 0.72)],
                        regime="TREND", family_statuses={})
        assert got["proposal"] is None
        assert got["reason"]["decision"] == NO_TRADE
        assert got["reason"]["conflict_type"] == "OPPOSITE_DIRECTION"
        assert got["reason"]["threshold_check"] == "FAIL"

    def test_governed_threshold_can_resolve_the_conflict(self):
        got = arbitrate([self.cand("pb-long", "LONG", 0.99),
                        self.cand("pb-short", "SHORT", 0.50)],
                        regime="TREND", family_statuses={}, threshold=0.15)
        assert got["reason"]["threshold_check"] == "PASS"
        assert got["proposal"]["direction"] == "LONG"
        # and both directions remain subject to the risk veto downstream
        assert "allocates_capital" in got["proposal"]

    def test_degraded_families_never_become_candidates(self):
        got = arbitrate([self.cand("pb1", "LONG", 0.99)],
                        regime="TREND",
                        family_statuses={"SF_FVG_SWEEP_REV": "DEGRADING"})
        assert got["proposal"] is None
        assert got["reason"]["family_status_filter"] == "1_FAMILIES_EXCLUDED"
        assert got["reason"]["excluded"]["family_status"] == 1

    def test_reason_structure_is_complete_for_every_output(self):
        for cands, statuses in (
            ([], {}),
            ([self.cand("pb1", "LONG", 0.5)], {}),
            ([self.cand("pb1", "LONG", 0.5)], {"SF_FVG_SWEEP_REV": "DEMOTED"}),
        ):
            got = arbitrate(cands, regime="TREND", family_statuses=statuses)
            reason = got["reason"]
            assert set(ARBITRATION_REASON_FIELDS) <= set(reason)
            assert reason["decision"] in ("TRADE", NO_TRADE)
            assert isinstance(reason["top_candidate"], (str, type(None)))
            assert reason["threshold_check"] in ("PASS", "FAIL", "N/A")

    def test_no_trade_is_a_first_class_output(self):
        got = arbitrate([], regime="SHOCK", family_statuses={})
        assert got["proposal"] is None
        assert got["reason"]["decision"] == NO_TRADE
        assert got["reason"]["excluded"]["regime_window"] == 0
        assert got["ranked"] == []


class TestStrategyProposalShape:
    def proposal(self, **over):
        kw = dict(setup_id="setup-1", direction="LONG",
                 entry_logic_ref="EL_SWEEP_RECLAIM_FVG", stop=97.0,
                 targets=(109.0,), p_hat=0.6, u=0.2, c=0.8,
                 conflict_state="CONSENSUS", snapshot_id="a" * 64,
                 r_penalty=0.0, cost_unit=0.02, entry=100.0)
        kw.update(over)
        return build_proposal(**kw)

    def test_fields_are_exactly_the_frozen_portfolio_proposal(self):
        p = self.proposal()
        d = p.to_dict()
        assert set(d) == set(PORTFOLIO_PROPOSAL_FIELDS) | {
            "arbitration_reason", "contract_version"}
        assert d["PUC"] == {"P": 0.6, "U": 0.2, "C": 0.8}
        assert p.PUC["P"] == 0.6
        assert set(PORTFOLIO_PROPOSAL_FIELDS) == {
            "setup_id", "direction", "entry_logic_ref", "stop", "targets",
            "sizing_request", "EU", "PUC", "conflict_state", "snapshot_id"}

    def test_proposal_carries_no_order_authority(self):
        d = self.proposal().to_dict()
        joined = " ".join(sorted(d)).lower()
        for word in ("order", "submit", "cancel", "withdraw", "transfer"):
            assert word not in joined
        # a sizing *request* is not an allocation
        assert d["sizing_request"]["requested"] is True
        assert "leverage" not in d["sizing_request"]

    def test_sizing_request_cannot_carry_execution_fields(self):
        p = self.proposal()
        bad = dict(p.sizing_request, order_type="MARKET")
        with pytest.raises(DecisionError, match="PROPOSAL_AUTHORITY_QX"):
            StrategyProposal(**{**p.__dict__, "sizing_request": bad})

    def test_no_trade_proposal_carries_no_plan(self):
        p = self.proposal(direction=NO_TRADE)
        assert p.stop is None and p.targets == ()
        assert p.EU == -math.inf
        assert p.sizing_request == {"requested": False, "reason": "NO_TRADE"}
        with pytest.raises(DecisionError, match="PROPOSAL_NO_TRADE_QX"):
            StrategyProposal(setup_id="s", direction=NO_TRADE,
                            entry_logic_ref="x", stop=1.0, targets=(2.0,),
                            sizing_request={}, EU=0.0, PUC={},
                            conflict_state="CONSENSUS", snapshot_id="b" * 64)

    def test_direction_domain_is_closed(self):
        with pytest.raises(DecisionError, match="PROPOSAL_DIRECTION_QX"):
            self.proposal(direction="SIDEWAYS")

    def test_snapshot_lineage_is_mandatory(self):
        with pytest.raises(DecisionError, match="PROPOSAL_SNAPSHOT_QX"):
            self.proposal(snapshot_id="")

    def test_proposal_id_is_content_bound(self):
        a, b = self.proposal(), self.proposal()
        assert a.proposal_id == b.proposal_id
        assert a.proposal_id.startswith("sp-")
        other = self.proposal(p_hat=0.55)
        assert other.proposal_id != a.proposal_id


class TestSeamArbitrationNeverImportsExecution:
    """Mission item: the seam test — the arbitration/decision and risk layers
    never import execution (CP-7 owns it); coupling is by record shape only."""

    LAYERS = ("apex/fabric", "apex/pattern", "apex/setup", "apex/playbook",
             "apex/forecast", "apex/decision", "apex/risk")
    FORBIDDEN = ("apex.execution", "apex.ledger", "apex.telegram", "apex.ui",
                 "apex.watchdog", "apex.optimizer")

    def _modules(self):
        root = pathlib.Path("apex")
        for layer in self.LAYERS:
            for path in sorted((root / layer.split("/")[1]).rglob("*.py")):
                if path.name == "__pycache__":
                    continue
                yield path

    def test_no_execution_or_ui_imports(self):
        offenders = []
        for path in self._modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods.add(node.module)
            hits = [m for m in mods
                    if any(m == f or m.startswith(f + ".")
                           for f in self.FORBIDDEN)]
            if hits:
                offenders.append((str(path), sorted(hits)))
        assert offenders == []

    def test_no_network_or_filesystem_write_from_the_chain(self):
        banned = {"socket", "ssl", "http", "urllib", "httpx", "requests",
                 "aiohttp", "subprocess", "shutil"}
        offenders = []
        for path in self._modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            mods = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mods.add(node.module.split(".")[0])
            hits = sorted(mods & banned)
            if hits:
                offenders.append((str(path), hits))
        assert offenders == []

    def test_decision_only_imports_risk_read_helpers_it_owns(self):
        # correlation REDUCE is delegated to the single §8.2 law (no parallel
        # implementation inside the risk kernel)
        src = pathlib.Path("apex/risk/kernel.py").read_text(encoding="utf-8")
        assert "from apex.fabric.conflict import correlation_exposure" in src
        assert "def correlation_exposure" not in src   # no second definition
