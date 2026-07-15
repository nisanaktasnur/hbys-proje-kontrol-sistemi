"""Otomatik test ayarları — SQLite, hızlı parola hash."""

from .settings_base import *  # noqa: F403

DEBUG = True
SECRET_KEY = (
    "test-only-hbys-proje-kontrol-sistemi-secret-key-not-for-production-use-2026"
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
SEED_DEMO_DATA = True

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
