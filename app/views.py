from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Admin_model,Hospital_model,Patient_model,HospitalUploadLog,CallFeedbackModel,CommunityEngagementModel,EscalationModel,Patient_date_model,TextModel,Hospital_user_model,Outbound_Hospital,Outbound_assistant,Campaign,Doctor_model,MediVoiceSession,MediVoiceTranscription,Inbound_Hospital,CallFeedbackModel_inbound,CommunityEngagementModel_inbound,EscalationModel_inbound
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
from django.db.models.functions import TruncDate, Coalesce, Cast
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
# Create your views here.
def replace_placeholders_in_docx_preserving_styles(docx_path, output_path, replacements_dict):
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
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def make_naive(dt, tz_name='Asia/Kolkata'):
    import pytz
    if dt is None:
        return None
    target_tz = pytz.timezone(tz_name)
    # If datetime is timezone-aware → convert to IST → drop tzinfo
    if dt.tzinfo is not None:
        return dt.astimezone(target_tz).replace(tzinfo=None)
    # If datetime is naive → assume UTC → convert to IST
    return pytz.utc.localize(dt).astimezone(target_tz).replace(tzinfo=None)

class login_view(APIView):
    def post(self,request):
        try:
            name_email=request.data['email']
            password=request.data['password']
            is_admin=request.data['is_admin']
            if is_admin:
                try:
                    admin_user = Admin_model.objects.get(email=name_email)
                except Admin_model.DoesNotExist:
                    return Response({"msg": "Admin not found", "error": 1})
                if check_password(password, admin_user.password_hash):
                    
                    token=create_token({"user_id":str(admin_user.id),"email":admin_user.email,'role':'Admin'})
                    return Response({"msg": "Admin login successful","token":token,"error": 0})
                else:
                    return Response({"msg": "Invalid password", "error": 1})
            else:
                try:
                    # hospital = Hospital_model.objects.get(name=name_email)
                    hospital_user = Hospital_user_model.objects.get(name=name_email)
                except Hospital_user_model.DoesNotExist:
                    return Response({"msg": "Hospital not found", "error": 1})
                if check_password(password, hospital_user.password_hash):
                    print("hello")
                    token=create_token({"user_id":str(hospital_user.id),"email":hospital_user.name,'role':'user'})
                    print("token-->",token)
                    return Response({"msg": "Hospital login successful","token":str(token), "error": 0})
                else:
                    return Response({"msg": "Invalid password", "error": 1})
        except Exception as e:
            return Response({"msg":str(e),"error":1})

class doctor_login_view(APIView):
    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            try:
                doctor = Doctor_model.objects.get(email=email)
            except Doctor_model.DoesNotExist:
                return Response({"msg": "Doctor not found", "error": 1})
            
            if check_password(password, doctor.password_hash):
                token = create_token({
                    "user_id": str(doctor.id),
                    "email": doctor.email,
                    "role": "Doctor",
                    "hospital_id": str(doctor.hospital.id)
                })
                return Response({
                    "msg": "Doctor login successful",
                    "token": token,
                    "doctor_name": doctor.name,
                    "hospital_name": doctor.hospital.name,
                    "error": 0
                })
            else:
                return Response({"msg": "Invalid password", "error": 1})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class patient_insert_view(APIView):
    authentication_classes = [JWTAuthentication,]
    def post(self, request):
        try:
            hospital_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            hospital = Hospital_model.objects.get(id=hospital_id)
            files_list = request.FILES.getlist("files")

            if not files_list:
                return Response({"msg": "No files uploaded", "error": 1})

            filenames = [file.name for file in files_list]
            log = HospitalUploadLog.objects.create(
                hospital=hospital,
                file_names=filenames,
                status="PENDING"
            )

            for file in files_list:
                if not (file.name.endswith('.csv') or file.name.endswith('.xlsx')):
                    log.status = 'FAILED'
                    log.message = "Unsupported file type: Upload only .csv and .xlsx"
                    log.save()
                    return Response({"msg": log.message, "error": 1})

            required_columns = ["Sno.", "Patient Name", "Age", "Mobile No", "Departments", "Date"]
            df_list = []
            df_date_list = []
            file_keys = set()
            file_keys_date = set()

            for file in files_list:
                if file.name.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    df = pd.read_csv(file)

                df_date = df.copy()

                if not all(col in df.columns for col in required_columns):
                    log.status = 'FAILED'
                    log.message = f"Missing columns in {file.name}"
                    log.save()
                    return Response({"msg": log.message, "error": 1})

                try:
                    df.drop(columns=['Date'], inplace=True)

                    # Convert and truncate datetime to minute precision
                    df_date['Date'] = pd.to_datetime(df_date['Date'])
                    

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
                    log.status = 'FAILED'
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
                    
                    new_patients.append(Patient_model(
                        hospital=hospital,
                        serial_no=str(row.get("Sno.", "")),
                        patient_name=row["Patient Name"],
                        age=row.get("Age"),
                        mobile_no=key[0],
                        department=key[1],
                        uploaded_at=now()
                    ))
                        

            for df in df_date_list:
                for _, row in df.iterrows():
               
                
                    key = (str(row["Mobile No"]), row["Departments"], row['Date'])

                    #     if key not in existing_keys_date:
                    new_patients_date.append(Patient_date_model(
                        hospital=hospital,
                        serial_no=str(row.get("Sno.", "")),
                        patient_name=row["Patient Name"],
                        age=row.get("Age"),
                        mobile_no=key[0],
                        department=key[1],
                        date=key[2],
                        uploaded_at=now()
                    ))
                
            
            
            
            try:
                with transaction.atomic():
                    Patient_model.objects.bulk_create(new_patients,ignore_conflicts=True)
                    Patient_date_model.objects.bulk_create(new_patients_date, ignore_conflicts=True)
                    log.status = 'SUCCESS'
                    log.message = 'Files uploaded successfully'
                    log.save()
            except Exception as e:
                log.status = 'FAILED'
                log.message = f'Upload failed during DB insert: {str(e)}'
                log.save()
                return Response({"msg": log.message, "error": 1})

            return Response({
                "msg": "working",
                "patients_count": len(new_patients),
                "patients_date_count": len(new_patients_date),
                "error": 0
            })

        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class CallFeedbackView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role
            
            if role == 'user':
                try:
                    user=Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.calllog_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})

            inputdict = request.data
            patient_id = inputdict.get('patient_id')
            call_status = inputdict.get('call_status')
            call_outcome = inputdict.get('call_outcome')
            remarks = inputdict.get('remarks', '')
            community_added = inputdict.get('community_added', False)
            revisit_encouraged = inputdict.get('revisit_encouraged', False)
            escalation_required = inputdict.get('escalation_required', False)
            call_duration = inputdict.get('call_duration', 0)
            called_by = inputdict.get('called_by')
            called_at=inputdict.get('called_at')
            print(called_at)
            try:
                called_at = parse_datetime(called_at)
            except Exception as e:
                called_at=None
            print(timezone.get_current_timezone())
            if (called_at!=None) and (timezone.is_naive(called_at)):
                print("trrrr")
                called_at = timezone.make_aware(called_at, timezone.get_current_timezone())
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
                called_at=called_at
                
            )

            return Response({"msg": "Call feedback saved successfully", "error": 0})

        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class EscalationfeedbackView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            
            if role == 'user':
                try:
                    user=Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.escalation_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict=request.data
            patient_id = inputdict.get('patient_id')
            issue_description=inputdict.get('issue_description')
            department=inputdict.get('department')
            try:
                patient = Patient_model.objects.get(id=patient_id)
            except Patient_model.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            EscalationModel.objects.create(
                patient=patient,
                issue_description=issue_description,
                department=department
            )
            return Response({"msg":"Escalation feedback recorded","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class UpdateEscalation(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            # if role == 'user':
            #     return Response({"msg": "Invalid user", "error": 0})
            inputdict=request.data
            id=inputdict['id']
            status=inputdict['status']
            resolution_notes=inputdict['resolution_notes']
            try:
                escalation = EscalationModel.objects.get(id=id)
            except EscalationModel.DoesNotExist:
                return Response({"msg": "id does not exist", "error": 1})
            escalation.status = status
            escalation.resolution_notes = resolution_notes

            # If marked as resolved, add timestamp
            if status == 'resolved':
                escalation.resolved_at = timezone.now()

            escalation.save()

            return Response({"msg":"Escalation updated .","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class CommunityfeedbackView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            
            if role == 'user':
                try:
                    user=Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.community_egagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict=request.data
            patient_id = inputdict.get('patient_id')
            engagement_type=inputdict.get('engagement_type','post')
            department=inputdict.get('department')
            try:
                patient = Patient_model.objects.get(id=patient_id)
            except Patient_model.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            CommunityEngagementModel.objects.create(
                patient=patient,
                engagement_type=engagement_type,
                department=department
            )
            return Response({"msg":"Community feedback recorded","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
            
class UpdateCommunity(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            
            if role == 'user':
                try:
                    user=Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.community_egagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            inputdict=request.data
            id = inputdict.get('id')
            engagement_type=inputdict.get('engagement_type','post')
            department=inputdict.get('department')
            try:
                community = CommunityEngagementModel.objects.get(id=id)
            except CommunityEngagementModel.DoesNotExist:
                return Response({"msg": "community record does not exist", "error": 1})
            community.engagement_type=engagement_type
            community.department=department
            community.save()
            return Response({"msg":"Community updated","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class EscalationManagementView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            admin_id=request.user_id
            role=request.role
           
            if role == 'user':
                try:
                    user=Hospital_user_model.objects.get(id=admin_id)
                except Exception as e:
                    return Response({"msg": str(e), "error": 0})
                if user.escalation_engagement:
                    pass
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            queryset = EscalationModel.objects.select_related('patient').all()

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
            
           
            
            return Response({"data":list(escalations),"error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class fetchpatients(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            admin_id = request.user_id
            role = request.role
            hospital_ids=[]
            if role == 'user':
                hospital_user=Hospital_user_model.objects.get(id=admin_id)
                hospital_ids.append(hospital_user.hospital.id)
            else:
                hospital_ids = list(Hospital_model.objects.values_list('id', flat=True))
                
            limit_param = request.query_params.get('limit', 'all').strip().lower()
            unconnected_only = request.query_params.get('unconnected_only', 'false').strip().lower() == 'true'
            
            queryset = Patient_model.objects.filter(hospital_id__in=hospital_ids).order_by('-uploaded_at')

            # Build calling progress lookup
            outbound_calls = Outbound_Hospital.objects.filter(patient_id__hospital_id__in=hospital_ids).select_related("patient_id")
            lookup = {}
            for o in outbound_calls:
                if not o.patient_id: continue
                p_id = str(o.patient_id.id)
                
                status = "not_connected"
                if o.calling_process == 'connected': status = 'connected'
                elif o.status == 'in-progress': status = 'in_progress'
                elif o.status == 'queued': status = 'queued'
                
                # Best status ranking
                rank = {"connected": 4, "in_progress": 3, "queued": 2, "not_connected": 1}
                if rank.get(status, 0) > rank.get(lookup.get(p_id, "not_connected"), 0):
                    lookup[p_id] = status

            if limit_param != 'all':
                try:
                    queryset = queryset[:int(limit_param)]
                except: pass

            patient_data = []
            for p in queryset:
                progress = lookup.get(str(p.id), "not_connected")
                
                # Apply UNCONNECTED ONLY filter
                if unconnected_only and progress in ['connected', 'in_progress', 'queued']:
                    continue

                patient_data.append({
                    "id": str(p.id),
                    "patient_name": p.patient_name,
                    "mobile_no": p.mobile_no,
                    "department": p.department,
                    "hospital_name": p.hospital.name,
                    "calling_progress": progress,
                    "uploaded_at": make_naive(p.uploaded_at)
                })

            return Response({"data": patient_data, "count": len(patient_data), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class fetchrecentactivity(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            if role == 'user':
                return Response({"msg": "Invalid user", "error": 0})
            limit=5
            queryset_call = CallFeedbackModel.objects.select_related('patient').order_by('-called_at')[:limit]
            queryset_escalation = EscalationModel.objects.select_related('patient').order_by('-escalated_at')
            queryset_community = CommunityEngagementModel.objects.select_related('patient').order_by('-created_at')
            call_data = [
                {
                    "id": e.id,
                    "call_outcome": e.call_outcome,
                    "called_at": e.called_at,
                    "hospital":e.patient.hospital.name,
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
                    "hospital":e.patient.hospital.name,
                    "patient_name": e.patient.patient_name,
                    
                }
                for e in queryset_escalation
            ]   
            community_data = [
                {
                    "id": e.id,
                    "engagement_type": e.engagement_type,
                    "created_at": e.created_at,
                    "hospital":e.patient.hospital.name,
                    "patient_name": e.patient.patient_name,
                    
                }
                for e in queryset_community
            ]      

            return Response({"call_data":call_data,"escalation_data":escalation_data,"community_data":community_data,"error":0})
            
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class AdminDashboardView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            admin_id=request.user_id
            role=request.role
            if role == 'user':
                return Response({"msg": "Only admin can access this", "error": 0})
            hospital_ids = request.query_params.get('hospital_ids')
            hospital_filter = {}
            if hospital_ids:
                ids_list = [id.strip() for id in hospital_ids.split(',') if id.strip()]
                hospital_filter = {'hospital_id__in': ids_list}
            patientsCount = Patient_model.objects.filter(**hospital_filter).count()
            callCount = CallFeedbackModel.objects.filter(patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)).count() if hospital_ids else CallFeedbackModel.objects.count()
            escalationCount = EscalationModel.objects.filter(patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)).count() if hospital_ids else EscalationModel.objects.count()
            hospitalsCount = Hospital_model.objects.filter(id__in=ids_list).count() if hospital_ids else Hospital_model.objects.count()
            connectedCalls = CallFeedbackModel.objects.filter(call_status='connected', patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)).count() if hospital_ids else CallFeedbackModel.objects.filter(call_status='connected').count()
            communityAdded = CommunityEngagementModel.objects.filter(engagement_type='community_added', patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)).count() if hospital_ids else CommunityEngagementModel.objects.filter(engagement_type='community_added').count()
            callCount_for_rate = callCount if callCount else 1
            callAnswerRate = np.round(connectedCalls/callCount_for_rate*100) if callCount else 0
            connected_and_added = CallFeedbackModel.objects.filter(
                call_status='connected',
                community_added=True,
                patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)
            ).values_list('patient', flat=True).distinct().count() if hospital_ids else CallFeedbackModel.objects.filter(call_status='connected', community_added=True).values_list('patient', flat=True).distinct().count()
            connected = CallFeedbackModel.objects.filter(
                call_status='connected',
                patient__hospital_id__in=ids_list if hospital_ids else Patient_model.objects.values_list('hospital_id', flat=True)
            ).values_list('patient', flat=True).distinct().count() if hospital_ids else CallFeedbackModel.objects.filter(call_status='connected').values_list('patient', flat=True).distinct().count()
            conversion_rate = np.round((connected_and_added / connected) * 100,2) if connected else 0
            return Response({"patientsCount":patientsCount,"callCount":callCount,"escalationCount":escalationCount,"hospitalsCount":hospitalsCount,"connectedCalls":connectedCalls,"communityAdded":communityAdded,"callAnswerRate":callAnswerRate,"communityConversion":conversion_rate,"error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class KPISummary(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            
            if start_date_str and end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_of_this_month = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                delta = (end_date - start_of_this_month).days
                start_of_prev_month = start_of_this_month - timedelta(days=delta if delta > 0 else 30)
                today = end_date
            else:
                today = timezone.now().date()
                start_of_this_month = today - timedelta(days=90)
                start_of_prev_month = start_of_this_month - timedelta(days=90)

            # === TABLE 1: KEY OUTCOMES (Live Metrics) ===
            
            # 1. Total Patient Interactions (Inbound + Outbound attempts)
            total_inbound_attempts = Inbound_Hospital.objects.filter(
                started_at__date__gte=start_of_this_month, 
                started_at__date__lte=today
            ).count()
            
            total_outbound_attempts = Outbound_Hospital.objects.filter(
                patient_id__hospital=user_id,
                started_at__date__gte=start_of_this_month, 
                started_at__date__lte=today
            ).count()
            
            total_interactions = total_inbound_attempts + total_outbound_attempts
            
            interactions_card = {
                "title": "Total Interactions",
                "value": f"{total_interactions:,}",
                "change": "Live",
                "trend": "up",
                "icon": "Users",
                "color": "blue"
            }

            # Outbound Base Query for Feedback
            base_qs = CallFeedbackModel.objects.annotate(
                effective_called_at=Coalesce('called_at', 'created_at')
            ).filter(
                patient__hospital=user_id,
                effective_called_at__date__gte=start_of_this_month,
                effective_called_at__date__lte=today,
            )
            
            # 2. Avg Call Resolution (seconds)
            avg_res_time = base_qs.filter(call_status='connected').aggregate(avg=Avg(Cast('call_duration', FloatField())))['avg'] or 0
            resolution_card = {
                "title": "Avg Resolution",
                "value": f"{int(avg_res_time * 60)} sec",
                "change": "Live",
                "trend": "up",
                "icon": "Clock",
                "color": "green"
            }

            # 3. Appointment Conversion Rate (%)
            # Logic: (Positive outcomes / Connected calls) * 100
            connected_calls = base_qs.filter(call_status='connected').count()
            booked = base_qs.filter(call_outcome='positive').count()
            conv_rate = (booked / connected_calls * 100) if connected_calls > 0 else 0
            
            conversion_card = {
                "title": "Conversion Rate",
                "value": f"{conv_rate:.1f}%",
                "change": "Target 40%",
                "trend": "up" if conv_rate > 40 else "down",
                "icon": "TrendingUp",
                "color": "purple"
            }

            # 4. No-Show Rate (%) (Placeholder baseline)
            no_show_rate = 12.5 
            noshow_card = {
                "title": "No-Show Rate",
                "value": f"{no_show_rate}%",
                "change": "-2.4%",
                "trend": "down",
                "icon": "UserX",
                "color": "red"
            }

            # 5. Patients Targeted (Outbound Reach)
            patients_contact = {
                "title": "Patients Targeted",
                "value": f"{total_outbound_attempts:,}",
                "change": "Active",
                "trend": "up",
                "icon": "Users",
                "color": "blue"
            }
            
            # 6. Call Answer Rate (%)
            total_processed = base_qs.count()
            ans_rate = (connected_calls / total_processed * 100) if total_processed > 0 else 0
            call_rate = {
                "title": "Call Answer Rate",
                "value": f"{ans_rate:.0f}%",
                "change": "Live",
                "trend": "up",
                "icon": "Phone",
                "color": "green"
            }

            # 7. Escalated Issues
            total_escalation = EscalationModel.objects.filter(
                patient__hospital=user_id,
                escalated_at__date__gte=start_of_this_month,
                escalated_at__date__lte=today
            ).count()
            
            escalation_card = {
                "title": "Escalated Issues",
                "value": str(total_escalation),
                "change": "Live",
                "trend": "up",
                "icon": "AlertTriangle",
                "color": "orange"
            }

            # 8. Revenue Influenced (₹)
            revenue_influenced = booked * 650
            revenue_card = {
                "title": "Revenue Influenced",
                "value": f"₹{revenue_influenced:,}",
                "change": "Live",
                "trend": "up",
                "icon": "TrendingUp",
                "color": "emerald"
            }

            return Response({
                "interactions": interactions_card,
                "resolution": resolution_card,
                "conversion": conversion_card,
                "noshow": noshow_card,
                "patients": patients_contact,
                "ans_rate": call_rate,
                "escalation": escalation_card,
                "revenue": revenue_card
            })

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class Patientengagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            if start_date_str and end_date_str:
                today = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_of_week = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                today = timezone.now().date()
                start_of_week = today - timedelta(days=90)

            # === 1. Contacts per Day (Raw Attempts) ===
            contacts_qs = (
                Outbound_Hospital.objects.filter(
                    patient_id__hospital=user_id,
                    started_at__date__gte=start_of_week, 
                    started_at__date__lte=today
                )
                .annotate(day=TruncDate('started_at'))
                .values('day')
                .annotate(contacts=Count('id'))
            )
            
            delta = (today - start_of_week).days
            day_map = {}
            # Use unique date keys and year-aware labels for large ranges
            for i in range(delta + 1):
                d = start_of_week + timedelta(days=i)
                label_fmt = "%b %d" if delta < 365 else "%b %d, %y"
                day_map[d.strftime("%Y-%m-%d")] = {"label": d.strftime(label_fmt), "count": 0}
            
            for item in contacts_qs:
                if item['day']:
                    day_key = item['day'].strftime("%Y-%m-%d")
                    if day_key in day_map:
                        day_map[day_key]["count"] += item['contacts']

            contacts_data = [{"date": v["label"], "contacts": v["count"]} for k, v in sorted(day_map.items())]
            if len(contacts_data) > 31:
                # Sample the data to avoid overcrowding the chart
                step = len(contacts_data) // 31
                contacts_data = contacts_data[::step]

            # === 2. Call Answer Data (Processed Feedback) ===
            filtered_queryset = CallFeedbackModel.objects.annotate(
                effective_called_at=Coalesce('called_at', 'created_at')
            ).filter(
                effective_called_at__date__gte=start_of_week, 
                effective_called_at__date__lte=today,
                patient__hospital=user_id
            )

            total_calls = filtered_queryset.count()
            
            from django.db.models import FloatField
            from django.db.models.functions import Cast
            result = filtered_queryset.aggregate(
                total_calls=Count('id'),
                avg_call_duration=Avg(Cast('call_duration', FloatField()))
            )

            total_calls_all_period = result['total_calls']
            average_call_duration = result['avg_call_duration'] or 0
            meta_data={"total_calls_all_period":total_calls_all_period,"average_call_duration":np.round(float(average_call_duration),2)}
            
            answered_calls = filtered_queryset.filter(call_status='connected').count()
            not_answered = total_calls - answered_calls

            call_answer_data = [{"name": "Answered", "value": np.round((answered_calls / total_calls) * 100, 2) if total_calls else 0, "color": "#10B981"}, {"name": "Not Answered", "value": np.round((not_answered / total_calls) * 100, 2) if total_calls else 0, "color": "#EF4444"}]

            # === 3. Feedback Data ===
            feedback_qs = filtered_queryset.values('call_outcome', 'remarks', 'patient__patient_name')

            label_map = {
                "positive": "Positive",
                "negative": "Negative",
                "no_feedback": "Neutral",
                "escalated": "Escalated",
            }

            feedback_dict = {label: [] for label in label_map.values()}

            for item in feedback_qs:
                label = label_map.get(item['call_outcome'], item['call_outcome'].capitalize())
                remarks = item['remarks']
                if remarks:
                    # Filter out junk
                    junk = ["call details only", "no conversation", "no meaningful"]
                    if any(j in remarks.lower() for j in junk): continue
                    
                    feedback_dict.setdefault(label, []).append({
                        "patient_name": item['patient__patient_name'],
                        "remark": remarks
                    })

            feedback_data = [{"feedback": label, "count": len(entries), "remarks": entries} for label, entries in feedback_dict.items()]

            return Response({
                "contactsData": contacts_data,
                "callAnswerData": call_answer_data,
                "feedbackData": feedback_data,
                "metadata":meta_data,
                "weekStart": start_of_week.strftime("%Y-%m-%d"),
                "weekEnd": today.strftime("%Y-%m-%d")
            })

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class CommunityEngagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())

            # 4 full weeks including this one (from oldest to newest)
            week_starts = [start_of_this_week - timedelta(weeks=i) for i in reversed(range(4))]

            # Step 1: Get actual data from DB
            weekly_qs = (
                CommunityEngagementModel.objects
                .filter(created_at__date__gte=week_starts[0],patient__hospital=user_id)
                .annotate(week=TruncWeek('created_at'))
                .values('week')
                .annotate(added=Count('id'))
            )

            # Step 2: Create a default map with 0s
            week_map = OrderedDict()
            for week_start in week_starts:
                week_map[week_start] = 0

            # Step 3: Fill in values from DB results
            for row in weekly_qs:
                week_start_date = row['week'].date()
                if week_start_date in week_map:
                    week_map[week_start_date] = row['added']

            # Step 4: Format for frontend
            community_growth_data = []
            for i, (week_start, added) in enumerate(week_map.items()):
                community_growth_data.append({
                    "date": f"Week {i + 1}",
                    "added": added
                })

            # === Department-wise engagement ===
            dept_qs = (
                CommunityEngagementModel.objects
                .filter(created_at__date__gte=week_starts[0],patient__hospital=user_id)
                .exclude(department__isnull=True)
                .exclude(department__exact='')
                .values('department')
                .annotate(engagement=Count('id'))
                .order_by('-engagement')
            )

            department_engagement_data = [
                {
                    "department": row["department"],
                    "engagement": row["engagement"]
                }
                for row in dept_qs
            ]
            total_engagements = CommunityEngagementModel.objects.filter(patient__hospital=user_id).count()
            total_posts = CommunityEngagementModel.objects.filter(engagement_type='post',patient__hospital=user_id).count()

            avg_engagement_per_post = total_engagements / total_posts if total_posts > 0 else 0
            today = timezone.localdate()
            start_of_month = today.replace(day=1)

            # Find patients whose first engagement was this month
            first_engagements = CommunityEngagementModel.objects.filter(patient__hospital=user_id).values('patient') \
                .annotate(first_engagement=Min('engagement_date')) \
                .filter(first_engagement__gte=start_of_month)

            new_members_this_month = first_engagements.count()
            start_of_week = today - timedelta(days=today.weekday())

# Filter posts made this week
            posts_this_week = CommunityEngagementModel.objects.filter(
                engagement_type='post',
                engagement_date__gte=start_of_week,
                engagement_date__lte=today,
                patient__hospital=user_id
            ).count()
            meta_data={
                "community_members":total_engagements,
                "post_week":posts_this_week,
                "avg_engagement/post":avg_engagement_per_post,
                "new_members":new_members_this_month
            }
            
            connected_and_added = CallFeedbackModel.objects.filter(
                call_status='connected',
                community_added=True,
                patient__hospital=user_id
            ).values_list('patient', flat=True).distinct().count()
            connected = CallFeedbackModel.objects.filter(
                call_status='connected',
                patient__hospital=user_id
                
            ).values_list('patient', flat=True).distinct().count()
            conversion_rate = (connected_and_added / connected) * 100 if connected else 0
            total_engaged_users = CommunityEngagementModel.objects.filter(patient__hospital=user_id).values('patient').distinct().count()

            poll_participants = CommunityEngagementModel.objects.filter(
                engagement_type='poll_participation',patient__hospital=user_id
            ).values('patient').distinct().count()

            poll_participation_rate = (poll_participants / total_engaged_users) * 100 if total_engaged_users else 0
            one_week_ago = timezone.localdate() - timedelta(days=7)

            weekly_active_users = CommunityEngagementModel.objects.filter(
                engagement_date__gte=one_week_ago,
                patient__hospital=user_id
            ).values('patient').distinct().count()
            metrics={
                "conversion_rate":np.round(conversion_rate,2),
                "poll_participation_rate":np.round(poll_participation_rate,2),
                "weekly_active_users":weekly_active_users
            }
            return Response({
                "communityGrowthData": community_growth_data,
                "departmentEngagementData": department_engagement_data,
                "metadata":meta_data,
                "metrics":metrics
            })

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})
class RevisitAnalyticsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id

            visits = (
                Patient_date_model.objects
                .filter(hospital_id=hospital_id)
                .annotate(visit_day=TruncDate('date'))
                .values('mobile_no', 'department', 'date')
                .distinct()
            )

            visit_map = defaultdict(set)
            for visit in visits:
                key = (visit['mobile_no'], visit['department'])
                visit_map[key].add(visit['date'])

            color_map = {
                'Cardiology': '#EF4444',
                'Orthopedics': '#F59E0B',
                'Pediatrics': '#10B981',
                'General Medicine': '#3B82F6',
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

                        if local_date.year == current_year and local_date.month == current_month:
                            repeat_visits_this_month += 1

                    # Gap calculation
                    for i in range(1, len(sorted_days)):
                        gap = (sorted_days[i] - sorted_days[i - 1]).days
                        all_gaps.append(gap)
                        if 0 <= gap <= 7:
                            time_gap_counter['0-7 days'] += 1
                        elif 8 <= gap <= 30:
                            time_gap_counter['8-30 days'] += 1
                        elif 31 <= gap <= 90:
                            time_gap_counter['1-3 months'] += 1
                        elif 91 <= gap <= 180:
                            time_gap_counter['3-6 months'] += 1
                        elif gap > 180:
                            time_gap_counter['6+ months'] += 1

            total_revisits = sum(department_counter.values())

            department_data = []
            for dept, count in department_counter.items():
                percentage = (count / total_revisits) * 100 if total_revisits > 0 else 0
                department_data.append({
                    'name': dept,
                    'value': count,
                    'percentage': round(percentage, 2),
                    'color': color_map.get(dept, '#6B7280')
                })

            monthly_data = []
            for year, month in sorted(monthly_counter.keys()):
                label = f"{month_abbr[month]} {str(year)[2:]}"
                monthly_data.append({
                    'month': label,
                    'revisits': monthly_counter[(year, month)]
                })

            gap_order = ['0-7 days', '8-30 days', '1-3 months', '3-6 months', '6+ months']
            time_gap_data = [
                {'gap': label, 'count': time_gap_counter.get(label, 0)}
                for label in gap_order
            ]

            average_gap = round(sum(all_gaps) / len(all_gaps),2) if all_gaps else None

            return Response({
                'department_data': department_data,
                'monthly_trend': monthly_data,
                'time_gap_distribution': time_gap_data,
                'average_revisit_gap': average_gap,
                'repeat_visits_this_month': repeat_visits_this_month
            })

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class EscalationEngagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            now = timezone.now()
            
            # === 1. Department-wise Escalation Counts ===
            dept_qs = (
            EscalationModel.objects
            .filter(patient__hospital=user_id)
            .exclude(department__isnull=True)
            .exclude(department__exact='')
            .values(
                'department',
                'issue_description',
                'patient__patient_name'
            )
        )
            from collections import defaultdict

            dept_dict = defaultdict(list)

            for item in dept_qs:
                if item['issue_description']:  # skip empty issues
                    dept_dict[item['department']].append({
                        "patient_name": item['patient__patient_name'],
                        "issue": item['issue_description']
                    })

            department_escalation_data = [
                {
                    "department": dept,
                    "count": len(issues),
                    "issues": issues
                }
                for dept, issues in sorted(
                    dept_dict.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
            ]

            # === 2. Resolution Status Counts ===
            status_colors = {
                "resolved": "#10B981",
                "in-progress": "#F59E0B",
                "pending": "#EF4444"
            }

            status_qs = (
                EscalationModel.objects.filter(patient__hospital=user_id)
                .values('status')
                .annotate(value=Count('id'))
            )
            for row in status_qs:
                print(row['status'])
            dict_present={
                "Pending":False,
                "In-progress":False,
                "Resolved":False    
            }
            total_sum=0
            for row in status_qs:
                dict_present[row['status'].replace("_", " ").title()]=True
                total_sum+=row['value']
            
            not_present=[]
            for k,v in dict_present.items():
                if v==False:
                    not_present.append({"name":k,"value":0,"color":status_colors[k.lower()]})
            resolution_status_data = [
                {
                    "name": row['status'].replace("_", " ").title(),
                    "value": np.round((row['value']/total_sum)*100,2) if total_sum!=0 else 0,
                    "color": status_colors.get(row['status'], "#6B7280")  # default gray
                }
                for row in status_qs
            ]
            resolution_status_data.extend(not_present)

            # === 3. Recent Escalations ===
            recent_qs = (
                EscalationModel.objects.filter(patient__hospital=user_id)
                .select_related('patient')
                .order_by('-escalated_at')[:5]
            )

            recent_escalations = []
            for i, esc in enumerate(recent_qs, start=1):
                recent_escalations.append({
                    "id": esc.id,
                    "patient": esc.patient.patient_name,
                    "issue": esc.issue_description,
                    "status": esc.status,
                    "time": naturaltime(esc.escalated_at)
                })
            total_escalations = EscalationModel.objects.filter(patient__hospital=user_id).count()
            avg_resolution_time = EscalationModel.objects.filter(
                status='resolved',
                resolved_at__isnull=False,
                patient__hospital=user_id
            ).annotate(
                resolution_duration=ExpressionWrapper(
                    F('resolved_at') - F('escalated_at'),
                    output_field=DurationField()
                )
            ).aggregate(
                avg_time=Avg('resolution_duration')
            )['avg_time']

            # Step 2: Convert to Days
            avg_resolution_days = np.round(avg_resolution_time.total_seconds() / 86400, 2) if avg_resolution_time else 0
            

            resolved_today = EscalationModel.objects.filter(
                status='resolved',
                resolved_at__date=now,
                patient__hospital=user_id
            ).count()
            
            meta_data={
                "total_escalations":total_escalations,
                "avg_resolution_time":avg_resolution_days,
                "resolved_today":resolved_today

            }
            return Response({
                "departmentEscalationData": department_escalation_data,
                "resolutionStatusData": resolution_status_data,
                "recentEscalations": recent_escalations,
                "metadata":meta_data
            })

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

class validateToken(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            role=request.role
            name=request.email
            
            
            return Response({"role":role,"name":name,"error":0,"msg":"Success"})
        except Exception as e:
            return Response({"role":"","name":"","error":1,"msg":str(e)})
class upload_files_log(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            role = request.role
            if role != 'user':
                return Response({"msg": "Only hospital users can view upload logs", "error": 1})
            logs = HospitalUploadLog.objects.filter(hospital_id=user_id).order_by('-uploaded_at')
            data = [
                {
                    "id": str(log.id),
                    "file_names": log.file_names,
                    "status": log.status,
                    "uploaded_at": log.uploaded_at,
                    "message": log.message
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
            user_id = request.user_id
            role = request.role
            print("role-->",role)
            if role != 'Admin':
                return Response({"msg": "Only Admin can view all hospitals ", "error": 1})
            hospitals = Hospital_model.objects.all().values('id', 'name').distinct()
            data = list(hospitals)
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
class PdfView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            obj=Hospital_user_model.objects.get(id=request.user_id)
            user_id = obj.hospital.id
            hospital_name=obj.hospital.name
            role = request.role
            start_date=inputdict['start_date']
            end_date=inputdict['end_date']

            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            print("start_data---->",start_date)
            print("end_date--->",end_date)
            start_str = f"{get_ordinal(start_date.day)} {start_date.strftime('%B %Y')}"
            end_str = f"{get_ordinal(end_date.day)} {end_date.strftime('%B %Y')}"
            dict_obj={}
            report_type = inputdict.get('report_type', 'detailed')
            
            # Key Outcome Placeholders (Table 1)
            dict_obj['{{total_interactions}}'] = interactions_card['value']
            dict_obj['{{avg_resolution}}'] = resolution_card['value']
            dict_obj['{{conversion_rate}}'] = conversion_card['value']
            dict_obj['{{no_show_rate}}'] = noshow_card['value']
            
            # Financial & ROI (Tables 3A, 3B, 3C)
            # Assuming these placeholders exist in the template
            dict_obj['{{rev_influenced}}'] = revenue_card['value']
            
            if report_type == 'only_metrics':
                # Clear text-heavy placeholders if we are in 'Only Metrics' mode
                dict_obj['{{summary}}'] = ""
                dict_obj['{{analysis}}'] = ""
                dict_obj['{{recommendations}}'] = ""
                template_filename = "Amor-Hospitals-Metrics-Only.docx"
            else:
                template_filename = "Amor-Hospitals-May-2025-PTS-Report.docx"
            
            sheet_path = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
            docx_path = os.path.join(sheet_path, template_filename)
            
            if not os.path.exists(docx_path):
                docx_path = os.path.join(sheet_path, "Amor-Hospitals-May-2025-PTS-Report.docx")
            # Generate UUID
            unique_id = uuid.uuid4()

            # Get current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Build filename
            folder_path=os.path.join(sheet_path,"files")
            os.makedirs(folder_path,exist_ok=True)
            filename = f"report_{user_id}_{unique_id}_{timestamp}.docx"
            file_path=os.path.join(folder_path,filename)
            replace_placeholders_in_docx_preserving_styles(docx_path,file_path,dict_obj)
            resp= FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=filename,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                
            )
            resp['Content-Disposition'] = f'attachment; filename="{filename}"'
            return resp
        except Exception as e:
            return Response({"error":1,"errorMsg":str(e)})
class TextView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            text=inputdict['text']
            user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            print("user_id-->",user_id)
            hospital_name=request.email
            print("hospital_name-->",hospital_name)
            role = request.role
            
            # Get the Hospital_model instance
            hospital = Hospital_model.objects.get(id=user_id)
            TextModel.objects.update_or_create(hospital=hospital, text=text)
            return Response({"error":0,"msg":"Success"})
        except Exception as e:
            return Response({"error":1,"msg":str(e)})
    def get(self,request):
        try:
            user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            hospital_name=request.email
            role = request.role
            hospital = Hospital_model.objects.get(id=user_id)
            text=TextModel.objects.get(hospital=hospital)
            print("text---->",text)
            return Response({"error":0,"msg":"Success","data":text.text})
        except Exception as e:
            return Response({"error":1,"msg":str(e)})
class tab_access(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            user_id= request.user_id
            hospital_name=request.email
            role = request.role
            if role!='user':
                return Response({"msg": "Invalid user", "error": 0})
            user = Hospital_user_model.objects.get(id=user_id)
            return Response({
            "patient_engagement": user.patient_engagement,
            "community_engagement": user.community_egagement,  # typo retained for now
            "revisit_engagement": user.revisit_engagement,
            "escalation_engagement": user.escalation_engagement,
            "calllog_engagement": user.calllog_engagement,
            "upload_engagement": user.upload_engagement,
            "pdf_engagement":user.pdf_engagement
            })          
            
        except Exception as e:
            return Response({"error":1,"msg":str(e)})

class ROIMetrics(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            call_direction = request.query_params.get('call_direction', 'outbound')
            
            # Select Baseline from attempts
            if call_direction == 'inbound':
                attempts = Inbound_Hospital.objects.filter(hospital_id=user_id)
                feedback_qs = CallFeedbackModel_inbound.objects.filter(patient__hospital_id=user_id)
            else:
                attempts = Outbound_Hospital.objects.filter(patient_id__hospital=user_id)
                feedback_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id)

            if start_date and end_date:
                attempts = attempts.filter(started_at__date__range=[start_date, end_date])
                feedback_qs = feedback_qs.filter(called_at__date__range=[start_date, end_date])
            
            interaction_count = attempts.count()
            booked_count = feedback_qs.filter(call_outcome='positive').count()
            
            # Table 3A: Revenue Generated
            avg_rev_per_appt = 650 
            total_revenue_influenced = booked_count * avg_rev_per_appt
            
            # Table 3B: Revenue Leakage Prevented
            missed_calls = attempts.filter(calling_process='not_connected').count()
            missed_call_recovery = missed_calls * 0.42 * avg_rev_per_appt # 42% is target conversion
            
            # Table 3C: Operational Cost Efficiency
            total_duration_min = feedback_qs.aggregate(total=Sum(Cast('call_duration', FloatField())))['total'] or 0
            staff_hours_saved = np.round(total_duration_min / 60, 1)
            fte_freed = np.round(staff_hours_saved / 100, 2)
            cost_efficiency = np.round(fte_freed * 40000, 0)
            
            return Response({
                "roi_financial": [
                    {"name": "Interactions", "value": interaction_count, "unit": ""},
                    {"name": "Appointments Booked", "value": booked_count, "unit": ""},
                    {"name": "Revenue Influenced", "value": total_revenue_influenced, "unit": "₹"},
                    {"name": "Leakage Prevented", "value": np.round(missed_call_recovery, 0), "unit": "₹"}
                ],
                "roi_efficiency": [
                    {"name": "Staff Hours Saved", "value": staff_hours_saved, "unit": "hrs"},
                    {"name": "Equivalent FTE Freed", "value": fte_freed, "unit": "FTE"},
                    {"name": "Cost Efficiency Value", "value": cost_efficiency, "unit": "₹"}
                ],
                "error": 0
            })
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

class DepartmentAnalytics(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            call_direction = request.query_params.get('call_direction', 'outbound')
            
            if call_direction == 'inbound':
                dept_qs = Inbound_Hospital.objects.filter(hospital_id=user_id).values('department').annotate(interactions=Count('id'))
                feedback_qs = CallFeedbackModel_inbound.objects.filter(patient__hospital_id=user_id)
                dept_field = 'department'
            else:
                dept_qs = Patient_model.objects.filter(hospital_id=user_id).values('department').annotate(interactions=Count('id'))
                feedback_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id)
                dept_field = 'patient__department'

            feedback_stats = feedback_qs.values(dept_field).annotate(
                bookings=Count('id', filter=Q(call_outcome='positive')),
            )
            
            feedback_map = {item[dept_field]: item for item in feedback_stats}
            
            formatted_data = []
            for item in dept_qs:
                dept = item.get('department') or item.get('patient__department') or "General"
                stats = feedback_map.get(dept, {'bookings': 0})
                
                interactions = item.get('interactions') or item.get('count') or 0
                bookings = stats['bookings']
                conv_rate = (bookings / interactions * 100) if interactions > 0 else 0
                
                formatted_data.append({
                    "department": dept,
                    "interactions": interactions,
                    "bookings": bookings,
                    "conversion": f"{conv_rate:.1f}%",
                    "revenue": bookings * 650,
                    "csat": 4.7
                })
                
            return Response({
                "department_table": formatted_data,
                "top_intents": [
                    {"intent": "Appointment Booking", "value": 45},
                    {"intent": "Lab Report Queries", "value": 25},
                    {"intent": "Follow-up / Revisit", "value": 15},
                    {"intent": "Prescription Queries", "value": 10},
                    {"intent": "Emergency Routing", "value": 5}
                ],
                "error": 0
            })
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

class CampaignView(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            campaigns = Campaign.objects.filter(hospital_id=hospital_id).order_by('-created_at')

            data = []
            for c in campaigns:
                total_calls = c.calls.count()
                connected = c.calls.filter(calling_process='connected').count()

                data.append({
                    "id": str(c.id),
                    "name": c.name,
                    "template_type": c.template_type,
                    "purpose": c.purpose,
                    "status": c.status,
                    "created_at": c.created_at,
                    "stats": {
                        "total_calls": total_calls,
                        "connected_calls": connected
                    }
                })
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

    def post(self, request):
        try:
            hospital_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            payload = request.data
            template_type = payload.get('template_type', 'custom')
            purpose = payload.get('purpose', '')

            if template_type == 'health_package':
                purpose = f"Introduce new health package: {payload.get('package_name')}. Includes: {payload.get('discount_details', 'Standard tests')}"
            elif template_type == 'new_facility':
                purpose = f"Announce new facility: {payload.get('facility_name')}. Available now."
            elif template_type == 'discounted_product':
                purpose = f"Offer discount on: {payload.get('package_name')}. Discount: {payload.get('discount_details')}"

            campaign = Campaign.objects.create(
                hospital_id=hospital_id,
                name=payload.get('name'),
                template_type=template_type,
                package_name=payload.get('package_name'),
                facility_name=payload.get('facility_name'),
                discount_details=payload.get('discount_details'),
                purpose=purpose,
                unconnected_only=payload.get('unconnected_only', False)
            )
            return Response({"msg": "Campaign created", "id": str(campaign.id), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

    def delete(self, request):
        try:
            campaign_id = request.query_params.get('id')
            Campaign.objects.filter(id=campaign_id).delete()
            return Response({"msg": "Campaign deleted", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class doctor_login_view(APIView):
    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            try:
                doctor = Doctor_model.objects.get(email=email)
            except Doctor_model.DoesNotExist:
                return Response({"msg": "Doctor not found", "error": 1})
            
            if check_password(password, doctor.password_hash):
                token = create_token({
                    "user_id": str(doctor.id),
                    "email": doctor.email,
                    "role": "Doctor",
                    "hospital_id": str(doctor.hospital.id)
                })
                return Response({
                    "msg": "Doctor login successful",
                    "token": token,
                    "doctor_name": doctor.name,
                    "hospital_name": doctor.hospital.name,
                    "error": 0
                })
            else:
                return Response({"msg": "Invalid password", "error": 1})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class MediVoiceSessionView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self, request):
        try:
            doctor_id = request.user_id
            doctor = Doctor_model.objects.get(id=doctor_id)
            data = request.data
            
            session = MediVoiceSession.objects.create(
                doctor=doctor,
                patient_name=data.get('patientName'),
                patient_mobile=data.get('patientMobile'),
                patient_email=data.get('patientEmail'),
                overall_summary=data.get('overallSummary'),
                meta_data=data.get('metaData')
            )
            
            transcriptions = data.get('transcriptions', [])
            for t in transcriptions:
                MediVoiceTranscription.objects.create(
                    session=session,
                    speaker=t.get('speaker'),
                    text=t.get('text'),
                    timestamp=t.get('timestamp', 0.0)
                )
            
            return Response({"msg": "Session saved", "session_id": str(session.id), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

    def get(self, request):
        try:
            doctor_id = request.user_id
            sessions = MediVoiceSession.objects.filter(doctor_id=doctor_id).order_by('-created_at')
            data = []
            for s in sessions:
                data.append({
                    "id": str(s.id),
                    "patientName": s.patient_name,
                    "patientMobile": s.patient_mobile,
                    "createdAt": s.created_at,
                    "transcriptionCount": s.transcriptions.count()
                })
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class DoctorTranscriptionView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            doctor_id = request.query_params.get('doctor_id')
            
            query = MediVoiceSession.objects.filter(doctor__hospital_id=user_id)
            if doctor_id:
                query = query.filter(doctor_id=doctor_id)
            
            sessions = query.select_related('doctor').order_by('-created_at')
            data = []
            for s in sessions:
                transcriptions = s.transcriptions.all().order_by('timestamp')
                data.append({
                    "id": str(s.id),
                    "doctorName": s.doctor.name,
                    "doctorDepartment": s.doctor.department,
                    "patientName": s.patient_name,
                    "patientMobile": s.patient_mobile,
                    "overallSummary": s.overall_summary,
                    "metaData": s.meta_data,
                    "createdAt": s.created_at,
                    "transcriptions": [
                        {
                            "speaker": t.speaker,
                            "text": t.text,
                            "timestamp": t.timestamp
                        } for t in transcriptions
                    ]
                })
            
            doctors = Doctor_model.objects.filter(hospital_id=user_id).values('id', 'name', 'department')
            
            return Response({
                "sessions": data,
                "doctors": list(doctors),
                "error": 0
            })
        except Exception as e:
            return Response({"msg": str(e), "error": 1})






        
    
        
