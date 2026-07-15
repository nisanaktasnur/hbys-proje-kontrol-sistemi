"""Canlı geçiş sonrası gösterge özetleri."""

from projects.models import MetricStatus


def post_go_live_summary(metrics_qs):
    return {
        "total": metrics_qs.count(),
        "on_target": metrics_qs.filter(status=MetricStatus.HEDEFTE).count(),
        "attention": metrics_qs.filter(status=MetricStatus.DIKKAT).count(),
        "below_target": metrics_qs.filter(status=MetricStatus.HEDEF_ALTI).count(),
    }


def parse_metric_number(value):
    import re

    match = re.search(r"[\d,\.]+", str(value or ""))
    if not match:
        return 0
    return float(match.group().replace(",", "."))


def metric_compare_data(metrics_qs, limit=6):
    rows = []
    for metric in metrics_qs.order_by("-measurement_date")[:limit]:
        rows.append({
            "name": metric.metric_name[:18],
            "current": parse_metric_number(metric.current_value),
            "target": parse_metric_number(metric.target_value),
        })
    return rows


def metric_timeline(metrics_qs, metric_name=None):
    qs = metrics_qs
    if metric_name:
        qs = qs.filter(metric_name=metric_name)
    return list(
        qs.order_by("measurement_date").values(
            "measurement_date", "current_value", "target_value", "metric_name", "status"
        )
    )
