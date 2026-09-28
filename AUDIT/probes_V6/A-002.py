"""V6 probe A-002: .env grammar — inline comments, unbalanced quotes,
duplicate names. Uses the REAL apex.config.parse_dotenv on temp files only.
"""
import os
import sys
import tempfile
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import parse_dotenv, Config

def parse(text):
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / ".env"
        p.write_text(text)
        return parse_dotenv(p)

print("== 1) inline comment after value ==")
try:
    d = parse("APEX_ALLOW_SIGNED=1 # comment\n")
    print("parsed:", d)
    print("value repr:", repr(d.get("APEX_ALLOW_SIGNED")))
    # does it make the flag False?
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / ".env"
        p.write_text("APEX_ALLOW_SIGNED=1 # comment\n")
        for k in ("APEX_ALLOW_SIGNED",):
            os.environ.pop(k, None)
        cfg = Config(str(p))
        print("Config.allow_signed with '1 # comment' =", cfg.allow_signed)
except ValueError as e:
    print("ValueError:", e)

print("== 2) '#' inside a value (no separator) ==")
try:
    d = parse("TOOBIT_API_KEY=sk#abc\n")
    print("parsed:", d)
except ValueError as e:
    print("ValueError:", e)

print("== 3) unbalanced quote in secret accepted? ==")
try:
    d = parse('TOOBIT_API_KEY="unbalanced\n')
    print("parsed without error:", d, "| value repr:", repr(d.get("TOOBIT_API_KEY")))
except ValueError as e:
    print("ValueError:", e)

print("== 4) duplicate name — silent replace? ==")
try:
    d = parse("APEX_ENV=PAPER\nAPEX_ENV=LIVE\n")
    print("parsed:", d, "| (last wins, no warning)")
except ValueError as e:
    print("ValueError:", e)

print("== 5) leading '#' full-line comment + export prefix ==")
d = parse("# full comment\nexport APEX_ENV=BACKTEST\n")
print("parsed:", d)

print("== 6) value with '=' inside ==")
d = parse("TOOBIT_API_SECRET=abc=def=\n")
print("parsed:", d, repr(d.get("TOOBIT_API_SECRET")))

print("== 7) quoted value with trailing spaces ==")
d = parse('APEX_ENV=" PAPER "\n')
print("parsed:", d, repr(d.get("APEX_ENV")))
