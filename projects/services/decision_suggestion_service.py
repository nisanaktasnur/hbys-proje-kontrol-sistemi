"""Karar destek önerileri ve yinelenen kayıt kontrolü."""

from django.utils import timezone

from projects.models import DecisionSource, DecisionStatus, DecisionSupportRecord, MetricStatus, ProjectRiskStatus, RequestStatus, RiskLevel, UATResultStatus


def build_decision_source_key(decision) -> str:
    parts = [decision.source or ""]
    for attr in (
        "related_request_id",
        "related_project_risk_id",
        "related_uat_record_id",
        "related_post_go_live_metric_id",
    ):
        val = getattr(decision, attr, None)
        if val:
            parts.append(f"{attr}:{val}")
    title_key = (decision.title or "").strip().lower()[:80]
    if title_key:
        parts.append(f"title:{title_key}")
    return "|".join(parts)


def decision_already_exists(project, source_key: str) -> bool:
    if not source_key:
        return False
    return DecisionSupportRecord.objects.filter(
        project=project,
        source_key=source_key,
    ).exclude(status=DecisionStatus.TAMAMLANDI).exclude(status=DecisionStatus.IPTAL).exists()


def create_decision_if_new(project, **fields):
    decision = DecisionSupportRecord(project=project, **fields)
    key = build_decision_source_key(decision)
    if decision_already_exists(project, key):
        return None
    decision.source_key = key
    decision.save()
    return decision


def suggest_decisions(project):
    """Yüksek proje riskleri, UAT bulguları, hedef altı metrikler ve geciken talepler için öneri listesi."""
    suggestions = []
    from projects.models import PostGoLiveMetric, ProjectRisk, RequestRecord, UATRecord

    for risk in ProjectRisk.objects.filter(
        project=project,
        risk_level=RiskLevel.YUKSEK,
    ).exclude(status=ProjectRiskStatus.TAMAMLANDI):
        suggestions.append({
            "source": DecisionSource.PROJE_RISKI,
            "title": f"Proje riski: {risk.title}",
            "finding": risk.description,
            "recommendation": risk.mitigation_action or "Önleyici aksiyon planlanmalı.",
            "expected_effect": "Proje risk seviyesinin düşürülmesi",
            "responsible_team": risk.owner.get_full_name() if risk.owner else "",
            "due_date": risk.due_date,
            "related_project_risk": risk,
            "priority": "Yüksek",
        })

    for uat in UATRecord.objects.filter(
        project=project,
        result_status__in=[UATResultStatus.BASARISIZ, UATResultStatus.BLOKE, UATResultStatus.TEKRAR],
    ):
        suggestions.append({
            "source": DecisionSource.UAT_BULGUSU,
            "title": f"UAT: {uat.scenario_name}",
            "finding": uat.actual_result or uat.expected_result,
            "recommendation": uat.resolution_note or "UAT bulgusu kapatılmalı veya tekrar test edilmeli.",
            "expected_effect": "Canlı geçiş öncesi UAT güvencesi",
            "responsible_team": uat.responsible_team,
            "due_date": uat.test_date,
            "related_uat_record": uat,
            "related_request": uat.related_request,
            "priority": "Yüksek" if uat.severity == RiskLevel.YUKSEK else "Orta",
        })

    for metric in PostGoLiveMetric.objects.filter(project=project, status=MetricStatus.HEDEF_ALTI):
        suggestions.append({
            "source": DecisionSource.CANLI_GECIS_METRIK,
            "title": f"Gösterge: {metric.metric_name}",
            "finding": metric.evaluation_note or f"Güncel: {metric.current_value}, Hedef: {metric.target_value}",
            "recommendation": "Hedef altındaki gösterge için iyileştirme planı oluşturulmalı.",
            "expected_effect": "Canlı geçiş sonrası performans hedeflerine dönüş",
            "responsible_team": metric.responsible_team,
            "due_date": metric.measurement_date,
            "related_post_go_live_metric": metric,
            "priority": "Orta",
        })

    today = timezone.localdate()
    for req in RequestRecord.objects.filter(
        project=project,
        due_date__lt=today,
    ).exclude(status=RequestStatus.TAMAMLANDI)[:5]:
        suggestions.append({
            "source": DecisionSource.TALEP,
            "title": f"Geciken talep: {req.record_number}",
            "finding": req.title,
            "recommendation": req.recommended_action or "Talep kapanış planı gözden geçirilmeli.",
            "expected_effect": "Proje takvimine uyum",
            "responsible_team": req.responsible_team,
            "due_date": req.due_date,
            "related_request": req,
            "priority": req.priority,
        })

    return suggestions


def get_pending_suggestions(project):
    pending = []
    for item in suggest_decisions(project):
        probe = DecisionSupportRecord(
            project=project,
            source=item["source"],
            title=item["title"],
            finding=item["finding"],
            recommendation=item["recommendation"],
            related_request=item.get("related_request"),
            related_project_risk=item.get("related_project_risk"),
            related_uat_record=item.get("related_uat_record"),
            related_post_go_live_metric=item.get("related_post_go_live_metric"),
        )
        if not decision_already_exists(project, build_decision_source_key(probe)):
            pending.append(item)
    return pending
