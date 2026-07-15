import pytest
from django.contrib.auth.models import User

from accounts.models import ApprovalStatus, Membership, Role, UserProfile
from assistant.providers import DeterministicDataAssistant, build_project_context
from core.models import Organization, Project
from projects.models import GoLiveReadiness, ReadinessStatus, RequestRecord, RequestStatus


@pytest.fixture
def ai_setup(db):
    org = Organization.objects.create(name="AI Kurum")
    project = Project.objects.create(organization=org, name="AI Proje")
    user = User.objects.create_user(username="aiuser", password="Pass12345!")
    UserProfile.objects.create(user=user, full_name="AI User", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=Role.PROJE_YONETICISI, is_active=True)
    GoLiveReadiness.objects.create(
        project=project,
        education_status=ReadinessStatus.DEVAM,
        uat_status=ReadinessStatus.EKSIK,
        overall_status=ReadinessStatus.DEVAM,
    )
    RequestRecord.objects.create(
        project=project,
        record_number="HBYS-01-0001",
        title="UAT hatası",
        description="Test",
        feedback_source="UAT Geri Bildirimi",
        process_area="UAT",
        status=RequestStatus.ACIK,
        responsible_team="UAT Ekibi",
        risk_level="Yüksek",
    )
    return project


@pytest.mark.django_db
def test_deterministic_assistant_uses_data(ai_setup):
    project = ai_setup
    context = build_project_context(project)
    assistant = DeterministicDataAssistant()
    answer = assistant.generate_response("UAT sürecinde risk var mı?", context)
    assert "UAT" in answer
    assert "HBYS-01-0001" in answer or "açık" in answer.lower()


@pytest.mark.django_db
def test_fallback_when_no_data():
    assistant = DeterministicDataAssistant()
    answer = assistant.generate_response("Rastgele soru?", {})
    assert "mevcut proje verileriyle" in answer.lower()
