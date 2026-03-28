from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (
    Admin_model,
    Hospital_model,
    Patient_model,
    HospitalUploadLog,
    CallFeedbackModel,
    CommunityEngagementModel,
    EscalationModel,
    Patient_date_model,
    TextModel,
    Hospital_user_model,
    Outbound_Hospital,
    Outbound_assistant,
    Campaign,
    Doctor_model,
    MediVoiceSession,
    MediVoiceTranscription,
    Inbound_Hospital,
    CallFeedbackModel_inbound,
)
from django.contrib.auth.hashers import check_password
import pandas as pd
from project.jwt_auth import create_token, JWTAuthentication
from django.utils.timezone import now
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone
import numpy as np
from datetime import timedelta
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.db.models import (
    Count,
    Avg,
    Min,
    F,
    ExpressionWrapper,
    DurationField,
    Q,
)
from collections import OrderedDict
from humanize import naturaltime
from collections import defaultdict, Counter
from calendar import month_abbr
from django.utils.timezone import localtime
from docx import Document
from datetime import datetime
import uuid
from django.conf import settings
from .utils.s3_uploader import upload_to_s3
from django.http import HttpResponse
from django.template.loader import render_to_string
from .utils.pdf_generator import generate_pdf_from_html


# Create your views here.
def replace_placeholders_in_docx_preserving_styles(
    docx_path, output_path, replacements_dict
):
    doc = Document(docx_path)

    for paragraph in doc.paragraphs:
        runs = paragraph.runs
        i = 0
        while i < len(runs):
            combined = ""
            indices = []

            j = i
            while j < len(runs):
                combined += runs[j].text
                indices.append(j)

                # Check if any placeholder is found in combined text
                match = None
                for placeholder in replacements_dict:
                    if placeholder in combined:
                        match = placeholder
                        break

                if match:
                    # Replace placeholder in combined text
                    replaced = combined.replace(match, str(replacements_dict[match]))

                    # Save formatting of first run
                    base_run = runs[indices[0]]
                    bold = base_run.bold
                    italic = base_run.italic
                    underline = base_run.underline
                    font = base_run.font.name
                    size = base_run.font.size

                    # Clear all involved runs
                    for idx in indices:
                        runs[idx].text = ""

                    # Set replaced text with preserved style in the first run
                    r = runs[indices[0]]
                    r.text = replaced
                    r.bold = bold
                    r.italic = italic
                    r.underline = underline
                    r.font.name = font
                    r.font.size = size

                    # Skip to end of matched run group
                    i = indices[-1]
                    break

                j += 1
            i += 1

    doc.save(output_path)
    # convert(output_path, "o.pdf")


def get_ordinal(n):
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


class login_view(APIView):
    def post(self, request):
        try:
            name_email = request.data["email"]
            password = request.data["password"]
            is_admin = request.data["is_admin"]
            if is_admin:
                try:
                    admin_user = Admin_model.objects.get(email=name_email)
                except Admin_model.DoesNotExist:
                    return Response({"msg": "Admin not found", "error": 1})
                if check_password(password, admin_user.password_hash):

                    token = create_token(
                        {
                            "user_id": str(admin_user.id),
                            "email": admin_user.email,
                            "role": "Admin",
                        }
                    )
                    return Response(
                        {"msg": "Admin login successful", "token": token, "error": 0}
                    )
                else:
                    return Response({"msg": "Invalid password", "error": 1})
            else:
                try:
                    # hospital = Hospital_model.objects.get(name=name_email)
                    hospital_user = Hospital_user_model.objects.get(name=name_email)
                except Admin_model.DoesNotExist:
                    return Response({"msg": "Hospital not found", "error": 1})
                if check_password(password, hospital_user.password_hash):
                    print("hello")
                    token = create_token(
                        {
                            "user_id": str(hospital_user.id),
                            "email": hospital_user.name,
                            "role": "user",
                        }
                    )
                    print("token-->", token)
                    return Response(
                        {
                            "msg": "Hospital login successful",
                            "token": str(token),
                            "error": 0,
                        }
                    )
                else:
                    return Response({"msg": "Invalid password", "error": 1})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class patient_insert_view(APIView):
    authentication_classes = [
        JWTAuthentication,
    ]

    def post(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(
                id=request.user_id
            ).hospital.id
            hospital = Hospital_model.objects.get(id=hospital_id)
            files_list = request.FILES.getlist("files")

            if not files_list:
                return Response({"msg": "No files uploaded", "error": 1})

            filenames = [file.name for file in files_list]
            log = HospitalUploadLog.objects.create(
                hospital=hospital, file_names=filenames, status="PENDING"
            )

            for file in files_list:
                if not (file.name.endswith(".csv") or file.name.endswith(".xlsx")):
                    log.status = "FAILED"
                    log.message = "Unsupported file type: Upload only .csv and .xlsx"
                    log.save()
                    return Response({"msg": log.message, "error": 1})

            required_columns = [
                "Sno.",
                "Patient Name",
                "Age",
                "Mobile No",
                "Departments",
                "Date",
            ]
            df_list = []
            df_date_list = []
            for file in files_list:
                if file.name.endswith(".xlsx"):
                    df = pd.read_excel(file)
                else:
                    df = pd.read_csv(file)

                df_date = df.copy()

                if not all(col in df.columns for col in required_columns):
                    log.status = "FAILED"
                    log.message = f"Missing columns in {file.name}"
                    log.save()
                    return Response({"msg": log.message, "error": 1})

                try:
                    df.drop(columns=["Date"], inplace=True)

                    # Convert and truncate datetime to minute precision
                    df_date["Date"] = pd.to_datetime(df_date["Date"])

                    df_list.append(df)
                    df_date_list.append(df_date)

                    # file_keys.update(
                    #     (str(row["Mobile No"]), row["Departments"])
                    #     for _, row in df.iterrows()
                    # )
                    # file_keys_date.update(
                    #     (str(row["Mobile No"]), row["Departments"], row["Date"])
                    #     for _, row in df_date.iterrows()
                    # )

                except Exception as e:
                    log.status = "FAILED"
                    log.message = str(e)
                    log.save()
                    return Response({"msg": str(e), "error": 1})

            # Query existing records
            # existing_keys = set(
            #     Patient_model.objects.filter(
            #         hospital=hospital,
            #         mobile_no__in=[k[0] for k in file_keys],
            #         department__in=[k[1] for k in file_keys]
            #     ).values_list('mobile_no', 'department')
            # )

            # FIX: Normalize dates from database to match our format
            # existing_keys_date = set()
            # for mobile_no, department, date in Patient_date_model.objects.filter(
            #     hospital=hospital,
            #     mobile_no__in=[k[0] for k in file_keys_date],
            #     department__in=[k[1] for k in file_keys_date],
            #     date__in=[k[2] for k in file_keys_date]
            # ).values_list('mobile_no', 'department', 'date'):
            #     # Normalize database date to match our format
            #     normalized_date = date.replace(second=0, microsecond=0, tzinfo=None)
            #     existing_keys_date.add((mobile_no, department, normalized_date))

            new_patients = []
            new_patients_date = []

            for df in df_list:
                for _, row in df.iterrows():
                    key = (str(row["Mobile No"]), row["Departments"])

                    new_patients.append(
                        Patient_model(
                            hospital=hospital,
                            serial_no=str(row.get("Sno.", "")),
                            patient_name=row["Patient Name"],
                            age=row.get("Age"),
                            mobile_no=key[0],
                            department=key[1],
                            uploaded_at=now(),
                        )
                    )

            for df in df_date_list:
                for _, row in df.iterrows():

                    key = (str(row["Mobile No"]), row["Departments"], row["Date"])

                    #     if key not in existing_keys_date:
                    new_patients_date.append(
                        Patient_date_model(
                            hospital=hospital,
                            serial_no=str(row.get("Sno.", "")),
                            patient_name=row["Patient Name"],
                            age=row.get("Age"),
                            mobile_no=key[0],
                            department=key[1],
                            date=key[2],
                            uploaded_at=now(),
                        )
                    )

            try:
                with transaction.atomic():
                    Patient_model.objects.bulk_create(
                        new_patients, ignore_conflicts=True
                    )
                    Patient_date_model.objects.bulk_create(
                        new_patients_date, ignore_conflicts=True
                    )
                    log.status = "SUCCESS"
                    log.message = "Files uploaded successfully"
                    log.save()
            except Exception as e:
                log.status = "FAILED"
                log.message = f"Upload failed during DB insert: {str(e)}"
                log.save()
                return Response({"msg": log.message, "error": 1})

            return Response(
                {
                    "msg": "working",
                    "patients_count": len(new_patients),
                    "patients_date_count": len(new_patients_date),
                    "error": 0,
                }
            )

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class CallFeedbackView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                try:
                    user = Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.calllog_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})

            inputdict = request.data
            patient_id = inputdict.get("patient_id")
            call_status = inputdict.get("call_status")
            call_outcome = inputdict.get("call_outcome")
            remarks = inputdict.get("remarks", "")
            community_added = inputdict.get("community_added", False)
            revisit_encouraged = inputdict.get("revisit_encouraged", False)
            escalation_required = inputdict.get("escalation_required", False)
            call_duration = inputdict.get("call_duration", 0)
            called_by = inputdict.get("called_by")
            called_at = inputdict.get("called_at")
            print(called_at)
            try:
                called_at = parse_datetime(called_at)
            except Exception:
                called_at = None
            print(timezone.get_current_timezone())
            if called_at is not None and timezone.is_naive(called_at):
                print("trrrr")
                called_at = timezone.make_aware(
                    called_at, timezone.get_current_timezone()
                )
            # print(called_at)
            # Ensure it's timezone-aware (IST)
            # if called_at is not None and timezone.is_naive(called_at):
            # called_at = make_aware(called_at)
            # # Validate patient existence
            try:
                patient = Patient_model.objects.get(id=patient_id)
            except Patient_model.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})

            # Create the feedback record
            CallFeedbackModel.objects.create(
                patient=patient,
                call_status=call_status,
                call_outcome=call_outcome,
                remarks=remarks,
                community_added=community_added,
                revisit_encouraged=revisit_encouraged,
                escalation_required=escalation_required,
                call_duration=call_duration,
                called_by=called_by,
                called_at=called_at,
            )

            return Response({"msg": "Call feedback saved successfully", "error": 0})

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class EscalationfeedbackView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                try:
                    user = Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.escalation_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict = request.data
            patient_id = inputdict.get("patient_id")
            issue_description = inputdict.get("issue_description")
            department = inputdict.get("department")
            try:
                patient = Patient_model.objects.get(id=patient_id)
            except Patient_model.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            EscalationModel.objects.create(
                patient=patient,
                issue_description=issue_description,
                department=department,
            )
            return Response({"msg": "Escalation feedback recorded", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class UpdateEscalation(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            # if role == 'user':
            #     return Response({"msg": "Invalid user", "error": 0})
            inputdict = request.data
            id = inputdict["id"]
            status = inputdict["status"]
            resolution_notes = inputdict["resolution_notes"]
            try:
                escalation = EscalationModel.objects.get(id=id)
            except EscalationModel.DoesNotExist:
                return Response({"msg": "id does not exist", "error": 1})
            escalation.status = status
            escalation.resolution_notes = resolution_notes

            # If marked as resolved, add timestamp
            if status == "resolved":
                escalation.resolved_at = timezone.now()

            escalation.save()

            return Response({"msg": "Escalation updated .", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class CommunityfeedbackView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                try:
                    user = Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.community_egagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict = request.data
            patient_id = inputdict.get("patient_id")
            engagement_type = inputdict.get("engagement_type", "post")
            department = inputdict.get("department")
            try:
                patient = Patient_model.objects.get(id=patient_id)
            except Patient_model.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            CommunityEngagementModel.objects.create(
                patient=patient, engagement_type=engagement_type, department=department
            )
            return Response({"msg": "Community feedback recorded", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class UpdateCommunity(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                try:
                    user = Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.community_egagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict = request.data
            id = inputdict.get("id")
            engagement_type = inputdict.get("engagement_type", "post")
            department = inputdict.get("department")
            try:
                community = CommunityEngagementModel.objects.get(id=id)
            except CommunityEngagementModel.DoesNotExist:
                return Response({"msg": "community record does not exist", "error": 1})
            community.engagement_type = engagement_type
            community.department = department
            community.save()
            return Response({"msg": "Community updated", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class EscalationManagementView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                try:
                    user = Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.escalation_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            queryset = EscalationModel.objects.select_related("patient").all()

            escalations = [
                {
                    "id": e.id,
                    "issue_description": e.issue_description,
                    "status": e.status,
                    "department": e.department,
                    "escalated_at": e.escalated_at,
                    "resolved_at": e.resolved_at,
                    "resolution_notes": e.resolution_notes,
                    "patient_name": e.patient.patient_name,
                    "hospital_name": e.patient.hospital.name,
                }
                for e in queryset
            ]

            return Response({"data": list(escalations), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class fetchpatients_restricted(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            admin_id = request.user_id
            role = request.role
            hospital_ids = []
            print("role--->", role)
            if role == "user":
                hospital_users = Hospital_user_model.objects.get(id=admin_id)
                if hospital_users.calllog_engagement:
                    hospital_ids.append(hospital_users.hospital.id)
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            else:
                restricted_hospital = list(
                    Hospital_user_model.objects.filter(calllog_engagement=True)
                    .values_list("hospital_id", flat=True)
                    .distinct()
                )
                all_hospital = list(
                    Hospital_user_model.objects.filter()
                    .values_list("hospital_id", flat=True)
                    .distinct()
                )
                hospital_ids.extend(list(set(all_hospital) - set(restricted_hospital)))

            limit_param = request.query_params.get("limit", "").strip().lower()
            raw_params = request.query_params.get("call_status", "").strip().lower()
            filter_params = set(
                [s.strip().lower() for s in raw_params.split(",") if s.strip()]
            )
            queryset = (
                Patient_model.objects.select_related("hospital")
                .filter(hospital_id__in=hospital_ids)
                .order_by("mobile_no", "uploaded_at")
            )

            outbound_assistant_ids = Outbound_assistant.objects.filter(
                hospital_id__in=hospital_ids
            )
            Outbound_Hospital_patients = list(
                Outbound_Hospital.objects.filter(
                    assistant_id__in=outbound_assistant_ids
                ).select_related("patient_id__hospital")
            )
            lookup = {}

            for o in Outbound_Hospital_patients:
                # print(o.patient)
                key = (
                    (o.patient_id.patient_name or "").strip().lower(),
                    (o.patient_id.mobile_no or "").strip().lower(),
                    (o.patient_id.hospital.name or "")
                    .strip()
                    .lower(),  # adjust if field name differs
                )
                if o.calling_process == "not_happened":
                    if o.status == "queued":
                        lookup[key] = "queued"
                    else:
                        lookup[key] = "not_connected"
                else:
                    lookup[key] = o.calling_process or "N/A"
            # print("lookup-->",lookup)
            # If 'limit' is not given, empty, or 'all' â†’ fetch all
            if limit_param in ["", "all"]:
                patients = queryset
            else:
                try:
                    limit = int(limit_param)
                    patients = queryset[:limit]
                except ValueError:
                    return Response({"msg": "Invalid limit value", "error": 1})
            # Preload all texts related to hospitals in one query
            hospital_ids = {p.hospital.id for p in patients}
            hospital_text_map = {
                t.hospital_id: t.text
                for t in TextModel.objects.filter(hospital_id__in=hospital_ids)
            }
            status_color_hex = {
                "connected": "#28A745",
                "not_connected": "#DC3545",
                "queued": "#FFC107",
            }
            gray_color = "#6C757D"
            for p in patients:
                key = (
                    (p.patient_name or "").strip().lower(),
                    (p.mobile_no or "").strip().lower(),
                    (p.hospital.name or "").strip().lower(),
                )
                p.calling_progress = lookup.get(key, "N/A")
                p.hex_color = status_color_hex.get(p.calling_progress, gray_color)

            patient_data = []
            print(filter_params)
            for p in patients:
                if (
                    len(filter_params) == 0
                    or p.calling_progress.strip().lower() in filter_params
                ):
                    patient_data.append(
                        {
                            "id": p.id,
                            "patient_name": p.patient_name,
                            "mobile_no": p.mobile_no,
                            "department": p.department,
                            "hospital_name": p.hospital.name,
                            "whatsapp_link": f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={hospital_text_map.get(p.hospital.id, '')}",
                            "calling_progress": p.calling_progress,
                            "color": p.hex_color,
                        }
                    )

            return Response(
                {"data": patient_data, "count": len(patient_data), "error": 0}
            )

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class fetchrecentactivity(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            role = request.role
            if role == "user":
                return Response({"msg": "Invalid user", "error": 0})
            limit = 5
            queryset_call = CallFeedbackModel.objects.select_related(
                "patient"
            ).order_by("-called_at")[:limit]
            queryset_escalation = EscalationModel.objects.select_related(
                "patient"
            ).order_by("-escalated_at")
            queryset_community = CommunityEngagementModel.objects.select_related(
                "patient"
            ).order_by("-created_at")
            call_data = [
                {
                    "id": e.id,
                    "call_outcome": e.call_outcome,
                    "called_at": e.called_at,
                    "hospital": e.patient.hospital.name,
                    "patient_name": e.patient.patient_name,
                }
                for e in queryset_call
            ]
            escalation_data = [
                {
                    "id": e.id,
                    "issue_description": e.issue_description,
                    "status": e.status,
                    "escalated_at": e.escalated_at,
                    "hospital": e.patient.hospital.name,
                    "patient_name": e.patient.patient_name,
                }
                for e in queryset_escalation
            ]
            community_data = [
                {
                    "id": e.id,
                    "engagement_type": e.engagement_type,
                    "created_at": e.created_at,
                    "hospital": e.patient.hospital.name,
                    "patient_name": e.patient.patient_name,
                }
                for e in queryset_community
            ]

            return Response(
                {
                    "call_data": call_data,
                    "escalation_data": escalation_data,
                    "community_data": community_data,
                    "error": 0,
                }
            )

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class AdminDashboardView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            role = request.role
            if role == "user":
                return Response({"msg": "Only admin can access this", "error": 0})
            hospital_ids = request.query_params.get("hospital_ids")
            hospital_filter = {}
            if hospital_ids:
                ids_list = [id.strip() for id in hospital_ids.split(",") if id.strip()]
                hospital_filter = {"hospital_id__in": ids_list}
            patientsCount = Patient_model.objects.filter(**hospital_filter).count()
            callCount = (
                CallFeedbackModel.objects.filter(
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    )
                ).count()
                if hospital_ids
                else CallFeedbackModel.objects.count()
            )
            escalationCount = (
                EscalationModel.objects.filter(
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    )
                ).count()
                if hospital_ids
                else EscalationModel.objects.count()
            )
            hospitalsCount = (
                Hospital_model.objects.filter(id__in=ids_list).count()
                if hospital_ids
                else Hospital_model.objects.count()
            )
            connectedCalls = (
                CallFeedbackModel.objects.filter(
                    call_status="connected",
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    ),
                ).count()
                if hospital_ids
                else CallFeedbackModel.objects.filter(call_status="connected").count()
            )
            communityAdded = (
                CommunityEngagementModel.objects.filter(
                    engagement_type="community_added",
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    ),
                ).count()
                if hospital_ids
                else CommunityEngagementModel.objects.filter(
                    engagement_type="community_added"
                ).count()
            )
            callCount_for_rate = callCount if callCount else 1
            callAnswerRate = (
                np.round(connectedCalls / callCount_for_rate * 100) if callCount else 0
            )
            connected_and_added = (
                CallFeedbackModel.objects.filter(
                    call_status="connected",
                    community_added=True,
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    ),
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
                if hospital_ids
                else CallFeedbackModel.objects.filter(
                    call_status="connected", community_added=True
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            connected = (
                CallFeedbackModel.objects.filter(
                    call_status="connected",
                    patient__hospital_id__in=(
                        ids_list
                        if hospital_ids
                        else Patient_model.objects.values_list("hospital_id", flat=True)
                    ),
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
                if hospital_ids
                else CallFeedbackModel.objects.filter(call_status="connected")
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            conversion_rate = (
                np.round((connected_and_added / connected) * 100, 2) if connected else 0
            )
            return Response(
                {
                    "patientsCount": patientsCount,
                    "callCount": callCount,
                    "escalationCount": escalationCount,
                    "hospitalsCount": hospitalsCount,
                    "connectedCalls": connectedCalls,
                    "communityAdded": communityAdded,
                    "callAnswerRate": callAnswerRate,
                    "communityConversion": conversion_rate,
                    "error": 0,
                }
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class KPISummary(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id

            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())  # Monday
            start_of_last_week = start_of_this_week - timedelta(days=7)

            # === Total calls ===
            contact_this_week_count = CallFeedbackModel.objects.filter(
                called_at__date__gte=start_of_this_week,
                called_at__date__lte=today,
                patient__hospital=user_id,
            ).count()

            contact_last_week_count = CallFeedbackModel.objects.filter(
                called_at__date__gte=start_of_last_week,
                called_at__date__lt=start_of_this_week,
                patient__hospital=user_id,
            ).count()

            # === Connected calls ===
            connected_this_week = CallFeedbackModel.objects.filter(
                call_status="connected",
                called_at__date__gte=start_of_this_week,
                called_at__date__lte=today,
                patient__hospital=user_id,
            )

            connected_last_week = CallFeedbackModel.objects.filter(
                call_status="connected",
                called_at__date__gte=start_of_last_week,
                called_at__date__lt=start_of_this_week,
                patient__hospital=user_id,
            )

            connected_this_week_count = connected_this_week.count()
            connected_last_week_count = connected_last_week.count()

            # === KPI 1: Total Patients Contacted ===
            if contact_last_week_count > 0:
                contact_change = (
                    (contact_this_week_count - contact_last_week_count)
                    / contact_last_week_count
                ) * 100
                contact_trend = "up" if contact_change > 0 else "down"
            else:
                contact_change = 100.0 if contact_this_week_count > 0 else 0.0
                contact_trend = "up" if contact_this_week_count > 0 else "flat"
            total_contacts = (
                CallFeedbackModel.objects.filter(patient__hospital=user_id)
                .distinct()
                .count()
            )
            patients_contact = {
                "title": "Total Patients Contacted",
                "value": f"{total_contacts:,}",
                "change": f"{contact_change:+.0f}%",
                "trend": contact_trend,
                "icon": "Users",
                "color": "blue",
            }

            # === KPI 2: Call Answer Rate ===
            connect_this_week_rate = (
                (connected_this_week_count / contact_this_week_count * 100)
                if contact_this_week_count > 0
                else 0
            )
            connect_last_week_rate = (
                (connected_last_week_count / contact_last_week_count * 100)
                if contact_last_week_count > 0
                else 0
            )

            if connect_last_week_rate > 0:
                connect_change = connect_this_week_rate - connect_last_week_rate
                connect_trend = "up" if connect_change > 0 else "down"
            else:
                connect_change = connect_this_week_rate
                connect_trend = "up" if connect_this_week_rate > 0 else "flat"
            try:
                connected_people_rate = np.round(
                    (
                        CallFeedbackModel.objects.filter(
                            patient__hospital=user_id, call_status="connected"
                        )
                        .values("patient")
                        .distinct()
                        .count()
                        / total_contacts
                    )
                    * 100,
                    2,
                )
            except Exception:
                connected_people_rate = 0
            call_rate = {
                "title": "Call Answer Rate",
                "value": f"{connected_people_rate:.0f}%",
                "change": f"{connect_change:+.0f}%",
                "trend": connect_trend,
                "icon": "Phone",
                "color": "green",
            }

            # === KPI 3: Community Conversion ===
            community_this_week = connected_this_week.filter(
                community_added=True, patient__hospital=user_id
            ).count()
            community_last_week = connected_last_week.filter(
                community_added=True, patient__hospital=user_id
            ).count()

            community_this_week_rate = (
                (community_this_week / connected_this_week_count * 100)
                if connected_this_week_count > 0
                else 0
            )
            community_last_week_rate = (
                (community_last_week / connected_last_week_count * 100)
                if connected_last_week_count > 0
                else 0
            )

            if community_last_week_rate > 0:
                community_change = community_this_week_rate - community_last_week_rate
                community_trend = "up" if community_change > 0 else "down"
            else:
                community_change = community_this_week_rate
                community_trend = "up" if community_this_week_rate > 0 else "flat"
            try:
                community_members_rate = (
                    CallFeedbackModel.objects.filter(
                        community_added=True, patient__hospital=user_id
                    )
                    .distinct()
                    .count()
                    / total_contacts
                )
                community_members_rate = np.round(community_members_rate * 100, 2)
            except Exception:
                community_members_rate = 0
            community_card = {
                "title": "Community Conversion",
                "value": f"{community_members_rate:.0f}%",
                "change": f"{community_change:+.0f}%",
                "trend": community_trend,
                "icon": "MessageCircle",
                "color": "purple",
            }
            # === KPI 4: Escalated Issues (from EscalationModel) ===
            escalated_this_week = EscalationModel.objects.filter(
                escalated_at__date__gte=start_of_this_week,
                escalated_at__date__lte=today,
                patient__hospital=user_id,
            ).count()

            escalated_last_week = EscalationModel.objects.filter(
                escalated_at__date__gte=start_of_last_week,
                escalated_at__date__lt=start_of_this_week,
                patient__hospital=user_id,
            ).count()

            if escalated_last_week > 0:
                escalated_change = (
                    (escalated_this_week - escalated_last_week) / escalated_last_week
                ) * 100
                escalated_trend = "up" if escalated_change > 0 else "down"
            else:
                escalated_change = 100.0 if escalated_this_week > 0 else 0.0
                escalated_trend = "up" if escalated_this_week > 0 else "flat"
            total_escalation = EscalationModel.objects.filter(
                patient__hospital=user_id
            ).count()
            escalation_card = {
                "title": "Escalated Issues",
                "value": str(total_escalation),
                "change": f"{escalated_change:+.0f}%",
                "trend": escalated_trend,
                "icon": "AlertTriangle",
                "color": "orange",
            }

            return Response(
                {
                    "total_patients_contacted": patients_contact,
                    "call_answer_rate": call_rate,
                    "community_conversion": community_card,
                    "escalated_issues": escalation_card,
                }
            )

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class fetchpatients(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = request.user_id
            role = request.role
            hospital_ids = []
            if role == "user":
                hospital_user = Hospital_user_model.objects.get(id=user_id)
                hospital_ids.append(hospital_user.hospital.id)
            else:
                hospital_ids = list(Hospital_model.objects.values_list("id", flat=True))

            limit_param = request.query_params.get("limit", "").strip().lower()
            raw_params = request.query_params.get("call_status", "").strip().lower()
            filter_params = set(
                [s.strip().lower() for s in raw_params.split(",") if s.strip()]
            )

            queryset = (
                Patient_model.objects.select_related("hospital")
                .filter(hospital_id__in=hospital_ids)
                .order_by("mobile_no", "uploaded_at")
            )

            if limit_param in ["", "all"]:
                patients_list = list(queryset)
            else:
                try:
                    limit = int(limit_param)
                    patients_list = list(queryset[:limit])
                except ValueError:
                    patients_list = list(queryset)

            out_calls = Outbound_Hospital.objects.filter(
                patient_id__hospital_id__in=hospital_ids
            ).values("patient_id", "calling_process", "status")
            lookup = {
                str(o["patient_id"]): (
                    o["calling_process"]
                    if o["calling_process"] != "not_happened"
                    else ("queued" if o["status"] == "queued" else "not_connected")
                )
                for o in out_calls
            }

            h_text_map = {
                t.hospital_id: t.text
                for t in TextModel.objects.filter(hospital_id__in=hospital_ids)
            }
            status_colors = {
                "connected": "#28A745",
                "not_connected": "#DC3545",
                "queued": "#FFC107",
                "in_progress": "#3B82F6",
            }

            patient_data = []
            for p in patients_list:
                cp = lookup.get(str(p.id), "not_connected")
                if not filter_params or cp.lower() in filter_params:
                    patient_data.append(
                        {
                            "id": p.id,
                            "patient_name": p.patient_name,
                            "mobile_no": p.mobile_no,
                            "department": p.department,
                            "hospital_name": p.hospital.name,
                            "whatsapp_link": f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={h_text_map.get(p.hospital.id, '')}",
                            "calling_progress": cp,
                            "color": status_colors.get(cp, "#6C757D"),
                        }
                    )
            return Response(
                {"data": patient_data, "count": len(patient_data), "error": 0}
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class Patientengagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            sd, ed = request.query_params.get("start_date"), request.query_params.get(
                "end_date"
            )
            if sd and ed:
                today, start = (
                    datetime.strptime(ed, "%Y-%m-%d").date(),
                    datetime.strptime(sd, "%Y-%m-%d").date(),
                )
            else:
                today, start = timezone.now().date(), timezone.now().date() - timedelta(
                    days=90
                )

            # Raw volume using started_at
            contacts_qs = Outbound_Hospital.objects.filter(
                patient_id__hospital=user_id, started_at__date__range=[start, today]
            )
            delta = (today - start).days
            data = []
            if delta > 60:
                qs = (
                    contacts_qs.annotate(p=TruncMonth("started_at"))
                    .values("p")
                    .annotate(c=Count("id"))
                    .order_by("p")
                )
                for item in qs:
                    if item["p"]:
                        data.append(
                            {"date": item["p"].strftime("%b %Y"), "contacts": item["c"]}
                        )
            else:
                qs = (
                    contacts_qs.annotate(p=TruncDate("started_at"))
                    .values("p")
                    .annotate(c=Count("id"))
                    .order_by("p")
                )
                day_map = {
                    (start + timedelta(days=i)).strftime("%Y-%m-%d"): 0
                    for i in range(delta + 1)
                }
                for item in qs:
                    if item["p"]:
                        day_map[item["p"].strftime("%Y-%m-%d")] = item["c"]
                for ds, count in sorted(day_map.items()):
                    data.append(
                        {
                            "date": datetime.strptime(ds, "%Y-%m-%d").strftime("%b %d"),
                            "contacts": count,
                        }
                    )

            # Feedback Data
            fb_qs = CallFeedbackModel.objects.filter(
                patient__hospital=user_id, called_at__date__range=[start, today]
            )
            total = fb_qs.count()
            ans = fb_qs.filter(call_status="connected").count()

            from django.db.models import FloatField
            from django.db.models.functions import Cast

            agg = fb_qs.aggregate(avg_dur=Avg(Cast("call_duration", FloatField())))
            avg_dur = agg["avg_dur"] or 0

            return Response(
                {
                    "contactsData": data,
                    "callAnswerData": [
                        {
                            "name": "Answered",
                            "value": np.round((ans / total * 100 if total else 0), 2),
                            "color": "#10B981",
                        },
                        {
                            "name": "Not Answered",
                            "value": np.round(
                                100 - (ans / total * 100 if total else 0), 2
                            ),
                            "color": "#EF4444",
                        },
                    ],
                    "metadata": {
                        "total_calls_all_period": total,
                        "average_call_duration": np.round(float(avg_dur), 2),
                    },
                    "error": 0,
                }
            )
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class CommunityEngagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())

            # 4 full weeks including this one (from oldest to newest)
            week_starts = [
                start_of_this_week - timedelta(weeks=i) for i in reversed(range(4))
            ]

            # Step 1: Get actual data from DB
            weekly_qs = (
                CommunityEngagementModel.objects.filter(
                    created_at__date__gte=week_starts[0], patient__hospital=user_id
                )
                .annotate(week=TruncWeek("created_at"))
                .values("week")
                .annotate(added=Count("id"))
            )

            # Step 2: Create a default map with 0s
            week_map = OrderedDict()
            for week_start in week_starts:
                week_map[week_start] = 0

            # Step 3: Fill in values from DB results
            for row in weekly_qs:
                week_start_date = row["week"].date()
                if week_start_date in week_map:
                    week_map[week_start_date] = row["added"]

            # Step 4: Format for frontend
            community_growth_data = []
            for i, (week_start, added) in enumerate(week_map.items()):
                community_growth_data.append({"date": f"Week {i + 1}", "added": added})

            # === Department-wise engagement ===
            dept_qs = (
                CommunityEngagementModel.objects.filter(
                    created_at__date__gte=week_starts[0], patient__hospital=user_id
                )
                .exclude(department__isnull=True)
                .exclude(department__exact="")
                .values("department")
                .annotate(engagement=Count("id"))
                .order_by("-engagement")
            )

            department_engagement_data = [
                {"department": row["department"], "engagement": row["engagement"]}
                for row in dept_qs
            ]
            total_engagements = CommunityEngagementModel.objects.filter(
                patient__hospital=user_id
            ).count()
            total_posts = CommunityEngagementModel.objects.filter(
                engagement_type="post", patient__hospital=user_id
            ).count()

            avg_engagement_per_post = (
                total_engagements / total_posts if total_posts > 0 else 0
            )
            today = timezone.localdate()
            start_of_month = today.replace(day=1)

            # Find patients whose first engagement was this month
            first_engagements = (
                CommunityEngagementModel.objects.filter(patient__hospital=user_id)
                .values("patient")
                .annotate(first_engagement=Min("engagement_date"))
                .filter(first_engagement__gte=start_of_month)
            )

            new_members_this_month = first_engagements.count()
            start_of_week = today - timedelta(days=today.weekday())

            # Filter posts made this week
            posts_this_week = CommunityEngagementModel.objects.filter(
                engagement_type="post",
                engagement_date__gte=start_of_week,
                engagement_date__lte=today,
                patient__hospital=user_id,
            ).count()
            meta_data = {
                "community_members": total_engagements,
                "post_week": posts_this_week,
                "avg_engagement/post": avg_engagement_per_post,
                "new_members": new_members_this_month,
            }

            connected_and_added = (
                CallFeedbackModel.objects.filter(
                    call_status="connected",
                    community_added=True,
                    patient__hospital=user_id,
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            connected = (
                CallFeedbackModel.objects.filter(
                    call_status="connected", patient__hospital=user_id
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            conversion_rate = (
                (connected_and_added / connected) * 100 if connected else 0
            )
            total_engaged_users = (
                CommunityEngagementModel.objects.filter(patient__hospital=user_id)
                .values("patient")
                .distinct()
                .count()
            )

            poll_participants = (
                CommunityEngagementModel.objects.filter(
                    engagement_type="poll_participation", patient__hospital=user_id
                )
                .values("patient")
                .distinct()
                .count()
            )

            poll_participation_rate = (
                (poll_participants / total_engaged_users) * 100
                if total_engaged_users
                else 0
            )
            one_week_ago = timezone.localdate() - timedelta(days=7)

            weekly_active_users = (
                CommunityEngagementModel.objects.filter(
                    engagement_date__gte=one_week_ago, patient__hospital=user_id
                )
                .values("patient")
                .distinct()
                .count()
            )
            metrics = {
                "conversion_rate": np.round(conversion_rate, 2),
                "poll_participation_rate": np.round(poll_participation_rate, 2),
                "weekly_active_users": weekly_active_users,
            }

            # === Feedback Distribution (based on CallFeedbackModel) ===
            fb_dist_qs = (
                CallFeedbackModel.objects.filter(patient__hospital=user_id)
                .values("call_outcome")
                .annotate(value=Count("id"))
                .order_by("-value")
            )
            feedback_distribution = []
            for item in fb_dist_qs:
                outcome = item["call_outcome"]
                # Fetch detailed data for this outcome
                details = (
                    CallFeedbackModel.objects.filter(
                        patient__hospital=user_id, call_outcome=outcome
                    )
                    .select_related("patient")
                    .order_by("-called_at")[:10]
                )
                feedback_distribution.append(
                    {
                        "name": outcome.replace("_", " ").title(),
                        "value": item["value"],
                        "patients": [
                            {
                                "name": d.patient.patient_name,
                                "date": (
                                    d.called_at.strftime("%Y-%m-%d")
                                    if d.called_at
                                    else "N/A"
                                ),
                                "feedback": d.remarks or "No remarks provided.",
                            }
                            for d in details
                        ],
                    }
                )

            # === Patient Intents (based on CommunityEngagementModel engagement types) ===
            intent_qs = (
                CommunityEngagementModel.objects.filter(patient__hospital=user_id)
                .values("engagement_type")
                .annotate(value=Count("id"))
                .order_by("-value")
            )
            patient_intents = []
            for item in intent_qs:
                etype = item["engagement_type"]
                details = (
                    CommunityEngagementModel.objects.filter(
                        patient__hospital=user_id, engagement_type=etype
                    )
                    .select_related("patient")
                    .order_by("-created_at")[:10]
                )
                patient_intents.append(
                    {
                        "name": etype.replace("_", " ").title(),
                        "value": item["value"],
                        "intent": etype.replace("_", " ").title(),
                        "count": item["value"],
                        "patients": [
                            {
                                "name": d.patient.patient_name,
                                "date": (
                                    d.created_at.strftime("%Y-%m-%d")
                                    if d.created_at
                                    else "N/A"
                                ),
                                "feedback": f"Engaged via {etype}",
                            }
                            for d in details
                        ],
                    }
                )

            return Response(
                {
                    "communityGrowthData": community_growth_data,
                    "departmentEngagementData": department_engagement_data,
                    "feedbackDistribution": feedback_distribution,
                    "patientIntents": patient_intents,
                    "metadata": meta_data,
                    "metrics": metrics,
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class RevisitAnalyticsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(
                id=request.user_id
            ).hospital.id

            visits = (
                Patient_date_model.objects.filter(hospital_id=hospital_id)
                .annotate(visit_day=TruncDate("date"))
                .values("mobile_no", "department", "date")
                .distinct()
            )

            visit_map = defaultdict(set)
            for visit in visits:
                key = (visit["mobile_no"], visit["department"])
                visit_map[key].add(visit["date"])

            color_map = {
                "Cardiology": "#EF4444",
                "Orthopedics": "#F59E0B",
                "Pediatrics": "#10B981",
                "General Medicine": "#3B82F6",
            }

            department_counter = Counter()
            monthly_counter = Counter()
            time_gap_counter = Counter()
            all_gaps = []
            repeat_visits_this_month = 0

            current_date = localtime(now())
            current_year = current_date.year
            current_month = current_date.month

            for (mobile_no, department), visit_days in visit_map.items():
                if len(visit_days) > 1:
                    sorted_days = sorted(visit_days)
                    department_counter[department] += 1

                    # Monthly revisits (skip first)
                    for date in sorted_days[1:]:
                        local_date = localtime(date)
                        month_key = (local_date.year, local_date.month)
                        monthly_counter[month_key] += 1

                        if (
                            local_date.year == current_year
                            and local_date.month == current_month
                        ):
                            repeat_visits_this_month += 1

                    # Gap calculation
                    for i in range(1, len(sorted_days)):
                        gap = (sorted_days[i] - sorted_days[i - 1]).days
                        all_gaps.append(gap)
                        if 0 <= gap <= 7:
                            time_gap_counter["0-7 days"] += 1
                        elif 8 <= gap <= 30:
                            time_gap_counter["8-30 days"] += 1
                        elif 31 <= gap <= 90:
                            time_gap_counter["1-3 months"] += 1
                        elif 91 <= gap <= 180:
                            time_gap_counter["3-6 months"] += 1
                        elif gap > 180:
                            time_gap_counter["6+ months"] += 1

            total_revisits = sum(department_counter.values())

            department_data = []
            for dept, count in department_counter.items():
                percentage = (count / total_revisits) * 100 if total_revisits > 0 else 0
                department_data.append(
                    {
                        "name": dept,
                        "value": count,
                        "percentage": round(percentage, 2),
                        "color": color_map.get(dept, "#6B7280"),
                    }
                )

            monthly_data = []
            for year, month in sorted(monthly_counter.keys()):
                label = f"{month_abbr[month]} {str(year)[2:]}"
                monthly_data.append(
                    {"month": label, "revisits": monthly_counter[(year, month)]}
                )

            gap_order = [
                "0-7 days",
                "8-30 days",
                "1-3 months",
                "3-6 months",
                "6+ months",
            ]
            time_gap_data = [
                {"gap": label, "count": time_gap_counter.get(label, 0)}
                for label in gap_order
            ]

            average_gap = round(sum(all_gaps) / len(all_gaps), 2) if all_gaps else None

            return Response(
                {
                    "department_data": department_data,
                    "monthly_trend": monthly_data,
                    "time_gap_distribution": time_gap_data,
                    "average_revisit_gap": average_gap,
                    "repeat_visits_this_month": repeat_visits_this_month,
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class EscalationEngagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            now = timezone.now()

            # === 1. Department-wise Escalation Counts ===
            dept_qs = (
                EscalationModel.objects.filter(patient__hospital=user_id)
                .exclude(department__isnull=True)
                .exclude(department__exact="")
                .values("department", "issue_description", "patient__patient_name")
            )
            from collections import defaultdict

            dept_dict = defaultdict(list)

            for item in dept_qs:
                if item["issue_description"]:  # skip empty issues
                    dept_dict[item["department"]].append(
                        {
                            "patient_name": item["patient__patient_name"],
                            "issue": item["issue_description"],
                        }
                    )

            department_escalation_data = [
                {"department": dept, "count": len(issues), "issues": issues}
                for dept, issues in sorted(
                    dept_dict.items(), key=lambda x: len(x[1]), reverse=True
                )
            ]

            # === 2. Resolution Status Counts ===
            status_colors = {
                "resolved": "#10B981",
                "in-progress": "#F59E0B",
                "pending": "#EF4444",
            }

            status_qs = (
                EscalationModel.objects.filter(patient__hospital=user_id)
                .values("status")
                .annotate(value=Count("id"))
            )
            for row in status_qs:
                print(row["status"])
            dict_present = {"Pending": False, "In-progress": False, "Resolved": False}
            total_sum = 0
            for row in status_qs:
                dict_present[row["status"].replace("_", " ").title()] = True
                total_sum += row["value"]

            not_present = []
            for k, v in dict_present.items():
                if not v:
                    not_present.append(
                        {"name": k, "value": 0, "color": status_colors[k.lower()]}
                    )
            resolution_status_data = [
                {
                    "name": row["status"].replace("_", " ").title(),
                    "value": (
                        np.round((row["value"] / total_sum) * 100, 2)
                        if total_sum != 0
                        else 0
                    ),
                    "color": status_colors.get(
                        row["status"], "#6B7280"
                    ),  # default gray
                }
                for row in status_qs
            ]
            resolution_status_data.extend(not_present)

            # === 3. Recent Escalations ===
            recent_qs = (
                EscalationModel.objects.filter(patient__hospital=user_id)
                .select_related("patient")
                .order_by("-escalated_at")[:5]
            )

            recent_escalations = []
            for i, esc in enumerate(recent_qs, start=1):
                recent_escalations.append(
                    {
                        "id": esc.id,
                        "patient": esc.patient.patient_name,
                        "issue": esc.issue_description,
                        "status": esc.status,
                        "time": naturaltime(esc.escalated_at),
                    }
                )
            total_escalations = EscalationModel.objects.filter(
                patient__hospital=user_id
            ).count()
            avg_resolution_time = (
                EscalationModel.objects.filter(
                    status="resolved",
                    resolved_at__isnull=False,
                    patient__hospital=user_id,
                )
                .annotate(
                    resolution_duration=ExpressionWrapper(
                        F("resolved_at") - F("escalated_at"),
                        output_field=DurationField(),
                    )
                )
                .aggregate(avg_time=Avg("resolution_duration"))["avg_time"]
            )

            # Step 2: Convert to minutes
            avg_resolution_minutes = (
                np.round(avg_resolution_time.total_seconds() / 60, 2)
                if avg_resolution_time
                else 0
            )

            resolved_today = EscalationModel.objects.filter(
                status="resolved", resolved_at__date=now, patient__hospital=user_id
            ).count()

            meta_data = {
                "total_escalations": total_escalations,
                "avg_resolution_time": avg_resolution_minutes,
                "resolved_today": resolved_today,
                "formulae": {
                    "Revenue Influenced": "Appointments Booked * 650",
                    "Leakage Prevented": "Missed Calls * 0.42 * 650",
                    "Staff Hours Saved": "Total Call Duration / 60",
                    "Equivalent FTE Freed": "Total Call Duration / 6000",
                    "Cost Efficiency Value": "(Total Call Duration / 6000) * 40000",
                },
            }
            return Response(
                {
                    "departmentEscalationData": department_escalation_data,
                    "resolutionStatusData": resolution_status_data,
                    "recentEscalations": recent_escalations,
                    "metadata": meta_data,
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class validateToken(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            role = request.role
            name = request.email

            return Response({"role": role, "name": name, "error": 0, "msg": "Success"})
        except Exception as e:
            return Response({"role": "", "name": "", "error": 1, "msg": str(e)})


class upload_files_log(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            role = request.role
            if role != "user":
                return Response(
                    {"msg": "Only hospital users can view upload logs", "error": 1}
                )
            logs = HospitalUploadLog.objects.filter(hospital_id=user_id).order_by(
                "-uploaded_at"
            )
            data = [
                {
                    "id": str(log.id),
                    "file_names": log.file_names,
                    "status": log.status,
                    "uploaded_at": log.uploaded_at,
                    "message": log.message,
                }
                for log in logs
            ]
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class Allhospitals(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            role = request.role
            print("role-->", role)
            if role != "Admin":
                return Response(
                    {"msg": "Only Admin can view all hospitals ", "error": 1}
                )
            hospitals = Hospital_model.objects.all().values("id", "name").distinct()
            data = list(hospitals)
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class PdfView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            inputdict = request.data
            obj = Hospital_user_model.objects.get(id=request.user_id)
            user_id, hospital_name = obj.hospital.id, obj.hospital.name
            start_date = datetime.strptime(inputdict["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(inputdict["end_date"], "%Y-%m-%d").date()

            start_str = f"{get_ordinal(start_date.day)} {start_date.strftime('%B %Y')}"
            end_str = f"{get_ordinal(end_date.day)} {end_date.strftime('%B %Y')}"

            # Interaction Data
            connected_data = (
                CallFeedbackModel.objects.filter(
                    called_at__date__range=[start_date, end_date],
                    patient__hospital=user_id,
                )
                .distinct()
                .count()
            )
            call_cc = (
                CallFeedbackModel.objects.filter(
                    patient__hospital=user_id,
                    called_at__date__range=[start_date, end_date],
                    call_status="connected",
                )
                .values("patient")
                .distinct()
                .count()
            )
            community_members = (
                CallFeedbackModel.objects.filter(
                    called_at__date__range=[start_date, end_date],
                    community_added=True,
                    patient__hospital=user_id,
                )
                .distinct()
                .count()
            )
            poll_participants = (
                CommunityEngagementModel.objects.filter(
                    created_at__date__range=[start_date, end_date],
                    engagement_type="poll_participation",
                    patient__hospital=user_id,
                )
                .values("patient")
                .distinct()
                .count()
            )
            total_escalations = EscalationModel.objects.filter(
                escalated_at__date__range=[start_date, end_date],
                patient__hospital=user_id,
            ).count()

            q_visits = Patient_date_model.objects.filter(
                date__range=(start_date, end_date), hospital=user_id
            )
            unique_patients = (
                q_visits.values("hospital", "mobile_no").distinct().count()
            )
            total_revisits = (
                q_visits.values("hospital", "mobile_no")
                .annotate(visit_count=Count("id"))
                .filter(visit_count__gt=1)
                .count()
            )

            revisit_conversion_rate = (
                (total_revisits / unique_patients * 100) if unique_patients else 0
            )
            connected_people_rate = (
                np.round((call_cc / connected_data) * 100, 2) if connected_data else 0
            )
            community_members_rate = (
                np.round((community_members / connected_data) * 100, 2)
                if connected_data
                else 0
            )

            report_type = inputdict.get("report_type", "detailed")

            context = {
                "report_type": report_type,
                "reporting_period": f"{start_str} to {end_str}",
                "hospital_name": hospital_name.title(),
                "call_patients": connected_data,
                "call_answer_rate": connected_people_rate,
                "community_added": community_members,
                "community_conversion_rate": community_members_rate,
                "poll_number": poll_participants,
                "escalation_number": total_escalations,
                "revisit_conversion_rate": np.round(revisit_conversion_rate, 2),
                "revisit_number": total_revisits,
                "call_connected": call_cc,
            }

            # If only metrics, we can use a different template or logic
            template = "report_template.html"
            if report_type == "only_metrics":
                # Maybe use a simplified template or context
                pass

            html_string = render_to_string(template, context)
            pdf_bytes = generate_pdf_from_html(html_string)

            if pdf_bytes:
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = (
                    f'attachment; filename="report_{uuid.uuid4()}.pdf"'
                )
                return response
            else:
                return Response({"error": 1, "errorMsg": "PDF generation failed"})
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})


class TextView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            # Handle both JSON and multipart/form-data
            text = request.data.get("text")
            media_file = request.FILES.get("media")
            target_list_file = request.FILES.get("target_list")

            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            hospital = Hospital_model.objects.get(id=user_id)

            media_url = None
            if media_file:
                # Use absolute path for S3 upload
                media_url = upload_to_s3(
                    media_file, f"whatsapp_media/{uuid.uuid4()}_{media_file.name}"
                )

            # Update or create TextModel for hospital's default message
            text_obj, created = TextModel.objects.update_or_create(
                hospital=hospital,
                defaults=(
                    {"text": text, "media_url": media_url}
                    if text
                    else {"media_url": media_url}
                ),
            )

            if target_list_file:
                # Parse Excel/CSV target list
                if target_list_file.name.endswith(".xlsx"):
                    df = pd.read_excel(target_list_file)
                else:
                    df = pd.read_csv(target_list_file)

                # Identify mobile number column
                numbers = []
                possible_cols = ["Mobile No", "Mobile", "Phone", "mobile_no", "Number"]
                for col in possible_cols:
                    if col in df.columns:
                        numbers = df[col].dropna().tolist()
                        break

                if not numbers:
                    # Try first column if none of the specific names match
                    numbers = df.iloc[:, 0].dropna().tolist()

                if numbers:
                    from phone_calling.tasks import cloudconnect_whatsapp_msg

                    for num in numbers:
                        # Ensure number is a string and formatted
                        num_str = (
                            str(int(float(num)))
                            if isinstance(num, (int, float))
                            else str(num)
                        )
                        msg = text if text else "Health Update from " + hospital.name
                        if media_url:
                            msg += f"\nView attachment: {media_url}"
                        cloudconnect_whatsapp_msg(msg, to_number=num_str)

            return Response(
                {
                    "error": 0,
                    "msg": (
                        "Message broadcast initiated"
                        if target_list_file
                        else "Template saved"
                    ),
                    "media_url": media_url,
                }
            )
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            hospital = Hospital_model.objects.get(id=user_id)
            text = TextModel.objects.get(hospital=hospital)
            print("text---->", text)
            return Response({"error": 0, "msg": "Success", "data": text.text})
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class tab_access(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = request.user_id
            role = request.role
            if role != "user":
                return Response({"msg": "Invalid user", "error": 0})
            user = Hospital_user_model.objects.get(id=user_id)
            return Response(
                {
                    "patient_engagement": user.patient_engagement,
                    "community_engagement": user.community_egagement,  # typo retained for now
                    "revisit_engagement": user.revisit_engagement,
                    "escalation_engagement": user.escalation_engagement,
                    "calllog_engagement": user.calllog_engagement,
                    "upload_engagement": user.upload_engagement,
                    "pdf_engagement": user.pdf_engagement,
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class ROIMetrics(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            sd, ed = request.query_params.get("start_date"), request.query_params.get(
                "end_date"
            )
            cd = request.query_params.get("call_direction", "outbound")
            attempts = (
                Inbound_Hospital.objects.filter(hospital_id=user_id)
                if cd == "inbound"
                else Outbound_Hospital.objects.filter(patient_id__hospital=user_id)
            )
            fb_qs = (
                CallFeedbackModel_inbound.objects.filter(patient__hospital_id=user_id)
                if cd == "inbound"
                else CallFeedbackModel.objects.filter(patient__hospital=user_id)
            )
            if sd and ed:
                attempts = attempts.filter(started_at__date__range=[sd, ed])
                fb_qs = fb_qs.filter(called_at__date__range=[sd, ed])
            booked = fb_qs.filter(call_outcome="positive").count()
            missed = attempts.filter(calling_process="not_connected").count()
            from django.db.models import FloatField, Sum
            from django.db.models.functions import Cast

            tdur = fb_qs.aggregate(t=Sum(Cast("call_duration", FloatField())))["t"] or 0
            return Response(
                {
                    "roi_financial": [
                        {"name": "Interactions", "value": attempts.count(), "unit": ""},
                        {"name": "Appointments Booked", "value": booked, "unit": ""},
                        {
                            "name": "Revenue Influenced",
                            "value": booked * 650,
                            "unit": "â‚¹",
                        },
                        {
                            "name": "Leakage Prevented",
                            "value": int(missed * 0.42 * 650),
                            "unit": "â‚¹",
                        },
                    ],
                    "roi_efficiency": [
                        {
                            "name": "Staff Hours Saved",
                            "value": np.round(tdur / 60, 1),
                            "unit": "hrs",
                        },
                        {
                            "name": "Equivalent FTE Freed",
                            "value": np.round(tdur / 6000, 2),
                            "unit": "FTE",
                        },
                        {
                            "name": "Cost Efficiency Value",
                            "value": int(tdur / 6000 * 40000),
                            "unit": "â‚¹",
                        },
                    ],
                    "error": 0,
                }
            )
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class DepartmentAnalytics(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            cd = request.query_params.get("call_direction", "outbound")
            if cd == "inbound":
                d_qs = (
                    Inbound_Hospital.objects.filter(hospital_id=user_id)
                    .values("department")
                    .annotate(i=Count("id"))
                )
                f_qs = CallFeedbackModel_inbound.objects.filter(
                    patient__hospital_id=user_id
                )
                df = "department"
            else:
                d_qs = (
                    Patient_model.objects.filter(hospital_id=user_id)
                    .values("department")
                    .annotate(i=Count("id"))
                )
                f_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id)
                df = "patient__department"
            stats = f_qs.values(df).annotate(
                b=Count("id", filter=Q(call_outcome="positive"))
            )
            f_map = {item[df]: item for item in stats}
            data = []
            for item in d_qs:
                dept = (
                    item.get("department")
                    or item.get("patient__department")
                    or "General"
                )
                s = f_map.get(dept, {"b": 0})
                i, b = item["i"], s["b"]
                data.append(
                    {
                        "department": dept,
                        "interactions": i,
                        "bookings": b,
                        "conversion": f"{(b/i*100 if i else 0):.1f}%",
                        "revenue": b * 650,
                    }
                )
            return Response({"department_table": data, "error": 0})
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class CampaignView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            campaigns = Campaign.objects.filter(
                hospital__hospital_user_model__id=request.user_id
            ).order_by("-created_at")
            data = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "status": c.status,
                    "created_at": c.created_at,
                    "stats": {
                        "total_calls": c.calls.count(),
                        "connected_calls": c.calls.filter(
                            calling_process="connected"
                        ).count(),
                    },
                }
                for c in campaigns
            ]
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

    def post(self, request):
        try:
            user = Hospital_user_model.objects.get(id=request.user_id)
            c = Campaign.objects.create(
                hospital=user.hospital,
                name=request.data.get("name"),
                purpose=request.data.get("purpose", ""),
            )
            return Response({"msg": "Success", "id": str(c.id), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class doctor_login_view(APIView):
    def post(self, request):
        try:
            doctor = Doctor_model.objects.get(email=request.data.get("email"))
            if check_password(request.data.get("password"), doctor.password_hash):
                token = create_token(
                    {
                        "user_id": str(doctor.id),
                        "email": doctor.email,
                        "role": "Doctor",
                        "hospital_id": str(doctor.hospital.id),
                    }
                )
                return Response(
                    {
                        "msg": "Success",
                        "token": token,
                        "doctor_name": doctor.name,
                        "hospital_name": doctor.hospital.name,
                        "error": 0,
                    }
                )
            return Response({"msg": "Invalid password", "error": 1})
        except Doctor_model.DoesNotExist:
            return Response({"msg": "Doctor not found", "error": 1})


class MediVoiceSessionView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            doctor = Doctor_model.objects.get(id=request.user_id)
            d = request.data
            s = MediVoiceSession.objects.create(
                doctor=doctor,
                patient_name=d.get("patientName"),
                patient_mobile=d.get("patientMobile"),
                patient_email=d.get("patientEmail"),
                overall_summary=d.get("overallSummary"),
                diagnosis=d.get("diagnosis"),
                medicines=d.get("medicines"),
                revisit_date=d.get("revisitDate"),
                revisit_time=d.get("revisitTime"),
                meta_data=d.get("metaData", {}),
            )
            from phone_calling.tasks import (
                send_prescription_notifications,
                schedule_reminder_calls,
            )

            send_prescription_notifications.delay(s.id)
            schedule_reminder_calls.delay(s.id)

            for t in d.get("transcriptions", []):
                MediVoiceTranscription.objects.create(
                    session=s,
                    speaker=t.get("speaker"),
                    text=t.get("text"),
                    timestamp=t.get("timestamp", 0.0),
                )
            return Response({"msg": "Success", "session_id": str(s.id), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class DoctorManagementView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            doctors = Doctor_model.objects.filter(hospital_id=user_id).order_by(
                "-created_at"
            )
            data = [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "email": d.email,
                    "department": d.department,
                    "created_at": d.created_at,
                }
                for d in doctors
            ]
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

    def post(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            payload = request.data
            action = payload.get("action")

            if action == "reset_password":
                doctor = Doctor_model.objects.get(
                    id=payload.get("id"), hospital_id=user_id
                )
                doctor.password_hash = "doctorpassword"  # Model save() handles hashing
                doctor.save()
                return Response({"msg": "Password reset to default", "error": 0})

            doctor, created = Doctor_model.objects.get_or_create(
                email=payload.get("email"),
                defaults={
                    "hospital_id": user_id,
                    "name": payload.get("name"),
                    "department": payload.get("department"),
                    "password_hash": payload.get(
                        "password", "doctorpassword"
                    ),  # Default if none provided
                },
            )
            if not created:
                return Response(
                    {"msg": "Doctor with this email already exists", "error": 1}
                )
            return Response(
                {"msg": "Doctor account created", "id": str(doctor.id), "error": 0}
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class DoctorTranscriptionView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            doctor_id = request.query_params.get("doctor_id")

            # Fetch all doctors for the filter dropdown
            doctors = Doctor_model.objects.filter(hospital_id=user_id).values(
                "id", "name", "department"
            )

            # Base session query
            session_qs = MediVoiceSession.objects.filter(doctor__hospital_id=user_id)

            # Apply doctor-specific filter if provided
            if doctor_id and doctor_id != "all":
                session_qs = session_qs.filter(doctor_id=doctor_id)

            sessions = session_qs.order_by("-created_at")

            session_data = [
                {
                    "id": str(s.id),
                    "doctorName": s.doctor.name,
                    "doctorDepartment": s.doctor.department,
                    "patientName": s.patient_name,
                    "patientMobile": s.patient_mobile,
                    "overallSummary": s.overall_summary,
                    "createdAt": s.created_at,
                    "transcriptions": [
                        {"speaker": t.speaker, "text": t.text, "timestamp": t.timestamp}
                        for t in s.transcriptions.all().order_by("timestamp")
                    ],
                }
                for s in sessions
            ]

            return Response(
                {"sessions": session_data, "doctors": list(doctors), "error": 0}
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class StaffAvailabilityView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(
                id=request.user_id
            ).hospital.id
            doctors = Doctor_model.objects.filter(hospital_id=hospital_id)
            data = []
            for doc in doctors:
                data.append(
                    {
                        "id": str(doc.id),
                        "name": doc.name,
                        "department": doc.department,
                        "availability": doc.availability,
                    }
                )
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class MediVoiceSyncView(APIView):
    # This is a webhook sync view
    def post(self, request):
        try:
            # Simple secret token check
            secret = request.headers.get("X-Fettle-Secret")
            if secret != settings.MEDIVOICE_SYNC_SECRET:
                return Response({"msg": "Unauthorized", "error": 1}, status=401)

            data = request.data
            # We look for doctor by email or mobile if provided in data
            doctor_email = data.get("doctorEmail")
            try:
                doctor = Doctor_model.objects.get(email=doctor_email)
            except Doctor_model.DoesNotExist:
                return Response({"msg": "Doctor not found", "error": 1})
            session = MediVoiceSession.objects.create(
                doctor=doctor,
                patient_name=data.get("patientName"),
                patient_mobile=data.get("patientMobile"),
                patient_email=data.get("patientEmail"),
                overall_summary=data.get("overallSummary"),
                diagnosis=data.get("diagnosis"),
                medicines=data.get("medicines"),
                revisit_date=data.get("revisitDate"),
                revisit_time=data.get("revisitTime"),
                meta_data=data.get("metaData", {}),
            )

            transcriptions = data.get("transcriptions", [])
            for t in transcriptions:
                MediVoiceTranscription.objects.create(
                    session=session,
                    speaker=t.get("speaker"),
                    text=t.get("text"),
                    timestamp=t.get("timestamp", 0.0),
                )

            from phone_calling.tasks import (
                send_prescription_notifications,
                schedule_reminder_calls,
            )

            send_prescription_notifications.delay(session.id)
            schedule_reminder_calls.delay(session.id)

            return Response(
                {"msg": "Sync successful", "session_id": str(session.id), "error": 0}
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
