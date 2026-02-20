"""
Event types and validation for Surfa Ingest SDK

Canonical event shape and helper constructors.
"""

from typing import Any, Dict, Optional
from .utils import get_current_timestamp


# ============================================================================
# Canonical Event Shape
# ============================================================================

def now_iso() -> str:
    """
    Get current timestamp in ISO 8601 UTC format.
    
    Returns:
        ISO 8601 timestamp string (e.g., "2026-01-29T20:00:00Z")
    """
    return get_current_timestamp()


def create_event(
    kind: str,
    subtype: Optional[str] = None,
    tool_name: Optional[str] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    method: Optional[str] = None,
    correlation_id: Optional[str] = None,
    span_parent_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
    ts: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a canonical event dictionary.
    
    Args:
        kind: Event kind (e.g., 'tool', 'session', 'runtime')
        subtype: Event subtype (e.g., 'call_started', 'session_ended')
        tool_name: Name of the tool (for tool events)
        status: Status (e.g., 'success', 'error')
        direction: Direction (e.g., 'request', 'response')
        method: HTTP method or similar
        correlation_id: Correlation ID for pairing events
        span_parent_id: Parent span ID for tracing
        latency_ms: Latency in milliseconds
        ts: Timestamp (ISO 8601 format, defaults to now)
        payload: Additional data (merged with kwargs)
        **kwargs: Additional fields for payload
        
    Returns:
        Event dictionary
    """
    event: Dict[str, Any] = {
        "ts": ts or now_iso(),
        "kind": kind,
    }
    
    # Add optional fields
    if subtype is not None:
        event["subtype"] = subtype
    if tool_name is not None:
        event["tool_name"] = tool_name
    if status is not None:
        event["status"] = status
    if direction is not None:
        event["direction"] = direction
    if method is not None:
        event["method"] = method
    if correlation_id is not None:
        event["correlation_id"] = correlation_id
    if span_parent_id is not None:
        event["span_parent_id"] = span_parent_id
    if latency_ms is not None:
        event["latency_ms"] = latency_ms
    
    # Merge payload
    if payload or kwargs:
        merged_payload = {}
        if payload:
            merged_payload.update(payload)
        if kwargs:
            merged_payload.update(kwargs)
        
        # Add payload fields to event (flattened)
        event.update(merged_payload)
    
    return event


# ============================================================================
# Session Event Helpers
# ============================================================================

def session_started(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a session_started event.
    
    Args:
        payload: Additional data
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> session_started()
        {'ts': '2026-01-29T20:00:00Z', 'kind': 'session', 'subtype': 'session_started'}
    """
    return create_event(
        kind="session",
        subtype="session_started",
        payload=payload,
        **kwargs
    )


def session_ended(payload: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """
    Create a session_ended event.
    
    Args:
        payload: Additional data
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> session_ended()
        {'ts': '2026-01-29T20:00:00Z', 'kind': 'session', 'subtype': 'session_ended'}
    """
    return create_event(
        kind="session",
        subtype="session_ended",
        payload=payload,
        **kwargs
    )


# ============================================================================
# Tool Event Helpers
# ============================================================================

def tool_call_started(
    tool_name: str,
    args: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a tool_call_started event.
    
    Args:
        tool_name: Name of the tool
        args: Tool arguments
        correlation_id: Correlation ID for pairing with completion
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> tool_call_started("search_web", args={"query": "AI news"})
        {
            'ts': '2026-01-29T20:00:00Z',
            'kind': 'tool',
            'subtype': 'tool_call_started',
            'tool_name': 'search_web',
            'direction': 'request',
            'args': {'query': 'AI news'}
        }
    """
    event_data = {
        "kind": "tool",
        "subtype": "tool_call_started",
        "tool_name": tool_name,
        "direction": "request",
    }
    
    if correlation_id is not None:
        event_data["correlation_id"] = correlation_id
    
    if args is not None:
        event_data["args"] = args
    
    event_data.update(kwargs)
    
    return create_event(**event_data)


def tool_call_completed(
    tool_name: str,
    result: Optional[Any] = None,
    latency_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a tool_call_completed event.
    
    Args:
        tool_name: Name of the tool
        result: Tool result/output
        latency_ms: Execution time in milliseconds
        correlation_id: Correlation ID for pairing with start
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> tool_call_completed("search_web", result={"count": 5}, latency_ms=234)
        {
            'ts': '2026-01-29T20:00:00Z',
            'kind': 'tool',
            'subtype': 'tool_call_completed',
            'tool_name': 'search_web',
            'direction': 'response',
            'status': 'success',
            'latency_ms': 234,
            'result': {'count': 5}
        }
    """
    event_data = {
        "kind": "tool",
        "subtype": "tool_call_completed",
        "tool_name": tool_name,
        "direction": "response",
        "status": "success",
    }
    
    if latency_ms is not None:
        event_data["latency_ms"] = latency_ms
    
    if correlation_id is not None:
        event_data["correlation_id"] = correlation_id
    
    if result is not None:
        event_data["result"] = result
    
    event_data.update(kwargs)
    
    return create_event(**event_data)


def tool_call_failed(
    tool_name: str,
    error: Optional[str] = None,
    latency_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a tool_call_failed event.
    
    Args:
        tool_name: Name of the tool
        error: Error message or description
        latency_ms: Execution time in milliseconds
        correlation_id: Correlation ID for pairing with start
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> tool_call_failed("search_web", error="Network timeout", latency_ms=5000)
        {
            'ts': '2026-01-29T20:00:00Z',
            'kind': 'tool',
            'subtype': 'tool_call_failed',
            'tool_name': 'search_web',
            'direction': 'response',
            'status': 'error',
            'latency_ms': 5000,
            'error': 'Network timeout'
        }
    """
    event_data = {
        "kind": "tool",
        "subtype": "tool_call_failed",
        "tool_name": tool_name,
        "direction": "response",
        "status": "error",
    }
    
    if latency_ms is not None:
        event_data["latency_ms"] = latency_ms
    
    if correlation_id is not None:
        event_data["correlation_id"] = correlation_id
    
    if error is not None:
        event_data["error"] = error
    
    event_data.update(kwargs)
    
    return create_event(**event_data)


# ============================================================================
# Custom Event Helper
# ============================================================================

def custom(
    kind: str = "custom",
    subtype: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create a custom event.
    
    Args:
        kind: Event kind (default: 'custom')
        subtype: Event subtype
        payload: Additional data
        **kwargs: Additional fields
        
    Returns:
        Event dictionary
        
    Example:
        >>> custom(subtype="user_action", action="button_click", button_id="submit")
        {
            'ts': '2026-01-29T20:00:00Z',
            'kind': 'custom',
            'subtype': 'user_action',
            'action': 'button_click',
            'button_id': 'submit'
        }
    """
    return create_event(
        kind=kind,
        subtype=subtype,
        payload=payload,
        **kwargs
    )


# ============================================================================
# Event Validation
# ============================================================================

def validate_event(event: Dict[str, Any]) -> bool:
    """
    Validate event structure.
    
    Args:
        event: Event dictionary
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If event is invalid
    """
    if not isinstance(event, dict):
        raise ValueError("Event must be a dictionary")
    
    if "kind" not in event:
        raise ValueError("Event must have 'kind' field")
    
    if not isinstance(event["kind"], str):
        raise ValueError("Event 'kind' must be a string")
    
    if not event["kind"]:
        raise ValueError("Event 'kind' cannot be empty")
    
    # Validate ts if present
    if "ts" in event and not isinstance(event["ts"], str):
        raise ValueError("Event 'ts' must be a string")
    
    return True


# ============================================================================
# Legacy Event Class (for backwards compatibility)
# ============================================================================

class Event:
    """
    Legacy Event class for backwards compatibility.
    
    Prefer using the helper functions instead.
    """
    
    def __init__(self, kind: str, **kwargs: Any):
        self.data = create_event(kind=kind, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data
    
    def __repr__(self) -> str:
        return f"Event(kind={self.data['kind']!r}, subtype={self.data.get('subtype')!r})"
