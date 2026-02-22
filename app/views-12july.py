from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Admin_model,Hospital_model,Patient_model,HospitalUploadLog,CallFeedbackModel,CommunityEngagementModel,EscalationModel
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
from django.db.models import Count,Avg,Min,F, ExpressionWrapper, DurationField
import calendar
from django.db.models.functions import TruncWeek
from collections import OrderedDict
from humanize import naturaltime
# Create your views here.
       
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
                    hospital = Hospital_model.objects.get(name=name_email)
                except Admin_model.DoesNotExist:
                    return Response({"msg": "Hospital not found", "error": 1})
                if check_password(password, hospital.password_hash):
                    print("hello")
                    token=create_token({"user_id":str(hospital.id),"email":hospital.name,'role':'user'})
                    print("token-->",token)
                    return Response({"msg": "Hospital login successful","token":str(token), "error": 0})
                else:
                    return Response({"msg": "Invalid password", "error": 1})
        except Exception as e:
            return Response({"msg":str(e),"error":1})
class patient_insert_view(APIView):
    authentication_classes = [JWTAuthentication,]
    def post(self,request):
        try:
            hospital_id=request.user_id
            hospital = Hospital_model.objects.get(id=hospital_id) 
            files_list=request.FILES.getlist("files")
            if not files_list:
                return Response({"msg": "No files uploaded", "error": 1})
            
            filenames = [file.name for file in files_list]
            log = HospitalUploadLog.objects.create(
                hospital=hospital,
                file_names=filenames,
                status="PENDING"
            )
            for file in files_list:
                if file.name.endswith('.csv'):
                    pass
                elif file.name.endswith('.xlsx'):
                    pass
                else:
                    log.status='FAILED'
                    log.message="Unsupported file type: Upload only .csv and .xlsx"
                    log.save()
                    return Response({"msg": f"Unsupported file type: Upload only .csv and .xlsx", "error": 1})
            file_keys=set()
            df_list=[]
            for file in files_list:
                required_columns = ["Sno.", "Patient Name", "Age", "Mobile No", "Departments"]
                if file.name.endswith('.xlsx'):
                    df=pd.read_excel(file)
                    df_list.append(df)
                elif file.name.endswith('.csv'):
                    df=pd.read_csv(file)
                    df_list.append(df)
                if not all(col in df.columns for col in required_columns):
                    log.status='FAILED'
                    log.message="Missing columns in {file.name}"
                    log.save()
                    return Response({"msg": f"Missing columns in {file.name}", "error": 1})
                print("file.name--->",file.name,df.head(2))
                file_keys.update(
                    ((row["Mobile No"]), row["Departments"])
                    for _, row in df.iterrows()
                )
            print("len---->",len(file_keys))
            existing_records = Patient_model.objects.filter(
                hospital=hospital,
                mobile_no__in=[k[0] for k in file_keys],
                department__in=[k[1] for k in file_keys]
            ).values_list('mobile_no', 'department')
            existing_keys = set((mobile_no, department) for mobile_no, department in existing_records)
            print("existing_keys---->",len(existing_keys))
            new_patients = []
            for i in df_list:
                for _, row in i.iterrows():
                    key = (str(row["Mobile No"]), row["Departments"])
                    if key not in existing_keys:
                        new_patients.append(Patient_model(
                            hospital=hospital,
                            serial_no=str(row.get("Sno.", "")),
                            patient_name=row["Patient Name"],
                            age=row.get("Age"),
                            mobile_no=key[0],
                            department=key[1],
                            uploaded_at=now()
                        ))
                        existing_keys.add(key)  # Avoid duplicate insert in same file
            
            # print(len())
            
            try:
                with transaction.atomic():
                    Patient_model.objects.bulk_create(new_patients)
                    log.status = 'SUCCESS'
                    log.message = 'files uploaded'
                    log.save()
            except Exception as e:
                log.status = 'FAILED'
                log.message = f'Upload failed during DB insert: {str(e)}'
                log.save()
                return Response({"msg": log.message, "error": 1})
            return Response({"msg":"working",'patients_count':len(new_patients),"error":0})
        except Exception as e:
            
            return Response({"msg":str(e),"error":1})

class CallFeedbackView(APIView):
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            admin_id = request.user_id
            role = request.role

            if role == 'user':
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
            called_at = parse_datetime(called_at)
            print(timezone.get_current_timezone())
            if timezone.is_naive(called_at):
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

            if role == 'user':
                return Response({"msg": "Invalid user", "error": 0})

            limit_param = request.query_params.get('limit', '').strip().lower()

            queryset = Patient_model.objects.select_related('hospital').order_by('-uploaded_at')

            # If 'limit' is not given, empty, or 'all' → fetch all
            if limit_param in ['', 'all']:
                patients = queryset
            else:
                try:
                    limit = int(limit_param)
                    patients = queryset[:limit]
                except ValueError:
                    return Response({"msg": "Invalid limit value", "error": 1})

            patient_data = [
                {
                    "id": e.id,
                    "patient_name": e.patient_name,
                    "mobile_no": e.mobile_no,
                    "department": e.department,
                    "hospital_name": e.hospital.name,
                    
                }
                for e in patients
            ]

            return Response({"data": patient_data, "error": 0})

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
            user_id=request.user_id
            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())  # Monday
            start_of_last_week = start_of_this_week - timedelta(days=7)

            # === Total calls ===
            contact_this_week_count = CallFeedbackModel.objects.filter(
                called_at__date__gte=start_of_this_week,
                called_at__date__lte=today,
                patient__hospital=user_id
            ).count()

            contact_last_week_count = CallFeedbackModel.objects.filter(
                called_at__date__gte=start_of_last_week,
                called_at__date__lt=start_of_this_week,
                patient__hospital=user_id
            ).count()

            # === Connected calls ===
            connected_this_week = CallFeedbackModel.objects.filter(
                call_status='connected',
                called_at__date__gte=start_of_this_week,
                called_at__date__lte=today,
                patient__hospital=user_id
            )

            connected_last_week = CallFeedbackModel.objects.filter(
                call_status='connected',
                called_at__date__gte=start_of_last_week,
                called_at__date__lt=start_of_this_week,
                patient__hospital=user_id
            )

            connected_this_week_count = connected_this_week.count()
            connected_last_week_count = connected_last_week.count()

            # === KPI 1: Total Patients Contacted ===
            if contact_last_week_count > 0:
                contact_change = ((contact_this_week_count - contact_last_week_count) / contact_last_week_count) * 100
                contact_trend = "up" if contact_change > 0 else "down"
            else:
                contact_change = 100.0 if contact_this_week_count > 0 else 0.0
                contact_trend = "up" if contact_this_week_count > 0 else "flat"

            patients_contact = {
                "title": "Total Patients Contacted",
                "value": f"{contact_this_week_count:,}",
                "change": f"{contact_change:+.0f}%",
                "trend": contact_trend,
                "icon": "Users",
                "color": "blue"
            }

            # === KPI 2: Call Answer Rate ===
            connect_this_week_rate = (connected_this_week_count / contact_this_week_count * 100) if contact_this_week_count > 0 else 0
            connect_last_week_rate = (connected_last_week_count / contact_last_week_count * 100) if contact_last_week_count > 0 else 0

            if connect_last_week_rate > 0:
                connect_change = connect_this_week_rate - connect_last_week_rate
                connect_trend = "up" if connect_change > 0 else "down"
            else:
                connect_change = connect_this_week_rate
                connect_trend = "up" if connect_this_week_rate > 0 else "flat"

            call_rate = {
                "title": "Call Answer Rate",
                "value": f"{connect_this_week_rate:.0f}%",
                "change": f"{connect_change:+.0f}%",
                "trend": connect_trend,
                "icon": "Phone",
                "color": "green"
            }

            # === KPI 3: Community Conversion ===
            community_this_week = connected_this_week.filter(community_added=True,patient__hospital=user_id).count()
            community_last_week = connected_last_week.filter(community_added=True,patient__hospital=user_id).count()

            community_this_week_rate = (community_this_week / connected_this_week_count * 100) if connected_this_week_count > 0 else 0
            community_last_week_rate = (community_last_week / connected_last_week_count * 100) if connected_last_week_count > 0 else 0

            if community_last_week_rate > 0:
                community_change = community_this_week_rate - community_last_week_rate
                community_trend = "up" if community_change > 0 else "down"
            else:
                community_change = community_this_week_rate
                community_trend = "up" if community_this_week_rate > 0 else "flat"

            community_card = {
                "title": "Community Conversion",
                "value": f"{community_this_week_rate:.0f}%",
                "change": f"{community_change:+.0f}%",
                "trend": community_trend,
                "icon": "MessageCircle",
                "color": "purple"
            }
            # === KPI 4: Escalated Issues (from EscalationModel) ===
            escalated_this_week = EscalationModel.objects.filter(
                escalated_at__date__gte=start_of_this_week,
                escalated_at__date__lte=today,
                patient__hospital=user_id
            ).count()

            escalated_last_week = EscalationModel.objects.filter(
                escalated_at__date__gte=start_of_last_week,
                escalated_at__date__lt=start_of_this_week,
                patient__hospital=user_id
            ).count()

            if escalated_last_week > 0:
                escalated_change = ((escalated_this_week - escalated_last_week) / escalated_last_week) * 100
                escalated_trend = "up" if escalated_change > 0 else "down"
            else:
                escalated_change = 100.0 if escalated_this_week > 0 else 0.0
                escalated_trend = "up" if escalated_this_week > 0 else "flat"

            escalation_card = {
                "title": "Escalated Issues",
                "value": str(escalated_this_week),
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


class Patientengagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            today = timezone.now().date()
            start_of_week = today - timedelta(days=today.weekday())  # Monday

            # === 1. Contacts per Day (Mon to Sun) ===
            contacts_qs = (
                CallFeedbackModel.objects
                .filter(called_at__date__gte=start_of_week)
                .annotate(day=TruncDate('called_at'))
                .values('day')
                .annotate(contacts=Count('id'))
            )
            

            # Initialize all 7 days with 0 contacts
            day_map = {calendar.day_name[i][:3]: 0 for i in range(7)}  # {'Mon': 0, ..., 'Sun': 0}
            for item in contacts_qs:
                day = calendar.day_name[item['day'].weekday()][:3]
                day_map[day] = item['contacts']

            contacts_data = [{"date": day, "contacts": count} for day, count in day_map.items()]

            # === 2. Call Answer Data ===
            total_calls = CallFeedbackModel.objects.filter(called_at__date__gte=start_of_week).count()
            result = CallFeedbackModel.objects.aggregate(
                total_calls=Count('id'),
                avg_call_duration=Avg('call_duration')
            )

            total_calls_all_period = result['total_calls']
            average_call_duration = result['avg_call_duration']
            meta_data={"total_calls_all_period":total_calls_all_period,"average_call_duration":np.round(average_call_duration,2)}
            answered_calls = CallFeedbackModel.objects.filter(call_status='connected', called_at__date__gte=start_of_week).count()
            not_answered = total_calls - answered_calls

            call_answer_data = [
                {"name": "Answered", "value": np.round((answered_calls/(answered_calls+not_answered))*100,2), "color": "#10B981"},
                {"name": "Not Answered", "value": np.round((not_answered/(answered_calls+not_answered))*100,2), "color": "#EF4444"},
            ]

            # === 3. Feedback Data ===
            feedback_qs = (
                CallFeedbackModel.objects
                .filter(called_at__date__gte=start_of_week)
                .values('call_outcome')
                .annotate(count=Count('id'))
            )

            label_map = {
                "positive": "Positive",
                "negative": "Negative",
                "no_feedback": "Neutral"
            }

            # Count outcome types
            feedback_dict = {label: 0 for label in label_map.values()}  # init all with 0
            for item in feedback_qs:
                label = label_map.get(item['call_outcome'], item['call_outcome'].capitalize())
                feedback_dict[label] = item['count']

            feedback_data = [{"feedback": label, "count": count} for label, count in feedback_dict.items()]

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
            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())

            # 4 full weeks including this one (from oldest to newest)
            week_starts = [start_of_this_week - timedelta(weeks=i) for i in reversed(range(4))]

            # Step 1: Get actual data from DB
            weekly_qs = (
                CommunityEngagementModel.objects
                .filter(created_at__date__gte=week_starts[0])
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
                .filter(created_at__date__gte=week_starts[0])
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
            total_engagements = CommunityEngagementModel.objects.count()
            total_posts = CommunityEngagementModel.objects.filter(engagement_type='post').count()

            avg_engagement_per_post = total_engagements / total_posts if total_posts > 0 else 0
            today = timezone.localdate()
            start_of_month = today.replace(day=1)

            # Find patients whose first engagement was this month
            first_engagements = CommunityEngagementModel.objects.values('patient') \
                .annotate(first_engagement=Min('engagement_date')) \
                .filter(first_engagement__gte=start_of_month)

            new_members_this_month = first_engagements.count()
            start_of_week = today - timedelta(days=today.weekday())

# Filter posts made this week
            posts_this_week = CommunityEngagementModel.objects.filter(
                engagement_type='post',
                engagement_date__gte=start_of_week,
                engagement_date__lte=today
            ).count()
            meta_data={
                "community_members":total_engagements,
                "post_week":posts_this_week,
                "avg_engagement/post":avg_engagement_per_post,
                "new_members":new_members_this_month
            }
            
            connected_and_added = CallFeedbackModel.objects.filter(
                call_status='connected',
                community_added=True
            ).values_list('patient', flat=True).distinct().count()
            connected = CallFeedbackModel.objects.filter(
                call_status='connected',
                
            ).values_list('patient', flat=True).distinct().count()
            conversion_rate = (connected_and_added / connected) * 100 if connected else 0
            total_engaged_users = CommunityEngagementModel.objects.values('patient').distinct().count()

            poll_participants = CommunityEngagementModel.objects.filter(
                engagement_type='poll_participation'
            ).values('patient').distinct().count()

            poll_participation_rate = (poll_participants / total_engaged_users) * 100 if total_engaged_users else 0
            one_week_ago = timezone.localdate() - timedelta(days=7)

            weekly_active_users = CommunityEngagementModel.objects.filter(
                engagement_date__gte=one_week_ago
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
class EscalationEngagement(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            now = timezone.now()

            # === 1. Department-wise Escalation Counts ===
            dept_qs = (
                EscalationModel.objects
                .exclude(department__isnull=True)
                .exclude(department__exact='')
                .values('department')
                .annotate(escalations=Count('id'))
                .order_by('-escalations')
            )

            department_escalation_data = [
                {
                    "department": row['department'],
                    "escalations": row['escalations']
                }
                for row in dept_qs
            ]

            # === 2. Resolution Status Counts ===
            status_colors = {
                "resolved": "#10B981",
                "in-progress": "#F59E0B",
                "pending": "#EF4444"
            }

            status_qs = (
                EscalationModel.objects
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
                EscalationModel.objects
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
            total_escalations = EscalationModel.objects.count()
            avg_resolution_time = EscalationModel.objects.filter(
                status='resolved',
                resolved_at__isnull=False
            ).annotate(
                resolution_duration=ExpressionWrapper(
                    F('resolved_at') - F('escalated_at'),
                    output_field=DurationField()
                )
            ).aggregate(
                avg_time=Avg('resolution_duration')
            )['avg_time']

            # Step 2: Convert to minutes
            avg_resolution_minutes = np.round(avg_resolution_time.total_seconds() / 60,2) if avg_resolution_time else 0
            

            resolved_today = EscalationModel.objects.filter(
                status='resolved',
                resolved_at__date=now
            ).count()
            
            meta_data={
                "total_escalations":total_escalations,
                "avg_resolution_time":avg_resolution_minutes,
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
            user_id = request.user_id
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
        
        
