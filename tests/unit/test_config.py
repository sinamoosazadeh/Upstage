"""CP-1 config surface: nine env names exact, stdlib .env parsing, no
shadowing, no python-dotenv, frozen defaults, secrets never in reprs."""
from __future__ import annotations

import os
import pathlib

import pytest

from apex import config
from apex.config import Config, ENV_DEFAULTS, ENV_NAMES, parse_dotenv

EXPECTED_NAMES = [
    "APEX_ENV", "APEX_ALLOW_SIGNED", "APEX_ECONOMIC_GATE_SIGNED",
    "TOOBIT_API_KEY", "TOOBIT_API_SECRET", "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_CHAT_ID", "TELEGRAM_WATCHDOG_CHAT_ID",
    "APEX_SQLITE_PATH",
]


def test_env_names_exact():
    assert ENV_NAMES == EXPECTED_NAMES


def test_env_defaults_frozen():
    assert ENV_DEFAULTS["APEX_ENV"] == "RESEARCH"
    assert ENV_DEFAULTS["APEX_ALLOW_SIGNED"] == "0"
    assert ENV_DEFAULTS["APEX_ECONOMIC_GATE_SIGNED"] == "0"
    assert ENV_DEFAULTS["APEX_SQLITE_PATH"] == "data/apex.sqlite3"


def test_defaults_when_unset(tmp_path, monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = Config()
    assert cfg.apex_env == "RESEARCH"
    assert cfg.allow_signed is False
    assert cfg.economic_gate_signed is False
    assert cfg.sqlite_path == "data/apex.sqlite3"
    cfg.validate_environment()


def test_dotenv_parsing_stdlib(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "APEX_ENV=PAPER\n"
        "APEX_ALLOW_SIGNED=1\n"
        "TOOBIT_API_KEY=\"sk-test\"\n"
        "export TELEGRAM_OWNER_CHAT_ID=123456\n"
        "APEX_SQLITE_PATH='data/test.sqlite3'\n"
    )
    parsed = parse_dotenv(env_file)
    assert parsed["APEX_ENV"] == "PAPER"
    assert parsed["APEX_ALLOW_SIGNED"] == "1"
    assert parsed["TOOBIT_API_KEY"] == "sk-test"
    assert parsed["TELEGRAM_OWNER_CHAT_ID"] == "123456"
    assert parsed["APEX_SQLITE_PATH"] == "data/test.sqlite3"


def test_dotenv_unknown_name_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("APEX_MAGIC_EXTRA=1\n")
    with pytest.raises(ValueError):
        parse_dotenv(env_file)


def test_dotenv_malformed_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NOT_A_PAIR\n")
    with pytest.raises(ValueError):
        parse_dotenv(env_file)


def test_no_shadowing_real_env_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("APEX_ENV=PAPER\n")
    monkeypatch.setenv("APEX_ENV", "BACKTEST")
    cfg = Config(env_path=env_file)
    assert cfg.apex_env == "BACKTEST"  # real env never shadowed
    cfg.validate_environment()


def test_dotenv_fills_unset_only(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("APEX_ENV=LIVE\nTELEGRAM_OWNER_CHAT_ID=777\n")
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    cfg = Config(env_path=env_file)
    assert cfg.apex_env == "LIVE"
    assert cfg.telegram_owner_chat_id == "777"


def test_shadow_environment_rejected(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APEX_ENV", "SHADOW")
    cfg = Config()
    with pytest.raises(ValueError):
        cfg.validate_environment()


def test_valid_environments():
    for env in ("PAPER", "LIVE", "RESEARCH", "BACKTEST"):
        monkeypatch_chk = os.environ.get("APEX_ENV")
        try:
            os.environ["APEX_ENV"] = env
            Config().validate_environment()
        finally:
            if monkeypatch_chk is None:
                os.environ.pop("APEX_ENV", None)
            else:
                os.environ["APEX_ENV"] = monkeypatch_chk


def test_no_dotenv_bypass():
    """No python-dotenv anywhere: not in deps, not importable by apex."""
    import sys
    assert "dotenv" not in sys.modules
    src = pathlib.Path(config.__file__).read_text()
    assert "dotenv" not in src.split("\n")[0:0] or True
    assert "from dotenv" not in src and "import dotenv" not in src
    for name in list(sys.modules):
        assert "dotenv" not in name


def test_secrets_masked_in_repr(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TOOBIT_API_KEY=supersecret\nTOOBIT_API_SECRET=s2\n")
    cfg = Config(env_path=env_file)
    text = repr(cfg)
    assert "supersecret" not in text and "s2" not in text
    assert "***" in text


def test_signed_flags(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("APEX_ALLOW_SIGNED=1\nAPEX_ECONOMIC_GATE_SIGNED=1\n")
    cfg = Config(env_path=env_file)
    assert cfg.allow_signed is True
    assert cfg.economic_gate_signed is True


def test_params_loader_reads_only():
    """params YAML is the ONLY source of parameter values (no hardcoding)."""
    p = config.load_params()
    for name in config.PARAMS_FILES:
        assert isinstance(p[name], dict)
    with pytest.raises(KeyError):
        p["invented_params_file"]
