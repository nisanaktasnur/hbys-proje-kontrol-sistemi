"""Rol bazlı özet kartları ve KPI hesaplamaları."""

from django.db.models import Count, Q
from django.utils import timezone

from core.permissions import TEKNIK_EKIP_LABEL
from projects.models import (
    DecisionStatus,
    DecisionSupportRecord,
    GoLiveReadiness,
    MetricStatus,
    PostGoLiveMetric,
    ProjectRisk,
    ProjectRiskStatus,
    RequestRecord,
    RequestStatus,
    RiskLevel,
    UATRecord,
)


def _open_requests(qs):
    return qs.exclude(status=RequestStatus.TAMAMLANDI)


def admin_dashboard_stats(organization):
    from accounts.models import ApprovalStatus, Membership, UserProfile
    from core.models import AuditLog, Organization, Project

    org = organization
    pending = UserProfile.objects.filter(
        approval_status=ApprovalStatus.PENDING,
        user__memberships__organization=org,
    ).distinct().count()
    active_users = Membership.objects.filter(organization=org, is_active=True).count()
    inactive_users = Membership.objects.filter(organization=org, is_active=False).count()
    active_orgs = Organization.objects.filter(is_active=True).count()
    active_projects = Project.objects.filter(organization=org, status__in=[
        "Planlama", "Uygulama", "UAT", "Canlı Geçiş",
    ]).count()
    recent_audit = AuditLog.objects.filter(organization=org).select_related("user")[:12]
    role_distribution = (
        Membership.objects.filter(organization=org, is_active=True)
        .values("role")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    pending_profiles = UserProfile.objects.filter(
        approval_status=ApprovalStatus.PENDING,
        user__memberships__organization=org,
    ).select_related("user").distinct()[:8]
    return {
        "pending_users": pending,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "active_orgs": active_orgs,
        "active_projects": active_projects,
        "recent_audit": recent_audit,
        "role_distribution": role_distribution,
        "pending_profiles": pending_profiles,
        "dashboard_mode": "admin",
    }


def project_manager_dashboard_stats(qs, project, readiness):
    open_qs = _open_requests(qs)
    today = timezone.localdate()
    uat_qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
    open_uat = uat_qs.filter(
        result_status__in=["Başarısız", "Bloke", "Tekrar Test Bekliyor"]
    ).count()
    return {
        "today_follow_up": open_qs.filter(due_date=today).order_by("due_date")[:8],
        "overdue_records": open_qs.filter(due_date__lt=today).order_by("due_date")[:8],
        "high_risk_requests": open_qs.filter(risk_level=RiskLevel.YUKSEK).order_by("-updated_at")[:8],
        "open_uat_findings": open_uat,
        "go_live_status": readiness.overall_status if readiness else "—",
        "team_workload": (
            open_qs.values("responsible_team")
            .annotate(count=Count("id"))
            .order_by("-count")[:6]
        ),
        "upcoming_due": open_qs.filter(due_date__gte=today).order_by("due_date")[:8],
        "recent_requests": qs.order_by("-created_at")[:8],
        "dashboard_mode": "project_manager",
    }


def technical_lead_dashboard_stats(qs, project, user):
    open_qs = _open_requests(qs)
    today = timezone.localdate()
    tech_qs = open_qs.filter(
        Q(responsible_team__icontains=TEKNIK_EKIP_LABEL) | Q(owner=user)
    )
    uat_qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
    blocked_uat = uat_qs.filter(result_status="Bloke").count()
    return {
        "awaiting_technical": tech_qs.filter(
            status__in=[RequestStatus.ACIK, RequestStatus.DEVAM]
        ).order_by("-updated_at")[:10],
        "high_risk_technical": tech_qs.filter(risk_level=RiskLevel.YUKSEK).order_by("due_date")[:8],
        "blocked_uat": blocked_uat,
        "no_workaround": tech_qs.filter(has_workaround=False).order_by("-updated_at")[:8],
        "upcoming_technical": tech_qs.filter(
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=7),
        ).order_by("due_date")[:8],
        "assigned_open": tech_qs.filter(owner=user).order_by("due_date")[:8],
        "kpi_awaiting_technical": tech_qs.filter(
            status__in=[RequestStatus.ACIK, RequestStatus.DEVAM]
        ).count(),
        "kpi_high_risk_technical": tech_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "kpi_blocked_uat": blocked_uat,
        "kpi_no_workaround": tech_qs.filter(has_workaround=False).count(),
        "kpi_upcoming_technical": tech_qs.filter(
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=7),
        ).count(),
        "kpi_assigned_open": tech_qs.filter(owner=user).count(),
        "dashboard_mode": "technical_lead",
    }


def executive_dashboard_stats(qs, project, readiness):
    open_qs = _open_requests(qs)
    pr_qs = ProjectRisk.objects.filter(project=project) if project else ProjectRisk.objects.none()
    top_risks = pr_qs.exclude(status=ProjectRiskStatus.TAMAMLANDI).order_by("-risk_level", "due_date")[:3]
    uat_qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
    blocking_uat = uat_qs.filter(
        result_status__in=["Başarısız", "Bloke", "Tekrar Test Bekliyor"]
    ).order_by("-severity")[:5]
    below_metrics = (
        PostGoLiveMetric.objects.filter(project=project, status=MetricStatus.HEDEF_ALTI)
        if project
        else PostGoLiveMetric.objects.none()
    )
    overdue_decisions = (
        DecisionSupportRecord.objects.filter(
            project=project,
            due_date__lt=timezone.localdate(),
        ).exclude(status=DecisionStatus.TAMAMLANDI)
        if project
        else DecisionSupportRecord.objects.none()
    )
    return {
        "project_status": project.status if project else "—",
        "top_risks": top_risks,
        "go_live_status": readiness.overall_status if readiness else "—",
        "blocking_uat": blocking_uat,
        "below_metrics": below_metrics[:5],
        "overdue_decisions": overdue_decisions[:8],
        "team_workload": (
            open_qs.values("responsible_team")
            .annotate(count=Count("id"))
            .order_by("-count")[:6]
        ),
        "open_count": open_qs.count(),
        "high_risk": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "dashboard_mode": "executive",
    }


def default_request_filters_for_role(role, user):
    from accounts.models import Role

    if role != Role.TEKNIK_LIDER:
        return {}
    return {
        "responsible_team": TEKNIK_EKIP_LABEL,
        "status": RequestStatus.ACIK,
        "risk_level": RiskLevel.YUKSEK,
        "owner": user.pk,
        "apply_defaults": True,
    }
