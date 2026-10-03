"""Configuración de EVALUON (plan 001).

Todo lo que cambia entre equipos o es secreto se lee de variables de entorno; los valores
por defecto y su explicación están en .env.example. Las aplicaciones propias (accounts,
audit, norms, queries) las agregan las tareas de la etapa 1.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

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

# Sin panel de administración ni grupos (ADR-0005). `auth` y `contenttypes` dan el
# ingreso, las claves y el comando `changepassword`; el usuario es el propio de accounts.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "evaluon.accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise va inmediatamente después de SecurityMiddleware (su documentación).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Toda página exige sesión salvo la de ingreso (REQ-016).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
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
                "django.template.context_processors.csrf",
                "django.contrib.auth.context_processors.auth",
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

# Usuarios, claves y sesiones (REQ-016; ADR-0005, "Acceso"; plan 001, "Decisiones tomadas").
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
# La raíz es la pantalla de consulta (T-016).
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "accounts:login"

# Argon2id primero, con los parámetros de Django (102.400 KiB, 2 iteraciones,
# 8 hilos), por encima del mínimo de OWASP. Los demás quedan solo para leer claves
# guardadas con otro algoritmo, que Django vuelve a guardar con Argon2id al ingresar.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# 15 caracteres como mínimo, sin reglas de composición (OWASP).
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 15},
    },
]

# Sesiones en la base (valor por defecto de Django). Vencen 8 horas después del ingreso
# (no se renuevan con el uso) y al cerrar el navegador. La cookie lleva solo el
# identificador, es HttpOnly (por defecto) y SameSite estricto. La cookie segura
# (HTTPS) es de la feature 007, acceso por red.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

# Política de contenido: solo recursos del propio servidor (ADR-0005, "Sin conexión").
SECURE_CSP = {
    "default-src": [CSP.SELF],
}

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# Archivos estáticos: los sirve la propia aplicación con WhiteNoise (ADR-0005), desde
# lo que reúne collectstatic al construir la imagen. Nada externo.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "evaluon" / "static"]
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
