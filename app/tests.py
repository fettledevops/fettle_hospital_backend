import os

import django
import pytest


def ensure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings_test")
    django.setup()


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (24, "24th"),
    ],
)
def test_get_ordinal(value, expected):
    ensure_django()
    from app.views import get_ordinal

    assert get_ordinal(value) == expected
