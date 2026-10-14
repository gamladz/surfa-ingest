"""
A small FastMCP server with Surfa capture: one line, `with_surfa(...)`.

    pip install surfa-ingest fastmcp
    SURFA_API_KEY=sk_live_... python examples/fastmcp_server.py

Connect it to Claude Desktop, Claude Code or MCP Inspector and call a few
tools; they appear in Surfa → Analytics and Sessions within seconds.
"""

import json

from fastmcp import FastMCP

from surfa_ingest import with_surfa

mcp = with_surfa(FastMCP("surfa-example"))


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool
async def divide(a: float, b: float) -> float:
    """Divide a by b (fails when b is 0, to show a failed call)"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


@mcp.tool
def search_notes(query: str, api_token: str = "", limit: int = 5) -> str:
    """Search notes. `api_token` is masked before anything is sent to Surfa."""
    notes = ["MCP servers expose tools", "Surfa finds wasted tool calls", "Batch similar calls"]
    hits = [note for note in notes if query.lower() in note.lower()][:limit]
    return json.dumps({"query": query, "results": hits})


if __name__ == "__main__":
    mcp.run()
