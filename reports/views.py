from django.core.exceptions import PermissionDenied
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views import View

from core.context import get_accessible_projects, resolve_active_organization, user_can_access_project
from core.mixins import OrganizationRequiredMixin
from core.permissions import can_export_reports, require_permission
from core.utils import get_active_project, get_user_membership
from projects.models import DecisionSupportRecord, PostGoLiveMetric, ProjectRisk, RequestRecord, UATRecord
from reports.services.csv_export import (
    export_audit_logs,
    export_decisions,
    export_monthly_usage,
    export_post_go_live_metrics,
    export_project_risks,
    export_readiness,
    export_requests,
    export_risk_summary,
    export_thirty_day_summary,
    export_uat_records,
)


def _ensure_project_export_access(request, project):
    if project and not user_can_access_project(request.user, project):
        raise PermissionDenied("Bu projeye erişim yetkiniz bulunmuyor.")
    return project


class ExportRequestsView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "requests"))
        qs = RequestRecord.objects.filter(project=project) if project else RequestRecord.objects.none()
        qs = _apply_request_filters(qs, request.GET)
        include_score = False
        return export_requests(
            request.user,
            request.membership.organization,
            qs,
            filters=dict(request.GET),
            include_internal_score=include_score,
        )


class ExportRiskView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "risk"))
        qs = RequestRecord.objects.filter(project=project) if project else RequestRecord.objects.none()
        qs = _apply_request_filters(qs, request.GET)
        return export_risk_summary(request.user, request.membership.organization, qs, filters=dict(request.GET))


class ExportDecisionsView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "decisions"))
        qs = DecisionSupportRecord.objects.filter(project=project) if project else DecisionSupportRecord.objects.none()
        return export_decisions(request.user, request.membership.organization, qs, filters=dict(request.GET))


class ExportReadinessView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "readiness"))
        if not project:
            return redirect("projects:executive_summary")
        return export_readiness(request.user, request.membership.organization, project, filters=dict(request.GET))


class ExportProjectRisksView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "project_risks"))
        qs = ProjectRisk.objects.filter(project=project) if project else ProjectRisk.objects.none()
        return export_project_risks(request.user, request.membership.organization, qs, filters=dict(request.GET))


class ExportUATView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "uat"))
        qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
        if request.GET.get("result_status"):
            qs = qs.filter(result_status=request.GET["result_status"])
        return export_uat_records(request.user, request.membership.organization, qs, filters=dict(request.GET))


class ExportMetricsView(OrganizationRequiredMixin, View):
    def get(self, request):
        project = _ensure_project_export_access(request, get_active_project(request))
        require_permission(can_export_reports(request.user, project, "metrics"))
        qs = PostGoLiveMetric.objects.filter(project=project) if project else PostGoLiveMetric.objects.none()
        if request.GET.get("date_from"):
            qs = qs.filter(measurement_date__gte=request.GET["date_from"])
        if request.GET.get("date_to"):
            qs = qs.filter(measurement_date__lte=request.GET["date_to"])
        return export_post_go_live_metrics(request.user, request.membership.organization, qs, filters=dict(request.GET))


class ExportAuditView(OrganizationRequiredMixin, View):
    def get(self, request):
        require_permission(can_export_reports(request.user, None, "audit"))
        from core.models import AuditLog

        org = resolve_active_organization(request)
        if not org:
            return redirect("accounts:system_records")
        qs = AuditLog.objects.filter(organization=org).select_related("user", "project")
        return export_audit_logs(request.user, org, qs, filters=dict(request.GET))


class ExportThirtyDaySummaryView(OrganizationRequiredMixin, View):
    def get(self, request):
        require_permission(can_export_reports(request.user, None, "usage"))
        org = resolve_active_organization(request)
        if not org:
            return redirect("accounts:system_records")
        from projects.services.system_usage_service import thirty_day_summary

        return export_thirty_day_summary(
            request.user,
            org,
            thirty_day_summary(org),
            filters=dict(request.GET),
        )


class ExportMonthlyUsageView(OrganizationRequiredMixin, View):
    def get(self, request):
        require_permission(can_export_reports(request.user, None, "usage"))
        org = resolve_active_organization(request)
        if not org:
            return redirect("accounts:system_records")
        from projects.services.system_usage_service import monthly_usage_stats

        return export_monthly_usage(
            request.user,
            org,
            monthly_usage_stats(org),
            filters=dict(request.GET),
        )


def _apply_request_filters(qs, params):
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("process_area"):
        qs = qs.filter(process_area=params["process_area"])
    if params.get("responsible_team"):
        qs = qs.filter(responsible_team__icontains=params["responsible_team"])
    if params.get("risk_level"):
        qs = qs.filter(risk_level=params["risk_level"])
    return qs
