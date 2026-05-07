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


def test_full_width_chars_normalize_via_nfkc(make_settings):
    """Full-width Unicode digits/letters should normalize to ASCII so the
    allow-list compares equal regardless of input form. Prevents a
    federated identity provider (or attacker upstream) from delivering
    a visually-equivalent variant that bypasses the gate."""
    # "ｓｏｌｏ＠ｅｘａｍｐｌｅ．ｃｏｍ" — full-width chars (U+FF53 etc.)
    s = make_settings("ｓｏｌｏ＠ｅｘａｍｐｌｅ．ｃｏｍ")
    # NFKC folds full-width to ASCII
    assert s.allowed_emails == ["solo@example.com"]


def test_unicode_homoglyph_does_not_silently_match_ascii(make_settings):
    """Cyrillic 'а' (U+0430) looks like Latin 'a' (U+0061) but is a
    different codepoint. NFKC does NOT fold Cyrillic→Latin (they're
    semantically different), so an env value 'а@x.com' (Cyrillic) must
    NOT match 'a@x.com' (Latin) at the comparison layer.

    The casefold + NFKC combo gives us a *consistent* compare surface
    without collapsing distinct scripts together — the right tradeoff
    for an allow-list."""
    cyrillic_a = "а"  # Cyrillic 'а'
    latin_a = "a"          # Latin 'a'
    s = make_settings(f"{cyrillic_a}@x.com")
    # The parsed entry stays as the Cyrillic form (NFKC keeps Cyrillic)
    assert s.allowed_emails == [f"{cyrillic_a}@x.com"]
    # And does NOT match a Latin-a lookup
    assert f"{latin_a}@x.com" not in s.allowed_emails
