"""Doğrulama ekran görüntülerini üretir (sistem Chrome/Edge kullanır)."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local")

OUTPUT_DIR = ROOT / "verification_screenshots"
ARCHIVE_DIR = OUTPUT_DIR / "archive"
HOST = "127.0.0.1"
PORT = 8765
BASE = f"http://{HOST}:{PORT}"
VIEWPORT = "1440,900"

SHOTS = [
    ("verify-00-giris.png", "/giris/", None, None),
    ("verify-01-genel-gorunum.png", "/", "pm", "Pm123!"),
    ("verify-02-teknik-gorunum.png", "/teknik-gorunum/", "techlead", "Tech123!"),
    ("verify-03-risk-erken-uyari.png", "/risk-erken-uyari/", "techlead", "Tech123!"),
    ("verify-04-talep-yonetimi-uat.png", "/talep-yonetimi/?sekme=uat", "pm", "Pm123!"),
    ("verify-05-karar-destek.png", "/karar-destek-merkezi/", "pm", "Pm123!"),
    ("verify-06-yapay-zeka.png", "/yapay-zeka-asistani/", "pm", "Pm123!"),
    ("verify-07-yonetici-ozeti.png", "/yonetici-ozeti/", "manager", "Manager123!"),
    ("verify-08-admin-kullanici-yonetimi.png", "/kullanici-yonetimi/", "admin", "Admin123!"),
]

BROWSER_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def find_browser():
    for path in BROWSER_CANDIDATES:
        if path.exists():
            return path
    raise RuntimeError("Chrome veya Edge bulunamadı; ekran görüntüsü alınamadı.")


def archive_old():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("verify-*.png"):
        target = ARCHIVE_DIR / old.name
        if target.exists():
            target.unlink()
        old.rename(target)
    role_dir = OUTPUT_DIR / "role_refactor"
    if role_dir.exists():
        archive_role = ARCHIVE_DIR / "role_refactor_html"
        archive_role.mkdir(parents=True, exist_ok=True)
        for html in role_dir.glob("*.html"):
            target = archive_role / html.name
            if target.exists():
                target.unlink()
            html.rename(target)
        try:
            role_dir.rmdir()
        except OSError:
            pass


def inject_base_href(html):
    if re.search(r"<base\s", html, re.I):
        return html
    return re.sub(r"(<head[^>]*>)", rf'\1<base href="{BASE}/">', html, count=1, flags=re.I)


def screenshot_html(browser, html, output_path):
    tmp = OUTPUT_DIR / "_capture_tmp.html"
    tmp.write_text(html, encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={VIEWPORT}",
        f"--screenshot={output_path}",
        tmp.as_uri(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tmp.unlink(missing_ok=True)


def main():
    import django
    from django.test import Client
    from django.urls import reverse

    django.setup()
    archive_old()
    browser = find_browser()

    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings_local"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(3)
        client = Client(HTTP_HOST=HOST)

        for filename, path, user, password in SHOTS:
            c = Client(HTTP_HOST=HOST)
            if user:
                login_url = reverse("accounts:login")
                page = c.get(login_url)
                token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
                assert token, "CSRF token bulunamadı"
                c.post(
                    login_url,
                    {
                        "username": user,
                        "password": password,
                        "csrfmiddlewaretoken": token.group(1),
                    },
                )
            response = c.get(path)
            html = inject_base_href(response.content.decode("utf-8", errors="replace"))
            screenshot_html(browser, html, OUTPUT_DIR / filename)
            print(f"  saved {filename}")
    finally:
        server.terminate()
        server.wait(timeout=10)

    print(f"Saved {len(SHOTS)} screenshots to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
