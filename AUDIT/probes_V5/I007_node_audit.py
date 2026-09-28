from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
matrix = (ROOT / "PHASE2_TRACEABILITY_MATRIX.md").read_text()
collected_path = ROOT / "AUDIT/probes_V5/I007_collect.out"
collected_lines = collected_path.read_text().splitlines()
collected = {
    line.strip() for line in collected_lines
    if line.startswith("tests/") and "::" in line
}
files = {item.split("::", 1)[0] for item in collected}
classes = set()
methods = set()
for item in collected:
    parts = item.split("::")
    if len(parts) >= 2:
        classes.add("::".join(parts[:2]))
    methods.add(item)

# Fully qualified matrix paths. Some matrix cells intentionally group class
# names with '+' or '/', so expand those separators after the module suffix.
refs = []
for line_no, line in enumerate(matrix.splitlines(), 1):
    for match in re.finditer(r"(tests/[^\s`|,()]+?\.py)(?:::(.+?))?(?=\s|`|\||,|\)|$)", line):
        path, suffix = match.group(1), match.group(2)
        if suffix is None:
            continue
        suffix = suffix.rstrip(".;:")
        # Strip punctuation included in markdown emphasis/table text.
        suffix = suffix.strip("*_")
        for group in re.split(r"[+/]", suffix):
            group = group.strip("*_;, ")
            if group:
                refs.append((line_no, path, group, match.group(0)))

missing_files = sorted({path for _, path, _, _ in refs if not (ROOT / path).is_file()})
missing_nodes = []
for line_no, path, node, raw in refs:
    if not (ROOT / path).is_file():
        continue
    # Dotted/slashed group references normalize to pytest's :: syntax.
    pieces = node.split("::")
    if len(pieces) == 1:
        candidate = f"{path}::{node}"
        exists = candidate in methods or candidate in classes
        # Pytest class collections emit child nodes rather than the parent ID.
        exists = exists or any(item.startswith(candidate + "::") for item in collected)
    else:
        candidate = path + "::" + "::".join(pieces)
        exists = candidate in methods
        if len(pieces) == 1:
            exists = exists or candidate in classes or any(item.startswith(candidate + "::") for item in collected)
    if not exists:
        missing_nodes.append((line_no, candidate, raw))

print(f"collected node IDs={len(collected)}; collected test files={len(files)}")
print(f"fully-qualified matrix reference components={len(refs)}")
print("reference groups are split on '+' and '/' (matrix shorthand), punctuation stripped")
print("missing test files:")
for path in missing_files:
    print(" ", path)
print("missing node components:")
for line_no, candidate, raw in missing_nodes:
    print(f"  PHASE2_TRACEABILITY_MATRIX.md:{line_no}: {candidate} [from {raw}]")
print(f"missing node component count={len(missing_nodes)}")
print("collection summary lines:")
for line in collected_lines[-6:]:
    print(line)
