"""V6 probe A-007: null first key breaks the rest of the mapping.
`a:` followed by `b: 2` — the null branch returns a SINGLE-entry map and the
remaining line becomes 'trailing content' (ValueError) instead of
{'a': None, 'b': 2}.
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
    ("null first key + more",   "a:\nb: 2"),
    ("null mid key",            "a: 1\nb:\nc: 3"),
    ("null last key (control)", "a: 1\nb:"),
    ("single null key",         "a:"),
    ("nested null then value",  "outer:\n  a:\n  b: 2"),
]
for name, text in CASES:
    print("%-26s | %-16r -> %r" % (name, text.replace("\n", "\\n"), p(text)))

print()
print("real YAML semantics expect: a: None, b: 2 for case 1")
print()
print("== do any real params files contain a null value key? ==")
import apex.config as C
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING" % fname)
        continue
    hits = []
    for ln, raw in enumerate(path.read_text().splitlines(), 1):
        s = raw.split("#")[0].rstrip()
        st = s.strip()
        if st.endswith(":") and not st.startswith("-"):
            hits.append((ln, st))
    print("%-28s %s" % (fname, "no null-value keys" if not hits else hits))
