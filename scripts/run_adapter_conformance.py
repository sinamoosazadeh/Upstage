#!/usr/bin/env python3
"""AI.10 conformance **harness runner** (CP-8 scope; delegated by CP-7).

Runs, in one executable pass:

* the hash-locked 19-case Toobit conformance fixture
  (``tests/fixtures/toobit_adapter_conformance.json``) against the REAL CP-7
  ``ToobitAdapter`` over the in-repo fake responder (a test double only — no
  network, no credentials, nothing outside the sandbox);
* **T-AD-001** legacy-adapter translation (synthetic self-checks; an owner
  export path can be supplied with ``--legacy-export``);
* **T-AD-002** idempotent-retry conformance through the adapter seam.

The fixture is verified against ``_meta.cases_sha256`` BEFORE any case runs;
a tampered fixture aborts the harness (exit 2) instead of producing a verdict.

Usage
-----
    python3 scripts/run_adapter_conformance.py [--json] [--legacy-export PATH]

Exit codes: 0 all green · 1 conformance failure · 2 fixture integrity failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "toobit_adapter_conformance.json"

#: The harness itself is the composition root: it sets the PAPER/test-double
#: environment the adapter needs. These are the nine G16 names only — the
#: values here are the fixture key/secret of the in-repo responder.
HARNESS_ENV = {
    "APEX_ENV": "PAPER",
    "APEX_ALLOW_SIGNED": "1",
    "TOOBIT_API_KEY": "TEST_KEY_CP8_HARNESS",
    "TOOBIT_API_SECRET": "TEST_SECRET_CP8_HARNESS",
}


def _prepare_imports() -> None:
    for extra in (str(REPO_ROOT), str(REPO_ROOT / "tests")):
        if extra not in sys.path:
            sys.path.insert(0, extra)


def verify_fixture(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Hash-seal check over the ``cases`` array (never over the whole file)."""
    from apex.identity.canonical_json import canonical_json

    cases = payload.get("cases")
    meta = payload.get("_meta", {})
    if not isinstance(cases, list) or not cases:
        return {"ok": False, "reason": "FIXTURE_CASES_ABSENT"}
    digest = hashlib.sha256(canonical_json(cases).encode("utf-8")).hexdigest()
    expected = meta.get("cases_sha256")
    return {"ok": digest == expected, "cases_sha256": digest,
            "expected": expected, "case_count": len(cases),
            "declared_count": meta.get("case_count"),
            "count_ok": meta.get("case_count") == len(cases),
            "reason": None if digest == expected else "FIXTURE_HASH_MISMATCH"}


def _apply_scenario(responder, scenario: Dict[str, Any]) -> None:
    if "fill_mode" in scenario:
        responder.set_fill_mode(scenario["fill_mode"],
                                price=scenario.get("fill_price"))
    if scenario.get("timeouts"):
        responder.lose_next_ack(scenario["timeouts"],
                                record=scenario.get("record_before_timeout",
                                                    True))
    if scenario.get("fail_with") is not None:
        responder.fail_next(scenario["fail_with"],
                            scenario.get("fail_times", 1))
    for order in scenario.get("seed_orders", []):
        responder.seed_order(**order)
    if scenario.get("seed_position"):
        responder.seed_position(**scenario["seed_position"])


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """One fixture case against the real adapter + the fake responder."""
    import asyncio

    from apex.config import Config
    from apex.execution.toobit_adapter import ToobitAdapter
    from fake_toobit_responder import FakeToobitResponder

    operations = {
        "submit_order": lambda adapter, call: adapter.submit_order(**call),
        "cancel_order": lambda adapter, call: adapter.cancel_order(**call),
        "query_order_state": lambda adapter, call:
            adapter.query_order_state(**call),
        "query_open_positions": lambda adapter, call:
            adapter.query_open_positions(**call),
        "query_account_margin_health": lambda adapter, call:
            adapter.query_account_margin_health(**call),
    }
    responder = FakeToobitResponder(api_key=HARNESS_ENV["TOOBIT_API_KEY"],
                                    api_secret=HARNESS_ENV["TOOBIT_API_SECRET"])
    adapter = ToobitAdapter(config=Config(), transport=responder,
                            utc_now=lambda: "2026-01-01T00:00:00.000Z",
                            clock=lambda: 1000.0)
    _apply_scenario(responder, case.get("scenario", {}))
    calls = case.get("calls") or [case["call"]]
    posts_before = len(responder.calls_to("/api/v1/futures/order", "POST"))
    result = None
    for call in calls:
        result = asyncio.run(operations[case["operation"]](adapter, call))
    observed = result.to_dict()
    failures: List[str] = []
    for key, expected in case.get("expect", {}).items():
        if key == "attempts":
            if len(result.attempts) != expected:
                failures.append(f"{key}: {len(result.attempts)} != {expected}")
        elif key == "attempt_sources":
            sources = [a.result_source for a in result.attempts]
            if sources != expected:
                failures.append(f"{key}: {sources} != {expected}")
        elif key == "unique_idempotency_keys":
            keys = [a.idempotency_key for a in result.attempts]
            unique = len(set(keys)) == len(keys)
            if unique is not expected:
                failures.append(f"{key}: unique={unique} != {expected}")
        elif key == "interval_disabled":
            if dict(result.interval_disabled or {}) != expected:
                failures.append(f"{key}: {result.interval_disabled} != {expected}")
        elif observed.get(key) != expected:
            failures.append(f"{key}: {observed.get(key)!r} != {expected!r}")
    venue = case.get("expect_venue") or {}
    if "posts_to_order_endpoint" in venue:
        posts = len(responder.calls_to("/api/v1/futures/order", "POST")) - \
            posts_before
        if posts != venue["posts_to_order_endpoint"]:
            failures.append(f"posts_to_order_endpoint: {posts} != "
                            f"{venue['posts_to_order_endpoint']}")
    if "signature_violations" in venue:
        violations = len(responder.signature_violations())
        if violations != venue["signature_violations"]:
            failures.append(f"signature_violations: {violations} != "
                            f"{venue['signature_violations']}")
    if "request_params" in venue:
        sent = responder.calls_to("/api/v1/futures/order", "POST")[-1].params
        for key, value in venue["request_params"].items():
            if sent.get(key) != value:
                failures.append(f"request_params.{key}: {sent.get(key)!r} != "
                                f"{value!r}")
    if "venue_recorded_client_order_id" in venue:
        if venue["venue_recorded_client_order_id"] not in responder.orders:
            failures.append("venue_recorded_client_order_id: absent")
    if "leverage_sent_for_BTCUSDT" in venue:
        if responder.leverage.get("BTC-SWAP-USDT") != \
                venue["leverage_sent_for_BTCUSDT"]:
            failures.append("leverage_sent_for_BTCUSDT: mismatch")
    state = case.get("expect_state") or {}
    if "disabled_intervals" in state:
        observed_state = {k: list(v) for k, v in
                          adapter.disabled_intervals().items()}
        if observed_state != state["disabled_intervals"]:
            failures.append(f"disabled_intervals: {observed_state} != "
                            f"{state['disabled_intervals']}")
    return {"id": case["id"], "operation": case["operation"],
            "ok": not failures, "failures": failures}


def run_harness(*, legacy_export: str | None = None) -> Dict[str, Any]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seal = verify_fixture(payload)
    try:
        fixture_name = str(FIXTURE.relative_to(REPO_ROOT))
    except ValueError:                    # relocated fixture (tests, owner copy)
        fixture_name = str(FIXTURE)
    report: Dict[str, Any] = {"harness": "AI.10 adapter conformance runner",
                              "fixture": fixture_name,
                              "fixture_seal": seal, "cases": []}
    if not (seal["ok"] and seal["count_ok"]):
        report["status"] = "FIXTURE_INTEGRITY_FAILURE"
        report["passed"] = False
        return report

    from apex.research import adapter_conformance as ac

    cases = [run_case(case) for case in payload["cases"]]
    report["cases"] = cases
    report["cases_passed"] = sum(1 for c in cases if c["ok"])
    report["cases_total"] = len(cases)
    report["t_ad_001"] = ac.t_ad_001(export_path=legacy_export)
    report["t_ad_002"] = ac.t_ad_002(retries=100, submit=_retry_seam())
    report["passed"] = (report["cases_passed"] == report["cases_total"]
                        and report["t_ad_001"]["passed"]
                        and report["t_ad_002"]["passed"])
    report["status"] = "PASS" if report["passed"] else "FAIL"
    return report


def _retry_seam():
    """T-AD-002 seam: the CP-7 adapter's own duplicate cache."""
    import asyncio

    from apex.config import Config
    from apex.execution.toobit_adapter import ToobitAdapter
    from fake_toobit_responder import FakeToobitResponder

    responder = FakeToobitResponder(api_key=HARNESS_ENV["TOOBIT_API_KEY"],
                                    api_secret=HARNESS_ENV["TOOBIT_API_SECRET"])
    adapter = ToobitAdapter(config=Config(), transport=responder)

    def submit(intent_id: str) -> Dict[str, Any]:
        result = asyncio.run(adapter.submit_order(
            intent_id=intent_id, symbol="BTCUSDT", timeframe="15m",
            direction="LONG", quantity=1, price=60000, order_type="LIMIT"))
        return result.to_dict()

    return submit


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="print the full JSON verdict")
    parser.add_argument("--legacy-export", default=None,
                        help="path to an owner-supplied v2/v3 export (JSON list)")
    args = parser.parse_args(argv)

    _prepare_imports()
    for name, value in HARNESS_ENV.items():
        os.environ.setdefault(name, value)
    report = run_harness(legacy_export=args.legacy_export)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "FIXTURE_INTEGRITY_FAILURE":
        print(f"FIXTURE INTEGRITY FAILURE: {report['fixture']} — "
              f"{report['fixture_seal'].get('reason')}; no case was executed")
    else:
        seal = report["fixture_seal"]
        print(f"fixture: {report['fixture']} "
              f"({seal.get('case_count')} cases, sha256 "
              f"{str(seal.get('cases_sha256'))[:16]}…, "
              f"sealed={seal['ok']})")
        for case in report["cases"]:
            mark = "PASS" if case["ok"] else "FAIL"
            print(f"  [{mark}] {case['id']} {case['operation']}"
                  + ("" if case["ok"] else " — " + "; ".join(case["failures"])))
        print(f"T-AD-001 legacy translation: "
              f"{'PASS' if report['t_ad_001']['passed'] else 'FAIL'}")
        print(f"T-AD-002 idempotent retries: "
              f"{'PASS' if report['t_ad_002']['passed'] else 'FAIL'}")
        print(f"status: {report['status']} "
              f"({report.get('cases_passed')}/{report.get('cases_total')} cases)")
    if report["status"] == "FIXTURE_INTEGRITY_FAILURE":
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
