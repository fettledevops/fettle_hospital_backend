"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from app.views import (
    login_view,
    patient_insert_view,
    CallFeedbackView,
    EscalationfeedbackView,
    UpdateEscalation,
    CommunityfeedbackView,
    UpdateCommunity,
    EscalationManagementView,
    fetchpatients,
    fetchrecentactivity,
    AdminDashboardView,
    KPISummary,
    Patientengagement,
    CommunityEngagement,
    EscalationEngagement,
    validateToken,
    upload_files_log,
    Allhospitals,
    RevisitAnalyticsAPIView,
    TextView,
    tab_access,
    PdfView,
    CampaignView,
    ROIMetrics,
    DepartmentAnalytics,
    doctor_login_view,
    MediVoiceSessionView,
    DoctorTranscriptionView,
    DoctorManagementView,
)
from phone_calling.views import (
    Outbound_call,
    Process_Outbound_call,
    download_excel_outbound,
    Inboundcall,
    showInboundcall,
    processinboundcall_view,
)
from inbound_dashboard.views import (
    Patientengagement_inbound,
    CallFeedbackView_inbound,
    CommunityfeedbackView_inbound,
    CommunityEngagement_inbound,
    EscalationfeedbackView_inbound,
    EscalationEngagement_inbound,
    RevisitAnalyticsAPIView_inbound,
    KPISummary_inbound,
    UpdateEscalation_inbound,
)

urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/login/", login_view.as_view()),
    path("api/files_insert/", patient_insert_view.as_view()),
    path("api/callfeedback/", CallFeedbackView.as_view()),
    path("api/escalationfeedback/", EscalationfeedbackView.as_view()),
    path("api/update_escalation/", UpdateEscalation.as_view()),
    path("api/communityfeedback/", CommunityfeedbackView.as_view()),
    path("api/updated_community/", UpdateCommunity.as_view()),
    path("api/escalation_management/", EscalationManagementView.as_view()),
    path("api/fetchpatients/", fetchpatients.as_view()),
    path("api/fetchrecentactivity/", fetchrecentactivity.as_view()),
    path("api/admindashboard/", AdminDashboardView.as_view()),
    path("api/kpisummary/", KPISummary.as_view()),
    path("api/patientengagement/", Patientengagement.as_view()),
    path("api/communityengagement/", CommunityEngagement.as_view()),
    path("api/escalationengagement/", EscalationEngagement.as_view()),
    path("api/validate_token/", validateToken.as_view()),
    path("api/files_log/", upload_files_log.as_view()),
    path("api/allhospitals/", Allhospitals.as_view()),
    path("api/revisitengagement/", RevisitAnalyticsAPIView.as_view()),
    path("api/text/", TextView.as_view()),
    path("api/tab_access/", tab_access.as_view()),
    path("api/pdf_view/", PdfView.as_view()),
    path("api/campaigns/", CampaignView.as_view()),
    path("api/doctor_management/", DoctorManagementView.as_view()),
    path("api/doctor/login/", doctor_login_view.as_view()),
    path("api/medivoice/sessions/", MediVoiceSessionView.as_view()),
    path("api/hospital/doctor_transcripts/", DoctorTranscriptionView.as_view()),
    path("api/roi_metrics/", ROIMetrics.as_view()),
    path("api/department_analytics/", DepartmentAnalytics.as_view()),
    path("api/outbound_call/", Outbound_call.as_view()),
    path("api/process_outbound_call/", Process_Outbound_call.as_view()),
    path("api/download_excel/", download_excel_outbound.as_view()),
    path("api/inbound/", Inboundcall.as_view()),
    path("api/show_inbound/", showInboundcall.as_view()),
    path("api/patientengagement_inbound/", Patientengagement_inbound.as_view()),
    path("api/callfeedback_inbound/", CallFeedbackView_inbound.as_view()),
    path("api/communityfeedback_inbound/", CommunityfeedbackView_inbound.as_view()),
    path("api/communityengagement_inbound/", CommunityEngagement_inbound.as_view()),
    path("api/escalationfeedback_inbound/", EscalationfeedbackView_inbound.as_view()),
    path("api/escalationengagement_inbound/", EscalationEngagement_inbound.as_view()),
    path("api/revisitengagement_inbound/", RevisitAnalyticsAPIView_inbound.as_view()),
    path("api/kpisummary_inbound/", KPISummary_inbound.as_view()),
    path("api/update_escalation_inbound/", UpdateEscalation_inbound.as_view()),
    path("api/process_inbound_call/", processinboundcall_view.as_view()),
]
