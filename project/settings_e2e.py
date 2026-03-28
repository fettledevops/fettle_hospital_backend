from .settings import (
    BASE_DIR,
    INSTALLED_APPS,
    MIDDLEWARE,
    TEMPLATES,
    AUTH_PASSWORD_VALIDATORS,
    LANGUAGE_CODE,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    STATIC_URL,
    DEFAULT_AUTO_FIELD,
    REST_FRAMEWORK,
    CORS_ALLOW_ALL_ORIGINS,
    DEBUG,
    SECRET_KEY,
    ALLOWED_HOSTS,
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_e2e.sqlite3",
    }
}
