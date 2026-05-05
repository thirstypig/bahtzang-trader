"""Auth allow-list parsing — supports both single-email and CSV multi-user."""

import os

import pytest


@pytest.fixture
def make_settings():
    """Build a fresh Settings() with a temporary ALLOWED_EMAIL value."""
    from app.config import Settings

    def _make(value: str):
        os.environ["ALLOWED_EMAIL"] = value
        return Settings()

    original = os.environ.get("ALLOWED_EMAIL")
    yield _make
    if original is not None:
        os.environ["ALLOWED_EMAIL"] = original


def test_single_email_parses_to_one_entry(make_settings):
    s = make_settings("solo@example.com")
    assert s.allowed_emails == ["solo@example.com"]


def test_csv_emails_parse_to_list(make_settings):
    s = make_settings("a@example.com,b@example.com,c@example.com")
    assert s.allowed_emails == ["a@example.com", "b@example.com", "c@example.com"]


def test_csv_strips_whitespace(make_settings):
    s = make_settings("  a@x.com , b@x.com ")
    assert s.allowed_emails == ["a@x.com", "b@x.com"]


def test_csv_lowercases_for_case_insensitive_match(make_settings):
    s = make_settings("Owner@Example.com,Buddy@Example.com")
    assert s.allowed_emails == ["owner@example.com", "buddy@example.com"]


def test_empty_segments_dropped(make_settings):
    s = make_settings("a@x.com,,b@x.com,")
    assert s.allowed_emails == ["a@x.com", "b@x.com"]
