"""In-memory error ring buffer with unique reference codes.

Stores the last 100 errors with ERR-XXXXXX reference codes for
easy lookup without needing Railway logs. Thread-safe via deque.
"""

import os
import traceback
from collections import deque
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class ErrorEntry:
    ref: str
    error_type: str
    message: str
    stack: str
    path: str
    method: str
    user_email: str
    timestamp: str
    error_code: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_summary(self) -> dict:
        """Short version for list views (no stack trace)."""
        return {
            "ref": self.ref,
            "error_code": self.error_code,
            "message": self.message[:120],
            "path": self.path,
            "method": self.method,
            "timestamp": self.timestamp,
        }


# Ring buffer — thread-safe, fixed size, oldest entries auto-evicted
_errors: deque[ErrorEntry] = deque(maxlen=100)


def _generate_ref() -> str:
    """Generate ERR-XXXXXX reference code (6 hex chars)."""
    return f"ERR-{os.urandom(3).hex()}"


def record_error(
    exception: Exception,
    path: str = "",
    method: str = "",
    user_email: str = "",
    error_code: str = "INTERNAL_ERROR",
) -> str:
    """Record an error and return its reference code."""
    ref = _generate_ref()
    entry = ErrorEntry(
        ref=ref,
        error_type=type(exception).__name__,
        message=str(exception)[:500],
        stack=traceback.format_exc()[-2000:],  # Last 2000 chars of traceback
        path=path,
        method=method,
        user_email=user_email,
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_code=error_code,
    )
    _errors.append(entry)
    return ref


def get_recent_errors(limit: int = 20) -> list[dict]:
    """Return most recent errors (summary, no stack traces)."""
    errors = list(_errors)
    errors.reverse()  # Most recent first
    return [e.to_summary() for e in errors[:limit]]


def get_error_by_ref(ref: str) -> dict | None:
    """Look up a specific error by reference code (includes full stack)."""
    for entry in _errors:
        if entry.ref == ref:
            return entry.to_dict()
    return None


def get_error_count() -> int:
    """Total errors currently in the buffer."""
    return len(_errors)
