from django.contrib import admin
from django.urls import include, path

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("projects.urls")),
    path("", include("assistant.urls")),
    path("", include("reports.urls")),
]
