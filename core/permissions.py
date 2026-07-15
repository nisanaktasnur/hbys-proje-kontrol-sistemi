"""Merkezi rol ve yetki katmanı."""

from django.core.exceptions import PermissionDenied

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role
from core.context import (
    ActiveMembership,
    get_accessible_organizations,
    get_project_membership,
    user_can_access_project,
    user_is_system_admin,
)
from core.utils import user_is_approved
from projects.models import ProcessArea

TEKNIK_EKIP_LABEL = "Teknik Ekip"

TEKNICAL_PROCESS_AREAS = {
    ProcessArea.UAT,
    ProcessArea.VERI_AKTARIMI,
    ProcessArea.YETKILENDIRME,
    ProcessArea.PERFORMANS,
    ProcessArea.RAPORLAMA,
    ProcessArea.CANLI_GECIS,
}

TEKNICAL_TEAM_KEYWORDS = (
    "teknik",
    "yazılım",
    "yazilim",
    "test",
    "entegrasyon",
    "veri",
    "yetkilendirme",
    "raporlama",
    "destek",
    "uat",
    "performans",
)

PAGE_ACCESS = {
    "accounts:user_management": {Role.SISTEM_YONETICISI},
    "accounts:org_project_management": {Role.SISTEM_YONETICISI},
    "accounts:system_records": {Role.SISTEM_YONETICISI},
    "projects:dashboard": {Role.SISTEM_YONETICISI, Role.PROJE_YONETICISI},
    "projects:dashboard_alt": {Role.SISTEM_YONETICISI, Role.PROJE_YONETICISI},
    "projects:technical_view": {Role.TEKNIK_LIDER},
    "projects:technical_work_list": {Role.TEKNIK_LIDER},
    "projects:technical_risks": {Role.TEKNIK_LIDER},
    "projects:technical_uat": {Role.TEKNIK_LIDER},
    "projects:technical_actions": {Role.TEKNIK_LIDER},
    "projects:request_management": {Role.PROJE_YONETICISI},
    "projects:request_detail": {Role.PROJE_YONETICISI, Role.TEKNIK_LIDER, Role.YONETICI},
    "projects:risk_warning": {Role.PROJE_YONETICISI},
    "projects:decision_center": {Role.PROJE_YONETICISI},
    "projects:manager_panel": {Role.YONETICI},
    "projects:executive_summary": {Role.YONETICI},
    "projects:communication_center": {
        Role.SISTEM_YONETICISI,
        Role.PROJE_YONETICISI,
        Role.TEKNIK_LIDER,
        Role.YONETICI,
    },
    "projects:communication_detail": {
        Role.SISTEM_YONETICISI,
        Role.PROJE_YONETICISI,
        Role.TEKNIK_LIDER,
        Role.YONETICI,
    },
    "assistant:chat": {
        Role.SISTEM_YONETICISI,
        Role.PROJE_YONETICISI,
        Role.TEKNIK_LIDER,
        Role.YONETICI,
    },
}

ROLE_DESCRIPTIONS = {
    Role.SISTEM_YONETICISI: "Hesap, kurum ve sistem kayıtlarını yönetir.",
    Role.PROJE_YONETICISI: "Günlük proje operasyonlarını ve canlı geçiş hazırlığını yönetir.",
    Role.TEKNIK_LIDER: "Teknik iş yükü, risk ve UAT çözümlerini yönetir.",
    Role.YONETICI: "Proje durumunu stratejik olarak izler ve karar verir.",
}


def _membership(user, project=None):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if user_is_system_admin(user):
        organization = None
        if project:
            organization = project.organization
        if organization is None:
            organization = get_accessible_organizations(user).first()
        if not organization:
            return None
        return ActiveMembership(
            user=user,
            role=Role.SISTEM_YONETICISI,
            organization=organization,
            project=project,
        )
    if project:
        return get_project_membership(user, project)
    return (
        ProjectMembership.objects.filter(user=user, is_active=True)
        .select_related("project", "project__organization")
        .first()
    )


def _approved(user):
    return user_is_approved(user)


def _same_project(membership, project):
    if not membership or not project:
        return False
    if getattr(membership, "role", None) == Role.SISTEM_YONETICISI:
        return True
    if isinstance(membership, ProjectMembership):
        return membership.project_id == project.id
    if isinstance(membership, ActiveMembership):
        if membership.role == Role.SISTEM_YONETICISI:
            return True
        return membership.project_id == project.id if membership.project else False
    return False


def _get_request_org(request_record):
    if not request_record:
        return None
    return getattr(request_record, "organization", None) or (
        request_record.project.organization if request_record.project_id else None
    )


def require_permission(condition, message="Bu işlem için yetkiniz bulunmuyor."):
    if not condition:
        raise PermissionDenied(message)


def can_access_page(membership, url_name):
    if not membership or not getattr(membership, "is_active", True):
        return False
    role = getattr(membership, "role", None)
    allowed = PAGE_ACCESS.get(url_name)
    if allowed is None:
        return True
    return role in allowed


def is_system_admin(user, project=None):
    if user_is_system_admin(user):
        return _approved(user)
    membership = _membership(user, project)
    return bool(membership and membership.role == Role.SISTEM_YONETICISI and _approved(user))


def is_project_manager(user, project=None):
    membership = _membership(user, project)
    return bool(membership and membership.role == Role.PROJE_YONETICISI and _approved(user))


def is_technical_lead(user, project=None):
    membership = _membership(user, project)
    return bool(membership and membership.role == Role.TEKNIK_LIDER and _approved(user))


def is_executive(user, project=None):
    membership = _membership(user, project)
    return bool(membership and membership.role == Role.YONETICI and _approved(user))


def can_view_request(user, request_record):
    if not user_can_access_project(user, request_record.project):
        return False
    membership = _membership(user, request_record.project)
    if not membership or not _approved(user):
        return False
    if membership.role == Role.SISTEM_YONETICISI:
        return False
    return membership.role in {
        Role.PROJE_YONETICISI,
        Role.TEKNIK_LIDER,
        Role.YONETICI,
    }


def can_create_request(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    if not user_can_access_project(user, project):
        return False
    return membership.role == Role.PROJE_YONETICISI


def can_edit_request(user, request_record):
    membership = _membership(user, request_record.project)
    if not membership or not _approved(user) or not request_record:
        return False
    if not user_can_access_project(user, request_record.project):
        return False
    return membership.role == Role.PROJE_YONETICISI


def can_assign_request(user, request_record):
    return can_edit_request(user, request_record)


def can_update_technical_fields(user, request_record):
    membership = _membership(user, request_record.project)
    if not membership or not _approved(user) or not request_record:
        return False
    if not user_can_access_project(user, request_record.project):
        return False
    return membership.role == Role.TEKNIK_LIDER


def can_manage_uat(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    if not user_can_access_project(user, project):
        return False
    return membership.role == Role.PROJE_YONETICISI


def can_update_uat_technical(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    if not user_can_access_project(user, project):
        return False
    return membership.role == Role.TEKNIK_LIDER


def can_manage_project_risks(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    if not user_can_access_project(user, project):
        return False
    return membership.role == Role.PROJE_YONETICISI


def can_manage_technical_risks(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    return membership.role == Role.TEKNIK_LIDER and user_can_access_project(user, project)


def can_manage_decision_records(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    if not user_can_access_project(user, project):
        return False
    return membership.role == Role.PROJE_YONETICISI


def can_manage_technical_actions(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    return membership.role == Role.TEKNIK_LIDER and user_can_access_project(user, project)


def can_update_go_live_readiness(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    return membership.role == Role.PROJE_YONETICISI and user_can_access_project(user, project)


def can_view_executive_reports(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    return membership.role == Role.YONETICI and user_can_access_project(user, project)


def can_send_communication(user, project):
    membership = _membership(user, project)
    if not membership or not _approved(user) or not project:
        return False
    return membership.role in {
        Role.SISTEM_YONETICISI,
        Role.PROJE_YONETICISI,
        Role.TEKNIK_LIDER,
        Role.YONETICI,
    } and user_can_access_project(user, project)


def can_export_reports(user, project, export_key):
    membership = _membership(user, project)
    if not membership or not _approved(user):
        return False
    if project and not user_can_access_project(user, project):
        return False

    role = membership.role
    if role == Role.SISTEM_YONETICISI:
        return export_key in {"users", "audit", "usage", "communications"}
    if role == Role.PROJE_YONETICISI:
        return export_key in {
            "requests",
            "risk",
            "uat",
            "decisions",
            "readiness",
            "project_risks",
            "metrics",
            "communications",
        }
    if role == Role.TEKNIK_LIDER:
        return export_key in {"requests", "uat", "project_risks", "risk"}
    if role == Role.YONETICI:
        return export_key in {
            "requests",
            "risk",
            "uat",
            "decisions",
            "readiness",
            "project_risks",
            "metrics",
            "communications",
        }
    return False


def can_manage_users(user):
    return is_system_admin(user)


def role_nav_items(membership):
    if not membership:
        return []
    role = membership.role
    if role == Role.SISTEM_YONETICISI:
        return [
            ("accounts:user_management", "Kullanıcı Yönetimi"),
            ("accounts:org_project_management", "Kurum ve Proje Yönetimi"),
            ("accounts:system_records", "Sistem Kayıtları"),
            ("projects:dashboard", "Genel Görünüm"),
            ("projects:communication_center", "Proje İletişim Merkezi"),
        ]
    if role == Role.PROJE_YONETICISI:
        return [
            ("projects:dashboard", "Genel Görünüm"),
            ("projects:request_management", "Talep Yönetimi"),
            ("projects:risk_warning", "Risk Erken Uyarı"),
            ("projects:decision_center", "Karar Destek Merkezi"),
            ("projects:communication_center", "Proje İletişim Merkezi"),
            ("assistant:chat", "Yapay Zekâ Proje Asistanı"),
        ]
    if role == Role.TEKNIK_LIDER:
        return [
            ("projects:technical_view", "Teknik Operasyon Özeti"),
            ("projects:technical_work_list", "Teknik İş Listesi"),
            ("projects:technical_risks", "Teknik Riskler"),
            ("projects:technical_uat", "UAT Teknik Bulguları"),
            ("projects:technical_actions", "Teknik Aksiyonlar"),
            ("projects:communication_center", "Proje İletişim Merkezi"),
            ("assistant:chat", "Yapay Zekâ Proje Asistanı"),
        ]
    if role == Role.YONETICI:
        return [
            ("projects:manager_panel", "Yönetici Paneli"),
            ("projects:communication_center", "Proje İletişim Merkezi"),
            ("assistant:chat", "Yapay Zekâ Proje Asistanı"),
        ]
    return []


def role_context_flags(user, project=None):
    membership = _membership(user, project)
    return {
        "can_create_request": can_create_request(user, project),
        "can_manage_uat": can_manage_uat(user, project),
        "can_update_uat_technical": can_update_uat_technical(user, project),
        "can_manage_project_risks": can_manage_project_risks(user, project),
        "can_manage_decision_records": can_manage_decision_records(user, project),
        "can_update_go_live_readiness": can_update_go_live_readiness(user, project),
        "can_view_executive_reports": can_view_executive_reports(user, project),
        "can_manage_users": can_manage_users(user),
        "can_send_communication": can_send_communication(user, project),
        "is_read_only_role": bool(membership and membership.role == Role.YONETICI),
        "is_system_admin_role": bool(membership and membership.role == Role.SISTEM_YONETICISI),
        "is_technical_lead_role": bool(membership and membership.role == Role.TEKNIK_LIDER),
        "is_project_manager_role": bool(membership and membership.role == Role.PROJE_YONETICISI),
        "role_description": ROLE_DESCRIPTIONS.get(membership.role, "") if membership else "",
    }


def is_technical_request(record):
    team = (record.responsible_team or "").lower()
    if any(kw in team for kw in TEKNICAL_TEAM_KEYWORDS):
        return True
    return record.process_area in TECHNICAL_PROCESS_AREAS
