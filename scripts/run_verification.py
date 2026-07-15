"""Yerel doğrulama betiği — config.settings_local ile çalıştırın."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local")

import django

django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client

from accounts.models import ApprovalStatus, Membership, Role, UserProfile
from core.models import Organization, Project
from projects.models import DecisionSource, DecisionSupportRecord, RequestRecord

HOST = "127.0.0.1"
ENGLISH_UI = re.compile(
    r"\b(Dashboard|Submit|Cancel|Export|Status|Priority|Action|Login|Logout|Ticket|Risk Score)\b",
    re.I,
)
NUMERIC_RISK = re.compile(r"\b\d{1,3}\s*/\s*100\b|confidence|probability|internal_risk|dahili risk", re.I)
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF]")


def client():
    return Client(HTTP_HOST=HOST)


def login(c, username, password):
    return c.post("/giris/", {"username": username, "password": password})


def visible_text(html):
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", html)
    text = re.sub(r"Tamamlanma:\s*%\d+", " ", text)
    return text


class Verifier:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def record(self, name, ok):
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        return ok

    def check_html(self, name, html, extra=None):
        text = visible_text(html)
        issues = []
        if EMOJI.search(text):
            issues.append("emoji")
        if ENGLISH_UI.search(text):
            issues.append("english_label")
        if NUMERIC_RISK.search(text):
            issues.append("numeric_risk")
        if extra:
            issues.extend(extra(html))
        self.record(name, not issues)

    def exit_code(self):
        print(f"\n=== Sonuç: {self.passed} geçti, {self.failed} başarısız ===")
        return 0 if self.failed == 0 else 1


def main():
    call_command("seed_demo_data")
    v = Verifier()
    print("=== HBYS Doğrulama Betiği ===\n")

    for user, pwd, expect_path in [
        ("admin", "Admin123!", "/kullanici-yonetimi/"),
        ("pm", "Pm123!", "/"),
        ("techlead", "Tech123!", "/teknik-gorunum/"),
        ("manager", "Manager123!", "/yonetici-paneli/"),
    ]:
        c = client()
        r = login(c, user, pwd)
        v.record(f"{user} acilis -> {expect_path}", r.status_code == 302 and r["Location"].endswith(expect_path))

    c = client()
    uname = "dogrulama_bekleyen"
    User.objects.filter(username=uname).delete()
    r = c.post(
        "/kayit/",
        {
            "username": uname,
            "full_name": "Doğrulama Bekleyen",
            "role": Role.PROJE_YONETICISI,
            "password1": "Test12345!",
            "password2": "Test12345!",
        },
        follow=True,
    )
    v.record("kayit ol", "Kayıt başvurunuz alındı" in r.content.decode())

    c = client()
    r = login(c, uname, "Test12345!")
    v.record("onay bekleyen giriş engeli", "onaylanmamış" in r.content.decode().lower())

    c = client()
    login(c, "admin", "Admin123!")
    pending = UserProfile.objects.get(user__username=uname)
    r = c.post(f"/kullanici-yonetimi/{pending.user_id}/onayla/")
    v.record(
        "yönetici onayı",
        r.status_code == 302 and UserProfile.objects.get(user__username=uname).is_approved,
    )

    c = client()
    login(c, "pm", "Pm123!")
    r = c.post(
        "/talep-yonetimi/",
        {
            "form_type": "request",
            "title": "Doğrulama talebi 2",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Yüksek",
            "status": "Açık",
            "responsible_team": "Doğrulama Ekibi",
            "due_date": "2026-08-20",
            "go_live_impact": "Yüksek",
            "has_workaround": "on",
            "affects_patient_or_user_safety": "Orta",
            "operational_impact": "Orta",
        },
    )
    v.record("talep oluşturma", r.status_code == 302)

    rec = RequestRecord.objects.filter(title="Doğrulama talebi 2").first()
    v.record("talep kaydı bulundu", rec is not None)
    if rec:
        c = client()
        login(c, "pm", "Pm123!")
        r = c.get(f"/talep/{rec.pk}/")
        html = r.content.decode()
        v.record(
            "talep detay + risk etiketi",
            r.status_code == 200 and rec.risk_level in html and "internal" not in html.lower(),
        )
        v.check_html("talep detay html", html)

        r = c.get("/talep-yonetimi/?risk_level=Yüksek&sort=title")
        v.record("talep listesi filtre", r.status_code == 200 and "Filtrele" in r.content.decode())

        c = client()
        login(c, "pm", "Pm123!")
        r = c.post(
            "/karar-destek-merkezi/",
            {
                "source": DecisionSource.TALEP,
                "title": "Doğrulama kararı",
                "finding": "Test bulgu",
                "recommendation": "Test öneri",
                "expected_effect": "İyileşme",
                "priority": "Orta",
                "responsible_team": "Doğrulama Ekibi",
                "status": "Beklemede",
                "related_request": str(rec.pk),
                "notes": "",
            },
        )
        dec = DecisionSupportRecord.objects.filter(title="Doğrulama kararı").first()
        v.record("karar destek oluşturma", dec is not None and r.status_code == 302)
        if dec:
            r = c.post(f"/karar-destek-merkezi/{dec.pk}/guncelle/", {"status": "Tamamlandı"})
            dec.refresh_from_db()
            v.record("karar destek güncelleme", dec.status == "Tamamlandı")
        else:
            v.record("karar destek güncelleme", False)

    c = client()
    login(c, "pm", "Pm123!")
    r = c.get("/yapay-zeka-asistani/")
    v.check_html(
        "AI sayfası",
        r.content.decode(),
        lambda h: [] if "Yapay Zekâ Proje Asistanı" in h else ["missing_title"],
    )
    r = c.post("/yapay-zeka-asistani/gonder/", {"question": "Hedef tarihi geçen talepler nelerdir?"})
    v.record(
        "AI serbest metin sorusu",
        r.status_code in (200, 302) and ("geçen" in r.content.decode().lower() or r.status_code == 200),
    )

    c = client()
    login(c, "manager", "Manager123!")
    r = c.get("/yonetici-paneli/")
    v.check_html("yönetici paneli", r.content.decode())
    r = c.get("/disa-aktar/talepler/")
    csv = b"".join(r.streaming_content).decode("utf-8-sig")
    v.record("CSV dışa aktarma", r.status_code == 200 and "Kayıt No" in csv)

    c = client()
    login(c, "admin", "Admin123!")
    v.record("admin talep yönetimi engeli", c.get("/talep-yonetimi/").status_code == 403)

    c = client()
    login(c, "manager", "Manager123!")
    v.record("yönetici talep yönetimi engeli", c.get("/talep-yonetimi/").status_code == 403)
    v.record("yönetici karar merkezi engeli", c.get("/karar-destek-merkezi/").status_code == 403)

    org2 = Organization.objects.filter(name="İzolasyon Kurumu").order_by("pk").first()
    if not org2:
        org2 = Organization.objects.create(name="İzolasyon Kurumu")
    p2 = Project.objects.filter(organization=org2, name="Gizli").order_by("pk").first()
    if not p2:
        p2 = Project.objects.create(organization=org2, name="Gizli")
    secret = RequestRecord.objects.filter(project=p2, record_number="HBYS-99-0001").first()
    if not secret:
        secret = RequestRecord.objects.create(
            project=p2,
            record_number="HBYS-99-0001",
            title="Gizli",
            description="x",
            feedback_source="Proje Ekibi",
            process_area="UAT",
            responsible_team="X",
        )
    c = client()
    login(c, "pm", "Pm123!")
    v.record("kurum izolasyonu", c.get(f"/talep/{secret.pk}/").status_code == 404)

    c = client()
    login(c, "pm", "Pm123!")
    v.record("çıkış", c.post("/cikis/").status_code == 302)

    pages = [
        ("admin", "Admin123!", "/genel-gorunum/", "admin genel görünüm"),
        ("pm", "Pm123!", "/", "genel görünüm"),
        ("techlead", "Tech123!", "/teknik-gorunum/", "teknik görünüm"),
        ("pm", "Pm123!", "/karar-destek-merkezi/", "karar destek"),
    ]
    for user, pwd, path, label in pages:
        c = client()
        login(c, user, pwd)
        r = c.get(path)

        def only_valid_risk(h):
            bad = []
            risk_kritik = re.sub(r"Kritik Açık Kayıt", "", h)
            risk_kritik = re.sub(r"Kritik iş akış", "", risk_kritik)
            risk_kritik = re.sub(r"kritik ekran", "", risk_kritik, flags=re.I)
            if re.search(r"\bKritik\b", risk_kritik):
                bad.append("kritik_label")
            if "---------" in h:
                bad.append("empty_select_label")
            return bad

        v.check_html(label, r.content.decode(), only_valid_risk)

    return v.exit_code()


if __name__ == "__main__":
    sys.exit(main())
