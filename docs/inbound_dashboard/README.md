# Inbound Dashboard Package Docs

## Modules

| Module | Role | Notes |
| --- | --- | --- |
| `inbound_dashboard/__init__.py` | Package marker | Empty. |
| `inbound_dashboard/admin.py` | Admin placeholder | No model registrations. |
| `inbound_dashboard/apps.py` | Django app config | Declares the inbound dashboard app. |
| `inbound_dashboard/models.py` | Model placeholder | No local models; uses `app.models`. |
| `inbound_dashboard/tests.py` | Utility tests | Covers timezone normalization helper. |
| `inbound_dashboard/views.py` | Inbound analytics API | KPI, feedback, community, escalation, revisit analytics for inbound calls. |
| `inbound_dashboard/migrations/__init__.py` | Migration package marker | Empty. |

## Notes

### `inbound_dashboard/__init__.py`

Empty package marker.

### `inbound_dashboard/admin.py`

Placeholder only. No admin customizations yet.

### `inbound_dashboard/apps.py`

Minimal app configuration for inbound analytics.

### `inbound_dashboard/models.py`

Empty by design right now. The package is shaped like a Django app, but inbound data models live in `app.models`.

### `inbound_dashboard/tests.py`

Tests `make_naive()`, the helper that normalizes datetimes into naive Asia/Kolkata values for reporting output.

### `inbound_dashboard/views.py`

Read/write API layer for inbound-specific reporting.

Analytics endpoints:

- `Patientengagement_inbound`
- `CommunityEngagement_inbound`
- `EscalationEngagement_inbound`
- `RevisitAnalyticsAPIView_inbound`
- `KPISummary_inbound`

Write endpoints:

- `CallFeedbackView_inbound`
- `CommunityfeedbackView_inbound`
- `EscalationfeedbackView_inbound`
- `UpdateEscalation_inbound`

Implementation notes:

- this package depends on inbound-related models stored in `app.models`
- the file mixes transactional writes and dashboard-style aggregations
- datetime normalization is handled explicitly for frontend-friendly output

### `inbound_dashboard/migrations/__init__.py`

Empty migration package marker.
