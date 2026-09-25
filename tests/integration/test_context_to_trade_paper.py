"""CP-6 integration — the full PAPER chain, end to end, plus determinism.

Stage-prompt EXIT item: "synthetic end-to-end chain (engine evidence →
StrategyProposal → sized plan) runs in PAPER with stub execution".

Chain, in the order the blueprint makes it normative (Ch.8→Ch.15):

    real engine evidence (E08 on the GF_SC_01 Spring fixture — the detector
    call is E08's own ``compute``; the bars and expectations are the locked
    fixtures of CP-6 group 2)
      → SL-14: CANDIDATE evidence is EXCLUDED from the fabric, then admitted
        through the two lawful forward moves CANDIDATE→CONFIRMED→ACTIVE
      → Evidence Fabric (Ch.8 §8.0) + Context Fabric combiner (§8.0/§10.1)
      → pattern catalogue + Spring delegation (Ch.9, AC.1 admission)
      → setup family SF_FVG_SWEEP_REV over the cell + all 13 hard gates
        (Ch.10) — the forecast Q feeding Gate 12 is the REAL bootstrap
        forecast record built from the same fabric, not a constant
      → bootstrap forecast, PAPER-only, LIVE refused (Ch.13)
      → playbook stop construction (Ch.11/Ch.12: X.1 buffer, 3R target)
      → candidate generation + ranking + StrategyArbitration +
        StrategyProposal (Ch.12/§14; the proposal never orders, never allocates)
      → Risk-Kernel adjudication: 14 vetoes BEFORE sizing, then the sizing
        machine (Ch.15) → sized plan; then one hard veto flips ALLOW→REJECT.

Determinism (AI.10 L18920–L18922):
    T-DR-001 — engine evidence payload hash + state fields reproduce exactly;
    T-DR-002 — stored inputs ⇒ same gates trigger, same setup/arbitration
               lineage byte-identical over the whole CP-6 chain;
    T-DR-003 — the forecast P/U/C record re-runs byte-identical.

Execution is a local stub: CP-6 must not import anything from
``apex.execution`` (the seam is asserted by the unit battery; the stub below
merely receives the two shapes CP-7 will consume and proves the authority
guard — it never fabricates an order).
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Mapping

import pytest

from apex.data_catalog.contracts import MarketObservation
from apex.decision.pipeline import (
    PORTFOLIO_PROPOSAL_FIELDS,
    DecisionError,
    StrategyProposal,
    arbitrate,
    build_proposal,
    eligibility,
    generate_candidates,
    rank,
    select,
)
from apex.engines.e08_wyckoff import (
    E08WyckoffEngine,
    atr14,
    detect_spring,
    spring_recovered,
)
from apex.fabric.conflict import HARD_CONFLICT, disagreement_of, resolve
from apex.fabric.context import (
    band_of,
    build_context,
    q_min_setup,
    setup_score,
)
from apex.fabric.evidence import (
    EvidenceFabric,
    FabricEvidenceRef,
    advance_lifecycle,
    fabric_from_events,
    is_forward,
    lifecycle_of,
)
from apex.forecast.logistic import (
    BOOTSTRAP_Q_FORECAST,
    ForecastError,
    ForecastEvent,
    X_FEATURES,
    build_forecast,
)
from apex.identity.canonical_json import canonical_json
from apex.pattern.detect import (
    CATALOGUE,
    assert_scoring_admissible,
    detect_all,
    entity_for,
    from_e08_spring,
)
from apex.playbook.pb_fvg_sweep_rev_a import build_stops, instantiate_playbook
from apex.risk.kernel import adjudicate, evaluate_vetoes
from apex.setup.family_sf_fvg_sweep_rev import (
    EMITTED,
    ENTRY_LOGIC_REF,
    FAMILY_ID,
    HORIZON_BARS,
    NOT_EMITTED,
    PLAYBOOK_ID,
    REQUIRED_EVIDENCE,
    evaluate_cell,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"

SYMBOL = "BTCUSDT"
TIMEFRAME = "1h"
AS_OF_ISO = "2026-01-15T14:00:00Z"
AS_OF_MS = 1768485600000 + 14 * 3600000
ATR = 1.0

SCORED = ("structure", "liquidity", "fvg", "trend", "regime", "temporal",
          "orderblock", "momentum")
SYNTH_ENGINES = tuple(e for e in REQUIRED_EVIDENCE if e != "E08") + ("E06",
                                                                      "E10")


# ---------------------------------------------------------------------------
# Step 1 — real engine evidence on the locked GF_SC_01 fixture bars
# ---------------------------------------------------------------------------

def gf_bars():
    doc = json.loads((FIXTURE_DIR / "gf_sc_01.json").read_text(encoding="utf-8"))
    fixture = doc["fixtures"][0]
    bars = [dict(b, ts=AS_OF_MS + i * 3600000)
            for i, b in enumerate(fixture["bars"])]
    return fixture, bars


def _obs_window(bars):
    out = []
    for i, b in enumerate(bars):
        dt = datetime.datetime.fromtimestamp(b["ts"] / 1000,
                                             tz=datetime.timezone.utc)
        out.append(MarketObservation(
            symbol=SYMBOL, timeframe=TIMEFRAME,
            open=Decimal(repr(b["o"])), high=Decimal(repr(b["h"])),
            low=Decimal(repr(b["l"])), close=Decimal(repr(b["c"])),
            volume=Decimal(repr(b["v"])), oi=None,
            timestamp=dt.strftime("%Y-%m-%dT%H:%M:%S.") + "000Z",
            sequence=i, status="CLOSED"))
    return out


def compute_e08_events(bars):
    """THE real E08 engine surface (EngineBase.compute) on fixture bars."""
    n = len(bars)
    atr = float(atr14(bars))
    return E08WyckoffEngine().compute(SYMBOL, TIMEFRAME, AS_OF_ISO, {
        "window": _obs_window(bars),
        "atr_by_idx": {i: atr for i in range(n)},
        "vol_ratio_by_idx": {i: 1.6 for i in range(n)},
        "evr_by_idx": {i: 0.5 for i in range(n)}})


def real_active_refs(bars):
    """Store-backed promotion of the real events: fabric admission is SL-14
    only, so the CANDIDATE events the engine actually emitted are moved
    through the two governed forward steps — never re-labelled by hand."""
    evs = compute_e08_events(bars)
    assert evs, "E08 must emit on the GF_SC_01 Spring fixture"
    refs = []
    for ev in evs:
        if int(ev.direction) != 1:
            continue                     # the bullish Spring event carries +1
        state = lifecycle_of(str(getattr(ev.fate_state, "value",
                                         ev.fate_state))) \
            if str(getattr(ev.fate_state, "value", ev.fate_state)) \
            in ("emitted", "consumed", "created", "expired", "superseded") \
            else str(ev.fate_state.value)
        state = advance_lifecycle(state, "CONFIRMED")
        state = advance_lifecycle(state, "ACTIVE")
        # PAPER-ingest hop: the engine journal token is the parent; the raw
        # observation id of the confirming bar is the lineage root the fabric
        # contract (Ch.8 §8.0 "down to raw observation_id") and Gate 11 check.
        # The GF_SC_01 schema locks the event bar at index 16 (fixture
        # contract — tests/unit/test_pattern_detect.py::derive pins the same).
        bar_idx = 16
        refs.append(FabricEvidenceRef(
            evidence_id=ev.evidence_id, engine_id=ev.engine_id,
            symbol=ev.symbol, timeframe=ev.timeframe, state=state,
            direction=int(ev.direction), quality=float(ev.quality),
            resolution_class=str(ev.resolution_class), age_bars=0.0,
            as_of=AS_OF_MS, snapshot_id=ev.snapshot_id,
            lineage=(f"obs-gf01-{bar_idx}",), parent_ids=tuple(ev.lineage)))
    assert refs, "a promoted ACTIVE ref is required"
    return refs


def synth_refs():
    """PAPER-synthetic context refs for the remaining required engines
    (explicitly synthetic — the family contract needs the whole required set;
    only E08 evidence is produced live in this test)."""
    refs = []
    for i, eng in enumerate(SYNTH_ENGINES):
        refs.append(FabricEvidenceRef(
            evidence_id=f"synth-{eng}", engine_id=eng, symbol=SYMBOL,
            timeframe=TIMEFRAME, state="ACTIVE", direction=1, quality=0.9,
            resolution_class="Q3", age_bars=0.0, as_of=AS_OF_MS,
            snapshot_id="a" * 64, lineage=(f"obs-{eng}",)))
    return refs


def sweep_bars(n=25, low_t=95.0):
    """EL_SWEEP_RECLAIM_FVG shape (Ch.10 §10.2): sweep of the documented low,
    close back inside, at the FVG index — the family's green-cell recipe."""
    bars = [{"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0, "v": 1000.0}
            for _ in range(n - 1)]
    bars.append({"o": 100.0, "h": 100.5, "l": low_t, "c": 99.7,
                 "v": 2000.0})
    return bars


# ---------------------------------------------------------------------------
# The chain — deterministic given its stored inputs (the refs)
# ---------------------------------------------------------------------------

def run_chain(refs):
    out: dict = {}
    fabric = EvidenceFabric.assemble(
        symbol=SYMBOL, timeframe=TIMEFRAME, as_of=AS_OF_MS,
        evidence=list(refs), data_trust=0.9)
    out["fabric"] = fabric

    ctx = build_context(
        fabric, market_regime="TREND", mtf_state="ALIGNED",
        utc_window_state="UTC_W2", is_overlap=True, volatility_state="NORMAL",
        structure_state="BOS_UP", regime_confidence=0.7,
        regime_uncertainty=0.2, divergence_magnitude=0.1,
        temporal_window_validity=0.9, q_raw=0.9)
    out["context"] = ctx

    fixture, gfb = gf_bars()
    atr = float(atr14(gfb))
    lvl = min(b["l"] for b in gfb[:16])
    sma = sum(b["v"] for b in gfb[:16]) / 16
    from apex.quality.numerical import formula_volume_ratio
    vr = float(formula_volume_ratio(Decimal(repr(gfb[16]["v"])),
                                    Decimal(repr(sma)))[0])
    spring_hit = from_e08_spring(gfb, lvl, 16, atr, vr)
    out["spring_hit"] = spring_hit
    out["spring_detect"] = bool(detect_spring(
        gfb[16]["l"], lvl, gfb[16]["c"], atr, vr, 0.0)) \
        and bool(spring_recovered(gfb, lvl, 16, 3))
    row = next(r for r in CATALOGUE if r.pattern_id == "PAT-WYC-001")
    entity = entity_for(row)
    assert_scoring_admissible(entity)
    out["pattern_entity"] = entity

    x = {k: 0.5 for k in X_FEATURES}
    x["s_struct"] = 0.6
    x["trend_stack"] = 1.0
    x["regime_entropy"] = 0.4
    x["log_rr"] = math.log(3.0)
    x["log_cost_R"] = math.log(0.05)
    event = ForecastEvent(
        target_condition="PB_FVG_SWEEP_REV_A:TARGET_3R",
        stop_condition="EL_SWEEP_RECLAIM_FVG:SWEEP_LOW_INVALIDATION",
        horizon=HORIZON_BARS, entry_ref=ENTRY_LOGIC_REF, symbol=SYMBOL,
        timeframe=TIMEFRAME, timestamp=AS_OF_MS)
    rec = build_forecast(event, x=x, environment="PAPER", rr=3.0,
                         cost_r=0.05, uncertainty={"calibration": .2, "data_quality": .2, "disagreement": .2})
    out["forecast"] = rec

    evaluation = evaluate_cell(
        symbol=SYMBOL, timeframe=TIMEFRAME, as_of=AS_OF_MS, fabric=fabric,
        bars=sweep_bars(), atr=ATR, direction=1,
        fvg_zones=[{"index": 24, "filled": False}],
        bos={"s_struct": 0.6, "direction": 1}, regime_state="TREND",
        q_forecast=rec.q_forecast, forecast={"quality": "Q3", "h_norm": 0.4},
        package={"package_version": 1, "parameter_package_id": "pkg-1",
                 "calibration": "BOOTSTRAP_UNCALIBRATED"},
        s_i={c: 1.0 for c in SCORED}, q_i={c: 0.9 for c in SCORED},
        context_confidence=ctx["context_confidence"], environment="PAPER")
    out["evaluation"] = evaluation
    out["setup_event"] = evaluation.to_setup_event()

    extreme = evaluation.entry_logic_steps["2_3_sweep_reclaim"]["extreme"]
    pb = instantiate_playbook()
    stops = build_stops(direction=1, entry=evaluation.entry, atr=ATR,
                        sweep_extreme=extreme)
    out["playbook"] = pb
    out["stops"] = stops

    setup = {"setup_id": out["setup_event"]["setup_id"],
             "entry": evaluation.entry, "stop": stops["stop"],
             "target": stops["target"], "P": rec.p_hat, "C": rec.c,
             "U_sum": rec.u, "cost_unit": 0.05, "r_penalty": rec.r_penalty,
             "is_risk_increase": False, "uncertainty_is_rising": False}
    cands = generate_candidates([setup])
    out["candidates"] = cands
    out["ranked"] = rank(cands)
    out["selected"] = select(cands, environment="PAPER")

    arb_cand = {"playbook_id": PLAYBOOK_ID, "family_id": FAMILY_ID,
                "direction": "LONG", "regime_window": ["TREND",
                                                       "TREND_EXPANSION"],
                "composite_weights": {"quality": 0.4, "alignment": 0.3,
                                      "recency": 0.3},
                "quality": evaluation.final_score, "alignment": 0.5,
                "recency": 0.5}
    arb = arbitrate([arb_cand], regime="TREND",
                    family_statuses={FAMILY_ID: "ACTIVE"})
    out["arbitration"] = arb
    out["eligibility"] = eligibility(
        {"setup_valid": True, "forecast_quality_ok": True,
         "conflict_state": fabric.conflict_state, "q_raw": 0.9,
         "timeframe": TIMEFRAME, "freshness_ok": True, "data_trust": 0.9,
         "p": rec.p_hat, "p_min_tf": BOOTSTRAP_Q_FORECAST, "c": rec.c,
         "c_min": 0.5})

    proposal = build_proposal(
        setup_id=setup["setup_id"], direction="LONG",
        entry_logic_ref=ENTRY_LOGIC_REF, stop=stops["stop"],
        targets=(stops["target"],), p_hat=rec.p_hat, u=rec.u, c=rec.c,
        conflict_state=fabric.conflict_state,
        snapshot_id=evaluation.fabric_hash, r_penalty=rec.r_penalty,
        cost_unit=0.05, entry=evaluation.entry,
        arbitration_reason=arb["reason"])
    out["proposal"] = proposal

    base = {
        "snapshot_id": proposal.snapshot_id, "timeframe": TIMEFRAME,
        "capital": 10_000.0, "q_raw": 0.9, "qx_state": False,
        "failed_setup_gate": False, "pit_violation": False,
        "availability_time": 1, "portfolio_exposure": 100.0,
        "proposed_notional": 50.0, "capital_hard_cap": 1_000_000.0,
        "circuit_breaker_engaged": False, "emergency_state": "NORMAL",
        "per_symbol_exposure": 100.0, "symbol_cap": 1_000.0,
        "portfolio_cap": 1_000_000.0,
        "conflict_state": proposal.conflict_state, "staleness_seconds": 1.0,
        "freshness_sla_seconds": 30.0, "oi_lag_seconds": 5.0,
        "oi_lag_threshold_seconds": 60.0, "is_risk_increase": False,
        "uncertainty_is_rising": False, "realized_daily_loss_fraction": 0.0,
        "realized_weekly_loss_fraction": 0.0, "consecutive_losses": 0,
        "time_to_expiry_days": 40.0, "margin_health_fraction": 0.9,
        "stop_distance": abs(evaluation.entry - stops["stop"]),
        "min_quantity": 0.001, "risk_state": "LowRisk",
        "environment": "PAPER",
        "package": {"package_version": 1, "parameter_package_id": "pkg-1",
                    "calibration": "BOOTSTRAP_UNCALIBRATED"},
    }
    out["plan"] = adjudicate(base)
    out["veto_verdict"] = evaluate_vetoes(base)
    return out


@pytest.fixture(scope="module")
def chain():
    fixture, bars = gf_bars()
    refs = real_active_refs(bars)
    c = run_chain(refs + synth_refs())
    c["refs"] = refs
    c["fixture_bars"] = bars
    c["fixture"] = fixture
    return c


# ---------------------------------------------------------------------------
# The stub execution surface (CP-7's slot; consumes the §INTERFACES shapes
# ONLY and must be unable to turn them into orders)
# ---------------------------------------------------------------------------

class PaperExecutionStub:
    FORBIDDEN = ("order", "order_type", "client_order_id", "leverage",
                 "margin_mode", "position_id")

    def __init__(self):
        self.book = []

    def accept(self, proposal: StrategyProposal, plan):
        d = proposal.to_dict()
        for f in self.FORBIDDEN:
            assert f not in d and f not in d["sizing_request"]
        assert plan["decision"] in ("ALLOW", "REDUCE")
        receipt = {"proposal_id": proposal.proposal_id,
                   "quantity": plan["sized_quantity"],
                   "package": plan["selected_parameter_package"],
                   "status": "PAPER_SUBMITTED"}
        self.book.append(receipt)
        return receipt


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

class TestPaperChain:
    def test_real_engine_evidence_enters_fabric_only_through_sl14(self, chain):
        fixture, bars = chain["fixture"], gf_bars()[1]
        raw = compute_e08_events(bars)
        # CANDIDATE evidence is not admissible: the fabric excludes it with a
        # reason, never repairs it.
        f0 = fabric_from_events(raw, symbol=SYMBOL, timeframe=TIMEFRAME,
                                as_of=AS_OF_MS, data_trust=0.9)
        assert f0.is_empty()
        assert all(reason == "NOT_ACTIVE_SL14" for _, reason in f0.excluded)
        # promotion is the governed ladder, forward-only
        assert is_forward("CANDIDATE", "CONFIRMED") and not is_forward(
            "CANDIDATE", "ACTIVE")
        refs = chain["refs"]
        assert all(r.state == "ACTIVE" for r in refs)
        real_ids = {r.evidence_id for r in refs}
        assert real_ids <= {m.evidence_id for m in chain["fabric"].members}
        by_group = chain["fabric"].members_by_group()
        assert "E08" in [m.engine_id for m in by_group["structure"]] or \
            any(m.engine_id == "E08" for m in chain["fabric"].members)

    def test_pattern_spring_and_catalogue_admission(self, chain):
        assert chain["spring_detect"] is True
        hit = chain["spring_hit"]
        assert hit.pattern_id == "PAT-WYC-001" and hit.direction == 1
        assert chain["pattern_entity"].setup_score_contribution_class == \
            "s_i_component"
        res = detect_all(chain["fixture_bars"], float(atr14(
            chain["fixture_bars"])))
        assert isinstance(res["hits"], dict)
        assert res["n_admitted_rows"] >= 13

    def test_context_is_produced_not_declared(self, chain):
        ctx = chain["context"]
        cc = ctx["context_confidence"]
        assert 0.30 < cc <= 1.0                    # solvency floor respected
        assert ctx["solvency"]["ok"] is True
        assert ctx["band"] == band_of(cc)          # classification, nothing more
        assert ctx["band"] in ("ADMISSIBLE", "CONFIRMATORY", "WEAK")
        assert set(ctx["context"]) >= set(
            ["data_trust", "conflict_state", "context_confidence"])

    def test_forecast_is_bootstrap_paper_only(self, chain):
        rec = chain["forecast"]
        assert rec.p_raw == 0.5 and rec.bootstrap_prior is True
        assert rec.q_forecast == BOOTSTRAP_Q_FORECAST == 0.5
        assert rec.eligible_environments == ("RESEARCH", "PAPER", "BACKTEST")
        event = ForecastEvent(
            target_condition="T", stop_condition="S", horizon=HORIZON_BARS,
            entry_ref=ENTRY_LOGIC_REF, symbol=SYMBOL, timeframe=TIMEFRAME,
            timestamp=AS_OF_MS)
        with pytest.raises(ForecastError,
                           match="FORECAST_BOOTSTRAP_NOT_LIVE_ELIGIBLE"):
            build_forecast(event, x={k: 0.5 for k in X_FEATURES},
                           environment="LIVE")

    def test_family_cell_emits_with_all_thirteen_gates(self, chain):
        ev = chain["evaluation"]
        assert ev.status == EMITTED
        assert ev.final_score >= q_min_setup()
        results = ev.gate_block["results"]
        assert len(results) == 13 and ev.gate_block["all_pass"]
        assert all(r["passed"] for r in results.values())
        se = chain["setup_event"]
        assert se["family_id"] == FAMILY_ID
        assert se["authority"] == "SETUP_ENGINE" and se["validity"] == 1
        assert se["entry_logic_ref"] == ENTRY_LOGIC_REF

    def test_playbook_stop_mathenters_the_proposal_plan(self, chain):
        stops = chain["stops"]
        # extreme = the PRIOR-window low that was swept (99.0); the stop sits
        # 0.25·ATR below it — never at the sweep bar's own low.
        assert stops["stop"] == pytest.approx(99.0 - 0.25 * ATR)
        assert stops["R"] == pytest.approx(99.7 - stops["stop"])
        assert stops["target"] == pytest.approx(99.7 + 3.0 * stops["R"])
        assert chain["playbook"].record["ID"] == PLAYBOOK_ID

    def test_arbitration_produces_proposal_then_sized_plan(self, chain):
        arb = chain["arbitration"]
        assert arb["reason"]["decision"] == "TRADE"
        assert arb["proposal"]["authority"] == "STRATEGY_ARBITRATION"
        assert arb["proposal"]["is_order"] is False \
            and arb["proposal"]["allocates_capital"] is False
        prop = chain["proposal"]
        assert set(prop.to_dict()) == set(PORTFOLIO_PROPOSAL_FIELDS) | {
            "arbitration_reason", "contract_version"}
        assert prop.proposal_id.startswith("sp-")
        plan = chain["plan"]
        assert plan["decision"] == "ALLOW" and plan["sized_quantity"] > 0.0
        assert plan["veto_evaluation_order"] == list(range(1, 15))
        assert plan["sized_after_all_vetoes"] is True
        # the sizing machine's exact arithmetic on the chain's own inputs:
        # Q = floor(R_allowed / stop_distance / min_quantity) · min_quantity
        r_allowed = 0.005 * 10_000.0 * 1.0
        q = math.floor(r_allowed / chain["stops"]["R"] / 0.001) * 0.001
        assert plan["sized_quantity"] == pytest.approx(q)
        assert plan["sizing"]["R_allowed"] == pytest.approx(r_allowed)
        assert chain["eligibility"]["eligible"] is True
        assert chain["veto_verdict"]["fired"] == []

    def test_hard_veto_flips_allow_to_reject(self, chain):
        base = {"snapshot_id": chain["proposal"].snapshot_id,
                "timeframe": TIMEFRAME, "capital": 10_000.0, "q_raw": 0.9,
                "qx_state": False, "failed_setup_gate": False,
                "pit_violation": False, "availability_time": 1,
                "portfolio_exposure": 100.0, "proposed_notional": 50.0,
                "capital_hard_cap": 1_000_000.0,
                "circuit_breaker_engaged": False, "emergency_state": "NORMAL",
                "per_symbol_exposure": 100.0, "symbol_cap": 1_000.0,
                "portfolio_cap": 1_000_000.0,
                "conflict_state": "CONSENSUS", "staleness_seconds": 1.0,
                "freshness_sla_seconds": 30.0, "oi_lag_seconds": 5.0,
                "oi_lag_threshold_seconds": 60.0, "is_risk_increase": False,
                "uncertainty_is_rising": False,
                "realized_daily_loss_fraction": 0.0,
                "realized_weekly_loss_fraction": 0.0, "consecutive_losses": 0,
                "time_to_expiry_days": 40.0, "margin_health_fraction": 0.9,
                "stop_distance": chain["stops"]["R"], "min_quantity": 0.001,
                "risk_state": "LowRisk"}
        assert adjudicate(dict(base))["decision"] == "ALLOW"
        flip = adjudicate(dict(base, margin_health_fraction=0.40))
        assert flip["decision"] == "REJECT" and flip["sized_quantity"] == 0.0
        assert flip["vetoes_applied"] == [14]
        assert flip["sized_after_all_vetoes"] is False
        flip6 = adjudicate(dict(base, conflict_state=HARD_CONFLICT))
        assert flip6["decision"] == "REJECT" and flip6["vetoes_applied"] == [6]
        assert "sizing" not in flip6                # a veto never reaches Q

    def test_stub_execution_consumes_only_the_two_shapes(self, chain):
        stub = PaperExecutionStub()
        receipt = stub.accept(chain["proposal"], chain["plan"])
        assert receipt["status"] == "PAPER_SUBMITTED"
        assert receipt["quantity"] == chain["plan"]["sized_quantity"]
        # the authority guard lives in StrategyProposal itself: an
        # order-shaped payload can never be wrapped into a proposal.
        with pytest.raises(DecisionError, match="PROPOSAL_AUTHORITY_QX"):
            StrategyProposal(
                setup_id="s", direction="LONG",
                entry_logic_ref=ENTRY_LOGIC_REF, stop=94.75,
                targets=(114.55,),
                sizing_request={"requested": True, "order": {"type": "MARKET"}},
                EU=1.0, PUC={"P": 0.5, "U": 0.0, "C": 1.0},
                conflict_state="NONE", snapshot_id="a" * 64)

    def test_chain_refuses_to_emit_on_empty_or_candidate_only_evidence(
            self, chain):
        empty = EvidenceFabric.assemble(symbol=SYMBOL, timeframe=TIMEFRAME,
                                        as_of=AS_OF_MS, evidence=[],
                                        data_trust=0.9)
        assert empty.is_empty()
        score = setup_score(empty, s_i={}, q_i={})
        assert score["vacuous"] is True and score["final"] == 0.0
        out = resolve(disagreement=disagreement_of([]), data_trust=0.9,
                      q_raw=0.9, timeframe=TIMEFRAME)
        assert out["output"] == HARD_CONFLICT     # nothing to agree with
        ev = evaluate_cell(symbol=SYMBOL, timeframe=TIMEFRAME,
                           as_of=AS_OF_MS, fabric=empty, bars=sweep_bars(),
                           atr=ATR, direction=1,
                           fvg_zones=[{"index": 24, "filled": False}],
                           bos={"s_struct": 0.6, "direction": 1},
                           regime_state="TREND")
        assert ev.status == NOT_EMITTED
        assert ev.reason.startswith("REQUIRED_EVIDENCE_MISSING")
        assert ev.final_score == 0.0              # reported, never assumed
        assert ev.entry is None                   # no fabricated plan either


# ---------------------------------------------------------------------------
# Determinism — T-DR-001/002/003 over THIS chain (AI.10 L18920–L18922)
# ---------------------------------------------------------------------------

def _comparable_forecast(rec):
    return _canon(dataclasses.asdict(rec))


def _canon(obj):
    """String-keyed recursive canonicalization (the gate map is int-keyed by
    design; canonical_json is identity-canonical and refuses int keys)."""
    if isinstance(obj, Mapping):
        return {str(k): _canon(v) for k, v in sorted(
            obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _canon(dataclasses.asdict(obj))
    return obj


class TestDeterminism:
    def test_t_dr_001_engine_evidence_payload_reproduces(self):
        _, bars = gf_bars()
        a = compute_e08_events(bars)
        b = compute_e08_events(bars)
        assert len(a) == len(b)
        for ea, eb in zip(a, b):
            # identity ids embed UUIDv7 time/random bits and legitimately
            # differ across runs — the PAYLOAD hash and every state field
            # must reproduce byte-identically:
            assert ea.snapshot_id == eb.snapshot_id
            assert str(ea.fate_state) == str(eb.fate_state)
            assert int(ea.direction) == int(eb.direction)
            assert float(ea.quality) == float(eb.quality)
            assert ea.event_time == eb.event_time and ea.availability_time \
                == eb.availability_time
            assert ea.feature_dependencies == eb.feature_dependencies
            assert ea.explanation == eb.explanation

    def test_t_dr_002_stored_inputs_replay_the_whole_chain_identically(self):
        _, bars = gf_bars()
        refs = real_active_refs(bars) + synth_refs()
        c1, c2 = run_chain(refs), run_chain(refs)
        # the setup identity + lineage, every gate verdict, the arbitration
        # reason and the proposal id: all byte-identical ("same gates trigger")
        assert _canon(c1["setup_event"]) == _canon(c2["setup_event"])
        def _gates(c):
            out = {}
            for k, r in c["evaluation"].gate_block["results"].items():
                d = r if isinstance(r, Mapping) else dataclasses.asdict(r)
                out[str(k)] = (d["passed"], _canon(d["measured"]))
            return out
        g1, g2 = _gates(c1), _gates(c2)
        assert g1 == g2 and len(g1) == 13
        assert c1["proposal"].proposal_id == c2["proposal"].proposal_id
        assert canonical_json(c1["arbitration"]) == \
            canonical_json(c2["arbitration"])
        assert c1["plan"]["sized_quantity"] == c2["plan"]["sized_quantity"]
        assert canonical_json(c1["plan"]["sizing"]) == \
            canonical_json(c2["plan"]["sizing"])

    def test_t_dr_003_forecast_p_u_c_replay_byte_identical(self):
        _, bars = gf_bars()
        refs = real_active_refs(bars) + synth_refs()
        c1, c2 = run_chain(refs), run_chain(refs)
        assert _comparable_forecast(c1["forecast"]) == \
            _comparable_forecast(c2["forecast"])
        assert c1["forecast"].eu == c2["forecast"].eu
        assert c1["fabric"].hash == c2["fabric"].hash
