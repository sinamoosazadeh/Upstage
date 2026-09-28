"""V6 probe A-006: root-level flow map is misparsed as a block map with a
garbage key, because ':' detection runs BEFORE flow-node detection.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import _YamlSubsetParser

def p(text):
    try:
        return _YamlSubsetParser(text).parse()
    except ValueError as e:
        return "ValueError: %s" % e

CASES = [
    ("root flow map",          "{a: 1, b: 2}"),
    ("root flow map, no space","{a:1,b:2}"),
    ("root flow seq",          "[1, 2, 3]"),
    ("root flow map single",   "{a: 1}"),
    ("root flow empty map",    "{}"),
]
for name, text in CASES:
    print("%-24s | %-18r -> %r" % (name, text, p(text)))

print()
print("expected by real YAML semantics: {a: 1, b: 2} -> {'a': 1, 'b': 2}")
print()
print("== do any real params files start with a root flow map? ==")
import apex.config as C
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if path.exists():
        first = next((l for l in path.read_text().splitlines() if l.strip() and not l.strip().startswith("#")), "")
        print("%-28s first content line: %r" % (fname, first))
    else:
        print("%-28s MISSING" % fname)
