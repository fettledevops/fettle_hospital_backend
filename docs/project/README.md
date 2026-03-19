# Project Package Docs

## Modules

| Module | Role | Notes |
| --- | --- | --- |
| `project/__init__.py` | Celery app export | Re-exports `celery_app`. |
| `project/asgi.py` | ASGI bootstrap | Standard Django ASGI entrypoint. |
| `project/celery.py` | Celery bootstrap | Configures Celery and autodiscovers tasks. |
| `project/jwt_auth.py` | JWT creation and DRF auth | Custom bearer-token authentication classes. |
| `project/settings.py` | Main runtime settings | Env loading, PostgreSQL, CORS, Celery, static config. |
| `project/settings_test.py` | Test-only settings | In-memory SQLite, eager Celery, fast hashers. |
| `project/tests.py` | Auth tests | Verifies JWT payload and expiry behavior. |
| `project/urls.py` | Route registry | Central API URL map. |
| `project/wsgi.py` | WSGI bootstrap | Standard Django WSGI entrypoint. |

## Notes

### `project/__init__.py`

Exports the Celery application as `celery_app`.

### `project/asgi.py`

Thin ASGI bootstrap for async deployment targets.

### `project/celery.py`

Initializes Celery with Django settings, applies the `CELERY_` namespace, autodiscovers tasks, and exposes `debug_task`.

### `project/jwt_auth.py`

Defines the token contract used by most protected endpoints:

- `create_token(payload, timeout=120)` adds an `exp` claim using `settings.SECRET_KEY`
- `JWTAuthentication` reads bearer tokens from `Authorization`
- `JWTAuthenticationUrl` supports query-string token auth

The project uses custom JWT payloads instead of Django's built-in auth user model.

### `project/settings.py`

Main runtime settings file. Key behaviors:

- loads environment variables from `.env`
- uses PostgreSQL by default
- switches database SSL mode based on `DEBUG`
- requires explicit `SECRET_KEY`, `DB_PASSWORD`, and non-wildcard `ALLOWED_HOSTS` in production
- enables `corsheaders`, `rest_framework`, `app`, `phone_calling`, `django_celery_results`, and `sslserver`

Notable detail: `inbound_dashboard` is not listed in `INSTALLED_APPS`, but its views are still imported in the URLConf because that package currently contributes views only.

### `project/settings_test.py`

Overrides runtime settings for tests:

- forces `DEBUG=True`
- uses in-memory SQLite
- uses MD5 password hashing
- runs Celery tasks eagerly
- appends `inbound_dashboard` when needed

### `project/tests.py`

Regression tests around token payload fields and timeout handling.

### `project/urls.py`

Single flat URL registry for the backend API. This is the best high-level map of the request surface.

### `project/wsgi.py`

Thin WSGI bootstrap for sync deployment targets.
