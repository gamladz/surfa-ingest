"""
Surfa Ingest Client

Main client for tracking events to Surfa Analytics.
"""

from typing import Any, Dict, List, Optional
import logging
import time

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from .utils import generate_session_id, validate_ingest_key
from .events import (
    Event,
    validate_event,
    session_started as create_session_started,
    session_ended as create_session_ended,
    tool_call_started as create_tool_call_started,
    tool_call_completed as create_tool_call_completed,
    tool_call_failed as create_tool_call_failed,
    custom as create_custom,
)
from .exceptions import (
    SurfaConfigError,
    SurfaValidationError,
    SurfaAuthError,
    SurfaIngestError,
    SurfaNetworkError,
)


logger = logging.getLogger(__name__)


class SurfaClient:
    """
    Client for ingesting live traffic events to Surfa Analytics.
    
    Example:
        >>> client = SurfaClient(ingest_key="sk_live_...")
        >>> client.track({"kind": "tool", "subtype": "call_started"})
        >>> client.flush()
        
    Or use as context manager:
        >>> with SurfaClient(ingest_key="sk_live_...") as client:
        ...     client.track({"kind": "tool", "subtype": "call_started"})
    """
    
    def __init__(
        self,
        ingest_key: str,
        api_url: str = "http://localhost:3000",
        flush_at: int = 25,
        timeout_s: int = 10,
    ):
        """
        Initialize Surfa client.
        
        Args:
            ingest_key: Ingest API key (starts with sk_live_ or sk_test_)
            api_url: Base URL for Surfa API (default: http://localhost:3000)
            flush_at: Number of events to buffer before auto-flush (default: 25)
            timeout_s: HTTP request timeout in seconds (default: 10)
            
        Raises:
            SurfaConfigError: If configuration is invalid
        """
        # Validate ingest key
        try:
            validate_ingest_key(ingest_key)
        except ValueError as e:
            raise SurfaConfigError(f"Invalid ingest key: {e}")
        
        self.ingest_key = ingest_key
        self.api_url = api_url.rstrip('/')
        self.flush_at = flush_at
        self.timeout_s = timeout_s
        
        # Generate unique session ID
        self.session_id = generate_session_id()
        
        # Execution ID (set by server on first flush)
        self.execution_id: Optional[str] = None
        
        # Event buffer
        self._buffer: List[Dict[str, Any]] = []
        
        # Optional runtime metadata
        self._runtime: Optional[Dict[str, Any]] = None
        
        # Track if runtime_info event has been emitted
        self._runtime_info_emitted = False
        
        # Track if session has ended
        self._session_ended = False
        
        logger.info(f"Initialized SurfaClient with session_id={self.session_id}")
    
    def set_runtime(
        self,
        provider: str,
        model: str,
        mode: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Set runtime metadata for this session.
        
        This will:
        1. Store runtime metadata to be included in every flush
        2. Emit a runtime_info event on the next flush (once per session)
        
        Args:
            provider: Runtime provider (e.g., 'anthropic', 'openai')
            model: Model name (e.g., 'claude-sonnet-4-5', 'gpt-4')
            mode: API mode (e.g., 'messages', 'completions')
            extra: Additional runtime metadata dictionary
            **kwargs: Additional runtime metadata (merged with extra)
        """
        runtime: Dict[str, Any] = {
            "provider": provider,
            "model": model,
        }
        
        if mode:
            runtime["mode"] = mode
        
        # Merge extra dict and kwargs
        if extra:
            runtime.update(extra)
        if kwargs:
            runtime.update(kwargs)
        
        self._runtime = runtime
        
        # Reset runtime_info_emitted flag so it gets sent on next flush
        self._runtime_info_emitted = False
        
        logger.info(f"Set runtime metadata: provider={provider}, model={model}, mode={mode}")
    
    def track(self, event: Dict[str, Any]) -> None:
        """
        Track an event (alias for track_raw).
        
        The event will be buffered and sent when the buffer reaches flush_at
        or when flush() is called explicitly.
        
        Args:
            event: Event dictionary with at least 'kind' field
            
        Raises:
            SurfaValidationError: If event is invalid
        """
        self.track_raw(event)
    
    def track_raw(self, event_dict: Dict[str, Any]) -> None:
        """
        Track a raw event dictionary.
        
        Validates minimal fields (kind, ts) and adds to buffer.
        
        Args:
            event_dict: Event dictionary with at least 'kind' field
            
        Raises:
            SurfaValidationError: If event is invalid
        """
        # Validate event
        try:
            validate_event(event_dict)
        except ValueError as e:
            raise SurfaValidationError(f"Invalid event: {e}")
        
        # Add to buffer
        self._buffer.append(event_dict)
        
        logger.debug(f"Tracked event: {event_dict.get('kind')}/{event_dict.get('subtype')} (buffer: {len(self._buffer)}/{self.flush_at})")
        
        # Auto-flush if buffer is full
        if len(self._buffer) >= self.flush_at:
            logger.debug(f"Buffer full ({len(self._buffer)}/{self.flush_at}), auto-flushing")
            self.flush()
    
    def session_start(self, **kwargs: Any) -> None:
        """
        Track session start event.
        
        Convenience method that uses session_started() helper.
        
        Args:
            **kwargs: Additional fields for the event
        """
        event = create_session_started(**kwargs)
        self.track(event)
    
    def session_end(self, **kwargs: Any) -> None:
        """
        Track session end event.
        
        Convenience method that uses session_ended() helper.
        After calling this, the session is marked as ended.
        
        Args:
            **kwargs: Additional fields for the event
        """
        if not self._session_ended:
            event = create_session_ended(**kwargs)
            self.track(event)
            self._session_ended = True
            logger.info(f"Session ended: {self.session_id}")
    
    # Legacy aliases
    def session_started(self) -> None:
        """Legacy alias for session_start()"""
        self.session_start()
    
    def session_ended(self) -> None:
        """Legacy alias for session_end()"""
        self.session_end()
    
    def tool_started(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Track tool call started event.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            correlation_id: Correlation ID for pairing
            **kwargs: Additional fields
        """
        event = create_tool_call_started(
            tool_name=tool_name,
            args=args,
            correlation_id=correlation_id,
            **kwargs
        )
        self.track(event)
    
    def tool_completed(
        self,
        tool_name: str,
        result: Optional[Any] = None,
        latency_ms: Optional[int] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Track tool call completed event.
        
        Args:
            tool_name: Name of the tool
            result: Tool result/output
            latency_ms: Execution time in milliseconds
            correlation_id: Correlation ID for pairing
            **kwargs: Additional fields
        """
        event = create_tool_call_completed(
            tool_name=tool_name,
            result=result,
            latency_ms=latency_ms,
            correlation_id=correlation_id,
            **kwargs
        )
        self.track(event)
    
    def tool_failed(
        self,
        tool_name: str,
        error: Optional[str] = None,
        latency_ms: Optional[int] = None,
        correlation_id: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Track tool call failed event.
        
        Args:
            tool_name: Name of the tool
            error: Error message
            latency_ms: Execution time in milliseconds
            correlation_id: Correlation ID for pairing
            **kwargs: Additional fields
        """
        event = create_tool_call_failed(
            tool_name=tool_name,
            error=error,
            latency_ms=latency_ms,
            correlation_id=correlation_id,
            **kwargs
        )
        self.track(event)
    
    def custom_event(
        self,
        kind: str = "custom",
        subtype: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Track a custom event.
        
        Args:
            kind: Event kind
            subtype: Event subtype
            **kwargs: Additional fields
        """
        event = create_custom(kind=kind, subtype=subtype, **kwargs)
        self.track(event)
    
    def flush(self) -> Optional[Dict[str, Any]]:
        """
        Flush buffered events to Surfa API.
        
        This will send all buffered events to the API and clear the buffer.
        Implements retry logic for transient failures.
        
        Returns:
            Response JSON from API, or None if buffer was empty
            
        Raises:
            SurfaAuthError: If authentication fails (401/403)
            SurfaIngestError: If ingestion fails (4xx/5xx)
            SurfaNetworkError: If network request fails after retries
        """
        if not self._buffer:
            logger.debug("No events to flush")
            return None
        
        event_count = len(self._buffer)
        logger.info(f"Flushing {event_count} events to {self.api_url}")
        
        # Prepare events list
        events_to_send = self._buffer.copy()  # Copy to avoid mutation during retry
        
        # Inject runtime_info event at the start if runtime is set and not yet emitted
        if self._runtime and not self._runtime_info_emitted:
            runtime_info_event = {
                "kind": "runtime",
                "subtype": "runtime_info",
                **self._runtime  # Spread runtime metadata into event
            }
            events_to_send.insert(0, runtime_info_event)
            logger.info(f"Injecting runtime_info event: {self._runtime}")
        
        # Build request payload
        payload = {
            "session_id": self.session_id,
            "events": events_to_send,
        }
        
        # Add optional fields
        if self.execution_id is not None:
            payload["execution_id"] = self.execution_id
        
        if self._runtime is not None:
            payload["runtime"] = self._runtime
        
        # Retry configuration
        max_retries = 3
        retry_statuses = {429, 500, 502, 503, 504}
        base_delay = 0.5  # seconds
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Make HTTP request
                response = requests.post(
                    f"{self.api_url}/api/v1/ingest/events",
                    headers={
                        "Authorization": f"Bearer {self.ingest_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout_s,
                )
                
                # Handle success (2xx)
                if 200 <= response.status_code < 300:
                    try:
                        data = response.json()
                    except ValueError:
                        logger.warning("Failed to parse JSON response")
                        data = {}
                    
                    # Store execution_id if provided and we don't have one yet
                    if "execution_id" in data and self.execution_id is None:
                        self.execution_id = data["execution_id"]
                        logger.info(f"Stored execution_id: {self.execution_id}")
                    
                    # Mark runtime_info as emitted if runtime is set
                    if self._runtime and not self._runtime_info_emitted:
                        self._runtime_info_emitted = True
                        logger.debug("Marked runtime_info as emitted")
                    
                    # Clear buffer on success
                    self._buffer.clear()
                    logger.info(f"Successfully flushed {event_count} events")
                    
                    return data
                
                # Handle authentication errors (don't retry)
                if response.status_code in (401, 403):
                    error_msg = f"Authentication failed: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = f"{error_msg} - {error_data['error']}"
                    except ValueError:
                        pass
                    
                    logger.error(error_msg)
                    raise SurfaAuthError(error_msg)
                
                # Handle client errors (don't retry except 429)
                if 400 <= response.status_code < 500 and response.status_code not in retry_statuses:
                    error_msg = f"Client error: {response.status_code}"
                    response_text = response.text[:500]  # Limit length
                    
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = f"{error_msg} - {error_data['error']}"
                    except ValueError:
                        pass
                    
                    logger.error(f"{error_msg} - {response_text}")
                    raise SurfaIngestError(error_msg, response.status_code, response_text)
                
                # Handle retryable errors
                if response.status_code in retry_statuses:
                    logger.warning(f"Retryable error {response.status_code} on attempt {attempt + 1}/{max_retries}")
                    last_error = SurfaIngestError(
                        f"Server error: {response.status_code}",
                        response.status_code,
                        response.text[:500]
                    )
                    
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.debug(f"Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise last_error
                
                # Handle other server errors
                error_msg = f"Server error: {response.status_code}"
                logger.error(f"{error_msg} - {response.text[:500]}")
                raise SurfaIngestError(error_msg, response.status_code, response.text[:500])
                
            except (Timeout, ConnectionError) as e:
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}")
                last_error = SurfaNetworkError(f"Network error: {e}")
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.debug(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise last_error
            
            except RequestException as e:
                logger.error(f"Request failed: {e}")
                raise SurfaNetworkError(f"Request failed: {e}")
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        
        raise SurfaNetworkError("Failed to flush events after retries")
    
    def __enter__(self) -> "SurfaClient":
        """
        Enter context manager.
        
        Returns:
            Self
        """
        logger.debug("Entering SurfaClient context")
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """
        Exit context manager.
        
        Automatically calls session_ended() and flush() on exit.
        Does not raise exceptions (best-effort).
        
        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
            
        Returns:
            False (do not suppress exceptions)
        """
        logger.debug("Exiting SurfaClient context")
        
        try:
            # Mark session as ended
            self.session_ended()
            
            # Flush remaining events
            self.flush()
        except Exception as e:
            # Best-effort: log but don't raise
            logger.warning(f"Error during context exit: {e}")
        
        # Don't suppress exceptions from the with block
        return False
    
    def __repr__(self) -> str:
        return f"SurfaClient(session_id={self.session_id!r}, buffer_size={len(self._buffer)})"
