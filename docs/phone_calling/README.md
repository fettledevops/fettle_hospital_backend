# Phone Calling Package Docs

## Modules

| Module | Role | Notes |
| --- | --- | --- |
| `phone_calling/__init__.py` | Package marker | Empty. |
| `phone_calling/admin.py` | Admin placeholder | No model registrations. |
| `phone_calling/apps.py` | Django app config | Declares the telephony app. |
| `phone_calling/livekit_calling.py` | LiveKit SIP dispatch | Creates agent dispatches and SIP participants. |
| `phone_calling/models.py` | Model placeholder | No local models; uses `app.models`. |
| `phone_calling/tasks.py` | Celery task layer | Outbound dispatch, transcript analysis, S3 reads, inbound stubs. |
| `phone_calling/tests.py` | Task-level tests | Mocks LiveKit and S3-facing helpers. |
| `phone_calling/views.py` | Telephony API endpoints | Starts campaigns, triggers processing, inbound reporting, exports. |
| `phone_calling/migrations/__init__.py` | Migration package marker | Empty. |

## Notes

### `phone_calling/__init__.py`

Empty package marker.

### `phone_calling/admin.py`

Placeholder only. No admin registrations.

### `phone_calling/apps.py`

Minimal app configuration for the telephony app.

### `phone_calling/livekit_calling.py`

Bridge module to LiveKit SIP:

- `_dispatch_call()` creates an agent dispatch and SIP participant for a room
- `dispatch_call()` wraps the async workflow in its own event loop for sync callers

This is the boundary between Django/Celery orchestration and LiveKit call placement.

### `phone_calling/models.py`

Empty by design. Call-related persistence lives in `app.models`.

### `phone_calling/tasks.py`

Celery task layer for asynchronous call handling:

- `cloudconnect_whatsapp_msg()` is a stubbed notifier
- `call_outbound_task()` dispatches LiveKit calls and creates `Outbound_Hospital` rows
- `json_audio()` sends transcript text to OpenAI for structured call analysis
- `read_from_s3_bucket()` reads transcript and metadata artifacts from S3
- `process_outbound_calls()` reads artifacts, analyzes transcripts, loops results back through internal API endpoints, and updates DB state
- `inbound_call_task()` and `process_inbound_calls()` are currently placeholder implementations

External integrations used here:

- LiveKit
- AWS S3
- OpenAI
- an internal authenticated loopback to the same backend API

### `phone_calling/tests.py`

Focused unit tests around task helpers, with mocked LiveKit dispatch and S3 access.

### `phone_calling/views.py`

Operational telephony API:

- `Outbound_call` resolves hospital context, selects patients, builds campaign metadata, and queues outbound call tasks
- `Process_Outbound_call` reprocesses queued outbound records
- `Inboundcall` acknowledges inbound call notifications
- `showInboundcall` returns normalized inbound call history
- `processinboundcall_view` retries inbound calls still marked `not_happened`
- `LiveKitWebhook` is designed for automatic processing after room completion, but is not currently routed
- `download_excel_outbound` exports outbound call history to Excel

Implementation notes:

- this module depends on `app.models` for persistence and `phone_calling.tasks` for async execution
- the routed endpoints focus on operational triggering and export rather than analytics

### `phone_calling/migrations/__init__.py`

Empty migration package marker.
