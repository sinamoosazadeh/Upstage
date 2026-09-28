"""V6 probe A-008: nesting inside flow collections breaks structure.
x: {a: [1, 2], b: 3} raises; x: [[1, 2], [3, 4]] silently degrades to strings.
_split_flow tracks quotes but NOT bracket/brace depth.
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
    ("flow map w/ nested seq",  "x: {a: [1, 2], b: 3}"),
    ("flow seq of seqs",        "x: [[1, 2], [3, 4]]"),
    ("flow seq w/ nested map",  "x: [{a: 1}, {b: 2}]"),
    ("flat flow map (control)", "x: {a: 1, b: 3}"),
    ("flat flow seq (control)", "x: [1, 2, 3, 4]"),
    ("unterminated flow map",   "x: {a: 1"),
    ("unterminated flow seq",   "x: [1, 2"),
]
for name, text in CASES:
    print("%-26s | %-26r -> %r" % (name, text, p(text)))

print()
print("== nesting usage in real params files (flow value containing '[' or '{' inside)? ==")
import apex.config as C
for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING" % fname)
        continue
    hits = []
    for ln, raw in enumerate(path.read_text().splitlines(), 1):
        s = raw.rstrip()
        st = s.strip()
        if st.startswith("#"):
            continue
        # flow value containing nested brackets/braces
        if (st.count("[") > 2 or st.count("{") > 2 or
                ("[" in st.split(":", 1)[-1] and "{" in st.split(":", 1)[-1])):
            hits.append((ln, st[:70]))
    print("%-28s %s" % (fname, "no nested flow" if not hits else hits))
