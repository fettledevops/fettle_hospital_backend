# Fettle Hospital Platform Enhancements - Implementation Plan

**Goal:** Implement UI/UX fixes and core functionality enhancements across Fettle Hospital Backend and Frontend repositories.

**Architecture:** Hybrid Django (Backend) + React (Frontend) with Celery-based async tasks for PDF generation and notifications.

**Tech Stack:** Python/Django, DRF, React, Tailwind CSS, Shadcn UI, WeasyPrint, Celery, Redis.

---

## Phase 1: Core Backend Enhancements (Models & Tasks)
**Objective:** Update data models and background tasks to support new features.

- [ ] **Step 1: Update Models**
  - Modify `Hospital_model` to add `reception_email` and `pharmacy_email`.
  - Modify `MediVoiceSession` to add `diagnosis`, `medicines`, `revisit_date`, `revisit_time`.
  - Modify `Doctor_model` to ensure `mobile_no` is primary and update `availability` structure.
- [ ] **Step 2: Run Migrations**
  - `python manage.py makemigrations && python manage.py migrate`
- [ ] **Step 3: Update Celery Tasks**
  - Refactor `schedule_reminder_calls` in `phone_calling/tasks.py` to trigger relative to `revisit_date`.
  - Update `send_prescription_notifications` to include new fields and notify reception/pharmacy.

## Phase 2: Backend API Updates
**Objective:** Update views to return correct data formats and handle new logic.

- [ ] **Step 1: ROI & Analytics**
  - Update `ROIMetrics` in `app/views.py` with formula metadata.
  - Fix `CommunityEngagement` logic to return `name/value` for Pie charts and ensure `Patient Intents` is populated.
- [ ] **Step 2: MediVoice Sync**
  - Update `MediVoiceSessionView` to save new clinical fields.
- [ ] **Step 3: Reporting & Data Portal**
  - Migrate `PdfView` to WeasyPrint-based PDF generation for both report types.
  - Complete `TextView` logic for media upload and targeted list parsing.

## Phase 3: Frontend - MediVoice PWA Enhancements
**Objective:** Enhance the MediVoice PWA to capture and display clinical data.

- [ ] **Step 1: MediVoice Server**
  - Update `gemini.js` schema and prompt to extract diagnosis, medicines, and revisit info.
  - Update `routes.js` to sync new fields to Django.
- [ ] **Step 2: MediVoice Client**
  - Update `PatientForm.jsx` and `Home.jsx` to show/edit the new fields after transcription.

## Phase 4: Frontend - Main Dashboard UI/UX
**Objective:** Fix UI gaps and add new interactive elements.

- [ ] **Step 1: KPI Redesign**
  - Update `KPISummary.tsx` to use full width and clearer layout.
- [ ] **Step 2: Interactive Analytics**
  - Update `CommunityEngagementMetrics.tsx` with details modal and fixed Pie chart data binding.
  - Add Inbound/Outbound toggle to `HospitalDashboard.tsx`.
- [ ] **Step 3: Agent & Staff Management**
  - Update `AgentControl.tsx` with audience selection logic and renaming.
  - Update `StaffManagement.tsx` with mobile-first inputs and dynamic availability editing.

---

## Phase 5: Validation & Deployment
**Objective:** Verify all changes and prepare for PR.

- [ ] **Step 1: Local Verification**
  - Run `npm run build` in frontend.
  - Run `python manage.py test` in backend.
- [ ] **Step 2: Git Cleanup**
  - Resolve any remaining merge conflicts.
  - Create new branches and push to remotes.
