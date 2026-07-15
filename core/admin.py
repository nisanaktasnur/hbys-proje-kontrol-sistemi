from django.contrib import admin
from django.contrib.auth.models import User

from core.models import AuditLog, Organization, Project
from accounts.models import Membership, UserProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "status", "planned_go_live_date")
    list_filter = ("organization", "status")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "object_type", "user", "organization", "created_at")
    list_filter = ("action", "object_type")


admin.site.register(UserProfile)
admin.site.register(Membership)
