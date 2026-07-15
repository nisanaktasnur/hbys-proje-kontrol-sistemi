from django.utils import timezone

from .settings_base import *  # noqa: F403

DEBUG = True
SECRET_KEY = (
    "local-dev-only-hbys-proje-kontrol-sistemi-secret-key-not-for-production-use-2026"
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
SEED_DEMO_DATA = True

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
