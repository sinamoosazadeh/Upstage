#!/usr/bin/env python3
"""AI.10 NFR harness runner (T-NFR-001 … T-NFR-004) — CP-8 scope.

Honesty rules (AI.13 / ADR-P2-010) applied here:

* **T-NFR-004** (queue bounds & priorities) is an in-process law and is
  therefore measured and asserted exactly as AI.10 specifies.
* **T-NFR-001** (analysis p95 < 400 ms) and **T-NFR-002** (submission ACK
  p95 < 200 ms) are measured *in this environment* against in-repo fixtures
  and the fake responder (no network) and are labelled ``SANDBOX-PARTIAL``:
  AI.10 rule 5 requires the run on the actual target device with 30 % headroom
  before live deployment — that measurement is an OWNER procedure and is never
  claimed here.
* **T-NFR-003** (CPU < 20 %, memory < 400 MB over 60 min) is sampled for
  ``--minutes`` (default 1) and always labelled OWNER-VERIFY, because the
  60-minute on-device run is the acceptance condition.

Usage
-----
    python3 scripts/run_nfr_harness.py [--json] [--minutes 1] [--decisions 200]

Exit codes: 0 measured within AI.7 bounds (sandbox labels attached) · 1 a
bound was exceeded · 2 harness error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path
from statistics import quantiles
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]

#: AI.7 bounds (never re-tuned here).
ANALYSIS_P95_MS = 400.0
SUBMISSION_P95_MS = 200.0
CPU_PERCENT_MAX = 20.0
MEMORY_MB_MAX = 400.0

HARNESS_ENV = {
    "APEX_ENV": "PAPER",
    "APEX_ALLOW_SIGNED": "1",
    "TOOBIT_API_KEY": "TEST_KEY_CP8_NFR",
    "TOOBIT_API_SECRET": "TEST_SECRET_CP8_NFR",
}


def _prepare_imports() -> None:
    for extra in (str(REPO_ROOT), str(REPO_ROOT / "tests")):
        if extra not in sys.path:
            sys.path.insert(0, extra)


def percentile(values: List[float], fraction: float) -> float:
    """Nearest-rank percentile, ``rank = ceil(p·n)`` (no interpolation)."""
    if not values:
        raise ValueError("EMPTY_SAMPLE")
    if not 0.0 < float(fraction) <= 1.0:
        raise ValueError("FRACTION_QX")
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil(float(fraction) * len(ordered))))
    return ordered[rank - 1]


async def _queue_bounds_probe() -> Dict[str, Any]:
    """T-NFR-004: 2000 P0 + 1000 P2 (+ P3 pressure) on the frozen bus."""
    from apex.bus import EventBus, Priority, make_event

    bus = EventBus()                      # dispatcher NOT started: nothing drains
    seen = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    async def consumer(event):
        seen[f"P{int(event.priority)}"] += 1

    bus.subscribe("nfr", consumer)
    for _ in range(2000):
        await bus.publish(make_event(Priority.P0, "nfr", {"i": 1}))
    for _ in range(1000):
        await bus.publish(make_event(Priority.P2, "nfr", {"i": 2}))
    for _ in range(100):
        await bus.publish(make_event(Priority.P3, "nfr", {"i": 3}))
    evictions = bus.eviction_log
    return {"p0_delivered": bus.counts["p0_delivered"],
            "p0_expected": 2000,
            "all_p0_processed": bus.counts["p0_delivered"] == 2000,
            "p2_published": 1000,
            "p3_published": 100,
            "p2_evicted": sum(1 for e in evictions if int(e.priority) == 2),
            "p3_evicted": sum(1 for e in evictions if int(e.priority) == 3),
            "some_p2_evicted": any(int(e.priority) == 2 for e in evictions),
            "eviction_reason": evictions[0].reason if evictions else None,
            "bounded": bus._shared_lane.qsize() <= 1000,
            "lane_qsize": bus._shared_lane.qsize(),
            "counts": bus.counts}


def _analysis_latency(samples: int) -> Dict[str, Any]:
    """T-NFR-001: time the in-repo decision path on synthetic context input."""
    from apex.decision.pipeline import build_proposal
    from apex.risk.kernel import adjudicate

    proposal_input = {
        "setup_id": "SF_FVG_SWEEP_REV-0001", "direction": "LONG",
        "entry_logic_ref": "E-05/FVG", "stop": 99.0, "targets": (103.0,),
        "p_hat": 0.6, "u": 0.2, "c": 0.7, "conflict_state": "CONSENSUS",
        "snapshot_id": "sn-nfr-0001", "r_penalty": 0.10, "cost_unit": 0.05,
        "entry": 100.0}
    adjudication_input = {
        "snapshot_id": "sn-nfr-0001", "timeframe": "15m", "capital": 10_000.0,
        "q_raw": 0.9, "qx_state": False, "failed_setup_gate": False,
        "pit_violation": False, "availability_time": 1,
        "portfolio_exposure": 100.0, "proposed_notional": 50.0,
        "capital_hard_cap": 1_000_000.0, "circuit_breaker_engaged": False,
        "emergency_state": "NORMAL", "per_symbol_exposure": 100.0,
        "symbol_cap": 1_000.0, "portfolio_cap": 1_000_000.0,
        "conflict_state": "CONSENSUS", "staleness_seconds": 1.0,
        "freshness_sla_seconds": 30.0, "oi_lag_seconds": 5.0,
        "oi_lag_threshold_seconds": 60.0, "is_risk_increase": False,
        "uncertainty_is_rising": False, "realized_daily_loss_fraction": 0.0,
        "realized_weekly_loss_fraction": 0.0, "consecutive_losses": 0,
        "time_to_expiry_days": 40.0, "margin_health_fraction": 0.9,
        "stop_distance": 1.0, "min_quantity": 0.001, "risk_state": "LowRisk"}
    timings: List[float] = []
    for _ in range(int(samples)):
        start = time.perf_counter()
        build_proposal(**proposal_input)
        adjudicate(adjudication_input)
        timings.append((time.perf_counter() - start) * 1000.0)
    p95 = percentile(timings, 0.95)
    return {"samples": len(timings), "p95_ms": p95, "max_ms": max(timings),
            "median_ms": percentile(timings, 0.50),
            "bound_ms": ANALYSIS_P95_MS, "within_bound": p95 <= ANALYSIS_P95_MS,
            "label": "SANDBOX-PARTIAL",
            "owner_gate": "AI.10 rule 5 — target device, 30 % headroom"}


def _submission_latency(samples: int) -> Dict[str, Any]:
    """T-NFR-002: ACK latency against the in-repo fake responder."""
    from apex.config import Config
    from apex.execution.toobit_adapter import ToobitAdapter
    from fake_toobit_responder import FakeToobitResponder

    responder = FakeToobitResponder(api_key=HARNESS_ENV["TOOBIT_API_KEY"],
                                    api_secret=HARNESS_ENV["TOOBIT_API_SECRET"])
    adapter = ToobitAdapter(config=Config(), transport=responder)
    timings: List[float] = []
    for i in range(int(samples)):
        start = time.perf_counter()
        asyncio.run(adapter.submit_order(
            intent_id=f"intent-nfr-{i:05d}", symbol="BTCUSDT", timeframe="15m",
            direction="LONG", quantity=1, price=60000, order_type="LIMIT"))
        timings.append((time.perf_counter() - start) * 1000.0)
    p95 = percentile(timings, 0.95)
    return {"samples": len(timings), "p95_ms": p95, "max_ms": max(timings),
            "bound_ms": SUBMISSION_P95_MS, "within_bound": p95 <= SUBMISSION_P95_MS,
            "label": "SANDBOX-PARTIAL",
            "note": "in-process fake responder; the network leg is an owner "
                    "measurement on the target device"}


def _resource_sample(minutes: float) -> Dict[str, Any]:
    """T-NFR-003: CPU/memory sample for the requested window."""
    import resource

    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    deadline = start_wall + max(0.0, float(minutes)) * 60.0
    while time.perf_counter() < deadline:
        time.sleep(0.05)
    wall = max(1e-9, time.perf_counter() - start_wall)
    cpu = time.process_time() - start_cpu
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    memory_mb = peak_rss_kb / 1024.0
    cpu_percent = 100.0 * cpu / wall
    return {"minutes": float(minutes), "cpu_percent": cpu_percent,
            "cpu_bound": CPU_PERCENT_MAX,
            "memory_mb": memory_mb, "memory_bound_mb": MEMORY_MB_MAX,
            "within_bounds": cpu_percent <= CPU_PERCENT_MAX
            and memory_mb <= MEMORY_MB_MAX,
            "label": "OWNER-VERIFY",
            "owner_gate": "AI.10 rule 5 — 60-minute run on the target device",
            "note": "an idle sample is not the acceptance measurement"}


def run_harness(*, decisions: int = 200, orders: int = 100,
                minutes: float = 1.0) -> Dict[str, Any]:
    _prepare_imports()
    for name, value in HARNESS_ENV.items():
        os.environ.setdefault(name, value)
    report: Dict[str, Any] = {
        "harness": "AI.10 NFR harness (AI.7 bounds)",
        "bounds": {"analysis_p95_ms": ANALYSIS_P95_MS,
                   "submission_p95_ms": SUBMISSION_P95_MS,
                   "cpu_percent": CPU_PERCENT_MAX,
                   "memory_mb": MEMORY_MB_MAX},
        "t_nfr_004": asyncio.run(_queue_bounds_probe()),
        "t_nfr_001": _analysis_latency(decisions),
        "t_nfr_002": _submission_latency(orders),
        "t_nfr_003": _resource_sample(minutes),
    }
    measured_in_bounds = (report["t_nfr_004"]["all_p0_processed"]
                          and report["t_nfr_004"]["some_p2_evicted"]
                          and report["t_nfr_001"]["within_bound"]
                          and report["t_nfr_002"]["within_bound"])
    report["sandbox_verdict"] = "MEASURED_IN_BOUNDS" if measured_in_bounds \
        else "BOUND_EXCEEDED"
    report["measured_in_bounds"] = measured_in_bounds
    report["owner_gates_open"] = ["T-NFR-001 target device (30 % headroom)",
                                  "T-NFR-002 target device (30 % headroom)",
                                  "T-NFR-003 target device 60-minute run",
                                  "T-TOOBIT-001 depth > 500k USDT per symbol",
                                  "T-TOOBIT-002 venue rate ≤ 100 req/s"]
    report["note"] = ("sandbox numbers are measurements of this repository in "
                      "this environment; they are NOT target-device acceptance "
                      "results (AI.10 rule 5 / AI.13)")
    return report


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--decisions", type=int, default=200)
    parser.add_argument("--orders", type=int, default=100)
    parser.add_argument("--minutes", type=float, default=1.0)
    args = parser.parse_args(argv)
    report = run_harness(decisions=args.decisions, orders=args.orders,
                         minutes=args.minutes)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        q = report["t_nfr_004"]
        print(f"T-NFR-004 queue bounds: P0 {q['p0_delivered']}/{q['p0_expected']} "
              f"delivered, P2 evicted {q['p2_evicted']}, "
              f"reason={q['eviction_reason']} "
              f"→ {'PASS' if q['all_p0_processed'] and q['some_p2_evicted'] else 'FAIL'}")
        a, s = report["t_nfr_001"], report["t_nfr_002"]
        print(f"T-NFR-001 analysis p95 {a['p95_ms']:.2f} ms "
              f"(bound {a['bound_ms']} ms) → "
              f"{'within' if a['within_bound'] else 'EXCEEDS'} [{a['label']}]")
        print(f"T-NFR-002 submission p95 {s['p95_ms']:.2f} ms "
              f"(bound {s['bound_ms']} ms) → "
              f"{'within' if s['within_bound'] else 'EXCEEDS'} [{s['label']}]")
        r = report["t_nfr_003"]
        print(f"T-NFR-003 resource sample {r['minutes']:.1f} min: "
              f"CPU {r['cpu_percent']:.2f} %, RSS {r['memory_mb']:.1f} MB "
              f"[{r['label']}]")
        print(f"sandbox verdict: {report['sandbox_verdict']}; owner gates open: "
              f"{len(report['owner_gates_open'])}")
    return 0 if report["measured_in_bounds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
