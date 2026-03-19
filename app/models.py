from django.db import models
import uuid
from django.contrib.auth.hashers import make_password
from django.utils import timezone

# Create your models here.


class Hospital_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Hospital_user_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="hostpitals"
    )
    name = models.CharField(max_length=255, unique=True)
    password_hash = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    patient_engagement = models.BooleanField(default=False)
    community_egagement = models.BooleanField(default=False)
    revisit_engagement = models.BooleanField(default=False)
    escalation_engagement = models.BooleanField(default=False)
    calllog_engagement = models.BooleanField(default=False)
    upload_engagement = models.BooleanField(default=False)
    pdf_engagement = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Hash only if it's not already hashed
        if not self.password_hash.startswith("pbkdf2_"):
            self.password_hash = make_password(self.password_hash)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Admin_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Hash only if it's not already hashed
        if not self.password_hash.startswith("pbkdf2_"):
            self.password_hash = make_password(self.password_hash)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Patient_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="patients"
    )
    serial_no = models.CharField(max_length=255, blank=True, null=True)
    # date = models.DateField()
    patient_name = models.CharField(max_length=255)
    age = models.IntegerField(blank=True, null=True)
    mobile_no = models.CharField(max_length=20)
    department = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("hospital", "mobile_no", "department")

    def __str__(self):
        return f"{self.patient_name} ({self.mobile_no}) ({self.department})"


class HospitalUploadLog(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        "Hospital_model", on_delete=models.CASCADE, related_name="upload_logs"
    )
    file_names = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    uploaded_at = models.DateTimeField(default=timezone.now)
    message = models.TextField(blank=True, null=True)

    def __str__(self):
        return " {self.status} - {self.uploaded_at.date()}"


class CallFeedbackModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Patient_model",  # Update this to match your actual app/model name
        on_delete=models.CASCADE,
    )

    CALL_STATUS_CHOICES = [
        ("connected", "Connected"),
        ("not_connected", "Not Connected"),
    ]
    call_status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES)

    CALL_OUTCOME_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
        ("escalated", "Escalated"),
        ("no_feedback", "No Feedback"),
    ]
    call_outcome = models.CharField(max_length=20, choices=CALL_OUTCOME_CHOICES)

    remarks = models.TextField(blank=True, null=True)
    community_added = models.BooleanField(default=False)
    revisit_encouraged = models.BooleanField(default=False)
    escalation_required = models.BooleanField(default=False)
    call_duration = models.CharField(blank=True, null=True)  # in minutes
    called_by = models.CharField(max_length=255, blank=True, null=True)
    called_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "call_feedback"


class EscalationModel(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in-progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Patient_model", on_delete=models.CASCADE  # Adjust app/model name as needed
    )
    issue_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    department = models.TextField(null=True, blank=True)
    escalated_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Escalation {self.id} - {self.status}"


class CommunityEngagementModel(models.Model):
    ENGAGEMENT_TYPE_CHOICES = [
        ("post", "Post"),
        ("comment", "Comment"),
        ("poll_participation", "Poll Participation"),
        ("like", "Like"),
        ("share", "Share"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Patient_model",  # Update 'patients' if the app label is different
        on_delete=models.CASCADE,
    )
    engagement_type = models.CharField(max_length=20, choices=ENGAGEMENT_TYPE_CHOICES)
    engagement_date = models.DateField(
        default=timezone.localdate  # This returns the current date in IST if TIME_ZONE is set
    )
    department = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.engagement_type} by {self.patient_id} on {self.engagement_date}"


class Patient_date_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="date_patients"
    )
    serial_no = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateTimeField()
    patient_name = models.CharField(max_length=255)
    age = models.IntegerField(blank=True, null=True)
    mobile_no = models.CharField(max_length=20)
    department = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("hospital", "mobile_no", "department", "date")

    def __str__(self):
        return f"{self.patient_name} ({self.mobile_no}) ({self.department})"


class TextModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="text_hospital"
    )
    text = models.TextField(null=True, blank=True)


class Outbound_assistant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="hospital_patients"
    )
    assistant_id = models.CharField(max_length=10000, null=True, blank=True)
    call_id = models.CharField(max_length=10000, null=True, blank=True)

    def __str__(self):
        return f"{self.hospital} {self.assistant_id}"


class Campaign(models.Model):
    TEMPLATE_CHOICES = [
        ("health_package", "New Health Package"),
        ("new_facility", "New Facility"),
        ("discounted_product", "Discounted Product"),
        ("custom", "Custom AI Draft"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="campaigns"
    )
    name = models.CharField(max_length=255)
    template_type = models.CharField(
        max_length=50, choices=TEMPLATE_CHOICES, default="custom"
    )
    package_name = models.CharField(max_length=255, blank=True, null=True)
    facility_name = models.CharField(max_length=255, blank=True, null=True)
    discount_details = models.CharField(max_length=255, blank=True, null=True)
    purpose = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    unconnected_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="active")

    def __str__(self):
        return self.name


class Doctor_model(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital_model, on_delete=models.CASCADE, related_name="doctors"
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password_hash = models.TextField()
    department = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.password_hash.startswith("pbkdf2_"):
            self.password_hash = make_password(self.password_hash)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.department})"


class MediVoiceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        Doctor_model, on_delete=models.CASCADE, related_name="sessions"
    )
    patient_name = models.CharField(max_length=255)
    patient_mobile = models.CharField(max_length=20)
    patient_email = models.EmailField(null=True, blank=True)
    overall_summary = models.TextField(null=True, blank=True)
    meta_data = models.JSONField(
        null=True, blank=True
    )  # For Gemini metadata (BP, findings, etc)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session: {self.patient_name} - {self.created_at.date()}"


class MediVoiceTranscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        MediVoiceSession, on_delete=models.CASCADE, related_name="transcriptions"
    )
    speaker = models.CharField(max_length=20)  # 'doctor' or 'patient'
    text = models.TextField()
    timestamp = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)


class Outbound_Hospital(models.Model):
    CALLING_STATUS_CHOICES = [
        ("not_happened", "NOT HAPPENED"),
        ("connected", "CONNECTED"),
        ("not_connected", "NOT CONNECTED"),
        ("in_progress", "IN PROGRESS"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vapi_id = models.CharField(max_length=1000, null=True, blank=True)
    status = models.CharField(max_length=1000, null=True, blank=True)
    assistant_id = models.ForeignKey(
        Outbound_assistant, on_delete=models.SET_NULL, null=True, blank=True
    )
    patient_id = models.ForeignKey(
        Patient_model,
        on_delete=models.SET_NULL,
        related_name="patients_outbound",
        null=True,
        blank=True,
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="calls"
    )
    endedReason = models.CharField(max_length=1000, null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(default=timezone.now)
    message_s3_link = models.CharField(max_length=10000, null=True, blank=True)
    audio_link = models.CharField(max_length=10000, null=True, blank=True)
    task_id = models.CharField(max_length=10000, null=True, blank=True)
    task_id_process = models.CharField(max_length=10000, null=True, blank=True)
    calling_process = models.CharField(
        max_length=30,
        choices=CALLING_STATUS_CHOICES,
        default="not_happened",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.vapi_id} ({self.patient_id})"


class Inbound_Hospital(models.Model):
    CALLING_STATUS_CHOICES = [
        ("not_happened", "NOT HAPPENED"),
        ("connected", "CONNECTED"),
        ("not_connected", "NOT CONNECTED"),
        ("in_progress", "IN PROGRESS"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    hospital = models.ForeignKey(
        Hospital_model,
        on_delete=models.CASCADE,
        related_name="inbound_calls",
        null=True,
        blank=True,
    )
    vapi_id = models.CharField(max_length=1000, null=True, blank=True)
    status = models.CharField(max_length=1000, null=True, blank=True)
    # assistant_id=models.ForeignKey(Outbound_assistant,on_delete=models.SET_NULL,null=True,blank=True)
    # patient_id=models.ForeignKey(Patient_model, on_delete=models.SET_NULL, related_name='patients_outbound',null=True,blank=True)
    endedReason = models.CharField(max_length=1000, null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(default=timezone.now)
    message_s3_link = models.CharField(max_length=10000, null=True, blank=True)
    audio_link = models.CharField(max_length=10000, null=True, blank=True)
    task_id = models.CharField(max_length=10000, null=True, blank=True)
    task_id_process = models.CharField(max_length=10000, null=True, blank=True)
    calling_process = models.CharField(
        max_length=30,
        choices=CALLING_STATUS_CHOICES,
        default="not_happened",
        null=True,
        blank=True,
    )
    from_phone_number = models.CharField(max_length=30, null=True, blank=True)
    to_phone_numnber = models.CharField(max_length=30, null=True, blank=True)
    department = models.CharField(max_length=255, default="N/A", null=True, blank=True)

    def __str__(self):
        return f"{self.vapi_id} "


class CallFeedbackModel_inbound(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Inbound_Hospital",  # Update this to match your actual app/model name
        on_delete=models.CASCADE,
    )

    CALL_STATUS_CHOICES = [
        ("connected", "Connected"),
        ("not_connected", "Not Connected"),
    ]
    call_status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES)

    CALL_OUTCOME_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
        ("escalated", "Escalated"),
        ("no_feedback", "No Feedback"),
    ]
    call_outcome = models.CharField(max_length=20, choices=CALL_OUTCOME_CHOICES)

    remarks = models.TextField(blank=True, null=True)
    community_added = models.BooleanField(default=False)
    revisit_encouraged = models.BooleanField(default=False)
    escalation_required = models.BooleanField(default=False)
    call_duration = models.CharField(blank=True, null=True)  # in minutes
    called_by = models.CharField(max_length=255, blank=True, null=True)
    called_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CommunityEngagementModel_inbound(models.Model):
    ENGAGEMENT_TYPE_CHOICES = [
        ("post", "Post"),
        ("comment", "Comment"),
        ("poll_participation", "Poll Participation"),
        ("like", "Like"),
        ("share", "Share"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Inbound_Hospital",  # Update 'patients' if the app label is different
        on_delete=models.CASCADE,
    )
    engagement_type = models.CharField(max_length=20, choices=ENGAGEMENT_TYPE_CHOICES)
    engagement_date = models.DateField(
        default=timezone.localdate  # This returns the current date in IST if TIME_ZONE is set
    )
    department = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.engagement_type} by {self.patient_id} on {self.engagement_date}"


class EscalationModel_inbound(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in-progress", "In Progress"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        "Inbound_Hospital", on_delete=models.CASCADE  # Adjust app/model name as needed
    )
    issue_description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    department = models.TextField(null=True, blank=True)
    escalated_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Escalation {self.id} - {self.status}"
