"""Data privacy, anonymisation, and PII filtering for Arabic and English text."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Tuple

# Regex patterns for sensitive PII across Arabic & English contexts
PII_PATTERNS = {
    # UAE Emirates ID (784-xxxx-xxxxxxx-x)
    "emirates_id": re.compile(r"\b784-[0-9]{4}-[0-9]{7}-[0-9]\b"),
    # Saudi National ID / Iqama (10 digits starting with 1 or 2)
    "saudi_id": re.compile(r"\b[12]\d{9}\b"),
    # Credit card patterns
    "credit_card": re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
    # Email pattern
    "email": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    # International & GCC phone numbers (+971, +966, 05x, etc.)
    "phone": re.compile(
        r"(?<!\d)(?:(?:\+|00)(?:971|966|965|974|973|968|20)\s?|0)(?:5[0-9]|2|3|4|6|7|9)[0-9\s-]{6,9}(?!\d)"
    ),
}


def sanitize_pii(text: str) -> Tuple[str, Dict[str, int]]:
    """Sanitize PII from prompt or response text, replacing with anonymized tokens.
    
    Returns:
        (sanitized_text, redaction_counts)
    """
    if not text:
        return "", {}

    redaction_counts: Dict[str, int] = {}
    cleaned = text

    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(cleaned)
        if matches:
            redaction_counts[pii_type] = len(matches)
            cleaned = pattern.sub(f"[REDACTED_{pii_type.upper()}]", cleaned)

    return cleaned, redaction_counts


def anonymize_user_id(raw_user_id: str, salt: str = "peregrine_privacy_salt_2026") -> str:
    """Produce deterministic one-way SHA-256 hash of user identifier."""
    if not raw_user_id:
        return "anon_user"
    hasher = hashlib.sha256()
    hasher.update(f"{salt}:{raw_user_id}".encode("utf-8"))
    return f"usr_{hasher.hexdigest()[:16]}"
