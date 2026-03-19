from django.contrib import admin
from .models import (
    Hospital_model,
    Admin_model,
    Patient_model,
    HospitalUploadLog,
    CallFeedbackModel,
    EscalationModel,
    CommunityEngagementModel,
    Patient_date_model,
    TextModel,
    Hospital_user_model,
    Outbound_assistant,
    Outbound_Hospital,
)


# Register your models here.
@admin.register(Admin_model)
class AdminModel(admin.ModelAdmin):
    list_display = ("id", "email", "password_hash", "created_at")

    search_fields = ("id", "email", "password_hash", "created_at")


@admin.register(Hospital_model)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")

    search_fields = ("id", "name", "created_at")


@admin.register(Patient_model)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hospital",
        "patient_name",
        "age",
        "mobile_no",
        "department",
        "uploaded_at",
    )

    search_fields = (
        "id",
        "hospital",
        "patient_name",
        "age",
        "mobile_no",
        "department",
        "uploaded_at",
    )


@admin.register(HospitalUploadLog)
class HospitalLogAdmin(admin.ModelAdmin):
    list_display = ("id", "hospital", "file_names", "status", "uploaded_at", "message")
    search_fields = ("id", "hospital", "file_names", "status", "uploaded_at", "message")


@admin.register(CallFeedbackModel)
class CallFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "call_status",
        "call_outcome",
        "remarks",
        "community_added",
        "revisit_encouraged",
        "escalation_required",
        "call_duration",
        "called_by",
        "called_at",
        "created_at",
    )
    search_fields = (
        "id",
        "patient",
        "call_status",
        "call_outcome",
        "remarks",
        "community_added",
        "revisit_encouraged",
        "escalation_required",
        "call_duration",
        "called_by",
        "called_at",
        "created_at",
    )


@admin.register(EscalationModel)
class EscalationModelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "issue_description",
        "status",
        "department",
        "escalated_at",
        "resolved_at",
        "resolution_notes",
    )
    search_fields = (
        "id",
        "patient",
        "issue_description",
        "status",
        "department",
        "escalated_at",
        "resolved_at",
        "resolution_notes",
    )


@admin.register(CommunityEngagementModel)
class CommunityEngagementModelAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "engagement_type",
        "engagement_date",
        "department",
        "created_at",
    )
    search_fields = (
        "id",
        "patient",
        "engagement_type",
        "engagement_date",
        "department",
        "created_at",
    )


@admin.register(Patient_date_model)
class Patient_date_modelModelAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "hospital",
        "patient_name",
        "age",
        "mobile_no",
        "department",
        "date",
        "uploaded_at",
    )

    search_fields = (
        "id",
        "hospital",
        "patient_name",
        "age",
        "mobile_no",
        "department",
        "date",
        "uploaded_at",
    )


@admin.register(TextModel)
class TextModelAdmin(admin.ModelAdmin):

    list_display = ("id", "hospital", "text")

    search_fields = ("id", "hospital", "text")


@admin.register(Hospital_user_model)
class Hospital_user_ModelAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "hospital",
        "name",
        "password_hash",
        "created_at",
        "patient_engagement",
        "community_egagement",
        "revisit_engagement",
        "escalation_engagement",
        "calllog_engagement",
        "upload_engagement",
        "pdf_engagement",
    )

    search_fields = ("id", "hospital", "name", "password_hash", "created_at")


@admin.register(Outbound_Hospital)
class Outbound_Hospital_ModelAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "vapi_id",
        "status",
        "assistant_id",
        "patient_id",
        "endedReason",
        "started_at",
        "ended_at",
        "message_s3_link",
        "audio_link",
        "task_id",
        "task_id_process",
        "calling_process",
    )

    search_fields = (
        "id",
        "vapi_id",
        "status",
        "assistant_id",
        "patient_id",
        "endedReason",
        "started_at",
        "ended_at",
        "message_s3_link",
        "audio_link",
        "task_id",
        "task_id_process",
        "calling_process",
    )


@admin.register(Outbound_assistant)
class Outbound_assistant_ModelAdmin(admin.ModelAdmin):

    list_display = ("id", "hospital", "assistant_id", "call_id")

    search_fields = ("id", "hospital", "assistant_id", "call_id")
