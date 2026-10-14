"""
Background uploader used by with_surfa()

Built so it can never hurt the process it runs in (same rules as the
TypeScript SDK's client):
- `track()` never blocks and never does I/O. Uploads run on one daemon
  thread, one request at a time, shortly after events arrive.
- The queue is bounded (`max_queue_size`); past it, new events are dropped.
- Nothing here raises into the caller. Unreachable, slow (timeout), rate
  limited or failing Surfa means dropped events, not errors.
- Messages go to stderr only (stdout is the MCP stdio channel).
"""

import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

INGEST_PATH = "/api/v1/ingest/events"
DEFAULT_API_URL = "https://app.surfa.dev"

# Events per request; keeps request bodies small
MAX_EVENTS_PER_REQUEST = 100
# Longest pause honoured from a 429 Retry-After
MAX_RATE_LIMIT_PAUSE_S = 60.0
RETRY_DELAY_S = 0.5


def warn(message: str) -> None:
    """Print a one-line warning to stderr. Never raises."""
    try:
        print(f"[surfa] {message}", file=sys.stderr, flush=True)
    except Exception:
        pass


class Uploader:
    def __init__(
        self,
        ingest_key: str,
        api_url: str,
        *,
        max_queue_size: int = 1000,
        flush_delay_s: float = 0.25,
        timeout_s: float = 5.0,
        max_retries: int = 1,
        runtime: Optional[Dict[str, Any]] = None,
        debug: bool = False,
        key_source: str = "SURFA_API_KEY",
    ) -> None:
        self.ingest_key = ingest_key
        self.api_url = api_url.rstrip("/")
        self.max_queue_size = max_queue_size
        self.flush_delay_s = flush_delay_s
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.runtime = runtime
        self.debug = debug
        # Where the key came from, named in the rejected-key warning
        self.key_source = key_source

        self._queue: List[Tuple[str, Dict[str, Any]]] = []
        self._cond = threading.Condition()
        self._flush_requested = False
        self._flush_at: Optional[float] = None
        self._in_flight = False
        self._paused_until = 0.0
        self._disabled = False
        self._closed = False
        self._warned_queue_full = False
        self._session = requests.Session()
        self.stats = {"sent": 0, "dropped": 0, "failed_requests": 0}
        # Called on the upload thread about once a second (idle-session checks)
        self.tick_callbacks: List[Any] = []

        self._thread = threading.Thread(target=self._run, name="surfa-uploader", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ API

    def track(self, session_id: str, event: Dict[str, Any]) -> bool:
        """Queue an event. Never blocks on I/O. False if it was dropped."""
        with self._cond:
            if self._disabled or self._closed:
                return False
            if len(self._queue) >= self.max_queue_size:
                self.stats["dropped"] += 1
                if not self._warned_queue_full:
                    self._warned_queue_full = True
                    warn(f"event queue full ({self.max_queue_size}); dropping events until Surfa catches up")
                return False
            self._queue.append((session_id, event))
            if self.flush_delay_s > 0 and self._flush_at is None:
                self._flush_at = time.monotonic() + self.flush_delay_s
                self._cond.notify_all()
            return True

    def request_flush(self) -> None:
        """Upload as soon as possible, without waiting"""
        with self._cond:
            self._flush_requested = True
            self._cond.notify_all()

    def flush(self, timeout_s: float = 5.0) -> bool:
        """
        Upload everything queued and wait, at most `timeout_s`, for it to go
        out. True if the queue drained in time. Never raises.
        """
        deadline = time.monotonic() + max(0.0, timeout_s)
        with self._cond:
            self._flush_requested = True
            self._cond.notify_all()
            while (self._queue or self._in_flight) and not self._disabled:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                # Events queued during an upload go out in the next one
                self._flush_requested = True
                self._cond.notify_all()
                self._cond.wait(remaining)
            return True

    def close(self, timeout_s: float = 5.0) -> bool:
        """Upload what's left (bounded wait), then stop accepting events"""
        drained = self.flush(timeout_s)
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        return drained

    @property
    def queued(self) -> int:
        with self._cond:
            return len(self._queue)

    # --------------------------------------------------------------- thread

    def _run(self) -> None:
        last_tick = time.monotonic()
        while True:
            # Idle-session checks run outside the lock: they take the
            # wrapper's own lock and then queue events
            if time.monotonic() - last_tick >= 1.0:
                last_tick = time.monotonic()
                self._run_ticks()

            with self._cond:
                if self._closed and not self._queue:
                    return
                now = time.monotonic()
                due = self._flush_requested or (self._flush_at is not None and now >= self._flush_at)
                if not (self._queue and due and now >= self._paused_until):
                    if not self._queue:
                        self._flush_requested = False
                        self._flush_at = None
                        self._cond.notify_all()  # flush() waiters: nothing left
                    wait = 1.0
                    if self._queue and self._flush_at is not None:
                        wait = min(wait, max(0.0, self._flush_at - now))
                    if self._queue and self._paused_until > now:
                        wait = min(wait, self._paused_until - now)
                    self._cond.wait(wait)
                    continue

                batch, self._queue = self._queue, []
                self._flush_requested = False
                self._flush_at = None
                self._warned_queue_full = False
                self._in_flight = True

            try:
                self._upload(batch)
            except Exception as error:  # defensive: the thread must not die
                self._log(f"upload failed: {error}")
            finally:
                with self._cond:
                    self._in_flight = False
                    if self._queue and self._flush_at is None and self.flush_delay_s > 0:
                        self._flush_at = time.monotonic() + self.flush_delay_s
                    self._cond.notify_all()

    def _run_ticks(self) -> None:
        for callback in list(self.tick_callbacks):
            try:
                callback()
            except Exception:
                pass

    def _upload(self, batch: List[Tuple[str, Dict[str, Any]]]) -> None:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for session_id, event in batch:
            groups.setdefault(session_id, []).append(event)

        for session_id, events in groups.items():
            for i in range(0, len(events), MAX_EVENTS_PER_REQUEST):
                chunk = events[i : i + MAX_EVENTS_PER_REQUEST]
                if self._disabled or time.monotonic() < self._paused_until:
                    self._record_dropped(len(chunk))
                    continue
                outcome = self._send_with_retries(session_id, chunk)
                if outcome == "sent":
                    with self._cond:
                        self.stats["sent"] += len(chunk)
                else:
                    self._record_dropped(len(chunk))

    def _record_dropped(self, count: int) -> None:
        with self._cond:
            self.stats["dropped"] += count

    def _send_with_retries(self, session_id: str, events: List[Dict[str, Any]]) -> str:
        attempt = 0
        while True:
            outcome = self._send(session_id, events)
            if outcome != "retry":
                return outcome
            self.stats["failed_requests"] += 1
            if attempt >= self.max_retries:
                return "drop"
            attempt += 1
            time.sleep(RETRY_DELAY_S)

    def _send(self, session_id: str, events: List[Dict[str, Any]]) -> str:
        body: Dict[str, Any] = {"session_id": session_id, "events": events}
        if self.runtime:
            body["runtime"] = self.runtime

        try:
            response = self._session.post(
                f"{self.api_url}{INGEST_PATH}",
                json=body,
                headers={"Authorization": f"Bearer {self.ingest_key}"},
                timeout=self.timeout_s,
            )
        except requests.Timeout:
            self._log(f"upload timed out after {self.timeout_s}s")
            return "retry"
        except Exception as error:
            self._log(f"upload failed: {error}")
            return "retry"

        status = response.status_code
        if 200 <= status < 300:
            self._log(f"sent {len(events)} event(s) for session {session_id}")
            return "sent"

        if status in (401, 403):
            with self._cond:
                self._disabled = True
                self._queue = []
                self._cond.notify_all()
            reason = _rejection_reason(response)
            warn(
                f"Surfa rejected the ingest key (HTTP {status}{': ' + reason if reason else ''}). "
                f"Key used: {self.ingest_key[:16]}… ({len(self.ingest_key)} chars), sent to {self.api_url}. "
                f"Check {self.key_source} is the full key shown once when it was created "
                "(Surfa → Settings → API Keys). Tracking is off until restart."
            )
            return "unauthorized"

        if status == 429:
            try:
                pause = float(response.headers.get("retry-after", ""))
            except ValueError:
                pause = 0.0
            pause = pause if pause > 0 else 10.0
            self._paused_until = time.monotonic() + min(pause, MAX_RATE_LIMIT_PAUSE_S)
            self.stats["failed_requests"] += 1
            self._log(f"rate limited; pausing uploads for {round(pause)}s")
            return "rate_limited"

        if status >= 500:
            self._log(f"Surfa returned HTTP {status}")
            return "retry"

        # Other 4xx: the request itself was rejected; retrying won't help
        self.stats["failed_requests"] += 1
        self._log(f"Surfa rejected {len(events)} event(s): HTTP {status} {response.text[:200]}")
        return "drop"

    def _log(self, message: str) -> None:
        if self.debug:
            warn(message)


def _rejection_reason(response: Any) -> str:
    """Surfa's explanation for a 401/403, e.g. "API key not found (key_not_found)" """
    try:
        body = response.json()
        error = body.get("error") if isinstance(body.get("error"), str) else ""
        code = body.get("code") if isinstance(body.get("code"), str) else ""
        return " ".join(part for part in (error, f"({code})" if code else "") if part)
    except Exception:
        return ""
