"""APEX_GEN5 data-catalog performance tier (§3.12 module layout:
`performance/`): tier recompute schedules, stability/cost annotations,
and the ORGANISMIC LRU-100 cache.

§3.12 operating rules implemented here:
- ATOM is never cached; MOLECULAR cached for 5 candles; ORGANISMIC cached
  for 50+ candles with LRU-100 eviction.
- A failure at the ATOM tier stops the whole pipeline.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

# Tier recompute schedules (§3.12 data-flow architecture)
ATOM_RECOMPUTE = "every_candle"
MOLECULAR_RECOMPUTE = "every_5_candles"
ORGANISMIC_RECOMPUTE = "on_demand"
ATOM_CACHE_CANDLES = 0       # never cached
MOLECULAR_CACHE_CANDLES = 5  # cached for 5 candles
ORGANISMIC_CACHE_CANDLES = 50  # cached for 50+ candles
ORGANISMIC_LRU_MAX = 100     # LRU-100 eviction policy

# Uniform §3.12 annotations (template fields).
DEFAULT_STABILITY = "medium"
DEFAULT_COST = "low"


class LRUCache:
    """LRU cache with a fixed capacity (ORGANISMIC LRU-100)."""

    def __init__(self, capacity: int = ORGANISMIC_LRU_MAX) -> None:
        self._capacity = capacity
        self._store: "OrderedDict[Any, Any]" = OrderedDict()

    def get(self, key: Any) -> Optional[Any]:
        if key not in self._store:
            return None
        value = self._store.pop(key)
        self._store[key] = value  # touch → most recent
        return value

    def put(self, key: Any, value: Any) -> None:
        if key in self._store:
            self._store.pop(key)
        self._store[key] = value
        while len(self._store) > self._capacity:
            self._store.popitem(last=False)  # evict oldest

    def __len__(self) -> int:
        return len(self._store)


class TierCache:
    """Per-tier cache discipline for catalog.get.

    ATOM: never cached (compute every call).
    MOLECULAR: served from cache while bar age < 5 candles.
    ORGANISMIC: served from cache while bar age < 50 candles (LRU-100).
    Cache entries are invalidated when code_revision changes (AI.12
    idempotency layer: cached results discarded on code_version change).
    """

    def __init__(self) -> None:
        self._mole: Dict[Tuple[str, str, str], Tuple[int, Any]] = {}
        self._orgn = LRUCache(ORGANISMIC_LRU_MAX)
        self._code_revision: Optional[str] = None

    def set_code_revision(self, code_revision: str) -> None:
        if self._code_revision != code_revision:
            self._code_revision = code_revision
            self._mole.clear()
            self._orgn = LRUCache(ORGANISMIC_LRU_MAX)

    def lookup(self, super_layer: str, key: Tuple[str, str, str],
               bar_index: int) -> Optional[Any]:
        if super_layer == "ATOM":
            return None  # ATOM is never cached
        if super_layer == "MOLE":
            entry = self._mole.get(key)
            if entry is None:
                return None
            index, value = entry
            if bar_index - index < MOLECULAR_CACHE_CANDLES:
                return value
            return None
        if super_layer == "ORGN":
            entry = self._orgn.get(key)
            if entry is None:
                return None
            index, value = entry
            if bar_index - index < ORGANISMIC_CACHE_CANDLES:
                return value
            return None
        return None

    def store(self, super_layer: str, key: Tuple[str, str, str],
              bar_index: int, value: Any) -> None:
        if super_layer == "ATOM":
            return  # never cached
        if super_layer == "MOLE":
            self._mole[key] = (bar_index, value)
        elif super_layer == "ORGN":
            self._orgn.put(key, (bar_index, value))
