"""pytest configuration for the CP-7 (and later) test tree.

Two paths are made importable so that a test double can live in ONE place and
be shared by ``tests/unit`` and ``tests/integration`` (G9: mocks/fakes are
lawful ONLY as test doubles behind test code):

* the repository root (so ``import apex…`` works regardless of the runner's
  import mode), and
* ``tests/`` itself (so ``from fake_toobit_responder import …`` works).

No product logic lives here (P11: tests validate the design, they never
redefine it).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent

for _path in (str(_ROOT), str(_TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
