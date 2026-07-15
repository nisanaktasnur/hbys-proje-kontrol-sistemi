from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import LoginForm, RegisterForm
from accounts.models import ApprovalStatus, Membership, Role, UserProfile
from core.middleware import check_login_rate_limit, record_failed_login, reset_login_rate_limit
from core.mixins import SystemAdminRequiredMixin
from core.models import Organization
from core.utils import get_user_membership, log_audit, redirect_for_role
from projects.services.role_dashboard_service import admin_dashboard_stats
from django.views.generic import TemplateView


def login_view(request):
    if request.user.is_authenticated:
        membership = Membership.get_active_for_user(request.user)
        if membership:
            return redirect_for_role(membership)
        return redirect("accounts:pending")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST":
        if not check_login_rate_limit(request):
            messages.error(request, "Çok fazla başarısız giriş denemesi. Lütfen bir süre bekleyin.")
        elif form.is_valid():
            user = form.get_user()
            profile = getattr(user, "profile", None)
            if not profile or profile.approval_status != ApprovalStatus.APPROVED:
                messages.warning(request, "Hesabınız henüz onaylanmamış. Lütfen sistem yöneticisinin onayını bekleyin.")
            else:
                reset_login_rate_limit(request)
                login(request, user)
                membership = Membership.get_active_for_user(user)
                if membership:
                    log_audit(user, membership.organization, "Giriş", "Kullanıcı", user.pk)
                    return redirect_for_role(membership)
                messages.error(request, "Kurum üyeliğiniz bulunmuyor.")
        else:
            record_failed_login(request)
            messages.error(request, "Kullanıcı adı veya şifre hatalı.")

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        membership = Membership.get_active_for_user(request.user)
        if membership:
            return redirect_for_role(membership)
        return redirect("accounts:pending")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        UserProfile.objects.create(
            user=user,
            full_name=form.cleaned_data["full_name"],
            approval_status=ApprovalStatus.PENDING,
        )
        org = Organization.objects.filter(is_active=True).first()
        if org:
            Membership.objects.create(
                user=user,
                organization=org,
                role=form.cleaned_data["role"],
                is_active=False,
            )
        messages.success(
            request,
            "Kayıt başvurunuz alındı. Sistem yöneticisi onayından sonra giriş yapabilirsiniz.",
        )
        return redirect("accounts:login")

    return render(request, "accounts/register.html", {"form": form})


def pending_view(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile and profile.approval_status == ApprovalStatus.APPROVED:
            membership = Membership.get_active_for_user(request.user)
            if membership:
                return redirect_for_role(membership)
    return render(request, "accounts/pending.html")


@login_required
@require_POST
def logout_view(request):
    membership = Membership.get_active_for_user(request.user)
    if membership:
        log_audit(request.user, membership.organization, "Çıkış", "Kullanıcı", request.user.pk)
    logout(request)
    return redirect("accounts:login")


class UserManagementView(SystemAdminRequiredMixin, TemplateView):
    template_name = "accounts/user_management.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.membership.organization
        role_filter = self.request.GET.get("role", "")
        approval_filter = self.request.GET.get("approval", "")

        pending_qs = UserProfile.objects.filter(
            approval_status=ApprovalStatus.PENDING,
            user__memberships__organization=org,
        ).select_related("user").distinct()
        all_qs = UserProfile.objects.filter(
            user__memberships__organization=org,
        ).select_related("user").prefetch_related("user__memberships").distinct()

        if role_filter:
            pending_qs = pending_qs.filter(user__memberships__role=role_filter, user__memberships__organization=org)
            all_qs = all_qs.filter(user__memberships__role=role_filter, user__memberships__organization=org)
        if approval_filter:
            pending_qs = pending_qs.filter(approval_status=approval_filter)
            all_qs = all_qs.filter(approval_status=approval_filter)

        ctx["pending_profiles"] = pending_qs
        ctx["all_profiles"] = all_qs
        ctx["role_filter"] = role_filter
        ctx["approval_filter"] = approval_filter
        ctx["role_choices"] = Role.choices
        ctx["approval_choices"] = ApprovalStatus.choices
        ctx.update(admin_dashboard_stats(org))
        return ctx


@login_required
@require_POST
def approve_user(request, user_id):
    membership = get_user_membership(request)
    if not membership or membership.role != Role.SISTEM_YONETICISI:
        messages.error(request, "Bu işlem için yetkiniz bulunmuyor.")
        return redirect("accounts:user_management")

    profile = get_object_or_404(UserProfile, user_id=user_id)
    user_membership = Membership.objects.filter(user=profile.user).first()
    if not user_membership:
        messages.error(request, "Kullanıcı kurum üyeliği bulunamadı.")
        return redirect("accounts:user_management")

    profile.approval_status = ApprovalStatus.APPROVED
    profile.approved_by = request.user
    profile.approved_at = timezone.now()
    profile.save()

    user_membership.is_active = True
    user_membership.save()

    from accounts.models import ProjectMembership
    from core.models import Project

    first_project = Project.objects.filter(organization=user_membership.organization).order_by("id").first()
    if first_project:
        ProjectMembership.objects.get_or_create(
            user=profile.user,
            project=first_project,
            defaults={"role": user_membership.role, "is_active": True},
        )

    log_audit(
        request.user,
        user_membership.organization,
        "Kullanıcı Onayı",
        "Kullanıcı",
        user_id,
        profile.full_name,
    )
    messages.success(request, f"{profile.full_name} onaylandı.")
    return redirect("accounts:user_management")


@login_required
@require_POST
def reject_user(request, user_id):
    membership = Membership.get_active_for_user(request.user)
    if not membership or membership.role != Role.SISTEM_YONETICISI:
        messages.error(request, "Bu işlem için yetkiniz bulunmuyor.")
        return redirect("accounts:user_management")

    profile = get_object_or_404(
        UserProfile,
        user_id=user_id,
        user__memberships__organization=membership.organization,
    )
    profile.approval_status = ApprovalStatus.REJECTED
    profile.save()
    log_audit(request.user, membership.organization, "Kullanıcı Reddi", "Kullanıcı", user_id, profile.full_name)
    messages.warning(request, f"{profile.full_name} reddedildi.")
    return redirect("accounts:user_management")
