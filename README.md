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

**For different MCP distribution modes:**

<details>
<summary><b>Local MCP (stdio) - npm/PyPI package</b></summary>

Add to your `pyproject.toml`:
```toml
[project]
dependencies = [
    "surfa-ingest>=0.2.0",
    "fastmcp>=2.0.0"
]
```

Or `requirements.txt`:
```
surfa-ingest>=0.2.0
fastmcp>=2.0.0
```

Users install your MCP locally:
```bash
pip install your-mcp-server
```
</details>

<details>
<summary><b>Remote MCP (SSE) - Hosted service</b></summary>

Add to your server's `requirements.txt`:
```
surfa-ingest>=0.2.0
fastmcp>=2.0.0
```

Deploy to cloud (Vercel, Railway, Fly.io, etc.):
```bash
# Set environment variables
SURFA_INGEST_KEY=sk_live_your_key
SURFA_API_URL=https://surfa.dev
```

Users connect via URL (no installation needed):
```json
{
  "mcp_servers": [{
    "type": "url",
    "url": "https://your-mcp.com/sse"
  }]
}
```
</details>

### 2. Add to Your MCP Server

Choose the example that matches your distribution mode:

<details>
<summary><b>Local MCP (stdio) - Claude Desktop, Cursor</b></summary>

```python
from surfa_ingest import SurfaClient
from fastmcp import FastMCP
import os

# Initialize analytics
analytics = SurfaClient(
    ingest_key=os.getenv("SURFA_INGEST_KEY", "sk_live_your_key"),
    api_url=os.getenv("SURFA_API_URL", "https://surfa.dev")
)

# Set runtime for local stdio mode
analytics.set_runtime(
    provider="mcp",
    model="your-mcp-server-name",
    mode="stdio"  # Local mode
)

# Initialize MCP server
mcp = FastMCP("Your MCP Server")

@mcp.tool
def search_database(query: str) -> dict:
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
    analytics.flush()
    
    return result

# Run in stdio mode (for Claude Desktop)
if __name__ == "__main__":
    mcp.run()  # Defaults to stdio
```

**Users configure in Claude Desktop:**
```json
{
  "mcpServers": {
    "your-mcp": {
      "command": "npx",
      "args": ["-y", "your-mcp-server"]
    }
  }
}
```
</details>

<details>
<summary><b>Remote MCP (SSE) - Claude API, OpenAI API</b></summary>

```python
from surfa_ingest import SurfaClient
from fastmcp import FastMCP
import os

# Initialize analytics
analytics = SurfaClient(
    ingest_key=os.getenv("SURFA_INGEST_KEY", "sk_live_your_key"),
    api_url=os.getenv("SURFA_API_URL", "https://surfa.dev")
)

# Set runtime for remote SSE mode
analytics.set_runtime(
    provider="mcp",
    model="your-mcp-server-name",
    mode="sse"  # Remote mode
)

# Initialize MCP server
mcp = FastMCP("Your MCP Server", stateless_http=True)

@mcp.tool
def search_database(query: str) -> dict:
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
    analytics.flush()
    
    return result

# Run in HTTP/SSE mode
if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
        path="/mcp"
    )
```

**Users connect via URL:**
```python
# Claude API
response = client.messages.create(
    model="claude-opus-4",
    mcp_servers=[{
        "type": "url",
        "url": "https://your-mcp.com/mcp"
    }]
)

# OpenAI API
response = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_url": "https://your-mcp.com/mcp"
    }]
)
```
</details>

#### With MCP Context Auto-Detection (v0.2.0+)

**NEW:** Automatically extract `client_id`, `session_id`, and `request_id` from MCP context!

```python
from surfa_ingest import SurfaClient
from fastmcp import FastMCP, Context

analytics = SurfaClient(ingest_key="sk_live_...")
mcp = FastMCP("My MCP Server")

@mcp.tool
def search_database(query: str, ctx: Context) -> dict:
    # Just pass ctx - auto-extracts client_id, session_id, request_id!
    analytics.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "search_database"
    }, ctx=ctx)  # ✨ Auto-extraction happens here
    
    result = perform_search(query)
    
    analytics.track({
        "kind": "tool",
        "subtype": "call_completed",
        "tool_name": "search_database",
        "status": "success"
    }, ctx=ctx)
    
    return result
```

**Benefits:**
- ✅ No manual field extraction
- ✅ Works with FastMCP and future MCP frameworks
- ✅ Backwards compatible (ctx is optional)
- ✅ Never breaks tracking (fails gracefully)

**What gets auto-extracted:**
- `client_id` - Client identifier (if available from MCP context)
- `request_id` - Request identifier (for correlating MCP requests)

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

## Key Features

- 🚀 **Event Buffering** - Automatic batching with configurable buffer size
- 🔄 **Auto-Retry** - Built-in retry logic with exponential backoff
- 📦 **Context Manager** - Automatic session lifecycle management
- 🏷️ **Runtime Metadata** - Track AI provider, model, and configuration
- ✨ **MCP Context Auto-Detection** (v0.2.0+) - Automatically extract client_id, session_id from MCP context
- 📊 **Deterministic Agent Metrics** - Track task completion, retries, recovery, and performance metrics that traditional analytics platforms don't provide
- ✅ **Event Validation** - Client-side validation before sending
- 🔍 **Correlation IDs** - Link related events together
- 🛡️ **Type Safety** - Full type hints and IDE autocomplete
- 🔒 **Privacy-First** - No PII by default, user opt-out support

> **What makes Surfa different:** We calculate deterministic metrics like task completion, retry detection, and recovery rates automatically from your event stream - metrics that generic analytics platforms can't provide because they don't understand AI agent behavior.

## Learn More

### 📚 Documentation

- **[Full API Reference](https://docs.surfa.dev/sdk/api)** - Complete method documentation
- **[Deterministic Metrics](https://docs.surfa.dev/metrics)** - How we calculate task completion, retries, and recovery
- **[Advanced Usage](https://docs.surfa.dev/sdk/advanced)** - Context managers, error handling, logging
- **[Examples](https://docs.surfa.dev/sdk/examples)** - More code examples for different use cases

### 🔗 Links

- 📦 **PyPI**: https://pypi.org/project/surfa-ingest/
- 📝 **Changelog**: [CHANGELOG.md](./CHANGELOG.md)
- 🐛 **Issues**: https://github.com/gamladz/surfa/issues
- 💬 **Discussions**: https://github.com/gamladz/surfa/discussions

## Quick Reference

### Deterministic Metrics (Auto-Calculated)

When you send events using this SDK, the Surfa platform automatically calculates these metrics for each execution:

### Automatically Calculated Metrics

| Metric | Definition | How It's Calculated |
|--------|-----------|-------------------|
| **Task Completion** | Whether the task was actually completed | Uses `task_completed` field if present, otherwise infers from event sequence |
| **Tool Calls** | Total number of tool invocations | Count of `tool_call_started` events |
| **Retries** | Repeated calls with same tool+args | Detected from `tool_name` + `payload.input` matching |
| **Recovery** | Agent recovered from errors | First success after any failure |
| **Latency** | P50, P95, P99 latencies | Calculated from `latency_ms` distribution |

**[See full metrics documentation →](https://docs.surfa.dev/metrics)**

---

## Development Status

**Current Version: 0.2.0 (Alpha)**

This SDK is in active development. The API may change in future versions.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

---

**Made with ❤️ for MCP builders**
