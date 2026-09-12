"""CP-1 config tests — MATRIX Part I: test_env_names_exact_no_shadow +
test_no_dotenv_bypass (§9.5-12, §2.5, G16)."""
from __future__ import annotations

import pathlib
import sys

import pytest

from apex import config as apex_config
from apex.config import (
    ENV_NAMES,
    ApexConfig,
    ConfigurationError,
    load_config,
    parse_env_file,
    _parse_simple_yaml,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# §9.5-12 — exactly and only these nine, in blueprint order.
EXPECTED_ENV_NAMES = (
    "APEX_ENV",
    "APEX_ALLOW_SIGNED",
    "APEX_ECONOMIC_GATE_SIGNED",
    "TOOBIT_API_KEY",
    "TOOBIT_API_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_CHAT_ID",
    "TELEGRAM_WATCHDOG_CHAT_ID",
    "APEX_SQLITE_PATH",
)


def test_env_names_exact() -> None:
    assert ENV_NAMES == EXPECTED_ENV_NAMES


def test_defaults_per_2_5(tmp_path: pathlib.Path) -> None:
    cfg = load_config(env_path=tmp_path / "absent.env", environ={})
    assert cfg == ApexConfig(
        apex_env="RESEARCH",
        allow_signed=False,
        economic_gate_signed=False,
        sqlite_path="data/apex.sqlite3",
        toobit_api_key_set=False,
        toobit_api_secret_set=False,
        telegram_bot_token_set=False,
        telegram_owner_chat_id=None,
        telegram_watchdog_chat_id=None,
    )


def test_env_file_parsed_stdlib(tmp_path: pathlib.Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "export APEX_ENV=PAPER\n"
        "APEX_ALLOW_SIGNED=1\n"
        'TELEGRAM_OWNER_CHAT_ID="12345" # inline comment\n'
        "APEX_SQLITE_PATH=/tmp/x.sqlite3\n",
        encoding="utf-8",
    )
    cfg = load_config(env_path=env, environ={})
    assert cfg.apex_env == "PAPER"
    assert cfg.allow_signed is True
    assert cfg.telegram_owner_chat_id == "12345"
    assert cfg.sqlite_path == "/tmp/x.sqlite3"


def test_no_shadow_of_real_os_env(tmp_path: pathlib.Path) -> None:
    """A .env value must NEVER shadow an already-set OS environment variable."""
    env = tmp_path / ".env"
    env.write_text("APEX_ENV=LIVE\n", encoding="utf-8")
    cfg = load_config(env_path=env, environ={"APEX_ENV": "PAPER"})
    assert cfg.apex_env == "PAPER"


def test_unknown_reserved_name_fails_closed(tmp_path: pathlib.Path) -> None:
    env = tmp_path / ".env"
    env.write_text("APEX_NOT_A_REAL_KNOB=1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(env_path=env, environ={})


def test_shadow_env_rejected() -> None:
    with pytest.raises(ConfigurationError):
        load_config(env_path=None, environ={"APEX_ENV": "SHADOW"})


def test_parse_env_file_rejects_malformed() -> None:
    with pytest.raises(ConfigurationError):
        parse_env_file("NOT_A_PAIR\n")
    with pytest.raises(ConfigurationError):
        parse_env_file("APEX_ENV=PAPER\nAPEX_ENV=LIVE\n")


def test_no_dotenv_bypass() -> None:
    """python-dotenv (or any third-party env loader) is never imported by
    runtime code, and not present in the lock (ADR-P2-002)."""
    assert "dotenv" not in sys.modules
    lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "dotenv" not in lock
    src = (REPO_ROOT / "apex" / "config.py").read_text(encoding="utf-8")
    assert "import dotenv" not in src and "from dotenv" not in src


def test_secret_values_never_surface_in_config_object() -> None:
    cfg = load_config(
        env_path=None,
        environ={"TOOBIT_API_KEY": "sekrit-key-value", "TELEGRAM_BOT_TOKEN": "secret-bot-token-value"},
    )
    text = repr(cfg)
    assert "sekrit-key-value" not in text and "secret-bot-token-value" not in text
    assert cfg.toobit_api_key_set is True and cfg.telegram_bot_token_set is True


def test_yaml_subset_parser() -> None:
    doc = (
        "# header\n"
        "symbols: [BTCUSDT, ETHUSDT]\n"
        "nested:\n"
        "  a: 1\n"
        "  b: 0.5\n"
        "  c: ISOLATED\n"
        "  d: true\n"
        "  e: 'quoted'\n"
        "flag: false\n"
    )
    data = _parse_simple_yaml(doc, "inline")
    assert data["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert data["nested"] == {"a": 1, "b": 0.5, "c": "ISOLATED", "d": True, "e": "quoted"}
    assert data["flag"] is False
    with pytest.raises(ConfigurationError):
        _parse_simple_yaml("- block_list_item\n", "inline")
    with pytest.raises(ConfigurationError):
        _parse_simple_yaml("a: 1\na: 2\n", "inline")
