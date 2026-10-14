"""Shared fixtures: a fake Surfa ingest endpoint and a clean wrapper state."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

import pytest

from surfa_ingest.with_surfa import _reset_for_tests

TEST_KEY = "sk_live_test_key_0123456789abcdef"


class FakeIngest:
    """Records POST /api/v1/ingest/events bodies. `mode` changes its behaviour."""

    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        self.mode = "ok"  # ok | 500 | 429 | 401 | hang
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if fake.mode == "hang":
                    time.sleep(10)
                    return
                if fake.mode == "ok":
                    fake.requests.append({"path": self.path, "body": body, "auth": self.headers.get("authorization")})
                    self._reply(200, {"ok": True, "execution_id": "exec-1"})
                elif fake.mode == "429":
                    self._reply(429, {"error": "slow down"}, {"retry-after": "1"})
                elif fake.mode == "401":
                    self._reply(401, {"error": "API key not found", "code": "key_not_found"})
                else:
                    self._reply(500, {"error": "boom"})

            def _reply(self, status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def events(self) -> List[Dict[str, Any]]:
        return [event for request in self.requests for event in request["body"]["events"]]

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def ingest():
    fake = FakeIngest()
    yield fake
    _reset_for_tests()
    fake.stop()


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("SURFA_API_KEY", raising=False)
    monkeypatch.delenv("SURFA_API_URL", raising=False)
    yield
    _reset_for_tests()
