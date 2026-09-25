"""CP-9-006 plan bridge contract tests.

The integration battery drives the full real fixture. These focused tests pin
its fail-closed source seam: raw store data is not upgraded to engine context,
reduced evidence rows are not promoted to ACTIVE, and non-PAPER environments
never receive a bridge plan.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from apex.ops.plan_bridge import PaperPlanBridge


AS_OF = "2026-01-01T01:00:00.000Z"


def _complete_context(*, events: Any) -> Dict[str, Any]:
    components = ("structure", "liquidity", "fvg", "trend", "regime",
                  "temporal")
    return {
        "events": events, "data_trust": 0.9, "q_raw": 0.9,
        "market_regime": "TREND", "mtf_state": "ALIGNED",
        "utc_window_state": "UTC_W2", "is_overlap": True,
        "volatility_state": "NORMAL", "structure_state": "BOS_UP",
        "regime_confidence": 0.7, "regime_uncertainty": 0.2,
        "divergence_magnitude": 0.1, "temporal_window_validity": 0.9,
        "atr": 1.0, "fvg_zones": [{"index": 0, "filled": False}],
        "bos": {"s_struct": 0.6, "direction": 1},
        "regime_state": "TREND",
        "e11_context": {
            "ic_inputs": {"trendiness_raw": 0.7},
            "history_windows": {"trend": [0.5]},
            "classifier_W": [[0.0] * 8 for _ in range(9)],
            "classifier_b": [0.0] * 9, "regime_state": "TREND",
        },
        "direction": 1, "pattern_id": "PAT-WYC-001", "x": {"s_struct": 0.5},
        "forecast_quality": "Q3", "forecast_rr": 3.0,
        "forecast_uncertainty": {"calibration": .2, "data_quality": .2, "disagreement": .2},
        "forecast_cost_r": 0.05, "h_norm": 0.4,
        "window_qualities": [(1.0, 0.0)],
        "temporal_quality": "Q2", "volatility_quality": "Q2",
        "s_i": {key: 1.0 for key in components},
        "q_i": {key: 0.9 for key in components},
        "package": {"package_version": 1, "parameter_package_id": "pkg-1",
                    "rolling_calibration_error": 0.0, "brier": 0.0, "log_loss": 0.0},
        "p_min_tf": 0.5, "c_min": 0.5, "freshness_ok": True,
        "risk_state": "LowRisk", "family_status": "ACTIVE",
        "arbitration": {}, "risk": {},
    }


def test_non_paper_environment_is_a_named_refusal():
    async def scenario():
        bridge = PaperPlanBridge(
            store=object(), environment="LIVE",
            context_source=lambda *_: _complete_context(events=[]))
        assert await bridge("BTCUSDT", "1h", AS_OF) is None
        assert bridge.refusals["BTCUSDT:1h"]["reason"] == "PAPER_ONLY_EXECUTION"

    asyncio.run(scenario())


def test_raw_store_without_governed_context_never_mints_a_plan():
    class RawOnlyStore:
        async def get_window(self, symbol, timeframe, as_of, bars):
            return []

    async def scenario():
        bridge = PaperPlanBridge(store=RawOnlyStore())
        assert await bridge("BTCUSDT", "1h", AS_OF) is None
        assert bridge.refusals["BTCUSDT:1h"]["reason"] == "ENGINE_CONTEXT_UNAVAILABLE"

    asyncio.run(scenario())


def test_reduced_evidence_row_is_not_promoted_to_active():
    # This resembles the frozen evidence_event DDL row but intentionally lacks
    # direction, lifecycle and age. A bridge must reject it rather than infer
    # the missing values from a raw bar or from the row's engine id.
    reduced_row = {
        "evidence_id": "ev-reduced", "engine_id": "E01",
        "resolution_class": "Q3", "quality": 0.9,
        "snapshot_id": "snap-1", "lineage": ("obs-1",),
        "availability_time": AS_OF,
    }

    async def scenario():
        bridge = PaperPlanBridge(
            store=object(),
            context_source=lambda *_: _complete_context(events=[reduced_row]))
        assert await bridge("BTCUSDT", "1h", AS_OF) is None
        refusal = bridge.refusals["BTCUSDT:1h"]
        assert refusal["reason"] == "PERSISTED_EVIDENCE_INCOMPLETE"
        assert "direction" in refusal["detail"]

    asyncio.run(scenario())


def test_full_e11_state_label_projection_preserves_payload_and_legacy_source():
    from apex.ops.plan_bridge import _regime_label
    from apex.identity.canonical_json import canonical_json
    state = {"state": "TRANSITION", "state_raw": "AMBIGUOUS",
             "entropy": 2.1, "probs": {"TRANSITION": .6, "RANGE": .4},
             "snapshot_id": "fixture-native-object-shape"}
    before = canonical_json(state)
    assert _regime_label(state) == "TRANSITION"
    assert canonical_json(state) == before
    assert _regime_label("TREND") == "TREND"


def test_regime_label_projection_never_stringifies_missing_or_invalid_state():
    import pytest
    from apex.ops.plan_bridge import BridgeError, _regime_label
    for value in ({}, {"state_raw": "TREND"}, {"state": None}, {"state": ""}, 1, None):
        with pytest.raises(BridgeError, match="E11_CONTEXT_INVALID"):
            _regime_label(value)
