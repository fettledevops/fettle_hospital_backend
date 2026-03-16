from datetime import datetime, timezone

from inbound_dashboard.views import make_naive


def test_make_naive_none_returns_none():
    assert make_naive(None) is None


def test_make_naive_with_naive_datetime_assumes_utc():
    value = datetime(2025, 1, 1, 0, 0, 0)
    result = make_naive(value)
    assert result == datetime(2025, 1, 1, 5, 30, 0)
    assert result.tzinfo is None


def test_make_naive_with_aware_datetime_converts_timezone():
    value = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = make_naive(value)
    assert result == datetime(2025, 1, 1, 5, 30, 0)
    assert result.tzinfo is None
