"""
Utility functions for Surfa Ingest SDK
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict


def generate_session_id() -> str:
    """
    Generate a unique session ID.
    
    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


def generate_event_id() -> str:
    """
    Generate a unique event ID.
    
    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format with UTC timezone.
    
    Returns:
        ISO 8601 timestamp string (e.g., "2026-01-29T20:00:00Z")
    """
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_ingest_key(key: str) -> bool:
    """
    Validate ingest key format.
    
    Args:
        key: Ingest API key
        
    Returns:
        True if valid format
        
    Raises:
        ValueError: If key format is invalid
    """
    if not key:
        raise ValueError("Ingest key cannot be empty")
    
    if not key.startswith("sk_live_") and not key.startswith("sk_test_"):
        raise ValueError("Ingest key must start with 'sk_live_' or 'sk_test_'")
    
    if len(key) < 20:
        raise ValueError("Ingest key is too short")
    
    return True


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries, with override taking precedence.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    result.update(override)
    return result
