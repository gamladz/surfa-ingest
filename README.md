# Surfa Ingest SDK

[![PyPI version](https://badge.fury.io/py/surfa-ingest.svg)](https://badge.fury.io/py/surfa-ingest)
[![Python Support](https://img.shields.io/pypi/pyversions/surfa-ingest.svg)](https://pypi.org/project/surfa-ingest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/surfa-ingest)](https://pepy.tech/project/surfa-ingest)

**Analytics for MCP Servers and AI Agents** - Track usage, performance, and task completion whether your server runs locally or remotely.

## Why Surfa Ingest?

### For MCP Server Builders

Get visibility into how your MCP server is being used - whether it's installed locally on users' machines or hosted remotely:

**📊 Gain Visibility You Wouldn't Have Otherwise**
- **Local MCP servers:** Track usage even when installed on users' machines (Claude Desktop, Cursor, etc.)
- **Remote MCP servers:** Get structured analytics beyond basic server logs

**🎯 Understand Your Users**
- Which tools are most popular
- Which AI clients are using your server (Claude, ChatGPT, Cursor)
- Real-time usage patterns and trends
- Geographic distribution and platform breakdown

**🚀 Optimize Based on Real Data**
- Performance metrics (latency, error rates)
- Task completion tracking (did the user actually accomplish their goal?)
- Identify bottlenecks and failure points
- A/B test improvements

**💰 Enable Usage-Based Pricing**
- Track API calls and tool usage
- Monitor quota consumption
- Build monetization models

**🔍 Debug Issues Faster**
- See exactly what's failing and where
- Trace user sessions end-to-end
- Identify retry patterns and error sequences

### Privacy-First Design

- ✅ No PII collected by default
- ✅ Users can opt-out via environment variable
- ✅ You control what data is sent
- ✅ GDPR and privacy-compliant

## Quick Start for MCP Builders

### 1. Install the SDK

```bash
pip install surfa-ingest
```

### 2. Add to Your MCP Server

```python
from surfa_ingest import SurfaClient
import os

# Initialize once at server startup
analytics = SurfaClient(
    ingest_key=os.getenv("SURFA_INGEST_KEY", "sk_live_your_key"),
    api_url=os.getenv("SURFA_API_URL", "https://analytics.yourcompany.com")
)

# Set runtime metadata
analytics.set_runtime(
    provider="mcp",
    model="your-mcp-server-name",
    mode="stdio"  # or "sse" for remote
)

# Track tool calls
@mcp.tool()
def search_database(query: str):
    analytics.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "search_database"
    })
    
    result = perform_search(query)
    
    analytics.track({
        "kind": "tool",
        "subtype": "call_completed",
        "tool_name": "search_database",
        "status": "success"
    })
    
    return result
```

### 3. Get Your Analytics

Visit your Surfa dashboard to see:
- Real-time tool usage
- Performance metrics
- Task completion rates
- Client distribution
- Error tracking

## What You Get

### Real-Time Dashboards
- 📈 Tool usage trends
- ⚡ Performance metrics (P50, P95, P99 latency)
- ✅ Task completion rates
- 🔴 Error rates and types
- 👥 Active users and sessions

### Deterministic Agent Metrics
- **Task Completion:** Did the user actually accomplish their goal?
- **Tool Calls:** How many tools were invoked?
- **Retries:** Repeated calls with same parameters
- **Recovery:** Did the agent recover from errors?
- **Latency:** P95 and total latency tracking

### Client Intelligence
- Which AI clients are using your MCP (Claude, ChatGPT, Cursor)
- Platform distribution (macOS, Linux, Windows)
- Client versions and configurations

## SDK Features

- 🚀 **Event Buffering** - Automatic batching with configurable buffer size
- 🔄 **Auto-Retry** - Built-in retry logic with exponential backoff
- 📦 **Context Manager** - Automatic session lifecycle management
- 🏷️ **Runtime Metadata** - Track AI provider, model, and configuration
- ✅ **Event Validation** - Client-side validation before sending
- 🔍 **Correlation IDs** - Link related events together
- 📊 **Session Tracking** - Automatic session ID generation
- 🛡️ **Type Safety** - Full type hints and IDE autocomplete
- 🔒 **Privacy-First** - No PII by default, user opt-out support

## Deterministic Metrics

When you send events using this SDK, the Surfa platform automatically calculates these metrics for each execution:

### Automatically Calculated Metrics

| Metric | Definition | How It's Calculated |
|--------|-----------|-------------------|
| **Task Completion** | Whether the task was actually completed | Uses `task_completed` field if present, otherwise infers from event sequence |
| **Total Steps** | Number of agent steps taken | Count of tool call events |
| **Tool Calls** | Total number of tool invocations | Count of `tool_call_started` events |
| **Retries** | Repeated calls with same tool+args | Detected from `tool_name` + `payload.input` matching |
| **Reattempts** | Retries after a failed call | Retries where previous attempt had `status: "error"` |
| **Redundant Calls** | Retries after a successful call | Retries where previous attempt had `status: "success"` |
| **Schema Errors** | Schema validation failures | Count of `schema_validation_error` events |
| **Hallucinated Calls** | Calls to non-existent tools | Detected from error patterns |
| **Recovery** | Agent recovered from errors | First success after any failure |
| **Total Latency** | Sum of all operation latencies | Sum of `latency_ms` fields |
| **P95 Latency** | 95th percentile latency | Calculated from `latency_ms` distribution |

### What You Need to Send

For accurate metrics, ensure your events include:

**Required Fields:**
- `kind` - Event type (`"tool"`, `"session"`, `"runtime"`)
- `subtype` - Event subtype (`"call_started"`, `"call_completed"`, etc.)

**Recommended Fields:**
- `tool_name` - For retry detection
- `payload.input` - Tool arguments (for retry detection)
- `correlation_id` - To pair request/response events
- `latency_ms` - For latency metrics
- `status` - `"success"` or `"error"` for completion tracking

**Example:**
```python
# This event contributes to multiple metrics automatically
client.track({
    "kind": "tool",
    "subtype": "call_completed",
    "tool_name": "search_web",
    "payload": {
        "input": {"query": "AI news"}  # Used for retry detection
    },
    "correlation_id": "abc123",
    "latency_ms": 234,
    "status": "success"
})
```

### No Client-Side Calculation Needed

❌ **Don't do this:**
```python
# You don't need to track retries yourself!
is_retry = check_if_retry(params)  # Not needed
client.track({"is_retry": is_retry})  # Server calculates this
```

✅ **Do this instead:**
```python
# Just send clean events - server handles the rest
client.track({
    "kind": "tool",
    "subtype": "call_started",
    "tool_name": "search_web",
    "payload": {"input": {"query": "AI news"}}
})
```

The platform automatically detects retries, calculates latencies, and tracks all metrics from your event stream.

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
    # task_completed automatically set based on success/failure
```

### Explicit Task Completion

Mark whether a task was actually completed:

```python
# Explicit success
with SurfaClient(ingest_key="sk_live_...") as client:
    result = perform_task()
    client.session_end(task_completed=True)

# Explicit failure
with SurfaClient(ingest_key="sk_live_...") as client:
    try:
        result = perform_task()
        client.session_end(task_completed=True)
    except Exception:
        client.session_end(task_completed=False)
        raise

# Automatic (context manager infers from exceptions)
with SurfaClient(ingest_key="sk_live_...") as client:
    result = perform_task()  # If exception: task_completed=False
    # If no exception: task_completed=True
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

### 0.1.1 (2026-02-21)

**New Features:**
- ✨ Added `task_completed` parameter to `session_end()` method
- ✨ Exported `generate_session_id` utility function for external use
- ✨ Context manager now automatically sets `task_completed` based on exception status

**Improvements:**
- 📝 Updated README with MCP builder-focused value proposition
- 📝 Added privacy-first design section
- 📝 Improved quick start guide for MCP servers

**Use Case:**
Perfect for MCP server builders who want to track whether users actually completed their tasks, not just whether the session ended.

```python
# Explicit task completion tracking
with SurfaClient(ingest_key="sk_live_...") as client:
    result = perform_task()
    client.session_end(task_completed=True)  # ✅ Task succeeded

# Automatic inference from exceptions
with SurfaClient(ingest_key="sk_live_...") as client:
    result = perform_task()  # ✅ No exception = task_completed=True
    # ❌ Exception raised = task_completed=False
```

### 0.1.0 (2026-02-20)

- Initial release
- Event buffering and batching
- Session management
- Context manager support
- Runtime metadata capture
- HTTP API integration with retry logic
- Event validation
