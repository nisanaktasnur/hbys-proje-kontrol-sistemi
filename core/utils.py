from django.shortcuts import redirect
from django.urls import reverse

from accounts.models import ApprovalStatus, Role
from core.context import (
    build_active_membership,
    get_accessible_organizations,
    get_accessible_projects,
    resolve_active_organization,
    resolve_active_project,
    set_active_context,
    user_can_access_organization,
    user_can_access_project,
)


def log_audit(user, organization, action, object_type, object_id="", details="", project=None):
    from core.models import AuditLog

    AuditLog.objects.create(
        organization=organization,
        project=project,
        user=user,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        details=details,
    )


def get_user_membership(request):
    if getattr(request, "membership", None):
        return request.membership
    return build_active_membership(request)


def get_user_organization(request):
    membership = get_user_membership(request)
    if membership:
        return membership.organization
    return resolve_active_organization(request)


def get_active_project(request):
    membership = get_user_membership(request)
    if membership and membership.project:
        return membership.project
    return resolve_active_project(request)


def role_landing_url(role):
    mapping = {
        Role.SISTEM_YONETICISI: "accounts:user_management",
        Role.PROJE_YONETICISI: "projects:dashboard",
        Role.TEKNIK_LIDER: "projects:technical_view",
        Role.YONETICI: "projects:manager_panel",
    }
    return reverse(mapping.get(role, "projects:dashboard"))


def redirect_for_role(membership):
    return redirect(role_landing_url(membership.role))


def is_system_admin(membership):
    return membership and membership.role == Role.SISTEM_YONETICISI


def user_is_approved(user):
    if not user.is_authenticated:
        return False
    profile = getattr(user, "profile", None)
    return profile and profile.approval_status == ApprovalStatus.APPROVED


__all__ = [
    "log_audit",
    "get_user_membership",
    "get_user_organization",
    "get_active_project",
    "role_landing_url",
    "redirect_for_role",
    "is_system_admin",
    "user_is_approved",
    "get_accessible_organizations",
    "get_accessible_projects",
    "set_active_context",
    "user_can_access_organization",
    "user_can_access_project",
]
