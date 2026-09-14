"""CP-8 — AI.10 NFR harness (``scripts/run_nfr_harness.py``): T-NFR-004 is an
asserted in-process law (2000 P0 delivered, P2 evicted under lane pressure,
lane never exceeding the governed 1000); T-NFR-001..003 are measured and
labelled SANDBOX-PARTIAL / OWNER-VERIFY so no target-device result is ever
claimed (AI.10 rule 5 / AI.13)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_nfr_harness.py"


def _load():
    spec = importlib.util.spec_from_file_location("cp8_nfr_harness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _load()


@pytest.fixture(scope="module")
def report(harness):
    return harness.run_harness(decisions=10, orders=5, minutes=0.0)


class TestBounds:
    def test_ai7_bounds_are_the_blueprint_values(self, harness):
        assert harness.ANALYSIS_P95_MS == 400.0
        assert harness.SUBMISSION_P95_MS == 200.0
        assert harness.CPU_PERCENT_MAX == 20.0
        assert harness.MEMORY_MB_MAX == 400.0

    def test_percentile_is_nearest_rank(self, harness):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert harness.percentile(values, 0.95) == 10.0
        assert harness.percentile(values, 0.50) == pytest.approx(5.0)
        assert harness.percentile([3.0], 0.95) == 3.0

    def test_empty_sample_is_refused(self, harness):
        with pytest.raises(ValueError):
            harness.percentile([], 0.95)


class TestTNFR004QueueBounds:
    def test_all_p0_delivered_and_p2_evicted(self, report):
        queue = report["t_nfr_004"]
        assert queue["p0_delivered"] == 2000
        assert queue["all_p0_processed"] is True
        assert queue["p2_published"] == 1000
        assert queue["some_p2_evicted"] is True
        assert queue["p2_evicted"] > 0
        assert queue["eviction_reason"] == "QUEUE_OVERFLOW_DROP"

    def test_the_shared_lane_never_exceeds_its_governed_bound(self, report):
        queue = report["t_nfr_004"]
        assert queue["bounded"] is True
        assert queue["lane_qsize"] <= 1000

    def test_p0_delivery_is_synchronous_not_buffered(self, harness):
        import asyncio

        from apex.bus import EventBus, Priority, make_event

        bus = EventBus()
        seen = []

        async def consumer(event):
            seen.append(event.payload["i"])

        bus.subscribe("t", consumer)

        async def _flow():
            for i in range(5):
                await bus.publish(make_event(Priority.P0, "t", {"i": i}))
            # no dispatcher was ever started: P0 must already be delivered
            return bus.counts["p0_delivered"]

        assert asyncio.run(_flow()) == 5
        assert seen == [0, 1, 2, 3, 4]


class TestHonestLabels:
    def test_latency_probes_are_labelled_sandbox_partial(self, report):
        assert report["t_nfr_001"]["label"] == "SANDBOX-PARTIAL"
        assert report["t_nfr_002"]["label"] == "SANDBOX-PARTIAL"
        assert "30 % headroom" in report["t_nfr_001"]["owner_gate"]

    def test_resource_sample_can_never_be_read_as_acceptance(self, report):
        assert report["t_nfr_003"]["label"] == "OWNER-VERIFY"
        assert "60-minute run" in report["t_nfr_003"]["owner_gate"]
        assert "idle sample is not the acceptance measurement" in \
            report["t_nfr_003"]["note"]

    def test_the_report_never_claims_a_target_device_result(self, report):
        assert "NOT target-device acceptance" in report["note"]
        assert report["owner_gates_open"] == [
            "T-NFR-001 target device (30 % headroom)",
            "T-NFR-002 target device (30 % headroom)",
            "T-NFR-003 target device 60-minute run",
            "T-TOOBIT-001 depth > 500k USDT per symbol",
            "T-TOOBIT-002 venue rate ≤ 100 req/s"]

    def test_measured_latencies_are_recorded_with_their_bounds(self, report):
        for key in ("t_nfr_001", "t_nfr_002"):
            probe = report[key]
            assert probe["samples"] > 0
            assert probe["p95_ms"] > 0.0
            assert probe["within_bound"] is (probe["p95_ms"] <= probe["bound_ms"])


class TestExitCodes:
    def test_zero_when_in_bounds(self, harness, monkeypatch):
        monkeypatch.setattr(harness, "run_harness",
                            lambda **kwargs: {"measured_in_bounds": True,
                                              "t_nfr_004": {
                                                  "p0_delivered": 2000,
                                                  "p0_expected": 2000,
                                                  "all_p0_processed": True,
                                                  "some_p2_evicted": True,
                                                  "p2_evicted": 1,
                                                  "eviction_reason":
                                                      "QUEUE_OVERFLOW_DROP"},
                                              "t_nfr_001": {"p95_ms": 1.0,
                                                            "bound_ms": 400.0,
                                                            "within_bound": True,
                                                            "label": "SANDBOX-PARTIAL"},
                                              "t_nfr_002": {"p95_ms": 1.0,
                                                            "bound_ms": 200.0,
                                                            "within_bound": True,
                                                            "label": "SANDBOX-PARTIAL"},
                                              "t_nfr_003": {"minutes": 0.0,
                                                            "cpu_percent": 0.1,
                                                            "memory_mb": 10.0,
                                                            "label": "OWNER-VERIFY"},
                                              "sandbox_verdict":
                                                  "MEASURED_IN_BOUNDS",
                                              "owner_gates_open": []})
        assert harness.main([]) == 0

    def test_one_when_a_bound_is_exceeded(self, harness, monkeypatch):
        monkeypatch.setattr(harness, "run_harness",
                            lambda **kwargs: {"measured_in_bounds": False,
                                              "sandbox_verdict": "BOUND_EXCEEDED",
                                              "t_nfr_004": {
                                                  "p0_delivered": 2000,
                                                  "p0_expected": 2000,
                                                  "all_p0_processed": True,
                                                  "some_p2_evicted": True,
                                                  "p2_evicted": 1,
                                                  "eviction_reason": "X"},
                                              "t_nfr_001": {"p95_ms": 900.0,
                                                            "bound_ms": 400.0,
                                                            "within_bound": False,
                                                            "label": "SANDBOX-PARTIAL"},
                                              "t_nfr_002": {"p95_ms": 1.0,
                                                            "bound_ms": 200.0,
                                                            "within_bound": True,
                                                            "label": "SANDBOX-PARTIAL"},
                                              "t_nfr_003": {"minutes": 0.0,
                                                            "cpu_percent": 0.1,
                                                            "memory_mb": 10.0,
                                                            "label": "OWNER-VERIFY"},
                                              "owner_gates_open": []})
        assert harness.main([]) == 1
