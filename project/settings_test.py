import os

os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")

from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

if "inbound_dashboard" not in INSTALLED_APPS:
    INSTALLED_APPS = [*INSTALLED_APPS, "inbound_dashboard"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
