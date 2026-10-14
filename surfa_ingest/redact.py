"""
Client-side masking of secrets in tool arguments

Runs before anything leaves the builder's server. Surfa also redacts PII
server-side; this layer is for credentials that should never be sent at all.
Same rules as the TypeScript SDK (packages/ingest/src/redact.ts).
"""

from typing import Any, Callable, Iterable, Optional, Set

REDACTED = "[REDACTED]"

# Key names (compared lower-cased, without `_`, `-` or spaces) whose values
# are always masked. A key matches if it contains any of these.
DEFAULT_SECRET_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "privatekey",
    "accesskey",
    "credential",
)

MAX_DEPTH = 8
MAX_STRING_LENGTH = 2000
MAX_ARRAY_ITEMS = 50


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch not in "_- \t")


def secret_key_matcher(extra_keys: Optional[Iterable[str]] = None) -> Callable[[str], bool]:
    """
    Build a predicate that says whether a key's value must be masked

    Args:
        extra_keys: More key names to mask, on top of the defaults
    """
    needles = [*DEFAULT_SECRET_KEYS, *(_normalize_key(k) for k in (extra_keys or ()))]
    needles = [n for n in needles if n]

    def is_secret(key: str) -> bool:
        normalized = _normalize_key(str(key))
        return any(needle in normalized for needle in needles)

    return is_secret


def mask_secrets(value: Any, is_secret_key: Callable[[str], bool]) -> Any:
    """
    Return a JSON-friendly copy of `value` with secret-looking keys masked,
    long strings truncated and very deep or large structures cut short.
    Never raises.
    """
    try:
        return _mask(value, is_secret_key, 0, set())
    except Exception:
        return "[unserializable]"


def _mask(value: Any, is_secret_key: Callable[[str], bool], depth: int, seen: Set[int]) -> Any:
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            return f"{value[:MAX_STRING_LENGTH]}… [truncated {len(value) - MAX_STRING_LENGTH} chars]"
        return value

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, (bytes, bytearray)):
        return f"[{len(value)} bytes]"

    # Pydantic models and dataclass-like objects: their fields
    if not isinstance(value, (dict, list, tuple, set, frozenset)):
        as_dict = _as_dict(value)
        if as_dict is None:
            return str(value)
        value = as_dict

    if id(value) in seen:
        return "[circular]"
    if depth >= MAX_DEPTH:
        return "[truncated]"
    seen.add(id(value))

    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            key_str = str(key)
            if is_secret_key(key_str) and not _is_plain_scalar(child):
                result[key_str] = REDACTED
            else:
                result[key_str] = _mask(child, is_secret_key, depth + 1, seen)
        return result

    items = list(value)
    masked = [_mask(item, is_secret_key, depth + 1, seen) for item in items[:MAX_ARRAY_ITEMS]]
    if len(items) > MAX_ARRAY_ITEMS:
        masked.append(f"[{len(items) - MAX_ARRAY_ITEMS} more items]")
    return masked


def _as_dict(value: Any) -> Optional[dict]:
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            result = dump(mode="json")
            return result if isinstance(result, dict) else None
        except Exception:
            return None
    fields = getattr(value, "__dict__", None)
    return dict(fields) if isinstance(fields, dict) else None


def _is_plain_scalar(value: Any) -> bool:
    """Numbers, booleans and None can't hold a credential, so keys like
    `max_tokens: 500` keep their value"""
    return value is None or isinstance(value, (bool, int, float))
