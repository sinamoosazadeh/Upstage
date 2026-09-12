"""APEX_GEN5 configuration (§9.5-12, §2.5, G16).

Binding rules implemented here:
* EXACTLY nine environment variable names exist for the runtime — no more:
  APEX_ENV, APEX_ALLOW_SIGNED, APEX_ECONOMIC_GATE_SIGNED, TOOBIT_API_KEY,
  TOOBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID,
  TELEGRAM_WATCHDOG_CHAT_ID, APEX_SQLITE_PATH.
* ``.env`` is parsed with the standard library ONLY (python-dotenv is never
  added — §9.5-12). Real OS environment variables are NEVER shadowed by
  ``.env`` entries (OS env wins).
* Defaults per §2.5: APEX_ENV=RESEARCH, APEX_ALLOW_SIGNED=0,
  APEX_ECONOMIC_GATE_SIGNED=0; APEX_SQLITE_PATH default data/apex.sqlite3
  (Ch.5 physical store).
* Parameter values live ONLY in the six ``params/*.yaml`` files; code reads
  them through :func:`load_params` and never hardcodes them (§CP-1 cross-cut
  invariant). The YAML subset parser is strict and fail-closed.
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "ENV_NAMES",
    "RESERVED_PREFIXES",
    "ConfigurationError",
    "ApexConfig",
    "parse_env_file",
    "load_config",
    "load_params",
    "params_root",
    "validate_symbol",
    "validate_timeframe",
]

# §9.5-12 / G16 — exactly and only these nine names.
ENV_NAMES: tuple[str, ...] = (
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

# Secrets are never logged, serialized, or placed in exception strings (§2.5/G16).
SECRET_ENV_NAMES: frozenset[str] = frozenset(
    {"TOOBIT_API_KEY", "TOOBIT_API_SECRET", "TELEGRAM_BOT_TOKEN"}
)

RESERVED_PREFIXES: tuple[str, ...] = ("APEX_", "TOOBIT_", "TELEGRAM_")

# §2.5 defaults; Ch.5 default store path.
_DEFAULTS: dict[str, str] = {
    "APEX_ENV": "RESEARCH",
    "APEX_ALLOW_SIGNED": "0",
    "APEX_ECONOMIC_GATE_SIGNED": "0",
    "APEX_SQLITE_PATH": "data/apex.sqlite3",
}

_ALLOWED_ENV_VALUES = ("PAPER", "LIVE", "RESEARCH", "BACKTEST")  # §2.4; SHADOW does not exist

_PARAMS_FILES = (
    "universe_v1",
    "risk_defaults_v1",
    "setup_weights_v1",
    "quality_weights_v1",
    "toobit_wire_v1",
    "e11_params_v4",
)


class ConfigurationError(ValueError):
    """Fail-closed configuration violation (unknown env name, bad value, ...)."""


@dataclass(frozen=True)
class ApexConfig:
    """Resolved runtime configuration (env layer only; params via load_params)."""

    apex_env: str
    allow_signed: bool
    economic_gate_signed: bool
    sqlite_path: str
    toobit_api_key_set: bool
    toobit_api_secret_set: bool
    telegram_bot_token_set: bool
    telegram_owner_chat_id: str | None
    telegram_watchdog_chat_id: str | None


def parse_env_file(text: str) -> dict[str, str]:
    """Parse a ``.env`` document using only the standard library.

    Supported syntax (the minimal, deterministic subset): blank lines,
    ``#`` comment lines, optional ``export `` prefix, ``KEY=VALUE`` pairs,
    single/double-quoted values, inline ``#`` comments outside quotes.
    Duplicate keys fail closed.
    """
    out: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            raise ConfigurationError(f".env line {lineno}: expected KEY=VALUE")
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key or not all(ch.isalnum() or ch == "_" for ch in key):
            raise ConfigurationError(f".env line {lineno}: invalid key")
        if key in out:
            raise ConfigurationError(f".env line {lineno}: duplicate key {key}")
        if not (len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"')):
            # strip inline comment outside quotes before unquoting
            hash_pos = value.find(" #")
            if hash_pos >= 0:
                value = value[:hash_pos].rstrip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def load_config(
    env_path: str | os.PathLike[str] | None = ".env",
    environ: Mapping[str, str] | None = None,
) -> ApexConfig:
    """Resolve configuration. Precedence: OS env > .env file > §2.5 defaults.

    The .env file NEVER shadows an already-set OS environment variable.
    Unknown ``APEX_*`` / ``TOOBIT_*`` / ``TELEGRAM_*`` keys fail closed
    (the nine names are exhaustive). Secrets are exposed only as presence
    booleans — never as values.
    """
    env = dict(os.environ if environ is None else environ)
    if env_path is not None:
        p = pathlib.Path(env_path)
        if p.exists():
            for key, value in parse_env_file(p.read_text(encoding="utf-8")).items():
                if key.startswith(RESERVED_PREFIXES):
                    if key not in ENV_NAMES:
                        raise ConfigurationError(
                            f"unknown reserved environment name in .env: {key}"
                        )
                    env.setdefault(key, value)  # no shadowing of real OS env
    unknown = sorted(k for k in env if k.startswith(RESERVED_PREFIXES) and k not in ENV_NAMES)
    if unknown:
        raise ConfigurationError(f"unknown reserved environment name(s): {', '.join(unknown)}")

    apex_env = env.get("APEX_ENV", _DEFAULTS["APEX_ENV"])
    if apex_env not in _ALLOWED_ENV_VALUES:
        raise ConfigurationError(
            f"APEX_ENV must be one of {_ALLOWED_ENV_VALUES} (SHADOW does not exist)"
        )
    return ApexConfig(
        apex_env=apex_env,
        allow_signed=env.get("APEX_ALLOW_SIGNED", _DEFAULTS["APEX_ALLOW_SIGNED"]) == "1",
        economic_gate_signed=env.get(
            "APEX_ECONOMIC_GATE_SIGNED", _DEFAULTS["APEX_ECONOMIC_GATE_SIGNED"]
        )
        == "1",
        sqlite_path=env.get("APEX_SQLITE_PATH", _DEFAULTS["APEX_SQLITE_PATH"]),
        toobit_api_key_set=bool(env.get("TOOBIT_API_KEY")),
        toobit_api_secret_set=bool(env.get("TOOBIT_API_SECRET")),
        telegram_bot_token_set=bool(env.get("TELEGRAM_BOT_TOKEN")),
        telegram_owner_chat_id=env.get("TELEGRAM_OWNER_CHAT_ID") or None,
        telegram_watchdog_chat_id=env.get("TELEGRAM_WATCHDOG_CHAT_ID") or None,
    )


# ---------------------------------------------------------------------------
# params/*.yaml — the six frozen parameter files (§9.5). Code reads, never
# hardcodes. Parsed with a strict YAML-subset reader (stdlib only; PyYAML is
# not in the frozen SBOM).
# ---------------------------------------------------------------------------

_PARAMS_CACHE: dict[str, dict[str, Any]] = {}


def params_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "params"


def _coerce_scalar(token: str) -> Any:
    t = token.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in ("'", '"'):
        return t[1:-1]
    low = t.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _parse_flow_list(token: str) -> list[Any]:
    inner = token.strip()[1:-1].strip()
    if not inner:
        return []
    return [_coerce_scalar(part) for part in inner.split(",")]


def _parse_simple_yaml(text: str, path: str) -> dict[str, Any]:
    """Strict YAML subset: nested block mappings (2-space indent), flow lists,
    scalars, comments. Anything else fails closed (no silent guessing)."""
    root: dict[str, Any] = {}
    # stack of (indent, dict)
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- "):
            raise ConfigurationError(f"{path}:{lineno}: block lists are not supported")
        if ":" not in line:
            raise ConfigurationError(f"{path}:{lineno}: expected 'key:' mapping line")
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.split(" #", 1)[0].strip() if " #" in rest else rest.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigurationError(f"{path}:{lineno}: bad indentation")
        parent = stack[-1][1]
        if key in parent:
            raise ConfigurationError(f"{path}:{lineno}: duplicate key {key}")
        if rest == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        elif rest.startswith("[") and rest.endswith("]"):
            parent[key] = _parse_flow_list(rest)
        else:
            parent[key] = _coerce_scalar(rest)
    return root


def load_params(name: str) -> dict[str, Any]:
    """Load one of the six frozen params files (cached). Names are fixed by
    §9.5; any other name fails closed."""
    if name not in _PARAMS_FILES:
        raise ConfigurationError(f"unknown params file: {name} (§9.5 defines six)")
    if name not in _PARAMS_CACHE:
        path = params_root() / f"{name}.yaml"
        if not path.exists():
            raise ConfigurationError(f"missing params file: {path}")
        _PARAMS_CACHE[name] = _parse_simple_yaml(path.read_text(encoding="utf-8"), str(path))
    return _PARAMS_CACHE[name]


def validate_symbol(symbol: str) -> str:
    """E-VAL-021 lint semantics: symbol must be in the frozen universe
    (params/universe_v1.yaml); otherwise fail."""
    universe = load_params("universe_v1")
    if symbol not in universe["symbols"]:
        raise ConfigurationError(f"E-VAL-021: invalid symbol not in Core-10: {symbol}")
    return symbol


def validate_timeframe(timeframe: str) -> str:
    """E-VAL-022 lint semantics: timeframe must be one of the frozen 14
    (8h supported, 3d NOT supported); otherwise fail."""
    universe = load_params("universe_v1")
    if timeframe not in universe["timeframes"]:
        raise ConfigurationError(f"E-VAL-022: invalid timeframe not in the 14: {timeframe}")
    return timeframe
