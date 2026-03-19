from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from app.models import (
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
    Inbound_Hospital,
)
from django.contrib.auth.hashers import check_password
import pandas as pd
from project.jwt_auth import create_token, JWTAuthentication
from django.utils.timezone import now
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from django.utils import timezone
from django.http import HttpResponse
import numpy as np
from datetime import timedelta
from django.db.models.functions import TruncDate
from django.db.models import Count, Avg, Min, F, ExpressionWrapper, DurationField, Q
import calendar
from django.db.models.functions import TruncWeek
from collections import OrderedDict
from humanize import naturaltime
from collections import defaultdict, Counter
from calendar import month_abbr
from django.utils.timezone import localtime
from docx import Document
from datetime import datetime
from docx2pdf import convert
import uuid
import os
from django.http import FileResponse
from .tasks import (
    call_outbound_task,
    process_outbound_calls,
    inbound_call_task,
    process_inbound_calls,
)
from django.db.models import Subquery
from django.conf import settings
import io


class Outbound_call(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                return Response(
                    {"msg": "Only Admin can run it", "error": 0, "errorMsg": ""}
                )

            payload = request.data
            hospital_id = payload.get("hospital_name")

            if not hospital_id:
                return Response({"msg": "hospital_id is required", "error": 1})

            # Safely get hospital or 404-style response
            try:
                hospital_obj = Hospital_model.objects.get(id=hospital_id)
            except Hospital_model.DoesNotExist:
                return Response({"msg": "Invalid hospital_id", "error": 1})

            # Get assistant for hospital
            try:
                outbound_assistant = Outbound_assistant.objects.get(
                    hospital=hospital_obj
                )
            except Outbound_assistant.DoesNotExist:
                return Response(
                    {"msg": "No assistant id found for this hospital", "error": 1}
                )
            except Outbound_assistant.MultipleObjectsReturned:
                return Response(
                    {"msg": "Multiple assistants found for this hospital", "error": 1}
                )

            assistant_id = outbound_assistant.assistant_id
            call_id = outbound_assistant.call_id

            if not assistant_id:
                return Response(
                    {"msg": "Assistant exists but assistant_id is empty", "error": 1}
                )
            hospital_ids = [hospital_obj.id]
            start_date_str = payload.get("start_date")
            end_date_str = payload.get("end_date")
            unconnected_only = payload.get("unconnected_only", False)
            is_individual = payload.get("individual", False)
            target_patient_id = payload.get("patient_id")

            if is_individual and target_patient_id:
                patients = Patient_model.objects.filter(id=target_patient_id)
            else:
                # Find mobile numbers that have successfully connected at least once
                connected_mobile_qs = (
                    Outbound_Hospital.objects.filter(calling_process="connected")
                    .values("patient_id__mobile_no")
                    .distinct()
                )

                patients_query = Patient_model.objects.select_related(
                    "hospital"
                ).filter(hospital_id__in=hospital_ids)

                if unconnected_only:
                    patients_query = patients_query.exclude(
                        mobile_no__in=Subquery(connected_mobile_qs)
                    )

                if start_date_str and end_date_str:
                    patients_query = patients_query.filter(
                        uploaded_at__date__range=[start_date_str, end_date_str]
                    )

                patients = patients_query.order_by(
                    "mobile_no", "-uploaded_at"
                ).distinct("mobile_no")

            hospital_ids_set = {p.hospital.id for p in patients}
            hospital_text_map = {
                t.hospital_id: t.text
                for t in TextModel.objects.filter(hospital_id__in=hospital_ids_set)
            }

            patient_data = [
                {
                    "id": p.id,
                    "patient_name": p.patient_name,
                    "mobile_no": p.mobile_no,
                    "department": p.department,
                    "hospital_name": p.hospital.name,
                    "whatsapp_link": f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={hospital_text_map.get(p.hospital.id, '')}",
                }
                for p in patients
            ]

            # Create/Get Campaign Record (Skip for individual)
            campaign_obj = None
            if not is_individual:
                campaign_name = payload.get("campaign_name", "Default Campaign")
                campaign_id = payload.get("campaign_id")

                from app.models import Campaign

                if campaign_id:
                    campaign_obj = Campaign.objects.get(id=campaign_id)
                else:
                    campaign_obj = Campaign.objects.create(
                        hospital=hospital_obj,
                        name=campaign_name,
                        start_date=(
                            datetime.strptime(start_date_str, "%Y-%m-%d").date()
                            if start_date_str
                            else None
                        ),
                        end_date=(
                            datetime.strptime(end_date_str, "%Y-%m-%d").date()
                            if end_date_str
                            else None
                        ),
                        unconnected_only=unconnected_only,
                    )

            calling = []
            for i in patient_data:
                # Dispatching via LiveKit + CloudConnect SIP
                id_key = (
                    str(i["id"])
                    + "__"
                    + i["hospital_name"]
                    + "__"
                    + i["mobile_no"]
                    + "__"
                    + datetime.now().strftime("%Y%m%d%H%M%S")
                    + "__livekit"
                )
                metadata = {
                    "patient_id": str(i["id"]),
                    "patient_name": i["patient_name"],
                    "hospital": i["hospital_name"],
                    "department": i["department"],
                    "campaign_name": (
                        campaign_obj.name if campaign_obj else "Individual Call"
                    ),
                    "campaign_id": str(campaign_obj.id) if campaign_obj else None,
                    "language_policy": "Strictly ONLY English, Hindi, or Telugu. If the patient speaks any other language, politely end the call and mark as language_barrier.",
                }

                json_payload = {
                    "customer": {"number": "+91" + i["mobile_no"], "id_key": id_key},
                    "metadata": metadata,
                }
                calling.append(call_outbound_task.delay(json_payload).id)

            return Response(
                {
                    "msg": "Outbound campaign initiated via CloudConnect",
                    "campaign_id": str(campaign_obj.id),
                    "patients": patient_data,
                    "calling": calling,
                    "error": 0,
                }
            )
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})


class Process_Outbound_call(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == "user":
                return Response(
                    {"msg": "Only Admin can run it", "error": 0, "errorMsg": ""}
                )
            outbound_calls = Outbound_Hospital.objects.filter(status="queued")
            print(len(outbound_calls))
            outbound_data = [
                {
                    "id": str(p.id),
                    "vapi_id": str(p.vapi_id),
                    "is_livekit": str(p.vapi_id).split("__")[-1] == "livekit",
                    "status": p.status,
                    "patient_id": str(p.patient_id.id),
                    "patient_name": p.patient_id.patient_name,
                    "mobile_no": p.patient_id.mobile_no,
                    "department": p.patient_id.department,
                    "hospital_name": p.patient_id.hospital.name,
                    "endedReason": p.endedReason,
                    "started_at": p.started_at,
                    "ended_at": p.ended_at,
                    "message_s3_link": p.message_s3_link,
                    "audio_link": p.audio_link,
                    "task_id": p.task_id,
                }
                for p in outbound_calls
            ]
            calling = []
            processing_ids = []
            for i in outbound_data:
                res = process_outbound_calls.delay(i).id
                processing_ids.append(i["id"])
                calling.append(res)

            return Response(
                {"processing_ids": processing_ids, "calling_task_id": calling}
            )
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})


class Inboundcall(APIView):
    """
    Handle Inbound Call triggers from LiveKit SIP.
    """

    def post(self, request):
        try:
            print("Inbound Call Request Received:", request.data)
            # LiveKit SIP usually handles room creation automatically.
            # This endpoint can be used for secondary notifications or metadata logging.
            return Response({"status": "acknowledged"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class showInboundcall(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = request.user_id
            role = request.role
            if role == "user":
                return Response({"msg": "Invalid User", "error": 0})
            all_patients = Inbound_Hospital.objects.all().order_by("-started_at")
            print("ok", len(all_patients))
            arr = []

            def make_naive(dt, tz_name="Asia/Kolkata"):
                import pytz

                if dt is None:
                    return None
                if getattr(dt, "tzinfo", None) is not None:
                    target_tz = pytz.timezone(tz_name)
                    return dt.astimezone(target_tz).replace(tzinfo=None)
                return dt

            for i in all_patients:
                arr.append(
                    {
                        "from_phone_number": i.from_phone_number,
                        "to_phone_number": i.to_phone_numnber,
                        "status": (
                            "in_progress"
                            if i.calling_process == "not_happened"
                            else i.calling_process
                        ),
                        "audio_link": i.audio_link,
                        "started_at": make_naive(i.started_at),
                        "ended_at": make_naive(i.ended_at),
                    }
                )
            return Response({"error": 0, "patients": arr})
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})


class processinboundcall_view(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            user_id = request.user_id
            role = request.role
            if role == "user":
                return Response({"msg": "Invalid User", "error": 0})

            # This view is for re-processing historical inbound calls if automation fails
            all_patients = Inbound_Hospital.objects.filter(
                calling_process="not_happened"
            )
            processing_ids = []
            calling = []
            for i in all_patients:
                payload = {
                    "patient_id": str(i.id),
                    "vapi_id": i.vapi_id,  # room_name in LiveKit context
                    "is_livekit": True,
                }
                res = process_inbound_calls.delay(payload).id
                processing_ids.append(str(i.id))
                calling.append(res)
            return Response(
                {"processing_ids": processing_ids, "calling_task_id": calling}
            )
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})


from livekit import api


class LiveKitWebhook(APIView):
    """
    Handle LiveKit Webhooks.
    Automatically triggers processing when a room (call) finishes.
    """

    def post(self, request):
        try:
            # LiveKit webhook verification would go here in production
            # For now, we process the event payload
            event = request.data
            event_type = event.get("event")
            room_name = event.get("room", {}).get("name")

            print(f"LiveKit Webhook: {event_type} for Room: {room_name}")

            if event_type == "room_finished" and room_name:
                # room_name is our id_key
                try:
                    call_obj = Outbound_Hospital.objects.get(vapi_id=room_name)

                    # Prepare payload for processing task
                    process_payload = {
                        "id": str(call_obj.id),
                        "vapi_id": call_obj.vapi_id,
                        "is_livekit": True,
                        "patient_id": str(call_obj.patient_id.id),
                        "mobile_no": call_obj.patient_id.mobile_no,
                        "hospital_name": call_obj.patient_id.hospital.name,
                    }

                    # Trigger processing automatically
                    process_outbound_calls.delay(process_payload)
                    print(f"Automatic processing triggered for: {room_name}")

                except Outbound_Hospital.DoesNotExist:
                    print(f"Webhook error: Call record not found for room {room_name}")

            return Response({"status": "received"}, status=200)
        except Exception as e:
            print(f"LiveKit Webhook Exception: {str(e)}")
            return Response({"error": str(e)}, status=500)


class download_excel_outbound(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:

            def make_naive(dt, tz_name="UTC"):
                import pytz

                if dt is None:
                    return None
                # If dt is timezone-aware, convert to tz_name and then drop tzinfo.
                if getattr(dt, "tzinfo", None) is not None:
                    target_tz = pytz.timezone(tz_name)
                    return dt.astimezone(target_tz).replace(tzinfo=None)
                # already naive
                return dt

            user_id = request.user_id
            role = request.role
            if role == "user":
                return Response({"msg": "Invalid User", "error": 0})
            start_date = request.data["start_date"]
            end_date = request.data["end_date"]
            Oqs = Outbound_Hospital.objects.select_related("patient_id").filter(
                started_at__date__range=[start_date, end_date]
            )
            data = []
            for obj in Oqs:
                print(
                    "id--->",
                    obj.id,
                    obj.patient_id.patient_name,
                    obj.patient_id.mobile_no,
                )
                data.append(
                    {
                        "id": obj.id,
                        "vapi_id": obj.vapi_id,
                        "patient_name": (
                            obj.patient_id.patient_name if obj.patient_id else None
                        ),
                        "mobile_no": obj.patient_id.mobile_no,
                        "age": obj.patient_id.age,
                        "department": obj.patient_id.department,
                        "started_at": make_naive(
                            obj.started_at, tz_name="Asia/Kolkata"
                        ),
                        "ended_at": make_naive(obj.ended_at, tz_name="Asia/Kolkata"),
                        "transcription_link": (
                            f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/"
                            + obj.message_s3_link.replace(
                                f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/", ""
                            )
                            if obj.message_s3_link
                            else ""
                        ),
                        "audio_link": obj.audio_link if obj.audio_link else "",
                        "status": obj.status,
                        "calling_process": obj.calling_process,
                        "uploaded_at": make_naive(
                            obj.patient_id.uploaded_at, tz_name="Asia/Kolkata"
                        ),
                    }
                )
            df_empty = pd.DataFrame(data)
            print(df_empty.columns)
            buffer = io.BytesIO()
            df_empty.to_excel(buffer, index=False, engine="openpyxl")

            buffer.seek(0)
            # print("ehllo")
            # df_empty.to_excel("abcd.xlsx")
            filename = f"outbound_hospitals.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})
