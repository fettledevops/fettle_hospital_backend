# App Package Docs

## Modules

| Module | Role | Notes |
| --- | --- | --- |
| `app/__init__.py` | Package marker | Empty. |
| `app/admin.py` | Django admin registrations | Registers most main-domain models. |
| `app/apps.py` | Django app config | Declares the core app. |
| `app/models.py` | Main persistence layer | Hospitals, users, patients, engagements, campaigns, doctors, call records. |
| `app/tests.py` | Utility tests | Verifies `get_ordinal()`. |
| `app/views.py` | Main business API | Auth, uploads, analytics, PDFs, campaigns, doctor workflows. |
| `app/migrations/__init__.py` | Migration package marker | Empty. |
| `app/migrations/0001_initial.py` | Initial schema | Creates the base domain model set. |
| `app/migrations/0002_outbound_hospital_calling_process.py` | Schema change | Adds outbound call processing state. |
| `app/migrations/0003_inbound_hospital.py` | Schema change | Introduces inbound call records. |
| `app/migrations/0004_callfeedbackmodel_inbound_and_more.py` | Schema change | Adds inbound feedback, community, escalation models. |
| `app/migrations/0005_inbound_hospital_department.py` | Schema change | Adds inbound department tracking. |
| `app/migrations/0006_alter_inbound_hospital_calling_process_and_more.py` | Schema change | Adds `in_progress` calling status. |
| `app/migrations/0007_campaign_outbound_hospital_campaign.py` | Schema change | Adds campaigns and links outbound calls to campaigns. |

## Notes

### `app/__init__.py`

Empty package marker.

### `app/admin.py`

Registers the operational models used in Django admin:

- admins and hospitals
- hospital users and patients
- upload logs
- call feedback, escalation, and community engagement
- text templates and outbound call entities

Campaign and doctor/MediVoice models are not registered here yet.

### `app/apps.py`

Minimal Django app configuration for the core business app.

### `app/models.py`

This is the central data model for the whole system.

Core organization and access:

- `Hospital_model`
- `Hospital_user_model`
- `Admin_model`

Patient and engagement tracking:

- `Patient_model`
- `Patient_date_model`
- `HospitalUploadLog`
- `CallFeedbackModel`
- `EscalationModel`
- `CommunityEngagementModel`
- `TextModel`

Outbound and campaign tracking:

- `Outbound_assistant`
- `Campaign`
- `Outbound_Hospital`

Doctor and voice workflow:

- `Doctor_model`
- `MediVoiceSession`
- `MediVoiceTranscription`

Inbound call tracking:

- `Inbound_Hospital`
- `CallFeedbackModel_inbound`
- `CommunityEngagementModel_inbound`
- `EscalationModel_inbound`

Design notes:

- password hashes are stored on custom models instead of Django's auth user table
- patient state is split between current patient rows and dated visit history
- inbound and outbound call records live here even though telephony orchestration is elsewhere

### `app/tests.py`

Small regression coverage for the ordinal-formatting helper used in reporting.

### `app/views.py`

This is the largest module in the repository and acts as the main business API.

Authentication and access:

- `login_view`
- `doctor_login_view`
- `validateToken`
- `tab_access`

File and content flows:

- `patient_insert_view`
- `upload_files_log`
- `TextView`
- `PdfView`
- `replace_placeholders_in_docx_preserving_styles()`

Feedback and engagement writes:

- `CallFeedbackView`
- `EscalationfeedbackView`
- `UpdateEscalation`
- `CommunityfeedbackView`
- `UpdateCommunity`

Dashboard and analytics reads:

- `fetchpatients`
- `fetchrecentactivity`
- `AdminDashboardView`
- `KPISummary`
- `Patientengagement`
- `CommunityEngagement`
- `RevisitAnalyticsAPIView`
- `EscalationEngagement`
- `ROIMetrics`
- `DepartmentAnalytics`
- `Allhospitals`
- `EscalationManagementView`

Campaign and doctor workflows:

- `CampaignView`
- `MediVoiceSessionView`
- `DoctorManagementView`
- `DoctorTranscriptionView`

Implementation notes:

- the file mixes CRUD, analytics, uploads, and document generation in one module
- nearly every endpoint is JWT-protected except the login endpoints
- `patient_insert_view` parses CSV/XLSX uploads and writes both current patient rows and dated visit history
- there are two top-level `fetchpatients` class definitions; the later one overrides the earlier one in module scope

### Migrations

`0001_initial.py` creates the base schema.

`0002_outbound_hospital_calling_process.py` adds `calling_process` to outbound calls.

`0003_inbound_hospital.py` introduces inbound call records.

`0004_callfeedbackmodel_inbound_and_more.py` adds inbound feedback, community, and escalation tables.

`0005_inbound_hospital_department.py` adds department metadata to inbound calls.

`0006_alter_inbound_hospital_calling_process_and_more.py` expands inbound and outbound status choices with `in_progress`.

`0007_campaign_outbound_hospital_campaign.py` adds campaigns and links outbound calls to them.
