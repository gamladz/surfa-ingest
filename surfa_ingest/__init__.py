"""
Surfa Ingest SDK

Official Python SDK for ingesting live traffic events to Surfa Analytics.

One-line capture for an MCP server (set SURFA_API_KEY):
    >>> from fastmcp import FastMCP
    >>> from surfa_ingest import with_surfa
    >>>
    >>> mcp = with_surfa(FastMCP("my-server"))

Manual events:
    >>> from surfa_ingest import SurfaClient
    >>> 
    >>> with SurfaClient(ingest_key="sk_live_...") as client:
    ...     client.track({
    ...         "kind": "tool",
    ...         "subtype": "call_started",
    ...         "tool_name": "search_web"
    ...     })
"""

__version__ = "0.3.0"

from .client import SurfaClient
from .with_surfa import with_surfa, flush_surfa, shutdown_surfa
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
    "with_surfa",
    "flush_surfa",
    "shutdown_surfa",
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
