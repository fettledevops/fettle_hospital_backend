from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Admin_model,Hospital_model,Patient_model,HospitalUploadLog,CallFeedbackModel,CommunityEngagementModel,EscalationModel,Patient_date_model,TextModel,Hospital_user_model,Outbound_Hospital,Outbound_assistant
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
# Create your views here.
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
                    "phone_number": "+91"+e.patient.mobile_no,
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
            print("role--->",role)
            if role == 'user':
                hospital_users=Hospital_user_model.objects.get(id=admin_id)
                if hospital_users.calllog_engagement:
                    hospital_ids.append(hospital_users.hospital.id)
                else:
                    return Response({"msg": "Invalid user", "error": 0})
            else:
                restricted_hospital=list(
                    Hospital_user_model.objects.filter(
                        calllog_engagement=True
                    ).values_list('hospital_id', flat=True).distinct()
                )
                all_hospital=list(
                    Hospital_user_model.objects.filter(
                        
                    ).values_list('hospital_id', flat=True).distinct()
                )
                hospital_ids.extend(list(set(all_hospital) - set(restricted_hospital)))
                
                
            limit_param = request.query_params.get('limit', '').strip().lower()
            raw_params = request.query_params.get('call_status','').strip().lower()
            start_date_str = request.query_params.get('start_date', '').strip()
            end_date_str = request.query_params.get('end_date', '').strip()
            unconnected_only = request.query_params.get('unconnected_only', 'false').strip().lower() == 'true'
            
            filter_params = set([s.strip().lower() for s in raw_params.split(',') if s.strip()])
            
            queryset = Patient_model.objects.select_related('hospital').filter(
                hospital_id__in=hospital_ids
            )

            if start_date_str and end_date_str:
                queryset = queryset.filter(uploaded_at__date__range=[start_date_str, end_date_str])

            queryset = queryset.order_by('mobile_no', 'uploaded_at')

            outbound_assistant_ids=Outbound_assistant.objects.filter(hospital_id__in=hospital_ids)
            Outbound_Hospital_patients=list(Outbound_Hospital.objects.filter(assistant_id__in=outbound_assistant_ids).select_related("patient_id__hospital"))
            lookup = {}

            for o in Outbound_Hospital_patients:
                # print(o.patient)
                key = (
                    (o.patient_id.patient_name or '').strip().lower(),
                    (o.patient_id.mobile_no or '').strip().lower(),
                    (o.patient_id.hospital.name or '').strip().lower(),     # adjust if field name differs
                )
                if o.calling_process=='not_happened':
                    if o.status=='in-progress':
                        lookup[key]='in_progress'
                    elif o.status=='queued':
                        lookup[key]='queued'
                    else:
                        lookup[key]='not_connected'
                else:
                    lookup[key] = o.calling_process or "N/A"
            # print("lookup-->",lookup)
            # If 'limit' is not given, empty, or 'all' → fetch all
            if limit_param in ['', 'all']:
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
                "in_progress": "#007BFF",
            }
            gray_color="#6C757D"
            for p in patients:
                key = (
                    (p.patient_name or '').strip().lower(),
                    (p.mobile_no or '').strip().lower(),
                    (p.hospital.name or '').strip().lower(),
                )
                p.calling_progress = lookup.get(key, "N/A")
                p.hex_color=status_color_hex.get(p.calling_progress,gray_color)
                
            patient_data=[]
            print(filter_params)
            
            for p in patients:
                if len(filter_params)==0 or p.calling_progress.strip().lower() in filter_params:
                    patient_data.append({
                        "id": p.id,
                        "patient_name": p.patient_name,
                        "mobile_no": p.mobile_no,
                        "department": p.department,
                        "hospital_name": p.hospital.name,
                        "whatsapp_link":f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={hospital_text_map.get(p.hospital.id, '')}",
                        "calling_progress":p.calling_progress,
                        "color":p.hex_color,
                        # "uploaded_at":p.uploaded_at
                        "uploaded_at": make_naive(p.uploaded_at, tz_name='Asia/Kolkata'),
                        
                    })
               

            
            

            return Response({"data": patient_data,"count":len(patient_data), "error": 0})

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
                    "mobile_no": "+91"+e.patient.mobile_no,
                    
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
                    "mobile_no": "+91"+e.patient.mobile_no,
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
                    "mobile_no": "+91"+e.patient.mobile_no,
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
                # for trend, we look at an equal period before
                delta = (end_date - start_of_this_month).days
                start_of_prev_month = start_of_this_month - timedelta(days=delta if delta > 0 else 30)
                today = end_date
            else:
                today = timezone.now().date()
                start_of_this_month = today - timedelta(days=90)
                start_of_prev_month = start_of_this_month - timedelta(days=90)

            base_qs = CallFeedbackModel.objects.annotate(
                effective_called_at=Coalesce('called_at', 'created_at')
            ).filter(patient__hospital=user_id)

            # === Total calls ===
            contact_this_month_count = base_qs.filter(
                effective_called_at__date__gte=start_of_this_month,
                effective_called_at__date__lte=today,
            ).count()

            contact_prev_month_count = base_qs.filter(
                effective_called_at__date__gte=start_of_prev_month,
                effective_called_at__date__lt=start_of_this_month,
            ).count()

            # === Connected calls ===
            connected_this_month = base_qs.filter(
                call_status='connected',
                effective_called_at__date__gte=start_of_this_month,
                effective_called_at__date__lte=today,
            )

            connected_prev_month = base_qs.filter(
                call_status='connected',
                effective_called_at__date__gte=start_of_prev_month,
                effective_called_at__date__lt=start_of_this_month,
            )

            connected_this_month_count = connected_this_month.count()
            connected_prev_month_count = connected_prev_month.count()

            # === KPI 1: Total Patients Contacted ===
            if contact_prev_month_count > 0:
                contact_change = ((contact_this_month_count - contact_prev_month_count) / contact_prev_month_count) * 100
                contact_trend = "up" if contact_change > 0 else "down"
            else:
                contact_change = 100.0 if contact_this_month_count > 0 else 0.0
                contact_trend = "up" if contact_this_month_count > 0 else "flat"
            
            total_contacts = CallFeedbackModel.objects.filter(patient__hospital=user_id).distinct().count()
            patients_contact = {
                "title": "Total Patients Contacted",
                "value": f"{total_contacts:,}",
                "change": f"{contact_change:+.0f}%",
                "trend": contact_trend,
                "icon": "Users",
                "color": "blue"
            }

            # === KPI 2: Call Answer Rate ===
            connect_this_month_rate = (connected_this_month_count / contact_this_month_count * 100) if contact_this_month_count > 0 else 0
            connect_prev_month_rate = (connected_prev_month_count / contact_prev_month_count * 100) if contact_prev_month_count > 0 else 0

            if connect_prev_month_rate > 0:
                connect_change = connect_this_month_rate - connect_prev_month_rate
                connect_trend = "up" if connect_change > 0 else "down"
            else:
                connect_change = connect_this_month_rate
                connect_trend = "up" if connect_this_month_rate > 0 else "flat"
            
            try:
                connected_total = CallFeedbackModel.objects.filter(patient__hospital=user_id, call_status='connected').values('patient').distinct().count()
                connected_people_rate = np.round((connected_total / total_contacts) * 100, 2) if total_contacts > 0 else 0
            except Exception:
                connected_people_rate = 0

            call_rate = {
                "title": "Call Answer Rate",
                "value": f"{connected_people_rate:.0f}%",
                "change": f"{connect_change:+.0f}%",
                "trend": connect_trend,
                "icon": "Phone",
                "color": "green"
            }

            # === KPI 3: Community Conversion ===
            community_this_month = connected_this_month.filter(community_added=True).count()
            community_prev_month = connected_prev_month.filter(community_added=True).count()

            community_this_month_rate = (community_this_month / connected_this_month_count * 100) if connected_this_month_count > 0 else 0
            community_prev_month_rate = (community_prev_month / connected_prev_month_count * 100) if connected_prev_month_count > 0 else 0

            if community_prev_month_rate > 0:
                community_change = community_this_month_rate - community_prev_month_rate
                community_trend = "up" if community_change > 0 else "down"
            else:
                community_change = community_this_month_rate
                community_trend = "up" if community_this_month_rate > 0 else "flat"
            
            try:
                community_total = CallFeedbackModel.objects.filter(community_added=True, patient__hospital=user_id).distinct().count()
                community_members_rate = np.round((community_total / total_contacts) * 100, 2) if total_contacts > 0 else 0
            except Exception:
                community_members_rate = 0

            community_card = {
                "title": "Community Conversion",
                "value": f"{community_members_rate:.0f}%",
                "change": f"{community_change:+.0f}%",
                "trend": community_trend,
                "icon": "MessageCircle",
                "color": "purple"
            }

            # === KPI 4: Escalated Issues ===
            escalated_this_month = EscalationModel.objects.filter(
                patient__hospital=user_id,
                escalated_at__date__gte=start_of_this_month,
                escalated_at__date__lte=today,
            ).count()

            escalated_prev_month = EscalationModel.objects.filter(
                patient__hospital=user_id,
                escalated_at__date__gte=start_of_prev_month,
                escalated_at__date__lt=start_of_this_month,
            ).count()

            if escalated_prev_month > 0:
                escalated_change = ((escalated_this_month - escalated_prev_month) / escalated_prev_month) * 100
                escalated_trend = "up" if escalated_change > 0 else "down"
            else:
                escalated_change = 100.0 if escalated_this_month > 0 else 0.0
                escalated_trend = "up" if escalated_this_month > 0 else "flat"
            
            total_escalation = EscalationModel.objects.filter(patient__hospital=user_id).count()
            escalation_card = {
                "title": "Escalated Issues",
                "value": str(total_escalation),
                "change": f"{escalated_change:+.0f}%",
                "trend": escalated_trend,
                "icon": "AlertTriangle",
                "color": "orange"
            }

            return Response({
                "total_patients_contacted": patients_contact,
                "call_answer_rate": call_rate,
                "community_conversion": community_card,
                "escalated_issues": escalation_card
            })

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


from django.db.models.functions import Coalesce

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
                start_of_week = today - timedelta(days=90)  # default 90 days window

            print("start_of_week--->",start_of_week,"today--->",today)
            # === 1. Contacts per Day ===
            contacts_qs = (
                CallFeedbackModel.objects
                .annotate(effective_called_at=Coalesce('called_at', 'created_at'))
                .filter(effective_called_at__date__gte=start_of_week, effective_called_at__date__lte=today, patient__hospital=user_id)
                .annotate(day=TruncDate('effective_called_at'))
                .values('day')
                .annotate(contacts=Count('id'))
            )
            

            # Initialize map for the window
            delta_days = (today - start_of_week).days
            day_map={}
            for i in range(delta_days + 1):
                date_w=(start_of_week + timedelta(days=i))
                day_map[date_w.strftime("%b %d")]=0
            
            for item in contacts_qs:
                day_label = item['day'].strftime("%b %d")
                if day_label in day_map:
                    day_map[day_label] += item['contacts']

            contacts_data = [{"date": day, "contacts": count} for day, count in day_map.items()]

            # === 2. Call Answer Data ===
            print("user_id--->",user_id,"start_of_week--->",start_of_week)
            # Apply filter
            filtered_queryset = CallFeedbackModel.objects.annotate(
                effective_called_at=Coalesce('called_at', 'created_at')
            ).filter(
                effective_called_at__date__gte=start_of_week, effective_called_at__date__lte=today, patient__hospital=user_id
            )

            # Total calls
            total_calls = filtered_queryset.count()
            print("total_calls --->", total_calls)

            # Aggregate on same filtered data
            from django.db.models import FloatField
            from django.db.models.functions import Cast
            result = filtered_queryset.aggregate(
                total_calls=Count('id'),
                avg_call_duration=Avg(Cast('call_duration', FloatField()))
            )

            total_calls_all_period = result['total_calls'] or 0
            average_call_duration = result['avg_call_duration']
            meta_data={"total_calls_all_period":total_calls_all_period,"average_call_duration":np.round(average_call_duration,2) if average_call_duration is not None else 0}
            
            answered_calls = filtered_queryset.filter(call_status='connected').count()
            print("answered_calls--->",answered_calls)
            not_answered = total_calls - answered_calls

            call_answer_data = [{"name": "Answered", "value": np.round((answered_calls / total_calls) * 100, 2) if total_calls else 0, "color": "#10B981"}, {"name": "Not Answered", "value": np.round((not_answered / total_calls) * 100, 2) if total_calls else 0, "color": "#EF4444"}]

            # === 3. Feedback Data ===
            feedback_qs = (
                filtered_queryset
                .values(
                    'call_outcome',
                    'remarks',
                    "effective_called_at",
                    'patient__patient_name',
                    'patient__mobile_no'
                )
            )

            label_map = {
                "positive": "Positive",
                "negative": "Negative",
                "no_feedback": "Neutral",
                "escalated": "Escalated",
            }

            feedback_dict = {label: [] for label in label_map.values()}

            for item in feedback_qs:
                label = label_map.get(
                    item['call_outcome'],
                    item['call_outcome'].capitalize()
                )

                remarks = item['remarks']
                if remarks:
                    # Filter out junk remarks
                    junk_patterns = [
                        "call details only include timestamp",
                        "no conversation or outcome recorded",
                        "no conversation recorded",
                        "no meaningful feedback",
                        "call connected but no conversation"
                    ]
                    if any(pattern in remarks.lower() for pattern in junk_patterns):
                        continue

                    feedback_dict.setdefault(label, []).append({
                        "patient_name": item['patient__patient_name'],
                        "remark": remarks,
                        "mobile_no": "+91"+item['patient__mobile_no'],
                        "feedback_at": make_naive(item['effective_called_at'], tz_name='Asia/Kolkata')
                    })

            feedback_data = [
                {
                    "feedback": label,
                    "count": len(entries),
                    "remarks": entries
                }
                for label, entries in feedback_dict.items()
            ]

            # === Final response ===
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

            # 12 full weeks including this one (from oldest to newest)
            week_starts = [start_of_this_week - timedelta(weeks=i) for i in reversed(range(12))]

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
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            visits_query = Patient_date_model.objects.filter(hospital_id=hospital_id)

            if start_date_str and end_date_str:
                visits_query = visits_query.filter(date__date__range=[start_date_str, end_date_str])

            visits = (
                visits_query
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
                'Dental': '#8B5CF6',
                'Dermatology': '#EC4899',
                'Neurology': '#6366F1',
                'ENT': '#14B8A6',
                'Opthalmology': '#F97316',
                'Oncology': '#06B6D4',
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
                sorted_days = sorted(visit_days)
                
                # Count ALL visits in the monthly trend for a better overall activity view
                for date in sorted_days:
                    local_date = localtime(date)
                    month_key = (local_date.year, local_date.month)
                    monthly_counter[month_key] += 1

                if len(visit_days) > 1:
                    # Each visit after the first one is a "revisit" for the KPIs
                    revisit_count = len(sorted_days) - 1
                    department_counter[department] += revisit_count

                    for date in sorted_days[1:]:
                        local_date = localtime(date)
                        if local_date.year == current_year and local_date.month == current_month:
                            repeat_visits_this_month += 1

                    # Gap calculation: Time between consecutive visits
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
            # Use provided date range or default to 6 months
            if start_date_str and end_date_str:
                s_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                e_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
            else:
                e_dt = datetime.now()
                s_dt = e_dt - timedelta(days=180)

            # Generate all month keys in range
            curr = s_dt.replace(day=1)
            all_month_keys = []
            while curr <= e_dt:
                all_month_keys.append((curr.year, curr.month))
                # move to next month
                if curr.month == 12:
                    curr = curr.replace(year=curr.year + 1, month=1)
                else:
                    curr = curr.replace(month=curr.month + 1)

            for year, month in all_month_keys:
                label = f"{month_abbr[month]} {str(year)[2:]}"
                monthly_data.append({
                    'month': label,
                    'revisits': monthly_counter.get((year, month), 0)
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
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            if start_date_str and end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=90)

            # === 1. Department-wise Escalation Counts ===
            dept_qs = (
            EscalationModel.objects
            .filter(patient__hospital=user_id, escalated_at__date__gte=start_date, escalated_at__date__lte=end_date)
            .exclude(department__isnull=True)
            .exclude(department__exact='')
            .values(
                'department',
                'issue_description',
                'patient__patient_name',
                'patient__mobile_no'
            )
        )
            from collections import defaultdict

            dept_dict = defaultdict(list)

            for item in dept_qs:
                if item['issue_description']:  # skip empty issues
                    dept_dict[item['department']].append({
                        "patient_name": item['patient__patient_name'],
                        "issue": item['issue_description'],
                        "mobile_no": "+91"+item['patient__mobile_no']
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
                .order_by('-escalated_at')
            )

            recent_escalations = []
            for i, esc in enumerate(recent_qs, start=1):
                recent_escalations.append({
                    "id": esc.id,
                    "patient": esc.patient.patient_name,
                    "issue": esc.issue_description,
                    "status": esc.status,
                    "mobile_no": "+91"+esc.patient.mobile_no,
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

            # Step 2: Convert to days
            avg_resolution_days = np.round(avg_resolution_time.total_seconds() / (24 * 3600), 2) if avg_resolution_time else 0
            

            resolved_today = EscalationModel.objects.filter(
                status='resolved',
                resolved_at__date=now,
                patient__hospital=user_id
            ).count()

            return Response({
                "departmentEscalationData": department_escalation_data,
                "resolutionStatusData": resolution_status_data,
                "recentEscalations": recent_escalations,
                "metadata": {
                    "total_escalations": total_escalations,
                    "avg_resolution_time": avg_resolution_days,
                    "resolved_today": resolved_today
                }
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
            report_type = inputdict.get('report_type', 'detailed')

            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            if report_type == 'metrics':
                return self.generate_metrics_report(request, user_id, hospital_name, start_date, end_date)

            print("start_data---->",start_date)
            print("end_date--->",end_date)
            start_str = f"{get_ordinal(start_date.day)} {start_date.strftime('%B %Y')}"
            end_str = f"{get_ordinal(end_date.day)} {end_date.strftime('%B %Y')}"
            dict_obj={}
            dict_obj['{{reporting_period}}']=f"{start_str} to {end_str}"
            dict_obj['{{hospital_name}}']=hospital_name.title()
            print("user_id---->",user_id)
            # total_contacts=CallFeedbackModel.objects.filter(patient__hospital=user_id).distinct().count()
            connected_data = CallFeedbackModel.objects.filter(
                    
                    called_at__date__gte=start_date,
                    called_at__date__lte=end_date,
                    patient__hospital=user_id
                ).distinct().count()
            print("connected---->",connected_data)
            community_members=CallFeedbackModel.objects.filter(called_at__date__gte=start_date,called_at__date__lte=end_date,community_added=True,patient__hospital=user_id).distinct().count()
            poll_participants = CommunityEngagementModel.objects.filter(
                    created_at__date__gte=start_date,created_at__date__lte=end_date,engagement_type='poll_participation',patient__hospital=user_id
                ).values('patient').distinct().count()
            total_escalations = EscalationModel.objects.filter(escalated_at__date__gte=start_date,escalated_at__date__lte=end_date,patient__hospital=user_id).count()
            queryset = Patient_date_model.objects.filter(
                date__range=(start_date, end_date),
                hospital=user_id
            )

            # Count of unique (hospital, mobile_no) pairs
            unique_patients = queryset.values('hospital', 'mobile_no').distinct().count()

            # Group by hospital and mobile_no → find duplicates (more than 1 visit)
            revisit_groups = (
                queryset
                .values('hospital', 'mobile_no')
                .annotate(visit_count=Count('id'))
                .filter(visit_count__gt=1)
            )
            total_revisits = revisit_groups.count()

        
            revisit_conversion_rate = (total_revisits / unique_patients * 100) if unique_patients else 0

            
            try:
                call_cc=CallFeedbackModel.objects.filter(
                patient__hospital=user_id,
                called_at__date__gte=start_date,
                called_at__date__lte=end_date,
                call_status='connected'
            ).values('patient').distinct().count()
                connected_people_rate = np.round((call_cc/connected_data)*100,2)
            except Exception as e:
                connected_people_rate=0
            try:
                community_members_rate=community_members/connected_data
                community_members_rate=np.round(community_members_rate*100,2)
            except Exception as e:
                community_members_rate=0
            dict_obj['{{call_patients}}']=connected_data
            dict_obj['{{call_answer_rate}}']=connected_people_rate
            dict_obj['{{community_added}}']=community_members
            dict_obj['{{community_conversion_rate}}']=community_members_rate
            dict_obj['{{poll_number}}']=poll_participants
            dict_obj['{{escalation_number}}']=total_escalations
            dict_obj['{{revisit_conversion_rate}}']=revisit_conversion_rate
            dict_obj['{{revisit_number}}']=total_revisits
            dict_obj['{{call_connected}}']=call_cc
            
            
            dict_obj['{{call_p}}']=connected_data
            dict_obj['{{calla_c}}']=connected_people_rate
            dict_obj['{{com_c}}']=community_members
            dict_obj['{{coma_c}}']=community_members_rate
            dict_obj['{{poll_number}}']=poll_participants
            dict_obj['{{ess_c}}']=total_escalations
            dict_obj['{{reva_c}}']=revisit_conversion_rate
            dict_obj['{{rev_c}}']=total_revisits
            dict_obj['{{call_c}}']=call_cc
            
            sheet_path = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
            docx_path=os.path.join(sheet_path,"Amor-Hospitals-May-2025-PTS-Report.docx")
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

    def generate_metrics_report(self, request, user_id, hospital_name, start_date, end_date):
        try:
            from django.db.models import Count, Avg, Sum, FloatField, Q
            from django.db.models.functions import Cast, TruncDate
            
            # 1. KEY OUTCOMES
            base_qs = CallFeedbackModel.objects.filter(
                patient__hospital=user_id,
                called_at__date__gte=start_date,
                called_at__date__lte=end_date
            )
            
            total_outbound = base_qs.count()
            # Placeholder for inbound/chatbot as they might be in separate models
            total_inbound = Inbound_Hospital.objects.filter(
                started_at__date__gte=start_date,
                started_at__date__lte=end_date
            ).count() 
            chatbot_interactions = 0 
            total_interactions = total_inbound + total_outbound + chatbot_interactions
            
            # Calculate total duration for staff hours saved
            total_duration_min = base_qs.aggregate(
                total=Sum(Cast('call_duration', FloatField()))
            )['total'] or 0
            
            avg_call_res_sec = (total_duration_min / total_outbound * 60) if total_outbound else 0
            avg_call_res_sec = round(avg_call_res_sec, 1)
            
            # Appointments booked (assuming positive outcome)
            appointments_booked = base_qs.filter(call_outcome='positive').count()
            appointment_inquiry_calls = base_qs.count() 
            conv_rate = (appointments_booked / appointment_inquiry_calls * 100) if appointment_inquiry_calls else 0
            
            # 2. MEASURABLE GAINS
            avg_response_time = 22 # sec (placeholder)
            sla_compliance = 94 # % (placeholder)
            
            # 3. FINANCIAL & REVENUE INTELLIGENCE
            avg_revenue_per_appointment = 850 
            total_revenue_influenced = appointments_booked * avg_revenue_per_appointment
            
            # 4. OPERATIONAL COST EFFICIENCY
            staff_hours_saved = round(total_duration_min / 60, 1)
            equivalent_fte = round(staff_hours_saved / 100, 2)
            cost_per_staff = 40000
            cost_efficiency = round(equivalent_fte * cost_per_staff, 0)

            # 5. REVENUE EFFICIENCY METRICS
            rev_per_call = round(total_revenue_influenced / total_outbound, 0) if total_outbound else 0
            
            # 6. DEPARTMENT-WISE BREAKDOWN
            dept_data = base_qs.values('patient__department').annotate(
                interactions=Count('id'),
                bookings=Count('id', filter=Q(call_outcome='positive'))
            )
            
            # Create DOCX
            doc = Document()
            doc.add_heading(f'Key Performance Indicators - {hospital_name}', 0)
            doc.add_paragraph(f'Period: {start_date} to {end_date}')
            
            # 1. KEY OUTCOMES
            doc.add_heading('1. KEY OUTCOMES', level=1)
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'KPI'
            hdr_cells[1].text = 'Value'
            hdr_cells[2].text = 'Calculation Logic'
            
            kpi_list = [
                ('Total Patient Interactions Handled', f'{total_interactions}', 'Total inbound calls + outbound calls + chatbot interactions'),
                ('Avg Call Resolution Time (seconds)', f'{avg_call_res_sec} sec', '(Total duration of all completed calls) / (Total calls handled)'),
                ('Appointment Conversion Rate (%)', f'{round(conv_rate, 1)}%', '(Appointments booked / Total appointment inquiry calls) * 100'),
                ('Automated Follow-ups Completed', f'{total_outbound}', 'Count of successfully completed automated follow-up calls'),
            ]
            
            for kpi, val, logic in kpi_list:
                row_cells = table.add_row().cells
                row_cells[0].text = kpi
                row_cells[1].text = val
                row_cells[2].text = logic

            # 2. MEASURABLE GAINS
            doc.add_heading('2. MEASURABLE GAINS', level=1)
            table_gains = doc.add_table(rows=1, cols=3)
            table_gains.style = 'Table Grid'
            hdr_cells = table_gains.rows[0].cells
            hdr_cells[0].text = 'KPI'
            hdr_cells[1].text = 'Value'
            hdr_cells[2].text = 'Calculation Logic'
            
            gains_kpis = [
                ('Avg Response Time (seconds)', f'{avg_response_time} sec', '(Total wait time of all answered calls) / (Total calls answered)'),
                ('First Response SLA Compliance (%)', f'{sla_compliance}%', '(Calls answered within 30 sec / Total calls) * 100'),
            ]
            for kpi, val, logic in gains_kpis:
                row_cells = table_gains.add_row().cells
                row_cells[0].text = kpi
                row_cells[1].text = val
                row_cells[2].text = logic

            # 3. FINANCIAL & REVENUE INTELLIGENCE
            doc.add_heading('3. FINANCIAL & REVENUE INTELLIGENCE', level=1)
            table_fin = doc.add_table(rows=1, cols=3)
            table_fin.style = 'Table Grid'
            hdr_cells = table_fin.rows[0].cells
            hdr_cells[0].text = 'KPI'
            hdr_cells[1].text = 'Value'
            hdr_cells[2].text = 'Calculation Logic'
            
            fin_kpis = [
                ('Appointments Booked via AI', f'{appointments_booked}', 'Count of bookings created through AI system'),
                ('Avg Revenue per Appointment', f'₹{avg_revenue_per_appointment}', 'Standard hospital average'),
                ('Total Revenue Influenced', f'₹{total_revenue_influenced}', 'Appointments booked via AI * Avg revenue per appointment'),
            ]
            for kpi, val, logic in fin_kpis:
                row_cells = table_fin.add_row().cells
                row_cells[0].text = kpi
                row_cells[1].text = val
                row_cells[2].text = logic

            # 4. OPERATIONAL COST EFFICIENCY
            doc.add_heading('4. OPERATIONAL COST EFFICIENCY', level=1)
            table_ops = doc.add_table(rows=1, cols=3)
            table_ops.style = 'Table Grid'
            hdr_cells = table_ops.rows[0].cells
            hdr_cells[0].text = 'KPI'
            hdr_cells[1].text = 'Value'
            hdr_cells[2].text = 'Calculation Logic'
            
            ops_kpis = [
                ('Staff Hours Saved (hrs/month)', f'{staff_hours_saved} hrs', '(Total AI handled call duration in minutes / 60)'),
                ('Equivalent FTE Freed', f'{equivalent_fte} FTE', '(Staff hours saved / 100 hrs per staff per month)'),
                ('Cost Efficiency Value', f'₹{cost_efficiency}', '(FTE freed * Cost per staff per month)'),
            ]
            for kpi, val, logic in ops_kpis:
                row_cells = table_ops.add_row().cells
                row_cells[0].text = kpi
                row_cells[1].text = val
                row_cells[2].text = logic

            # 5. REVENUE EFFICIENCY METRICS
            doc.add_heading('5. REVENUE EFFICIENCY METRICS', level=1)
            table_rev_eff = doc.add_table(rows=1, cols=3)
            table_rev_eff.style = 'Table Grid'
            hdr_cells = table_rev_eff.rows[0].cells
            hdr_cells[0].text = 'KPI'
            hdr_cells[1].text = 'Value'
            hdr_cells[2].text = 'Calculation Logic'
            
            rev_eff_kpis = [
                ('Revenue per Call Handled', f'₹{rev_per_call}', '(Total revenue influenced / Total calls handled)'),
            ]
            for kpi, val, logic in rev_eff_kpis:
                row_cells = table_rev_eff.add_row().cells
                row_cells[0].text = kpi
                row_cells[1].text = val
                row_cells[2].text = logic

            # 6. DEPARTMENT-WISE PERFORMANCE BREAKDOWN section
            doc.add_heading('6. DEPARTMENT-WISE PERFORMANCE BREAKDOWN', level=1)
            table_dept = doc.add_table(rows=1, cols=4)
            table_dept.style = 'Table Grid'
            hdr_cells = table_dept.rows[0].cells
            hdr_cells[0].text = 'Department'
            hdr_cells[1].text = 'Interactions'
            hdr_cells[2].text = 'Bookings'
            hdr_cells[3].text = 'Conv. %'
            
            for dept in dept_data:
                row_cells = table_dept.add_row().cells
                row_cells[0].text = dept['patient__department'] or 'N/A'
                row_cells[1].text = str(dept['interactions'])
                row_cells[2].text = str(dept['bookings'])
                d_conv = (dept['bookings'] / dept['interactions'] * 100) if dept['interactions'] else 0
                row_cells[3].text = f'{round(d_conv, 1)}%'

            sheet_path = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
            folder_path = os.path.join(sheet_path, "files")
            os.makedirs(folder_path, exist_ok=True)
            filename = f"metrics_report_{user_id}_{uuid.uuid4()}.docx"
            file_path = os.path.join(folder_path, filename)
            doc.save(file_path)
            
            resp = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
            resp['Content-Disposition'] = f'attachment; filename="{filename}"'
            return resp
        except Exception as e:
            return Response({"error": 1, "errorMsg": str(e)})
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






        
    
        
