import os

os.environ["DEBUG"] = "True"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1"
os.environ.setdefault("CELERY_BROKER_URL", "memory://")

from . import settings as base_settings

for setting_name in dir(base_settings):
    if setting_name.isupper():
        globals()[setting_name] = getattr(base_settings, setting_name)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

INSTALLED_APPS = list(getattr(base_settings, "INSTALLED_APPS", []))

if "inbound_dashboard" not in INSTALLED_APPS:
    INSTALLED_APPS = [*INSTALLED_APPS, "inbound_dashboard"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
