"""
with_surfa(server): one-line live-traffic capture for Python MCP servers

    mcp = with_surfa(FastMCP("my-server"))

How it hooks in, by server type (verified against fastmcp 3.0.2 and 4.1.0,
mcp 1.30.0 and 2.3.0):

- Standalone FastMCP (`fastmcp`, 2.9+): a FastMCP middleware (`on_call_tool`),
  added outermost so it sees calls exactly as the client does.
- Official SDK 2.x (`mcp.server.mcpserver.MCPServer`, low-level
  `mcp.server.Server`): a context-tier middleware on the low-level server's
  `middleware` list.
- Official SDK 1.x (`mcp.server.fastmcp.FastMCP`, low-level
  `mcp.server.lowlevel.Server`) and fastmcp before 2.9: the low-level server's
  `tools/call` request handler is wrapped (again at `run()`, so a handler
  registered after wrapping is covered too).

Every hook sits on the single `tools/call` dispatch, so tools registered
before or after wrapping are all captured. Requests and results pass through
untouched; nothing here can raise into tool code.

Each MCP session (connection) becomes one Surfa session. Its `session_ended`
event goes out when the session object goes away (the client disconnected),
after `session_idle_timeout_s` without tool calls, or at process exit. Surfa
computes a session's metrics (redundant calls, batch opportunities) when it
ends; sessions that never end are closed server-side after 15 idle minutes.
"""

import atexit
import json
import os
import signal
import threading
import time
import uuid
import weakref
from typing import Any, Callable, Dict, Iterable, Optional

from .redact import mask_secrets, secret_key_matcher
from .uploader import DEFAULT_API_URL, Uploader, warn
from .utils import get_current_timestamp, validate_ingest_key

__all__ = ["with_surfa", "flush_surfa", "shutdown_surfa"]

_INSTRUMENTED_ATTR = "_surfa_instrumented"
MAX_ERROR_LENGTH = 1000
MAX_PENDING_CALLS = 1000
DEFAULT_IDLE_TIMEOUT_S = 15 * 60
# Longest a SIGTERM exit waits for the final upload
SIGNAL_FLUSH_TIMEOUT_S = 1.0
# Longest a normal exit waits for the final upload
EXIT_FLUSH_TIMEOUT_S = 2.0
# First MCP protocol version without a connection handshake (sessions)
STATELESS_PROTOCOL_VERSION = "2026-07-28"

_lock = threading.RLock()
# Uploaders shared by every wrapped server in the process, keyed by key + URL
_uploaders: Dict[str, Uploader] = {}
# Open sessions, keyed as described in _Recorder._session_for
_sessions: Dict[Any, "_Session"] = {}
_warned_missing_key = False
_exit_hooks_installed = False


def with_surfa(
    server: Any,
    *,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    capture_args: bool = True,
    redact_keys: Optional[Iterable[str]] = None,
    session_idle_timeout_s: float = DEFAULT_IDLE_TIMEOUT_S,
    max_queue_size: int = 1000,
    flush_delay_s: float = 0.25,
    timeout_s: float = 5.0,
    debug: bool = False,
) -> Any:
    """
    Send this MCP server's tool calls to Surfa.

        mcp = with_surfa(FastMCP("my-server"))

    Works with standalone FastMCP (`fastmcp`), the official SDK's
    `MCPServer` / `FastMCP` and its low-level `Server`. Call it before the
    server starts. Returns the same server, so it can wrap the constructor
    call. With no API key it does nothing except print one warning.

    Args:
        api_key: Workspace ingest key. Default: `SURFA_API_KEY`
        api_url: Surfa app URL. Default: `SURFA_API_URL`, else https://app.surfa.dev
        capture_args: Send tool arguments (secrets masked). Default True
        redact_keys: Extra argument key names to mask, on top of
            token/password/secret/api_key/authorization/...
        session_idle_timeout_s: End a Surfa session after this long without
            tool calls. 0 = only on disconnect or exit. Default 15 min
        max_queue_size: Most events held in memory while Surfa is slow or
            unreachable. Default 1000
        flush_delay_s: Upload this long after a tool call, batching what
            arrives meanwhile. Default 0.25; 0 = only on flush_surfa()
        timeout_s: Upload request timeout. Default 5
        debug: Log upload activity to stderr. Default False
    """
    try:
        _instrument(
            server,
            api_key=api_key,
            api_url=api_url,
            settings=_Settings(
                capture_args=capture_args,
                is_secret_key=secret_key_matcher(redact_keys),
                idle_timeout_s=session_idle_timeout_s,
            ),
            uploader_options={
                "max_queue_size": max_queue_size,
                "flush_delay_s": flush_delay_s,
                "timeout_s": timeout_s,
                "debug": debug,
            },
        )
    except Exception as error:
        warn(f"could not instrument this server; it will run without Surfa: {error}")
    return server


def flush_surfa(timeout_s: float = 5.0) -> None:
    """
    Upload queued events now, waiting at most `timeout_s`. Useful at the end
    of a serverless handler. Blocks the calling thread; from async code use
    `await asyncio.to_thread(flush_surfa)`. Never raises.
    """
    deadline = time.monotonic() + timeout_s
    for uploader in list(_uploaders.values()):
        try:
            uploader.flush(max(0.0, deadline - time.monotonic()))
        except Exception:
            pass


def shutdown_surfa(timeout_s: float = EXIT_FLUSH_TIMEOUT_S) -> None:
    """
    End open sessions and upload everything queued (at most `timeout_s`).
    Runs automatically at exit; call it from your own SIGTERM handler if you
    have one. Never raises.
    """
    try:
        with _lock:
            sessions = list(_sessions.values())
        for session in sessions:
            session.end("shutdown")
    except Exception:
        pass
    deadline = time.monotonic() + timeout_s
    with _lock:
        uploaders = list(_uploaders.values())
        _uploaders.clear()
    for uploader in uploaders:
        try:
            uploader.close(max(0.0, deadline - time.monotonic()))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Setup


class _Settings:
    def __init__(self, capture_args: bool, is_secret_key: Callable[[str], bool], idle_timeout_s: float):
        self.capture_args = capture_args
        self.is_secret_key = is_secret_key
        self.idle_timeout_s = idle_timeout_s


def _instrument(server: Any, *, api_key, api_url, settings: _Settings, uploader_options) -> None:
    hook = _find_hook(server)
    if hook is None:
        warn(
            "with_surfa() expects a FastMCP, MCPServer or Server from `fastmcp` or `mcp`; "
            "leaving this object as is"
        )
        return
    kind, target = hook

    if getattr(target, _INSTRUMENTED_ATTR, False):
        return

    framework = _framework_name(server)
    uploader = _get_uploader(api_key, api_url, framework, uploader_options)
    if uploader is None:
        return

    recorder = _Recorder(uploader, settings, framework)
    if kind == "fastmcp":
        _hook_fastmcp(target, recorder)
    elif kind == "mcp2":
        _hook_mcp2(target, recorder)
    else:
        _hook_mcp1(target, recorder)
    setattr(target, _INSTRUMENTED_ATTR, True)


def _find_hook(server: Any):
    """Which seam to use: ("fastmcp" | "mcp2" | "mcp1", object to hook)"""
    module = type(server).__module__ or ""

    # Standalone FastMCP with middleware (2.9+)
    if module.startswith("fastmcp") and callable(getattr(server, "add_middleware", None)):
        return "fastmcp", server

    # Official SDK 2.x: MCPServer wraps a low-level Server with a middleware list
    for candidate in (server, getattr(server, "_lowlevel_server", None)):
        if candidate is not None and isinstance(getattr(candidate, "middleware", None), list) and callable(
            getattr(candidate, "add_request_handler", None)
        ):
            return "mcp2", candidate

    # Official SDK 1.x FastMCP and older fastmcp wrap a low-level Server in
    # `_mcp_server`; the low-level Server has a `request_handlers` dict
    for candidate in (server, getattr(server, "_mcp_server", None)):
        if candidate is not None and isinstance(getattr(candidate, "request_handlers", None), dict):
            return "mcp1", candidate

    return None


def _framework_name(server: Any) -> str:
    package = (type(server).__module__ or "").split(".")[0]
    try:
        from importlib.metadata import version

        return f"{package}/{version(package)}"
    except Exception:
        return package or "unknown"


def _get_uploader(api_key, api_url, framework: str, options) -> Optional[Uploader]:
    global _warned_missing_key
    key = api_key or os.environ.get("SURFA_API_KEY")
    if not key:
        if not _warned_missing_key:
            _warned_missing_key = True
            warn("SURFA_API_KEY is not set; tool calls will not be sent to Surfa.")
        return None

    try:
        validate_ingest_key(key)
    except ValueError as error:
        warn(f"Invalid ingest key: {error}; tool calls will not be sent to Surfa.")
        return None

    url = (api_url or os.environ.get("SURFA_API_URL") or DEFAULT_API_URL).rstrip("/")
    cache_key = f"{key}|{url}"
    with _lock:
        existing = _uploaders.get(cache_key)
        if existing is not None:
            return existing
        uploader = Uploader(
            key,
            url,
            runtime={"mode": "mcp_server", "sdk": "with_surfa-py", "framework": framework},
            **options,
        )
        uploader.tick_callbacks.append(_end_idle_sessions)
        _uploaders[cache_key] = uploader
    _install_exit_hooks()
    return uploader


def _install_exit_hooks() -> None:
    """
    Upload what's left when the process ends:
    - normal exit, including Ctrl-C (KeyboardInterrupt): atexit
    - SIGTERM (hosts stopping containers; Claude Code after SIGINT): Python's
      default kills the process without running atexit. If nothing else
      handles SIGTERM, end sessions and upload (at most
      SIGNAL_FLUSH_TIMEOUT_S), then re-raise it so the process exits exactly
      as it would have without Surfa. A server's own handler is left alone.
    """
    global _exit_hooks_installed
    with _lock:
        if _exit_hooks_installed:
            return
        _exit_hooks_installed = True

    atexit.register(shutdown_surfa)

    try:
        if threading.current_thread() is not threading.main_thread():
            return
        if signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL:
            return

        def on_sigterm(signum, frame):
            try:
                shutdown_surfa(SIGNAL_FLUSH_TIMEOUT_S)
            finally:
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                os.kill(os.getpid(), signal.SIGTERM)

        signal.signal(signal.SIGTERM, on_sigterm)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Hooks


def _hook_fastmcp(server: Any, recorder: "_Recorder") -> None:
    from fastmcp.server.middleware import Middleware

    class SurfaMiddleware(Middleware):
        async def on_call_tool(self, context, call_next):
            mcp_session, http_request = _fastmcp_session(context)
            call = recorder.start(mcp_session, http_request, *_name_and_args(context.message))
            try:
                result = await call_next(context)
            except BaseException as error:
                recorder.finish_error(call, error)
                raise
            recorder.finish_result(call, result)
            return result

    middleware = getattr(server, "middleware", None)
    if isinstance(middleware, list):
        # Outermost: see calls as the client does, including ones other
        # middleware answer or reject
        middleware.insert(0, SurfaMiddleware())
    else:
        server.add_middleware(SurfaMiddleware())


def _fastmcp_session(context: Any):
    """(MCP session, HTTP request or None) for a FastMCP middleware context"""
    fastmcp_context = getattr(context, "fastmcp_context", None)
    try:
        session = fastmcp_context.session
    except Exception:
        session = None
    try:
        http_request = getattr(fastmcp_context.request_context, "request", None)
    except Exception:
        http_request = None
    return session, http_request


def _hook_mcp2(server: Any, recorder: "_Recorder") -> None:
    async def surfa_middleware(ctx, call_next):
        if getattr(ctx, "method", None) != "tools/call" or getattr(ctx, "request_id", None) is None:
            return await call_next(ctx)
        call = recorder.start(
            getattr(ctx, "session", None), getattr(ctx, "request", None), *_name_and_args(getattr(ctx, "params", None))
        )
        try:
            result = await call_next(ctx)
        except BaseException as error:
            recorder.finish_error(call, error)
            raise
        recorder.finish_result(call, result)
        return result

    server.middleware.insert(0, surfa_middleware)


def _hook_mcp1(server: Any, recorder: "_Recorder") -> None:
    from mcp import types

    def wrap_handler() -> None:
        original = server.request_handlers.get(types.CallToolRequest)
        if original is None or getattr(original, _INSTRUMENTED_ATTR, False):
            return

        async def handler(request):
            try:
                request_context = server.request_context
                session, http_request = request_context.session, getattr(request_context, "request", None)
            except Exception:
                session, http_request = None, None
            call = recorder.start(session, http_request, *_name_and_args(getattr(request, "params", None)))
            try:
                result = await original(request)
            except BaseException as error:
                recorder.finish_error(call, error)
                raise
            recorder.finish_result(call, result)
            return result

        setattr(handler, _INSTRUMENTED_ATTR, True)
        server.request_handlers[types.CallToolRequest] = handler

    wrap_handler()

    # A low-level Server may register its call_tool handler after with_surfa()
    original_run = server.run

    async def run(*args, **kwargs):
        try:
            wrap_handler()
        except Exception:
            pass
        return await original_run(*args, **kwargs)

    server.run = run


def _name_and_args(params: Any):
    """(tool name, arguments) from a dict or a params model"""
    if params is None:
        return None, None
    if isinstance(params, dict) or hasattr(params, "get") and not hasattr(params, "name"):
        try:
            return params.get("name"), params.get("arguments")
        except Exception:
            return None, None
    return getattr(params, "name", None), getattr(params, "arguments", None)


# ---------------------------------------------------------------------------
# Recording


class _Call:
    __slots__ = ("session", "tool_name", "correlation_id", "started_at", "done")

    def __init__(self, session: "_Session", tool_name: str, correlation_id: str):
        self.session = session
        self.tool_name = tool_name
        self.correlation_id = correlation_id
        self.started_at = time.perf_counter()
        self.done = False


class _Recorder:
    """Turns tool calls seen by a hook into Surfa events. Never raises."""

    def __init__(self, uploader: Uploader, settings: _Settings, framework: str):
        self.uploader = uploader
        self.settings = settings
        self.framework = framework
        # Calls with no MCP session object share one session per server
        self._fallback_key = object()

    def start(self, mcp_session: Any, http_request: Any, tool_name: Any, arguments: Any) -> Optional[_Call]:
        try:
            if not isinstance(tool_name, str):
                return None
            session = self._session_for(mcp_session, http_request)
            if session.pending >= MAX_PENDING_CALLS:
                return None
            surfa_session_id = session.ensure_started()
            call = _Call(session, tool_name, str(uuid.uuid4()))
            with _lock:
                session.pending += 1
                session.last_activity = time.monotonic()

            event = _event("tool", "tool_call_started", tool_name=tool_name, correlation_id=call.correlation_id)
            if self.settings.capture_args:
                event["input"] = mask_secrets(arguments if arguments is not None else {}, self.settings.is_secret_key)
            self.uploader.track(surfa_session_id, event)
            return call
        except Exception:
            return None

    def finish_result(self, call: Optional[_Call], result: Any) -> None:
        if call is None:
            return
        try:
            is_error, content = _result_error_and_content(result)
            response_bytes = _byte_length(result)
            if is_error:
                self._finish(call, _tool_error_text(content), "tool_error", None, response_bytes)
            else:
                self._finish(call, None, None, None, response_bytes)
        except Exception:
            pass

    def finish_error(self, call: Optional[_Call], error: BaseException) -> None:
        if call is None:
            return
        try:
            message, error_type, code = _classify_exception(error)
            self._finish(call, message, error_type, code, None)
        except Exception:
            pass

    def _finish(self, call: _Call, error, error_type, error_code, response_bytes) -> None:
        with _lock:
            if call.done:
                return
            call.done = True
            session = call.session
            session.pending = max(0, session.pending - 1)
            session.last_activity = time.monotonic()
            surfa_session_id = session.surfa_session_id

        if surfa_session_id is None:
            return  # the session ended (e.g. shutdown) while the tool ran
        latency_ms = max(0, int(round((time.perf_counter() - call.started_at) * 1000)))
        fields: Dict[str, Any] = {"correlation_id": call.correlation_id, "latency_ms": latency_ms}
        if response_bytes is not None:
            fields["response_bytes"] = response_bytes

        if error is not None:
            fields["error_type"] = error_type
            if error_code is not None:
                fields["error_code"] = error_code
            event = _event(
                "tool",
                "tool_call_failed",
                tool_name=call.tool_name,
                status="error",
                error=_truncate(error, MAX_ERROR_LENGTH),
                **fields,
            )
        else:
            event = _event("tool", "tool_call_completed", tool_name=call.tool_name, status="success", **fields)
        self.uploader.track(surfa_session_id, event)
        if session.per_call:
            session.end("completed")

    def _session_for(self, mcp_session: Any, http_request: Any) -> "_Session":
        """
        Which Surfa session a call belongs to.

        - Protocol versions with a handshake (before 2026-07-28): the MCP
          connection. Its object lives as long as the client is connected,
          so its finalizer ends the session on disconnect.
        - Stateless protocol (2026-07-28+, mcp 2.x / fastmcp 4.x): every
          request gets a fresh connection object, so group by the HTTP
          session id if there is one; over stdio (no HTTP request) one
          process serves one client, so group by process. Stateless HTTP
          without a session id has nothing to group by: one session per call.
        """
        connection = getattr(mcp_session, "_connection", None)
        protocol_version = _protocol_version(mcp_session)
        owner: Any = None
        per_call = False

        if mcp_session is None:
            key: Any = ("process", id(self))
        elif protocol_version and protocol_version >= STATELESS_PROTOCOL_VERSION:
            http_session_id = getattr(connection, "session_id", None)
            if http_session_id:
                key = ("http", id(self), http_session_id)
            elif http_request is None:
                key = ("process", id(self))
            else:
                key = ("call", uuid.uuid4().hex)
                per_call = True
        else:
            owner = connection if connection is not None else mcp_session
            key = ("connection", id(owner))

        with _lock:
            session = _sessions.get(key)
            if session is not None and session.recorder is self:
                return session
            session = _Session(key, self, mcp_session, per_call)
            _sessions[key] = session
        if owner is not None:
            try:
                # The connection object goes away when the client disconnects
                weakref.finalize(owner, _on_mcp_session_gone, session)
            except TypeError:
                pass  # not weak-referenceable: ended when idle or at exit
        return session


class _Session:
    """One MCP session (connection); one Surfa session while it has activity"""

    def __init__(self, key: Any, recorder: _Recorder, mcp_session: Any, per_call: bool = False):
        self.key = key
        self.recorder = recorder
        self.per_call = per_call
        self.surfa_session_id: Optional[str] = None
        self.pending = 0
        self.last_activity = time.monotonic()
        # Read client info when the session starts; don't keep the MCP session alive
        try:
            self._mcp_session_ref = weakref.ref(mcp_session) if mcp_session is not None else None
        except TypeError:
            self._mcp_session_ref = None

    def ensure_started(self) -> str:
        with _lock:
            if self.surfa_session_id is not None:
                return self.surfa_session_id
            self.surfa_session_id = str(uuid.uuid4())
            surfa_session_id = self.surfa_session_id
            _sessions[self.key] = self

        fields: Dict[str, Any] = {"framework": self.recorder.framework}
        client, protocol_version = self._client_info()
        if client:
            fields["client"] = client
        if protocol_version:
            fields["protocol_version"] = protocol_version
        self.recorder.uploader.track(surfa_session_id, _event("session", "session_started", **fields))
        return surfa_session_id

    def end(self, reason: str) -> None:
        with _lock:
            surfa_session_id = self.surfa_session_id
            self.surfa_session_id = None
            self.pending = 0
            if _sessions.get(self.key) is self:
                del _sessions[self.key]
        if surfa_session_id is None:
            return
        uploader = self.recorder.uploader
        uploader.track(surfa_session_id, _event("session", "session_ended", reason=reason))
        # Upload now: after a disconnect the process may be killed within seconds
        if reason == "disconnected":
            uploader.request_flush()

    def _client_info(self):
        try:
            mcp_session = self._mcp_session_ref() if self._mcp_session_ref else None
            params = getattr(mcp_session, "client_params", None)
            if params is None:
                return None, None
            info = getattr(params, "clientInfo", None) or getattr(params, "client_info", None)
            client = None
            if info is not None:
                client = {"name": getattr(info, "name", None), "version": getattr(info, "version", None)}
            protocol_version = getattr(params, "protocolVersion", None) or getattr(params, "protocol_version", None)
            return client, protocol_version
        except Exception:
            return None, None


def _protocol_version(mcp_session: Any) -> Optional[str]:
    for source in (getattr(mcp_session, "_connection", None), getattr(mcp_session, "client_params", None)):
        for name in ("protocol_version", "protocolVersion"):
            try:
                value = getattr(source, name, None)
            except Exception:
                value = None
            if isinstance(value, str) and value:
                return value
    return None


def _on_mcp_session_gone(session: _Session) -> None:
    try:
        session.end("disconnected")
    except Exception:
        pass


def _end_idle_sessions() -> None:
    now = time.monotonic()
    with _lock:
        idle = [
            session
            for session in _sessions.values()
            if session.surfa_session_id is not None
            and session.pending == 0
            and session.recorder.settings.idle_timeout_s > 0
            and now - session.last_activity >= session.recorder.settings.idle_timeout_s
        ]
    for session in idle:
        session.end("idle")


# ---------------------------------------------------------------------------
# Helpers


def _event(kind: str, subtype: str, **fields: Any) -> Dict[str, Any]:
    event = {key: value for key, value in fields.items() if value is not None}
    event.update({"kind": kind, "subtype": subtype, "ts": get_current_timestamp()})
    return event


def _unwrap(result: Any) -> Any:
    # mcp 1.x low-level handlers return ServerResult(root=CallToolResult)
    root = getattr(result, "root", None)
    return root if root is not None and not isinstance(result, dict) else result


def _result_error_and_content(result: Any):
    result = _unwrap(result)
    if isinstance(result, dict):
        return bool(result.get("isError") or result.get("is_error")), result.get("content")
    is_error = getattr(result, "is_error", None)
    if is_error is None:
        is_error = getattr(result, "isError", False)
    return bool(is_error), getattr(result, "content", None)


def _tool_error_text(content: Any) -> str:
    texts = []
    for part in content or []:
        if isinstance(part, dict):
            kind, text = part.get("type"), part.get("text")
        else:
            kind, text = getattr(part, "type", None), getattr(part, "text", None)
        if kind == "text" and isinstance(text, str):
            texts.append(text)
    return "\n".join(texts) or "Tool returned an error"


def _byte_length(result: Any) -> Optional[int]:
    try:
        result = _unwrap(result)
        dump_json = getattr(result, "model_dump_json", None)
        if callable(dump_json):
            return len(dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
        return len(json.dumps(result, default=str).encode("utf-8"))
    except Exception:
        return None


def _classify_exception(error: BaseException):
    """(message, error_type, error_code) for an exception raised by a tool call"""
    if not isinstance(error, Exception):
        # asyncio/anyio cancellation (the client cancelled or disconnected)
        return "Cancelled", "cancelled", None

    # McpError (1.x) / MCPError (2.x): a JSON-RPC error response
    rpc_error = getattr(error, "error", None)
    code = getattr(rpc_error, "code", None)
    if isinstance(code, int):
        return str(getattr(rpc_error, "message", "") or error), "protocol_error", code

    name = type(error).__name__
    if name == "ValidationError":
        # Pydantic messages carry the client's input; don't send them
        return "Invalid request parameters", "protocol_error", -32602
    if "NotFound" in name:
        return str(error) or name, "protocol_error", None
    return str(error) or name, "tool_error", None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}…"


def _reset_for_tests() -> None:
    """For tests: forget uploaders and sessions"""
    global _warned_missing_key
    with _lock:
        uploaders = list(_uploaders.values())
        _uploaders.clear()
        _sessions.clear()
        _warned_missing_key = False
    for uploader in uploaders:
        uploader.close(0.5)
