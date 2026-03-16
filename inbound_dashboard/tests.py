import os
from datetime import datetime, timezone

import django


def ensure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings_test")
    django.setup()


def test_make_naive_none_returns_none():
    ensure_django()
    from inbound_dashboard.views import make_naive

    assert make_naive(None) is None


def test_make_naive_with_naive_datetime_assumes_utc():
    ensure_django()
    from inbound_dashboard.views import make_naive

    value = datetime(2025, 1, 1, 0, 0, 0)
    result = make_naive(value)
    assert result == datetime(2025, 1, 1, 5, 30, 0)
    assert result.tzinfo is None


def test_make_naive_with_aware_datetime_converts_timezone():
    ensure_django()
    from inbound_dashboard.views import make_naive

    value = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = make_naive(value)
    assert result == datetime(2025, 1, 1, 5, 30, 0)
    assert result.tzinfo is None
