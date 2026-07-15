"""Yönetici paneli stratejik KPI hesaplamaları."""

from django.db.models import Count, Q
from django.utils import timezone

from projects.models import (
    DecisionStatus,
    DecisionSupportRecord,
    GoLiveReadiness,
    MetricStatus,
    PostGoLiveMetric,
    ProjectRisk,
    ProjectRiskStatus,
    ReadinessStatus,
    RequestStatus,
    RiskLevel,
    UATRecord,
    UATResultStatus,
)


def _open_requests(qs):
    return qs.exclude(status=RequestStatus.TAMAMLANDI)


def _compute_go_live_decision(project, readiness, open_qs, uat_qs, pr_qs):
    """Canlı geçiş kararı: Hazır / Dikkat Gerekli / Hazır Değil / Devam Ediyor."""
    if not project:
        return "—"

    blocking_uat = uat_qs.filter(
        result_status__in=[
            UATResultStatus.BASARISIZ,
            UATResultStatus.BLOKE,
            UATResultStatus.TEKRAR,
        ],
        severity=RiskLevel.YUKSEK,
    ).count()
    critical_risks = pr_qs.filter(risk_level=RiskLevel.YUKSEK).exclude(
        status__in=[ProjectRiskStatus.TAMAMLANDI, ProjectRiskStatus.IPTAL]
    ).count()
    high_requests = open_qs.filter(risk_level=RiskLevel.YUKSEK).count()
    overdue = open_qs.filter(due_date__lt=timezone.localdate()).count()
    below_metrics = PostGoLiveMetric.objects.filter(
        project=project, status=MetricStatus.HEDEF_ALTI
    ).exists()

    if blocking_uat or critical_risks >= 3 or (high_requests >= 5 and overdue >= 3):
        return "Hazır Değil"
    if readiness and readiness.overall_status in (ReadinessStatus.TAMAMLANDI,):
        if blocking_uat == 0 and critical_risks == 0:
            return "Hazır"
    if (
        blocking_uat
        or critical_risks
        or high_requests >= 3
        or overdue >= 2
        or below_metrics
        or (readiness and readiness.overall_status in (ReadinessStatus.EKSIK, ReadinessStatus.RISKLI))
    ):
        return "Dikkat Gerekli"
    if readiness and readiness.overall_status == ReadinessStatus.DEVAM:
        return "Devam Ediyor"
    if project.status in ("Planlama", "Uygulama", "UAT"):
        return "Devam Ediyor"
    return "Dikkat Gerekli"


def manager_strategic_summary(qs, project, readiness=None):
    """Yönetici paneli için stratejik özet KPI'ları."""
    open_qs = _open_requests(qs)
    uat_qs = UATRecord.objects.filter(project=project) if project else UATRecord.objects.none()
    pr_qs = ProjectRisk.objects.filter(project=project) if project else ProjectRisk.objects.none()
    open_pr = pr_qs.exclude(status__in=[ProjectRiskStatus.TAMAMLANDI, ProjectRiskStatus.IPTAL])

    critical_risk_count = (
        open_pr.filter(risk_level=RiskLevel.YUKSEK).count()
        + open_qs.filter(risk_level=RiskLevel.YUKSEK).count()
    )
    blocking_uat = uat_qs.filter(
        result_status__in=[
            UATResultStatus.BASARISIZ,
            UATResultStatus.BLOKE,
            UATResultStatus.TEKRAR,
        ]
    ).count()
    overdue_decisions = (
        DecisionSupportRecord.objects.filter(
            project=project,
            due_date__lt=timezone.localdate(),
        ).exclude(status=DecisionStatus.TAMAMLANDI).count()
        if project
        else 0
    )

    go_live_decision = _compute_go_live_decision(project, readiness, open_qs, uat_qs, pr_qs)

    strategic_notes = []
    if critical_risk_count:
        strategic_notes.append(
            f"{critical_risk_count} kritik risk kaydı canlı geçiş kararını etkileyebilir."
        )
    if blocking_uat:
        strategic_notes.append(
            f"{blocking_uat} açık UAT bulgusu teknik güvence açısından değerlendirilmelidir."
        )
    if overdue_decisions:
        strategic_notes.append(
            f"{overdue_decisions} geciken karar destek aksiyonu yönetim takibi gerektirir."
        )
    if readiness and readiness.recommended_next_step:
        strategic_notes.append(readiness.recommended_next_step)
    if not strategic_notes:
        strategic_notes.append("Proje genel olarak planlı ilerliyor; rutin stratejik izleme yeterlidir.")

    return {
        "project_status": project.status if project else "—",
        "go_live_decision": go_live_decision,
        "go_live_status": readiness.overall_status if readiness else "—",
        "critical_risk_count": critical_risk_count,
        "open_count": open_qs.count(),
        "high_risk_requests": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "overdue_requests": open_qs.filter(due_date__lt=timezone.localdate()).count(),
        "blocking_uat": blocking_uat,
        "overdue_decisions": overdue_decisions,
        "top_project_risks": open_pr.filter(risk_level=RiskLevel.YUKSEK).order_by("due_date")[:5],
        "priority_decisions": (
            DecisionSupportRecord.objects.filter(project=project)
            .exclude(status=DecisionStatus.TAMAMLANDI)
            .order_by("due_date")[:8]
            if project
            else []
        ),
        "team_workload": (
            open_qs.values("responsible_team")
            .annotate(count=Count("id"))
            .order_by("-count")[:6]
        ),
        "strategic_notes": strategic_notes[:4],
        "readiness": readiness,
        "dashboard_mode": "manager_strategic",
    }
