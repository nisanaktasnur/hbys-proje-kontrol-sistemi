from django.urls import path

from projects import views
from projects import views_extended as ext

app_name = "projects"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("genel-gorunum/", views.DashboardView.as_view(), name="dashboard_alt"),
    path("teknik-gorunum/", views.TechnicalView.as_view(), name="technical_view"),
    path("teknik-is-listesi/", ext.TechnicalWorkListView.as_view(), name="technical_work_list"),
    path("teknik-riskler/", ext.TechnicalRisksView.as_view(), name="technical_risks"),
    path("teknik-uat/", ext.TechnicalUATView.as_view(), name="technical_uat"),
    path("teknik-aksiyonlar/", ext.TechnicalActionsView.as_view(), name="technical_actions"),
    path("yonetici-paneli/", ext.ManagerPanelView.as_view(), name="manager_panel"),
    path("proje-iletisim-merkezi/", ext.CommunicationCenterView.as_view(), name="communication_center"),
    path("proje-iletisim-merkezi/<int:pk>/", ext.CommunicationDetailView.as_view(), name="communication_detail"),
    path("talep-yonetimi/", views.RequestManagementView.as_view(), name="request_management"),
    path("talep/<int:pk>/", views.RequestDetailView.as_view(), name="request_detail"),
    path("risk-erken-uyari/", views.RiskWarningView.as_view(), name="risk_warning"),
    path("karar-destek-merkezi/", views.DecisionCenterView.as_view(), name="decision_center"),
    path("karar-destek-merkezi/<int:pk>/guncelle/", views.update_decision_status, name="update_decision"),
    path("karar-destek-merkezi/oneri-olustur/", views.create_decision_from_suggestion, name="create_decision_suggestion"),
    path("karar-destek-merkezi/uat/<int:pk>/karar/", views.create_decision_from_uat, name="create_decision_from_uat"),
    path("talep-yonetimi/uat/<int:pk>/guncelle/", views.update_uat_record, name="update_uat"),
    path("yonetici-ozeti/", views.ExecutiveSummaryView.as_view(), name="executive_summary"),
    path("proje/<int:project_id>/sec/", views.set_active_project, name="set_project"),
    path("kurum/<int:organization_id>/sec/", ext.set_active_organization, name="set_active_organization"),
]
