from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import resolve, reverse

from accounts.models import Membership
from core.context import build_active_membership, user_is_system_admin
from core.utils import user_is_approved


class OrganizationMiddleware:
    PUBLIC_URLS = {
        "accounts:login",
        "accounts:register",
        "accounts:pending",
        "core:health",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        request.active_project = None

        if request.user.is_authenticated:
            request.membership = build_active_membership(request)
            if request.membership:
                request.active_project = request.membership.project

        url_name = None
        try:
            match = resolve(request.path_info)
            url_name = match.url_name
            namespace = match.namespace
            if namespace:
                url_name = f"{namespace}:{url_name}"
        except Exception:
            pass

        if request.user.is_authenticated and url_name not in self.PUBLIC_URLS:
            if not user_is_approved(request.user):
                if url_name != "accounts:pending":
                    return redirect("accounts:pending")
            elif request.membership is None and not user_is_system_admin(request.user):
                has_membership = Membership.objects.filter(
                    user=request.user, is_active=True
                ).exists()
                if not has_membership:
                    return HttpResponseForbidden("Kurum üyeliğiniz bulunmuyor.")

        response = self.get_response(request)
        return response


class LoginRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


def check_login_rate_limit(request):
    from django.conf import settings

    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"login_attempts:{ip}"
    attempts = cache.get(key, 0)
    return attempts < settings.LOGIN_RATE_LIMIT


def record_failed_login(request):
    from django.conf import settings

    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"login_attempts:{ip}"
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, settings.LOGIN_RATE_WINDOW)


def reset_login_rate_limit(request):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    cache.delete(f"login_attempts:{ip}")
