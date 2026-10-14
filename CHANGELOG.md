# Changelog

All notable changes to surfa-ingest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-14

### Added
- **`with_surfa(server)`**: one-line capture for MCP servers. Works with standalone FastMCP (2.x–4.x), the official SDK's `FastMCP` (1.x) and `MCPServer` (2.x), and the low-level `Server`. Captures every tool call (arguments with secrets masked, latency, errors, response size) and the client's name and version, grouped into sessions. Same events as the TypeScript `withSurfa`.
- `flush_surfa()` and `shutdown_surfa()` for serverless handlers and custom signal handlers.
- Uploads run on a background thread with a bounded queue, a 5 s timeout and at most one retry; tool calls never wait on Surfa and never see its errors.

### Changed
- `SurfaClient`'s default `api_url` is now `SURFA_API_URL`, else `https://app.surfa.dev` (was `http://localhost:3000`).

## [0.2.0] - 2026-02-22

### Added
- **MCP Context Auto-Detection** - Automatically extract `client_id`, `session_id`, and `request_id` from MCP context objects
  - Just pass `ctx` parameter to `track()` method
  - Works with FastMCP Context and future MCP frameworks
  - Backwards compatible (ctx is optional)
  - Never breaks tracking (fails gracefully)

### Example
```python
from fastmcp import FastMCP, Context

@mcp.tool
def my_tool(query: str, ctx: Context) -> dict:
    # Auto-extracts client_id, session_id, request_id!
    analytics.track({
        "kind": "tool",
        "subtype": "call_started"
    }, ctx=ctx)  # ✨ Magic happens here
```

### Benefits
- No more manual field extraction boilerplate
- Consistent tracking across all MCP servers
- Framework-agnostic design (easy to add support for new frameworks)

## [0.1.1] - 2026-02-21

### Added
- `task_completed` parameter to `session_end()` method
- Exported `generate_session_id` utility function for external use
- Context manager now automatically sets `task_completed` based on exception status

### Changed
- Updated README with MCP builder-focused value proposition
- Added privacy-first design section
- Improved quick start guide for MCP servers

### Use Case
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

## [0.1.0] - 2026-02-20

### Added
- Initial release
- Event buffering and batching
- Session management
- Context manager support
- Runtime metadata capture
- HTTP API integration with retry logic
- Event validation

[0.2.0]: https://github.com/gamladz/surfa-ingest/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/gamladz/surfa-ingest/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/gamladz/surfa-ingest/releases/tag/v0.1.0
