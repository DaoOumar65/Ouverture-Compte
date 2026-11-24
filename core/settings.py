"""Settings pour le projet BCB Recueil Express."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load a local .env when python-dotenv is installed; production should inject secrets.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}
if not DEBUG and not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be configured when DEBUG is disabled."
    )
if not DEBUG and not os.environ.get("DB_PASSWORD"):
    raise ImproperlyConfigured(
        "DB_PASSWORD must be configured when DEBUG is disabled."
    )
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured when DEBUG is disabled.")
    SECRET_KEY = "development-only-not-for-production"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "recueil",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "recueil.middleware.ActiveDirectorySessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "recueil.context_processors.access_approval_notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# PostgreSQL database connection. Set DB_PASSWORD in the local environment.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "ouverture"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "admin"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5433"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31_536_000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").is_dir() else []
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AD is the only authentication provider by default. LOCAL must be selected
# explicitly for isolated development environments.
AUTH_MODE = os.environ.get("AUTH_MODE", "AD").strip().upper()
if AUTH_MODE not in {"AD", "LOCAL"}:
    raise ImproperlyConfigured("AUTH_MODE must be AD or LOCAL.")
if AUTH_MODE == "LOCAL" and not DEBUG:
    raise ImproperlyConfigured("Local authentication is only allowed while DJANGO_DEBUG is enabled.")

AD_MODE = os.environ.get("AD_MODE", "ldap").strip().lower()
if AUTH_MODE == "AD" and AD_MODE != "ldap":
    raise ImproperlyConfigured("Only AD_MODE=ldap is supported by this Django backend.")

AD_HOST = os.environ.get("AD_HOST", "192.168.10.15").strip()
AD_TLS = os.environ.get("AD_TLS", "ldaps").strip().lower()
if AD_TLS in {"aucun", "none"}:
    AD_TLS = "none"
if AUTH_MODE == "AD" and AD_TLS not in {"ldaps", "starttls", "none"}:
    raise ImproperlyConfigured("AD_TLS must be ldaps, starttls, or aucun.")
AD_PORT = int(os.environ.get("AD_PORT", "636" if AD_TLS == "ldaps" else "389"))
AD_DOMAIN_NETBIOS = os.environ.get("AD_DOMAIN_NETBIOS", "BCB").strip()
AD_UPN_SUFFIXES = tuple(
    value.strip()
    for value in os.environ.get("AD_UPN_SUFFIXES", "bcb.bf,bcb.lan").split(",")
    if value.strip()
)
AD_BIND_DN = os.environ.get("AD_BIND_DN", "").strip()
AD_BIND_PASSWORD = os.environ.get("AD_BIND_PASSWORD", "")
AD_BASE_DN = os.environ.get("AD_BASE_DN", "DC=bcb,DC=lan").strip()
AD_CA_CERT = os.environ.get("AD_CA_CERT", "").strip()
AD_TIMEOUT_MS = int(os.environ.get("AD_TIMEOUT_MS", "5000"))

if AUTH_MODE == "AD":
    AUTHENTICATION_BACKENDS = ["recueil.auth_backends.ActiveDirectoryBackend"]
else:
    AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
