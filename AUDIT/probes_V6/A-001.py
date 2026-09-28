"""V6 probe A-001: explicit --env-file path that does not exist is silently
ignored; inherited env (LIVE/1/1) survives; no error is raised.

Read-only: only reads repository code; writes nothing outside AUDIT/.
"""
import os
import sys
import tempfile
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.config import Config, _load_env  # real repository loader

results = []

# 1) explicit non-existent env file -> silently ignored (no exception)
missing = "/tmp/does_not_exist_V6/env.paper"
assert not os.path.exists(missing)
env = _load_env(missing)
results.append(("explicit missing path ignored by _load_env", True,
                "no exception raised; keys=%s" % sorted(env)[:3]))

# 2) inherited process env LIVE/1/1 + missing PAPER env file -> Config stays LIVE/True/True
saved = {k: os.environ.get(k) for k in
         ("APEX_ENV", "APEX_ALLOW_SIGNED", "APEX_ECONOMIC_GATE_SIGNED", "APEX_SQLITE_PATH")}
try:
    os.environ["APEX_ENV"] = "LIVE"
    os.environ["APEX_ALLOW_SIGNED"] = "1"
    os.environ["APEX_ECONOMIC_GATE_SIGNED"] = "1"
    os.environ["APEX_SQLITE_PATH"] = "data/live.sqlite3"
    with tempfile.TemporaryDirectory() as td:
        paper_env = pathlib.Path(td) / "env.paper"   # NOT created
        cfg = Config(str(paper_env))
        got = (cfg.apex_env, cfg.allow_signed, cfg.economic_gate_signed, cfg.sqlite_path)
    results.append(("Config(env_path=<missing paper file>)",
                    got == ("LIVE", True, True, "data/live.sqlite3"), repr(got)))
    # 3) the same, but the file DOES exist with PAPER values -> still LIVE (no-shadow)
    with tempfile.TemporaryDirectory() as td:
        paper_env = pathlib.Path(td) / "env.paper"
        paper_env.write_text("APEX_ENV=PAPER\nAPEX_ALLOW_SIGNED=0\n"
                             "APEX_ECONOMIC_GATE_SIGNED=0\nAPEX_SQLITE_PATH=data/paper.sqlite3\n")
        cfg2 = Config(str(paper_env))
        got2 = (cfg2.apex_env, cfg2.allow_signed, cfg2.economic_gate_signed, cfg2.sqlite_path)
    results.append(("Config(env_path=<existing paper file>) with LIVE process env",
                    got2 == ("LIVE", True, True, "data/live.sqlite3"), repr(got2)))
    # 4) control: unset process env, existing file -> file values apply
    for k in ("APEX_ENV", "APEX_ALLOW_SIGNED", "APEX_ECONOMIC_GATE_SIGNED", "APEX_SQLITE_PATH"):
        del os.environ[k]
    with tempfile.TemporaryDirectory() as td:
        paper_env = pathlib.Path(td) / "env.paper"
        paper_env.write_text("APEX_ENV=PAPER\nAPEX_ALLOW_SIGNED=0\n"
                             "APEX_ECONOMIC_GATE_SIGNED=0\nAPEX_SQLITE_PATH=data/paper.sqlite3\n")
        cfg3 = Config(str(paper_env))
        got3 = (cfg3.apex_env, cfg3.allow_signed, cfg3.economic_gate_signed, cfg3.sqlite_path)
    results.append(("control: unset env + existing file", got3 == ("PAPER", False, False, "data/paper.sqlite3"), repr(got3)))
    # 5) control: unset process env, MISSING file -> defaults (RESEARCH)
    cfg4 = Config("/tmp/does_not_exist_V6/env.paper")
    got4 = (cfg4.apex_env, cfg4.allow_signed, cfg4.economic_gate_signed)
    results.append(("control: unset env + missing file -> defaults", got4 == ("RESEARCH", False, False), repr(got4)))
finally:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + " | " + detail)
