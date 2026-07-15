import pytest
from django.contrib.auth.models import User

from accounts.models import ApprovalStatus, Membership, Role, UserProfile
from core.models import Organization, Project
from projects.models import RequestRecord, RequestStatus
from reports.services.csv_export import export_requests


@pytest.fixture
def setup_data(db):
    org = Organization.objects.create(name="Export Kurum")
    project = Project.objects.create(organization=org, name="Export Proje")
    user = User.objects.create_user(username="exporter", password="Pass12345!")
    UserProfile.objects.create(user=user, full_name="Exporter", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=Role.YONETICI, is_active=True)
    RequestRecord.objects.create(
        project=project,
        record_number="HBYS-01-0001",
        title="Türkçe başlık — özel",
        description="Açıklama",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        priority="Orta",
        status=RequestStatus.ACIK,
        responsible_team="Test Ekibi",
        risk_level="Orta",
    )
    return org, project, user


@pytest.mark.django_db
def test_csv_turkish_headers(setup_data):
    org, project, user = setup_data
    qs = RequestRecord.objects.filter(project=project)
    response = export_requests(user, org, qs)
    content = b"".join(response.streaming_content).decode("utf-8-sig")
    assert "Kayıt No" in content
    assert "Türkçe başlık" in content
    assert "Dahili Risk Skoru" not in content


@pytest.mark.django_db
def test_csv_admin_internal_score(setup_data):
    org, project, user = setup_data
    admin = User.objects.create_user(username="sysadmin", password="Admin123!")
    UserProfile.objects.create(user=admin, full_name="Admin", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=admin, organization=org, role=Role.SISTEM_YONETICISI, is_active=True)
    qs = RequestRecord.objects.filter(project=project)
    response = export_requests(user, org, qs, include_internal_score=True)
    content = b"".join(response.streaming_content).decode("utf-8-sig")
    assert "Dahili Risk Skoru" in content
