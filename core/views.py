from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from accounts.models import Role


class HealthCheckView(View):
    def get(self, request):
        from django.db import connection

        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            db_ok = False
        status = 200 if db_ok else 503
        return JsonResponse({"durum": "calisiyor" if db_ok else "hata", "veritabani": db_ok}, status=status)


def error_403(request, exception=None):
    from core.context import user_is_system_admin
    from core.utils import get_user_membership, role_landing_url

    home_url = "/"
    if request.user.is_authenticated:
        membership = get_user_membership(request)
        if user_is_system_admin(request.user):
            home_url = role_landing_url(Role.SISTEM_YONETICISI)
        elif membership:
            home_url = role_landing_url(membership.role)
    return render(request, "errors/403.html", {"home_url": home_url}, status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
