import csv
import io
from datetime import datetime

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone

from core.utils import log_audit
from projects.models import DecisionSupportRecord, GoLiveReadiness, PostGoLiveMetric, ProjectRisk, RequestRecord, RequestStatus, UATRecord


class Echo:
    def write(self, value):
        return value


def _csv_cell(value):
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def _utf8_bom_writer():
    buffer = io.StringIO()
    buffer.write("\ufeff")
    return buffer


def export_requests(user, organization, queryset, filters=None, include_internal_score=False):
    filters = filters or {}
    filename = f"talep_kayitlari_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi",
        "Kayıt No",
        "Talep Başlığı",
        "Açıklama",
        "Geri Bildirim Kaynağı",
        "İlgili Süreç",
        "Öncelik",
        "Durum",
        "Risk Seviyesi",
        "Sorumlu Ekip",
        "Hedef Tarih",
        "Canlı Geçiş Etkisi",
        "Son Güncelleme",
    ]
    if include_internal_score:
        headers.insert(8, "Dahili Risk Skoru")

    def row_iter():
        buffer = Echo()
        writer = csv.writer(buffer)
        yield "\ufeff"
        yield writer.writerow(headers)
        export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        for obj in queryset.select_related("project"):
            row = [
                _csv_cell(export_date),
                _csv_cell(obj.record_number),
                _csv_cell(obj.title),
                _csv_cell(obj.description),
                _csv_cell(obj.feedback_source),
                _csv_cell(obj.process_area),
                _csv_cell(obj.priority),
                _csv_cell(obj.status),
                _csv_cell(obj.risk_level),
                _csv_cell(obj.responsible_team),
                _csv_cell(obj.due_date.strftime("%d.%m.%Y") if obj.due_date else ""),
                _csv_cell(obj.go_live_impact),
                _csv_cell(timezone.localtime(obj.updated_at).strftime("%d.%m.%Y %H:%M")),
            ]
            if include_internal_score:
                row.insert(8, obj.internal_risk_score)
            yield writer.writerow(row)

    log_audit(user, organization, "CSV Dışa Aktarma", "RequestRecord", details=str(filters))
    response = StreamingHttpResponse(row_iter(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_risk_summary(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"risk_ozeti_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = ["Dışa Aktarma Tarihi", "Risk Seviyesi", "Kayıt Sayısı", "Açık Kayıt", "Geciken Kayıt"]
    open_qs = queryset.exclude(status=RequestStatus.TAMAMLANDI)
    today = timezone.localdate()
    rows = []
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for level in ["Düşük", "Orta", "Yüksek"]:
        level_qs = queryset.filter(risk_level=level)
        rows.append([
            export_date,
            level,
            level_qs.count(),
            level_qs.exclude(status=RequestStatus.TAMAMLANDI).count(),
            level_qs.filter(due_date__lt=today).exclude(status=RequestStatus.TAMAMLANDI).count(),
        ])

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    log_audit(user, organization, "CSV Dışa Aktarma", "RiskSummary", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_decisions(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"karar_destek_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi",
        "Kaynak",
        "Başlık",
        "Tespit",
        "Önerilen Karar",
        "Öncelik",
        "Durum",
        "Sorumlu Ekip",
        "Hedef Tarih",
        "Beklenen Etki",
        "İlgili Talep",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for obj in queryset.select_related("related_request"):
        writer.writerow([
            _csv_cell(export_date),
            _csv_cell(obj.source),
            _csv_cell(obj.title),
            _csv_cell(obj.finding),
            _csv_cell(obj.recommendation),
            _csv_cell(obj.priority),
            _csv_cell(obj.status),
            _csv_cell(obj.responsible_team),
            _csv_cell(obj.due_date.strftime("%d.%m.%Y") if obj.due_date else ""),
            _csv_cell(obj.expected_effect),
            _csv_cell(obj.related_request.record_number if obj.related_request else ""),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "DecisionSupportRecord", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_readiness(user, organization, project, filters=None):
    filters = filters or {}
    filename = f"canli_gecis_hazirligi_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    readiness = GoLiveReadiness.objects.filter(project=project).first()
    headers = [
        "Dışa Aktarma Tarihi",
        "Proje",
        "Eğitim Durumu",
        "UAT Durumu",
        "Veri Aktarımı",
        "Yetkilendirme Kontrolü",
        "Kritik Açık Kayıt",
        "Genel Durum",
        "Önerilen Sonraki Adım",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    if readiness:
        writer.writerow([
            export_date,
            project.name,
            readiness.education_status,
            readiness.uat_status,
            readiness.data_migration_status,
            readiness.authorization_status,
            readiness.critical_open_request_status,
            readiness.overall_status,
            readiness.recommended_next_step,
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "GoLiveReadiness", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_project_risks(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"proje_riskleri_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi", "Risk Başlığı", "Risk Açıklaması", "Risk Kategorisi",
        "Olasılık", "Etki Seviyesi", "Risk Seviyesi", "Önleyici Aksiyon",
        "Gerçekleşme Durumunda Aksiyon", "Sorumlu", "Hedef Tarih", "Durum", "İlgili Talep",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for obj in queryset.select_related("owner", "related_request"):
        writer.writerow([
            _csv_cell(export_date), _csv_cell(obj.title), _csv_cell(obj.description),
            _csv_cell(obj.category), _csv_cell(obj.probability), _csv_cell(obj.impact),
            _csv_cell(obj.risk_level), _csv_cell(obj.mitigation_action),
            _csv_cell(obj.contingency_action),
            _csv_cell(obj.owner.username if obj.owner else ""),
            _csv_cell(obj.due_date.strftime("%d.%m.%Y") if obj.due_date else ""),
            _csv_cell(obj.status),
            _csv_cell(obj.related_request.record_number if obj.related_request else ""),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "ProjectRisk", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_uat_records(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"uat_sonuclari_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi", "Senaryo Adı", "İlgili Süreç", "Beklenen Sonuç",
        "Gerçekleşen Sonuç", "Sonuç Durumu", "Önem Düzeyi", "Sorumlu Ekip",
        "Test Eden", "Test Eden Rol", "Test Tarihi", "Çözüm Notu", "İlgili Talep",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for obj in queryset.select_related("related_request"):
        writer.writerow([
            _csv_cell(export_date), _csv_cell(obj.scenario_name), _csv_cell(obj.process_area),
            _csv_cell(obj.expected_result), _csv_cell(obj.actual_result),
            _csv_cell(obj.result_status), _csv_cell(obj.severity),
            _csv_cell(obj.responsible_team), _csv_cell(obj.tester_name),
            _csv_cell(obj.tester_role),
            _csv_cell(obj.test_date.strftime("%d.%m.%Y") if obj.test_date else ""),
            _csv_cell(obj.resolution_note),
            _csv_cell(obj.related_request.record_number if obj.related_request else ""),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "UATRecord", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_post_go_live_metrics(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"canli_gecis_gostergeleri_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi", "Gösterge Adı", "Gösterge Kategorisi", "Hedef Değer",
        "Güncel Değer", "Birim", "Durum", "Ölçüm Tarihi", "Sorumlu Ekip", "Değerlendirme Notu",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for obj in queryset:
        writer.writerow([
            _csv_cell(export_date), _csv_cell(obj.metric_name), _csv_cell(obj.metric_category),
            _csv_cell(obj.target_value), _csv_cell(obj.current_value), _csv_cell(obj.unit),
            _csv_cell(obj.status),
            _csv_cell(obj.measurement_date.strftime("%d.%m.%Y") if obj.measurement_date else ""),
            _csv_cell(obj.responsible_team), _csv_cell(obj.evaluation_note),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "PostGoLiveMetric", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_audit_logs(user, organization, queryset, filters=None):
    filters = filters or {}
    filename = f"sistem_denetiim_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi",
        "İşlem Tarihi",
        "Kullanıcı",
        "İşlem",
        "Nesne Türü",
        "Nesne Kimliği",
        "Detay",
        "Proje",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    for obj in queryset:
        user_name = ""
        if obj.user:
            profile = getattr(obj.user, "profile", None)
            user_name = profile.full_name if profile else obj.user.username
        writer.writerow([
            _csv_cell(export_date),
            _csv_cell(timezone.localtime(obj.created_at).strftime("%d.%m.%Y %H:%M")),
            _csv_cell(user_name),
            _csv_cell(obj.action),
            _csv_cell(obj.object_type),
            _csv_cell(obj.object_id),
            _csv_cell(obj.details),
            _csv_cell(obj.project.name if obj.project else ""),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "AuditLog", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_thirty_day_summary(user, organization, summary_data, filters=None):
    filters = filters or {}
    filename = f"sistem_ozet_30gun_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi",
        "Kurum",
        "İzleme Dönemi (Gün)",
        "Toplam İşlem",
        "Aktif Kullanıcı",
        "Kategori",
        "Öğe",
        "Adet",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    org_name = organization.name if organization else ""
    period = summary_data.get("period_days", 30)
    writer.writerow([
        _csv_cell(export_date),
        _csv_cell(org_name),
        _csv_cell(period),
        _csv_cell(summary_data.get("total_actions", 0)),
        _csv_cell(summary_data.get("unique_users", 0)),
        _csv_cell("Özet"),
        _csv_cell("Genel"),
        _csv_cell(""),
    ])
    for item in summary_data.get("top_actions", []):
        writer.writerow([
            _csv_cell(export_date), _csv_cell(org_name), _csv_cell(period),
            _csv_cell(""), _csv_cell(""), _csv_cell("İşlem Türü"),
            _csv_cell(item.get("action", "")), _csv_cell(item.get("count", 0)),
        ])
    for item in summary_data.get("top_users", []):
        name = item.get("user__profile__full_name") or item.get("user__username") or ""
        writer.writerow([
            _csv_cell(export_date), _csv_cell(org_name), _csv_cell(period),
            _csv_cell(""), _csv_cell(""), _csv_cell("Kullanıcı"),
            _csv_cell(name), _csv_cell(item.get("count", 0)),
        ])
    for item in summary_data.get("project_activity", []):
        writer.writerow([
            _csv_cell(export_date), _csv_cell(org_name), _csv_cell(period),
            _csv_cell(""), _csv_cell(""), _csv_cell("Proje Aktivitesi"),
            _csv_cell(item.get("project__name", "")), _csv_cell(item.get("count", 0)),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "SistemÖzeti30", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_monthly_usage(user, organization, usage_data, filters=None):
    filters = filters or {}
    filename = f"sistem_aylik_kullanim_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    headers = [
        "Dışa Aktarma Tarihi",
        "Kurum",
        "Ay",
        "İşlem Sayısı",
    ]
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    export_date = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    org_name = organization.name if organization else ""
    labels = usage_data.get("labels", [])
    values = usage_data.get("values", [])
    for label, value in zip(labels, values):
        writer.writerow([
            _csv_cell(export_date),
            _csv_cell(org_name),
            _csv_cell(label),
            _csv_cell(value),
        ])
    log_audit(user, organization, "CSV Dışa Aktarma", "AylıkKullanım", details=str(filters))
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
