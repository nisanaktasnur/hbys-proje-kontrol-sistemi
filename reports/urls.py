from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("disa-aktar/talepler/", views.ExportRequestsView.as_view(), name="export_requests"),
    path("disa-aktar/risk/", views.ExportRiskView.as_view(), name="export_risk"),
    path("disa-aktar/karar/", views.ExportDecisionsView.as_view(), name="export_decisions"),
    path("disa-aktar/canli-gecis/", views.ExportReadinessView.as_view(), name="export_readiness"),
    path("disa-aktar/proje-riskleri/", views.ExportProjectRisksView.as_view(), name="export_project_risks"),
    path("disa-aktar/uat/", views.ExportUATView.as_view(), name="export_uat"),
    path("disa-aktar/gostergeler/", views.ExportMetricsView.as_view(), name="export_metrics"),
    path("disa-aktar/sistem-kayitlari/", views.ExportAuditView.as_view(), name="export_audit"),
    path("disa-aktar/sistem-ozet-30/", views.ExportThirtyDaySummaryView.as_view(), name="export_usage_30"),
    path("disa-aktar/sistem-aylik/", views.ExportMonthlyUsageView.as_view(), name="export_usage_monthly"),
]
