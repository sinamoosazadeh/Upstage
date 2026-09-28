"""V6 probe A-010: '#' in a plain scalar is treated as a comment start even
without a preceding space: `x: abc#def` -> 'abc' (value silently truncated).
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
    ("no separator",        "x: abc#def"),
    ("with space",          "x: abc #def"),
    ("full-line comment",   "# comment\nx: 1"),
    ("hash inside quotes",  'x: "ab#cd"'),
    ("hash in key",         "a#b: 1"),
    ("hash in flow",        "x: {a: b#c, d: 1}"),
]
for name, text in CASES:
    print("%-22s | %-22r -> %r" % (name, text.replace("\n", "\\n"), p(text)))

print()
print("real YAML 1.2: a '#' not preceded by whitespace is part of the plain scalar")
print()
print("== '#' inside values of real params files? ==")
import apex.config as C
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING" % fname)
        continue
    hits = []
    for ln, raw in enumerate(path.read_text().splitlines(), 1):
        if "#" in raw:
            # lines whose '#' is inside a quoted value
            stripped_of_comments = raw
            # naive check: does removing '#' truncate anything that is quoted?
            if '"' in raw or "'" in raw:
                q = raw.split("#")[0]
                if q.count('"') % 2 == 1 or q.count("'") % 2 == 1:
                    hits.append((ln, raw.strip()[:70], "odd quotes before # -> # inside quoted value"))
    print("%-28s %s" % (fname, "no '#' inside quoted values" if not hits else hits))
