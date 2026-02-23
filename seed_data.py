import os
import django
import uuid
from datetime import timedelta
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from app.models import Hospital_model, Patient_model, EscalationModel, Patient_date_model, CallFeedbackModel

def seed_data():
    print("Starting data seeding for testing...")
    
    # 1. Get or create a hospital
    hospital, created = Hospital_model.objects.get_or_create(
        name="Amor Hospitals",
        defaults={'id': uuid.uuid4()}
    )
    print(f"Using Hospital: {hospital.name}")

    # Ensure a hospital user exists with all permissions enabled
    hospital_user, user_created = Hospital_user_model.objects.get_or_create(
        name="hospital_user",
        defaults={
            'hospital': hospital,
            'password_hash': 'hospital123',
            'patient_engagement': True,
            'community_egagement': True,
            'revisit_engagement': True,
            'escalation_engagement': True,
            'calllog_engagement': True,
            'upload_engagement': True,
            'pdf_engagement': True
        }
    )
    if not user_created:
        hospital_user.calllog_engagement = True
        hospital_user.revisit_engagement = True
        hospital_user.escalation_engagement = True
        hospital_user.save()
    print(f"Ensured Hospital User 'hospital_user' exists with full tab access.")

    # 2. Create some patients
    patients_data = [
        {"name": "John Doe", "phone": "9876543210", "dept": "Cardiology"},
        {"name": "Jane Smith", "phone": "9876543211", "dept": "Orthopedics"},
        {"name": "Robert Brown", "phone": "9876543212", "dept": "Pediatrics"},
    ]
    
    patients = []
    for p in patients_data:
        patient, created = Patient_model.objects.get_or_create(
            hospital=hospital,
            mobile_no=p["phone"],
            department=p["dept"],
            defaults={"patient_name": p["name"], "age": 45}
        )
        patients.append(patient)
    
    print(f"Ensured {len(patients)} patients exist.")

    # 3. Seed some Escalations (Current month)
    now = timezone.now()
    escalation_count = 0
    for i in range(5):
        EscalationModel.objects.create(
            patient=patients[i % len(patients)],
            issue_description=f"Automated test escalation issue #{i+1}: Delayed report for blood work.",
            status='pending',
            department=patients[i % len(patients)].department,
            escalated_at=now - timedelta(days=i)
        )
        escalation_count += 1
    
    print(f"Seeded {escalation_count} pending escalations.")

    # 4. Seed some Revisits (to test Revisit Metrics)
    revisit_count = 0
    for p in patients:
        # Create 3 visits for each patient
        for i in range(3):
            Patient_date_model.objects.get_or_create(
                hospital=hospital,
                mobile_no=p.mobile_no,
                department=p.department,
                date=now - timedelta(days=i*15), # Visits spaced by 15 days
                defaults={"patient_name": p.patient_name}
            )
            revisit_count += 1
    
    print(f"Seeded {revisit_count} visit entries for revisit analysis.")

    # 5. Seed some Call Feedback
    call_count = 0
    for p in patients:
        CallFeedbackModel.objects.create(
            patient=p,
            call_status='connected',
            call_outcome='positive',
            remarks="Patient satisfied with service.",
            called_by="Vapi Agent",
            called_at=now - timedelta(days=1)
        )
        call_count += 1
    
    print(f"Seeded {call_count} call feedback records.")
    print("Seeding complete! You should now see data in the dashboard.")

if __name__ == "__main__":
    seed_data()
