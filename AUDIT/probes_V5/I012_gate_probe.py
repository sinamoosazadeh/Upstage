"""Independent in-memory/tempfile reproduction for I-012; no real export or network."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from apex.research import adapter_conformance as ac

cases = ac.synthetic_legacy_cases()
records = cases * 25  # 4 unique v4-derived records, repeated 25 times = 100 rows
unique = {
    json.dumps(record, sort_keys=True, separators=(",", ":"))
    for record in records
}
with tempfile.TemporaryDirectory(prefix="i012-") as tmp:
    export = Path(tmp) / "synthetic.json"
    export.write_text(json.dumps(records), encoding="utf-8")
    result = ac.t_ad_001(export_path=str(export))

gate = result["real_data_gate"]
print(f"synthetic_case_count={len(cases)}")
print(f"export_record_count={len(records)}")
print(f"unique_record_count={len(unique)}")
print(f"records_per_unique={len(records) // len(unique)}")
print(f"required_samples={gate['required_samples']}")
print(f"samples_supplied={gate['samples_supplied']}")
print(f"translated={gate['translated']}")
print(f"failures={len(gate['failures'])}")
print(f"gate_status={gate['status']}")
print(f"export_summary_keys={','.join(sorted(gate))}")
print(f"synthetic_self_checks_passed={result['passed']}")
