import pytest
from django.urls import reverse

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.models import Organization, Project
from projects.models import RequestRecord


@pytest.fixture
def hospitals(db):
    orgs = []
    for name in [
        "Örnek Şehir Hastanesi",
        "Örnek Eğitim ve Araştırma Hastanesi",
    ]:
        orgs.append(Organization.objects.create(name=name, is_active=True))
    return orgs


@pytest.fixture
def projects(hospitals):
    items = []
    for org in hospitals:
        for pname in ["HBYS Uygulama Projesi", "HBYS Canlı Geçiş Projesi"]:
            items.append(
                Project.objects.create(organization=org, name=pname, status="Uygulama")
            )
    return items


def _create_user(username, role, org, project):
    from django.contrib.auth.models import User

    user = User.objects.create_user(username=username, password="Test12345!")
    UserProfile.objects.create(user=user, full_name=username, approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=org, role=role, is_active=True)
    ProjectMembership.objects.create(user=user, project=project, role=role, is_active=True)
    return user


@pytest.mark.django_db
def test_active_project_filters_data(client, hospitals, projects):
    org_a, org_b = hospitals
    project_a = projects[0]
    project_b = projects[2]
    user = _create_user("pmctx", Role.PROJE_YONETICISI, org_a, project_a)
    ProjectMembership.objects.create(
        user=user, project=project_b, role=Role.PROJE_YONETICISI, is_active=True
    )
    Membership.objects.create(user=user, organization=org_b, role=Role.PROJE_YONETICISI, is_active=True)
    RequestRecord.objects.create(
        project=project_a,
        record_number="CTX-A-001",
        title="A Projesi Talebi",
        description="A",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    RequestRecord.objects.create(
        project=project_b,
        record_number="CTX-B-001",
        title="B Projesi Talebi",
        description="B",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    client.login(username="pmctx", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org_a.id
    session["active_project_id"] = project_a.id
    session.save()
    response = client.get(reverse("projects:request_management"))
    content = response.content.decode()
    assert "A Projesi Talebi" in content
    assert "B Projesi Talebi" not in content


@pytest.mark.django_db
def test_unauthorized_project_url_blocked(client, hospitals, projects):
    org_a, org_b = hospitals
    project_a = projects[0]
    project_b = projects[2]
    user = _create_user("pmiso", Role.PROJE_YONETICISI, org_a, project_a)
    record_b = RequestRecord.objects.create(
        project=project_b,
        record_number="ISO-B-001",
        title="İzole Talep",
        description="B",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    client.login(username="pmiso", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org_a.id
    session["active_project_id"] = project_a.id
    session.save()
    assert client.get(reverse("projects:request_detail", kwargs={"pk": record_b.pk})).status_code == 404


@pytest.mark.django_db
def test_same_hospital_project_b_blocked_by_url(client, hospitals, projects):
    """Aynı kurumda yalnızca proje A üyeliği olan kullanıcı proje B'ye erişemez."""
    org_a = hospitals[0]
    project_a = projects[0]
    project_b = projects[1]
    assert project_a.organization_id == project_b.organization_id

    user = _create_user("pmsame", Role.PROJE_YONETICISI, org_a, project_a)
    RequestRecord.objects.create(
        project=project_b,
        record_number="SAME-B-001",
        title="Aynı Kurum B Talebi",
        description="B",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    client.login(username="pmsame", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org_a.id
    session["active_project_id"] = project_a.id
    session.save()

    assert client.post(reverse("projects:set_project", kwargs={"project_id": project_b.id})).status_code == 403
    record_b = RequestRecord.objects.get(project=project_b)
    response = client.get(reverse("projects:request_detail", kwargs={"pk": record_b.pk}))
    assert response.status_code in (403, 404)


@pytest.mark.django_db
def test_csv_export_does_not_leak_unauthorized_project(client, hospitals, projects):
    org_a = hospitals[0]
    project_a = projects[0]
    project_b = projects[1]
    user = _create_user("pmcsv", Role.PROJE_YONETICISI, org_a, project_a)
    RequestRecord.objects.create(
        project=project_a,
        record_number="CSV-A-001",
        title="Yetkili Proje Talebi",
        description="A",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    RequestRecord.objects.create(
        project=project_b,
        record_number="CSV-B-001",
        title="Yetkisiz Proje Talebi",
        description="B",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        created_by=user,
    )
    client.login(username="pmcsv", password="Test12345!")
    session = client.session
    session["active_organization_id"] = org_a.id
    session["active_project_id"] = project_a.id
    session.save()

    response = client.get(reverse("reports:export_requests"))
    assert response.status_code == 200
    content = b"".join(response.streaming_content).decode("utf-8-sig")
    assert "Yetkili Proje Talebi" in content
    assert "Yetkisiz Proje Talebi" not in content


@pytest.mark.django_db
def test_set_active_project_requires_access(client, hospitals, projects):
    org_a = hospitals[0]
    project_a = projects[0]
    project_other = projects[2]
    user = _create_user("pmset", Role.PROJE_YONETICISI, org_a, project_a)
    client.login(username="pmset", password="Test12345!")
    response = client.post(reverse("projects:set_project", kwargs={"project_id": project_other.id}))
    assert response.status_code == 403
