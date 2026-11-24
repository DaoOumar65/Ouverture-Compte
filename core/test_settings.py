"""Isolated SQLite settings for running the project test suite locally."""

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Unit tests use Django's local test identities; AD integration is tested separately.
AUTH_MODE = "LOCAL"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
