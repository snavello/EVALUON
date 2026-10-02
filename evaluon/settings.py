"""Configuración de EVALUON (plan 001).

Todo lo que cambia entre equipos o es secreto se lee de variables de entorno; los valores
por defecto y su explicación están en .env.example. Las aplicaciones propias (accounts,
audit, norms, queries) las agregan las tareas de la etapa 1.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_required(name):
    value = os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(
            f"Falta la variable de entorno {name} (copiar .env.example a .env y completarla)."
        )
    return value


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    if value.lower() in ("1", "true", "yes", "si", "sí"):
        return True
    if value.lower() in ("0", "false", "no"):
        return False
    raise ImproperlyConfigured(f"La variable de entorno {name} tiene que ser true o false.")


def env_list(name, default):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = env_required("DJANGO_SECRET_KEY")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise va inmediatamente después de SecurityMiddleware (su documentación).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "evaluon.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "evaluon" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "evaluon.wsgi.application"

# Postgres del servicio `db`, por psycopg 3. Las pruebas usan una base aparte que
# pytest-django crea y borra (test_<nombre de la base>).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "evaluon"),
        "USER": os.environ.get("POSTGRES_USER", "evaluon"),
        "PASSWORD": env_required("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# Archivos estáticos: los sirve la propia aplicación con WhiteNoise (ADR-0005), desde
# lo que reúne collectstatic al construir la imagen. Nada externo.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "evaluon" / "static"]
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
