from datetime import date, timedelta

import pytest
from django.conf import settings

from projects.services.risk_service import calculate_risk, _level_from_score


def test_level_from_score_boundaries():
    thresholds = settings.RISK_ENGINE["THRESHOLDS"]
    assert _level_from_score(thresholds["medium"] - 1) == "Düşük"
    assert _level_from_score(thresholds["medium"]) == "Orta"
    assert _level_from_score(thresholds["high"] - 1) == "Orta"
    assert _level_from_score(thresholds["high"]) == "Yüksek"


def test_low_risk_record():
    result = calculate_risk(
        priority="Düşük",
        go_live_impact="Düşük",
        affects_patient_or_user_safety="Düşük",
        operational_impact="Düşük",
        has_workaround=True,
        due_date=date.today() + timedelta(days=14),
        status="Tamamlandı",
    )
    assert result.risk_level == "Düşük"
    assert 0 <= result.internal_score <= 100


def test_high_risk_record():
    result = calculate_risk(
        priority="Acil",
        go_live_impact="Yüksek",
        affects_patient_or_user_safety="Yüksek",
        operational_impact="Yüksek",
        has_workaround=False,
        due_date=date.today() - timedelta(days=3),
        status="Açık",
    )
    assert result.risk_level == "Yüksek"


def test_medium_risk_record():
    result = calculate_risk(
        priority="Yüksek",
        go_live_impact="Orta",
        affects_patient_or_user_safety="Orta",
        operational_impact="Orta",
        has_workaround=False,
        due_date=date.today() + timedelta(days=5),
        status="Devam Ediyor",
    )
    thresholds = settings.RISK_ENGINE["THRESHOLDS"]
    assert thresholds["medium"] <= result.internal_score < thresholds["high"]
    assert result.risk_level == "Orta"


def test_overdue_increases_risk():
    base = calculate_risk(
        priority="Orta",
        go_live_impact="Orta",
        affects_patient_or_user_safety="Orta",
        operational_impact="Orta",
        has_workaround=True,
        due_date=date.today() + timedelta(days=5),
        status="Açık",
    )
    overdue = calculate_risk(
        priority="Orta",
        go_live_impact="Orta",
        affects_patient_or_user_safety="Orta",
        operational_impact="Orta",
        has_workaround=True,
        due_date=date.today() - timedelta(days=1),
        status="Açık",
    )
    assert overdue.internal_score >= base.internal_score


def test_missing_workaround_increases_risk():
    with_w = calculate_risk(
        priority="Orta",
        go_live_impact="Orta",
        affects_patient_or_user_safety="Orta",
        operational_impact="Orta",
        has_workaround=True,
        due_date=date.today() + timedelta(days=5),
        status="Açık",
    )
    without = calculate_risk(
        priority="Orta",
        go_live_impact="Orta",
        affects_patient_or_user_safety="Orta",
        operational_impact="Orta",
        has_workaround=False,
        due_date=date.today() + timedelta(days=5),
        status="Açık",
    )
    assert without.internal_score > with_w.internal_score


def test_go_live_impact():
    low = calculate_risk(
        priority="Orta",
        go_live_impact="Düşük",
        affects_patient_or_user_safety="Düşük",
        operational_impact="Düşük",
        has_workaround=True,
        due_date=date.today() + timedelta(days=10),
        status="Açık",
    )
    high = calculate_risk(
        priority="Orta",
        go_live_impact="Yüksek",
        affects_patient_or_user_safety="Düşük",
        operational_impact="Düşük",
        has_workaround=True,
        due_date=date.today() + timedelta(days=10),
        status="Açık",
    )
    assert high.internal_score > low.internal_score
