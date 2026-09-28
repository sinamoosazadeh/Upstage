"""V6 probe A-003: out-of-subset YAML syntax accepted silently.
ISSUE-CP1-008 promises: anything outside the frozen subset raises ValueError.
Anchors/aliases/tags/block-scalar markers should therefore be REJECTED.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import _YamlSubsetParser, _load_yaml, PARAMS_FILES, PARAMS_DIR

def p(text):
    try:
        return _YamlSubsetParser(text).parse()
    except ValueError as e:
        return "ValueError: %s" % e

CASES = [
    ("anchor on value",        "k: &base 123"),
    ("alias as value",         "k2: *base"),
    ("tag !!str",              "k3: !!str 123"),
    ("block scalar marker |",  "k4: |\n  line1\n"),
    ("block scalar marker >",  "k5: >\n  folded\n"),
    ("document separator",     "---\na: 1\n"),
    ("unclosed single quote",  "k6: 'unterminated"),
    ("unclosed double quote",  'k7: "unterminated'),
    ("set syntax ?",           "? complex\n: value\n"),
    ("multiline plain scalar", "k8: some value\n  continuation\n"),
    ("plain multi-line",       "a: 1\nb: 2\nc: 3"),
]
for name, text in CASES:
    print("%-26s | %-38r -> %r" % (name, text.replace("\n", "\\n"), p(text)))

print()
print("== do the six frozen YAMLs + others use any of this syntax? ==")
for fname in sorted(PARAMS_FILES.values()):
    path = PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING (expected for e11_classifier_v1.yaml)" % fname)
        continue
    text = path.read_text()
    hits = []
    for pat in ("&", "*", "!!", "|", ">", "---", "..."):
        for ln, line in enumerate(text.splitlines(), 1):
            s = line.split("#")[0]
            if pat in s and not s.strip().startswith("-"):
                # '|' or '>' inside a flow/quoted value is legitimate; report raw
                hits.append((pat, ln, line.strip()[:60]))
    print("%-28s %s" % (fname, "clean" if not hits else hits[:6]))
