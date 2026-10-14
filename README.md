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

## Quick Start: one line

```bash
pip install surfa-ingest
```

```python
from fastmcp import FastMCP
from surfa_ingest import with_surfa

mcp = with_surfa(FastMCP("my-server"))
```

Set `SURFA_API_KEY` (create one at [app.surfa.dev](https://app.surfa.dev) → Settings → API Keys) and every tool call shows up in your dashboard: tool name, arguments (secrets masked), latency, errors, and which client called it. No per-tool decorators; tools added later are captured too.

Works with:

| Server | Versions tested |
|---|---|
| `fastmcp` `FastMCP` | 2.8, 2.9, 2.14, 3.0, 3.4, 4.1 |
| Official SDK `mcp.server.fastmcp.FastMCP` (mcp 1.x) | 1.9, 1.10, 1.26, 1.30 |
| Official SDK `mcp.server.mcpserver.MCPServer` (mcp 2.x) | 2.3 |
| Low-level `mcp.server.Server` (1.x and 2.x) | as above |

It never hurts your server: events are queued in memory (bounded) and uploaded on a background thread; if Surfa is slow, down or rejects the key, tool calls behave exactly as before. Messages go to stderr only, never stdout (the stdio channel).

| Option | Env var | Default |
|---|---|---|
| `api_key` | `SURFA_API_KEY` | required (without it, one warning and nothing is sent) |
| `api_url` | `SURFA_API_URL` | `https://app.surfa.dev` |
| `capture_args` | | `True` |
| `redact_keys` | | extra key names to mask, on top of password/secret/token/api_key/authorization/cookie/... |
| `session_idle_timeout_s` | | `900` |
| `flush_delay_s` | | `0.25` |
| `debug` | | `False` (log uploads to stderr) |

Serverless or short-lived processes: call `flush_surfa()` before returning. A server with its own SIGTERM handler should call `shutdown_surfa()` in it.

Full guide: [docs.surfa.dev/python-setup](https://docs.surfa.dev/python-setup). Example: [`examples/fastmcp_server.py`](examples/fastmcp_server.py).

### Manual events (advanced)

`SurfaClient` sends events you build yourself, for code that isn't an MCP server:

```python
import os

from surfa_ingest import SurfaClient

with SurfaClient(ingest_key=os.environ["SURFA_API_KEY"]) as client:
    client.tool_started("search", args={"query": "mcp"})
    client.tool_completed("search", latency_ms=120)
```

For MCP servers prefer `with_surfa()`: it records the fields Surfa's metrics read (`input`, `correlation_id`, sessions per client connection), which manual events often miss.

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
