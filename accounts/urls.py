from django.urls import path

from accounts import system_views, views

app_name = "accounts"

urlpatterns = [
    path("giris/", views.login_view, name="login"),
    path("kayit/", views.register_view, name="register"),
    path("onay-bekliyor/", views.pending_view, name="pending"),
    path("cikis/", views.logout_view, name="logout"),
    path("kullanici-yonetimi/", views.UserManagementView.as_view(), name="user_management"),
    path("kullanici-yonetimi/<int:user_id>/onayla/", views.approve_user, name="approve_user"),
    path("kullanici-yonetimi/<int:user_id>/reddet/", views.reject_user, name="reject_user"),
    path("kullanici-yonetimi/<int:user_id>/durum/", system_views.toggle_user_active, name="toggle_user_active"),
    path("kurum-proje-yonetimi/", system_views.OrgProjectManagementView.as_view(), name="org_project_management"),
    path("sistem-kayitlari/", system_views.SystemRecordsView.as_view(), name="system_records"),
]
