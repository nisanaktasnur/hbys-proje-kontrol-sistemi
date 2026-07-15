"""Proje risk matrisi hesaplama servisi."""

from django.db.models import Q

from projects.models import RiskLevel

_LEVEL_INDEX = {
    RiskLevel.DUSUK: 0,
    RiskLevel.ORTA: 1,
    RiskLevel.YUKSEK: 2,
}

_MATRIX = (
    (RiskLevel.DUSUK, RiskLevel.DUSUK, RiskLevel.ORTA),
    (RiskLevel.DUSUK, RiskLevel.ORTA, RiskLevel.YUKSEK),
    (RiskLevel.ORTA, RiskLevel.YUKSEK, RiskLevel.YUKSEK),
)


def calculate_project_risk_level(probability: str, impact: str) -> str:
    prob_idx = _LEVEL_INDEX.get(probability)
    impact_idx = _LEVEL_INDEX.get(impact)
    if prob_idx is None or impact_idx is None:
        return RiskLevel.ORTA
    return _MATRIX[prob_idx][impact_idx]


def build_matrix_counts(project_risks_qs):
    """3x3 matris hücre sayıları — yalnızca açık proje riskleri."""
    open_qs = project_risks_qs.exclude(status="Tamamlandı").exclude(status="İptal")
    cells = {}
    for prob in RiskLevel.values:
        for impact in RiskLevel.values:
            key = f"{prob}|{impact}"
            cells[key] = open_qs.filter(probability=prob, impact=impact).count()
    return cells


def project_risk_summary(project_risks_qs):
    from django.utils import timezone

    open_qs = project_risks_qs.exclude(status="Tamamlandı").exclude(status="İptal")
    today = timezone.localdate()
    cells = build_matrix_counts(project_risks_qs)
    matrix_rows = []
    for impact in reversed(RiskLevel.values):
        row = {"impact": impact, "cells": []}
        for prob in RiskLevel.values:
            key = f"{prob}|{impact}"
            row["cells"].append({
                "probability": prob,
                "impact": impact,
                "level": calculate_project_risk_level(prob, impact),
                "count": cells.get(key, 0),
            })
        matrix_rows.append(row)
    return {
        "low": open_qs.filter(risk_level=RiskLevel.DUSUK).count(),
        "medium": open_qs.filter(risk_level=RiskLevel.ORTA).count(),
        "high": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "overdue_actions": open_qs.filter(due_date__lt=today).count(),
        "matrix_cells": cells,
        "matrix_rows": matrix_rows,
    }


def matrix_risk_details(project_risks_qs, categories=None):
    """Matris hücrelerine göre risk listeleri — yalnızca dolu hücreler."""
    open_qs = project_risks_qs.exclude(status="Tamamlandı").exclude(status="İptal")
    if categories:
        open_qs = open_qs.filter(category__in=categories)
    groups = []
    for impact in reversed(RiskLevel.values):
        for prob in RiskLevel.values:
            risks = list(
                open_qs.filter(probability=prob, impact=impact)
                .select_related("owner", "owner__profile", "related_request")
                .order_by("-risk_level", "due_date")
            )
            if risks:
                groups.append({
                    "title": f"{prob} Olasılık / {impact} Etki",
                    "probability": prob,
                    "impact": impact,
                    "level": calculate_project_risk_level(prob, impact),
                    "count": len(risks),
                    "risks": risks,
                })
    return groups


def high_risks_without_action(project_risks_qs, categories=None):
    qs = project_risks_qs.filter(risk_level=RiskLevel.YUKSEK).exclude(
        status="Tamamlandı"
    ).exclude(status="İptal")
    if categories:
        qs = qs.filter(category__in=categories)
    return qs.filter(
        Q(mitigation_action="") | Q(mitigation_action__isnull=True)
    ).select_related("owner", "related_request")
