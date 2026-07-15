"""Proje iletişimi ve talimat takibi."""

from django.db.models import Q
from django.utils import timezone

from projects.models import CommunicationType, InstructionStatus, ProjectCommunication


def recipient_filter(user, role=None):
    """Kullanıcıya veya aktif proje rolüne yöneltilmiş kayıtlar."""
    if not user:
        return Q(pk__in=[])
    filters = Q(recipient_user=user)
    if role:
        filters |= Q(recipient_role=role, recipient_user__isnull=True)
    return filters


def _thread_roots(qs):
    return qs.filter(parent__isnull=True)


def communication_thread_root(communication):
    current = communication
    while current.parent_id:
        current = current.parent
    return current


def user_can_view_communication(user, communication, membership=None):
    if not user or not communication:
        return False
    from core.context import user_can_access_project, user_is_system_admin
    from core.permissions import _membership

    if not user_can_access_project(user, communication.project):
        return False
    if user_is_system_admin(user):
        return True
    membership = membership or _membership(user, communication.project)
    if not membership:
        return False
    if communication.sender_id == user.id:
        return True
    if communication.recipient_user_id == user.id:
        return True
    if (
        communication.recipient_role
        and communication.recipient_role == membership.role
        and not communication.recipient_user_id
    ):
        return True
    if communication.parent_id:
        return user_can_view_communication(user, communication.parent, membership)
    return False


def user_is_recipient(user, communication, membership=None):
    from core.permissions import _membership

    membership = membership or _membership(user, communication.project)
    if not membership:
        return False
    if communication.recipient_user_id == user.id:
        return True
    return (
        bool(communication.recipient_role)
        and communication.recipient_role == membership.role
        and not communication.recipient_user_id
        and communication.sender_id != user.id
    )


def mark_communication_read(communication, user, membership=None):
    """Alıcı kaydı açtığında okundu işaretle."""
    from core.permissions import _membership

    membership = membership or _membership(user, communication.project)
    if not user_is_recipient(user, communication, membership):
        return communication
    if communication.is_read:
        return communication
    communication.is_read = True
    communication.read_at = timezone.now()
    update_fields = ["is_read", "read_at", "updated_at"]
    if (
        communication.communication_type == CommunicationType.TALIMAT
        and communication.status == InstructionStatus.GONDERILDI
    ):
        communication.status = InstructionStatus.GORULDU
        update_fields.append("status")
    communication.save(update_fields=update_fields)
    return communication


def create_reply(parent, user, reply_text, membership=None):
    """Orijinal gönderene yanıt oluştur."""
    root = communication_thread_root(parent)
    if not user_can_view_communication(user, root, membership):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("Bu iletişime yanıt verme yetkiniz bulunmuyor.")
    text = (reply_text or "").strip()
    if not text:
        from django.core.exceptions import ValidationError

        raise ValidationError("Yanıt metni boş olamaz.")

    title = f"Yanıt: {root.title}"
    if len(title) > 300:
        title = title[:297] + "..."

    reply = ProjectCommunication.objects.create(
        project=root.project,
        communication_type=root.communication_type,
        title=title,
        description=text,
        sender=user,
        recipient_user=root.sender,
        recipient_role="",
        parent=root,
        priority=root.priority,
        due_date=root.due_date,
        status=InstructionStatus.GONDERILDI,
        is_read=False,
    )
    return reply


def incoming_messages(user, project, role=None):
    if not project or not user or not user.is_authenticated:
        return ProjectCommunication.objects.none()
    return _thread_roots(
        ProjectCommunication.objects.filter(
            project=project,
            communication_type=CommunicationType.MESAJ,
        )
        .filter(recipient_filter(user, role))
        .exclude(sender=user)
        .select_related(
            "sender",
            "sender__profile",
            "recipient_user",
            "recipient_user__profile",
            "project",
            "project__organization",
        )
        .order_by("-created_at")
    )


def incoming_instructions(user, project, role=None, include_completed=False):
    if not project or not user or not user.is_authenticated:
        return ProjectCommunication.objects.none()
    qs = _thread_roots(
        ProjectCommunication.objects.filter(
            project=project,
            communication_type=CommunicationType.TALIMAT,
        ).filter(recipient_filter(user, role))
    )
    if not include_completed:
        qs = qs.exclude(status__in=[InstructionStatus.TAMAMLANDI, InstructionStatus.IPTAL])
    return qs.select_related(
        "sender",
        "sender__profile",
        "recipient_user",
        "recipient_user__profile",
        "project",
        "project__organization",
    ).order_by("-created_at")


def unread_communications(user, project, role=None):
    if not project or not user or not user.is_authenticated:
        return ProjectCommunication.objects.none()
    qs = _thread_roots(
        ProjectCommunication.objects.filter(project=project, is_read=False)
        .filter(recipient_filter(user, role))
        .exclude(sender=user)
    )
    return qs.select_related(
        "sender",
        "sender__profile",
        "project",
        "project__organization",
    ).order_by("-created_at")


def completed_instructions(user, project, role=None):
    if not project or not user or not user.is_authenticated:
        return ProjectCommunication.objects.none()
    return _thread_roots(
        ProjectCommunication.objects.filter(
            project=project,
            communication_type=CommunicationType.TALIMAT,
        )
        .filter(recipient_filter(user, role))
        .filter(status__in=[InstructionStatus.TAMAMLANDI, InstructionStatus.IPTAL])
        .select_related(
            "sender",
            "sender__profile",
            "project",
            "project__organization",
        )
        .order_by("-updated_at")
    )


def sent_communications(user, project):
    if not project or not user or not user.is_authenticated:
        return ProjectCommunication.objects.none()
    return _thread_roots(
        ProjectCommunication.objects.filter(project=project, sender=user)
        .select_related(
            "recipient_user",
            "recipient_user__profile",
            "project",
            "project__organization",
        )
        .order_by("-created_at")
    )


def pending_instructions(user, project, role=None):
    """Kullanıcıya veya rolüne atanmış tamamlanmamış talimatlar."""
    return incoming_instructions(user, project, role, include_completed=False)


def communication_inbox_summary(user, project, role=None):
    """Dashboard özeti: okunmamış mesaj, açık talimat, son gelen kayıtlar."""
    if not project or not user or not user.is_authenticated:
        return {
            "unread_message_count": 0,
            "open_instruction_count": 0,
            "recent_incoming": [],
        }
    messages_qs = incoming_messages(user, project, role)
    instructions_qs = incoming_instructions(user, project, role)
    recent_messages = list(messages_qs[:3])
    recent_instructions = list(instructions_qs[:3])
    combined = sorted(
        recent_messages + recent_instructions,
        key=lambda item: item.created_at,
        reverse=True,
    )[:3]
    return {
        "unread_message_count": messages_qs.filter(is_read=False).count(),
        "open_instruction_count": instructions_qs.count(),
        "recent_incoming": combined,
    }


def manager_communication_summary(user, project):
    """Yönetici paneli: gönderilen mesaj/talimat özeti."""
    if not project or not user or not user.is_authenticated:
        return {
            "sent_message_count": 0,
            "pending_sent_instruction_count": 0,
            "recent_sent": [],
        }
    sent_qs = sent_communications(user, project)
    pending_sent = sent_qs.filter(
        communication_type=CommunicationType.TALIMAT,
    ).exclude(status__in=[InstructionStatus.TAMAMLANDI, InstructionStatus.IPTAL])
    return {
        "sent_message_count": sent_qs.filter(communication_type=CommunicationType.MESAJ).count(),
        "pending_sent_instruction_count": pending_sent.count(),
        "recent_sent": list(sent_qs[:3]),
    }


def user_can_update_communication(user, communication, membership=None):
    """Talimat/mesaj durumunu güncelleyebilir mi."""
    return user_can_view_communication(user, communication, membership)
