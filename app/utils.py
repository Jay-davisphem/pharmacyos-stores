import hashlib
from typing import Any

import orjson


def sanitize_payload(payload: Any, price_field: str | None = None, quantity_field: str | None = None) -> Any:
    """Remove price and quantity fields from payload for fingerprinting.
    
    Only excludes the specific fields detected by AI, not hardcoded variants.
    This ensures unique identification per organization based on their actual field names.
    """
    if not isinstance(payload, dict):
        return payload
    
    excluded = set()
    
    # Exclude only the detected/specified price field
    if price_field:
        excluded.add(price_field)
    
    # Exclude only the detected/specified quantity field
    if quantity_field:
        excluded.add(quantity_field)
    
    # If no fields detected, exclude common defaults
    if not excluded:
        excluded = {"price", "quantity"}
    
    return {key: value for key, value in payload.items() if key not in excluded}


def compute_fingerprint(payload: Any, price_field: str | None = None, quantity_field: str | None = None) -> str:
    """Compute fingerprint excluding ONLY the detected price/quantity fields.
    
    This allows proper deduplication based on all non-price/quantity fields.
    - If fields are detected by AI: excludes only those specific fields
    - If not detected: excludes common defaults ("price", "quantity")
    """
    sanitized = sanitize_payload(payload, price_field, quantity_field)
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
