"""V6 probe A-004: duplicate YAML keys silently overwrite (block + flow),
including via the public _load_yaml path. NEVER touches the real params/ —
PARAMS_DIR is redirected to a temp dir inside this process only.
"""
import sys
import tempfile
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import apex.config as C
from apex.config import _YamlSubsetParser

def p(text):
    try:
        return _YamlSubsetParser(text).parse()
    except ValueError as e:
        return "ValueError: %s" % e

print("== 1) duplicate key, root block map ==")
print(p("budget_per_trade: 0.005\nbudget_per_trade: 0.50\n"))

print("== 2) duplicate key, nested block map ==")
print(p("risk:\n  budget_per_trade: 0.005\n  budget_per_trade: 0.50\n"))

print("== 3) duplicate key, flow map ==")
print(p("m: {a: 1, a: 2}\n"))

print("== 4) duplicate key via the PUBLIC loader (risk_defaults name) ==")
with tempfile.TemporaryDirectory() as td:
    tmp = pathlib.Path(td)
    (tmp / "risk_defaults_v1.yaml").write_text(
        "# probe file\nbudget_per_trade: 0.005\nk_attn: 0.25\nbudget_per_trade: 0.50\n")
    orig = C.PARAMS_DIR
    C.PARAMS_DIR = tmp
    try:
        data = C._load_yaml("risk_defaults")
        print("public _load_yaml ->", data)
    finally:
        C.PARAMS_DIR = orig

print("== 5) control: real risk_defaults_v1.yaml has no duplicate keys ==")
import collections
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING" % fname)
        continue
    text = path.read_text()
    # crude duplicate-key scan per indentation block (nested-aware via indent+key)
    seen = {}
    dups = []
    for ln, raw in enumerate(text.splitlines(), 1):
        s = raw.split("#")[0].rstrip()
        if not s.strip() or ":" not in s:
            continue
        indent = len(s) - len(s.lstrip())
        key = s.strip().split(":")[0].strip()
        sig = (indent, key)
        if sig in seen:
            dups.append((key, seen[sig], ln))
        seen[sig] = ln
    print("%-28s %s" % (fname, "no duplicate (indent,key) pairs" if not dups else dups))
