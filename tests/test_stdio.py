"""
A real stdio server process (examples/fastmcp_server.py), driven with raw
JSON-RPC like an MCP client would: events arrive when the client closes
stdin, and when the process is stopped with SIGTERM.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .conftest import TEST_KEY

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "fastmcp_server.py"


def start_server(ingest):
    env = {**os.environ, "SURFA_API_KEY": TEST_KEY, "SURFA_API_URL": ingest.url, "FASTMCP_SHOW_SERVER_BANNER": "false"}
    process = subprocess.Popen(
        [sys.executable, str(EXAMPLE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    def send(message):
        process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        process.stdin.flush()

    def request(id, method, params):
        send({"id": id, "method": method, "params": params})
        while True:
            reply = json.loads(process.stdout.readline())
            if reply.get("id") == id:
                return reply

    request(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "raw-client", "version": "1.0"}})
    send({"method": "notifications/initialized"})
    add = request(2, "tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}})
    divide = request(3, "tools/call", {"name": "divide", "arguments": {"a": 1, "b": 0}})
    assert add["result"]["isError"] is False
    assert divide["result"]["isError"] is True
    return process


def subtypes(ingest):
    return [e["subtype"] for e in ingest.events]


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_client_closes_stdin(ingest):
    process = start_server(ingest)
    process.stdin.close()
    assert process.wait(10) == 0

    assert subtypes(ingest) == [
        "session_started",
        "tool_call_started",
        "tool_call_completed",
        "tool_call_started",
        "tool_call_failed",
        "session_ended",
    ]
    assert ingest.events[0]["client"] == {"name": "raw-client", "version": "1.0"}


def test_sigterm_uploads_then_exits_by_the_signal(ingest):
    process = start_server(ingest)
    time.sleep(0.1)
    started = time.monotonic()
    process.send_signal(signal.SIGTERM)
    code = process.wait(10)
    elapsed = time.monotonic() - started

    assert code == -signal.SIGTERM
    assert elapsed < 3
    assert "tool_call_failed" in subtypes(ingest)
    assert subtypes(ingest)[-1] == "session_ended"
    assert ingest.events[-1]["reason"] == "shutdown"


def test_server_answers_normally_when_surfa_is_unreachable(ingest):
    ingest.stop()
    ingest.url = "http://127.0.0.1:9"
    process = start_server(ingest)
    process.stdin.close()
    started = time.monotonic()
    assert process.wait(10) == 0
    # Exit waits at most a couple of seconds for the final upload
    assert time.monotonic() - started < 4
