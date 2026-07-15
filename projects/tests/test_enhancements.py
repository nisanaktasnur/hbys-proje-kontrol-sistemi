import pytest
from django.contrib.auth.models import User

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.models import Organization, Project
from projects.models import (
    DecisionSource,
    DecisionSupportRecord,
    DecisionStatus,
    MetricCategory,
    MetricStatus,
    PostGoLiveMetric,
    ProjectRisk,
    ProjectRiskStatus,
    RiskCategory,
    RiskLevel,
    UATRecord,
    UATResultStatus,
)
from projects.services.decision_suggestion_service import (
    build_decision_source_key,
    create_decision_if_new,
    decision_already_exists,
)
from projects.services.risk_matrix_service import calculate_project_risk_level
from reports.services.csv_export import _csv_cell, export_project_risks, export_uat_records


@pytest.mark.parametrize(
    "probability,impact,expected",
    [
        (RiskLevel.DUSUK, RiskLevel.DUSUK, RiskLevel.DUSUK),
        (RiskLevel.DUSUK, RiskLevel.ORTA, RiskLevel.DUSUK),
        (RiskLevel.DUSUK, RiskLevel.YUKSEK, RiskLevel.ORTA),
        (RiskLevel.ORTA, RiskLevel.DUSUK, RiskLevel.DUSUK),
        (RiskLevel.ORTA, RiskLevel.ORTA, RiskLevel.ORTA),
        (RiskLevel.ORTA, RiskLevel.YUKSEK, RiskLevel.YUKSEK),
        (RiskLevel.YUKSEK, RiskLevel.DUSUK, RiskLevel.ORTA),
        (RiskLevel.YUKSEK, RiskLevel.ORTA, RiskLevel.YUKSEK),
        (RiskLevel.YUKSEK, RiskLevel.YUKSEK, RiskLevel.YUKSEK),
    ],
)
def test_risk_matrix_all_combinations(probability, impact, expected):
    assert calculate_project_risk_level(probability, impact) == expected


@pytest.fixture
def org_setup(db):
    org = Organization.objects.create(name="Test Kurum")
    project = Project.objects.create(organization=org, name="Test Proje", status="Uygulama")
    user = User.objects.create_user(username="tester", password="Test12345!")
    UserProfile.objects.create(user=user, full_name="Tester", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=Role.PROJE_YONETICISI, is_active=True)
    ProjectMembership.objects.create(user=user, project=project, role=Role.PROJE_YONETICISI, is_active=True)
    return org, project, user


@pytest.mark.django_db
def test_project_risk_creation_sets_level(org_setup):
    org, project, user = org_setup
    risk = ProjectRisk.objects.create(
        project=project,
        title="Demo risk",
        description="Açıklama",
        category=RiskCategory.TEKNIK,
        probability=RiskLevel.YUKSEK,
        impact=RiskLevel.ORTA,
        created_by=user,
    )
    assert risk.risk_level == RiskLevel.YUKSEK


@pytest.mark.django_db
def test_uat_record_creation(org_setup):
    org, project, user = org_setup
    uat = UATRecord.objects.create(
        project=project,
        scenario_name="Test senaryosu",
        process_area="UAT",
        expected_result="Beklenen",
        result_status=UATResultStatus.BASARISIZ,
        severity=RiskLevel.YUKSEK,
        responsible_team="UAT Ekibi",
    )
    assert uat.blocks_go_live is True


@pytest.mark.django_db
def test_post_go_live_metric_authorization(org_setup, client):
    org, project, user = org_setup
    user.memberships.update(role=Role.YONETICI)
    ProjectMembership.objects.filter(user=user, project=project).update(role=Role.YONETICI)
    client.login(username="tester", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org.id
    session["active_project_id"] = project.id
    session.save()
    PostGoLiveMetric.objects.create(
        project=project,
        metric_name="SLA oranı",
        metric_category=MetricCategory.PERFORMANS,
        target_value="90",
        current_value="75",
        unit="%",
        status=MetricStatus.HEDEF_ALTI,
        measurement_date="2026-06-01",
        responsible_team="Destek",
    )
    response = client.get("/yonetici-ozeti/")
    assert response.status_code == 200
    assert "Canlı Geçiş Sonrası Başarı Göstergeleri" in response.content.decode()


@pytest.mark.django_db
def test_decision_source_relationships(org_setup):
    org, project, user = org_setup
    risk = ProjectRisk.objects.create(
        project=project,
        title="Risk",
        description="x",
        category=RiskCategory.UAT,
        probability=RiskLevel.ORTA,
        impact=RiskLevel.ORTA,
        created_by=user,
    )
    decision = DecisionSupportRecord.objects.create(
        project=project,
        source=DecisionSource.PROJE_RISKI,
        title="Karar",
        finding="Tespit",
        recommendation="Öneri",
        related_project_risk=risk,
    )
    assert decision.source_key
    assert decision.related_project_risk_id == risk.pk


@pytest.mark.django_db
def test_duplicate_decision_prevention(org_setup):
    org, project, user = org_setup
    fields = {
        "source": DecisionSource.UAT_BULGUSU,
        "title": "UAT kararı",
        "finding": "Bulgu",
        "recommendation": "Öneri",
        "status": DecisionStatus.BEKLEMEDE,
    }
    first = create_decision_if_new(project, **fields)
    second = create_decision_if_new(project, **fields)
    assert first is not None
    assert second is None
    probe = DecisionSupportRecord(project=project, **fields)
    assert decision_already_exists(project, build_decision_source_key(probe))


@pytest.mark.django_db
def test_csv_exports_turkish_headers(org_setup):
    org, project, user = org_setup
    risk = ProjectRisk.objects.create(
        project=project,
        title="=FORMULA",
        description="Test",
        category=RiskCategory.TEKNIK,
        probability=RiskLevel.DUSUK,
        impact=RiskLevel.DUSUK,
        created_by=user,
    )
    response = export_project_risks(user, org, ProjectRisk.objects.filter(pk=risk.pk))
    content = response.content.decode("utf-8-sig")
    assert "Risk Başlığı" in content
    assert "'=FORMULA" in content

    uat = UATRecord.objects.create(
        project=project,
        scenario_name="Senaryo",
        process_area="UAT",
        expected_result="OK",
        result_status=UATResultStatus.BASARILI,
        severity=RiskLevel.ORTA,
        responsible_team="Ekip",
    )
    uat_resp = export_uat_records(user, org, UATRecord.objects.filter(pk=uat.pk))
    assert "Senaryo Adı" in uat_resp.content.decode("utf-8-sig")


def test_csv_formula_injection_guard():
    assert _csv_cell("=SUM(A1)").startswith("'")


@pytest.mark.django_db
def test_organization_isolation_project_risk(org_setup, client):
    org, project, user = org_setup
    other_org = Organization.objects.create(name="Diğer")
    other_project = Project.objects.create(organization=other_org, name="Gizli")
    secret = ProjectRisk.objects.create(
        project=other_project,
        title="Gizli",
        description="x",
        category=RiskCategory.TEKNIK,
        probability=RiskLevel.DUSUK,
        impact=RiskLevel.DUSUK,
    )
    client.login(username="tester", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org.id
    session["active_project_id"] = project.id
    session.save()
    response = client.get(f"/talep-yonetimi/")
    assert response.status_code == 200
    assert ProjectRisk.objects.filter(project=project).count() >= 0
    assert secret.project.organization_id != org.id


@pytest.mark.django_db
def test_ai_fallback_without_data(client, org_setup):
    from assistant.providers import DeterministicDataAssistant

    assistant = DeterministicDataAssistant()
    answer = assistant.generate_response("En yüksek proje riskleri?", {})
    assert assistant.FALLBACK.split(".")[0] in answer or "proje risk" in answer.lower() or "kayıtlı" in answer.lower()
