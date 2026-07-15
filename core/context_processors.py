from accounts.models import Role
from core.context import get_accessible_organizations, get_accessible_projects
from core.permissions import role_context_flags, role_nav_items
from core.utils import get_active_project, get_user_membership


def global_context(request):
    membership = get_user_membership(request)
    project = get_active_project(request) if membership else None
    resolver = getattr(request, "resolver_match", None)
    current_nav = None
    if resolver and resolver.url_name:
        current_nav = (
            f"{resolver.namespace}:{resolver.url_name}"
            if resolver.namespace
            else resolver.url_name
        )
    perm_flags = role_context_flags(request.user, project) if membership else {}
    accessible_orgs = (
        get_accessible_organizations(request.user) if request.user.is_authenticated else []
    )
    accessible_projects = (
        get_accessible_projects(request.user, membership.organization)
        if membership and membership.organization
        else []
    )
    return {
        "membership": membership,
        "active_project": project,
        "active_organization": membership.organization if membership else None,
        "accessible_organizations": accessible_orgs,
        "accessible_projects": accessible_projects,
        "is_system_admin": membership.role == Role.SISTEM_YONETICISI if membership else False,
        "nav_items": role_nav_items(membership),
        "current_nav": current_nav,
        **perm_flags,
    }
