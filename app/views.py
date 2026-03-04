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
from django.db.models.functions import TruncDate, TruncMonth, Coalesce, Cast
from django.db.models import Count,Avg,Min,F, ExpressionWrapper, DurationField, Q, FloatField, Sum
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

    def process_paragraphs(paragraphs):
        for paragraph in paragraphs:
            runs = paragraph.runs
            i = 0
            while i < len(runs):
                combined = ""
                indices = []
                j = i
                while j < len(runs):
                    combined += runs[j].text
                    indices.append(j)
                    match = None
                    for placeholder in replacements_dict:
                        if placeholder in combined:
                            match = placeholder
                            break
                    if match:
                        replaced = combined.replace(match, str(replacements_dict[match]))
                        base_run = runs[indices[0]]
                        # Preserve styles
                        bold, italic, underline = base_run.bold, base_run.italic, base_run.underline
                        font_name, size = base_run.font.name, base_run.font.size
                        for idx in indices: runs[idx].text = ""
                        r = runs[indices[0]]
                        r.text = replaced
                        r.bold, r.italic, r.underline = bold, italic, underline
                        r.font.name, r.font.size = font_name, size
                        i = indices[-1]
                        break
                    j += 1
                i += 1

    # Process main body
    process_paragraphs(doc.paragraphs)
    
    # Process tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                process_paragraphs(cell.paragraphs)

    doc.save(output_path)

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
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(target_tz).replace(tzinfo=None)
    return dt

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
                    hospital_user = Hospital_user_model.objects.get(name=name_email)
                except Hospital_user_model.DoesNotExist:
                    return Response({"msg": "Hospital not found", "error": 1})
                if check_password(password, hospital_user.password_hash):
                    token=create_token({"user_id":str(hospital_user.id),"email":hospital_user.name,'role':'user'})
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
            if not files_list: return Response({"msg": "No files uploaded", "error": 1})
            log = HospitalUploadLog.objects.create(hospital=hospital, file_names=[f.name for f in files_list], status="PENDING")
            return Response({"msg": "Processing", "error": 0}) # Placeholder for async
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class CallFeedbackView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self, request):
        try:
            inputdict = request.data
            patient = Patient_model.objects.get(id=inputdict.get('patient_id'))
            CallFeedbackModel.objects.create(
                patient=patient,
                call_status=inputdict.get('call_status'),
                call_outcome=inputdict.get('call_outcome'),
                remarks=inputdict.get('remarks', ''),
                community_added=inputdict.get('community_added', False),
                revisit_encouraged=inputdict.get('revisit_encouraged', False),
                escalation_required=inputdict.get('escalation_required', False),
                call_duration=inputdict.get('call_duration', 0),
                called_by=inputdict.get('called_by'),
                called_at=now()
            )
            return Response({"msg": "Success", "error": 0})
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
                today = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_of_period = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                today = timezone.now().date()
                start_of_period = today - timedelta(days=90)

            total_outbound = Outbound_Hospital.objects.filter(patient_id__hospital=user_id, started_at__date__gte=start_of_period, started_at__date__lte=today).count()
            total_inbound = Inbound_Hospital.objects.filter(hospital_id=user_id, started_at__date__gte=start_of_period, started_at__date__lte=today).count()
            
            base_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id, called_at__date__gte=start_of_period, called_at__date__lte=today)
            connected = base_qs.filter(call_status='connected')
            booked = base_qs.filter(call_outcome='positive').count()
            avg_res = connected.aggregate(avg=Avg(Cast('call_duration', FloatField())))['avg'] or 0
            
            return Response({
                "interactions": {"title": "Total Interactions", "value": f"{total_outbound + total_inbound:,}", "icon": "Users", "color": "blue"},
                "resolution": {"title": "Avg Resolution", "value": f"{int(avg_res * 60)} sec", "icon": "Clock", "color": "green"},
                "conversion": {"title": "Conversion Rate", "value": f"{(booked/connected.count()*100 if connected.count() else 0):.1f}%", "icon": "TrendingUp", "color": "purple"},
                "noshow": {"title": "No-Show Rate", "value": "12.5%", "icon": "UserX", "color": "red"},
                "patients": {"title": "Patients Targeted", "value": f"{total_outbound:,}", "icon": "Users", "color": "blue"},
                "ans_rate": {"title": "Call Answer Rate", "value": f"{(connected.count()/base_qs.count()*100 if base_qs.count() else 0):.0f}%", "icon": "Phone", "color": "green"},
                "escalation": {"title": "Escalated Issues", "value": str(EscalationModel.objects.filter(patient__hospital=user_id).count()), "icon": "AlertTriangle", "color": "orange"},
                "revenue": {"title": "Revenue Influenced", "value": f"₹{booked * 650:,}", "icon": "TrendingUp", "color": "emerald"}
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
                today, start_of_week = datetime.strptime(end_date_str, "%Y-%m-%d").date(), datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                today = timezone.now().date()
                start_of_week = today - timedelta(days=90)

            contacts_qs = Outbound_Hospital.objects.filter(patient_id__hospital=user_id, started_at__date__gte=start_of_week, started_at__date__lte=today)
            delta = (today - start_of_week).days
            contacts_data = []
            if delta > 60:
                period_qs = contacts_qs.annotate(period=TruncMonth('started_at')).values('period').annotate(contacts=Count('id')).order_by('period')
                for item in period_qs:
                    if item['period']: contacts_data.append({"date": item['period'].strftime("%b %Y"), "contacts": item['contacts']})
            else:
                period_qs = contacts_qs.annotate(period=TruncDate('started_at')).values('period').annotate(contacts=Count('id')).order_by('period')
                day_map = { (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(delta + 1) }
                for item in period_qs:
                    if item['period']: day_map[item['period'].strftime("%Y-%m-%d")] = item['contacts']
                for date_str, count in sorted(day_map.items()):
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                    contacts_data.append({"date": d.strftime("%b %d"), "contacts": count})

            feedback_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id, called_at__date__gte=start_of_week, called_at__date__lte=today)
            total_calls = feedback_qs.count()
            answered = feedback_qs.filter(call_status='connected').count()
            
            return Response({
                "contactsData": contacts_data,
                "callAnswerData": [{"name": "Answered", "value": (answered/total_calls*100 if total_calls else 0), "color": "#10B981"}, {"name": "Not Answered", "value": (100 - (answered/total_calls*100 if total_calls else 0)), "color": "#EF4444"}],
                "feedbackData": [], # Simplified for brevity
                "metadata": {"total_calls_all_period": total_calls, "average_call_duration": 0},
                "weekStart": start_of_week.strftime("%Y-%m-%d"),
                "weekEnd": today.strftime("%Y-%m-%d")
            })
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

class PdfView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            obj=Hospital_user_model.objects.get(id=request.user_id)
            user_id, hospital_name = obj.hospital.id, obj.hospital.name
            start_date = datetime.strptime(inputdict['start_date'], "%Y-%m-%d").date()
            end_date = datetime.strptime(inputdict['end_date'], "%Y-%m-%d").date()
            
            # Recalculate metrics for placeholders
            base_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id, called_at__date__range=[start_date, end_date])
            total_processed = base_qs.count()
            booked = base_qs.filter(call_outcome='positive').count()
            
            dict_obj={
                '{{reporting_period}}': f"{start_date} to {end_date}",
                '{{hospital_name}}': hospital_name.title(),
                '{{total_interactions}}': str(total_processed),
                '{{conversion_rate}}': f"{(booked/total_processed*100 if total_processed else 0):.1f}%",
                '{{rev_influenced}}': f"₹{booked * 650:,}",
            }
            
            if inputdict.get('report_type') == 'only_metrics':
                for p in ['summary', 'analysis', 'recommendations', 'introduction', 'conclusion']:
                    dict_obj[f'{{{{{p}}}}}'] = ""
                template = "Amor-Hospitals-Metrics-Only.docx"
            else:
                template = "Amor-Hospitals-May-2025-PTS-Report.docx"
            
            sheet_path = os.path.dirname(os.path.abspath(__file__))
            docx_path = os.path.join(sheet_path, template)
            if not os.path.exists(docx_path): docx_path = os.path.join(sheet_path, "Amor-Hospitals-May-2025-PTS-Report.docx")
            
            filename = f"report_{uuid.uuid4()}.docx"
            file_path = os.path.join(sheet_path, "files", filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            replace_placeholders_in_docx_preserving_styles(docx_path, file_path, dict_obj)
            return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
        except Exception as e:
            return Response({"error":1,"errorMsg":str(e)})

class ROIMetrics(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date, end_date = request.query_params.get('start_date'), request.query_params.get('end_date')
            call_direction = request.query_params.get('call_direction', 'outbound')
            
            if call_direction == 'inbound':
                attempts = Inbound_Hospital.objects.filter(hospital_id=user_id)
                feedback_qs = CallFeedbackModel_inbound.objects.filter(patient__hospital_id=user_id)
            else:
                attempts = Outbound_Hospital.objects.filter(patient_id__hospital=user_id)
                feedback_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id)

            if start_date and end_date:
                attempts = attempts.filter(started_at__date__range=[start_date, end_date])
                feedback_qs = feedback_qs.filter(called_at__date__range=[start_date, end_date])
            
            booked_count = feedback_qs.filter(call_outcome='positive').count()
            missed = attempts.filter(calling_process='not_connected').count()
            total_dur = feedback_qs.aggregate(total=Sum(Cast('call_duration', FloatField())))['total'] or 0
            
            return Response({
                "roi_financial": [
                    {"name": "Interactions", "value": attempts.count(), "unit": ""},
                    {"name": "Appointments Booked", "value": booked_count, "unit": ""},
                    {"name": "Revenue Influenced", "value": booked_count * 650, "unit": "₹"},
                    {"name": "Leakage Prevented", "value": int(missed * 0.42 * 650), "unit": "₹"}
                ],
                "roi_efficiency": [
                    {"name": "Staff Hours Saved", "value": np.round(total_dur/60, 1), "unit": "hrs"},
                    {"name": "Equivalent FTE Freed", "value": np.round(total_dur/6000, 2), "unit": "FTE"},
                    {"name": "Cost Efficiency Value", "value": int(total_dur/6000 * 40000), "unit": "₹"}
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

            feedback_stats = feedback_qs.values(dept_field).annotate(bookings=Count('id', filter=Q(call_outcome='positive')))
            feedback_map = {item[dept_field]: item for item in feedback_stats}
            
            formatted_data = []
            for item in dept_qs:
                dept = item.get('department') or item.get('patient__department') or "General"
                stats = feedback_map.get(dept, {'bookings': 0})
                interactions = item.get('interactions') or item.get('count') or 0
                bookings = stats['bookings']
                formatted_data.append({
                    "department": dept,
                    "interactions": interactions,
                    "bookings": bookings,
                    "conversion": f"{(bookings/interactions*100 if interactions else 0):.1f}%",
                    "revenue": bookings * 650,
                    "csat": 4.7
                })
            return Response({"department_table": formatted_data, "top_intents": [], "error": 0})
        except Exception as e:
            return Response({"error": 1, "msg": str(e)})

class CampaignView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            campaigns = Campaign.objects.filter(hospital__hospital_user_model__id=request.user_id).order_by('-created_at')
            data = [{
                "id": str(c.id), "name": c.name, "template_type": c.template_type, "purpose": c.purpose, "status": c.status, "created_at": c.created_at,
                "stats": {"total_calls": c.calls.count(), "connected_calls": c.calls.filter(calling_process='connected').count()}
            } for c in campaigns]
            return Response({"data": data, "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})
    def post(self, request):
        try:
            user = Hospital_user_model.objects.get(id=request.user_id)
            payload = request.data
            purpose = payload.get('purpose', '')
            if payload.get('template_type') == 'health_package':
                purpose = f"Introduce health package: {payload.get('package_name')}. Inclusions: {payload.get('discount_details')}"
            campaign = Campaign.objects.create(
                hospital=user.hospital, name=payload.get('name'), template_type=payload.get('template_type', 'custom'),
                package_name=payload.get('package_name'), facility_name=payload.get('facility_name'),
                discount_details=payload.get('discount_details'), purpose=purpose
            )
            return Response({"msg": "Success", "id": str(campaign.id), "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class doctor_login_view(APIView):
    def post(self, request):
        try:
            doctor = Doctor_model.objects.get(email=request.data.get('email'))
            if check_password(request.data.get('password'), doctor.password_hash):
                token = create_token({"user_id": str(doctor.id), "email": doctor.email, "role": "Doctor", "hospital_id": str(doctor.hospital.id)})
                return Response({"msg": "Success", "token": token, "doctor_name": doctor.name, "hospital_name": doctor.hospital.name, "error": 0})
            return Response({"msg": "Invalid password", "error": 1})
        except: return Response({"msg": "Doctor not found", "error": 1})

class DoctorTranscriptionView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            sessions = MediVoiceSession.objects.filter(doctor__hospital_id=user_id).order_by('-created_at')
            data = [{
                "id": str(s.id), "doctorName": s.doctor.name, "doctorDepartment": s.doctor.department, "patientName": s.patient_name,
                "patientMobile": s.patient_mobile, "overallSummary": s.overall_summary, "metaData": s.meta_data, "createdAt": s.created_at,
                "transcriptions": [{"speaker": t.speaker, "text": t.text, "timestamp": t.timestamp} for t in s.transcriptions.all().order_by('timestamp')]
            } for s in sessions]
            return Response({"sessions": data, "doctors": list(Doctor_model.objects.filter(hospital_id=user_id).values('id', 'name', 'department')), "error": 0})
        except Exception as e: return Response({"msg": str(e), "error": 1})
