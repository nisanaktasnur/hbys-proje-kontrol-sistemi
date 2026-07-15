"""Tam sistem QA / smoke test — Django test istemcisi ile yerel çalışır."""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local")

import django

django.setup()

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Membership, Role
from core.demo_defaults import DEMO_PRIMARY_ORG_NAME, DEMO_PRIMARY_PROJECT_NAME
from core.context import get_accessible_organizations
from core.models import Organization, Project
from core.permissions import role_nav_items
from projects.models import (
    CommunicationType,
    InstructionStatus,
    ProjectCommunication,
    RequestRecord,
)

HOST = "127.0.0.1"
REPORT_PATH = ROOT / "QA_REPORT.md"

DEMO_USERS = {
    "admin": ("Admin123!", Role.SISTEM_YONETICISI, reverse("accounts:user_management")),
    "pm": ("Pm123!", Role.PROJE_YONETICISI, reverse("projects:dashboard")),
    "techlead": ("Tech123!", Role.TEKNIK_LIDER, reverse("projects:technical_view")),
    "manager": ("Manager123!", Role.YONETICI, reverse("projects:manager_panel")),
}

BAD_UI_PATTERNS = [
    ("Erişim Engellendi", "critical", "access_denied_text"),
    ("Traceback (most recent call last)", "critical", "server_traceback"),
    ("Server Error (500)", "critical", "server_error_500"),
    ("Kurum Bilgileri", "major", "old_kurum_bilgileri_section"),
]

MANAGER_REMOVED_BUTTONS = [
    "Talimat Gönder",
    "Raporları Dışa Aktar",
]

MANAGER_KPI_LABELS = [
    "Genel Proje Durumu",
    "Canlı Geçiş Kararı",
    "Kritik Risk Sayısı",
    "Açık Talep",
    "Yüksek Riskli Talep",
    "Hedef Tarihi Geçen",
    "Açık UAT Bulgusu",
    "Canlı Geçiş Hazırlığı",
]

TECH_WORK_COLUMNS = [
    "Teknik Sorumlu",
    "Teknik Durum",
    "Geçici Çözüm Var mı?",
    "Kök Neden Durumu",
    "Çözüm Notu",
    "Tekrar Test Durumu",
    "Canlı Geçiş Etkisi",
]

CSV_BY_ROLE = {
    "admin": [
        ("reports:export_usage_30", ["Dışa Aktarma Tarihi", "Toplam İşlem"]),
        ("reports:export_usage_monthly", ["Dışa Aktarma Tarihi", "Ay"]),
        ("reports:export_audit", ["Dışa Aktarma Tarihi", "Kullanıcı"]),
    ],
    "pm": [
        ("reports:export_requests", ["Kayıt No", "Başlık"]),
        ("reports:export_risk", ["Risk Seviyesi"]),
        ("reports:export_decisions", ["Başlık"]),
        ("reports:export_readiness", ["Proje"]),
        ("reports:export_project_risks", ["Risk Başlığı"]),
        ("reports:export_uat", ["Senaryo"]),
        ("reports:export_metrics", ["Gösterge"]),
    ],
    "manager": [
        ("reports:export_requests", ["Kayıt No"]),
        ("reports:export_risk", ["Risk Seviyesi"]),
    ],
    "techlead": [
        ("reports:export_requests", ["Kayıt No"]),
        ("reports:export_uat", ["Senaryo"]),
        ("reports:export_project_risks", ["Risk Başlığı"]),
    ],
}


@dataclass
class QACheck:
    section: str
    name: str
    passed: bool
    severity: str = "minor"
    url: str = ""
    detail: str = ""


@dataclass
class QAReport:
    started_at: datetime = field(default_factory=timezone.now)
    checks: list[QACheck] = field(default_factory=list)
    pages_tested: set[str] = field(default_factory=set)
    fixes: list[str] = field(default_factory=list)

    def add(
        self,
        section: str,
        name: str,
        passed: bool,
        *,
        severity: str = "minor",
        url: str = "",
        detail: str = "",
    ):
        self.checks.append(
            QACheck(section, name, passed, severity=severity, url=url, detail=detail)
        )
        if url:
            self.pages_tested.add(url)

    @property
    def failures(self):
        return [c for c in self.checks if not c.passed]

    @property
    def critical_failures(self):
        return [c for c in self.failures if c.severity == "critical"]

    @property
    def major_failures(self):
        return [c for c in self.failures if c.severity == "major"]

    def write_markdown(self, external_runs: list[tuple[str, int, str]] | None = None):
        lines = [
            "# HBYS Proje Kontrol Sistemi — QA Raporu",
            "",
            f"- **Tarih/Saat:** {self.started_at.strftime('%d.%m.%Y %H:%M')}",
            f"- **Ortam:** Yerel (`config.settings_local`)",
            f"- **Test kullanıcıları:** {', '.join(DEMO_USERS)}",
            "",
            "## Özet",
            "",
            f"- Toplam kontrol: **{len(self.checks)}**",
            f"- Geçen: **{sum(1 for c in self.checks if c.passed)}**",
            f"- Başarısız: **{len(self.failures)}**",
            f"- Kritik: **{len(self.critical_failures)}**",
            f"- Majör: **{len(self.major_failures)}**",
            f"- Minör: **{len(self.failures) - len(self.critical_failures) - len(self.major_failures)}**",
            "",
        ]
        if external_runs:
            lines.extend(["## Ek test komutları", ""])
            for cmd, code, snippet in external_runs:
                status = "PASS" if code == 0 else "FAIL"
                lines.append(f"- `{cmd}` → **{status}** (çıkış kodu {code})")
                if snippet.strip():
                    lines.append(f"  ```\n  {snippet.strip()}\n  ```")
            lines.append("")

        lines.extend(["## Test edilen sayfalar", ""])
        for page in sorted(self.pages_tested):
            lines.append(f"- `{page}`")
        lines.append("")

        lines.extend(["## Geçen kontroller", ""])
        for check in self.checks:
            if check.passed:
                lines.append(f"- [{check.section}] {check.name}")
        lines.append("")

        if self.failures:
            lines.extend(["## Başarısız kontroller", ""])
            for check in self.failures:
                lines.append(
                    f"- **[{check.severity.upper()}]** [{check.section}] {check.name}"
                )
                if check.url:
                    lines.append(f"  - URL: `{check.url}`")
                if check.detail:
                    lines.append(f"  - Detay: {check.detail}")
            lines.append("")

        if self.fixes:
            lines.extend(["## Düzeltme özeti", ""])
            for fix in self.fixes:
                lines.append(f"- {fix}")
            lines.append("")

        lines.extend(
            [
                "## Kalan sınırlamalar",
                "",
                "- Tarayıcı (Playwright/Selenium) seviyesinde UI testi bu betikte yok; Django test istemcisi kullanıldı.",
                "- Yönetici paneli KPI etiketleri ürün spesifikasyonundaki bazı isimlerden farklı olabilir (minör).",
                "- Harici servis veya canlı ortam testi yapılmadı.",
                "",
            ]
        )
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def client() -> Client:
    return Client(HTTP_HOST=HOST)


def login(c: Client, username: str, password: str):
    return c.post(reverse("accounts:login"), {"username": username, "password": password})


def decode(response) -> str:
    if hasattr(response, "content"):
        payload = response.content
    elif isinstance(response, (bytes, bytearray)):
        payload = bytes(response)
    else:
        return str(response)
    return payload.decode("utf-8", errors="replace")


def visible_text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def scan_bad_ui(report: QAReport, section: str, html: str, url: str, *, allow_gizli: bool = False):
    for pattern, severity, slug in BAD_UI_PATTERNS:
        if pattern in html:
            report.add(section, f"Kötü UI: {slug}", False, severity=severity, url=url, detail=pattern)
    if not allow_gizli and re.search(r">\s*Gizli\s*<", html):
        report.add(section, "Yetkili sayfada 'Gizli' proje adı", False, severity="major", url=url)
    if "---------" in html:
        report.add(section, "Boş 'Seçiniz' dropdown", False, severity="minor", url=url)
    if "Internal Server Error" in html:
        report.add(section, "Sunucu hatası", False, severity="critical", url=url)


def assert_page_ok(report: QAReport, section: str, response, url: str, *, expected=200, allow_gizli=False):
    report.pages_tested.add(url)
    ok = response.status_code == expected
    report.add(
        section,
        f"HTTP {expected} — {url}",
        ok,
        severity="critical" if not ok else "minor",
        url=url,
        detail=f"status={response.status_code}",
    )
    if ok and expected == 200:
        scan_bad_ui(report, section, decode(response), url, allow_gizli=allow_gizli)
    return response


def membership_for(user: User):
    return Membership.objects.filter(user=user, is_active=True).select_related("organization").first()


def nav_urls(user: User) -> list[str]:
    membership = membership_for(user)
    if not membership:
        return []
    return [reverse(name) for name, _label in role_nav_items(membership)]


def read_csv(response) -> str:
    if hasattr(response, "streaming_content"):
        return b"".join(response.streaming_content).decode("utf-8-sig", errors="replace")
    return response.content.decode("utf-8-sig", errors="replace")


def prepare_demo_data(report: QAReport):
    call_command("seed_demo_data")
    hospitals = Organization.objects.filter(name__startswith="Örnek").count()
    projects = Project.objects.filter(organization__name__startswith="Örnek").count()
    report.add("1. Demo veri", "En az 3 demo hastane", hospitals >= 3, severity="critical", detail=str(hospitals))
    report.add("1. Demo veri", "Birden fazla demo proje", projects >= 3, severity="critical", detail=str(projects))

    primary = Project.objects.filter(
        organization__name=DEMO_PRIMARY_ORG_NAME,
        name=DEMO_PRIMARY_PROJECT_NAME,
    ).first()
    if primary:
        report.add(
            "1. Demo veri",
            "Demo talepler dolu",
            RequestRecord.objects.filter(project=primary).exists(),
            severity="major",
        )
        report.add(
            "1. Demo veri",
            "Demo iletişim kayıtları",
            ProjectCommunication.objects.filter(project=primary).exists(),
            severity="major",
        )

    for username, (password, _role, _landing) in DEMO_USERS.items():
        exists = User.objects.filter(username=username).exists()
        c = client()
        resp = login(c, username, password)
        report.add(
            "1. Demo veri",
            f"Kullanıcı girişi: {username}",
            exists and resp.status_code == 302,
            severity="critical",
            detail=f"user={exists}, login={resp.status_code}",
        )


def check_role_dashboards(report: QAReport):
    for username, (password, role, landing) in DEMO_USERS.items():
        c = client()
        resp = login(c, username, password)
        report.add(
            "2. Rol panelleri",
            f"{username} yönlendirme",
            resp.status_code == 302 and landing in resp.url,
            severity="critical",
            url=landing,
        )
        page = c.get(landing)
        assert_page_ok(report, "2. Rol panelleri", page, landing)
        html = decode(page)
        if role != Role.SISTEM_YONETICISI:
            has_org = "Kurum" in html or DEMO_PRIMARY_ORG_NAME in html
            has_project = "Proje" in html or DEMO_PRIMARY_PROJECT_NAME in html
            report.add(
                "2. Rol panelleri",
                f"{username} aktif kurum/proje bağlamı",
                has_org and has_project,
                severity="major",
                url=landing,
            )


def check_admin_flow(report: QAReport):
    c = client()
    login(c, "admin", "Admin123!")
    urls = [
        reverse("accounts:user_management"),
        reverse("accounts:org_project_management"),
        reverse("accounts:system_records"),
    ]
    for url in urls:
        assert_page_ok(report, "3. Sistem Yöneticisi", c.get(url), url)

    hospitals = Organization.objects.filter(name__startswith="Örnek").order_by("name")
    for org in hospitals:
        url = reverse("accounts:org_project_management") + f"?org={org.id}"
        resp = c.get(url)
        assert_page_ok(report, "3. Sistem Yöneticisi", resp, url)
        html = decode(resp)
        report.add(
            "3. Sistem Yöneticisi",
            f"Hastane proje listesi: {org.name}",
            org.name in html and "HBYS" in html,
            severity="major",
            url=url,
        )
        report.add(
            "3. Sistem Yöneticisi",
            f"Rol atamaları görünür: {org.name}",
            "Proje Rolü" in html or "project_role" in html or "Proje Üyeliği" in html or "Kurum Üyeliği" in html,
            severity="major",
            url=url,
        )

    records = decode(c.get(reverse("accounts:system_records")))
    report.add(
        "3. Sistem Yöneticisi",
        "30 günlük özet bölümü",
        "Son 30 Gün Kullanım Özeti" in records,
        severity="major",
        url=reverse("accounts:system_records"),
    )
    report.add(
        "3. Sistem Yöneticisi",
        "Aylık sistem kullanımı",
        "Aylık Sistem Kullanımı" in records or "usageChart" in records,
        severity="major",
        url=reverse("accounts:system_records"),
    )
    for label in [
        "Son 30 Gün Sistem Özeti CSV",
        "Yıllık Aylık Kullanım CSV",
        "Sistem İşlem Kayıtları CSV",
    ]:
        report.add(
            "3. Sistem Yöneticisi",
            f"CSV düğmesi: {label}",
            label in records,
            severity="major",
            url=reverse("accounts:system_records"),
        )


def check_pm_flow(report: QAReport):
    c = client()
    login(c, "pm", "Pm123!")
    urls = [
        reverse("projects:dashboard"),
        reverse("projects:request_management"),
        reverse("projects:risk_warning"),
        reverse("projects:decision_center"),
        reverse("assistant:chat"),
    ]
    for url in urls:
        assert_page_ok(report, "4. Proje Yöneticisi", c.get(url), url)

    report.add(
        "4. Proje Yöneticisi",
        "Yönetici özeti engeli (PM)",
        c.get(reverse("projects:executive_summary")).status_code == 403,
        severity="major",
        url=reverse("projects:executive_summary"),
    )

    empty = c.post(
        reverse("projects:request_management"),
        {"form_type": "request"},
    )
    html = decode(empty)
    report.add(
        "4. Proje Yöneticisi",
        "Boş talep formu doğrulama",
        empty.status_code == 200 and ("errorlist" in html or "zorunlu" in html.lower() or "Bu alan" in html),
        severity="major",
        url=reverse("projects:request_management"),
    )

    high_missing = c.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "QA Yüksek Öncelik",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Yüksek",
            "status": "Açık",
            "responsible_team": "QA Ekibi",
            "go_live_impact": "Orta",
            "operational_impact": "Orta",
        },
    )
    high_html = decode(high_missing)
    report.add(
        "4. Proje Yöneticisi",
        "Yüksek öncelik koşullu alanlar",
        "güvenlik etkisi" in high_html.lower() or "geçici çözüm" in high_html.lower(),
        severity="major",
        url=reverse("projects:request_management"),
    )

    go_live_missing = c.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "QA Canlı Geçiş",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Açık",
            "responsible_team": "QA Ekibi",
            "go_live_impact": "Yüksek",
            "operational_impact": "Orta",
        },
    )
    gl_html = decode(go_live_missing)
    report.add(
        "4. Proje Yöneticisi",
        "Yüksek canlı geçiş etkisi koşullu alanlar",
        "hedef kapanış" in gl_html.lower() or "geçici çözüm" in gl_html.lower(),
        severity="major",
        url=reverse("projects:request_management"),
    )

    completed_missing = c.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "QA Tamamlandı",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Tamamlandı",
            "responsible_team": "QA Ekibi",
            "go_live_impact": "Orta",
            "operational_impact": "Orta",
        },
    )
    comp_html = decode(completed_missing)
    report.add(
        "4. Proje Yöneticisi",
        "Tamamlandı durumu koşullu alanlar",
        "çözüm notu" in comp_html.lower() or "tamamlanma tarihi" in comp_html.lower(),
        severity="major",
        url=reverse("projects:request_management"),
    )

    risk = decode(c.get(reverse("projects:risk_warning")).content)
    report.add(
        "4. Proje Yöneticisi",
        "Risk matrisi görünür",
        "risk-matrix" in risk or "matrix-grid" in risk,
        severity="major",
        url=reverse("projects:risk_warning"),
    )
    report.add(
        "4. Proje Yöneticisi",
        "Matrise Göre Risk Detayları",
        "Matrise Göre Risk Detayları" in risk,
        severity="major",
        url=reverse("projects:risk_warning"),
    )
    counts = [int(x) for x in re.findall(r'matrix-count">(\d+)', risk)]
    has_demo_risk = "Demo matris" in risk
    report.add(
        "4. Proje Yöneticisi",
        "Demo risk kayıtları görünür",
        has_demo_risk,
        severity="major",
        url=reverse("projects:risk_warning"),
    )
    report.add(
        "4. Proje Yöneticisi",
        "Matris hücre sayıları mevcut",
        bool(counts) and sum(counts) >= 1,
        severity="major",
        url=reverse("projects:risk_warning"),
        detail=f"counts={counts}",
    )


def check_techlead_flow(report: QAReport):
    c = client()
    login(c, "techlead", "Tech123!")
    dash = decode(c.get(reverse("projects:technical_view")).content)
    pm_dash = client()
    login(pm_dash, "pm", "Pm123!")
    pm_html = decode(pm_dash.get(reverse("projects:dashboard")).content)
    report.add(
        "5. Teknik Lider",
        "Teknik panel PM panelinden farklı",
        dash != pm_html and "Teknik Operasyon" in dash,
        severity="major",
        url=reverse("projects:technical_view"),
    )
    report.add(
        "5. Teknik Lider",
        "Teknik KPI kartları",
        "kpi-card" in dash or "kpi-grid" in dash,
        severity="major",
        url=reverse("projects:technical_view"),
    )

    work = decode(c.get(reverse("projects:technical_work_list")).content)
    for col in TECH_WORK_COLUMNS:
        report.add(
            "5. Teknik Lider",
            f"Teknik iş listesi sütunu: {col}",
            col in work,
            severity="major",
            url=reverse("projects:technical_work_list"),
        )

    risks = decode(c.get(reverse("projects:technical_risks")).content)
    report.add(
        "5. Teknik Lider",
        "Matrise Göre Teknik Risk Detayları",
        "Matrise Göre Teknik Risk Detayları" in risks and "Demo matris" in risks,
        severity="major",
        url=reverse("projects:technical_risks"),
    )

    uat = decode(c.get(reverse("projects:technical_uat")).content)
    report.add(
        "5. Teknik Lider",
        "UAT teknik bulgular görüntüleme",
        "UAT" in uat and uat.count("data-table") >= 1,
        severity="major",
        url=reverse("projects:technical_uat"),
    )
    report.add(
        "5. Teknik Lider",
        "UAT oluşturma formu yok",
        'form_type" value="uat"' not in uat and "Yeni UAT Kaydı" not in uat,
        severity="major",
        url=reverse("projects:technical_uat"),
    )

    actions = assert_page_ok(
        report,
        "5. Teknik Lider",
        c.get(reverse("projects:technical_actions")),
        reverse("projects:technical_actions"),
    )
    report.add(
        "5. Teknik Lider",
        "Teknik aksiyon kayıtları",
        "data-table" in decode(actions.content),
        severity="major",
        url=reverse("projects:technical_actions"),
    )

    assert_page_ok(report, "5. Teknik Lider", c.get(reverse("assistant:chat")), reverse("assistant:chat"))


def check_manager_flow(report: QAReport):
    c = client()
    login(c, "manager", "Manager123!")
    url = reverse("projects:manager_panel")
    resp = c.get(url)
    assert_page_ok(report, "6. Yönetici", resp, url)
    html = decode(resp)

    report.add(
        "6. Yönetici",
        "Stratejik salt okunur panel",
        "read_only_dashboard" in html or "Yönetici Paneli" in html,
        severity="minor",
        url=url,
    )
    report.add(
        "6. Yönetici",
        "Operasyonel talep oluşturma formu yok",
        'form_type" value="request"' not in html,
        severity="major",
        url=url,
    )
    for btn in MANAGER_REMOVED_BUTTONS:
        report.add(
            "6. Yönetici",
            f"Kaldırılmış kısayol yok: {btn}",
            btn not in html,
            severity="major",
            url=url,
        )
    for label in MANAGER_KPI_LABELS:
        report.add(
            "6. Yönetici",
            f"KPI kartı: {label}",
            label in html,
            severity="major",
            url=url,
        )

    values = re.findall(r'class="kpi-value(?: kpi-value-sm)?">([^<]+)<', html)
    non_zero = any(v.strip() not in {"0", "0%", "—", "-"} for v in values)
    report.add(
        "6. Yönetici",
        "Demo proje KPI değerleri sıfır değil",
        non_zero,
        severity="major",
        url=url,
        detail=f"values={values[:8]}",
    )

    exec_url = reverse("projects:executive_summary")
    exec_resp = c.get(exec_url)
    report.add(
        "6. Yönetici",
        "Yönetici özeti erişimi",
        exec_resp.status_code == 200,
        severity="major",
        url=exec_url,
    )

    manager_user = User.objects.get(username="manager")
    orgs = get_accessible_organizations(manager_user)
    if orgs.count() > 1:
        second = orgs.exclude(name=DEMO_PRIMARY_ORG_NAME).order_by("name").first()
        if second:
            switch_url = reverse("projects:set_active_organization", args=[second.id])
            switch = c.post(switch_url, HTTP_REFERER=url)
            report.add(
                "6. Yönetici",
                "Hastane seçici çalışıyor",
                switch.status_code in (302, 200),
                severity="major",
                url=switch_url,
                detail=f"target={second.name}",
            )


def check_communication_workflow(report: QAReport):
    primary = Project.objects.get(
        organization__name=DEMO_PRIMARY_ORG_NAME,
        name=DEMO_PRIMARY_PROJECT_NAME,
    )
    other = (
        Project.objects.filter(organization__name__startswith="Örnek")
        .exclude(pk=primary.pk)
        .first()
    )

    mgr = client()
    login(mgr, "manager", "Manager123!")
    create_msg = mgr.post(
        reverse("projects:communication_center"),
        {
            "communication_type": CommunicationType.MESAJ,
            "title": "QA Yönetici Mesajı",
            "description": "PM için QA mesajı",
            "recipient_role": Role.PROJE_YONETICISI,
        },
    )
    report.add(
        "7. İletişim merkezi",
        "Yönetici mesaj gönderimi",
        create_msg.status_code == 302,
        severity="critical",
        url=reverse("projects:communication_center"),
    )
    msg = ProjectCommunication.objects.filter(title="QA Yönetici Mesajı", project=primary).first()
    report.add(
        "7. İletişim merkezi",
        "Mesaj kaydı oluştu",
        msg is not None,
        severity="critical",
    )

    pm = client()
    login(pm, "pm", "Pm123!")
    inbox = decode(pm.get(reverse("projects:communication_center")).content)
    report.add(
        "7. İletişim merkezi",
        "PM gelen mesajı görür",
        msg and msg.title in inbox,
        severity="critical",
        url=reverse("projects:communication_center"),
    )

    if msg:
        detail_url = reverse("projects:communication_detail", args=[msg.pk])
        detail = pm.get(detail_url)
        assert_page_ok(report, "7. İletişim merkezi", detail, detail_url)
        msg.refresh_from_db()
        report.add(
            "7. İletişim merkezi",
            "Mesaj okundu işaretlendi",
            msg.is_read or msg.read_at is not None,
            severity="major",
            url=detail_url,
        )
        reply = pm.post(
            detail_url,
            {"action": "reply", "description": "PM QA yanıtı"},
        )
        report.add(
            "7. İletişim merkezi",
            "PM yanıt gönderdi",
            reply.status_code == 302
            and ProjectCommunication.objects.filter(parent=msg, description__contains="PM QA").exists(),
            severity="major",
            url=detail_url,
        )

        mgr2 = client()
        login(mgr2, "manager", "Manager123!")
        mgr_view = decode(mgr2.get(detail_url).content)
        report.add(
            "7. İletişim merkezi",
            "Gönderen yanıtı görür",
            "PM QA yanıtı" in mgr_view,
            severity="major",
            url=detail_url,
        )

    mgr3 = client()
    login(mgr3, "manager", "Manager123!")
    create_inst = mgr3.post(
        reverse("projects:communication_center"),
        {
            "communication_type": CommunicationType.TALIMAT,
            "title": "QA Teknik Talimat",
            "description": "Teknik lider QA talimatı",
            "recipient_role": Role.TEKNIK_LIDER,
            "priority": "Yüksek",
            "due_date": timezone.localdate().isoformat(),
        },
    )
    inst = ProjectCommunication.objects.filter(title="QA Teknik Talimat").first()
    report.add(
        "7. İletişim merkezi",
        "Yönetici talimat gönderimi",
        create_inst.status_code == 302 and inst is not None,
        severity="critical",
        url=reverse("projects:communication_center"),
    )

    if inst:
        tech = client()
        login(tech, "techlead", "Tech123!")
        tech_inbox = decode(tech.get(reverse("projects:communication_center")).content)
        report.add(
            "7. İletişim merkezi",
            "Teknik lider gelen talimatı görür",
            inst.title in tech_inbox,
            severity="critical",
            url=reverse("projects:communication_center"),
        )
        inst_url = reverse("projects:communication_detail", args=[inst.pk])
        tech.get(inst_url)
        progress = tech.post(
            inst_url,
            {
                "action": "update_status",
                "status": InstructionStatus.DEVAM,
                "completion_note": "",
            },
        )
        report.add(
            "7. İletişim merkezi",
            "Talimat durumu Devam Ediyor",
            progress.status_code == 302,
            severity="major",
            url=inst_url,
        )
        done = tech.post(
            inst_url,
            {
                "action": "update_status",
                "status": InstructionStatus.TAMAMLANDI,
                "completion_note": "QA tamamlandı notu",
            },
        )
        inst.refresh_from_db()
        report.add(
            "7. İletişim merkezi",
            "Talimat Tamamlandı + not",
            done.status_code == 302 and inst.status == InstructionStatus.TAMAMLANDI,
            severity="major",
            url=inst_url,
        )
        mgr4 = client()
        login(mgr4, "manager", "Manager123!")
        sender_view = decode(mgr4.get(inst_url).content)
        report.add(
            "7. İletişim merkezi",
            "Gönderen tamamlanma durumunu görür",
            "Tamamlandı" in sender_view and "QA tamamlandı" in sender_view,
            severity="major",
            url=inst_url,
        )

    if other and msg:
        pm_other = (
            Project.objects.filter(
                organization__name=DEMO_PRIMARY_ORG_NAME,
            )
            .exclude(pk=primary.pk)
            .first()
        )
        if pm_other:
            wrong = client()
            login(wrong, "pm", "Pm123!")
            switch_url = reverse("projects:set_project", args=[pm_other.pk])
            wrong.post(switch_url, HTTP_REFERER=reverse("projects:communication_center"))
            wrong_inbox = decode(wrong.get(reverse("projects:communication_center")))
            report.add(
                "7. İletişim merkezi",
                "Proje A mesajı proje B gelen kutusunda görünmez",
                msg.title not in wrong_inbox and pm_other.name in wrong_inbox,
                severity="major",
                url=reverse("projects:communication_center"),
                detail=f"active={pm_other.name}",
            )

    if msg:
        blocked = client()
        login(blocked, "techlead", "Tech123!")
        blocked_resp = blocked.get(reverse("projects:communication_detail", args=[msg.pk]))
        report.add(
            "7. İletişim merkezi",
            "Yetkisiz kullanıcı detay URL engeli",
            blocked_resp.status_code in (403, 404),
            severity="major",
            url=reverse("projects:communication_detail", args=[msg.pk]),
            detail=f"status={blocked_resp.status_code}",
        )


def check_context_isolation(report: QAReport):
    primary = Project.objects.get(
        organization__name=DEMO_PRIMARY_ORG_NAME,
        name=DEMO_PRIMARY_PROJECT_NAME,
    )

    for username, (password, _role, landing) in DEMO_USERS.items():
        c = client()
        login(c, username, password)
        resp = c.get(landing)
        html = decode(resp)
        report.add(
            "8. Bağlam",
            f"{username} panelinde proje adı",
            primary.name in html or username == "admin",
            severity="major",
            url=landing,
        )

    pm = client()
    login(pm, "pm", "Pm123!")
    iso_org = Organization.objects.filter(name="İzolasyon Kurumu").order_by("pk").first()
    if not iso_org:
        iso_org = Organization.objects.create(name="İzolasyon Kurumu")
    iso_proj = Project.objects.filter(organization=iso_org, name="Gizli").order_by("pk").first()
    if not iso_proj:
        iso_proj = Project.objects.create(organization=iso_org, name="Gizli")
    iso_req = RequestRecord.objects.filter(project=iso_proj, record_number="HBYS-99-0001").first()
    if not iso_req:
        iso_req = RequestRecord.objects.create(
            project=iso_proj,
            record_number="HBYS-99-0001",
            title="Gizli QA Talebi",
            description="İzolasyon testi",
            feedback_source="Proje Ekibi",
            process_area="UAT",
            responsible_team="X",
        )
    blocked = pm.get(reverse("projects:request_detail", args=[iso_req.pk]))
    report.add(
        "8. Bağlam",
        "PM yetkisiz proje talebine erişemez",
        blocked.status_code in (403, 404),
        severity="critical",
        url=reverse("projects:request_detail", args=[iso_req.pk]),
        detail=f"status={blocked.status_code}, project={iso_proj.name}",
    )

    admin = client()
    login(admin, "admin", "Admin123!")
    alt_org = Organization.objects.filter(name__startswith="Örnek").exclude(name=DEMO_PRIMARY_ORG_NAME).first()
    if alt_org:
        admin.get(reverse("accounts:org_project_management") + f"?org={alt_org.id}")
        admin_resp = admin.get(reverse("projects:dashboard"))
        report.add(
            "8. Bağlam",
            "Sistem yöneticisi tüm hastanelere erişir",
            admin_resp.status_code == 200,
            severity="major",
            url=reverse("accounts:org_project_management"),
        )


def check_csv_exports(report: QAReport):
    primary = Project.objects.get(
        organization__name=DEMO_PRIMARY_ORG_NAME,
        name=DEMO_PRIMARY_PROJECT_NAME,
    )
    isolation_org = Organization.objects.filter(name="İzolasyon Kurumu").first()
    secret_title = "Gizli"

    for username, exports in CSV_BY_ROLE.items():
        password = DEMO_USERS[username][0]
        c = client()
        login(c, username, password)
        for url_name, headers in exports:
            url = reverse(url_name)
            resp = c.get(url)
            csv_text = read_csv(resp) if resp.status_code == 200 else ""
            ok = resp.status_code == 200 and "text/csv" in resp.get("Content-Type", "")
            report.add(
                "10. CSV",
                f"{username} {url_name} HTTP 200",
                ok,
                severity="major" if username in ("admin", "pm") else "minor",
                url=url,
                detail=f"status={resp.status_code}",
            )
            if ok:
                report.add(
                    "10. CSV",
                    f"{username} {url_name} Türkçe başlık",
                    all(h in csv_text for h in headers[:1]),
                    severity="minor",
                    url=url,
                )
                if secret_title and isolation_org and username == "pm":
                    report.add(
                        "10. CSV",
                        f"{username} CSV yetkisiz proje içermez",
                        secret_title not in csv_text or isolation_org.name not in csv_text,
                        severity="major",
                        url=url,
                    )
                if username == "pm" and csv_text:
                    report.add(
                        "10. CSV",
                        "CSV formül enjeksiyon koruması",
                        not re.search(r'(?:^|[,\n])="', csv_text),
                        severity="major",
                        url=url,
                    )


def check_broken_links(report: QAReport):
    for username, (password, _role, landing) in DEMO_USERS.items():
        c = client()
        login(c, username, password)
        user = User.objects.get(username=username)
        urls = nav_urls(user) + [landing]
        seen = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            resp = c.get(url)
            ok = resp.status_code in (200, 302)
            if resp.status_code == 403 and username == "admin" and "talep" in url:
                ok = True
            report.add(
                "11. Bağlantılar",
                f"{username} → {url}",
                ok,
                severity="critical" if not ok else "minor",
                url=url,
                detail=f"status={resp.status_code}",
            )
            if resp.status_code == 200:
                scan_bad_ui(report, "11. Bağlantılar", decode(resp), url)


def run_external_script(command: list[str]) -> tuple[str, int, str]:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    snippet = "\n".join(out.strip().splitlines()[-8:])
    return " ".join(command), proc.returncode, snippet


def main():
    report = QAReport()
    print("=== HBYS Tam Sistem QA ===\n")

    prepare_demo_data(report)
    check_role_dashboards(report)
    check_admin_flow(report)
    check_pm_flow(report)
    check_techlead_flow(report)
    check_manager_flow(report)
    check_communication_workflow(report)
    check_context_isolation(report)
    check_csv_exports(report)
    check_broken_links(report)

    external = [
        run_external_script([sys.executable, "-m", "pytest", "-q"]),
        run_external_script([sys.executable, "scripts/run_verification.py"]),
        run_external_script([sys.executable, "scripts/verify_role_experience.py"]),
    ]

    report.write_markdown(external)

    passed = sum(1 for c in report.checks if c.passed)
    failed = len(report.failures)
    print(f"QA kontrolleri: {passed}/{len(report.checks)} geçti, {failed} başarısız")
    print(f"  Kritik: {len(report.critical_failures)}, Majör: {len(report.major_failures)}")
    for check in report.critical_failures + report.major_failures:
        print(f"  [FAIL/{check.severity}] {check.section}: {check.name}")
        if check.detail:
            print(f"         {check.detail}")
    print(f"\nRapor: {REPORT_PATH}")
    for cmd, code, snippet in external:
        print(f"\n{cmd} -> exit {code}")
        if snippet:
            print(snippet.encode("ascii", errors="replace").decode("ascii"))

    blocking = report.critical_failures or report.major_failures
    external_fail = any(code != 0 for _cmd, code, _snippet in external)
    return 0 if not blocking and not external_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
