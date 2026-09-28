"""Exercise NFR result aggregation with in-memory injected component reports."""
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
script = root / "scripts" / "run_nfr_harness.py"
spec = importlib.util.spec_from_file_location("i015_nfr_harness", script)
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
for name, value in harness.HARNESS_ENV.items():
    os.environ[name] = value  # hard-coded test-double values, not credentials

async def failed_bounded_queue():
    return {
        "p0_delivered": 2000, "p0_expected": 2000,
        "all_p0_processed": True, "p2_published": 1000,
        "p3_published": 100, "p2_evicted": 1, "p3_evicted": 0,
        "some_p2_evicted": True, "eviction_reason": "QUEUE_OVERFLOW_DROP",
        "bounded": False, "lane_qsize": 1001,
        "counts": {"p0_delivered": 2000},
    }

harness._queue_bounds_probe = failed_bounded_queue
harness._analysis_latency = lambda samples: {
    "samples": samples, "p95_ms": 1.0, "bound_ms": 400.0,
    "within_bound": True, "label": "SANDBOX-PARTIAL",
}
harness._submission_latency = lambda samples: {
    "samples": samples, "p95_ms": 1.0, "bound_ms": 200.0,
    "within_bound": True, "label": "SANDBOX-PARTIAL",
}
harness._resource_sample = lambda minutes: {
    "minutes": minutes, "cpu_percent": 99.0, "cpu_bound": 20.0,
    "memory_mb": 999.0, "memory_bound_mb": 400.0,
    "within_bounds": False, "label": "OWNER-VERIFY",
    "owner_gate": "AI.10 rule 5 — 60-minute run on the target device",
    "note": "injected failed sandbox sample",
}
report = harness.run_harness(decisions=1, orders=1, minutes=0.0)
print(f"queue_bounded={report['t_nfr_004']['bounded']}")
print(f"queue_lane_qsize={report['t_nfr_004']['lane_qsize']}")
print(f"resource_within_bounds={report['t_nfr_003']['within_bounds']}")
print(f"resource_label={report['t_nfr_003']['label']}")
print(f"measured_in_bounds={report['measured_in_bounds']}")
print(f"sandbox_verdict={report['sandbox_verdict']}")
print(f"owner_gates_open={len(report['owner_gates_open'])}")

harness.run_harness = lambda **kwargs: report
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    exit_code = harness.main([])
print(f"cli_exit_code={exit_code}")
print("cli_output_begin")
print(captured.getvalue().rstrip())
print("cli_output_end")
