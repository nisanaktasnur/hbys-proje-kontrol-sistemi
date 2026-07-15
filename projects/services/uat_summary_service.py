"""UAT özet istatistikleri."""

from projects.models import RiskLevel, UATResultStatus


def uat_summary(uat_qs):
    total = uat_qs.count()
    successful = uat_qs.filter(result_status=UATResultStatus.BASARILI).count()
    failed = uat_qs.filter(result_status=UATResultStatus.BASARISIZ).count()
    blocked = uat_qs.filter(result_status=UATResultStatus.BLOKE).count()
    retest = uat_qs.filter(result_status=UATResultStatus.TEKRAR).count()
    high_open = uat_qs.filter(
        severity=RiskLevel.YUKSEK,
        result_status__in=[
            UATResultStatus.BASARISIZ,
            UATResultStatus.BLOKE,
            UATResultStatus.TEKRAR,
        ],
    ).count()
    completion_pct = round((successful / total) * 100) if total else 0
    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "blocked": blocked,
        "retest": retest,
        "high_open": high_open,
        "completion_pct": completion_pct,
    }
