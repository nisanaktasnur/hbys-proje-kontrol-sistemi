import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.models import Organization, Project
from projects.models import RequestRecord, RequestStatus, TechnicalStatus, UATRecord, UATResultStatus


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Rol Test Kurum")


@pytest.fixture
def project(organization):
    return Project.objects.create(organization=organization, name="Rol Test Proje", status="Uygulama")


def _user(username, password, role, organization, full_name, project=None):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, full_name=full_name, approval_status=ApprovalStatus.APPROVED)
    Membership.objects.create(user=user, organization=organization, role=role, is_active=True)
    if project:
        ProjectMembership.objects.create(user=user, project=project, role=role, is_active=True)
    return user


@pytest.fixture
def admin_user(organization, project):
    return _user("admin", "Admin123!", Role.SISTEM_YONETICISI, organization, "Admin", project)


@pytest.fixture
def pm_user(organization, project):
    return _user("pm", "Pm123!", Role.PROJE_YONETICISI, organization, "PM", project)


@pytest.fixture
def tech_user(organization, project):
    return _user("techlead", "Tech123!", Role.TEKNIK_LIDER, organization, "Teknik", project)


@pytest.fixture
def manager_user(organization, project):
    return _user("manager", "Manager123!", Role.YONETICI, organization, "Yönetici", project)


@pytest.fixture
def sample_request(project, pm_user):
    return RequestRecord.objects.create(
        project=project,
        record_number="HBYS-01-0001",
        title="Test Talep",
        description="Açıklama",
        feedback_source="Proje Ekibi",
        process_area="UAT",
        responsible_team="Teknik Ekip",
        owner=pm_user,
        created_by=pm_user,
        status=RequestStatus.ACIK,
    )


@pytest.mark.django_db
def test_login_redirects_all_roles(client, admin_user, pm_user, tech_user, manager_user):
    cases = [
        ("admin", "Admin123!", reverse("accounts:user_management")),
        ("pm", "Pm123!", reverse("projects:dashboard")),
        ("techlead", "Tech123!", reverse("projects:technical_view")),
        ("manager", "Manager123!", reverse("projects:manager_panel")),
    ]
    for username, password, expected in cases:
        client.logout()
        response = client.post(reverse("accounts:login"), {"username": username, "password": password})
        assert response.status_code == 302
        assert expected in response.url


@pytest.mark.django_db
def test_role_navigation_items(client, admin_user, pm_user, tech_user, manager_user):
    client.login(username="pm", password="Pm123!")
    response = client.get(reverse("projects:dashboard"))
    content = response.content.decode()
    assert "Talep Yönetimi" in content
    assert "Kullanıcı Yönetimi" not in content

    client.login(username="admin", password="Admin123!")
    response = client.get(reverse("accounts:user_management"))
    content = response.content.decode()
    assert "Kurum ve Proje Yönetimi" in content
    assert "Talep Yönetimi" not in content


@pytest.mark.django_db
def test_admin_can_access_user_management(client, admin_user):
    client.login(username="admin", password="Admin123!")
    assert client.get(reverse("accounts:user_management")).status_code == 200
    assert client.get(reverse("accounts:org_project_management")).status_code == 200
    assert client.get(reverse("accounts:system_records")).status_code == 200


@pytest.mark.django_db
def test_admin_cannot_access_request_management(client, admin_user):
    client.login(username="admin", password="Admin123!")
    assert client.get(reverse("projects:request_management")).status_code == 403


@pytest.mark.django_db
def test_admin_cannot_create_request_post(client, admin_user, project):
    client.login(username="admin", password="Admin123!")
    response = client.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "Yetkisiz",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Açık",
            "responsible_team": "Test",
            "go_live_impact": "Orta",
            "affects_patient_or_user_safety": "Düşük",
            "operational_impact": "Orta",
        },
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_pm_can_create_request(client, pm_user, project):
    client.login(username="pm", password="Pm123!")
    response = client.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "Yeni Talep",
            "description": "Açıklama",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Açık",
            "responsible_team": "Teknik Ekip",
            "due_date": "2026-08-01",
            "go_live_impact": "Orta",
            "has_workaround": "",
            "affects_patient_or_user_safety": "Düşük",
            "operational_impact": "Orta",
        },
    )
    assert response.status_code == 302
    assert RequestRecord.objects.filter(title="Yeni Talep").exists()


@pytest.mark.django_db
def test_pm_cannot_access_user_management(client, pm_user):
    client.login(username="pm", password="Pm123!")
    assert client.get(reverse("accounts:user_management")).status_code == 403


@pytest.mark.django_db
def test_techlead_can_access_technical_view(client, tech_user):
    client.login(username="techlead", password="Tech123!")
    response = client.get(reverse("projects:technical_view"))
    assert response.status_code == 200
    assert "Teknik Operasyon Özeti" in response.content.decode()


@pytest.mark.django_db
def test_techlead_can_update_technical_fields(client, tech_user, sample_request):
    client.login(username="techlead", password="Tech123!")
    response = client.post(
        reverse("projects:request_detail", kwargs={"pk": sample_request.pk}),
        {
            "form_type": "technical",
            "technical_status": TechnicalStatus.GELISTIRME,
            "has_workaround": "on",
            "recommended_action": "Geçici çözüm uygulandı",
            "evaluation_note": "Teknik inceleme tamamlandı",
        },
    )
    assert response.status_code == 302
    sample_request.refresh_from_db()
    assert sample_request.technical_status == TechnicalStatus.GELISTIRME
    assert sample_request.has_workaround is True


@pytest.mark.django_db
def test_techlead_cannot_approve_users(client, tech_user, organization):
    pending = User.objects.create_user(username="pending2", password="Pass12345!")
    UserProfile.objects.create(user=pending, full_name="Bekleyen", approval_status=ApprovalStatus.PENDING)
    Membership.objects.create(user=pending, organization=organization, role=Role.PROJE_YONETICISI, is_active=False)
    client.login(username="techlead", password="Tech123!")
    response = client.post(reverse("accounts:approve_user", kwargs={"user_id": pending.pk}))
    assert response.status_code == 302
    pending.profile.refresh_from_db()
    assert pending.profile.approval_status == ApprovalStatus.PENDING


@pytest.mark.django_db
def test_manager_can_access_manager_panel(client, manager_user):
    client.login(username="manager", password="Manager123!")
    assert client.get(reverse("projects:manager_panel")).status_code == 200


@pytest.mark.django_db
def test_manager_cannot_access_request_management(client, manager_user):
    client.login(username="manager", password="Manager123!")
    assert client.get(reverse("projects:request_management")).status_code == 403


@pytest.mark.django_db
def test_manager_cannot_create_request_post(client, manager_user, project):
    client.login(username="manager", password="Manager123!")
    response = client.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "Yetkisiz",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Açık",
            "responsible_team": "Test",
            "go_live_impact": "Orta",
            "affects_patient_or_user_safety": "Düşük",
            "operational_impact": "Orta",
        },
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_manager_can_export_authorized_reports(client, manager_user, project):
    client.login(username="manager", password="Manager123!")
    session = client.session
    session["active_project_id"] = project.id
    session.save()
    assert client.get(reverse("reports:export_risk")).status_code == 200


@pytest.mark.django_db
def test_admin_export_audit_only(client, admin_user, project):
    client.login(username="admin", password="Admin123!")
    session = client.session
    session["active_project_id"] = project.id
    session.save()
    assert client.get(reverse("reports:export_audit")).status_code == 200
    assert client.get(reverse("reports:export_requests")).status_code == 403


@pytest.mark.django_db
def test_manager_cannot_access_decision_center(client, manager_user):
    client.login(username="manager", password="Manager123!")
    assert client.get(reverse("projects:decision_center")).status_code == 403


@pytest.mark.django_db
def test_pm_can_manage_uat(client, pm_user, project):
    client.login(username="pm", password="Pm123!")
    session = client.session
    session["active_project_id"] = project.id
    session.save()
    response = client.post(
        reverse("projects:request_management"),
        {
            "form_type": "uat",
            "scenario_name": "Senaryo 1",
            "process_area": "UAT",
            "expected_result": "Beklenen",
            "actual_result": "Gerçekleşen",
            "result_status": UATResultStatus.BASARISIZ,
            "severity": "Yüksek",
            "responsible_team": "Teknik Ekip",
            "tester_name": "Test",
            "tester_role": "Teknik Lider",
            "test_date": "2026-07-01",
        },
    )
    assert response.status_code == 302
    assert UATRecord.objects.filter(scenario_name="Senaryo 1").exists()


@pytest.mark.django_db
def test_ai_suggested_questions_vary_by_role(client, pm_user, tech_user, manager_user, admin_user, project):
    session_kwargs = {"active_project_id": project.id}
    client.login(username="pm", password="Pm123!")
    client.session.update(session_kwargs)
    client.session.save()
    pm_content = client.get(reverse("assistant:chat")).content.decode()
    assert "Bugün takip edilmesi gereken talepler hangileri?" in pm_content

    client.login(username="techlead", password="Tech123!")
    client.session.update(session_kwargs)
    client.session.save()
    tech_content = client.get(reverse("assistant:chat")).content.decode()
    assert "Teknik müdahale bekleyen talepler hangileri?" in tech_content
