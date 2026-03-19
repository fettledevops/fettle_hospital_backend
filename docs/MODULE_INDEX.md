# Codebase Module Index

Generated from the repository state on 2026-03-19.

## Layout

The module docs are now split to mirror the codebase:

- [project docs](/workspaces/fettle_hospital_backend/docs/project/README.md)
- [app docs](/workspaces/fettle_hospital_backend/docs/app/README.md)
- [inbound_dashboard docs](/workspaces/fettle_hospital_backend/docs/inbound_dashboard/README.md)
- [phone_calling docs](/workspaces/fettle_hospital_backend/docs/phone_calling/README.md)
- [support docs](/workspaces/fettle_hospital_backend/docs/support/README.md)

## Architecture Snapshot

- `project/` contains Django bootstrap, configuration, routing, and JWT auth.
- `app/` contains the main data model and most of the business API.
- `inbound_dashboard/` contains inbound-call-specific analytics and write endpoints.
- `phone_calling/` contains telephony orchestration, Celery task processing, and LiveKit integration.
- Root-level scripts and `docs/voice_agent_code.py` are documented under `docs/support`.

## API Surface Summary

### `app.views`

- Auth and access: login, doctor login, token validation, tab access
- File/content flows: patient uploads, upload logs, text templates, PDF generation
- Feedback flows: call feedback, community feedback, escalation feedback, update endpoints
- Analytics: patient, community, revisit, escalation, KPI, ROI, department, and dashboard endpoints
- Doctor flows: doctor management, MediVoice sessions, doctor transcript retrieval

### `inbound_dashboard.views`

- Inbound patient engagement analytics
- Inbound call feedback and community feedback writes
- Inbound escalation writes and analytics
- Inbound revisit and KPI reporting

### `phone_calling.views`

- Outbound campaign dispatch
- Outbound call processing and export
- Inbound call acknowledgement and reprocessing
- LiveKit webhook handler defined in code but not currently routed

## Suggested Next Splits

If you want the docs to go one level deeper, the next clean split would be:

1. API request/response reference
2. Data model reference
3. Call-flow and integration reference
