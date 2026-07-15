"""Üretim Django ayarları — PostgreSQL ve güvenlik doğrulamaları."""

from django.core.exceptions import ImproperlyConfigured

from .settings_base import *  # noqa: F403

DEBUG = env.bool("DEBUG", default=False)

INSECURE_SECRET_KEYS = {
    "",
    "gelistirme-icin-degistirin",
    "degistirin-guclu-bir-anahtar-kullanin",
    "django-insecure",
    "change-me",
}

WEAK_DB_PASSWORDS = {
    "hbys_sifre",
    "password",
    "postgres",
    "admin",
    "123456",
    "secret",
}


def _require_production_env(name):
    value = env(name, default=None)
    if not value:
        raise ImproperlyConfigured(f"Üretim ortamında {name} ortam değişkeni zorunludur.")
    return value


SECRET_KEY = env("SECRET_KEY", default="")
if not DEBUG:
    if SECRET_KEY in INSECURE_SECRET_KEYS or len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            "Üretim ortamında güvenli ve en az 50 karakterlik SECRET_KEY tanımlanmalıdır."
        )

if DEBUG:
    if not SECRET_KEY:
        SECRET_KEY = "gelistirme-icin-degistirin"
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="hbys_proje_kontrol"),
            "USER": env("POSTGRES_USER", default="hbys_user"),
            "PASSWORD": env("POSTGRES_PASSWORD", default=""),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    db_password = _require_production_env("POSTGRES_PASSWORD")
    if db_password in WEAK_DB_PASSWORDS:
        raise ImproperlyConfigured("Üretim ortamında zayıf PostgreSQL parolası kullanılamaz.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _require_production_env("POSTGRES_DB"),
            "USER": _require_production_env("POSTGRES_USER"),
            "PASSWORD": db_password,
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SEED_DEMO_DATA = env("SEED_DEMO_DATA")
