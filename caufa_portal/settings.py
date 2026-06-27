from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-change-me-for-production"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core_system",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "caufa_portal.urls"
# Inside caufa_portal/settings.py

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
            ],
            # ADD THIS BLOCK BELOW TO GLOBALLY ENABLE LOAD STATIC
            "builtins": [
                "django.templatetags.static",
            ],
        },
    },
]

WSGI_APPLICATION = "caufa_portal.wsgi.application"
ASGI_APPLICATION = "caufa_portal.asgi.application"

# Replace your old DATABASES dictionary with this:
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "capstone_project_db",
        "USER": "root",
        "PASSWORD": "new_password",
        "HOST": "127.0.0.1",
        "PORT": "3307",
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media upload configuration (receipts / supporting proofs)
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication Redirect routing boundaries
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# -------------------------
# Gmail SMTP (for notifications)
# -------------------------
# Add these to your environment (recommended via .env + python-dotenv) or set them directly.
# Expected values for Gmail SMTP:
# - GMAIL_SMTP_HOST: smtp.gmail.com
# - GMAIL_SMTP_PORT: 587
# - GMAIL_SMTP_USER: your_gmail_address
# - GMAIL_SMTP_PASSWORD: your Gmail App Password
# - GMAIL_SMTP_USE_TLS: true (optional; default True)
#
# If you already set Django's EMAIL_* settings, we fall back to them.

import os as _os

# Host/port
GMAIL_SMTP_HOST = _os.getenv("GMAIL_SMTP_HOST", _os.getenv("EMAIL_HOST", "smtp.gmail.com"))
GMAIL_SMTP_PORT = int(_os.getenv("GMAIL_SMTP_PORT", _os.getenv("EMAIL_PORT", "587")))

# Credentials
GMAIL_SMTP_USER = _os.getenv("GMAIL_SMTP_USER", _os.getenv("EMAIL_HOST_USER", ""))
GMAIL_SMTP_PASSWORD = _os.getenv("GMAIL_SMTP_PASSWORD", _os.getenv("EMAIL_HOST_PASSWORD", ""))

# TLS
GMAIL_SMTP_USE_TLS = _os.getenv(
    "GMAIL_SMTP_USE_TLS",
    _os.getenv("EMAIL_USE_TLS", "true"),
).lower() in {"1", "true", "yes"}


