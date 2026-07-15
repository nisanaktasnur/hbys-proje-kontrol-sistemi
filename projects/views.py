from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, TemplateView

from accounts.models import Role
from core.mixins import PageAccessMixin
from core.models import Project
from core.permissions import (
    TEKNIK_EKIP_LABEL,
    can_create_request,
    can_edit_request,
    can_manage_decision_records,
    can_manage_project_risks,
    can_manage_uat,
    can_update_go_live_readiness,
    can_update_technical_fields,
    can_update_uat_technical,
    can_view_executive_reports,
    can_view_request,
    require_permission,
)
from core.utils import get_active_project, get_user_membership, log_audit
from projects.forms import (
    DecisionSupportForm,
    ExecutiveFilterForm,
    PostGoLiveMetricForm,
    ProjectRiskForm,
    RequestFilterForm,
    RequestRecordForm,
    TechnicalRequestUpdateForm,
    UATRecordForm,
    UATTechnicalUpdateForm,
)
from projects.models import (
    DecisionSource,
    DecisionSupportRecord,
    DecisionStatus,
    GoLiveReadiness,
    MetricStatus,
    PostGoLiveMetric,
    ProjectRisk,
    ProjectRiskStatus,
    RequestActivity,
    RequestRecord,
    RequestStatus,
    RiskLevel,
    UATRecord,
)
from projects.services.dashboard_kpi_service import DASHBOARD_DECISIONS, KPI_EXPLANATIONS, UAT_MANAGEMENT_NOTE
from projects.services.decision_suggestion_service import create_decision_if_new, get_pending_suggestions
from projects.services.post_go_live_service import metric_compare_data, metric_timeline, post_go_live_summary
from projects.services.risk_matrix_service import (
    high_risks_without_action,
    matrix_risk_details,
    project_risk_summary,
)
from projects.services.role_dashboard_service import (
    admin_dashboard_stats,
    executive_dashboard_stats,
    project_manager_dashboard_stats,
)
from projects.services.technical_service import technical_dashboard_stats
from projects.services.uat_summary_service import uat_summary
from projects.services.risk_service import apply_risk_to_request


def _accessible_projects(request):
    from core.context import get_accessible_projects

    return get_accessible_projects(request.user)


def _org_projects(request):
    from core.context import get_accessible_projects, resolve_active_organization

    org = resolve_active_organization(request)
    return get_accessible_projects(request.user, org)


def _project_queryset(request, project=None):
    project = project or get_active_project(request)
    if not project:
        return RequestRecord.objects.none(), None
    qs = RequestRecord.objects.filter(project=project).select_related("owner", "created_by", "project")
    return qs, project


def _generate_record_number(project):
    count = RequestRecord.objects.filter(project=project).count() + 1
    return f"HBYS-{project.id:02d}-{count:04d}"


def _process_open_count(project, process_area):
    return RequestRecord.objects.filter(
        project=project,
        process_area=process_area,
        status__in=[RequestStatus.ACIK, RequestStatus.DEVAM, RequestStatus.PLANLANDI],
    ).count()


def _dashboard_stats(qs, readiness):
    open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI)
    return {
        "open_count": open_qs.count(),
        "high_risk": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "medium_risk": open_qs.filter(risk_level=RiskLevel.ORTA).count(),
        "low_risk": open_qs.filter(risk_level=RiskLevel.DUSUK).count(),
        "overdue": open_qs.filter(due_date__lt=timezone.localdate()).count(),
        "recent_requests": qs.order_by("-created_at")[:8],
        "process_attention": (
            open_qs.values("process_area")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        ),
        "readiness": readiness,
        "overall_status": readiness.overall_status if readiness else "—",
    }


class DashboardView(PageAccessMixin, TemplateView):
    template_name = "projects/dashboard.html"
    page_url_name = "projects:dashboard"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        membership = self.request.membership
        qs, project = _project_queryset(self.request)
        readiness = GoLiveReadiness.objects.filter(project=project).first() if project else None

        if membership.role == Role.SISTEM_YONETICISI:
            ctx.update(admin_dashboard_stats(membership.organization))
            ctx["read_only_dashboard"] = True
            return ctx

        ctx.update(_dashboard_stats(qs, readiness))
        ctx["risk_chart"] = {
            "labels": ["Düşük", "Orta", "Yüksek"],
            "values": [
                qs.filter(risk_level=RiskLevel.DUSUK).exclude(status=RequestStatus.TAMAMLANDI).count(),
                qs.filter(risk_level=RiskLevel.ORTA).exclude(status=RequestStatus.TAMAMLANDI).count(),
                qs.filter(risk_level=RiskLevel.YUKSEK).exclude(status=RequestStatus.TAMAMLANDI).count(),
            ],
        }
        ctx["kpi_explanations"] = KPI_EXPLANATIONS
        ctx["dashboard_decisions"] = DASHBOARD_DECISIONS

        if membership.role == Role.PROJE_YONETICISI:
            ctx.update(project_manager_dashboard_stats(qs, project, readiness))
            open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI)
            ctx["priority_follow_list"] = (
                open_qs.filter(
                    Q(risk_level=RiskLevel.YUKSEK)
                    | Q(due_date__lt=timezone.localdate())
                )
                .order_by("-risk_level", "due_date")[:12]
            )
        elif membership.role == Role.YONETICI:
            ctx.update(executive_dashboard_stats(qs, project, readiness))
            ctx["read_only_dashboard"] = True

        if project:
            uat_qs = UATRecord.objects.filter(project=project)
            ctx["uat_summary"] = uat_summary(uat_qs)
            ctx["uat_note"] = UAT_MANAGEMENT_NOTE
        else:
            ctx["uat_summary"] = uat_summary(UATRecord.objects.none())
            ctx["uat_note"] = UAT_MANAGEMENT_NOTE

        from projects.services.communication_service import (
            communication_inbox_summary,
            pending_instructions,
        )

        ctx["pending_instructions"] = (
            list(
                pending_instructions(
                    self.request.user,
                    project,
                    membership.role,
                )[:8]
            )
            if project
            else []
        )
        if project and membership.role in {Role.PROJE_YONETICISI, Role.TEKNIK_LIDER}:
            ctx["communication_summary"] = communication_inbox_summary(
                self.request.user,
                project,
                membership.role,
            )
        return ctx


class TechnicalView(PageAccessMixin, TemplateView):
    template_name = "projects/technical_view.html"
    page_url_name = "projects:technical_view"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs, project = _project_queryset(self.request)
        readiness = GoLiveReadiness.objects.filter(project=project).first() if project else None
        ctx.update(technical_dashboard_stats(qs, project, self.request.user))
        ctx["readiness"] = readiness
        if project:
            ctx["uat_summary"] = uat_summary(UATRecord.objects.filter(project=project))
        from projects.services.communication_service import (
            communication_inbox_summary,
            pending_instructions,
        )

        ctx["pending_instructions"] = (
            list(
                pending_instructions(
                    self.request.user,
                    project,
                    self.request.membership.role if self.request.membership else None,
                )[:8]
            )
            if project
            else []
        )
        if project:
            ctx["communication_summary"] = communication_inbox_summary(
                self.request.user,
                project,
                self.request.membership.role if self.request.membership else None,
            )
        return ctx


class RequestManagementView(PageAccessMixin, TemplateView):
    template_name = "projects/request_management.html"
    page_url_name = "projects:request_management"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs, project = _project_queryset(self.request)
        membership = self.request.membership
        get_data = self.request.GET.copy()
        show_all = self.request.GET.get("tumunu") == "1"
        if (
            membership.role == Role.TEKNIK_LIDER
            and not show_all
            and self.request.GET.get("sekme", "liste") == "liste"
            and not any(
                self.request.GET.get(k)
                for k in ("q", "status", "risk_level", "process_area", "responsible_team", "owner", "overdue")
            )
        ):
            get_data.setdefault("responsible_team", TEKNIK_EKIP_LABEL)
            get_data.setdefault("owner", str(self.request.user.pk))
            get_data.setdefault("status", RequestStatus.ACIK)
            get_data.setdefault("risk_level", RiskLevel.YUKSEK)

        filter_form = RequestFilterForm(
            get_data or None,
            organization=self.request.membership.organization,
        )
        filtered = qs
        ctx["using_technical_defaults"] = (
            membership.role == Role.TEKNIK_LIDER and not show_all and not self.request.GET.get("tumunu")
        )
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            if data.get("q"):
                filtered = filtered.filter(
                    Q(title__icontains=data["q"])
                    | Q(responsible_team__icontains=data["q"])
                    | Q(record_number__icontains=data["q"])
                )
            if data.get("status"):
                filtered = filtered.filter(status=data["status"])
            if data.get("risk_level"):
                filtered = filtered.filter(risk_level=data["risk_level"])
            if data.get("process_area"):
                filtered = filtered.filter(process_area=data["process_area"])
            if data.get("responsible_team"):
                filtered = filtered.filter(responsible_team__icontains=data["responsible_team"])
            if data.get("owner"):
                filtered = filtered.filter(owner=data["owner"])
            if data.get("overdue"):
                filtered = filtered.filter(
                    due_date__lt=timezone.localdate()
                ).exclude(status=RequestStatus.TAMAMLANDI)
            if membership.role == Role.TEKNIK_LIDER and ctx["using_technical_defaults"]:
                filtered = filtered.filter(
                    status__in=[RequestStatus.ACIK, RequestStatus.DEVAM],
                    risk_level__in=[RiskLevel.YUKSEK, RiskLevel.ORTA],
                )
            sort = data.get("sort") or "-updated_at"
            filtered = filtered.order_by(sort)
        else:
            filtered = filtered.order_by("-updated_at")

        from django.core.paginator import Paginator

        paginator = Paginator(filtered, 15)
        page = paginator.get_page(self.request.GET.get("page"))

        ctx["filter_form"] = filter_form
        ctx["page_obj"] = page
        ctx["create_form"] = RequestRecordForm(organization=self.request.membership.organization)
        ctx["can_create_request"] = can_create_request(self.request.user, project)
        ctx["can_manage_uat"] = can_manage_uat(self.request.user, project)
        ctx["can_update_uat_technical"] = can_update_uat_technical(self.request.user, project)
        ctx["active_tab"] = self.request.GET.get("sekme", "liste")
        if project:
            ctx["uat_records"] = UATRecord.objects.filter(project=project).select_related("related_request")
            ctx["uat_form"] = UATRecordForm(project=project)
            ctx["uat_summary"] = uat_summary(UATRecord.objects.filter(project=project))
            ctx["uat_note"] = UAT_MANAGEMENT_NOTE
        return ctx

    def post(self, request, *args, **kwargs):
        qs, project = _project_queryset(request)
        if not project:
            return redirect("projects:request_management")

        tab = request.POST.get("form_type", "request")
        if tab == "uat":
            require_permission(can_manage_uat(request.user, project))
            form = UATRecordForm(request.POST, project=project)
            if form.is_valid():
                uat = form.save(commit=False)
                uat.project = project
                uat.save()
                log_audit(
                    request.user,
                    request.membership.organization,
                    "UAT Kaydı",
                    "UATRecord",
                    uat.pk,
                    uat.scenario_name,
                    project,
                )
                return redirect("/talep-yonetimi/?sekme=uat")
            ctx = self.get_context_data(**kwargs)
            ctx["uat_form"] = form
            ctx["active_tab"] = "uat"
            return render(request, self.template_name, ctx)

        require_permission(can_create_request(request.user, project))
        form = RequestRecordForm(request.POST, organization=request.membership.organization)
        if form.is_valid():
            record = form.save(commit=False)
            record.project = project
            record.created_by = request.user
            record.record_number = _generate_record_number(project)
            open_count = _process_open_count(project, record.process_area)
            apply_risk_to_request(record, open_count)
            record.save()
            RequestActivity.objects.create(
                request=record,
                user=request.user,
                action="Talep oluşturuldu",
                details=record.title,
            )
            log_audit(
                request.user,
                request.membership.organization,
                "Talep Oluşturma",
                "RequestRecord",
                record.pk,
                record.title,
                project,
            )
            return redirect(f"/talep-yonetimi/?sekme=liste&highlight={record.pk}")
        ctx = self.get_context_data(**kwargs)
        ctx["create_form"] = form
        ctx["active_tab"] = "yeni"
        return render(request, self.template_name, ctx)


class RequestDetailView(PageAccessMixin, DetailView):
    model = RequestRecord
    template_name = "projects/request_detail.html"
    context_object_name = "request_record"
    pk_url_kwarg = "pk"
    page_url_name = "projects:request_detail"

    def get_queryset(self):
        from core.context import get_accessible_projects

        return RequestRecord.objects.filter(
            project__in=get_accessible_projects(self.request.user)
        ).select_related("project", "owner", "technical_owner")

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        require_permission(can_view_request(request.user, self.object))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        record = self.object
        ctx["can_edit_request"] = can_edit_request(self.request.user, record)
        ctx["can_update_technical_fields"] = can_update_technical_fields(self.request.user, record)
        ctx["edit_form"] = RequestRecordForm(
            instance=record,
            organization=self.request.membership.organization,
        )
        ctx["technical_form"] = TechnicalRequestUpdateForm(
            instance=record,
            project=record.project,
        )
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        record = self.object
        form_type = request.POST.get("form_type", "management")
        if form_type == "management":
            require_permission(can_edit_request(request.user, record))
            form = RequestRecordForm(
                request.POST,
                instance=record,
                organization=request.membership.organization,
            )
            if form.is_valid():
                old_status = record.status
                old_due = record.due_date
                old_owner = record.owner_id
                updated = form.save()
                if old_status != updated.status:
                    RequestActivity.objects.create(
                        request=updated,
                        user=request.user,
                        action="Durum değişikliği",
                        details=f"{old_status} → {updated.status}",
                    )
                if old_due != updated.due_date:
                    RequestActivity.objects.create(
                        request=updated,
                        user=request.user,
                        action="Hedef tarih değişikliği",
                        details=str(updated.due_date or "—"),
                    )
                if old_owner != updated.owner_id:
                    RequestActivity.objects.create(
                        request=updated,
                        user=request.user,
                        action="Atama",
                        details=updated.responsible_team,
                    )
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Talep Güncelleme",
                    "RequestRecord",
                    updated.pk,
                    updated.title,
                    updated.project,
                )
                return redirect("projects:request_detail", pk=updated.pk)
        else:
            require_permission(can_update_technical_fields(request.user, record))
            form = TechnicalRequestUpdateForm(
                request.POST,
                instance=record,
                project=record.project,
            )
            if form.is_valid():
                old_tech = record.technical_status
                updated = form.save()
                RequestActivity.objects.create(
                    request=updated,
                    user=request.user,
                    action="Teknik not",
                    details=updated.recommended_action[:200]
                    if updated.recommended_action
                    else (updated.technical_status or "—"),
                )
                if old_tech != updated.technical_status:
                    RequestActivity.objects.create(
                        request=updated,
                        user=request.user,
                        action="Teknik durum değişikliği",
                        details=f"{old_tech or '—'} → {updated.technical_status or '—'}",
                    )
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Teknik Talep Güncelleme",
                    "RequestRecord",
                    updated.pk,
                    updated.title,
                    updated.project,
                )
                return redirect("projects:request_detail", pk=updated.pk)
        ctx = self.get_context_data(object=record)
        if form_type == "management":
            ctx["edit_form"] = form
        else:
            ctx["technical_form"] = form
        return render(request, self.template_name, ctx)


class RiskWarningView(PageAccessMixin, TemplateView):
    template_name = "projects/risk_warning.html"
    page_url_name = "projects:risk_warning"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs, project = _project_queryset(self.request)
        open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI)
        ctx["low_count"] = open_qs.filter(risk_level=RiskLevel.DUSUK).count()
        ctx["medium_count"] = open_qs.filter(risk_level=RiskLevel.ORTA).count()
        ctx["high_count"] = open_qs.filter(risk_level=RiskLevel.YUKSEK).count()
        ctx["overdue_count"] = open_qs.filter(due_date__lt=timezone.localdate()).count()
        ctx["go_live_high"] = open_qs.filter(
            risk_level=RiskLevel.YUKSEK,
            go_live_impact="Yüksek",
        ).order_by("-updated_at")[:10]
        ctx["process_risk"] = (
            open_qs.values("process_area")
            .annotate(
                dusuk=Count("id", filter=Q(risk_level=RiskLevel.DUSUK)),
                orta=Count("id", filter=Q(risk_level=RiskLevel.ORTA)),
                yuksek=Count("id", filter=Q(risk_level=RiskLevel.YUKSEK)),
            )
            .order_by("-yuksek", "-orta")
        )
        ctx["priority_list"] = open_qs.filter(
            risk_level=RiskLevel.YUKSEK
        ).order_by("due_date", "-updated_at")[:15]
        overdue_decisions = DecisionSupportRecord.objects.filter(
            project=project,
            due_date__lt=timezone.localdate(),
        ).exclude(status=DecisionStatus.TAMAMLANDI)[:10] if project else []
        ctx["overdue_decisions"] = overdue_decisions
        ctx["overdue_requests"] = open_qs.filter(due_date__lt=timezone.localdate()).order_by("due_date")[:10]
        if project:
            pr_qs = ProjectRisk.objects.filter(project=project).select_related("owner", "related_request")
            ctx["project_risk_summary"] = project_risk_summary(pr_qs)
            ctx["project_risks"] = pr_qs.exclude(status=ProjectRiskStatus.TAMAMLANDI).order_by("-risk_level", "due_date")
            ctx["matrix_risk_details"] = matrix_risk_details(pr_qs)
            ctx["high_risks_no_action"] = high_risks_without_action(pr_qs)
            ctx["project_risk_form"] = ProjectRiskForm(
                project=project,
                organization=self.request.membership.organization,
            )
            ctx["matrix_levels"] = list(RiskLevel.values)
        ctx["can_manage_project_risks"] = can_manage_project_risks(self.request.user, project)
        ctx["read_only_risk_page"] = self.request.membership.role in {
            Role.SISTEM_YONETICISI,
            Role.YONETICI,
        }
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_manage_project_risks(request.user, project))
        if not project:
            return redirect("projects:risk_warning")
        edit_pk = request.POST.get("edit_pk")
        instance = None
        if edit_pk:
            instance = get_object_or_404(ProjectRisk, pk=edit_pk, project=project)
        form = ProjectRiskForm(
            request.POST,
            instance=instance,
            project=project,
            organization=request.membership.organization,
        )
        if form.is_valid():
            risk = form.save(commit=False)
            risk.project = project
            if not risk.pk:
                risk.created_by = request.user
            risk.save()
            log_audit(
                request.user,
                request.membership.organization,
                "Proje Riski",
                "ProjectRisk",
                risk.pk,
                risk.title,
                project,
            )
        return redirect("projects:risk_warning")


class DecisionCenterView(PageAccessMixin, TemplateView):
    template_name = "projects/decision_center.html"
    page_url_name = "projects:decision_center"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, project = _project_queryset(self.request)
        decisions = DecisionSupportRecord.objects.filter(project=project).select_related(
            "related_request", "owner"
        ) if project else DecisionSupportRecord.objects.none()
        ctx["decisions"] = decisions.order_by("-updated_at")
        ctx["recommended"] = decisions.exclude(status=DecisionStatus.TAMAMLANDI).order_by("due_date")[:10]
        ctx["process_areas"] = (
            decisions.exclude(status=DecisionStatus.TAMAMLANDI)
            .values("responsible_team")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
        ctx["form"] = DecisionSupportForm(project=project, organization=self.request.membership.organization)
        ctx["decision_statuses"] = DecisionStatus.choices
        ctx["pending_suggestions"] = get_pending_suggestions(project) if project else []
        ctx["decision_sources"] = DecisionSource.choices
        ctx["can_manage_decision_records"] = can_manage_decision_records(self.request.user, project)
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_manage_decision_records(request.user, project))
        form = DecisionSupportForm(
            request.POST,
            project=project,
            organization=request.membership.organization,
        )
        if form.is_valid() and project:
            decision = form.save(commit=False)
            decision.project = project
            decision.save()
            log_audit(
                request.user,
                request.membership.organization,
                "Karar Destek Kaydı",
                "DecisionSupportRecord",
                decision.pk,
                decision.title,
                project,
            )
            return redirect("projects:decision_center")
        ctx = self.get_context_data(**kwargs)
        ctx["form"] = form
        return render(request, self.template_name, ctx)


@login_required
@require_POST
def update_decision_status(request, pk):
    membership = get_user_membership(request)
    if not membership:
        return redirect("accounts:login")

    decision = get_object_or_404(
        DecisionSupportRecord,
        pk=pk,
        project__in=_accessible_projects(request),
    )
    require_permission(can_manage_decision_records(request.user, decision.project))
    new_status = request.POST.get("status", "")
    valid_statuses = {choice[0] for choice in DecisionStatus.choices}
    if new_status in valid_statuses:
        decision.status = new_status
        notes = request.POST.get("notes", "").strip()
        if notes:
            decision.notes = notes
        decision.save()
        log_audit(
            request.user,
            membership.organization,
            "Karar Destek Güncelleme",
            "DecisionSupportRecord",
            decision.pk,
            decision.title,
            decision.project,
        )
    return redirect("projects:decision_center")


class ExecutiveSummaryView(PageAccessMixin, TemplateView):
    template_name = "projects/executive_summary.html"
    page_url_name = "projects:executive_summary"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.membership.organization
        projects = _org_projects(self.request)
        filter_form = ExecutiveFilterForm(self.request.GET or None, projects=projects)
        project = get_active_project(self.request)

        date_from = date_to = None
        process_area = responsible_team = None
        if filter_form.is_valid():
            if filter_form.cleaned_data.get("project"):
                project = projects.filter(id=int(filter_form.cleaned_data["project"])).first() or project
            process_area = filter_form.cleaned_data.get("process_area") or None
            responsible_team = filter_form.cleaned_data.get("responsible_team") or None
            date_from = filter_form.cleaned_data.get("date_from")
            date_to = filter_form.cleaned_data.get("date_to")

        qs = RequestRecord.objects.filter(project=project) if project else RequestRecord.objects.none()
        if process_area:
            qs = qs.filter(process_area=process_area)
        if responsible_team:
            qs = qs.filter(responsible_team__icontains=responsible_team)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI)
        readiness = GoLiveReadiness.objects.filter(project=project).first() if project else None

        ctx["filter_form"] = filter_form
        ctx["projects"] = projects
        ctx["stats"] = {
            "project_status": project.status if project else "—",
            "open_count": open_qs.count(),
            "high_risk": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
            "overdue": open_qs.filter(due_date__lt=timezone.localdate()).count(),
            "completed": qs.filter(status=RequestStatus.TAMAMLANDI).count(),
            "overall_status": readiness.overall_status if readiness else "—",
        }
        ctx["status_chart"] = list(qs.values("status").annotate(count=Count("id")))
        ctx["risk_chart"] = {
            "labels": ["Düşük", "Orta", "Yüksek"],
            "values": [
                qs.filter(risk_level=RiskLevel.DUSUK).count(),
                qs.filter(risk_level=RiskLevel.ORTA).count(),
                qs.filter(risk_level=RiskLevel.YUKSEK).count(),
            ],
        }
        ctx["process_chart"] = list(
            open_qs.values("process_area").annotate(count=Count("id")).order_by("-count")
        )
        ctx["team_chart"] = list(
            open_qs.values("responsible_team").annotate(count=Count("id")).order_by("-count")[:10]
        )
        ctx["decision_chart"] = list(
            DecisionSupportRecord.objects.filter(project=project).values("status").annotate(count=Count("id"))
        ) if project else []
        ctx["timeline"] = _timeline_data(qs)
        ctx["overdue_timeline"] = _overdue_timeline(qs)
        ctx["overdue_decisions"] = (
            DecisionSupportRecord.objects.filter(
                project=project,
                due_date__lt=timezone.localdate(),
            ).exclude(status=DecisionStatus.TAMAMLANDI)[:10]
            if project else []
        )
        ctx["manager_notes"] = _manager_notes(open_qs, readiness, project)
        ctx["filter_params"] = self.request.GET.urlencode()
        if project:
            pr_qs = ProjectRisk.objects.filter(project=project)
            ctx["project_risk_summary"] = project_risk_summary(pr_qs)
            ctx["matrix_levels"] = list(RiskLevel.values)
            uat_qs = UATRecord.objects.filter(project=project)
            ctx["uat_summary"] = uat_summary(uat_qs)
            ctx["uat_note"] = UAT_MANAGEMENT_NOTE
            metrics_qs = PostGoLiveMetric.objects.filter(project=project)
            if date_from:
                metrics_qs = metrics_qs.filter(measurement_date__gte=date_from)
            if date_to:
                metrics_qs = metrics_qs.filter(measurement_date__lte=date_to)
            ctx["post_go_live_metrics"] = metrics_qs.order_by("-measurement_date")
            ctx["post_go_live_summary"] = post_go_live_summary(metrics_qs)
            ctx["metric_form"] = PostGoLiveMetricForm()
            ctx["metric_timeline"] = metric_timeline(metrics_qs)
            ctx["metric_compare"] = metric_compare_data(metrics_qs)
            ctx["metric_status_chart"] = list(
                metrics_qs.values("status").annotate(count=Count("id"))
            )
            ctx["decision_actions"] = DecisionSupportRecord.objects.filter(
                project=project
            ).exclude(status=DecisionStatus.TAMAMLANDI).order_by("due_date")[:10]
            top_risk = pr_qs.filter(risk_level=RiskLevel.YUKSEK).exclude(
                status=ProjectRiskStatus.TAMAMLANDI
            ).first()
            ctx["top_project_risk"] = top_risk
            ctx["blocking_uat"] = uat_qs.filter(
                result_status__in=["Başarısız", "Bloke", "Tekrar Test Bekliyor"]
            ).order_by("-severity", "-test_date")[:5]
        ctx["read_only_executive"] = self.request.membership.role == Role.YONETICI
        ctx["can_update_go_live_readiness"] = can_update_go_live_readiness(self.request.user, project)
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_update_go_live_readiness(request.user, project))
        if not project:
            return redirect("projects:executive_summary")
        form = PostGoLiveMetricForm(request.POST)
        edit_pk = request.POST.get("edit_pk")
        instance = None
        if edit_pk:
            instance = get_object_or_404(PostGoLiveMetric, pk=edit_pk, project=project)
            form = PostGoLiveMetricForm(request.POST, instance=instance)
        if form.is_valid():
            metric = form.save(commit=False)
            metric.project = project
            metric.save()
            log_audit(
                request.user,
                request.membership.organization,
                "Canlı Geçiş Göstergesi",
                "PostGoLiveMetric",
                metric.pk,
                metric.metric_name,
                project,
            )
        return redirect(f"{request.path}?{request.GET.urlencode()}" if request.GET else request.path)


def _timeline_data(qs):
    from django.db.models.functions import TruncMonth

    opened = (
        qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    completed = (
        qs.filter(status=RequestStatus.TAMAMLANDI, completed_at__isnull=False)
        .annotate(month=TruncMonth("completed_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    return {"opened": list(opened), "completed": list(completed)}


def _overdue_timeline(qs):
    from django.db.models.functions import TruncWeek

    open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI).filter(due_date__lt=timezone.localdate())
    return list(
        open_qs.annotate(week=TruncWeek("due_date"))
        .values("week")
        .annotate(count=Count("id"))
        .order_by("week")
    )


def _manager_notes(open_qs, readiness, project=None):
    notes = []
    high = open_qs.filter(risk_level=RiskLevel.YUKSEK).count()
    overdue = open_qs.filter(due_date__lt=timezone.localdate()).count()
    if project:
        pr_high = ProjectRisk.objects.filter(
            project=project,
            risk_level=RiskLevel.YUKSEK,
        ).exclude(status=ProjectRiskStatus.TAMAMLANDI).first()
        if pr_high:
            notes.append(
                f"Yüksek riskli proje riski: {pr_high.title}; hedef tarihinden önce kapatılması önerilir."
            )
        blocked_uat = UATRecord.objects.filter(
            project=project,
            result_status__in=["Başarısız", "Bloke", "Tekrar Test Bekliyor"],
            severity=RiskLevel.YUKSEK,
        ).count()
        if blocked_uat:
            notes.append(
                "Bloke veya başarısız yüksek önemli UAT senaryoları tamamlanmadan canlı geçiş onayı verilmemelidir."
            )
        below = PostGoLiveMetric.objects.filter(project=project, status=MetricStatus.HEDEF_ALTI).first()
        if below:
            notes.append(
                f"Hedef altında kalan {below.metric_name} için destek ekibi kapasitesi gözden geçirilmelidir."
            )
    if high and len(notes) < 3:
        notes.append(f"{high} yüksek riskli açık talep acil sahiplenme gerektiriyor.")
    if overdue and len(notes) < 3:
        notes.append(f"{overdue} kayıt hedef tarihini aşmış durumda; kapanış planları gözden geçirilmeli.")
    if readiness and readiness.overall_status in ("Eksik", "Riskli") and len(notes) < 3:
        notes.append("Canlı geçiş hazırlığında eksik alanlar mevcut; önerilen adımlar uygulanmalı.")
    if not notes:
        notes.append("Proje genel olarak planlı ilerliyor; rutin takip yeterlidir.")
    return notes[:3]


def set_active_project(request, project_id):
    from core.context import set_active_context

    if not request.user.is_authenticated:
        return redirect("accounts:login")
    set_active_context(request, project_id=project_id)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_POST
def create_decision_from_suggestion(request):
    membership = get_user_membership(request)
    if not membership:
        return redirect("accounts:login")
    project = get_active_project(request)
    require_permission(can_manage_decision_records(request.user, project))
    if not project:
        return redirect("projects:decision_center")
    idx = int(request.POST.get("suggestion_index", -1))
    suggestions = get_pending_suggestions(project)
    if idx < 0 or idx >= len(suggestions):
        return redirect("projects:decision_center")
    item = suggestions[idx]
    decision = create_decision_if_new(
        project,
        source=item["source"],
        title=item["title"],
        finding=item["finding"],
        recommendation=item["recommendation"],
        expected_effect=item.get("expected_effect", ""),
        responsible_team=item.get("responsible_team", ""),
        due_date=item.get("due_date"),
        priority=item.get("priority", "Orta"),
        related_request=item.get("related_request"),
        related_project_risk=item.get("related_project_risk"),
        related_uat_record=item.get("related_uat_record"),
        related_post_go_live_metric=item.get("related_post_go_live_metric"),
        status=DecisionStatus.BEKLEMEDE,
    )
    if decision:
        log_audit(
            request.user,
            membership.organization,
            "Karar Destek Önerisi",
            "DecisionSupportRecord",
            decision.pk,
            decision.title,
            project,
        )
    return redirect("projects:decision_center")


@login_required
@require_POST
def create_decision_from_uat(request, pk):
    membership = get_user_membership(request)
    if not membership:
        return redirect("accounts:login")
    uat = get_object_or_404(UATRecord, pk=pk, project__in=_accessible_projects(request))
    require_permission(can_manage_decision_records(request.user, uat.project))
    decision = create_decision_if_new(
        uat.project,
        source=DecisionSource.UAT_BULGUSU,
        title=f"UAT: {uat.scenario_name}",
        finding=uat.actual_result or uat.expected_result,
        recommendation=uat.resolution_note or "UAT bulgusu için karar aksiyonu planlanmalı.",
        expected_effect="Canlı geçiş öncesi UAT güvencesi",
        responsible_team=uat.responsible_team,
        due_date=uat.test_date,
        related_uat_record=uat,
        related_request=uat.related_request,
        priority="Yüksek" if uat.severity == RiskLevel.YUKSEK else "Orta",
        status=DecisionStatus.BEKLEMEDE,
    )
    if decision:
        log_audit(
            request.user,
            membership.organization,
            "UAT Karar Kaydı",
            "DecisionSupportRecord",
            decision.pk,
            decision.title,
            uat.project,
        )
    return redirect("projects:decision_center")


@login_required
@require_POST
def update_uat_record(request, pk):
    membership = get_user_membership(request)
    if not membership:
        return redirect("accounts:login")
    uat = get_object_or_404(UATRecord, pk=pk, project__in=_accessible_projects(request))
    if request.POST.get("form_type") == "technical":
        require_permission(can_update_uat_technical(request.user, uat.project))
        form = UATTechnicalUpdateForm(request.POST, instance=uat)
    else:
        require_permission(can_manage_uat(request.user, uat.project))
        form = UATRecordForm(request.POST, instance=uat, project=uat.project)
    if form.is_valid():
        form.save()
        log_audit(
            request.user,
            membership.organization,
            "UAT Güncelleme",
            "UATRecord",
            uat.pk,
            uat.scenario_name,
            uat.project,
        )
    return redirect("/talep-yonetimi/?sekme=uat")
