"""
Revoda — Reporter Anonymisation Module

PRIVACY GUARANTEE:
  Raw reporter data (phone, device ID) is NEVER written to the database.
  Only a one-way HMAC hash is stored, making re-identification computationally
  infeasible without the secret key, while still allowing deduplication of
  repeat reporters across incidents.
"""

import hashlib
import hmac
import os
from typing import Optional


# Secret key loaded from environment — rotate between election cycles
_ANON_SECRET = os.getenv("ANONYMIZER_SECRET", "change-this-in-production").encode()


def anonymize_reporter(
    phone: Optional[str] = None,
    device_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Optional[str]:
    """
    Produces a stable, pseudonymous identifier for a reporter.
    
    The hash allows:
    - Detecting if the same person files duplicate reports
    - Rate-limiting abuse from a single source
    
    It does NOT allow:
    - Recovering the original phone number or device ID
    - Linking identity to any external database
    
    Returns None if no identifying data is provided (fully anonymous report).
    """
    raw_inputs = [
        _normalize_phone(phone),
        _normalize_device_id(device_id),
        # IP is last resort; phone/device preferred
        ip_address.split(",")[0].strip() if ip_address else None,
    ]

    # Use the first available identifier
    identifier = next((x for x in raw_inputs if x), None)
    if not identifier:
        return None

    # HMAC-SHA256 with rotating secret
    digest = hmac.new(
        _ANON_SECRET,
        identifier.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Prefix makes it clear in DB this is an anon hash, not a user ID
    return f"anon:{digest[:48]}"


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Strip formatting, normalise to E.164-ish for consistent hashing."""
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 7:
        return None
    # Nigerian numbers: 080... → +23480...
    if digits.startswith("0") and len(digits) == 11:
        digits = "234" + digits[1:]
    return digits


def _normalize_device_id(device_id: Optional[str]) -> Optional[str]:
    if not device_id:
        return None
    cleaned = device_id.strip().lower()
    if len(cleaned) < 8:
        return None
    return cleaned


def check_rate_limit(anon_hash: str, redis_client, window_seconds: int = 3600, max_reports: int = 10) -> bool:
    """
    Returns True if this reporter is within allowed rate limits.
    Uses Redis sliding window counter.
    """
    if not anon_hash:
        return True  # Fully anonymous — allow but track IP separately
    key = f"ratelimit:{anon_hash}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window_seconds)
    return count <= max_reports
