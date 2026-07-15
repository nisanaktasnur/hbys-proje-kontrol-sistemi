from dataclasses import dataclass, field
from datetime import date

from django.conf import settings
from django.utils import timezone


@dataclass
class RiskResult:
    internal_score: int
    risk_level: str
    evaluated_factors: list = field(default_factory=list)
    evaluation_note: str = ""
    recommended_action: str = ""


def _impact_value(label: str) -> int:
    return settings.RISK_ENGINE["IMPACT_VALUES"].get(label, 1)


def _priority_value(label: str) -> int:
    return settings.RISK_ENGINE["PRIORITY_VALUES"].get(label, 1)


def _level_from_score(score: int) -> str:
    thresholds = settings.RISK_ENGINE["THRESHOLDS"]
    if score >= thresholds["high"]:
        return "Yüksek"
    if score >= thresholds["medium"]:
        return "Orta"
    return "Düşük"


def calculate_risk(
    *,
    priority: str,
    go_live_impact: str,
    affects_patient_or_user_safety: str,
    operational_impact: str,
    has_workaround: bool,
    due_date: date | None,
    status: str,
    created_at=None,
    process_area: str = "",
    process_open_count: int = 0,
) -> RiskResult:
    weights = settings.RISK_ENGINE["WEIGHTS"]
    factors = []
    raw = 0.0

    priority_val = _priority_value(priority)
    contrib = priority_val * weights["priority"]
    raw += contrib
    factors.append({"unsur": "Öncelik", "deger": priority, "etki": "yüksek" if priority_val >= 3 else "orta"})

    gl_val = _impact_value(go_live_impact)
    raw += gl_val * weights["go_live_impact"]
    factors.append({"unsur": "Canlı Geçiş Etkisi", "deger": go_live_impact, "etki": "yüksek" if gl_val >= 3 else "orta"})

    safety_val = _impact_value(affects_patient_or_user_safety)
    raw += safety_val * weights["patient_safety"]
    factors.append({
        "unsur": "Kullanıcı/Hasta Güvenliği",
        "deger": affects_patient_or_user_safety,
        "etki": "yüksek" if safety_val >= 3 else "düşük",
    })

    op_val = _impact_value(operational_impact)
    raw += op_val * weights["operational_impact"]
    factors.append({"unsur": "Operasyonel Etki", "deger": operational_impact, "etki": "yüksek" if op_val >= 3 else "orta"})

    if not has_workaround:
        raw += 3 * weights["workaround_missing"]
        factors.append({"unsur": "Geçici Çözüm", "deger": "Yok", "etki": "yüksek"})

    overdue = False
    if due_date and status != "Tamamlandı" and due_date < timezone.localdate():
        raw += 3 * weights["overdue"]
        overdue = True
        factors.append({"unsur": "Hedef Tarih", "deger": "Aşıldı", "etki": "yüksek"})

    if status in ("Açık", "Devam Ediyor"):
        raw += 2 * weights["open_status"]
        factors.append({"unsur": "Kayıt Durumu", "deger": status, "etki": "orta"})

    if created_at:
        age_days = (timezone.now() - created_at).days
        if age_days > 30:
            raw += min(3, age_days / 30) * weights["record_age"]
            factors.append({"unsur": "Kayıt Yaşı", "deger": f"{age_days} gün", "etki": "orta"})

    if process_open_count >= 5:
        raw += min(3, process_open_count / 5) * weights["process_density"]
        factors.append({
            "unsur": "Süreç Yoğunluğu",
            "deger": f"{process_area} ({process_open_count} açık)",
            "etki": "yüksek",
        })

    max_raw = sum(weights.values()) * 4
    internal_score = min(100, round((raw / max_raw) * 100))
    risk_level = _level_from_score(internal_score)

    high_factors = [f for f in factors if f["etki"] == "yüksek"]
    note_parts = []
    if risk_level == "Yüksek":
        note_parts.append("Bu kayıt yüksek riskli olarak değerlendirilmiştir.")
    elif risk_level == "Orta":
        note_parts.append("Bu kayıt orta riskli olarak değerlendirilmiştir.")
    else:
        note_parts.append("Bu kayıt düşük riskli olarak değerlendirilmiştir.")

    reasons = []
    if safety_val >= 3:
        reasons.append("kullanıcı güvenliği etkisinin yüksek olması")
    if op_val >= 3:
        reasons.append("operasyonel etki düzeyinin yüksek olması")
    if not has_workaround:
        reasons.append("geçici çözüm bulunmaması")
    if overdue:
        reasons.append("hedef tarihin aşılması")
    if gl_val >= 3:
        reasons.append("canlı geçiş etkisinin yüksek olması")

    if reasons:
        note_parts.append(
            " " + ", ".join(reasons) + " nedeniyle "
            + ("öncelikli takip önerilir." if risk_level != "Düşük" else "izleme yeterlidir.")
        )

    evaluation_note = "".join(note_parts)

    if risk_level == "Yüksek":
        recommended = "Kayıt acil olarak sahiplenilmeli, sorumlu ekip ile aksiyon planı oluşturulmalıdır."
    elif risk_level == "Orta":
        recommended = "Kayıt planlı takip listesine alınmalı ve hedef tarih gözden geçirilmelidir."
    else:
        recommended = "Rutin takip yeterlidir; durum değişirse yeniden değerlendirilmelidir."

    return RiskResult(
        internal_score=internal_score,
        risk_level=risk_level,
        evaluated_factors=factors,
        evaluation_note=evaluation_note,
        recommended_action=recommended,
    )


def apply_risk_to_request(request_record, process_open_count=0):
    result = calculate_risk(
        priority=request_record.priority,
        go_live_impact=request_record.go_live_impact,
        affects_patient_or_user_safety=request_record.affects_patient_or_user_safety,
        operational_impact=request_record.operational_impact,
        has_workaround=request_record.has_workaround,
        due_date=request_record.due_date,
        status=request_record.status,
        created_at=request_record.created_at,
        process_area=request_record.process_area,
        process_open_count=process_open_count,
    )
    request_record.internal_risk_score = result.internal_score
    request_record.risk_level = result.risk_level
    request_record.evaluated_factors = result.evaluated_factors
    request_record.evaluation_note = result.evaluation_note
    request_record.recommended_action = result.recommended_action
    return result
