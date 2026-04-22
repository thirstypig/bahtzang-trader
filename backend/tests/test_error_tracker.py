"""Unit tests for app/error_tracker.py.

Tests the in-memory error ring buffer: record, retrieve, eviction, lookup.
"""

import pytest

from app.error_tracker import (
    _errors,
    record_error,
    get_recent_errors,
    get_error_by_ref,
    get_error_count,
)


@pytest.fixture(autouse=True)
def clear_error_buffer():
    """Reset the global error ring buffer before each test."""
    _errors.clear()
    yield
    _errors.clear()


@pytest.mark.unit
class TestRecordAndRetrieve:
    def test_record_and_retrieve_error(self):
        """record_error stores an error that get_recent_errors returns."""
        ref = record_error(
            ValueError("something went wrong"),
            path="/api/trade",
            method="POST",
            user_email="test@example.com",
            error_code="TRADE_FAILED",
        )

        assert ref.startswith("ERR-")
        assert len(ref) == 10  # ERR- + 6 hex chars

        errors = get_recent_errors()
        assert len(errors) == 1
        assert errors[0]["ref"] == ref
        assert errors[0]["message"] == "something went wrong"
        assert errors[0]["path"] == "/api/trade"
        assert errors[0]["method"] == "POST"
        assert errors[0]["error_code"] == "TRADE_FAILED"

    def test_recent_errors_ordered_most_recent_first(self):
        """get_recent_errors returns newest errors first."""
        ref1 = record_error(RuntimeError("first"))
        ref2 = record_error(RuntimeError("second"))
        ref3 = record_error(RuntimeError("third"))

        errors = get_recent_errors()
        assert errors[0]["ref"] == ref3
        assert errors[1]["ref"] == ref2
        assert errors[2]["ref"] == ref1

    def test_recent_errors_respects_limit(self):
        """get_recent_errors returns at most `limit` entries."""
        for i in range(10):
            record_error(RuntimeError(f"error {i}"))

        errors = get_recent_errors(limit=3)
        assert len(errors) == 3


@pytest.mark.unit
class TestRingBufferEviction:
    def test_ring_buffer_evicts_oldest_when_full(self):
        """Deque maxlen=100 means oldest entries are evicted at capacity."""
        refs = []
        for i in range(110):
            ref = record_error(RuntimeError(f"error {i}"))
            refs.append(ref)

        # Buffer holds max 100 entries
        assert get_error_count() == 100

        # First 10 should be evicted
        for old_ref in refs[:10]:
            assert get_error_by_ref(old_ref) is None

        # Last 100 should still be present
        for recent_ref in refs[10:]:
            assert get_error_by_ref(recent_ref) is not None


@pytest.mark.unit
class TestGetErrorByRef:
    def test_returns_full_error_for_known_ref(self):
        """get_error_by_ref returns the full error dict including stack trace."""
        ref = record_error(
            TypeError("bad type"),
            path="/api/analyze",
            method="GET",
            user_email="admin@example.com",
        )

        result = get_error_by_ref(ref)
        assert result is not None
        assert result["ref"] == ref
        assert result["error_type"] == "TypeError"
        assert result["message"] == "bad type"
        assert result["path"] == "/api/analyze"
        assert result["method"] == "GET"
        assert result["user_email"] == "admin@example.com"
        assert "stack" in result
        assert "timestamp" in result

    def test_returns_none_for_unknown_ref(self):
        """get_error_by_ref returns None when ref code doesn't exist."""
        result = get_error_by_ref("ERR-000000")
        assert result is None

    def test_returns_none_for_empty_buffer(self):
        """get_error_by_ref returns None on an empty buffer."""
        result = get_error_by_ref("ERR-abcdef")
        assert result is None


@pytest.mark.unit
class TestGetErrorCount:
    def test_returns_zero_initially(self):
        """Empty buffer has count 0."""
        assert get_error_count() == 0

    def test_returns_correct_count(self):
        """Count matches number of recorded errors."""
        record_error(RuntimeError("one"))
        record_error(RuntimeError("two"))
        record_error(RuntimeError("three"))
        assert get_error_count() == 3

    def test_count_caps_at_buffer_size(self):
        """Count never exceeds the ring buffer maxlen (100)."""
        for i in range(150):
            record_error(RuntimeError(f"error {i}"))
        assert get_error_count() == 100
