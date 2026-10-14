"""with_surfa(): captured events, for every supported server type, and the
"never hurts the server" guarantees."""

import gc
import statistics
import time

import pytest

from surfa_ingest import flush_surfa, with_surfa
import importlib

with_surfa_module = importlib.import_module("surfa_ingest.with_surfa")

from .conftest import TEST_KEY
from .servers import CLIENT_NAME, CLIENT_VERSION, FRAMEWORKS, STATELESS, connect, build_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def summary(events):
    return [f"{e['subtype']}:{e['tool_name']}" if e.get("tool_name") else e["subtype"] for e in events]


async def run_calls(framework, server):
    results = {}
    async with connect(framework, server) as call:
        results["add"] = await call("add", {"a": 2, "b": 3})
        results["divide"] = await call("divide", {"a": 1, "b": 0})
        results["search_notes"] = await call("search_notes", {"query": "surfa", "api_token": "s3cret", "limit": 1})
        results["late_tool"] = await call("late_tool", {"x": 4})
    return results


def wait_for_session_end(ingest, timeout=3.0):
    """Handshake protocol: the session ends when the client disconnects (the
    connection object is collected). Stateless protocol: at process exit."""
    if STATELESS:
        with_surfa_module.shutdown_surfa(2.0)
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        gc.collect()
        flush_surfa(1.0)
        if any(e["subtype"] == "session_ended" for e in ingest.events):
            return
        time.sleep(0.05)


@pytest.mark.parametrize("framework", FRAMEWORKS)
async def test_captures_one_session_with_every_call(framework, ingest):
    wrap = lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url, flush_delay_s=0)
    results = await run_calls(framework, build_server(framework, wrap))
    wait_for_session_end(ingest)

    assert summary(ingest.events) == [
        "session_started",
        "tool_call_started:add",
        "tool_call_completed:add",
        "tool_call_started:divide",
        "tool_call_failed:divide",
        "tool_call_started:search_notes",
        "tool_call_completed:search_notes",
        "tool_call_started:late_tool",
        "tool_call_completed:late_tool",
        "session_ended",
    ]
    events = ingest.events
    assert len({r["body"]["session_id"] for r in ingest.requests}) == 1

    started = events[0]
    assert started["client"] == {"name": CLIENT_NAME, "version": CLIENT_VERSION}
    assert started["protocol_version"]

    by_subtype = lambda subtype, tool: next(e for e in events if e["subtype"] == subtype and e.get("tool_name") == tool)
    assert by_subtype("tool_call_started", "add")["input"] == {"a": 2, "b": 3}
    assert by_subtype("tool_call_started", "search_notes")["input"] == {
        "query": "surfa",
        "api_token": "[REDACTED]",
        "limit": 1,
    }

    completed = by_subtype("tool_call_completed", "add")
    assert completed["status"] == "success"
    assert isinstance(completed["latency_ms"], int) and completed["latency_ms"] >= 0
    assert completed["response_bytes"] > 0
    assert completed["correlation_id"] == by_subtype("tool_call_started", "add")["correlation_id"]

    failed = by_subtype("tool_call_failed", "divide")
    assert failed["status"] == "error"
    if framework == "official" and STATELESS:
        # MCPServer (mcp 2.x) hides exception text from clients; we record what the client sees
        assert failed["error"] == "Error executing tool divide"
    else:
        assert "Cannot divide by zero" in failed["error"]
    assert failed["error_type"] == "tool_error"

    assert events[-1]["reason"] == ("shutdown" if STATELESS else "disconnected")

    # The tool results themselves are untouched
    assert results["add"] == (False, "5")
    assert results["divide"][0] is True
    assert results["late_tool"] == (False, "8")


@pytest.mark.parametrize("framework", FRAMEWORKS)
async def test_results_identical_with_and_without_surfa(framework, ingest):
    plain = await run_calls(framework, build_server(framework))
    wrapped = await run_calls(
        framework, build_server(framework, lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url))
    )
    assert wrapped == plain


async def test_posts_bodies_the_ingest_route_accepts(ingest):
    """Mirror of validateRequestBody() in apps/web/app/api/v1/ingest/events/route.ts,
    plus what the dashboard and metrics-v2 read (same checks as the TS contract test)"""
    framework = "fastmcp"
    wrap = lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url, flush_delay_s=0)
    await run_calls(framework, build_server(framework, wrap))
    wait_for_session_end(ingest)

    assert ingest.requests
    for request in ingest.requests:
        body = request["body"]
        assert request["path"] == "/api/v1/ingest/events"
        assert request["auth"] == f"Bearer {TEST_KEY}"
        assert isinstance(body["session_id"], str) and body["session_id"]
        assert isinstance(body["events"], list) and body["events"]
        assert all(isinstance(e["kind"], str) and e["kind"] for e in body["events"])
        assert isinstance(body["runtime"], dict)
        assert body["runtime"]["sdk"] == "with_surfa-py"
        for event in body["events"]:
            assert event["ts"].endswith("Z")
            if "latency_ms" in event:
                assert isinstance(event["latency_ms"], int)
            if event["kind"] == "tool":
                assert event["correlation_id"]

    # metrics-v2 reads payload.input (not `args`)
    assert all("args" not in e for e in ingest.events)
    assert {e["subtype"] for e in ingest.events} == {
        "session_started",
        "tool_call_started",
        "tool_call_completed",
        "tool_call_failed",
        "session_ended",
    }


async def test_wrapping_twice_does_not_double_count(ingest):
    framework = "fastmcp"
    wrap = lambda s: with_surfa(with_surfa(s, api_key=TEST_KEY, api_url=ingest.url), api_key=TEST_KEY, api_url=ingest.url)
    await run_calls(framework, build_server(framework, wrap))
    flush_surfa()
    assert len([e for e in ingest.events if e["subtype"] == "tool_call_started"]) == 4


async def test_session_ends_after_idle_timeout(ingest):
    framework = "fastmcp"
    server = build_server(
        framework,
        lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url, session_idle_timeout_s=0.5),
    )
    async with connect(framework, server) as call:
        await call("add", {"a": 1, "b": 1})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(e["subtype"] == "session_ended" for e in ingest.events):
            time.sleep(0.1)
        ended = [e for e in ingest.events if e["subtype"] == "session_ended"]
        assert ended and ended[0]["reason"] == "idle"

        # A later call on the same connection starts a new Surfa session
        await call("add", {"a": 2, "b": 2})
    flush_surfa()
    assert len({r["body"]["session_id"] for r in ingest.requests}) == 2


async def test_uploads_shortly_after_a_call_without_explicit_flush(ingest):
    framework = "fastmcp"
    server = build_server(framework, lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url))
    async with connect(framework, server) as call:
        await call("add", {"a": 1, "b": 1})
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not any(e["subtype"] == "tool_call_completed" for e in ingest.events):
            time.sleep(0.05)
        assert any(e["subtype"] == "tool_call_completed" for e in ingest.events)


# ---------------------------------------------------------------------------
# Never hurts the server


async def test_no_api_key_means_no_network_and_one_warning(ingest, capsys):
    framework = "fastmcp"
    plain = await run_calls(framework, build_server(framework))
    wrapped = await run_calls(framework, build_server(framework, lambda s: with_surfa(s, api_url=ingest.url)))
    with_surfa(build_server(framework), api_url=ingest.url)
    flush_surfa()

    assert wrapped == plain
    assert ingest.requests == []
    err = capsys.readouterr().err
    assert err.count("SURFA_API_KEY is not set") == 1
    assert capsys.readouterr().out == ""


async def test_reads_key_and_url_from_environment(ingest, monkeypatch):
    monkeypatch.setenv("SURFA_API_KEY", TEST_KEY)
    monkeypatch.setenv("SURFA_API_URL", ingest.url)
    framework = "fastmcp"
    await run_calls(framework, build_server(framework, lambda s: with_surfa(s, flush_delay_s=0)))
    flush_surfa()
    assert any(e["subtype"] == "tool_call_started" for e in ingest.events)


@pytest.mark.parametrize("mode", ["unreachable", "500", "429", "hang"])
async def test_tool_calls_unchanged_and_fast_when_surfa_is_down(mode, ingest):
    framework = "fastmcp"
    url = "http://127.0.0.1:9" if mode == "unreachable" else ingest.url
    ingest.mode = mode

    async def timed_calls(server, count=30):
        timings = []
        results = []
        async with connect(framework, server) as call:
            for i in range(count):
                started = time.perf_counter()
                results.append(await call("add", {"a": i, "b": 1}))
                timings.append(time.perf_counter() - started)
        return statistics.median(timings), results

    plain_time, plain = await timed_calls(build_server(framework))
    wrapped_time, wrapped = await timed_calls(
        build_server(framework, lambda s: with_surfa(s, api_key=TEST_KEY, api_url=url, timeout_s=0.5, max_queue_size=50))
    )
    assert wrapped == plain
    assert (wrapped_time - plain_time) * 1000 < 2, f"overhead {(wrapped_time - plain_time) * 1000:.2f} ms"

    for uploader in with_surfa_module._uploaders.values():
        assert uploader.queued <= 50


async def test_queue_never_exceeds_its_bound(ingest):
    ingest.mode = "hang"
    framework = "fastmcp"
    server = build_server(
        framework, lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url, timeout_s=5, max_queue_size=20)
    )
    async with connect(framework, server) as call:
        for i in range(60):
            await call("add", {"a": i, "b": 1})
            for uploader in with_surfa_module._uploaders.values():
                assert uploader.queued <= 20


async def test_rejected_key_disables_tracking_with_one_warning(ingest, capsys):
    ingest.mode = "401"
    framework = "fastmcp"
    server = build_server(framework, lambda s: with_surfa(s, api_key=TEST_KEY, api_url=ingest.url, flush_delay_s=0))
    async with connect(framework, server) as call:
        assert await call("add", {"a": 1, "b": 1}) == (False, "2")
        flush_surfa(2)
        assert await call("add", {"a": 2, "b": 2}) == (False, "4")
        flush_surfa(2)
    err = capsys.readouterr().err
    assert err.count("Surfa rejected the ingest key") == 1
    assert "key_not_found" in err
    # Names where the key came from: here the api_key argument, not the env var
    assert "Check the api_key passed to with_surfa()" in err


async def test_rejected_key_from_environment_names_the_variable(ingest, capsys, monkeypatch):
    ingest.mode = "401"
    monkeypatch.setenv("SURFA_API_KEY", TEST_KEY)
    server = build_server("fastmcp", lambda s: with_surfa(s, api_url=ingest.url, flush_delay_s=0))
    async with connect("fastmcp", server) as call:
        await call("add", {"a": 1, "b": 1})
        flush_surfa(2)
    assert "Check SURFA_API_KEY is the full key" in capsys.readouterr().err


async def test_invalid_key_format_is_a_warning_not_an_error(ingest, capsys):
    server = build_server("fastmcp", lambda s: with_surfa(s, api_key="not-a-key", api_url=ingest.url))
    assert (await run_calls("fastmcp", server))["add"] == (False, "5")
    assert "Invalid ingest key" in capsys.readouterr().err


def test_unsupported_object_is_returned_unchanged(capsys):
    thing = object()
    assert with_surfa(thing, api_key=TEST_KEY) is thing
    assert "expects a FastMCP, MCPServer or Server" in capsys.readouterr().err
