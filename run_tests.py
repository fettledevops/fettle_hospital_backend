#!/usr/bin/env python3
import os
import sys


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings_test")
    import pytest

    test_labels = sys.argv[1:] or ["app", "phone_calling", "inbound_dashboard", "project"]
    return pytest.main(test_labels)


if __name__ == "__main__":
    raise SystemExit(main())
