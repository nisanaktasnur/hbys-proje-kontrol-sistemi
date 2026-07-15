import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.models import Organization, Project
from projects.models import RequestRecord


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Kurum")


@pytest.fixture
def project(organization):
    return Project.objects.create(organization=organization, name="Test Proje")


@pytest.fixture
def admin_user(organization):
    user = User.objects.create_user(username="admin", password="Admin123!")
    UserProfile.objects.create(user=user, full_name="Admin", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=organization, role=Role.SISTEM_YONETICISI, is_active=True)
    return user


@pytest.fixture
def pm_user(organization, project):
    user = User.objects.create_user(username="pm", password="Pm123!")
    UserProfile.objects.create(user=user, full_name="PM", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=organization, role=Role.PROJE_YONETICISI, is_active=True)
    ProjectMembership.objects.create(
        user=user, project=project, role=Role.PROJE_YONETICISI, is_active=True
    )
    return user


@pytest.fixture
def manager_user(organization, project):
    user = User.objects.create_user(username="manager", password="Manager123!")
    UserProfile.objects.create(user=user, full_name="Yönetici", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=organization, role=Role.YONETICI, is_active=True)
    ProjectMembership.objects.create(user=user, project=project, role=Role.YONETICI, is_active=True)
    return user


@pytest.fixture
def other_org(db):
    return Organization.objects.create(name="Başka Kurum")


@pytest.mark.django_db
def test_login_redirects_by_role(client, admin_user, manager_user):
    response = client.post(
        reverse("accounts:login"),
        {"username": "admin", "password": "Admin123!"},
    )
    assert response.status_code == 302
    assert reverse("accounts:user_management") in response.url

    client.logout()
    response = client.post(
        reverse("accounts:login"),
        {"username": "manager", "password": "Manager123!"},
    )
    assert response.status_code == 302
    assert reverse("projects:manager_panel") in response.url


@pytest.mark.django_db
def test_pending_user_cannot_access_dashboard(client, organization):
    user = User.objects.create_user(username="pending", password="Pass12345!")
    UserProfile.objects.create(user=user, full_name="Bekleyen", approval_status=ApprovalStatus.PENDING)
    Membership.objects.create(user=user, organization=organization, role=Role.PROJE_YONETICISI, is_active=False)
    client.login(username="pending", password="Pass12345!")
    response = client.get(reverse("projects:dashboard"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_organization_isolation(client, pm_user, other_org, project):
    other_project = Project.objects.create(organization=other_org, name="Gizli Proje")
    secret = RequestRecord.objects.create(
        project=other_project,
        record_number="HBYS-99-0001",
        title="Gizli",
        description="Test",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Test",
    )
    client.login(username="pm", password="Pm123!")
    session = client.session
    session["active_organization_id"] = project.organization_id
    session["active_project_id"] = project.id
    session.save()
    response = client.get(reverse("projects:request_detail", kwargs={"pk": secret.pk}))
    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_manager_cannot_access_user_management(client, manager_user):
    client.login(username="manager", password="Manager123!")
    response = client.get(reverse("accounts:user_management"))
    assert response.status_code == 403
