import hashlib
import json


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def compute_entry_hash(previous_hash: str | None, event_type: str, payload_hash: str, timestamp: str) -> str:
    """
    Tamper-evident hash for one audit_chain row. Changing previous_hash,
    event_type, payload_hash, or timestamp after the fact changes this
    value — and breaks every link computed after it.
    """
    material = _canonical(
        {
            "previous_hash": previous_hash,
            "event_type": event_type,
            "payload_hash": payload_hash,
            "timestamp": timestamp,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()