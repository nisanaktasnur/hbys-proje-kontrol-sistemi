"""System Admin global access regression tests."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.context import (
    get_accessible_organizations,
    get_accessible_projects,
    user_can_access_project,
    user_is_system_admin,
)
from core.models import Organization, Project
from core.utils import role_landing_url


@pytest.fixture
def demo_hospitals(db):
    orgs = []
    for name in [
        "Örnek Şehir Hastanesi",
        "Örnek Eğitim ve Araştırma Hastanesi",
        "Örnek Bölge Hastanesi",
    ]:
        orgs.append(Organization.objects.create(name=name, is_active=True))
    return orgs


@pytest.fixture
def demo_projects(demo_hospitals):
    projects = []
    for org in demo_hospitals:
        for pname in ["HBYS Uygulama Projesi", "HBYS Canlı Geçiş Projesi"]:
            projects.append(
                Project.objects.create(organization=org, name=pname, status="Uygulama")
            )
    return projects


def _admin_user(org, username="sysadmin_only"):
    user = User.objects.create_user(username=username, password="Admin123!")
    UserProfile.objects.create(
        user=user, full_name="Sistem Yöneticisi", approval_status=ApprovalStatus.APPROVED
    )
    Membership.objects.create(
        user=user, organization=org, role=Role.SISTEM_YONETICISI, is_active=True
    )
    return user


@pytest.mark.django_db
def test_system_admin_without_project_membership_has_global_access(demo_hospitals, demo_projects):
    admin = _admin_user(demo_hospitals[0])
    assert user_is_system_admin(admin)
    assert admin.project_memberships.count() == 0
    assert get_accessible_organizations(admin).count() == len(demo_hospitals)
    assert get_accessible_projects(admin).count() == len(demo_projects)
    for project in demo_projects:
        assert user_can_access_project(admin, project)


@pytest.mark.django_db
def test_system_admin_can_access_core_pages(client, demo_hospitals, demo_projects):
    _admin_user(demo_hospitals[0], username="sysadmin_pages")
    client.login(username="sysadmin_pages", password="Admin123!")
    for url_name in (
        "accounts:user_management",
        "accounts:org_project_management",
        "accounts:system_records",
        "projects:dashboard",
        "projects:communication_center",
    ):
        response = client.get(reverse(url_name))
        assert response.status_code == 200, url_name


@pytest.mark.django_db
def test_system_admin_can_select_every_demo_hospital(client, demo_hospitals, demo_projects):
    _admin_user(demo_hospitals[0], username="sysadmin_orgs")
    client.login(username="sysadmin_orgs", password="Admin123!")
    for org in demo_hospitals:
        response = client.post(
            reverse("projects:set_active_organization", kwargs={"organization_id": org.id})
        )
        assert response.status_code in (302, 200)
        assert client.session.get("active_organization_id") == org.id
        org_projects = [p for p in demo_projects if p.organization_id == org.id]
        for project in org_projects:
            response = client.post(reverse("projects:set_project", kwargs={"project_id": project.id}))
            assert response.status_code in (302, 200)
            assert client.session.get("active_project_id") == project.id


@pytest.mark.django_db
def test_system_admin_invalid_session_is_reset_not_denied(client, demo_hospitals, demo_projects):
    _admin_user(demo_hospitals[0], username="sysadmin_reset")
    client.login(username="sysadmin_reset", password="Admin123!")
    session = client.session
    session["active_organization_id"] = 999999
    session["active_project_id"] = 999999
    session.save()
    response = client.get(reverse("accounts:user_management"))
    assert response.status_code == 200
    assert client.session.get("active_organization_id") in [org.id for org in demo_hospitals]


@pytest.mark.django_db
def test_non_admin_still_blocked_from_unauthorized_project(client, demo_hospitals, demo_projects):
    org = demo_hospitals[0]
    project_a = demo_projects[0]
    project_b = demo_projects[1]
    user = User.objects.create_user(username="pm_block", password="Test12345!")
    UserProfile.objects.create(user=user, full_name="PM", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=Role.PROJE_YONETICISI, is_active=True)
    ProjectMembership.objects.create(
        user=user, project=project_a, role=Role.PROJE_YONETICISI, is_active=True
    )
    client.login(username="pm_block", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org.id
    session["active_project_id"] = project_a.id
    session.save()
    assert client.post(reverse("projects:set_project", kwargs={"project_id": project_b.id})).status_code == 403


@pytest.mark.django_db
def test_access_denied_home_url_for_system_admin(client, demo_hospitals):
    _admin_user(demo_hospitals[0], username="sysadmin_403")
    client.login(username="sysadmin_403", password="Admin123!")
    response = client.get(reverse("projects:request_management"))
    assert response.status_code == 403
    assert role_landing_url(Role.SISTEM_YONETICISI) in response.content.decode()


@pytest.mark.django_db
def test_access_denied_home_url_for_project_manager(client, demo_hospitals, demo_projects):
    org = demo_hospitals[0]
    project = demo_projects[0]
    user = User.objects.create_user(username="pm_403", password="Test12345!")
    UserProfile.objects.create(user=user, full_name="PM", approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=Role.PROJE_YONETICISI, is_active=True)
    ProjectMembership.objects.create(
        user=user, project=project, role=Role.PROJE_YONETICISI, is_active=True
    )
    client.login(username="pm_403", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org.id
    session["active_project_id"] = project.id
    session.save()
    response = client.get(reverse("accounts:user_management"))
    assert response.status_code == 403
    assert role_landing_url(Role.PROJE_YONETICISI) in response.content.decode()
