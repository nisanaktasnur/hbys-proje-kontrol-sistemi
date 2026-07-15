"""Sistem kullanım istatistikleri — AuditLog tabanlı."""

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.models import AuditLog


def thirty_day_summary(organization):
    """Son 30 günlük kullanım özeti."""
    since = timezone.now() - timedelta(days=30)
    qs = AuditLog.objects.filter(organization=organization, created_at__gte=since)
    total_actions = qs.count()
    unique_users = qs.exclude(user__isnull=True).values("user").distinct().count()
    top_actions = list(
        qs.values("action")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    top_users = list(
        qs.exclude(user__isnull=True)
        .values("user__username", "user__profile__full_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    project_activity = list(
        qs.exclude(project__isnull=True)
        .values("project__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:6]
    )
    return {
        "total_actions": total_actions,
        "unique_users": unique_users,
        "top_actions": top_actions,
        "top_users": top_users,
        "project_activity": project_activity,
        "period_days": 30,
    }


def monthly_usage_stats(organization, months=12):
    """Aylık işlem sayıları — grafik için."""
    since = timezone.now() - timedelta(days=months * 31)
    qs = (
        AuditLog.objects.filter(organization=organization, created_at__gte=since)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    labels = []
    values = []
    for row in qs:
        month = row["month"]
        if month:
            labels.append(month.strftime("%b %Y"))
            values.append(row["count"])
    return {"labels": labels, "values": values}
