"""AI.10 T-AD-001 / T-AD-002 + AI.13 G-ADAPTER-001 — the adapter-conformance
harness (read-only v2/v3 → v4.0.0 migration, ADR-P2-009).

Rules
-----
* Adapters are **read-only transformations**: they never mutate engine state,
  never write the store, and never enter a live v4 decision path (§9.9
  "historical interface versions"; AI.12 Phase-7 prohibition).
* The harness dispatches to the *real* in-tree adapters
  (``load_v3_adapter`` in E05/E06, the ``order_book_imbalance → obi_proxy``
  rename of AA.3/B04) and fails closed for any engine whose chapter defines no
  adapter — it never invents a translation.
* ADR-P2-009: this repository holds no v2/v3 data set, so the 100-legacy-sample
  leg of G-ADAPTER-001 cannot be sourced without fabrication. The harness
  therefore (a) runs real synthetic v4-derived self-checks, (b) accepts a
  user-provided legacy export, and (c) reports the real-data gate as
  ``OPEN/UNVERIFIED`` until such an export exists.
* T-AD-002 exercises the AI.8 idempotency contract: a stable retry key and a
  cache hit on re-run — 100 retries must produce exactly ONE venue submission.

CONTRACT_VERSION 4.0.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from apex.identity.canonical_json import canonical_json
from apex.identity.hashes import replay_key as _replay_key

CONTRACT_VERSION = "4.0.0"

#: AI.13 G-ADAPTER-001 sample requirement (legacy samples).
G_ADAPTER_SAMPLE_REQUIREMENT = 100
#: AI.10 T-AD-002 retry count.
T_AD_ADAPTER_RETRIES = 100
#: AI.10 T-AD-001 legacy interface versions.
LEGACY_VERSIONS: Tuple[str, ...] = ("v2", "v3")

ENGINE_ADAPTERS: Dict[str, str] = {
    "E05": "apex.engines.e05_fvg.engine:load_v3_adapter",
    "E06": "apex.engines.e06_orderblock.engine:load_v3_adapter",
}

#: AA.3/B04 — the one registry rename that the adapter layer must honour.
REGISTRY_RENAME = {"order_book_imbalance": "obi_proxy"}


class AdapterConformanceError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _load_adapter(engine_id: str) -> Callable[[Mapping[str, Any]], Any]:
    target = ENGINE_ADAPTERS.get(engine_id)
    if target is None:
        raise AdapterConformanceError("ENGINE_ADAPTER_ABSENT", engine_id)
    module_name, _, attr = target.partition(":")
    module = __import__(module_name, fromlist=[attr])
    return getattr(module, attr)


def translate_legacy(*, engine_id: str, payload: Mapping[str, Any],
                     version: str) -> Dict[str, Any]:
    """Read-only translation of ONE legacy record into its v4 object.

    The caller receives the canonical v4 projection plus the lineage facts of
    the migration; nothing is written anywhere.
    """
    if version not in LEGACY_VERSIONS:
        raise AdapterConformanceError("LEGACY_VERSION_QX", version)
    adapter = _load_adapter(engine_id)
    before = canonical_json(dict(payload))
    obj = adapter(dict(payload))
    after = canonical_json(obj.to_canonical() if hasattr(obj, "to_canonical")
                           else (obj.to_dict() if hasattr(obj, "to_dict")
                                 else str(obj)))
    return {"engine_id": engine_id, "version": version,
            "legacy_hash": __import__("hashlib").sha256(
                before.encode()).hexdigest(),
            "v4_hash": __import__("hashlib").sha256(after.encode()).hexdigest(),
            "v4_object_type": type(obj).__name__,
            "read_only": True, "state_mutated": False,
            "contract_version": CONTRACT_VERSION}


def synthetic_legacy_cases() -> List[Dict[str, Any]]:
    """v4-derived self-check cases (ADR-P2-009): each case is built from a v4
    object, expressed in the legacy shape, then round-tripped through the real
    adapter and compared semantically."""
    e05 = {
        "schema_version": "3.0.0", "fid": "fvg-synth-1", "direction": "BULL",
        "lower": 100.0, "upper": 102.0, "created_at_ts": 1710460800000,
        "created_at_idx": 10, "ftype": "CONVENTIONAL",
    }
    e05_doji = {**e05, "fid": "fvg-synth-2", "ftype": "DOJI_FVG"}
    e06 = {
        "version": "3.0.0", "oid": "ob-synth-1", "direction": "LONG",
        "zone_lo": 99.0, "zone_hi": 101.0, "origin_ts": 1710460800000,
        "origin_idx": 12,
    }
    e06_hl = {**e06, "oid": "ob-synth-2"}
    e06_hl.pop("zone_lo")
    e06_hl.pop("zone_hi")
    e06_hl["origin_high"] = 101.0
    e06_hl["origin_low"] = 99.0
    return [
        {"engine_id": "E05", "version": "v3", "payload": e05,
         "expect": {"ftype": "CONVENTIONAL", "penalty_applied": False}},
        {"engine_id": "E05", "version": "v3", "payload": e05_doji,
         "expect": {"ftype": "CONVENTIONAL", "penalty_applied": True}},
        {"engine_id": "E06", "version": "v3", "payload": e06,
         "expect": {"derived_from": "zone_lo_zone_hi"}},
        {"engine_id": "E06", "version": "v3", "payload": e06_hl,
         "expect": {"derived_from": "origin_high_origin_low"}},
    ]


def t_ad_001(*, export_path: Optional[str] = None) -> Dict[str, Any]:
    """T-AD-001 — v2/v3 → v4.0.0 translation correct; semantics preserved.

    Without a user-provided legacy export the harness runs the synthetic
    v4-derived self-checks and reports the real-data leg as OPEN/UNVERIFIED
    (ADR-P2-009 — never fabricated).
    """
    results: List[Dict[str, Any]] = []
    failures: List[str] = []
    for case in synthetic_legacy_cases():
        translated = translate_legacy(engine_id=case["engine_id"],
                                      payload=case["payload"],
                                      version=case["version"])
        obj = _load_adapter(case["engine_id"])(dict(case["payload"]))
        expect = case["expect"]
        checks: Dict[str, Any] = {"translated": True}
        if "ftype" in expect:
            checks["ftype"] = getattr(obj, "ftype", None) == expect["ftype"]
            marker = getattr(obj, "extra", {}).get("v3_doji_penalty")
            checks["penalty_applied"] = ((marker == 0.7)
                                        == bool(expect["penalty_applied"]))
        if "derived_from" in expect:
            checks["zone_bounds"] = (float(obj.zone_lo) == 99.0
                                     and float(obj.zone_hi) == 101.0)
            checks["v4_snapshot_minted"] = bool(getattr(obj, "snapshot_id", ""))
        ok = all(bool(v) for v in checks.values())
        if not ok:
            failures.append(f"{case['engine_id']}:{json.dumps(checks, sort_keys=True)}")
        results.append({"engine_id": case["engine_id"], "version": case["version"],
                        "checks": checks, "ok": ok,
                        "v4_hash": translated["v4_hash"],
                        "read_only": translated["read_only"]})
    export_summary: Dict[str, Any] = {
        "gate": "G-ADAPTER-001", "status": "OPEN/UNVERIFIED",
        "reason": "ADR-P2-009 — no v2/v3 data set exists in this repository; "
                  "100 legacy samples cannot be sourced without fabrication",
        "required_samples": G_ADAPTER_SAMPLE_REQUIREMENT,
        "samples_supplied": 0, "owner_procedure": True}
    if export_path:
        path = Path(export_path)
        if not path.exists():
            raise AdapterConformanceError("EXPORT_PATH_ABSENT", export_path)
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise AdapterConformanceError("EXPORT_SHAPE_QX", export_path)
        export_summary = run_legacy_export(records)
    return {"test": "T-AD-001", "synthetic_cases": len(results),
            "results": results, "failures": failures,
            "passed": not failures,
            "real_data_gate": export_summary,
            "contract_version": CONTRACT_VERSION}


def run_legacy_export(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Run a *user-provided* legacy export through the read-only adapters."""
    translated = 0
    failed: List[Dict[str, Any]] = []
    for record in records:
        try:
            engine_id = str(record.get("engine_id", ""))
            version = str(record.get("version", "v3"))
            if isinstance(record.get("payload"), Mapping):
                # harness synthetic case: engine_id/version + nested payload
                payload = dict(record["payload"])
            else:
                payload = {k: v for k, v in record.items()
                           if k not in ("engine_id", "version", "expect")}
            translate_legacy(engine_id=engine_id, payload=payload,
                             version=version)
            translated += 1
        except Exception as exc:               # noqa: BLE001 - reported, not hidden
            failed.append({"record": str(record)[:120],
                           "reason": f"{type(exc).__name__}:{exc}"})
    status = ("CLOSED" if translated >= G_ADAPTER_SAMPLE_REQUIREMENT
              and not failed else "OPEN/UNVERIFIED")
    return {"gate": "G-ADAPTER-001", "status": status,
            "samples_supplied": len(records), "translated": translated,
            "failures": failed,
            "required_samples": G_ADAPTER_SAMPLE_REQUIREMENT,
            "data_loss": 0 if translated == len(records) else
                         len(records) - translated}


# --------------------------------------------------------------------------
# T-AD-002 — idempotency adapter (AI.8)
# --------------------------------------------------------------------------

def stable_retry_key(*, engine_version: str, contract_version: str,
                     symbol: str, timeframe: str, as_of: str,
                     input_hash: str, parameter_package_id: str,
                     code_revision: str, payload: Mapping[str, Any]) -> str:
    """The AI.3 replay key, used here as the stable retry key."""
    return _replay_key(engine_version, contract_version, symbol, timeframe,
                       as_of, input_hash, parameter_package_id, code_revision,
                       canonical_json(dict(payload)))


def t_ad_002(*, retries: int = T_AD_ADAPTER_RETRIES,
             submit: Optional[Callable[[str], Mapping[str, Any]]] = None
             ) -> Dict[str, Any]:
    """T-AD-002 — retry key stable; cache hit on re-run; no double execution.

    ``submit(intent_id)`` is the adapter seam (production: the CP-7
    ``ToobitAdapter.submit_order`` whose duplicate path returns the ORIGINAL
    result with ``cached=True``); the harness counts how many times the seam
    produced a *new* venue submission.
    """
    intent_id = "intent-cp8-tad002"
    #: AI.8: a *retry* repeats the identical request — the payload of the key
    #: is the order intent, never the attempt counter (otherwise every retry
    #: would look like a new order).
    order_payload = {"intent_id": intent_id, "symbol": "BTCUSDT",
                     "timeframe": "15m", "direction": "LONG", "quantity": 1.0}
    keys: List[str] = []
    submissions = 0
    cached_hits = 0
    results: List[Dict[str, Any]] = []
    for i in range(int(retries)):
        key = stable_retry_key(
            engine_version="4.0.0", contract_version="4.0.0",
            symbol="BTCUSDT", timeframe="15m",
            as_of="2026-08-30T14:00:00Z", input_hash="a" * 64,
            parameter_package_id="pkg-cp8-0.1.0", code_revision="0" * 40,
            payload=order_payload)
        keys.append(key)
        if submit is not None:
            result = dict(submit(intent_id))
            if result.get("cached"):
                cached_hits += 1
            else:
                submissions += 1
            results.append({"attempt": i, "cached": bool(result.get("cached"))})
    unique_keys = len(set(keys))
    if submit is None:
        return {"test": "T-AD-002", "retries": retries,
                "unique_keys": unique_keys, "key_stable": unique_keys == 1,
                "seam": "NOT_PROVIDED",
                "note": "the live seam is exercised in "
                        "tests/integration/test_cp8_adapters.py against the "
                        "CP-7 adapter and the in-repo fake responder",
                "contract_version": CONTRACT_VERSION}
    return {"test": "T-AD-002", "retries": retries, "unique_keys": unique_keys,
            "key_stable": unique_keys == 1,
            "new_submissions": submissions, "cached_hits": cached_hits,
            "no_double_execution": submissions == 1,
            "passed": unique_keys == 1 and submissions == 1,
            "contract_version": CONTRACT_VERSION}


def rename_registry_entry(old_name: str) -> str:
    """AA.3/B04 — ``order_book_imbalance`` is renamed ``obi_proxy``; any other
    name is returned unchanged (no invented aliases)."""
    return REGISTRY_RENAME.get(old_name, old_name)


def conformance_summary() -> Dict[str, Any]:
    return {"token_1": "T-AD-001", "token_2": "T-AD-002",
            "gate": "G-ADAPTER-001",
            "engine_adapters": dict(ENGINE_ADAPTERS),
            "legacy_versions": list(LEGACY_VERSIONS),
            "real_data_requirement": G_ADAPTER_SAMPLE_REQUIREMENT,
            "contract_version": CONTRACT_VERSION}
