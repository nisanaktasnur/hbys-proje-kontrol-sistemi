import json

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.context import get_accessible_organizations
from core.mixins import SystemAdminRequiredMixin, permission_required
from core.models import AuditLog, Organization, Project
from core.permissions import can_manage_users, require_permission
from core.utils import get_user_membership, log_audit
from projects.services.system_usage_service import monthly_usage_stats, thirty_day_summary


class OrgProjectManagementView(SystemAdminRequiredMixin, TemplateView):
    template_name = "accounts/org_project_management.html"
    page_url_name = "accounts:org_project_management"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        organizations = get_accessible_organizations(self.request.user)
        selected_org_id = self.request.GET.get("org") or self.request.session.get("active_organization_id")
        organization = organizations.filter(id=selected_org_id).first() if selected_org_id else None
        if not organization:
            organization = organizations.first()
        if organization:
            self.request.session["active_organization_id"] = organization.id
        ctx["organizations"] = organizations
        ctx["organization"] = organization
        ctx["projects"] = (
            Project.objects.filter(organization=organization).order_by("name")
            if organization
            else Project.objects.none()
        )
        ctx["selected_project_id"] = self.request.GET.get("project") or ""
        selected_project = None
        if ctx["selected_project_id"]:
            selected_project = ctx["projects"].filter(id=ctx["selected_project_id"]).first()
        if not selected_project and ctx["projects"].exists():
            selected_project = ctx["projects"].first()
        ctx["selected_project"] = selected_project
        if organization and selected_project:
            self.request.session["active_organization_id"] = organization.id
            self.request.session["active_project_id"] = selected_project.id
        ctx["project_memberships"] = (
            ProjectMembership.objects.filter(project=selected_project, is_active=True)
            .select_related("user", "user__profile")
            .order_by("user__username")
            if selected_project
            else ProjectMembership.objects.none()
        )
        ctx["project_roles_by_user"] = {
            pm.user_id: pm.role for pm in ctx["project_memberships"]
        }
        ctx["org_memberships"] = (
            Membership.objects.filter(organization=organization, is_active=True)
            .select_related("user", "user__profile")
            .order_by("user__username")
            if organization
            else Membership.objects.none()
        )
        ctx["org_members_with_project_role"] = [
            {
                "membership": m,
                "project_role": ctx["project_roles_by_user"].get(m.user_id, "—"),
            }
            for m in ctx["org_memberships"]
        ]
        ctx["roles"] = Role.choices
        return ctx

    def post(self, request, *args, **kwargs):
        require_permission(can_manage_users(request.user))
        organizations = get_accessible_organizations(request.user)
        org_id = request.POST.get("organization_id") or request.session.get("active_organization_id")
        org = organizations.filter(id=org_id).first() or organizations.first()
        if not org:
            return redirect("accounts:org_project_management")
        action = request.POST.get("action")
        if action == "update_org":
            org.name = request.POST.get("name", org.name).strip() or org.name
            org.is_active = request.POST.get("is_active") == "on"
            org.save()
            log_audit(request.user, org, "Kurum Güncelleme", "Organization", org.pk, org.name)
            messages.success(request, "Kurum bilgileri güncellendi.")
        elif action == "update_project":
            project = get_object_or_404(Project, pk=request.POST.get("project_id"), organization=org)
            project.name = request.POST.get("name", project.name).strip() or project.name
            project.status = request.POST.get("status", project.status)
            project.client_name = request.POST.get("client_name", project.client_name)
            project.save()
            log_audit(request.user, org, "Proje Güncelleme", "Project", project.pk, project.name, project)
            messages.success(request, "Proje bilgileri güncellendi.")
        elif action == "assign_project_role":
            project = get_object_or_404(Project, pk=request.POST.get("project_id"), organization=org)
            user_id = request.POST.get("user_id")
            new_role = request.POST.get("role")
            if user_id and new_role in dict(Role.choices):
                pm, created = ProjectMembership.objects.get_or_create(
                    user_id=user_id,
                    project=project,
                    defaults={"role": new_role, "is_active": True},
                )
                if not created:
                    pm.role = new_role
                    pm.is_active = True
                    pm.save()
                log_audit(
                    request.user,
                    org,
                    "Proje Rol Atama",
                    "ProjectMembership",
                    pm.pk,
                    f"{pm.user.username} → {new_role} ({project.name})",
                    project,
                )
                messages.success(request, "Proje rolü güncellendi.")
        elif action == "assign_role":
            membership = get_object_or_404(Membership, pk=request.POST.get("membership_id"), organization=org)
            new_role = request.POST.get("role")
            if new_role in dict(Role.choices):
                membership.role = new_role
                membership.save()
                log_audit(
                    request.user,
                    org,
                    "Rol Atama",
                    "Membership",
                    membership.pk,
                    f"{membership.user.username} → {new_role}",
                )
                messages.success(request, "Kurum rolü güncellendi.")
        redirect_url = f"{request.path}?org={org.id}"
        project_id = request.POST.get("project_id")
        if project_id:
            redirect_url += f"&project={project_id}"
        return redirect(redirect_url)


class SystemRecordsView(SystemAdminRequiredMixin, TemplateView):
    template_name = "accounts/system_records.html"
    page_url_name = "accounts:system_records"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.membership.organization
        ctx["audit_logs"] = AuditLog.objects.filter(organization=org).select_related("user", "project")[:50]
        ctx["recent_registrations"] = (
            UserProfile.objects.filter(user__memberships__organization=org)
            .select_related("user")
            .order_by("-created_at")[:10]
        )
        ctx["role_distribution"] = (
            Membership.objects.filter(organization=org, is_active=True)
            .values("role")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        ctx["usage_summary"] = thirty_day_summary(org)
        monthly = monthly_usage_stats(org)
        ctx["monthly_usage"] = monthly
        ctx["monthly_usage_labels_json"] = json.dumps(monthly["labels"], ensure_ascii=False)
        ctx["monthly_usage_values_json"] = json.dumps(monthly["values"])
        return ctx


@require_POST
@permission_required(lambda request, *a, **k: can_manage_users(request.user))
def toggle_user_active(request, user_id):
    membership = get_user_membership(request)
    target_membership = get_object_or_404(
        Membership,
        user_id=user_id,
        organization=membership.organization,
    )
    if target_membership.user_id == request.user.id:
        messages.error(request, "Kendi hesabınızı pasifleştiremezsiniz.")
        return redirect("accounts:user_management")
    target_membership.is_active = not target_membership.is_active
    target_membership.save()
    profile = getattr(target_membership.user, "profile", None)
    action = "Kullanıcı Aktifleştirme" if target_membership.is_active else "Kullanıcı Pasifleştirme"
    log_audit(
        request.user,
        membership.organization,
        action,
        "Kullanıcı",
        user_id,
        profile.full_name if profile else target_membership.user.username,
    )
    messages.success(request, "Kullanıcı durumu güncellendi.")
    return redirect("accounts:user_management")
