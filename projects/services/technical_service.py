"""Teknik operasyon filtreleme ve KPI hesaplamaları."""

from django.db.models import Count, Q
from django.utils import timezone

from core.permissions import TEKNICAL_PROCESS_AREAS, TEKNICAL_TEAM_KEYWORDS, is_technical_request
from projects.models import (
    ProjectRisk,
    ProjectRiskStatus,
    RequestRecord,
    RequestStatus,
    RiskLevel,
    TECHNICAL_RISK_CATEGORIES,
    TechnicalStatus,
    UATRecord,
    UATResultStatus,
)


def technical_request_q():
    """Veritabanı düzeyinde teknik talep filtresi."""
    q = Q(process_area__in=TEKNICAL_PROCESS_AREAS)
    for kw in TEKNICAL_TEAM_KEYWORDS:
        q |= Q(responsible_team__icontains=kw)
    return q


def filter_technical_requests(qs):
    """QuerySet veya liste üzerinde teknik talep filtresi."""
    if hasattr(qs, "filter"):
        return qs.filter(technical_request_q())
    return [r for r in qs if is_technical_request(r)]


def _open_technical(qs):
    return filter_technical_requests(qs).exclude(status=RequestStatus.TAMAMLANDI)


def team_workload_counts(tech_qs):
    return (
        tech_qs.values("responsible_team")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


def technical_dashboard_stats(qs, project, user):
    """Teknik Operasyon Özeti KPI'ları."""
    open_tech = _open_technical(qs)
    today = timezone.localdate()
    uat_qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
    blocked_uat = uat_qs.filter(result_status=UATResultStatus.BLOKE).count()
    open_blocked = uat_qs.filter(
        result_status__in=[
            UATResultStatus.BASARISIZ,
            UATResultStatus.BLOKE,
            UATResultStatus.TEKRAR,
        ]
    ).count()
    assigned = open_tech.filter(Q(technical_owner=user) | Q(owner=user))
    bloke_tech = open_tech.filter(technical_status=TechnicalStatus.BLOKE)

    return {
        "kpi_open_technical": open_tech.count(),
        "kpi_high_risk_technical": open_tech.filter(risk_level=RiskLevel.YUKSEK).count(),
        "kpi_blocked_uat": blocked_uat,
        "kpi_open_uat_findings": open_blocked,
        "kpi_no_workaround": open_tech.filter(has_workaround=False).count(),
        "kpi_upcoming_technical": open_tech.filter(
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=7),
        ).count(),
        "kpi_assigned_open": assigned.count(),
        "kpi_bloke_technical": bloke_tech.count(),
        "kpi_root_cause_pending": open_tech.filter(
            root_cause_status__in=["", "Beklemede", "Analiz Ediliyor"]
        ).count(),
        "kpi_retest_pending": open_tech.filter(
            retest_status__in=["Bekliyor", "Planlandı"]
        ).count(),
        "awaiting_technical": open_tech.filter(
            status__in=[RequestStatus.ACIK, RequestStatus.DEVAM]
        ).order_by("-updated_at")[:10],
        "high_risk_technical": open_tech.filter(risk_level=RiskLevel.YUKSEK).order_by("due_date")[:8],
        "blocked_uat_list": uat_qs.filter(result_status=UATResultStatus.BLOKE).order_by("-severity")[:8],
        "no_workaround": open_tech.filter(has_workaround=False).order_by("-updated_at")[:8],
        "upcoming_technical": open_tech.filter(
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=7),
        ).order_by("due_date")[:8],
        "assigned_open": assigned.order_by("due_date")[:8],
        "team_workload": team_workload_counts(open_tech)[:6],
        "dashboard_mode": "technical_lead",
        # Geriye dönük şablon uyumluluğu
        "kpi_awaiting_technical": open_tech.filter(
            status__in=[RequestStatus.ACIK, RequestStatus.DEVAM]
        ).count(),
    }


def technical_work_list(qs, user=None, status=None, risk_level=None):
    """Teknik iş listesi."""
    tech_qs = _open_technical(qs).select_related("owner", "technical_owner", "project")
    if status:
        tech_qs = tech_qs.filter(status=status)
    if risk_level:
        tech_qs = tech_qs.filter(risk_level=risk_level)
    if user:
        tech_qs = tech_qs.filter(Q(technical_owner=user) | Q(owner=user))
    return tech_qs.order_by("-risk_level", "due_date", "-updated_at")


def technical_risks(project):
    """Teknik kategorideki proje riskleri."""
    if not project:
        return ProjectRisk.objects.none()
    return (
        ProjectRisk.objects.filter(project=project, category__in=TECHNICAL_RISK_CATEGORIES)
        .exclude(status__in=[ProjectRiskStatus.TAMAMLANDI, ProjectRiskStatus.IPTAL])
        .select_related("owner", "related_request")
        .order_by("-risk_level", "due_date")
    )


def technical_uat_findings(project):
    """Teknik UAT bulguları (salt okunur)."""
    if not project:
        return UATRecord.objects.none()
    return (
        UATRecord.objects.filter(
            project=project,
            result_status__in=[
                UATResultStatus.BASARISIZ,
                UATResultStatus.BLOKE,
                UATResultStatus.TEKRAR,
            ],
        )
        .select_related("related_request")
        .order_by("-severity", "-test_date")
    )


def technical_actions(project, user):
    """Teknik aksiyon gerektiren kayıtlar."""
    if not project:
        return RequestRecord.objects.none()
    qs = _open_technical(RequestRecord.objects.filter(project=project))
    return qs.filter(
        Q(recommended_action__gt="")
        | Q(technical_status=TechnicalStatus.BLOKE)
        | Q(technical_status=TechnicalStatus.TEST)
        | Q(technical_owner=user)
        | Q(owner=user, risk_level=RiskLevel.YUKSEK)
    ).select_related("owner", "technical_owner").distinct().order_by("-risk_level", "due_date")
