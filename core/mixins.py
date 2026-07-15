from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from accounts.models import ApprovalStatus, Role
from core.permissions import can_access_page
from core.utils import get_user_membership, user_is_approved


class OrganizationRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not user_is_approved(request.user):
            return redirect("accounts:pending")
        membership = get_user_membership(request)
        if not membership:
            raise PermissionDenied("Bu kuruma erişim yetkiniz bulunmuyor.")
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if self.allowed_roles:
            membership = get_user_membership(request)
            if not membership or membership.role not in self.allowed_roles:
                raise PermissionDenied("Bu sayfaya erişim yetkiniz bulunmuyor.")
        return super().dispatch(request, *args, **kwargs)


class PageAccessMixin(OrganizationRequiredMixin):
    page_url_name = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not user_is_approved(request.user):
            return redirect("accounts:pending")
        membership = get_user_membership(request)
        if not membership:
            raise PermissionDenied("Bu kuruma erişim yetkiniz bulunmuyor.")
        url_name = self.page_url_name or self._resolve_page_name(request)
        if url_name and not can_access_page(membership, url_name):
            raise PermissionDenied("Bu sayfaya erişim yetkiniz bulunmuyor.")
        return super(OrganizationRequiredMixin, self).dispatch(request, *args, **kwargs)

    def _resolve_page_name(self, request):
        match = getattr(request, "resolver_match", None)
        if match and match.url_name:
            if match.namespace:
                return f"{match.namespace}:{match.url_name}"
            return match.url_name
        return None


class SystemAdminRequiredMixin(OrganizationRequiredMixin, RoleRequiredMixin):
    allowed_roles = [Role.SISTEM_YONETICISI]


def approved_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not user_is_approved(request.user):
            return redirect("accounts:pending")
        return view_func(request, *args, **kwargs)

    return wrapper


def permission_required(check_func):
    """View decorator: check_func(request, *args, **kwargs) -> bool"""

    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if not user_is_approved(request.user):
                return redirect("accounts:pending")
            membership = get_user_membership(request)
            if not membership:
                raise PermissionDenied("Bu kuruma erişim yetkiniz bulunmuyor.")
            if not check_func(request, *args, **kwargs):
                raise PermissionDenied("Bu işlem için yetkiniz bulunmuyor.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
