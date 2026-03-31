# Fettle Hospital Platform Enhancements - Design Document

**Date:** 2026-03-27
**Topic:** Frontend and Backend Improvements for Hospital Engagement and ROI
**Design Depth:** Standard
**Task Complexity:** Complex

## 1. Problem Statement
The current Fettle Hospital platform has several UI/UX gaps, empty data sections (Engagement feedback distribution, Patient Intents), and missing core functionalities in the Agent Command Center and Staff management. Additionally, the MediVoice transcription app needs to capture and sync more clinical data (diagnosis, medicines, revisit info) to trigger automated patient follow-ups and staff notifications.

## 2. Requirements

### Functional Requirements
- **Engagement Analytics**: Fix feedback distribution graph visibility and make it interactive. Show patient name, date, and number on click.
- **Dashboard UI**: Redesign top 4 KPI cards to occupy full viewport width and improve clarity.
- **ROI Metrics**: Document and potentially configure the formulae for Revenue, Leakage, and FTE savings.
- **Patient Intents**: Fix the empty distribution section by ensuring correct data flow from backend.
- **Agent Command Center**: Enhance campaign creation with audience selection (upload Excel, historical data, date range). Rename "Launch Robot" to hospital-centric terminology.
- **Staff Management**: Replace email with mobile number, add dynamic availability scheduling, and feed this to the Voice Agent.
- **Transcripts & MediVoice**: Add diagnosis, medicines, and revisit date/time to MediVoice extraction and sync. Show digital prescriptions in the Fettle dashboard.
- **Automated Workflows**: Trigger 24h and 1h appointment reminders based on revisit dates. Auto-send prescriptions to pharmacy/reception/patient via email/WhatsApp.
- **Reporting**: Fix "Metrics Only" report logic and migrate all reports to PDF format.
- **Data Portal**: Add media upload (images/videos) and targeted number list upload for WhatsApp campaigns.
- **Inbound Analytics**: Add a header toggle to switch between inbound and outbound dashboard modes.

### Non-Functional Requirements
- **Performance**: Ensure PDF generation and bulk WhatsApp/Email triggers are handled asynchronously via Celery.
- **Security**: Maintain JWT-based authentication across all new endpoints and repository boundaries.
- **Consistency**: Adhere to existing Tailwind CSS and Shadcn UI patterns in the frontend.

## 3. Approach

### Backend Architecture
- **Models**: 
  - Add `reception_email`, `pharmacy_email` to `Hospital_model`.
  - Add `diagnosis`, `medicines` (JSON), `revisit_date`, `revisit_time` to `MediVoiceSession`.
  - Add `mobile_no` and update `availability` handling in `Doctor_model`.
- **Views**: 
  - Update `ROIMetrics` to include detailed formula explanations in the response metadata.
  - Fix `CommunityEngagement` to return `name` and `value` for Pie charts.
  - Update `PdfView` to support `report_type` and generate PDF via WeasyPrint.
  - Update `TextView` to handle media uploads and target list Excel parsing.
  - Update `MediVoiceSessionView` to handle new clinical fields.
- **Tasks**: 
  - Update `schedule_reminder_calls` to use `revisit_date`.
  - Implement `send_hospital_notifications` for pharmacy and reception.

### Frontend Architecture
- **Dashboard**: Use a responsive grid for `KPISummary` that expands to full width.
- **Engagement**: Update `CommunityEngagementMetrics.tsx` to handle the new backend response format and add a details modal.
- **Staff**: Add an "Edit Availability" dialog to `StaffManagement.tsx`.
- **Agent**: Integrate file upload and date range picker into the `launchAgent` payload in `AgentControl.tsx`.
- **MediVoice**: Update `Home.jsx` and `PatientForm.jsx` to capture and display the new fields.

### Decision Matrix

| Criterion | Weight | Approach: Unified PDF & Async Tasks |
|-----------|--------|------------------------------------|
| Maintainability | 30% | 5: Consolidating report logic to PDF reduces template fragmentation. |
| User Experience | 40% | 5: Direct interaction with graphs and clearer KPI cards significantly improves UX. |
| Scalability | 30% | 4: Moving triggers to Celery ensures the system scales with hospital load. |
| **Weighted Total** | | **4.7** |

## 4. Risk Assessment
- **PDF Generation**: WeasyPrint can be resource-intensive; must be handled in Celery.
- **WhatsApp API Limits**: Bulk sending via CloudConnect must respect provider rate limits.
- **Merge Conflicts**: The current local state has uncommitted changes and merge conflicts in `requirements.txt` that must be resolved first.

## 5. Success Criteria
- Feedback distribution graph is visible and interactive.
- Top 4 KPI cards look clear and occupy full width.
- Campaigns can be launched with custom Excel lists or date-range targeted history.
- MediVoice successfully extracts and syncs diagnosis/medicines/revisit info.
- Appointment reminders are sent exactly 24h and 1h before the revisit time.
- All reports generate as valid PDFs.
