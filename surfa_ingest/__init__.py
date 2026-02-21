"""
Surfa Ingest SDK

Official Python SDK for ingesting live traffic events to Surfa Analytics.

Example:
    >>> from surfa_ingest import SurfaClient
    >>> 
    >>> with SurfaClient(ingest_key="sk_live_...") as client:
    ...     client.track({
    ...         "kind": "tool",
    ...         "subtype": "call_started",
    ...         "tool_name": "search_web"
    ...     })
"""

__version__ = "0.1.1"

from .client import SurfaClient
from .events import Event
from .utils import generate_session_id
from .exceptions import (
    SurfaError,
    SurfaConfigError,
    SurfaNetworkError,
    SurfaValidationError,
    SurfaAuthError,
    SurfaIngestError,
)

__all__ = [
    "SurfaClient",
    "Event",
    "generate_session_id",
    "SurfaError",
    "SurfaConfigError",
    "SurfaNetworkError",
    "SurfaValidationError",
    "SurfaAuthError",
    "SurfaIngestError",
]
