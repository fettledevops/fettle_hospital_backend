# Fettle Backend - Project Overview

Fettle Backend is a Django-based system designed for managing and analyzing hospital-to-patient communications. It automates both inbound and outbound calls using AI (Vapi.ai, LiveKit, OpenAI) to generate transcripts, summaries, and structured feedback for hospitals.

## 🚀 Technologies & Architecture

-   **Framework:** Django (Python) with Django Rest Framework (DRF).
-   **Authentication:** JWT (SimpleJWT).
-   **Database:** PostgreSQL (AWS RDS).
-   **Async Tasks:** Celery with Redis as the message broker.
-   **AI & Communication:** 
    -   **OpenAI:** For call analysis, summarization, and sentiment extraction.
    -   **Vapi.ai:** For automated outbound calling.
    -   **LiveKit:** For real-time voice agents (`agent_dispatch`).
    -   **Twilio:** For WhatsApp messaging and telephony integration.
-   **Storage:** AWS S3 for audio files and transcripts.
-   **Data Processing:** `pandas` (reporting), `python-docx` (document generation), `docx2pdf`.

## 📁 Directory Structure

-   `project/`: Core Django configuration (`settings.py`, `urls.py`, `celery.py`).
-   `app/`: Core domain models (Hospital, Patient, Admin) and general dashboard APIs.
-   `phone_calling/`: Management of call tasks (inbound/outbound), LiveKit integration, and Vapi.ai hooks.
-   `inbound_dashboard/`: Specialized views and analytics for inbound call performance.
-   `env/`: Python virtual environment (standard location).

## 🛠️ Commands

### Development
-   **Run Server (HTTP):** `python manage.py runserver`
-   **Run Server (HTTPS):** `python manage.py runsslserver` (required for some webhooks)
-   **Migrations:** `python manage.py migrate`
-   **Create Superuser:** `python manage.py createsuperuser`

### Background Tasks (Celery)
-   **Run Worker:** `celery -A project worker -l info -P gevent`
-   **Run Beat (Scheduler):** `celery -A project beat -l info`

### Testing
-   **Run Tests:** `python manage.py test`

## 📝 Development Conventions

-   **API First:** All new functionality should be exposed via DRF views in the `api/` namespace.
-   **Task Offloading:** Any operation involving external AI APIs (Vapi, OpenAI, LiveKit) or document generation must be handled asynchronously via Celery.
-   **Environment Variables:** Sensitive keys (AWS, OpenAI, Twilio, LiveKit) are managed via `.env`. Do not hardcode secrets.
-   **Timezone:** The project uses `Asia/Kolkata` as the primary timezone, though Celery is configured for `Australia/Tasmania` (verify if this discrepancy is intentional).
-   **SSL:** Use `sslserver` for local development to ensure compatibility with real-time communication protocols.
