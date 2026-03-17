import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Admin_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=255, unique=True)),
                ("password_hash", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Hospital_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Hospital_user_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("password_hash", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("patient_engagement", models.BooleanField(default=False)),
                ("community_egagement", models.BooleanField(default=False)),
                ("revisit_engagement", models.BooleanField(default=False)),
                ("escalation_engagement", models.BooleanField(default=False)),
                ("calllog_engagement", models.BooleanField(default=False)),
                ("upload_engagement", models.BooleanField(default=False)),
                ("pdf_engagement", models.BooleanField(default=False)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hostpitals", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="HospitalUploadLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("file_names", models.JSONField()),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed")], default="PENDING", max_length=20)),
                ("uploaded_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("message", models.TextField(blank=True, null=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="upload_logs", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="Patient_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("serial_no", models.CharField(blank=True, max_length=255, null=True)),
                ("patient_name", models.CharField(max_length=255)),
                ("age", models.IntegerField(blank=True, null=True)),
                ("mobile_no", models.CharField(max_length=20)),
                ("department", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="patients", to="app.hospital_model")),
            ],
            options={
                "unique_together": {("hospital", "mobile_no", "department")},
            },
        ),
        migrations.CreateModel(
            name="Patient_date_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("serial_no", models.CharField(blank=True, max_length=255, null=True)),
                ("date", models.DateTimeField()),
                ("patient_name", models.CharField(max_length=255)),
                ("age", models.IntegerField(blank=True, null=True)),
                ("mobile_no", models.CharField(max_length=20)),
                ("department", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="date_patients", to="app.hospital_model")),
            ],
            options={
                "unique_together": {("hospital", "mobile_no", "department", "date")},
            },
        ),
        migrations.CreateModel(
            name="TextModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("text", models.TextField(blank=True, null=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="text_hospital", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="CallFeedbackModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("call_status", models.CharField(choices=[("connected", "Connected"), ("not_connected", "Not Connected")], max_length=20)),
                ("call_outcome", models.CharField(choices=[("positive", "Positive"), ("negative", "Negative"), ("escalated", "Escalated"), ("no_feedback", "No Feedback")], max_length=20)),
                ("remarks", models.TextField(blank=True, null=True)),
                ("community_added", models.BooleanField(default=False)),
                ("revisit_encouraged", models.BooleanField(default=False)),
                ("escalation_required", models.BooleanField(default=False)),
                ("call_duration", models.CharField(blank=True, null=True)),
                ("called_by", models.CharField(blank=True, max_length=255, null=True)),
                ("called_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.patient_model")),
            ],
            options={
                "db_table": "call_feedback",
            },
        ),
        migrations.CreateModel(
            name="EscalationModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("issue_description", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("in-progress", "In Progress"), ("resolved", "Resolved")], default="pending", max_length=20)),
                ("department", models.TextField(blank=True, null=True)),
                ("escalated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_notes", models.TextField(blank=True, null=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.patient_model")),
            ],
        ),
        migrations.CreateModel(
            name="CommunityEngagementModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("engagement_type", models.CharField(choices=[("post", "Post"), ("comment", "Comment"), ("poll_participation", "Poll Participation"), ("like", "Like"), ("share", "Share")], max_length=20)),
                ("engagement_date", models.DateField(default=django.utils.timezone.localdate)),
                ("department", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.patient_model")),
            ],
        ),
        migrations.CreateModel(
            name="Outbound_assistant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("assistant_id", models.CharField(blank=True, max_length=10000, null=True)),
                ("call_id", models.CharField(blank=True, max_length=10000, null=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="hospital_patients", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("template_type", models.CharField(choices=[("health_package", "New Health Package"), ("new_facility", "New Facility"), ("discounted_product", "Discounted Product"), ("custom", "Custom AI Draft")], default="custom", max_length=50)),
                ("package_name", models.CharField(blank=True, max_length=255, null=True)),
                ("facility_name", models.CharField(blank=True, max_length=255, null=True)),
                ("discount_details", models.CharField(blank=True, max_length=255, null=True)),
                ("purpose", models.TextField(blank=True, null=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("unconnected_only", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(default="active", max_length=20)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campaigns", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="Doctor_model",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(unique=True)),
                ("password_hash", models.TextField()),
                ("department", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="doctors", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="Outbound_Hospital",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("vapi_id", models.CharField(blank=True, max_length=1000, null=True)),
                ("status", models.CharField(blank=True, max_length=1000, null=True)),
                ("endedReason", models.CharField(blank=True, max_length=1000, null=True)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("message_s3_link", models.CharField(blank=True, max_length=10000, null=True)),
                ("audio_link", models.CharField(blank=True, max_length=10000, null=True)),
                ("task_id", models.CharField(blank=True, max_length=10000, null=True)),
                ("task_id_process", models.CharField(blank=True, max_length=10000, null=True)),
                ("calling_process", models.CharField(blank=True, choices=[("not_happened", "NOT HAPPENED"), ("connected", "CONNECTED"), ("not_connected", "NOT CONNECTED"), ("in_progress", "IN PROGRESS")], default="not_happened", max_length=30, null=True)),
                ("assistant_id", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="app.outbound_assistant")),
                ("patient_id", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="patients_outbound", to="app.patient_model")),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="calls", to="app.campaign")),
            ],
        ),
        migrations.CreateModel(
            name="Inbound_Hospital",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("vapi_id", models.CharField(blank=True, max_length=1000, null=True)),
                ("status", models.CharField(blank=True, max_length=1000, null=True)),
                ("endedReason", models.CharField(blank=True, max_length=1000, null=True)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("message_s3_link", models.CharField(blank=True, max_length=10000, null=True)),
                ("audio_link", models.CharField(blank=True, max_length=10000, null=True)),
                ("task_id", models.CharField(blank=True, max_length=10000, null=True)),
                ("task_id_process", models.CharField(blank=True, max_length=10000, null=True)),
                ("calling_process", models.CharField(blank=True, choices=[("not_happened", "NOT HAPPENED"), ("connected", "CONNECTED"), ("not_connected", "NOT CONNECTED"), ("in_progress", "IN PROGRESS")], default="not_happened", max_length=30, null=True)),
                ("from_phone_number", models.CharField(blank=True, max_length=30, null=True)),
                ("to_phone_numnber", models.CharField(blank=True, max_length=30, null=True)),
                ("department", models.CharField(blank=True, default="N/A", max_length=255, null=True)),
                ("hospital", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="inbound_calls", to="app.hospital_model")),
            ],
        ),
        migrations.CreateModel(
            name="CallFeedbackModel_inbound",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("call_status", models.CharField(choices=[("connected", "Connected"), ("not_connected", "Not Connected")], max_length=20)),
                ("call_outcome", models.CharField(choices=[("positive", "Positive"), ("negative", "Negative"), ("escalated", "Escalated"), ("no_feedback", "No Feedback")], max_length=20)),
                ("remarks", models.TextField(blank=True, null=True)),
                ("community_added", models.BooleanField(default=False)),
                ("revisit_encouraged", models.BooleanField(default=False)),
                ("escalation_required", models.BooleanField(default=False)),
                ("call_duration", models.CharField(blank=True, null=True)),
                ("called_by", models.CharField(blank=True, max_length=255, null=True)),
                ("called_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.inbound_hospital")),
            ],
        ),
        migrations.CreateModel(
            name="CommunityEngagementModel_inbound",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("engagement_type", models.CharField(choices=[("post", "Post"), ("comment", "Comment"), ("poll_participation", "Poll Participation"), ("like", "Like"), ("share", "Share")], max_length=20)),
                ("engagement_date", models.DateField(default=django.utils.timezone.localdate)),
                ("department", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.inbound_hospital")),
            ],
        ),
        migrations.CreateModel(
            name="EscalationModel_inbound",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("issue_description", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("in-progress", "In Progress"), ("resolved", "Resolved")], default="pending", max_length=20)),
                ("department", models.TextField(blank=True, null=True)),
                ("escalated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_notes", models.TextField(blank=True, null=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="app.inbound_hospital")),
            ],
        ),
        migrations.CreateModel(
            name="MediVoiceSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("patient_name", models.CharField(max_length=255)),
                ("patient_mobile", models.CharField(max_length=20)),
                ("patient_email", models.EmailField(blank=True, null=True)),
                ("overall_summary", models.TextField(blank=True, null=True)),
                ("meta_data", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("doctor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="app.doctor_model")),
            ],
        ),
        migrations.CreateModel(
            name="MediVoiceTranscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("speaker", models.CharField(max_length=20)),
                ("text", models.TextField()),
                ("timestamp", models.FloatField(default=0.0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transcriptions", to="app.medivoicesession")),
            ],
        ),
    ]
