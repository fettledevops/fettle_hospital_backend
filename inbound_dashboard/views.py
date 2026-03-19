from rest_framework.response import Response
from rest_framework.views import APIView
from app.models import (
    CallFeedbackModel_inbound,
    CommunityEngagementModel_inbound,
    EscalationModel_inbound,
    Hospital_user_model,
    Inbound_Hospital,
)
from project.jwt_auth import JWTAuthentication
from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
from django.utils import timezone
import numpy as np
from datetime import timedelta
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Coalesce, Cast
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    FloatField,
    Min,
)
from collections import OrderedDict
from humanize import naturaltime
from collections import defaultdict, Counter
from calendar import month_abbr
from django.utils.timezone import localtime
from datetime import datetime

# Create your views here.


def make_naive(dt, tz_name="Asia/Kolkata"):
    import pytz

    if dt is None:
        return None
    target_tz = pytz.timezone(tz_name)
    # If datetime is timezone-aware → convert to IST → drop tzinfo
    if dt.tzinfo is not None:
        return dt.astimezone(target_tz).replace(tzinfo=None)
    # If datetime is naive → assume UTC → convert to IST
    return pytz.utc.localize(dt).astimezone(target_tz).replace(tzinfo=None)


class Patientengagement_inbound(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            # user_id = Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            if start_date_str and end_date_str:
                today = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_of_week = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                today = timezone.now().date()
                start_of_week = today - timedelta(days=90)

            # === 1. Contacts per Period (Raw Inbound Attempts) ===
            contacts_qs_base = Inbound_Hospital.objects.filter(
                started_at__date__gte=start_of_week, started_at__date__lte=today
            )

            delta = (today - start_of_week).days
            contacts_data = []

            if delta > 60:
                # Aggregate by Month
                period_qs = (
                    contacts_qs_base.annotate(period=TruncMonth("started_at"))
                    .values("period")
                    .annotate(contacts=Count("id"))
                    .order_by("period")
                )
                for item in period_qs:
                    if item["period"]:
                        contacts_data.append(
                            {
                                "date": item["period"].strftime("%b %Y"),
                                "contacts": item["contacts"],
                            }
                        )
            else:
                # Aggregate by Day
                period_qs = (
                    contacts_qs_base.annotate(period=TruncDate("started_at"))
                    .values("period")
                    .annotate(contacts=Count("id"))
                    .order_by("period")
                )
                day_map = {
                    (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0
                    for i in range(delta + 1)
                }
                for item in period_qs:
                    if item["period"]:
                        day_map[item["period"].strftime("%Y-%m-%d")] = item["contacts"]

                for date_str, count in sorted(day_map.items()):
                    d = datetime.strptime(date_str, "%Y-%m-%d")
                    contacts_data.append(
                        {"date": d.strftime("%b %d"), "contacts": count}
                    )

            # === 2. Call Answer Data ===
            # Apply filter
            filtered_queryset = CallFeedbackModel_inbound.objects.annotate(
                effective_called_at=Coalesce("called_at", "created_at")
            ).filter(
                effective_called_at__date__gte=start_of_week,
                effective_called_at__date__lte=today,
            )

            # Total calls
            total_calls = filtered_queryset.count()
            print("total_calls --->", total_calls)

            # Aggregate on same filtered data
            from django.db.models import FloatField
            from django.db.models.functions import Cast

            result = filtered_queryset.aggregate(
                total_calls=Count("id"),
                avg_call_duration=Avg(Cast("call_duration", FloatField())),
            )

            total_calls_all_period = result["total_calls"] or 0
            average_call_duration = result["avg_call_duration"]
            meta_data = {
                "total_calls_all_period": total_calls_all_period,
                "average_call_duration": (
                    np.round(average_call_duration, 2)
                    if average_call_duration is not None
                    else 0
                ),
            }
            answered_calls = filtered_queryset.filter(call_status="connected").count()
            not_answered = total_calls - answered_calls

            call_answer_data = [
                {
                    "name": "Answered",
                    "value": (
                        np.round((answered_calls / total_calls) * 100, 2)
                        if total_calls
                        else 0
                    ),
                    "color": "#10B981",
                },
                {
                    "name": "Not Answered",
                    "value": (
                        np.round((not_answered / total_calls) * 100, 2)
                        if total_calls
                        else 0
                    ),
                    "color": "#EF4444",
                },
            ]

            # === 3. Feedback Data ===
            feedback_qs = filtered_queryset.values(
                "call_outcome",
                "remarks",
                "effective_called_at",
                "patient__from_phone_number",
                "patient__to_phone_numnber",
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
                    item["call_outcome"], item["call_outcome"].capitalize()
                )

                remarks = item["remarks"]
                if remarks:
                    # Filter out junk remarks
                    junk_patterns = [
                        "call details only include timestamp",
                        "no conversation or outcome recorded",
                        "no meaningful feedback",
                        "no conversation recorded",
                        "call connected but no conversation",
                    ]
                    if any(pattern in remarks.lower() for pattern in junk_patterns):
                        continue

                    feedback_dict.setdefault(label, []).append(
                        {
                            "patient_name": item[
                                "patient__from_phone_number"
                            ],  # Inbound uses phone number
                            "remark": remarks,
                            "mobile_no": item["patient__from_phone_number"],
                            "feedback_at": make_naive(
                                item["effective_called_at"], tz_name="Asia/Kolkata"
                            ),
                        }
                    )

            feedback_data = [
                {"feedback": label, "count": len(entries), "remarks": entries}
                for label, entries in feedback_dict.items()
            ]

            # === Final response ===
            return Response(
                {
                    "contactsData": contacts_data,
                    "callAnswerData": call_answer_data,
                    "feedbackData": feedback_data,
                    "metadata": meta_data,
                    "weekStart": start_of_week.strftime("%Y-%m-%d"),
                    "weekEnd": today.strftime("%Y-%m-%d"),
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class CallFeedbackView_inbound(APIView):
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
            patient_id = inputdict.get("patient_id")  ###inbound_hospital_id
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
                patient = Inbound_Hospital.objects.get(id=patient_id)
            except Inbound_Hospital.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})

            # Create the feedback record
            CallFeedbackModel_inbound.objects.create(
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

            # If community was added, log engagement
            if community_added:
                CommunityEngagementModel_inbound.objects.create(
                    patient=patient,
                    engagement_type="post",
                    department=patient.department,
                )

            # If escalation is required, create escalation record
            if escalation_required:
                EscalationModel_inbound.objects.create(
                    patient=patient,
                    issue_description=remarks if remarks else "Inbound Escalation",
                    department=patient.department,
                )

            return Response({"msg": "Call feedback saved successfully", "error": 0})

        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class CommunityEngagement_inbound(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            # user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            today = timezone.now().date()
            start_of_this_week = today - timedelta(days=today.weekday())

            # 12 full weeks including this one (from oldest to newest)
            week_starts = [
                start_of_this_week - timedelta(weeks=i) for i in reversed(range(12))
            ]

            # Step 1: Get actual data from DB
            weekly_qs = (
                CommunityEngagementModel_inbound.objects.filter(
                    created_at__date__gte=week_starts[0]
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
                CommunityEngagementModel_inbound.objects.filter(
                    created_at__date__gte=week_starts[0]
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
            total_engagements = CommunityEngagementModel_inbound.objects.count()
            total_posts = CommunityEngagementModel_inbound.objects.filter(
                engagement_type="post"
            ).count()

            avg_engagement_per_post = (
                total_engagements / total_posts if total_posts > 0 else 0
            )
            today = timezone.localdate()
            start_of_month = today.replace(day=1)

            # Find patients whose first engagement was this month
            first_engagements = (
                CommunityEngagementModel_inbound.objects.values("patient")
                .annotate(first_engagement=Min("engagement_date"))
                .filter(first_engagement__gte=start_of_month)
            )

            new_members_this_month = first_engagements.count()
            start_of_week = today - timedelta(days=today.weekday())

            # Filter posts made this week
            posts_this_week = CommunityEngagementModel_inbound.objects.filter(
                engagement_type="post",
                engagement_date__gte=start_of_week,
                engagement_date__lte=today,
            ).count()
            meta_data = {
                "community_members": total_engagements,
                "post_week": posts_this_week,
                "avg_engagement/post": avg_engagement_per_post,
                "new_members": new_members_this_month,
            }

            connected_and_added = (
                CallFeedbackModel_inbound.objects.filter(
                    call_status="connected",
                    community_added=True,
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            connected = (
                CallFeedbackModel_inbound.objects.filter(
                    call_status="connected",
                )
                .values_list("patient", flat=True)
                .distinct()
                .count()
            )
            conversion_rate = (
                (connected_and_added / connected) * 100 if connected else 0
            )
            total_engaged_users = (
                CommunityEngagementModel_inbound.objects.values("patient")
                .distinct()
                .count()
            )

            poll_participants = (
                CommunityEngagementModel_inbound.objects.filter(
                    engagement_type="poll_participation"
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
                CommunityEngagementModel_inbound.objects.filter(
                    engagement_date__gte=one_week_ago,
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
            return Response(
                {
                    "communityGrowthData": community_growth_data,
                    "departmentEngagementData": department_engagement_data,
                    "metadata": meta_data,
                    "metrics": metrics,
                }
            )

        except Exception as e:
            return Response({"error": 1, "msg": str(e)})


class CommunityfeedbackView_inbound(APIView):
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
            department = inputdict.get("department", "#N/A")
            try:
                patient = Inbound_Hospital.objects.get(id=patient_id)
            except Inbound_Hospital.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            CommunityEngagementModel_inbound.objects.create(
                patient=patient, engagement_type=engagement_type, department=department
            )
            return Response({"msg": "Community feedback recorded", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class EscalationEngagement_inbound(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            # user_id= Hospital_user_model.objects.get(id=request.user_id).hospital.id
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            if start_date_str and end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=90)

            # === 1. Department-wise Escalation Counts ===
            dept_qs = (
                EscalationModel_inbound.objects.filter(
                    escalated_at__date__gte=start_date, escalated_at__date__lte=end_date
                )
                .exclude(department__isnull=True)
                .exclude(department__exact="")
                .values(
                    "department",
                    "issue_description",
                    "patient__from_phone_number",
                    "patient__to_phone_numnber",
                )
            )
            from collections import defaultdict

            dept_dict = defaultdict(list)

            for item in dept_qs:
                if item["issue_description"]:  # skip empty issues
                    dept_dict[item["department"]].append(
                        {
                            "patient_name": item["patient__from_phone_number"],
                            "issue": item["issue_description"],
                            "mobile_no": item["patient__from_phone_number"],
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
                EscalationModel_inbound.objects.filter(
                    escalated_at__date__gte=start_date, escalated_at__date__lte=end_date
                )
                .values("status")
                .annotate(value=Count("id"))
            )
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
                EscalationModel_inbound.objects.filter(
                    escalated_at__date__gte=start_date, escalated_at__date__lte=end_date
                )
                .select_related("patient")
                .order_by("-escalated_at")[:10]
            )

            recent_escalations = []
            for i, esc in enumerate(recent_qs, start=1):
                recent_escalations.append(
                    {
                        "id": esc.id,
                        "patient": esc.patient.from_phone_number,
                        "issue": esc.issue_description,
                        "status": esc.status,
                        "time": naturaltime(esc.escalated_at),
                    }
                )
            total_escalations = EscalationModel_inbound.objects.filter(
                escalated_at__date__gte=start_date, escalated_at__date__lte=end_date
            ).count()
            avg_resolution_time = (
                EscalationModel_inbound.objects.filter(
                    status="resolved",
                    resolved_at__isnull=False,
                    escalated_at__date__gte=start_date,
                    escalated_at__date__lte=end_date,
                )
                .annotate(
                    resolution_duration=ExpressionWrapper(
                        F("resolved_at") - F("escalated_at"),
                        output_field=DurationField(),
                    )
                )
                .aggregate(avg_time=Avg("resolution_duration"))["avg_time"]
            )

            # Step 2: Convert to days
            avg_resolution_days = (
                np.round(avg_resolution_time.total_seconds() / (24 * 3600), 2)
                if avg_resolution_time
                else 0
            )

            resolved_today = EscalationModel_inbound.objects.filter(
                status="resolved",
                resolved_at__date=timezone.now().date(),
            ).count()

            meta_data = {
                "total_escalations": total_escalations,
                "avg_resolution_time": avg_resolution_days,
                "resolved_today": resolved_today,
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


class EscalationfeedbackView_inbound(APIView):
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
                patient = Inbound_Hospital.objects.get(id=patient_id)
            except Inbound_Hospital.DoesNotExist:
                return Response({"msg": "Patient does not exist", "error": 1})
            EscalationModel_inbound.objects.create(
                patient=patient,
                issue_description=issue_description,
                department=department,
            )
            return Response({"msg": "Escalation feedback recorded", "error": 0})
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class RevisitAnalyticsAPIView_inbound(APIView):
    authentication_classes = [JWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            visits_query = Inbound_Hospital.objects.all()

            if start_date_str and end_date_str:
                visits_query = visits_query.filter(
                    started_at__date__range=[start_date_str, end_date_str]
                )

            visits = (
                visits_query.annotate(visit_day=TruncDate("started_at"))
                .values("to_phone_numnber", "department", "started_at")
                .distinct()
            )

            visit_map = defaultdict(set)
            for visit in visits:
                key = (visit["to_phone_numnber"], visit["department"])
                visit_map[key].add(visit["started_at"])

            color_map = {
                "Cardiology": "#EF4444",
                "Orthopedics": "#F59E0B",
                "Pediatrics": "#10B981",
                "General Medicine": "#3B82F6",
                "Dental": "#8B5CF6",
                "Dermatology": "#EC4899",
                "Neurology": "#6366F1",
                "ENT": "#14B8A6",
                "Opthalmology": "#F97316",
                "Oncology": "#06B6D4",
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

                # Count ALL visits in the monthly trend
                for date in sorted_days:
                    local_date = localtime(date)
                    month_key = (local_date.year, local_date.month)
                    monthly_counter[month_key] += 1

                if len(visit_days) > 1:
                    revisit_count = len(sorted_days) - 1
                    department_counter[department] += revisit_count

                    for date in sorted_days[1:]:
                        local_date = localtime(date)
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
            if start_date_str and end_date_str:
                s_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                e_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
            else:
                e_dt = datetime.now()
                s_dt = e_dt - timedelta(days=180)

            curr = s_dt.replace(day=1)
            all_month_keys = []
            while curr <= e_dt:
                all_month_keys.append((curr.year, curr.month))
                if curr.month == 12:
                    curr = curr.replace(year=curr.year + 1, month=1)
                else:
                    curr = curr.replace(month=curr.month + 1)

            for year, month in all_month_keys:
                label = f"{month_abbr[month]} {str(year)[2:]}"
                monthly_data.append(
                    {"month": label, "revisits": monthly_counter.get((year, month), 0)}
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


class KPISummary_inbound(APIView):
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")

            if start_date_str and end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_of_this_month = datetime.strptime(
                    start_date_str, "%Y-%m-%d"
                ).date()
                today = end_date
            else:
                today = timezone.now().date()
                start_of_this_month = today - timedelta(days=90)

            base_qs = CallFeedbackModel_inbound.objects.annotate(
                effective_called_at=Coalesce("called_at", "created_at")
            ).filter(
                effective_called_at__date__gte=start_of_this_month,
                effective_called_at__date__lte=today,
            )

            # === 1. Total Inbound Traffic (Attempts) ===
            total_inbound_attempts = Inbound_Hospital.objects.filter(
                started_at__date__gte=start_of_this_month, started_at__date__lte=today
            ).count()

            interactions_card = {
                "title": "Total Interactions",
                "value": f"{total_inbound_attempts:,}",
                "change": "Live",
                "trend": "up",
                "icon": "Users",
                "color": "blue",
            }

            # 2. Avg Call Resolution
            avg_res_time = (
                base_qs.filter(call_status="connected").aggregate(
                    avg=Avg(Cast("call_duration", FloatField()))
                )["avg"]
                or 0
            )
            resolution_card = {
                "title": "Avg Resolution",
                "value": f"{int(avg_res_time * 60)} sec",
                "change": "Live",
                "trend": "up",
                "icon": "Clock",
                "color": "green",
            }

            # 3. Conversion Rate
            connected_calls = base_qs.filter(call_status="connected").count()
            booked = base_qs.filter(call_outcome="positive").count()
            conv_rate = (booked / connected_calls * 100) if connected_calls > 0 else 0

            conversion_card = {
                "title": "Inbound Conversion",
                "value": f"{conv_rate:.1f}%",
                "change": "Target 40%",
                "trend": "up" if conv_rate > 40 else "down",
                "icon": "TrendingUp",
                "color": "purple",
            }

            # 4. No-Show Rate
            noshow_card = {
                "title": "No-Show Rate",
                "value": "11.0%",
                "change": "Baseline",
                "trend": "flat",
                "icon": "UserX",
                "color": "red",
            }

            # 5. Total Inbound Volume (Historical)
            traffic_card = {
                "title": "Inbound Traffic",
                "value": f"{total_inbound_attempts:,}",
                "change": "Active",
                "trend": "up",
                "icon": "Users",
                "color": "blue",
            }

            # 6. Call Answer Rate
            ans_rate = (
                (connected_calls / total_inbound_attempts * 100)
                if total_inbound_attempts > 0
                else 0
            )
            call_rate = {
                "title": "Inbound Answer Rate",
                "value": f"{ans_rate:.0f}%",
                "change": "Live",
                "trend": "up",
                "icon": "Phone",
                "color": "green",
            }

            # 7. Escalated Issues
            total_escalation = EscalationModel_inbound.objects.count()
            escalation_card = {
                "title": "Escalated Issues",
                "value": str(total_escalation),
                "change": "Live",
                "trend": "up",
                "icon": "AlertTriangle",
                "color": "orange",
            }

            # 8. Revenue Influenced
            revenue_card = {
                "title": "Revenue Influenced",
                "value": f"₹{booked * 650:,}",
                "change": "Live",
                "trend": "up",
                "icon": "TrendingUp",
                "color": "emerald",
            }

            return Response(
                {
                    "interactions": interactions_card,
                    "resolution": resolution_card,
                    "conversion": conversion_card,
                    "noshow": noshow_card,
                    "patients": traffic_card,
                    "ans_rate": call_rate,
                    "escalation": escalation_card,
                    "revenue": revenue_card,
                }
            )
        except Exception as e:
            return Response({"msg": str(e), "error": 1})


class UpdateEscalation_inbound(APIView):
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
                escalation = EscalationModel_inbound.objects.get(id=id)
            except EscalationModel_inbound.DoesNotExist:
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
