#!/usr/bin/env python3
"""C-001 probe: Config() is built BEFORE the try/except in main() (run_apex.py:1132
vs 1133). Reproduce: run the real CLI with (a) a malformed .env, (b) an
unreadable .env, (c) a non-UTF8 .env via --env-file, and compare with (d) an
arg error raised INSIDE the try (--cells bad syntax) which IS handled.

No network: boot fails before any venue call; no .env in repo root is used.
"""
import subprocess, sys, os, tempfile, pathlib

ROOT = pathlib.Path("/home/user/Upstage")
tmp = pathlib.Path(tempfile.mkdtemp(prefix="c001-"))

def run(label, argv, env_extra=None):
    env = dict(os.environ)
    env.pop("APEX_DOTENV_PATH", None)      # make the default path deterministic
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, "scripts/run_apex.py", *argv],
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       timeout=120)
    tail = (p.stderr.strip().splitlines() or [""])[-3:]
    print(f"== {label} ==")
    print(f"argv={argv}")
    print(f"exit_code={p.returncode}")
    print(f"stdout_head={p.stdout.strip().splitlines()[:2]}")
    print(f"stderr_tail={tail}")
    print()

# (a) malformed .env (no '=' line) -> ValueError from parse_dotenv
bad = tmp / "malformed.env"
bad.write_text("THIS IS NOT A KEY VALUE LINE\n", encoding="utf-8")
run("malformed .env", ["boot", "--env-file", str(bad)])

# (b) unknown env name in .env -> ValueError from parse_dotenv
unk = tmp / "unknown.env"
unk.write_text("NOT_A_KNOWN_NAME=1\n", encoding="utf-8")
run("unknown name in .env", ["boot", "--env-file", str(unk)])

# (c) non-UTF8 .env -> UnicodeDecodeError from open(...).read iteration
binf = tmp / "binary.env"
binf.write_bytes(b"\xff\xfe\x00APEX_ENV=PAPER\n")
run("non-UTF8 .env", ["status", "--env-file", str(binf)])

# (d) control: a ValueError raised INSIDE the try (bad --cells) -> clean ERROR line
run("control: bad --cells (inside try)", ["bootstrap", "--cells", "bogus", "--env-file", str(tmp / "none.env")])

# (e) control: unreadable .env file -> PermissionError/FileNotFoundError path
missing = tmp / "does-not-exist.env"
run("missing --env-file (falls back, exists() guard)", ["status", "--env-file", str(missing)])
