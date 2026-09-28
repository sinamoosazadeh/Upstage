"""V6 probe A-009: a QUOTED block-sequence item containing ':' is turned into
a single-entry dict (key = the broken quoted prefix) instead of a string.
`- "https://example.invalid"` -> {'"https': '//example.invalid"'}
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
    ("quoted URL item",     'endpoints:\n  - "https://example.invalid"'),
    ("plain URL item",      'endpoints:\n  - https://example.invalid'),
    ("quoted item, no :",   'endpoints:\n  - "plain"'),
    ("quoted host:port",    'endpoints:\n  - "example.com:8443"'),
    ("inline k:v quoted",   'endpoints:\n  - "GET /path"'),
]
for name, text in CASES:
    print("%-22s | %-40r -> %r" % (name, text.replace("\n", "\\n"), p(text)))

print()
print("== real toobit_wire_v1.yaml endpoint items: quoted or plain? ==")
import apex.config as C
text = (C.PARAMS_DIR / "toobit_wire_v1.yaml").read_text()
for ln, raw in enumerate(text.splitlines(), 1):
    st = raw.strip()
    if st.startswith("- "):
        print("%4d %r" % (ln, st))
