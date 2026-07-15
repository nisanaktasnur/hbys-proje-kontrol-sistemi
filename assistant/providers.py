from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def generate_response(self, question: str, project_context: dict) -> str:
        pass


class DeterministicDataAssistant(AIProvider):
    FALLBACK = (
        "Bu soruyu mevcut proje verileriyle kesin olarak yanıtlayamıyorum. "
        "İlgili kayıtların sisteme eklenmesi veya daha ayrıntılı bilgi sağlanması gerekir."
    )

    def generate_response(self, question: str, project_context: dict) -> str:
        q = (question or "").lower().strip()
        data = project_context
        requests = data.get("requests", [])
        readiness = data.get("readiness", {})
        if not requests and not readiness:
            return self.FALLBACK

        if any(k in q for k in ["en riskli süreç", "riskli süreç", "hangi süreç"]):
            proc = data.get("top_risk_process")
            if proc:
                return (
                    f"Mevcut kayıtlara göre **{proc['name']}** süreci en fazla dikkat gerektiriyor "
                    f"({proc['high']} yüksek, {proc['open']} açık kayıt). "
                    f"Örnek: {proc.get('sample', '—')}."
                )
            return self.FALLBACK

        if any(k in q for k in ["canlı geçiş", "eksik"]):
            parts = []
            if readiness:
                for label, key in [
                    ("Eğitim", "education_status"),
                    ("UAT", "uat_status"),
                    ("Veri aktarımı", "data_migration_status"),
                    ("Yetkilendirme", "authorization_status"),
                ]:
                    val = readiness.get(key, "")
                    if val in ("Eksik", "Riskli", "Beklemede"):
                        parts.append(f"{label}: {val}")
            high_gl = data.get("go_live_high_count", 0)
            msg = "Canlı geçiş değerlendirmesi: "
            if parts:
                msg += "; ".join(parts) + ". "
            else:
                msg += "temel hazırlık alanları izleniyor. "
            if high_gl:
                msg += f"{high_gl} yüksek riskli canlı geçiş etkili talep açık."
            return msg

        if any(k in q for k in ["öncelikli kapat", "hangi talep", "öncelik"]):
            top = data.get("priority_requests", [])
            if not top:
                return "Önceliklendirilecek açık talep bulunmuyor."
            items = [
                f"{r['record_number']} — {r['title']} ({r['status']}, {r['risk_level']})"
                for r in top[:5]
            ]
            return "Öncelikli kapatılması önerilen talepler: " + "; ".join(items) + "."

        if any(k in q for k in ["yönetici", "özet", "kısa özet"]):
            return (
                f"Proje özeti: {data.get('open_count', 0)} açık talep, "
                f"{data.get('high_count', 0)} yüksek riskli, "
                f"{data.get('overdue_count', 0)} geciken kayıt. "
                f"Canlı geçiş durumu: {readiness.get('overall_status', '—')}."
            )

        if any(k in q for k in ["hedef tarih", "geçen talep", "geciken"]):
            overdue = data.get("overdue_requests", [])
            if not overdue:
                return "Hedef tarihi geçmiş açık talep bulunmuyor."
            items = [f"{r['record_number']} — {r['title']} ({r['risk_level']})" for r in overdue[:5]]
            return "Hedef tarihi geçen talepler: " + "; ".join(items) + "."

        if "uat" in q:
            uat = [r for r in requests if "uat" in r.get("process_area", "").lower() or "uat" in r.get("title", "").lower()]
            open_uat = [r for r in uat if r["status"] != "Tamamlandı"]
            if not open_uat:
                return "UAT ile ilişkili açık kayıt bulunmuyor."
            items = [f"{r['record_number']} — {r['title']} ({r['status']}, {r['risk_level']})" for r in open_uat[:5]]
            return f"UAT sürecinde {len(open_uat)} açık kayıt var: " + "; ".join(items) + "."

        if any(k in q for k in ["eğitim", "egitim"]):
            status = readiness.get("education_status", "—")
            if status in ("Tamamlandı",):
                return "Eğitim durumu canlı geçiş için yeterli görünüyor."
            return f"Eğitim durumu: {status}. Canlı geçiş öncesi tamamlanması önerilir."

        if any(k in q for k in ["yetkilendirme", "yetki"]):
            auth_issues = [r for r in requests if "Yetkilendirme" in r.get("process_area", "") and r["status"] != "Tamamlandı"]
            if not auth_issues:
                return "Yetkilendirme ile ilişkili açık kayıt bulunmuyor."
            items = [f"{r['record_number']} — {r['title']}" for r in auth_issues[:5]]
            return "Yetkilendirme sorunları: " + "; ".join(items) + "."

        if any(k in q for k in ["veri aktarım", "veri aktarim"]):
            dm = [r for r in requests if "Veri Aktarımı" in r.get("process_area", "") and r["status"] != "Tamamlandı"]
            if not dm:
                return "Veri aktarımı ile ilişkili açık kayıt bulunmuyor."
            items = [f"{r['record_number']} — {r['title']}" for r in dm[:5]]
            return "Veri aktarımıyla ilgili açık kayıtlar: " + "; ".join(items) + "."

        if any(k in q for k in ["hangi ekip", "daha fazla açık"]):
            team = data.get("top_team")
            if team:
                return f"En fazla açık talebe sahip ekip: **{team['name']}** ({team['count']} kayıt)."
            return self.FALLBACK

        if any(k in q for k in ["proje risk", "olasılık", "etki"]) and "talep" not in q:
            risks = data.get("project_risks", [])
            if not risks:
                return "Kayıtlı proje riski bulunmuyor."
            top = sorted(risks, key=lambda r: (r.get("impact"), r.get("probability")), reverse=True)[:5]
            items = [f"{r['title']} (Olasılık: {r['probability']}, Etki: {r['impact']}, Seviye: {r['risk_level']})" for r in top]
            return "En yüksek olasılık ve etkiye sahip proje riskleri: " + "; ".join(items) + "."

        if any(k in q for k in ["önleyici aksiyon", "önleyici aksiyonu bulunmuyor", "aksiyonu bulunmuyor"]):
            missing = [r for r in data.get("project_risks", []) if not r.get("mitigation_action")]
            if not missing:
                return "Tüm açık proje risklerinde önleyici aksiyon tanımlı görünüyor."
            items = [r["title"] for r in missing[:5]]
            return "Önleyici aksiyonu bulunmayan proje riskleri: " + "; ".join(items) + "."

        if any(k in q for k in ["uat sonuç", "canlı geçişi engel", "engelleyen bulgu"]):
            blocking = data.get("blocking_uat", [])
            if not blocking:
                return "Canlı geçişi engelleyen UAT bulgusu kayıtlarda görünmüyor."
            items = [f"{u['scenario_name']} ({u['result_status']}, {u['severity']})" for u in blocking[:5]]
            return "Canlı geçişi engelleyebilecek UAT bulguları: " + "; ".join(items) + "."

        if any(k in q for k in ["kaç uat", "başarısız", "bloke durum"]):
            summary = data.get("uat_summary", {})
            if not summary.get("total"):
                return "UAT kaydı bulunmuyor."
            return (
                f"UAT durumu: {summary.get('failed', 0)} başarısız, "
                f"{summary.get('blocked', 0)} bloke, {summary.get('retest', 0)} tekrar test bekleyen senaryo."
            )

        if any(k in q for k in ["hedefin altında", "hedef altında", "başarı gösterg"]):
            below = data.get("below_target_metrics", [])
            if not below:
                return "Hedef altında canlı geçiş göstergesi bulunmuyor."
            items = [f"{m['metric_name']} (Güncel: {m['current_value']}, Hedef: {m['target_value']})" for m in below[:5]]
            return "Hedef altındaki göstergeler: " + "; ".join(items) + "."

        if any(k in q for k in ["iyileştirme aksiyon", "öncelikli aksiyon", "hangi aksiyon"]):
            actions = data.get("priority_decisions", [])
            if not actions:
                return "Öncelikli iyileştirme aksiyonu bulunmuyor."
            items = [f"{a['title']} ({a['status']})" for a in actions[:5]]
            return "Öncelikli iyileştirme aksiyonları: " + "; ".join(items) + "."

        if any(k in q for k in ["risk, uat", "uat ve canlı", "canlı geçiş özeti"]):
            summary = data.get("uat_summary", {})
            return (
                f"Yönetici özeti — Açık talep: {data.get('open_count', 0)}, "
                f"yüksek riskli talep: {data.get('high_count', 0)}, "
                f"proje riski (yüksek): {data.get('high_project_risk_count', 0)}, "
                f"UAT başarısız/bloke: {summary.get('failed', 0)}/{summary.get('blocked', 0)}, "
                f"hedef altı gösterge: {data.get('below_target_metric_count', 0)}."
            )

        return self.FALLBACK


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, api_key, api_base, model):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model

    def generate_response(self, question: str, project_context: dict) -> str:
        import json
        import requests

        fallback = DeterministicDataAssistant()
        system_prompt = (
            "Sen bir HBYS proje karar destek asistanısın. "
            "Yalnızca verilen proje verilerine dayanarak Türkçe yanıt ver. "
            "Veri yoksa bunu açıkça belirt. Sayı uydurma."
        )
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Soru: {question}\nVeri: {json.dumps(project_context, ensure_ascii=False)}"},
                    ],
                    "temperature": 0.2,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            return fallback.generate_response(question, project_context)


def get_ai_provider():
    from django.conf import settings

    if settings.OPENAI_API_KEY:
        return OpenAICompatibleProvider(
            settings.OPENAI_API_KEY,
            settings.OPENAI_API_BASE,
            settings.OPENAI_MODEL,
        )
    return DeterministicDataAssistant()


def build_project_context(project, role=None):
    from accounts.models import ApprovalStatus, Membership, Role
    from core.models import AuditLog
    from django.db.models import Count
    from django.utils import timezone

    if role == Role.SISTEM_YONETICISI and project:
        org = project.organization
        return {
            "project_name": project.name,
            "pending_users": Membership.objects.filter(
                organization=org,
                is_active=False,
                user__profile__approval_status=ApprovalStatus.PENDING,
            ).count(),
            "active_users": Membership.objects.filter(organization=org, is_active=True).count(),
            "role_distribution": list(
                Membership.objects.filter(organization=org, is_active=True)
                .values("role")
                .annotate(count=Count("id"))
            ),
            "recent_audit": list(
                AuditLog.objects.filter(organization=org)
                .order_by("-created_at")
                .values("action", "object_type", "details")[:10]
            ),
        }

    from projects.models import (
        DecisionStatus,
        DecisionSupportRecord,
        GoLiveReadiness,
        MetricStatus,
        PostGoLiveMetric,
        ProjectRisk,
        ProjectRiskStatus,
        RequestRecord,
        RequestStatus,
        RiskLevel,
        UATRecord,
        UATResultStatus,
    )
    from projects.services.uat_summary_service import uat_summary

    if not project:
        return {}

    qs = RequestRecord.objects.filter(project=project)
    open_qs = qs.exclude(status=RequestStatus.TAMAMLANDI)
    requests = list(
        open_qs.values("record_number", "title", "status", "risk_level", "process_area", "responsible_team")[:50]
    )
    readiness_obj = GoLiveReadiness.objects.filter(project=project).first()
    readiness = {}
    if readiness_obj:
        readiness = {
            "education_status": readiness_obj.education_status,
            "uat_status": readiness_obj.uat_status,
            "data_migration_status": readiness_obj.data_migration_status,
            "authorization_status": readiness_obj.authorization_status,
            "overall_status": readiness_obj.overall_status,
        }

    process_stats = []
    for p in open_qs.values("process_area").distinct():
        area = p["process_area"]
        area_qs = open_qs.filter(process_area=area)
        process_stats.append({
            "name": area,
            "open": area_qs.count(),
            "high": area_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
            "sample": area_qs.first().title if area_qs.exists() else "",
        })
    process_stats.sort(key=lambda x: (x["high"], x["open"]), reverse=True)

    team_stats = list(
        open_qs.values("responsible_team")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    pr_qs = ProjectRisk.objects.filter(project=project).exclude(status=ProjectRiskStatus.TAMAMLANDI)
    uat_qs = UATRecord.objects.filter(project=project)
    metric_qs = PostGoLiveMetric.objects.filter(project=project)
    decisions = DecisionSupportRecord.objects.filter(project=project).exclude(status=DecisionStatus.TAMAMLANDI)

    return {
        "project_name": project.name,
        "requests": requests,
        "readiness": readiness,
        "open_count": open_qs.count(),
        "high_count": open_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "overdue_count": open_qs.filter(due_date__lt=timezone.localdate()).count(),
        "go_live_high_count": open_qs.filter(risk_level=RiskLevel.YUKSEK, go_live_impact="Yüksek").count(),
        "top_risk_process": process_stats[0] if process_stats else None,
        "top_team": {"name": team_stats[0]["responsible_team"], "count": team_stats[0]["count"]} if team_stats else None,
        "priority_requests": list(
            open_qs.order_by("-risk_level", "due_date").values(
                "record_number", "title", "status", "risk_level"
            )[:10]
        ),
        "overdue_requests": list(
            open_qs.filter(due_date__lt=timezone.localdate()).values(
                "record_number", "title", "risk_level"
            )[:10]
        ),
        "project_risks": list(
            pr_qs.values("title", "probability", "impact", "risk_level", "mitigation_action")[:20]
        ),
        "high_project_risk_count": pr_qs.filter(risk_level=RiskLevel.YUKSEK).count(),
        "uat_summary": uat_summary(uat_qs),
        "blocking_uat": list(
            uat_qs.filter(
                result_status__in=[UATResultStatus.BASARISIZ, UATResultStatus.BLOKE, UATResultStatus.TEKRAR],
                severity=RiskLevel.YUKSEK,
            ).values("scenario_name", "result_status", "severity")[:10]
        ),
        "below_target_metrics": list(
            metric_qs.filter(status=MetricStatus.HEDEF_ALTI).values(
                "metric_name", "current_value", "target_value"
            )[:10]
        ),
        "below_target_metric_count": metric_qs.filter(status=MetricStatus.HEDEF_ALTI).count(),
        "priority_decisions": list(
            decisions.order_by("due_date").values("title", "status", "source")[:10]
        ),
    }
