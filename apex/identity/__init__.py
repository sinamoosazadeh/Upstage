"""GLOBAL IDENTITY / PIT UTILITY CONTRACT v1.0.0 — single source of truth.

Modules: canonical_json (ONE canonical serializer), uuid_v7 (ONE UUIDv7),
hashes (content_id / replay_key / sha256_hex), snapshot (canonical envelope
+ governed as_of). UUIDv7 is operational-only and never enters canonical
snapshot payloads.
"""
from apex.identity.canonical_json import canonical_json, canonical_json_bytes, CanonicalJsonError
from apex.identity.uuid_v7 import uuid_v7, parse_uuid_v7_timestamp_ms
from apex.identity.hashes import sha256_hex, content_id, replay_key
from apex.identity.snapshot import canonical_snapshot_id, snapshot_envelope, governed_as_of_ms

__all__ = [
    "canonical_json",
    "canonical_json_bytes",
    "CanonicalJsonError",
    "uuid_v7",
    "parse_uuid_v7_timestamp_ms",
    "sha256_hex",
    "content_id",
    "replay_key",
    "canonical_snapshot_id",
    "snapshot_envelope",
    "governed_as_of_ms",
]
