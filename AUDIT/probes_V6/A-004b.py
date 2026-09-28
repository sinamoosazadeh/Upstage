"""V6 probe A-004b: parent-aware duplicate-key scan of the real params YAMLs.
Tracks the mapping context via an indentation stack so the same key under
DIFFERENT parents (e.g. '1m' under two different tables) is not a false hit.
Read-only over the repository files.
"""
import sys
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import apex.config as C


def dup_keys(text):
    """Return list of (parent_chain, key, first_line, dup_line)."""
    stack = []  # (indent, parent_chain)
    seen = {}   # parent_chain -> {key: lineno}
    out = []
    for ln, raw in enumerate(text.splitlines(), 1):
        s = raw.split("#")[0].rstrip() if '"' not in raw and "'" not in raw else raw.rstrip()
        if not s.strip():
            continue
        indent = len(s) - len(s.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = "/".join(x[1] for x in stack)
        content = s.strip()
        if content.startswith("- "):
            continue  # sequence item, keys inside are inline maps (checked separately)
        # flow map inside a value: check duplicates inside it too
        if ":" in content and ("{" in content):
            # e.g. 1m: {Q_schema: 0.20, ...}
            try:
                key, rest = content.split(":", 1)
            except ValueError:
                key = None
            if key is not None and "{" in rest:
                inner = rest[rest.index("{") + 1:rest.rindex("}")].strip()
                if inner:
                    lseen = {}
                    for chunk in inner.split(","):
                        if ":" in chunk:
                            k = chunk.split(":", 1)[0].strip()
                            if k in lseen:
                                out.append((parent + "/" + key.strip(), k, ln, ln))
                            lseen[k] = ln
        if ":" not in content:
            continue
        key = content.split(":", 1)[0].strip()
        if key.startswith("-"):
            continue
        if key in seen.get(parent, {}):
            out.append((parent or "<root>", key, seen[parent][key], ln))
        seen.setdefault(parent, {})[key] = ln
        rest = content.split(":", 1)[1].strip()
        if rest == "":
            stack.append((indent, key))
    return out


for fname in sorted(C.PARAMS_FILES.values()):
    path = C.PARAMS_DIR / fname
    if not path.exists():
        print("%-28s MISSING (device-only)" % fname)
        continue
    d = dup_keys(path.read_text())
    print("%-28s %s" % (fname, "NO duplicate keys within any mapping" if not d else d))
