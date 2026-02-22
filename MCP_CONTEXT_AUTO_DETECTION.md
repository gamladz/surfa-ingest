# MCP Context Auto-Detection - User Story

## Problem Statement

MCP servers are distributed and accessed through multiple modes, making it difficult for MCP builders to track client context consistently:

### Distribution Models

1. **Local (stdio)** - Installed on user's machine
   - Distributed via: npm, PyPI, GitHub, binaries
   - Examples: `npx @mycompany/mcp-server`, `pip install my-mcp`
   - Used by: Claude Desktop, Cursor, VS Code
   - Transport: stdio (Standard Input/Output)

2. **Remote (SSE)** - Hosted as a service
   - Distributed via: Hosted URL, cloud platforms
   - Examples: `https://mcp.stripe.com`, `https://my-mcp.com/sse`
   - Used by: Claude API, OpenAI API, custom clients
   - Transport: SSE/HTTP

3. **Hybrid** - Both local and remote
   - Example: Stripe offers both `npx @stripe/mcp` and `https://mcp.stripe.com`

### The Challenge

**Different modes expose different context:**

| Mode | client_id | session_id | client_name | client_version |
|------|-----------|------------|-------------|----------------|
| **stdio (local)** | Maybe | Maybe | ❌ Not exposed by FastMCP | ❌ Not exposed |
| **SSE (remote)** | Maybe | Maybe | ❌ Not in HTTP headers | ❌ Not available |
| **Claude API → SSE** | Maybe ("claude-api"?) | Yes | ❌ Proxy, not end client | ❌ Not available |
| **OpenAI API → SSE** | Maybe ("openai-api"?) | Yes | ❌ Proxy, not end client | ❌ Not available |

**Current Problem:**
MCP builders using `surfa-ingest` must manually extract context from MCP framework objects (like FastMCP's `Context`), leading to:
- ❌ Boilerplate code in every tool handler
- ❌ Inconsistent tracking across different MCP servers
- ❌ Easy to forget to pass context
- ❌ Framework-specific code (tight coupling)

**Example of current manual approach:**
```python
@mcp.tool
def my_tool(param: str, ctx: Context) -> str:
    # Manual extraction (boilerplate!)
    client_id = ctx.client_id if ctx and hasattr(ctx, 'client_id') else None
    session_id = ctx.session_id if ctx and hasattr(ctx, 'session_id') else None
    
    analytics.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "my_tool",
        "client_id": client_id,      # Manual
        "session_id": session_id,    # Manual
        "user_id": "user_123"
    })
    
    # ... tool logic
```

## User Story

**As an MCP builder**  
**I want** to automatically capture client context from MCP framework objects  
**So that** I don't have to manually extract context in every tool handler

### Acceptance Criteria

1. ✅ MCP builder can optionally pass MCP context object to `track()`
2. ✅ SDK automatically extracts available fields (`client_id`, `session_id`)
3. ✅ Works with multiple MCP frameworks (FastMCP, future frameworks)
4. ✅ Never breaks tracking if context is missing or malformed
5. ✅ Backwards compatible (context parameter is optional)
6. ✅ No boilerplate code required in tool handlers

## Proposed Solution

### SDK Enhancement

Add optional `ctx` parameter to `track()` method with automatic context extraction:

```python
# In surfa-ingest SDK (surfa_ingest/client.py)

class SurfaClient:
    def track(
        self, 
        event: dict, 
        ctx: Optional[Any] = None  # MCP Context object (FastMCP, etc.)
    ) -> None:
        """
        Track an event with optional MCP context auto-extraction.
        
        Args:
            event: Event dictionary to track
            ctx: Optional MCP context object (e.g., FastMCP Context)
                 If provided, automatically extracts client_id, session_id, etc.
        
        Example:
            # Without context (backwards compatible)
            analytics.track({"kind": "tool", "subtype": "call_started"})
            
            # With context (auto-extraction)
            @mcp.tool
            def my_tool(ctx: Context) -> str:
                analytics.track({
                    "kind": "tool",
                    "subtype": "call_started"
                }, ctx=ctx)  # Auto-extracts client_id, session_id!
        """
        # Auto-extract context if provided
        if ctx:
            self._extract_mcp_context(ctx, event)
        
        # Continue with normal tracking
        self._send_event(event)
    
    def _extract_mcp_context(self, ctx: Any, event: dict) -> None:
        """
        Extract available fields from MCP context object.
        Supports multiple MCP frameworks. Never raises exceptions.
        """
        try:
            # Extract client_id if available (FastMCP Context)
            if hasattr(ctx, 'client_id') and ctx.client_id:
                event.setdefault('client_id', ctx.client_id)
                logger.debug(f"Extracted client_id from context: {ctx.client_id}")
            
            # NOTE: We do NOT extract session_id from MCP context
            # The SDK's self.session_id is used for grouping events into executions
            # MCP's ctx.session_id is a different concept (protocol session)
            # Extracting it would create multiple executions instead of one
            
            # Extract request_id if available (FastMCP Context)
            if hasattr(ctx, 'request_id') and ctx.request_id:
                event.setdefault('request_id', ctx.request_id)
                logger.debug(f"Extracted request_id from context: {ctx.request_id}")
            
            # elif isinstance(ctx, OtherMCPContext):
            #     event.setdefault('client_id', ctx.get_client_id())
            
            # 3. Future: Extract provider from HTTP headers (if available)
            # if hasattr(ctx, 'request_context') and ctx.request_context:
            #     # Could detect OpenAI vs Claude from User-Agent
            #     pass
            
        except Exception as e:
            # Always fail gracefully - never break tracking
            # Log warning but continue
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to extract MCP context (non-fatal): {e}"
            )
```

### Usage Examples

**Before (Manual):**
```python
@mcp.tool
def search(query: str, ctx: Context) -> dict:
    # Boilerplate extraction
    client_id = ctx.client_id if ctx and hasattr(ctx, 'client_id') else None
    session_id = ctx.session_id if ctx and hasattr(ctx, 'session_id') else None
    
    analytics.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "search",
        "client_id": client_id,
        "session_id": session_id
    })
    
    # ... tool logic
```

**After (Automatic):**
```python
@mcp.tool
def search(query: str, ctx: Context) -> dict:
    # Clean, simple - just pass ctx!
    analytics.track({
        "kind": "tool",
        "subtype": "call_started",
        "tool_name": "search"
    }, ctx=ctx)  # Auto-extracts client_id, session_id!
    
    # ... tool logic
```

**Backwards Compatible:**
```python
# Still works without ctx
analytics.track({
    "kind": "tool",
    "subtype": "call_started",
    "tool_name": "search"
})  # No ctx - works fine!
```

## Benefits

1. ✅ **Zero cognitive load** - Just pass `ctx` if you have it
2. ✅ **DRY** - No repeated extraction logic
3. ✅ **Framework agnostic** - Works with FastMCP, future frameworks
4. ✅ **Fail-safe** - Never breaks tracking, even if context is malformed
5. ✅ **Backwards compatible** - Existing code continues to work
6. ✅ **Future-proof** - Easy to add support for new frameworks/fields
7. ✅ **Consistent** - All MCP servers track context the same way

## Implementation Checklist

- [ ] Add `ctx` parameter to `SurfaClient.track()` method
- [ ] Implement `_extract_mcp_context()` helper method
- [ ] Add FastMCP Context support (client_id, session_id, request_id)
- [ ] Add comprehensive error handling (never break tracking)
- [ ] Add logging for extraction failures (warnings only)
- [ ] Write unit tests for context extraction
- [ ] Write unit tests for graceful failure cases
- [ ] Update README with examples
- [ ] Update CHANGELOG
- [ ] Bump version to 0.2.0 (minor feature addition)
- [ ] Publish to PyPI

## Future Enhancements

### Phase 2: Provider Detection
```python
# Auto-detect if request came from OpenAI vs Claude API
if hasattr(ctx, 'request_context'):
    headers = ctx.request_context.headers
    user_agent = headers.get('user-agent', '')
    
    if 'openai' in user_agent.lower():
        event.setdefault('provider', 'openai')
    elif 'anthropic' in user_agent.lower():
        event.setdefault('provider', 'claude')
```

### Phase 3: Support More Frameworks
```python
# Support other MCP frameworks beyond FastMCP
elif isinstance(ctx, ModelContextProtocolContext):
    # Extract from official MCP SDK
    pass
elif isinstance(ctx, CustomMCPContext):
    # Support custom implementations
    pass
```

### Phase 4: Metadata Enrichment
```python
# Auto-extract request metadata if available
if hasattr(ctx, 'request_context') and ctx.request_context.meta:
    meta = ctx.request_context.meta
    if hasattr(meta, 'user_id'):
        event.setdefault('user_id', meta.user_id)
    if hasattr(meta, 'trace_id'):
        event.setdefault('trace_id', meta.trace_id)
```

## Related Documentation

- [FastMCP Context Documentation](https://gofastmcp.com/servers/context)
- [MCP Protocol Specification](https://modelcontextprotocol.io/docs)
- [Claude API MCP Connector](https://platform.claude.com/docs/en/agents-and-tools/mcp-connector)
- [OpenAI MCP Support](https://developers.openai.com/api/docs/guides/tools-connectors-mcp/)

## Success Metrics

- ✅ Reduced boilerplate code in MCP server implementations
- ✅ Increased adoption of context tracking (easier = more usage)
- ✅ Zero tracking failures due to context extraction errors
- ✅ Positive feedback from MCP builders on ease of use

---

**Status:** 📋 Planned  
**Priority:** Medium  
**Estimated Effort:** 1-2 days  
**Target Version:** 0.2.0
