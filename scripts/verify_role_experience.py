"""Rol bazlı deneyim doğrulaması — Django test istemcisi ile çalışır."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local")

import django

django.setup()

from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from projects.models import RequestRecord

HOST = "127.0.0.1"
ACCOUNTS = [
    ("admin", "Admin123!", "admin_landing", reverse("accounts:user_management"), ["Kullanıcı Yönetimi", "Kurum ve Proje Yönetimi"]),
    ("pm", "Pm123!", "pm_landing", reverse("projects:dashboard"), ["Genel Görünüm", "Talep Yönetimi"]),
    ("techlead", "Tech123!", "techlead_landing", reverse("projects:technical_view"), ["Teknik Operasyon Özeti", "Teknik İş Listesi"]),
    ("manager", "Manager123!", "manager_landing", reverse("projects:manager_panel"), ["Yönetici Paneli", "Proje İletişim Merkezi"]),
]
BLOCKED = [
    ("admin", "Admin123!", reverse("projects:request_management"), 403),
    ("manager", "Manager123!", reverse("projects:request_management"), 403),
    ("techlead", "Tech123!", reverse("accounts:user_management"), 403),
]
OUTPUT_DIR = ROOT / "verification_screenshots" / "role_refactor"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def client():
    return Client(HTTP_HOST=HOST)


def login(c, username, password):
    return c.post(reverse("accounts:login"), {"username": username, "password": password})


def main():
    call_command("seed_demo_data")
    results = []
    for username, password, slug, landing_url, nav_labels in ACCOUNTS:
        c = client()
        resp = login(c, username, password)
        ok_login = resp.status_code == 302 and landing_url in resp.url
        page = c.get(landing_url)
        html = page.content.decode("utf-8", errors="replace")
        (OUTPUT_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
        nav_ok = all(label in html for label in nav_labels)
        results.append((username, ok_login, page.status_code == 200, nav_ok))

    for username, password, url, expected in BLOCKED:
        c = client()
        login(c, username, password)
        resp = c.get(url)
        results.append((f"{username} blocked", resp.status_code == expected, True, True))

    c = client()
    login(c, "pm", "Pm123!")
    create = c.post(
        reverse("projects:request_management"),
        {
            "form_type": "request",
            "title": "Rol Doğrulama Talebi",
            "description": "Test",
            "feedback_source": "Proje Ekibi",
            "process_area": "UAT",
            "priority": "Orta",
            "status": "Açık",
            "responsible_team": "Teknik Ekip",
            "due_date": "2026-08-15",
            "go_live_impact": "Orta",
            "affects_patient_or_user_safety": "Düşük",
            "operational_impact": "Orta",
        },
    )
    results.append(("pm create request", create.status_code == 302, RequestRecord.objects.filter(title="Rol Doğrulama Talebi").exists(), True))

    print("Rol Doğrulama Sonuçları")
    print("=" * 60)
    passed = 0
    for name, *checks in results:
        ok = all(checks)
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
        if ok:
            passed += 1
    print(f"\n{passed}/{len(results)} kontrol başarılı")
    print(f"HTML çıktıları: {OUTPUT_DIR}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
