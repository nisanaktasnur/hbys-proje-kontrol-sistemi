"""Aktif kurum/proje bağlamı ve erişim kontrolü."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from accounts.models import Membership, ProjectMembership, Role
from core.demo_defaults import DEMO_PRIMARY_ORG_NAME, DEMO_PRIMARY_PROJECT_NAME
from core.models import Organization, Project


@dataclass
class ActiveMembership:
    """İstek bağlamında kullanılan birleşik üyelik nesnesi."""

    user: object
    role: str
    organization: Organization
    project: Project | None = None
    is_active: bool = True
    project_membership_id: int | None = None
    org_membership_id: int | None = None

    @property
    def is_system_admin(self):
        return self.role == Role.SISTEM_YONETICISI


def user_is_system_admin(user):
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(
        user=user,
        role=Role.SISTEM_YONETICISI,
        is_active=True,
    ).exists()


def _project_membership_qs(user):
    return ProjectMembership.objects.filter(user=user, is_active=True).select_related(
        "project", "project__organization"
    )


def get_accessible_organizations(user):
    if not user or not user.is_authenticated:
        return Organization.objects.none()
    if user_is_system_admin(user):
        return Organization.objects.filter(is_active=True).order_by("name")
    org_ids = (
        _project_membership_qs(user)
        .values_list("project__organization_id", flat=True)
        .distinct()
    )
    return Organization.objects.filter(id__in=org_ids, is_active=True).order_by("name")


def get_accessible_projects(user, organization=None):
    if not user or not user.is_authenticated:
        return Project.objects.none()
    if user_is_system_admin(user):
        qs = Project.objects.select_related("organization").all()
    else:
        project_ids = _project_membership_qs(user).values_list("project_id", flat=True)
        qs = Project.objects.filter(id__in=project_ids).select_related("organization")
    if organization:
        qs = qs.filter(organization=organization)
    return qs.order_by("organization__name", "name")


def user_can_access_organization(user, organization):
    if not user or not organization:
        return False
    if user_is_system_admin(user):
        return Organization.objects.filter(pk=organization.pk, is_active=True).exists()
    return get_accessible_organizations(user).filter(pk=organization.pk).exists()


def get_project_membership(user, project):
    if not user or not project:
        return None
    if user_is_system_admin(user):
        return None
    return _project_membership_qs(user).filter(project=project).first()


def user_can_access_project(user, project):
    if not user or not project:
        return False
    if user_is_system_admin(user):
        return True
    return _project_membership_qs(user).filter(project=project).exists()


def resolve_active_organization(request):
    org_id = request.session.get("active_organization_id")
    accessible = get_accessible_organizations(request.user)
    if org_id:
        org = accessible.filter(id=org_id).first()
        if org:
            return org
        request.session.pop("active_organization_id", None)
        request.session.pop("active_project_id", None)
    org = accessible.filter(name=DEMO_PRIMARY_ORG_NAME).first() or accessible.first()
    if org:
        request.session["active_organization_id"] = org.id
    return org


def _default_project(accessible):
    if not accessible.exists():
        return None
    preferred = accessible.filter(
        organization__name=DEMO_PRIMARY_ORG_NAME,
        name=DEMO_PRIMARY_PROJECT_NAME,
    ).first()
    if preferred:
        return preferred
    by_name = accessible.filter(name=DEMO_PRIMARY_PROJECT_NAME).first()
    if by_name:
        return by_name
    return accessible.first()


def resolve_active_project(request, organization=None):
    organization = organization or resolve_active_organization(request)
    if not organization:
        return None
    project_id = request.session.get("active_project_id")
    accessible = get_accessible_projects(request.user, organization)
    if project_id:
        project = accessible.filter(id=project_id).first()
        if project:
            return project
        request.session.pop("active_project_id", None)
    project = _default_project(accessible)
    if project:
        request.session["active_project_id"] = project.id
        request.session["active_organization_id"] = project.organization_id
    return project


def build_active_membership(request):
    if not request.user.is_authenticated:
        return None

    if user_is_system_admin(request.user):
        organization = resolve_active_organization(request)
        if not organization:
            organization = get_accessible_organizations(request.user).first()
            if organization:
                request.session["active_organization_id"] = organization.id
        if not organization:
            return None
        project = resolve_active_project(request, organization)
        return ActiveMembership(
            user=request.user,
            role=Role.SISTEM_YONETICISI,
            organization=organization,
            project=project,
        )

    organization = resolve_active_organization(request)
    if not organization:
        return None
    project = resolve_active_project(request, organization)
    if not project:
        return None
    pm = _project_membership_qs(request.user).filter(project=project).first()
    if not pm:
        return None
    return ActiveMembership(
        user=request.user,
        role=pm.role,
        organization=project.organization,
        project=project,
        project_membership_id=pm.id,
    )


def set_active_context(request, organization_id=None, project_id=None):
    if project_id:
        project = Project.objects.select_related("organization").filter(pk=project_id).first()
        if not project or not user_can_access_project(request.user, project):
            raise PermissionDenied("Bu projeye erişim yetkiniz bulunmuyor.")
        request.session["active_project_id"] = project.id
        request.session["active_organization_id"] = project.organization_id
        return project
    if organization_id:
        org = get_accessible_organizations(request.user).filter(pk=organization_id).first()
        if not org:
            raise PermissionDenied("Bu kuruma erişim yetkiniz bulunmuyor.")
        request.session["active_organization_id"] = org.id
        projects = get_accessible_projects(request.user, org)
        if projects.exists():
            current = request.session.get("active_project_id")
            if not projects.filter(id=current).exists():
                preferred = _default_project(projects)
                request.session["active_project_id"] = preferred.id if preferred else projects.first().id
        else:
            request.session.pop("active_project_id", None)
        return org
    return None


def ensure_project_access(request, project):
    if not user_can_access_project(request.user, project):
        raise PermissionDenied("Bu projeye erişim yetkiniz bulunmuyor.")
    return project
