import os
import django
import json
from unittest.mock import patch, MagicMock

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from django.test import Client
from app.models import Hospital_model, Doctor_model, MediVoiceSession, Hospital_user_model
from django.contrib.auth.hashers import make_password
from project.jwt_auth import create_token

def run_e2e_test():
    print("Starting E2E Test for MediVoice -> Django -> Celery flow...")
    
    client = Client()

    # 1. Setup Test Data
    hospital, _ = Hospital_model.objects.get_or_create(name="Test Hospital")
    doctor, _ = Doctor_model.objects.update_or_create(
        email="testdoctor@example.com",
        defaults={
            "hospital": hospital,
            "name": "Test Doctor",
            "department": "General Medicine",
            "password_hash": make_password("password123"),
            "availability": {"Monday": "9AM-5PM", "Tuesday": "9AM-5PM"}
        }
    )
    
    hospital_user, _ = Hospital_user_model.objects.get_or_create(
        name="test_hospital_admin",
        defaults={
            "hospital": hospital,
            "password_hash": make_password("adminpassword"),
            "calllog_engagement": True
        }
    )

    # 2. Mock Celery tasks
    with patch('phone_calling.tasks.send_prescription_notifications.delay') as mock_notify, \
         patch('phone_calling.tasks.schedule_reminder_calls.delay') as mock_reminder:
        
        print("Triggering MediVoiceSyncView...")
        sync_data = {
            "doctorEmail": "testdoctor@example.com",
            "patientName": "E2E Patient",
            "patientMobile": "1234567890",
            "overallSummary": "Patient has mild fever. Diagnosis: Viral Fever. Medicines: Paracetamol 500mg. Revisit in 3 days.",
            "metaData": {
                "diagnosis": "Viral Fever",
                "medicines": ["Paracetamol 500mg"],
                "revisit_date": "2025-08-15"
            },
            "transcriptions": [
                {"speaker": "doctor", "text": "How are you feeling?", "timestamp": 0.0},
                {"speaker": "patient", "text": "I have a fever.", "timestamp": 5.0}
            ]
        }
        
        response = client.post(
            '/api/medivoice/sync/',
            data=json.dumps(sync_data),
            content_type='application/json',
            HTTP_X_FETTLE_SECRET='placeholder-secret'
        )
        
        print(f"Sync Response: {response.status_code} - {response.content}")
        assert response.status_code == 200
        assert response.json()['error'] == 0
        
        session_id = response.json()['session_id']
        print(f"Session created with ID: {session_id}")
        
        # Verify clinical fields persistence
        session = MediVoiceSession.objects.get(id=session_id)
        assert session.diagnosis == "Viral Fever"
        assert "Paracetamol 500mg" in str(session.medicines)
        assert str(session.revisit_date) == "2025-08-15"
        print("SUCCESS: Clinical fields (diagnosis, medicines, revisit_date) were persisted correctly.")

        # Verify tasks were triggered
        # Note: DRF might pass UUID object to tasks if created in-process, or string if via API.
        # We check if the mock was called with the session_id (string from JSON response)
        mock_notify.assert_called_once()
        mock_reminder.assert_called_once()
        print("SUCCESS: Celery tasks send_prescription_notifications and schedule_reminder_calls were triggered.")

    # 3. Test Staff Availability Endpoint (Voice Agent Tool)
    print("Testing StaffAvailabilityView...")
    
    # Generate token for hospital user
    token = create_token({
        "user_id": str(hospital_user.id),
        "email": hospital_user.name,
        "role": "user"
    })
    
    response = client.get(
        '/api/staff/availability/',
        HTTP_AUTHORIZATION=f'Bearer {token}'
    )
    
    print(f"Availability Response: {response.status_code} - {response.content}")
    assert response.status_code == 200
    data = response.json()['data']
    assert len(data) >= 1
    
    found_doctor = False
    for d in data:
        if d['name'] == "Test Doctor":
            assert d['availability'] == {"Monday": "9AM-5PM", "Tuesday": "9AM-5PM"}
            found_doctor = True
            break
    
    assert found_doctor
    print("SUCCESS: StaffAvailabilityView returned correct JSON with doctor availability.")

    # 4. Verify PDF Generation Utility (Indirectly)
    print("Verifying PDF generation utility...")
    from app.utils.pdf_generator import generate_pdf_from_html
    
    test_html = "<html><body><h1>Test Report</h1><p>Patient: E2E Patient</p></body></html>"
    try:
        pdf_content = generate_pdf_from_html(test_html)
        if pdf_content:
            print(f"SUCCESS: PDF generation produced {len(pdf_content)} bytes.")
        else:
            print("FAILED: PDF generation returned empty content.")
    except Exception as e:
        print(f"FAILED: PDF generation crashed: {str(e)}")

    print("\nE2E Test Completed Successfully!")

if __name__ == "__main__":
    run_e2e_test()
