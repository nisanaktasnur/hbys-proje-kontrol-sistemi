"""Paylaşılan Django ayarları — ortam profilleri tarafından genişletilir."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SEED_DEMO_DATA=(bool, False),
    LOGIN_RATE_LIMIT=(int, 5),
    LOGIN_RATE_WINDOW=(int, 300),
)

environ.Env.read_env(BASE_DIR / ".env")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "core",
    "accounts",
    "projects",
    "assistant",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "core.middleware.OrganizationMiddleware",
    "core.middleware.LoginRateLimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.global_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "projects:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

LOGIN_RATE_LIMIT = env("LOGIN_RATE_LIMIT")
LOGIN_RATE_WINDOW = env("LOGIN_RATE_WINDOW")

OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_API_BASE = env("OPENAI_API_BASE", default="https://api.openai.com/v1")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini")

RISK_ENGINE = {
    "WEIGHTS": {
        "priority": 3.0,
        "go_live_impact": 3.5,
        "patient_safety": 3.5,
        "operational_impact": 2.5,
        "workaround_missing": 2.0,
        "overdue": 2.5,
        "record_age": 1.5,
        "open_status": 1.5,
        "process_density": 1.8,
    },
    "THRESHOLDS": {
        "high": 65,
        "medium": 38,
    },
    "PRIORITY_VALUES": {
        "Düşük": 1,
        "Orta": 2,
        "Yüksek": 3,
        "Acil": 4,
    },
    "IMPACT_VALUES": {
        "Düşük": 1,
        "Orta": 2,
        "Yüksek": 3,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "hbys-cache",
    }
}
