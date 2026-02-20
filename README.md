# Surfa Ingest SDK

[![PyPI version](https://badge.fury.io/py/surfa-ingest.svg)](https://badge.fury.io/py/surfa-ingest)
[![Python Support](https://img.shields.io/pypi/pyversions/surfa-ingest.svg)](https://pypi.org/project/surfa-ingest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/surfa-ingest)](https://pepy.tech/project/surfa-ingest)

Official Python SDK for ingesting live traffic events to Surfa Analytics.

## Features

- 🚀 **Event Buffering** - Automatic batching with configurable buffer size
- 🔄 **Auto-Retry** - Built-in retry logic with exponential backoff
- 📦 **Context Manager** - Automatic session lifecycle management
- 🏷️ **Runtime Metadata** - Track AI provider, model, and configuration
- ✅ **Event Validation** - Client-side validation before sending
- 🔍 **Correlation IDs** - Link related events together
- 📊 **Session Tracking** - Automatic session ID generation
- 🛡️ **Type Safety** - Full type hints and IDE autocomplete

## Installation

```bash
pip install surfa-ingest
```

## Quick Start

```python
from surfa_ingest import SurfaClient

# Initialize client with your ingest key
client = SurfaClient(ingest_key="sk_live_your_key_here")

# Track events
client.track({
    "kind": "tool",
    "subtype": "call_started",
    "tool_name": "search_web",
    "args": {"query": "AI news"}
})

client.track({
    "kind": "tool",
    "subtype": "call_completed",
    "tool_name": "search_web",
    "status": "success",
    "latency_ms": 234
})

# Flush events to API
client.flush()
```

## Context Manager (Recommended)

Use the context manager to automatically track session lifecycle:

```python
from surfa_ingest import SurfaClient

with SurfaClient(ingest_key="sk_live_your_key_here") as client:
    # Session automatically started
    
    client.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "search_web"
    })
    
    # Session automatically ended and events flushed on exit
```

## Configuration

```python
client = SurfaClient(
    ingest_key="sk_live_your_key_here",
    api_url="https://api.surfa.dev",  # Default: http://localhost:3000
    flush_at=25,                       # Auto-flush after 25 events
    timeout_s=10,                      # HTTP timeout in seconds
)
```

## Set Runtime Metadata

Track which AI runtime is being used:

```python
client = SurfaClient(ingest_key="sk_live_...")

client.set_runtime(
    provider="anthropic",
    model="claude-sonnet-4-5",
    mode="messages"
)
```

## Event Types

### Tool Events

```python
# Tool call started
client.track({
    "kind": "tool",
    "subtype": "call_started",
    "tool_name": "search_web",
    "direction": "request",
    "args": {"query": "Python tutorials"}
})

# Tool call completed
client.track({
    "kind": "tool",
    "subtype": "call_completed",
    "tool_name": "search_web",
    "direction": "response",
    "status": "success",
    "latency_ms": 234,
    "results": [{"title": "Learn Python", "url": "..."}]
})
```

### Session Events

```python
# Session started
client.session_started()

# Session ended
client.session_ended()
```

### Runtime Events

```python
# LLM request
client.track({
    "kind": "runtime",
    "subtype": "llm_request",
    "direction": "outbound",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7
})
```

## Event Fields

### Required Fields
- `kind` (str): Event type (e.g., "tool", "session", "runtime")

### Optional Fields
- `subtype` (str): Event subtype (e.g., "call_started", "session_ended")
- `tool_name` (str): Name of the tool
- `status` (str): Status (e.g., "success", "error")
- `direction` (str): Direction (e.g., "request", "response")
- `method` (str): HTTP method or similar
- `correlation_id` (str): Correlation ID for pairing events
- `span_parent_id` (str): Parent span ID for tracing
- `latency_ms` (int): Latency in milliseconds
- `ts` (str): Timestamp (ISO 8601 format, auto-generated if not provided)
- Any additional fields will be included in the event payload

## Auto-Flush

Events are automatically flushed when:
1. Buffer reaches `flush_at` events (default: 25)
2. Context manager exits
3. `flush()` is called explicitly

## Error Handling

```python
from surfa_ingest import SurfaClient, SurfaConfigError, SurfaValidationError

try:
    client = SurfaClient(ingest_key="invalid_key")
except SurfaConfigError as e:
    print(f"Configuration error: {e}")

try:
    client.track({"invalid": "event"})  # Missing 'kind'
except SurfaValidationError as e:
    print(f"Validation error: {e}")
```

## Logging

The SDK uses Python's standard logging module:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("surfa_ingest")
```

## Development Status

**Current Version: 0.1.0 (Alpha)**

This SDK is in active development. The API may change in future versions.

### Implemented
- ✅ Client initialization
- ✅ Event buffering
- ✅ Session management
- ✅ Context manager support
- ✅ Event validation
- ✅ Runtime metadata
- ✅ HTTP API integration
- ✅ Automatic retry logic (3 retries with exponential backoff)

### Coming Soon
- 🔜 Background flushing
- 🔜 Async support

## License

MIT

## Links

- 📦 **PyPI**: https://pypi.org/project/surfa-ingest/
- 📚 **Documentation**: https://docs.surfa.dev
- 🐛 **Issues**: https://github.com/gamladz/surfa/issues
- 💬 **Discussions**: https://github.com/gamladz/surfa/discussions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Changelog

### 0.1.0 (2026-02-20)

- Initial release
- Event buffering and batching
- Session management
- Context manager support
- Runtime metadata capture
- HTTP API integration with retry logic
- Event validation
