import hashlib
from typing import Any

import orjson


EXCLUDED_KEYS = {"price", "quantity"}


def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: value for key, value in payload.items() if key not in EXCLUDED_KEYS}
    return payload


def compute_fingerprint(payload: Any) -> str:
    sanitized = sanitize_payload(payload)
    raw = orjson.dumps(sanitized, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(raw).hexdigest()


def extract_number(payload: Any, key: str) -> float | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
