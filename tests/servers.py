"""
The same small server built with each supported framework, plus an
in-memory client for each. Which frameworks exist depends on the installed
`mcp` major version (1.x ships FastMCP, 2.x ships MCPServer).
"""

import importlib.metadata
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

MCP_MAJOR = int(importlib.metadata.version("mcp").split(".")[0])
# mcp 2.x clients speak the stateless protocol (2026-07-28): no connection to
# follow, so over stdio/in-memory a process is one session, ended at exit
STATELESS = MCP_MAJOR >= 2

FRAMEWORKS: List[str] = ["fastmcp", "official", "lowlevel"]

CLIENT_NAME = "test-client"
CLIENT_VERSION = "3.1.0"


def build_server(framework: str, wrap: Optional[Callable[[Any], Any]] = None):
    """
    Tools: add (sync), divide (async, raises on b == 0), search_notes (secret
    argument), and late_tool, registered after `wrap` runs.
    """
    if framework == "lowlevel":
        return _build_lowlevel(wrap)

    if framework == "fastmcp":
        from fastmcp import FastMCP

        server = FastMCP("example")
        tool = server.tool
    elif MCP_MAJOR >= 2:
        from mcp.server.mcpserver import MCPServer

        server = MCPServer("example")
        tool = server.tool()
    else:
        from mcp.server.fastmcp import FastMCP

        server = FastMCP("example")
        tool = server.tool()

    def add(a: int, b: int) -> int:
        """Add two numbers"""
        return a + b

    async def divide(a: float, b: float) -> float:
        """Divide a by b"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    async def search_notes(query: str, api_token: str = "", limit: int = 5) -> str:
        """Search notes"""
        return json.dumps({"query": query, "results": ["a", "b"][:limit]})

    tool(add)
    tool(divide)
    tool(search_notes)

    if wrap:
        server = wrap(server)

    def late_tool(x: int) -> int:
        """Registered after with_surfa()"""
        return x * 2

    (server.tool if framework == "fastmcp" else server.tool())(late_tool)
    return server


def _build_lowlevel(wrap):
    from mcp import types

    async def call(name: str, arguments: Dict[str, Any]) -> List[Any]:
        if name == "add":
            return [types.TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]
        if name == "divide":
            if arguments["b"] == 0:
                raise ValueError("Cannot divide by zero")
            return [types.TextContent(type="text", text=str(arguments["a"] / arguments["b"]))]
        if name == "late_tool":
            return [types.TextContent(type="text", text=str(arguments["x"] * 2))]
        if name == "search_notes":
            return [types.TextContent(type="text", text="ok")]
        raise ValueError(f"Unknown tool: {name}")

    tools = [
        types.Tool(name=name, description=name, inputSchema={"type": "object"})
        for name in ("add", "divide", "search_notes", "late_tool")
    ]

    if MCP_MAJOR >= 2:
        from mcp.server import Server

        async def on_list_tools(ctx, params):
            return types.ListToolsResult(tools=tools)

        async def on_call_tool(ctx, params):
            try:
                content = await call(params.name, params.arguments or {})
            except ValueError as error:
                return types.CallToolResult(content=[types.TextContent(type="text", text=str(error))], isError=True)
            return types.CallToolResult(content=content)

        server = Server("example", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
        return wrap(server) if wrap else server

    from mcp.server.lowlevel import Server

    server = Server("example")
    if wrap:
        server = wrap(server)

    # Registered after wrapping on purpose: covered when the server runs
    @server.list_tools()
    async def list_tools():
        return tools

    @server.call_tool()
    async def call_tool(name, arguments):
        return await call(name, arguments)

    return server


@asynccontextmanager
async def connect(framework: str, server: Any) -> AsyncIterator[Callable[..., Any]]:
    """Yields `call(name, args) -> (is_error, text)` over an in-memory connection"""
    if framework == "fastmcp":
        from fastmcp import Client
        from mcp.types import Implementation

        async with Client(server, client_info=Implementation(name=CLIENT_NAME, version=CLIENT_VERSION)) as client:

            async def call(name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
                if hasattr(client, "call_tool_mcp"):  # raw result, also on fastmcp < 2.10
                    result = await client.call_tool_mcp(name, args)
                else:
                    result = await client.call_tool(name, args, raise_on_error=False)
                return _is_error(result), _text(result.content)

            yield call
        return

    from mcp.types import Implementation

    info = Implementation(name=CLIENT_NAME, version=CLIENT_VERSION)
    if MCP_MAJOR >= 2:
        from mcp.client import Client

        async with Client(server, client_info=info) as client:

            async def call(name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
                result = await client.call_tool(name, args)
                return _is_error(result), _text(result.content)

            yield call
        return

    from mcp.shared.memory import create_connected_server_and_client_session

    if not hasattr(server, "create_initialization_options"):  # FastMCP on mcp < 1.11
        server = server._mcp_server
    async with create_connected_server_and_client_session(server, client_info=info) as session:

        async def call(name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
            result = await session.call_tool(name, args)
            return _is_error(result), _text(result.content)

        yield call


def _is_error(result: Any) -> bool:
    value = getattr(result, "is_error", None)
    return bool(getattr(result, "isError", False) if value is None else value)


def _text(content: Any) -> str:
    return "\n".join(getattr(part, "text", "") for part in content or [])
