# Changelog

All notable changes to surfa-ingest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
