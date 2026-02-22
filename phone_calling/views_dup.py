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
from django.http import HttpResponse
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
from django.db.models import Subquery
from django.conf import settings
import io
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
            # patients = Patient_model.objects.select_related('hospital').filter(
            #         hospital_id__in=hospital_ids
            #     ).order_by('-uploaded_at')
            ## add hospital id condition also
            outbound_mobile_qs = (
                Patient_model.objects
                .filter(patients_outbound__calling_process__in=['not_happened', 'connected'])
                .values('mobile_no')
                .distinct()
            )

            patients = (
                Patient_model.objects
                .select_related('hospital')
                .filter(hospital_id__in=hospital_ids)
                # exclude mobile_nos that appear in the outbound_mobile_qs above
                .exclude(mobile_no__in=Subquery(outbound_mobile_qs))
                # pick oldest per mobile_no
                .order_by('mobile_no', 'uploaded_at')   # created_at oldest-first
                .distinct('mobile_no')                 # PostgreSQL-only: one row per mobile_no
            )
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
            print(len(outbound_calls))
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
class download_excel_outbound(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            def make_naive(dt, tz_name='UTC'):
                import pytz
                if dt is None:
                    return None
                # If dt is timezone-aware, convert to tz_name and then drop tzinfo.
                if getattr(dt, "tzinfo", None) is not None:
                    target_tz = pytz.timezone(tz_name)
                    return dt.astimezone(target_tz).replace(tzinfo=None)
                # already naive
                return dt
            user_id= request.user_id
            role = request.role
            if role=='user':
                return Response({"msg":"Invalid User","error":0})
            start_date=request.data['start_date']
            end_date=request.data['end_date']
            Oqs = Outbound_Hospital.objects.select_related("patient_id").filter( started_at__date__range=[start_date, end_date] )
            data=[]
            for obj in Oqs:
                print("id--->",obj.id, obj.patient_id.patient_name,obj.patient_id.mobile_no)
                data.append({
                    "id": obj.id,
                    "vapi_id": obj.vapi_id,
                    "patient_name": obj.patient_id.patient_name if obj.patient_id else None,
                    "mobile_no":obj.patient_id.mobile_no,
                    "age":obj.patient_id.age,
                    "department":obj.patient_id.department,
                    "started_at": make_naive(obj.started_at, tz_name='Asia/Kolkata'),
                    "ended_at":   make_naive(obj.ended_at,   tz_name='Asia/Kolkata'),
                    "transcription_link":f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/"+obj.message_s3_link.replace(f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/", "") if obj.message_s3_link else "",
                    "audio_link":obj.audio_link if obj.audio_link else "",
                    "status": obj.status,
                    "calling_process": obj.calling_process,
                })
            df_empty=pd.DataFrame(data)
            print(df_empty.columns)
            buffer = io.BytesIO()
            df_empty.to_excel(buffer, index=False, engine='openpyxl')
            
            buffer.seek(0)
            print("ehllo")
            df_empty.to_excel("abcd.xlsx")
            filename = f"outbound_hospitals.xlsx"
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return Response({"error":1,"errorMsg":str(e)})
        
        
        
            
            