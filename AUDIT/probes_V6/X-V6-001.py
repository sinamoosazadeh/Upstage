"""V6 probe X-V6-001: FeatureRegistry._by_num is declared Dict[int, ...] and
named "by number", but is populated with FULL_ID string keys, and no code
ever reads it. Dead index + wrong type annotation (catalog.py:82/90).
"""
import sys
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.data_catalog.catalog import build_registry

registry, _ = build_registry()
keys = list(registry._by_num.keys())
print("_by_num size:", len(keys))
print("all keys are strings (full_ids), not feature numbers:",
      all(isinstance(k, str) for k in keys))
print("sample keys:", keys[:2])
print("declared type: Dict[int, FeatureContract] (catalog.py:82)")
print("populated with contract.id.full_id (catalog.py:90)")
print()
r = subprocess.run(["grep", "-rn", "_by_num", str(REPO / "apex"),
                    str(REPO / "tests"), str(REPO / "scripts")],
                   capture_output=True, text=True)
print("all _by_num references in the repo:")
print(r.stdout)
print("=> written in register(), never read anywhere (no lookup path uses it).")
