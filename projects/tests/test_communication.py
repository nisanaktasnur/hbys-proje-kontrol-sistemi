import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.models import Organization, Project
from projects.models import (
    CommunicationType,
    InstructionStatus,
    Priority,
    ProjectCommunication,
)


@pytest.fixture
def comm_setup(db):
    org_a = Organization.objects.create(name="İletişim Kurumu A", is_active=True)
    org_b = Organization.objects.create(name="İletişim Kurumu B", is_active=True)
    project_a = Project.objects.create(organization=org_a, name="Proje A", status="Uygulama")
    project_b = Project.objects.create(organization=org_b, name="Proje B", status="Uygulama")
    return org_a, org_b, project_a, project_b


def _user(username, role, org, project, full_name=None):
    user = User.objects.create_user(username=username, password="Test12345!")
    UserProfile.objects.create(
        user=user,
        full_name=full_name or username,
        approval_status=ApprovalStatus.APPROVED,
    )
    Membership.objects.create(user=user, organization=org, role=role, is_active=True)
    ProjectMembership.objects.create(user=user, project=project, role=role, is_active=True)
    return user


def _set_session(client, org, project):
    session = client.session
    session["active_organization_id"] = org.id
    session["active_project_id"] = project.id
    session.save()


def _create_comm(sender, project, comm_type, recipient_role=None, recipient_user=None, **kwargs):
    defaults = {
        "title": kwargs.pop("title", "Test İletişim"),
        "description": kwargs.pop("description", "Test açıklama"),
        "communication_type": comm_type,
        "recipient_role": recipient_role or "",
        "priority": Priority.ORTA,
        "status": InstructionStatus.GONDERILDI,
    }
    defaults.update(kwargs)
    return ProjectCommunication.objects.create(
        project=project,
        sender=sender,
        recipient_user=recipient_user,
        **defaults,
    )


@pytest.mark.django_db
def test_manager_message_visible_to_pm(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr", Role.YONETICI, org_a, project_a, "Yönetici")
    _user("pm", Role.PROJE_YONETICISI, org_a, project_a, "Proje Yöneticisi")

    _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Yönetici Mesajı",
    )

    client.login(username="pm", password="Test12345!")
    _set_session(client, org_a, project_a)
    response = client.get(reverse("projects:communication_center"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Gelen Mesajlar" in content
    assert "Yönetici Mesajı" in content
    assert "Gelen mesaj bulunmuyor." not in content


@pytest.mark.django_db
def test_pm_opens_detail_marks_read(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr5", Role.YONETICI, org_a, project_a)
    pm = _user("pmread", Role.PROJE_YONETICISI, org_a, project_a)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Okunacak Mesaj",
    )

    client.login(username="pmread", password="Test12345!")
    _set_session(client, org_a, project_a)
    response = client.get(reverse("projects:communication_detail", kwargs={"pk": comm.pk}))
    assert response.status_code == 200
    comm.refresh_from_db()
    assert comm.is_read is True
    assert comm.read_at is not None
    assert "Okundu" in response.content.decode()


@pytest.mark.django_db
def test_pm_replies_manager_sees_reply(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgrreply", Role.YONETICI, org_a, project_a)
    pm = _user("pmreply", Role.PROJE_YONETICISI, org_a, project_a)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Yanıtlanacak Mesaj",
    )

    client.login(username="pmreply", password="Test12345!")
    _set_session(client, org_a, project_a)
    client.post(
        reverse("projects:communication_detail", kwargs={"pk": comm.pk}),
        {"action": "reply", "description": "Mesaj alındı, değerlendiriyoruz."},
    )

    reply = ProjectCommunication.objects.filter(parent=comm).first()
    assert reply is not None
    assert reply.sender_id == pm.id
    assert reply.recipient_user_id == manager.id

    client.login(username="mgrreply", password="Test12345!")
    _set_session(client, org_a, project_a)
    detail = client.get(reverse("projects:communication_detail", kwargs={"pk": comm.pk}))
    content = detail.content.decode()
    assert "Yanıtlar ve Görüşme Geçmişi" in content
    assert "Mesaj alındı" in content


@pytest.mark.django_db
def test_manager_instruction_detail_and_status_update(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr6", Role.YONETICI, org_a, project_a)
    tech = _user("techup", Role.TEKNIK_LIDER, org_a, project_a)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.TALIMAT,
        recipient_role=Role.TEKNIK_LIDER,
        title="Tamamlanacak Talimat",
    )

    client.login(username="techup", password="Test12345!")
    _set_session(client, org_a, project_a)
    detail = client.get(reverse("projects:communication_detail", kwargs={"pk": comm.pk}))
    assert detail.status_code == 200
    assert "Talimat Durum Güncelleme" in detail.content.decode()

    client.post(
        reverse("projects:communication_detail", kwargs={"pk": comm.pk}),
        {
            "action": "update_status",
            "status": InstructionStatus.DEVAM,
            "completion_note": "İşleme alındı.",
        },
    )
    comm.refresh_from_db()
    assert comm.status == InstructionStatus.DEVAM
    assert comm.completion_note == "İşleme alındı."


@pytest.mark.django_db
def test_instruction_completed_requires_completion_note(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr7", Role.YONETICI, org_a, project_a)
    tech = _user("techdone", Role.TEKNIK_LIDER, org_a, project_a)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.TALIMAT,
        recipient_role=Role.TEKNIK_LIDER,
        title="Kapanacak Talimat",
    )

    client.login(username="techdone", password="Test12345!")
    _set_session(client, org_a, project_a)
    client.post(
        reverse("projects:communication_detail", kwargs={"pk": comm.pk}),
        {
            "action": "update_status",
            "status": InstructionStatus.TAMAMLANDI,
            "completion_note": "Tamamlandı, çözüm notu eklendi.",
        },
    )
    comm.refresh_from_db()
    assert comm.status == InstructionStatus.TAMAMLANDI
    assert comm.completion_note == "Tamamlandı, çözüm notu eklendi."


@pytest.mark.django_db
def test_sender_sees_read_status_and_replies(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr8", Role.YONETICI, org_a, project_a)
    pm = _user("pm8", Role.PROJE_YONETICISI, org_a, project_a)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Gönderilen Mesaj",
        is_read=True,
    )
    ProjectCommunication.objects.create(
        project=project_a,
        communication_type=CommunicationType.MESAJ,
        title="Yanıt: Gönderilen Mesaj",
        description="PM yanıtı",
        sender=pm,
        recipient_user=manager,
        parent=comm,
        status=InstructionStatus.GONDERILDI,
    )

    client.login(username="mgr8", password="Test12345!")
    _set_session(client, org_a, project_a)
    response = client.get(reverse("projects:communication_detail", kwargs={"pk": comm.pk}))
    content = response.content.decode()
    assert "Gönderim Durumu" in content
    assert "Okundu" in content
    assert "PM yanıtı" in content


@pytest.mark.django_db
def test_message_not_visible_in_other_project(client, comm_setup):
    org_a, org_b, project_a, project_b = comm_setup
    manager = _user("mgr4", Role.YONETICI, org_a, project_a)
    pm = _user("pmiso", Role.PROJE_YONETICISI, org_a, project_a)
    ProjectMembership.objects.create(
        user=pm, project=project_b, role=Role.PROJE_YONETICISI, is_active=True
    )
    Membership.objects.create(user=pm, organization=org_b, role=Role.PROJE_YONETICISI, is_active=True)

    _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Proje A Mesajı",
    )

    client.login(username="pmiso", password="Test12345!")
    _set_session(client, org_b, project_b)
    response = client.get(reverse("projects:communication_center"))
    content = response.content.decode()

    assert "Proje A Mesajı" not in content
    assert "Gelen mesaj bulunmuyor." in content


@pytest.mark.django_db
def test_unauthorized_user_cannot_open_detail(client, comm_setup):
    org_a, org_b, project_a, project_b = comm_setup
    manager = _user("mgr9", Role.YONETICI, org_a, project_a)
    outsider = _user("outsider", Role.PROJE_YONETICISI, org_b, project_b)

    comm = _create_comm(
        manager,
        project_a,
        CommunicationType.MESAJ,
        recipient_role=Role.PROJE_YONETICISI,
        title="Gizli Mesaj",
    )

    client.login(username="outsider", password="Test12345!")
    _set_session(client, org_b, project_b)
    response = client.get(reverse("projects:communication_detail", kwargs={"pk": comm.pk}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_send_message_requires_recipient(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr10", Role.YONETICI, org_a, project_a)

    client.login(username="mgr10", password="Test12345!")
    _set_session(client, org_a, project_a)
    before = ProjectCommunication.objects.count()
    response = client.post(
        reverse("projects:communication_center") + "?tab=yeni",
        {
            "action": "create",
            "communication_type": CommunicationType.MESAJ,
            "title": "Alıcısız Mesaj",
            "description": "Test",
        },
    )
    assert response.status_code == 200
    assert ProjectCommunication.objects.count() == before


@pytest.mark.django_db
def test_send_message_success_message(client, comm_setup):
    org_a, _, project_a, _ = comm_setup
    manager = _user("mgr11", Role.YONETICI, org_a, project_a)

    client.login(username="mgr11", password="Test12345!")
    _set_session(client, org_a, project_a)
    response = client.post(
        reverse("projects:communication_center") + "?tab=yeni",
        {
            "action": "create",
            "communication_type": CommunicationType.MESAJ,
            "title": "Geçerli Mesaj",
            "description": "PM için mesaj",
            "recipient_role": Role.PROJE_YONETICISI,
        },
        follow=True,
    )
    content = response.content.decode()
    assert "Mesaj gönderildi." in content
    assert ProjectCommunication.objects.filter(title="Geçerli Mesaj", project=project_a).exists()
