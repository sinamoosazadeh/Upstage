"""Independent I-013 reproduction using only the in-repo fake responder."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tests"))
script = root / "scripts" / "run_adapter_conformance.py"
spec = importlib.util.spec_from_file_location("i013_runner", script)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
# Explicitly use the runner's hard-coded test-double values; never read .env/secrets.
for name, value in runner.HARNESS_ENV.items():
    os.environ[name] = value

bad_records = [{
    "engine_id": "E99",
    "version": "v3",
    "payload": {"synthetic_invalid_record": True},
}]
with tempfile.TemporaryDirectory(prefix="i013-") as tmp:
    export = Path(tmp) / "invalid-legacy-export.json"
    export.write_text(json.dumps(bad_records), encoding="utf-8")
    report = runner.run_harness(legacy_export=str(export))
    cli_output = io.StringIO()
    with contextlib.redirect_stdout(cli_output):
        exit_code = runner.main(["--legacy-export", str(export)])

print(f"legacy_failures={len(report['t_ad_001']['real_data_gate']['failures'])}")
print(f"legacy_gate_status={report['t_ad_001']['real_data_gate']['status']}")
print(f"t_ad_001_synthetic_passed={report['t_ad_001']['passed']}")
print(f"top_level_passed={report['passed']}")
print(f"top_level_status={report['status']}")
print(f"cli_exit_code={exit_code}")
print("cli_output_begin")
print(cli_output.getvalue().rstrip())
print("cli_output_end")
