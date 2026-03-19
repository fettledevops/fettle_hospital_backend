# Support Module Docs

## Modules

| Module | Role | Notes |
| --- | --- | --- |
| `manage.py` | Django CLI entrypoint | Sets `DJANGO_SETTINGS_MODULE` to `project.settings`. |
| `conftest.py` | Pytest bootstrap | Configures Django test settings. |
| `run_tests.py` | Test runner convenience script | Defaults to the app packages. |
| `seed_data.py` | Development seed script | Seeds hospital, patients, escalations, revisits, and call feedback. |
| `seed_doctors.py` | Development seed script | Seeds doctor accounts for the first hospital. |
| `docs/voice_agent_code.py` | Standalone voice-agent reference | LiveKit agent sample / prototype, not wired into Django runtime. |

## Notes

### `manage.py`

Standard Django command entrypoint. Administrative commands route through `main()`, which points Django at `project.settings`.

### `conftest.py`

Pytest bootstrap that initializes Django against `project.settings_test`.

### `run_tests.py`

Convenience runner that defaults to:

- `app`
- `phone_calling`
- `inbound_dashboard`
- `project`

### `seed_data.py`

Development seeding script for dashboard/demo data:

- creates or finds a hospital
- creates a hospital user with broad permissions
- seeds patients
- seeds escalations
- seeds revisit history
- seeds call feedback

This is intended for local/dev setup rather than migrations or fixtures.

### `seed_doctors.py`

Development helper that seeds doctor accounts for the first available hospital.

### `docs/voice_agent_code.py`

Standalone LiveKit voice-agent reference code rather than part of the active Django request path. It defines:

- `Assistant`, a scripted hospital front-desk voice agent prompt
- `prewarm()`, which loads Silero VAD into worker state

It reads like an experimental or reference implementation for a voice agent stack using LiveKit, OpenAI, Cartesia, Soniox, and turn detection.
