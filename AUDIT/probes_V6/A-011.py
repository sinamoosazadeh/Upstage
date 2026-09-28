"""V6 probe A-011: escapes in quoted scalars are NOT decoded.
'it''s' -> "it''s" (should be "it's"); double-quote escapes stay raw.
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
    ("single-quote escape",  "x: 'it''s'"),
    ("double-quote \\n",     'x: "a\\nb"'),
    ("double-quote backslash", 'x: "a\\\\b"'),
    ("double-quote escaped quote", 'x: "a\\"b"'),
    ("single-quote plain",   "x: 'abc'"),
]
for name, text in CASES:
    out = p(text)
    print("%-30s | %-22r -> %r" % (name, text.replace("\n", "\\n"), out))

print()
print("real YAML semantics: 'it''s' -> \"it's\" ; \"a\\nb\" -> 'a<newline>b' ; \"a\\\\b\" -> 'a\\b' ; \"a\\\"b\" -> 'a\"b'")
print()
print("== escapes in real params files? ==")
import apex.config as C
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING" % fname)
        continue
    hits = []
    for ln, raw in enumerate(path.read_text().splitlines(), 1):
        if "''" in raw or "\\" in raw:
            hits.append((ln, raw.strip()[:70]))
    print("%-28s %s" % (fname, "no escapes" if not hits else hits))
