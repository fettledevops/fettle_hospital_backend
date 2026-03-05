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
                        val = str(replacements_dict[match]) if replacements_dict[match] is not None else ""
                        replaced = combined.replace(match, val)
                        base_run = runs[indices[0]]
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
    # Process headers/footers
    for section in doc.sections:
        process_paragraphs(section.header.paragraphs)
        process_paragraphs(section.footer.paragraphs)

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

class patient_insert_view(APIView):
    authentication_classes = [JWTAuthentication,]
    def post(self, request):
        try:
            hospital_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            hospital = Hospital_model.objects.get(id=hospital_id)
            files_list = request.FILES.getlist("files")
            if not files_list: return Response({"msg": "No files uploaded", "error": 1})
            log = HospitalUploadLog.objects.create(hospital=hospital, file_names=[f.name for f in files_list], status="PENDING")
            return Response({"msg": "Processing", "error": 0}) 
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

class EscalationfeedbackView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            patient = Patient_model.objects.get(id=inputdict.get('patient_id'))
            EscalationModel.objects.create(
                patient=patient,
                issue_description=inputdict.get('issue_description'),
                department=inputdict.get('department')
            )
            return Response({"msg":"Success","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class UpdateEscalation(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            escalation = EscalationModel.objects.get(id=inputdict['id'])
            escalation.status = inputdict['status']
            escalation.resolution_notes = inputdict['resolution_notes']
            if inputdict['status'] == 'resolved':
                escalation.resolved_at = timezone.now()
            escalation.save()
            return Response({"msg":"Success","error":0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})

class fetchpatients(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = request.user_id
            role = request.role
            if role == 'user':
                hospital_ids = [Hospital_user_model.objects.get(id=user_id).hospital.id]
            else:
                hospital_ids = list(Hospital_model.objects.values_list('id', flat=True))
            
            raw_params = request.query_params.get('call_status','').strip().lower()
            filter_params = set([s.strip().lower() for s in raw_params.split(',') if s.strip()])
            
            queryset = Patient_model.objects.select_related('hospital').filter(hospital_id__in=hospital_ids).order_by('mobile_no', 'uploaded_at')
            patients = list(queryset)
            
            out_calls = Outbound_Hospital.objects.filter(patient_id__hospital_id__in=hospital_ids).values('patient_id', 'calling_process', 'status')
            lookup = {str(o['patient_id']): (o['calling_process'] if o['calling_process'] != 'not_happened' else ('queued' if o['status'] == 'queued' else 'not_connected')) for o in out_calls}
            
            h_text_map = {t.hospital_id: t.text for t in TextModel.objects.filter(hospital_id__in=hospital_ids)}
            status_colors = {"connected": "#28A745", "not_connected": "#DC3545", "queued": "#FFC107", "in_progress": "#3B82F6"}
            
            data = []
            for p in patients:
                cp = lookup.get(str(p.id), "not_connected")
                if not filter_params or cp.lower() in filter_params:
                    data.append({
                        "id": p.id, "patient_name": p.patient_name, "mobile_no": p.mobile_no, "department": p.department, "hospital_name": p.hospital.name,
                        "whatsapp_link": f"https://web.whatsapp.com/send?phone={p.mobile_no}&text={h_text_map.get(p.hospital.id, '')}",
                        "calling_progress": cp, "color": status_colors.get(cp, "#6C757D")
                    })
            return Response({"data": data, "count": len(data), "error": 0})
        except Exception as e: return Response({"msg": str(e), "error": 1})

class KPISummary(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            if start_date_str and end_date_str:
                today, start_of_period = datetime.strptime(end_date_str, "%Y-%m-%d").date(), datetime.strptime(start_date_str, "%Y-%m-%d").date()
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
        except Exception as e: return Response({"msg": str(e), "error": 1})

class Patientengagement(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str, end_date_str = request.query_params.get('start_date'), request.query_params.get('end_date')
            if start_date_str and end_date_str:
                today, start_of_period = datetime.strptime(end_date_str, "%Y-%m-%d").date(), datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                today, start_of_period = timezone.now().date(), timezone.now().date() - timedelta(days=90)

            contacts_qs = Outbound_Hospital.objects.filter(patient_id__hospital=user_id, started_at__date__gte=start_of_period, started_at__date__lte=today)
            delta = (today - start_of_period).days
            contacts_data = []
            if delta > 60:
                period_qs = contacts_qs.annotate(period=TruncMonth('started_at')).values('period').annotate(contacts=Count('id')).order_by('period')
                for item in period_qs:
                    if item['period']: contacts_data.append({"date": item['period'].strftime("%b %Y"), "contacts": item['contacts']})
            else:
                period_qs = contacts_qs.annotate(period=TruncDate('started_at')).values('period').annotate(contacts=Count('id')).order_by('period')
                day_map = { (start_of_period + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(delta + 1) }
                for item in period_qs:
                    if item['period']: day_map[item['period'].strftime("%Y-%m-%d")] = item['contacts']
                for date_str, count in sorted(day_map.items()):
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                    contacts_data.append({"date": d.strftime("%b %d"), "contacts": count})

            feedback_qs = CallFeedbackModel.objects.filter(patient__hospital=user_id, called_at__date__gte=start_of_period, called_at__date__lte=today)
            total_calls = feedback_qs.count()
            answered = feedback_qs.filter(call_status='connected').count()
            
            return Response({
                "contactsData": contacts_data,
                "callAnswerData": [{"name": "Answered", "value": np.round((answered/total_calls*100 if total_calls else 0), 2), "color": "#10B981"}, {"name": "Not Answered", "value": np.round(100 - (answered/total_calls*100 if total_calls else 0), 2), "color": "#EF4444"}],
                "feedbackData": [], "metadata": {"total_calls_all_period": total_calls, "average_call_duration": 0},
                "weekStart": start_of_period.strftime("%Y-%m-%d"), "weekEnd": today.strftime("%Y-%m-%d")
            })
        except Exception as e: return Response({"error": 1, "msg": str(e)})

class PdfView(APIView):
    authentication_classes = [JWTAuthentication]
    def post(self,request):
        try:
            inputdict=request.data
            obj=Hospital_user_model.objects.get(id=request.user_id)
            user_id, hospital_name = obj.hospital.id, obj.hospital.name
            start_date = datetime.strptime(inputdict['start_date'], "%Y-%m-%d").date()
            end_date = datetime.strptime(inputdict['end_date'], "%Y-%m-%d").date()
            
            start_str = f"{get_ordinal(start_date.day)} {start_date.strftime('%B %Y')}"
            end_str = f"{get_ordinal(end_date.day)} {end_date.strftime('%B %Y')}"
            
            # 1. Interaction Data
            connected_data = CallFeedbackModel.objects.filter(called_at__date__range=[start_date, end_date], patient__hospital=user_id).distinct().count()
            call_cc = CallFeedbackModel.objects.filter(patient__hospital=user_id, called_at__date__range=[start_date, end_date], call_status='connected').values('patient').distinct().count()
            
            # 2. Community Data
            community_members = CallFeedbackModel.objects.filter(called_at__date__range=[start_date, end_date], community_added=True, patient__hospital=user_id).distinct().count()
            poll_participants = CommunityEngagementModel.objects.filter(created_at__date__range=[start_date, end_date], engagement_type='poll_participation', patient__hospital=user_id).values('patient').distinct().count()
            
            # 3. Escalations
            total_escalations = EscalationModel.objects.filter(escalated_at__date__range=[start_date, end_date], patient__hospital=user_id).count()
            
            # 4. Revisits
            q_visits = Patient_date_model.objects.filter(date__range=(start_date, end_date), hospital=user_id)
            unique_patients = q_visits.values('hospital', 'mobile_no').distinct().count()
            total_revisits = q_visits.values('hospital', 'mobile_no').annotate(vc=Count('id')).filter(visit_count__gt=1).count()
            
            revisit_rate = np.round((total_revisits / unique_patients * 100), 2) if unique_patients else 0
            call_answer_rate = np.round((call_cc / connected_data * 100), 2) if connected_data else 0
            comm_conv_rate = np.round((community_members / connected_data * 100), 2) if connected_data else 0
            
            dict_obj={
                '{{reporting_period}}': f"{start_str} to {end_str}", '{{hospital_name}}': hospital_name.title(),
                '{{call_patients}}': connected_data, '{{call_p}}': connected_data,
                '{{call_answer_rate}}': call_answer_rate, '{{calla_c}}': call_answer_rate,
                '{{community_added}}': community_members, '{{com_c}}': community_members,
                '{{community_conversion_rate}}': comm_conv_rate, '{{coma_c}}': comm_conv_rate,
                '{{poll_number}}': poll_participants, '{{escalation_number}}': total_escalations, '{{ess_c}}': total_escalations,
                '{{revisit_conversion_rate}}': revisit_rate, '{{reva_c}}': revisit_rate,
                '{{revisit_number}}': total_revisits, '{{rev_c}}': total_revisits,
                '{{call_connected}}': call_cc, '{{call_c}}': call_cc
            }
            
            report_type = inputdict.get('report_type', 'detailed')
            if report_type == 'only_metrics':
                for p in ['summary', 'analysis', 'recommendations', 'introduction', 'conclusion', 'observation', 'patient_feedback_summary', 'executive_summary']:
                    dict_obj[f'{{{{{p}}}}}'] = " "
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
        except Exception as e: return Response({"error":1,"errorMsg":str(e)})

class ROIMetrics(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            sd, ed = request.query_params.get('start_date'), request.query_params.get('end_date')
            cd = request.query_params.get('call_direction', 'outbound')
            attempts = Inbound_Hospital.objects.filter(hospital_id=user_id) if cd == 'inbound' else Outbound_Hospital.objects.filter(patient_id__hospital=user_id)
            fb_qs = CallFeedbackModel_inbound.objects.filter(patient__hospital_id=user_id) if cd == 'inbound' else CallFeedbackModel.objects.filter(patient__hospital=user_id)
            if sd and ed:
                attempts = attempts.filter(started_at__date__range=[sd, ed])
                fb_qs = fb_qs.filter(called_at__date__range=[sd, ed])
            booked = fb_qs.filter(call_outcome='positive').count()
            missed = attempts.filter(calling_process='not_connected').count()
            tdur = fb_qs.aggregate(t=Sum(Cast('call_duration', FloatField())))['t'] or 0
            return Response({"roi_financial": [{"name": "Interactions", "value": attempts.count(), "unit": ""}, {"name": "Appointments Booked", "value": booked, "unit": ""}, {"name": "Revenue Influenced", "value": booked * 650, "unit": "₹"}, {"name": "Leakage Prevented", "value": int(missed * 0.42 * 650), "unit": "₹"}], "roi_efficiency": [{"name": "Staff Hours Saved", "value": np.round(tdur/60, 1), "unit": "hrs"}, {"name": "Equivalent FTE Freed", "value": np.round(tdur/6000, 2), "unit": "FTE"}, {"name": "Cost Efficiency Value", "value": int(tdur/6000 * 40000), "unit": "₹"}], "error": 0})
        except Exception as e: return Response({"error": 1, "msg": str(e)})

class CampaignView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            campaigns = Campaign.objects.filter(hospital__hospital_user_model__id=request.user_id).order_by('-created_at')
            data = [{"id": str(c.id), "name": c.name, "status": c.status, "created_at": c.created_at, "stats": {"total_calls": c.calls.count(), "connected_calls": c.calls.filter(calling_process='connected').count()}} for c in campaigns]
            return Response({"data": data, "error": 0})
        except Exception as e: return Response({"msg": str(e), "error": 1})
    def post(self, request):
        try:
            user = Hospital_user_model.objects.get(id=request.user_id)
            c = Campaign.objects.create(hospital=user.hospital, name=request.data.get('name'), purpose=request.data.get('purpose', ''))
            return Response({"msg": "Success", "id": str(c.id), "error": 0})
        except Exception as e: return Response({"msg": str(e), "error": 1})

class DoctorTranscriptionView(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        try:
            user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            sessions = MediVoiceSession.objects.filter(doctor__hospital_id=user_id).order_by('-created_at')
            data = [{"id": str(s.id), "doctorName": s.doctor.name, "patientName": s.patient_name, "overallSummary": s.overall_summary, "createdAt": s.created_at} for s in sessions]
            return Response({"sessions": data, "error": 0})
        except Exception as e: return Response({"msg": str(e), "error": 1})

class tab_access(APIView):
    authentication_classes = [JWTAuthentication]
    def get(self,request):
        try:
            user = Hospital_user_model.objects.get(id=request.user_id)
            return Response({"patient_engagement": user.patient_engagement, "community_engagement": user.community_egagement, "revisit_engagement": user.revisit_engagement, "escalation_engagement": user.escalation_engagement, "calllog_engagement": user.calllog_engagement, "upload_engagement": user.upload_engagement, "pdf_engagement":user.pdf_engagement})
        except Exception as e: return Response({"error":1,"msg":str(e)})
