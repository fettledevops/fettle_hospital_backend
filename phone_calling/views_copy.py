from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from app.models import Admin_model,Hospital_model,Patient_model,HospitalUploadLog,CallFeedbackModel,CommunityEngagementModel,EscalationModel,Patient_date_model,TextModel,Hospital_user_model,Outbound_Hospital,Outbound_assistant
from django.contrib.auth.hashers import check_password
import pandas as pd
from project.jwt_auth import create_token,JWTAuthentication
from django.utils.timezone import now
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from django.utils import timezone
import numpy as np
from datetime import timedelta
from django.db.models.functions import TruncDate
from django.db.models import Count,Avg,Min,F, ExpressionWrapper, DurationField, Q
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
from .tasks import call_outbound_task,process_outbound_calls
class Outbound_call(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == 'user':
                return Response({"msg": "Only Admin can run it", "error": 0, "errorMsg": ""})

            payload = request.data
            hospital_id = payload.get('hospital_name')

            if not hospital_id:
                return Response({"msg": "hospital_id is required", "error": 1})

            # Safely get hospital or 404-style response
            try:
                hospital_obj = Hospital_model.objects.get(id=hospital_id)
            except Hospital_model.DoesNotExist:
                return Response({"msg": "Invalid hospital_id", "error": 1})

            # Get assistant for hospital
            try:
                outbound_assistant = Outbound_assistant.objects.get(hospital=hospital_obj)
            except Outbound_assistant.DoesNotExist:
                return Response({"msg": "No assistant id found for this hospital", "error": 1})
            except Outbound_assistant.MultipleObjectsReturned:
                return Response({"msg": "Multiple assistants found for this hospital", "error": 1})

            assistant_id = outbound_assistant.assistant_id
            call_id=outbound_assistant.call_id

            if not assistant_id:
                return Response({"msg": "Assistant exists but assistant_id is empty", "error": 1})
            hospital_ids=[hospital_obj.id]
            patients = Patient_model.objects.select_related('hospital').filter(
                    hospital_id__in=hospital_ids
                ).order_by('-uploaded_at')
            hospital_ids = {p.hospital.id for p in patients}
            hospital_text_map = {
                t.hospital_id: t.text
                for t in TextModel.objects.filter(hospital_id__in=hospital_ids)
            }

            patient_data = [
                    {
                        "id": p.id,
                        "patient_name": p.patient_name,
                        "mobile_no": p.mobile_no,
                        "department": p.department,
                        "hospital_name": p.hospital.name,
                        "whatsapp_link":f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={hospital_text_map.get(p.hospital.id, '')}"
                        
                    }
                    for p in patients
                ]
            calling=[]
            for i in patient_data:
                metadata={"patient_id":str(i["id"]),"patient_name":i["patient_name"],"hospital":i["hospital_name"],"department":i["department"]}
                json_payload={"assistantId":assistant_id,"phoneNumberId":call_id,"customer":{"number":"+91"+i["mobile_no"]},"metadata":metadata}
                # calling.append(json_payload)
                # print("json_payload--->",json_payload)
                calling.append(call_outbound_task.delay(json_payload).id)
                ##call in celery

            return Response({
                "msg": "Assistant found",
                "assistant_id": assistant_id,
                "patients":patient_data,
                "calling":calling,
                "error": 0
            })
        except Exception as e:
            return Response({"error":1,"errorMsg":str(e)})

class Process_Outbound_call(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == 'user':
                return Response({"msg": "Only Admin can run it", "error": 0, "errorMsg": ""})
            outbound_calls = (Outbound_Hospital.objects.filter(status='queued'))
            outbound_data = [
            {
                "id": str(p.id),
                "vapi_id":str(p.vapi_id),
                "status":p.status,
                "patient_id":str(p.patient_id.id),
                "patient_name":p.patient_id.patient_name,
                "mobile_no":p.patient_id.mobile_no,
                "department":p.patient_id.department,
                "hospital_name":p.patient_id.hospital.name,
                "endedReason":p.endedReason,
                "started_at":p.started_at,
                "ended_at":p.ended_at,
                "message_s3_link":p.message_s3_link,
                "audio_link":p.audio_link,
                "task_id":p.task_id,
                
                
            }
            for p in outbound_calls
        ]
            calling=[]
            processing_ids=[]
            for i in outbound_data:
                res=process_outbound_calls.delay(i).id
                processing_ids.append(i["id"])
                calling.append(res)
                
            return Response({"processing_ids":processing_ids,"calling_task_id":calling})
        except Exception as e:
            return Response({"error":1,"errorMsg":str(e)})

            
            