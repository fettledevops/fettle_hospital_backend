from django.db import models
import uuid
from django.utils import timezone


class DermatologyPatient(models.Model):
    """Represents a patient user for dermatology consultations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.email})"

    class Meta:
        db_table = 'dermatology_patients'


class DermatologyThread(models.Model):
    """Represents a consultation thread between a patient and the AI/doctor."""
    MODE_CHOICES = [
        ('general_education', 'General Education'),
        ('post_payment_intake', 'Post Payment Intake'),
        ('dermatologist_review', 'Dermatologist Review'),
        ('final_output', 'Final Output'),
    ]
    PAYMENT_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]

    id = models.AutoField(primary_key=True)
    patient = models.ForeignKey(
        DermatologyPatient,
        on_delete=models.CASCADE,
        related_name='threads',
    )
    name = models.CharField(max_length=255, default='Consultation')
    mode = models.CharField(
        max_length=50, choices=MODE_CHOICES, default='general_education'
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, default='unpaid'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active'
    )
    conversation = models.JSONField(default=list)
    intake_data = models.JSONField(null=True, blank=True)
    draft_response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dermatology_threads'
        ordering = ['-created_at']

    def __str__(self):
        return f"Thread {self.id} - {self.patient.email} ({self.mode})"


class GlobalConfig(models.Model):
    """Global configuration key-value store for system settings."""
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'global_config'

    def __str__(self):
        return self.key
