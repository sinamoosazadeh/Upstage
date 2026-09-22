"""APEX_GEN5 runtime configuration.

Blueprint: §2.5 Security Contract + §9.5 directive 12 (env names) + P17/G16.
- The nine runtime environment variable names, exactly and only:
  APEX_ENV, APEX_ALLOW_SIGNED, APEX_ECONOMIC_GATE_SIGNED, TOOBIT_API_KEY,
  TOOBIT_API_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID,
  TELEGRAM_WATCHDOG_CHAT_ID, APEX_SQLITE_PATH.
- `.env` parsing uses the Python standard library ONLY (no python-dotenv —
  ADR-P2-002/G16). A value present in the REAL process environment is never
  shadowed by a `.env` file (no-shadow rule; `.env` fills only unset names).
- Secrets are read as strings and never logged, stored in SQLite, embedded
  in exception messages, or printed (G16/§2.5). The GitHub token is not a
  runtime secret.
- Defaults (frozen): APEX_ENV=RESEARCH, APEX_ALLOW_SIGNED=0,
  APEX_ECONOMIC_GATE_SIGNED=0, APEX_SQLITE_PATH=data/apex.sqlite3.

Also hosts the parameter-package loader: parameter VALUES exist only in
`params/*.yaml` (frozen literal values from §9.5 / Ch.10 / §2.1 / Ch.16);
runtime code reads them here and never hardcodes them (§9.5-10, P8).
The runtime SBOM (Ch.1, nine pins) contains no YAML library, so the loader
uses a strict stdlib parser for the frozen "APEX params subset" of YAML
(block/flow maps, block/flow sequences, comments, quoted/plain scalars with
bool/int/float/null inference). Anything outside that subset raises
ValueError — fail-closed, never a guess. (Recorded: DECISION_LOG CP-1.)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# The nine frozen environment names (§9.5 directive 12). Anything else is an
# invented runtime env surface and forbidden.
ENV_NAMES: List[str] = [
    "APEX_ENV",
    "APEX_ALLOW_SIGNED",
    "APEX_ECONOMIC_GATE_SIGNED",
    "TOOBIT_API_KEY",
    "TOOBIT_API_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OWNER_CHAT_ID",
    "TELEGRAM_WATCHDOG_CHAT_ID",
    "APEX_SQLITE_PATH",
]

ENV_DEFAULTS: Dict[str, str] = {
    "APEX_ENV": "RESEARCH",           # §2.5: APEX_ENV default RESEARCH
    "APEX_ALLOW_SIGNED": "0",         # §2.5: default 0
    "APEX_ECONOMIC_GATE_SIGNED": "0",  # §2.5: default 0
    "APEX_SQLITE_PATH": "data/apex.sqlite3",  # G16: default data/apex.sqlite3
}

VALID_ENVIRONMENTS = ("PAPER", "LIVE", "RESEARCH", "BACKTEST")  # no SHADOW

_SENSITIVE = frozenset(
    {"TOOBIT_API_KEY", "TOOBIT_API_SECRET", "TELEGRAM_BOT_TOKEN"}
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PARAMS_DIR = REPO_ROOT / "params"

# Parameter YAML files (normative tree §9.5). Values are frozen literals from
# the blueprint; the loader only reads, never derives.
PARAMS_FILES: Dict[str, str] = {
    "universe": "universe_v1.yaml",
    "risk_defaults": "risk_defaults_v1.yaml",
    "setup_weights": "setup_weights_v1.yaml",
    "quality_weights": "quality_weights_v1.yaml",
    "toobit_wire": "toobit_wire_v1.yaml",
    "e11_params": "e11_params_v4.yaml",
    "e11_classifier": "e11_classifier_v1.yaml",
    "e11_training": "e11_training_v1.yaml",
    "paper_account": "paper_account_v1.yaml",
    "decision_runtime": "decision_runtime_v1.yaml",
}


# ---------------------------------------------------------------------------
# .env parsing (stdlib only; no python-dotenv)
# ---------------------------------------------------------------------------

def parse_dotenv(path: str | os.PathLike[str]) -> Dict[str, str]:
    """Parse a `.env` file into a dict of {NAME: value}.

    Grammar: ``NAME=VALUE`` lines; ``#`` comments; optional ``export ``
    prefix (tolerated, not required); surrounding quotes (single or double)
    stripped; blank lines skipped. Malformed lines raise ValueError
    (fail-closed: a broken secret file must not silently degrade).
    Only the nine ENV_NAMES are admitted; any other key raises ValueError
    (invented env surface is a failed deliverable, §9.5-12).
    """
    parsed: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                raise ValueError(
                    f"malformed .env line {lineno}: expected NAME=VALUE"
                )
            name, _, value = line.partition("=")
            name = name.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if name not in ENV_NAMES:
                raise ValueError(
                    f"unknown runtime env name {name!r} in .env (line {lineno}); "
                    f"the only lawful names are {ENV_NAMES}"
                )
            parsed[name] = value
    return parsed


def _load_env(env_path: str | os.PathLike[str] | None = None) -> Dict[str, str]:
    """Effective environment = process env (authoritative) ∪ .env fill.

    No-shadow rule: a name already set in the real process environment is
    NEVER overwritten by the .env file.
    """
    env: Dict[str, str] = dict(os.environ)
    path = env_path if env_path is not None else os.environ.get(
        "APEX_DOTENV_PATH", ".env"
    )
    if path and os.path.exists(path):
        for name, value in parse_dotenv(path).items():
            if name not in os.environ:  # no shadowing of real env
                env[name] = value
    return env


class Config:
    """Frozen runtime configuration surface (nine env names, defaults)."""

    def __init__(self, env_path: str | os.PathLike[str] | None = None) -> None:
        self._env = _load_env(env_path)

    # -- plain accessors ----------------------------------------------------
    @property
    def apex_env(self) -> str:
        return self._env.get("APEX_ENV", ENV_DEFAULTS["APEX_ENV"])

    @property
    def allow_signed(self) -> bool:
        return self._env.get("APEX_ALLOW_SIGNED",
                             ENV_DEFAULTS["APEX_ALLOW_SIGNED"]) == "1"

    @property
    def economic_gate_signed(self) -> bool:
        return self._env.get("APEX_ECONOMIC_GATE_SIGNED",
                             ENV_DEFAULTS["APEX_ECONOMIC_GATE_SIGNED"]) == "1"

    @property
    def toobit_api_key(self) -> str:
        return self._env.get("TOOBIT_API_KEY", "")

    @property
    def toobit_api_secret(self) -> str:
        return self._env.get("TOOBIT_API_SECRET", "")

    @property
    def telegram_bot_token(self) -> str:
        return self._env.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_owner_chat_id(self) -> str:
        return self._env.get("TELEGRAM_OWNER_CHAT_ID", "")

    @property
    def telegram_watchdog_chat_id(self) -> str:
        return self._env.get("TELEGRAM_WATCHDOG_CHAT_ID", "")

    @property
    def sqlite_path(self) -> str:
        return self._env.get("APEX_SQLITE_PATH", ENV_DEFAULTS["APEX_SQLITE_PATH"])

    # -- validation ---------------------------------------------------------
    def validate_environment(self) -> None:
        """Fail closed: unknown APEX_ENV value raises ValueError."""
        if self.apex_env not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"APEX_ENV={self.apex_env!r} is not one of "
                f"{VALID_ENVIRONMENTS} (SHADOW does not exist)"
            )

    def __repr__(self) -> str:  # never leaks secret values (G16)
        masked = {}
        for name in ENV_NAMES:
            value = self._env.get(name)
            if value is None:
                continue
            masked[name] = "***" if name in _SENSITIVE else value
        return f"Config({masked!r})"


# ---------------------------------------------------------------------------
# Strict stdlib parser for the frozen "APEX params subset" of YAML.
# Supported (exactly what params/*.yaml uses): comments, block mappings,
# block sequences, flow mappings {k: v}, flow sequences [a, b], double- and
# single-quoted scalars, plain scalars with true/false/null/int/float/str
# inference. No anchors, aliases, tags, block scalars, or multi-documents.
# Unsupported syntax raises ValueError (fail-closed, §9.5-7).
# ---------------------------------------------------------------------------

_TRUE = {"true", "True", "TRUE"}
_FALSE = {"false", "False", "FALSE"}
_NULL = {"null", "Null", "NULL", "~", ""}
_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")


def _strip_comment(line: str) -> str:
    """Remove a `#` comment unless it is inside quotes."""
    out: List[str] = []
    in_s, in_d = False, False
    for ch in line:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        if ch == "#" and not in_s and not in_d:
            break
        out.append(ch)
    return "".join(out)


def _parse_scalar(text: str) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    if text in _NULL:
        return None
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text) and re.search(r"[.eE]", text):
        return float(text)
    return text


class _YamlSubsetParser:
    """Small recursive-descent parser over pre-split logical lines."""

    def __init__(self, text: str) -> None:
        self._lines: List[Tuple[int, str]] = []
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = _strip_comment(raw).rstrip()
            if stripped.strip():
                self._lines.append((lineno, stripped))
        self._pos = 0

    def _peek(self) -> Tuple[int, str] | None:
        if self._pos >= len(self._lines):
            return None
        return self._lines[self._pos]

    def _next(self) -> Tuple[int, str]:
        item = self._lines[self._pos]
        self._pos += 1
        return item

    def parse(self) -> Any:
        if self._peek() is None:
            return None
        value = self._parse_node(indent=0)
        if self._peek() is not None:
            lineno, line = self._peek()  # type: ignore[misc]
            raise ValueError(
                f"params YAML line {lineno}: trailing content {line!r}"
            )
        return value

    def _parse_node(self, indent: int) -> Any:
        lineno, line = self._peek()  # type: ignore[misc]
        content = line[indent:].strip()
        if content.startswith("- ") or content == "-":
            return self._parse_block_seq(indent)
        if ":" in content:
            # distinguish "key: value" / "key:" (block map) from flow map
            key_part, sep, rest = content.partition(":")
            if sep and (
                rest.strip() == "" or rest.strip().startswith(("{", "["))
            ):
                if rest.strip() == "" and self._next_block_is_mapping(indent):
                    return self._parse_block_map(indent)
                if rest.strip().startswith(("{", "[")):
                    return self._parse_block_map(indent)
                # "key:" with an empty value and no nested block → null value
                self._next()
                return {key_part.strip(): None}
            return self._parse_block_map(indent)
        if content.startswith(("[", "{")):
            self._next()
            return self._parse_flow(line[indent:].strip())
        raise ValueError(
            f"params YAML line {lineno}: unsupported node {line!r} "
            f"(outside the frozen APEX params subset)"
        )

    def _next_block_is_mapping(self, indent: int) -> bool:
        """True when the line AFTER the current one is more indented."""
        if self._pos + 1 >= len(self._lines):
            return False
        nxt_line = self._lines[self._pos + 1][1]
        return len(nxt_line) - len(nxt_line.lstrip()) > indent

    def _parse_block_map(self, indent: int) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        while True:
            item = self._peek()
            if item is None:
                break
            lineno, line = item
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(
                    f"params YAML line {lineno}: bad indentation {line!r}"
                )
            content = line[indent:].strip()
            if content.startswith("- "):
                break  # a sequence at the same indent ends this map
            key_part, sep, rest = content.partition(":")
            if not sep:
                raise ValueError(
                    f"params YAML line {lineno}: expected 'key: value', got "
                    f"{line!r}"
                )
            key = _parse_scalar(key_part.strip())
            rest = rest.strip()
            self._next()
            if rest == "":
                nxt = self._peek()
                if nxt is not None:
                    nxt_indent = len(nxt[1]) - len(nxt[1].lstrip())
                    if nxt_indent > indent:
                        result[key] = self._parse_node(nxt_indent)
                    else:
                        result[key] = None
                else:
                    result[key] = None
            elif rest.startswith(("{", "[")):
                result[key] = self._parse_flow(rest)
            else:
                result[key] = _parse_scalar(rest)
        return result

    def _parse_block_seq(self, indent: int) -> List[Any]:
        result: List[Any] = []
        while True:
            item = self._peek()
            if item is None:
                break
            lineno, line = item
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(
                    f"params YAML line {lineno}: bad indentation {line!r}"
                )
            content = line[indent:].strip()
            if not (content == "-" or content.startswith("- ")):
                break
            self._next()
            rest = content[1:].strip()
            if rest == "":
                nxt = self._peek()
                if nxt is not None and (
                    len(nxt[1]) - len(nxt[1].lstrip()) > indent
                ):
                    result.append(self._parse_node(
                        len(nxt[1]) - len(nxt[1].lstrip())))
                else:
                    result.append(None)
            elif rest.startswith(("{", "[")):
                result.append(self._parse_flow(rest))
            elif ":" in rest:
                # inline "key: value" item → single-entry map
                k, _, v = rest.partition(":")
                result.append({_parse_scalar(k.strip()): _parse_scalar(v.strip())})
            else:
                result.append(_parse_scalar(rest))
        return result

    def _parse_flow(self, text: str) -> Any:
        text = text.strip()
        if text.startswith("{"):
            if not text.endswith("}"):
                raise ValueError(f"unterminated flow map: {text!r}")
            inner = text[1:-1].strip()
            result: Dict[str, Any] = {}
            if not inner:
                return result
            for chunk in self._split_flow(inner):
                k, _, v = chunk.partition(":")
                if not _:
                    raise ValueError(f"flow map entry without ':' {chunk!r}")
                result[_parse_scalar(k.strip())] = _parse_scalar(v.strip())
            return result
        if text.startswith("["):
            if not text.endswith("]"):
                raise ValueError(f"unterminated flow sequence: {text!r}")
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [
                _parse_scalar(chunk.strip())
                for chunk in self._split_flow(inner)
            ]
        raise ValueError(f"unsupported flow node: {text!r}")

    @staticmethod
    def _split_flow(inner: str) -> List[str]:
        parts: List[str] = []
        buf: List[str] = []
        in_s = in_d = False
        for ch in inner:
            if ch == "'" and not in_d:
                in_s = not in_s
            elif ch == '"' and not in_s:
                in_d = not in_d
            if ch == "," and not in_s and not in_d:
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf))
        return parts


def _load_yaml(name: str) -> Dict[str, Any]:
    """Load one params YAML. Fail-closed on absence/corruption."""
    fname = PARAMS_FILES[name]
    path = PARAMS_DIR / fname
    if not path.exists():
        raise FileNotFoundError(
            f"parameter file {fname} missing from params/ (normative tree §9.5)"
        )
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        data = _YamlSubsetParser(text).parse()
    except ValueError as exc:
        raise ValueError(f"corrupt parameter file {fname}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"parameter file {fname} must contain a YAML mapping")
    return data


class Params:
    """Read-only view of the six frozen parameter YAMLs.

    Values are loaded lazily once and cached; the loader never mutates,
    derives, or re-interpolates a value (§9.5 / P8).
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def __getitem__(self, name: str) -> Dict[str, Any]:
        if name not in PARAMS_FILES:
            raise KeyError(f"unknown parameter file {name!r}")
        if name not in self._cache:
            self._cache[name] = _load_yaml(name)
        return self._cache[name]

    def get(self, name: str, default: Any = None) -> Any:
        try:
            return self[name]
        except KeyError:
            return default

    def universe(self) -> Dict[str, Any]:
        return self["universe"]

    def risk_defaults(self) -> Dict[str, Any]:
        return self["risk_defaults"]

    def setup_weights(self) -> Dict[str, Any]:
        return self["setup_weights"]

    def quality_weights(self) -> Dict[str, Any]:
        return self["quality_weights"]

    def toobit_wire(self) -> Dict[str, Any]:
        return self["toobit_wire"]

    def e11_params(self) -> Dict[str, Any]:
        return self["e11_params"]


def load_params() -> Params:
    """Module-level convenience accessor for the frozen parameter package."""
    return Params()
