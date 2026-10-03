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


def env_str(name, default):
    """Valor de la variable de entorno, o `default` si falta o está vacía."""
    return os.environ.get(name) or default


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
    "evaluon.audit",
    "evaluon.norms",
    "evaluon.queries",
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

# --- Servicios de IA (T-011; plan 001, "Servicios"; ADR-0002 y ADR-0003) --------------
# Los tres son `llama-server` en la red interna (docker-compose.yml), puerto 8080. Los
# clientes de evaluon/ai/ leen estos valores en cada llamada. Los modelos se registran
# con su nombre, su archivo y su huella (P6); las huellas son las de
# scripts/models.sha256, que verifica scripts/fetch_models.sh. Las variables de entorno
# de modelos son las mismas que usa docker-compose.yml para arrancar cada servidor, y
# docker-compose.yml se las pasa también a `app` y `migrate` (T-054): servidor y
# aplicación leen una sola fuente. Los valores por defecto de aquí son los del compose
# (tests/test_compose_env.py lo comprueba).

GENERATION_URL = env_str("GENERATION_URL", "http://generation:8080")
EMBEDDINGS_URL = env_str("EMBEDDINGS_URL", "http://embeddings:8080")
RERANKER_URL = env_str("RERANKER_URL", "http://reranker:8080")

# Espera máxima de cada pedido; agotada, la consulta es una falla técnica con motivo
# `timeout` (plan 001, "Abstención").
AI_TIMEOUT_SECONDS = 60

# Compilación de llama.cpp de los tres servicios; tiene que coincidir con la etiqueta de
# la imagen en docker-compose.yml (entorno.md, T-002, sección 1); tests/test_compose_env.py
# compara las dos.
GENERATION_ENGINE_BUILD = "b11347"

GENERATION_MODEL = env_str("GENERATION_MODEL_ALIAS", "gemma-4-12b-it-qat-q4_0")
GENERATION_MODEL_FILE = env_str("GENERATION_MODEL_FILE", "gemma-4-12b-it-qat-q4_0.gguf")
GENERATION_MODEL_SHA256 = env_str(
    "GENERATION_MODEL_SHA256",
    "93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b",
)

EMBEDDINGS_MODEL = env_str("EMBEDDINGS_MODEL_ALIAS", "bge-m3")
EMBEDDINGS_MODEL_FILE = env_str("EMBEDDINGS_MODEL_FILE", "bge-m3-FP16.gguf")
EMBEDDINGS_MODEL_SHA256 = env_str(
    "EMBEDDINGS_MODEL_SHA256",
    "daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c",
)
# Dimensiones del vector de `bge-m3`. Única definición (T-054): la toman la columna
# `embedding` de `norms_passage` (norms.models.EMBEDDING_DIMENSIONS) y los dobles de
# prueba. Cambiarla cambia el esquema y exige una migración.
EMBEDDINGS_DIMENSIONS = 1024

RERANKER_MODEL = env_str("RERANKER_MODEL_ALIAS", "bge-reranker-v2-m3")
RERANKER_MODEL_FILE = env_str("RERANKER_MODEL_FILE", "bge-reranker-v2-m3-FP16.gguf")
RERANKER_MODEL_SHA256 = env_str(
    "RERANKER_MODEL_SHA256",
    "5df93be121c09c43432102ad2b9569d369ccb85c209ca7583e8ccd28f0e41b88",
)

# --- Parámetros de generación (plan 001, "Generación" y "Conteo de tokens") ----------
# Contexto del servidor `generation` (--ctx-size en docker-compose.yml).
GENERATION_CONTEXT_TOKENS = int(env_str("GENERATION_CTX_SIZE", "16384"))
GENERATION_TEMPERATURE = 0
# Semilla fija; 42 es la usada en las pruebas de la etapa 0 (entorno.md, T-002).
GENERATION_SEED = 42
# Pensamiento apagado. El servidor ya arranca con --reasoning off; además cada pedido lo
# pide a la plantilla de conversación. `enable_thinking` es la variable de la plantilla
# de Gemma 4: es propia del modelo y cambia con él (ADR-0002, "Consecuencias").
GENERATION_THINKING = False
GENERATION_CHAT_TEMPLATE_KWARGS = {"enable_thinking": GENERATION_THINKING}
# Máximo de tokens de salida: el del pedido largo con que se midió el tiempo en la etapa
# 0 (entorno.md, T-002, sección 6). Se descuenta del espacio del contexto.
GENERATION_MAX_OUTPUT_TOKENS = 800
# Tope de afirmaciones del esquema de salida.
GENERATION_MAX_STATEMENTS = 6

# --- Parámetros de búsqueda (plan 001, "Recuperación", "Reordenamiento" y "Conteo de
# tokens"). Valores iniciales; se copian en el registro de cada consulta y cambiarlos
# exige correr las evals (P7).
RETRIEVAL_CANDIDATES_PER_PATH = 30
# Umbral de abstención sobre el puntaje del reranker, entre 0 y 1 (después de la
# sigmoide). Provisorio hasta la calibración de T-045: 0,5 es el punto medio de la
# sigmoide (valor sin escala 0).
RERANK_THRESHOLD = 0.5
SELECTION_UNITS_PER_CATEGORY = 3
SELECTION_CONSIDERANDOS = 2
# Largo máximo de un pasaje (encabezado más texto), contado con el cliente de embeddings.
PASSAGE_MAX_TOKENS = 800
# Solape entre pasajes seguidos de una misma unidad: tramos completos del pasaje anterior
# que suman hasta esto, contados con el cliente de embeddings. Valor inicial provisorio,
# se calibra con las evals (T-045).
PASSAGE_OVERLAP_TOKENS = 100
# Una unidad más larga que esto se le muestra al modelo solo por sus pasajes que
# superaron el umbral; contado con el cliente de generación.
UNIT_BY_PASSAGES_FROM_TOKENS = 1500
# Margen por lo que agrega la plantilla de conversación, que /tokenize no ve (medido: 18).
PROMPT_TEMPLATE_MARGIN_TOKENS = 512
