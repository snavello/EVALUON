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
    "evaluon.assessment",
    "evaluon.audit",
    "evaluon.journey",
    "evaluon.norms",
    "evaluon.offers",
    "evaluon.portal",
    "evaluon.queries",
    "evaluon.tenders",
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
                "evaluon.journey.context.shell",
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

# 8 caracteres como mínimo, sin reglas de composición (decisión del responsable del
# 2026-10-03; ADR-0005 proponía 15).
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
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

# Modelo propio del motor de lotes, `generation_batch` (plan 004, ADR-0041 y ADR-0042): por
# omisión, el mismo que `generation`. Las evaluaciones, las propuestas de la 003 y las
# fichas de la 008 registran estos valores, no los de `generation` (P6). El proyector de
# imagen es el de la lectura con visión.
GENERATION_BATCH_MODEL = env_str("GENERATION_BATCH_MODEL_ALIAS", GENERATION_MODEL)
GENERATION_BATCH_MODEL_FILE = env_str("GENERATION_BATCH_MODEL_FILE", GENERATION_MODEL_FILE)
GENERATION_BATCH_MODEL_SHA256 = env_str(
    "GENERATION_BATCH_MODEL_SHA256", GENERATION_MODEL_SHA256)
GENERATION_BATCH_MMPROJ_FILE = env_str(
    "GENERATION_BATCH_MMPROJ_FILE", "mmproj-gemma-4-12b-it-qat-q4_0.gguf")
GENERATION_BATCH_MMPROJ_SHA256 = env_str(
    "GENERATION_BATCH_MMPROJ_SHA256",
    "cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7",
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
# sigmoide). Provisorio, fijado en T-062 el 2026-10-03 con la regla del hueco del
# ADR-0014, punto 2: punto medio, en la escala anterior a la sigmoide, entre la pregunta
# ajena a la normativa más alta (A, EV-025, 0,1195) y la pregunta con respuesta más baja
# (B, EV-020, 0,3680) del lote de ajuste, redondeado hacia abajo; margen 0,728 (mínimo
# 0,5). Sale de la recalificación
# `evals/corridas/2026-10-03T162823_1728ccc_gemma-4-12b-it-qat-q4_0_recalificada` de la
# corrida de T-045. Reemplaza al 0,368 de T-045. Se recalibra cuando cambie el lote de
# ajuste, el corpus, el reranker o el armado de pasajes.
RERANK_THRESHOLD = 0.219
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

# --- Matriz de cumplimiento (plan 003, "Parámetros"; ADR-0018 y ADR-0019) -------------
# Valores iniciales. Se copian en cada propuesta de matriz (`tenders_matrix_run`);
# cambiarlos exige volver a medir (P7).

# Tokens de entrada de los tramos de un lote de extracción.
MATRIX_BATCH_INPUT_TOKENS = 1500
# Máximo de tokens de salida de cada pedido de la matriz.
MATRIX_MAX_OUTPUT_TOKENS = 4096
# Largo de un tramo, en caracteres, a partir del cual se parte en límites de oración.
SEGMENT_MAX_CHARS = 4000
# Requisitos por pedido de consecuencias.
MATRIX_CONSEQUENCES_PER_REQUEST = 25
# Citas candidatas que el reranker suma para cada tramo de una circular o respuesta.
MATRIX_CIRCULAR_CANDIDATES = 8
# Versión de cada instrucción de la matriz: archivo `evaluon/tenders/prompts/<versión>.md`.
MATRIX_PROMPT_VERSIONS = {
    "extraccion": "matriz-extraccion-v3",
    "completitud": "matriz-completitud-v3",
    "consecuencias": "matriz-consecuencias-v1",
    "circulares": "matriz-circulares-v2",
    "circulares_cambios": "matriz-circulares-v5",
    "unificacion": "matriz-unificacion-v1",
    "filtro": "matriz-filtro-v2",
    "respaldo": "matriz-respaldo-v1",
}

# Proceso único de la propuesta (REQ-030 enmendado): el más completo, sin niveles. Se
# registra en cada propuesta y en su versión de matriz.
MATRIX_PROCESS = "completo"

# Extracción de cambios de circulares con el modelo (ADR-0023, REQ-031): enciende o
# apaga la entrega 2 y fija cuántas veces se repite cada unidad (1; 3 en la medición de
# estabilidad).
CIRCULAR_EXTRACTION_ENABLED = True
CIRCULAR_EXTRACTION_REPEATS = 1

# --- Filtro de sobrantes, unificación y descartadas (ADR-0021, REQ-033) ----------------
FILTER_ENABLED = True
# Filas formales o económicas por pedido del filtro.
FILTER_BATCH_ROWS = 15
# Motivos de descarte: lista cerrada (los del ADR-0019 más dos del ADR-0021).
FILTER_MOTIVES = [
    "titulo", "dato_procedimiento", "norma_aplicable", "obligacion_organismo",
    "ejecucion_contrato", "formulario", "indice_caratula", "consecuencia_sancion",
    "derecho_posterior",
]
# Similitud de palabras desde la que dos filas se unifican como repetidas.
DEDUP_MIN_SIMILARITY = 0.9
# Muestra de descartadas que se revisa en la medición: una de cada tres, mínimo 20.
MATRIX_SAMPLE_DISCARDED = {"every": 3, "minimum": 20}
# Tope de sobrantes sobre las filas firmes (REQ-024).
MATRIX_SOBRANTES_LIMIT = 0.20

# --- Sugerencias y respaldo normativo (ADR-0022, REQ-035 y REQ-036) --------------------
SUGGESTIONS_ENABLED = True
DOUBT_MOTIVES = [
    "no_coinciden", "duda", "descarte_sin_sustento", "opinion_incompleta",
]
NORM_SUPPORT_ENABLED = True
# Valor inicial: el umbral del reranker de la 001; se revisa con lo medido (T-106).
NORM_SUPPORT_MIN_SCORE = RERANK_THRESHOLD
# Unidades de norma que se le muestran al modelo por sugerencia.
NORM_SUPPORT_MAX_UNITS = 4
# Largo máximo del fragmento del pliego en la pregunta, en caracteres.
NORM_SUPPORT_QUERY_MAX_CHARS = 800

# Motor de generación de los pedidos del `worker` (ADR-0018). Apuntarlo a
# `GENERATION_URL` vuelve a un solo motor sin cambiar código.
GENERATION_BATCH_URL = env_str("GENERATION_BATCH_URL", "http://generation_batch:8080")
# Contexto del servidor `generation_batch` (--ctx-size en docker-compose.yml). Es propio del
# motor de lotes y mayor que el de `generation` (16.384) para la lectura completa de la
# evaluación (plan 004, ADR-0037). Se registra con cada propuesta y evaluación (P6).
GENERATION_BATCH_CONTEXT_TOKENS = int(env_str("GENERATION_BATCH_CTX_SIZE", "32768"))
# Espera máxima de cada pedido del `worker` al modelo.
GENERATION_BATCH_TIMEOUT_SECONDS = 180
# Segundos entre consultas a la cola de pedidos cuando está vacía.
WORKER_POLL_SECONDS = 5

# --- Importación desde el Portal de Compras (plan 012, "Parámetros"; ADR-0031) -----------
# Hosts a los que puede conectar el servicio `portal_worker` (solo HTTPS, puerto 443). El
# valor por omisión es el del Portal; la lista se repite en docker-compose.yml.
PORTAL_ALLOWED_HOSTS = env_list("PORTAL_ALLOWED_HOSTS", "afipcompras.afip.gob.ar")
# Espera máxima de cada solicitud, en segundos.
PORTAL_TIMEOUT_SECONDS = int(env_str("PORTAL_TIMEOUT_SECONDS", "30"))
# Tamaño máximo de cada respuesta, en bytes (50 MiB).
PORTAL_MAX_BYTES = int(env_str("PORTAL_MAX_BYTES", str(50 * 1024 * 1024)))
# Pausa entre solicitudes al Portal, en segundos.
PORTAL_PAUSE_SECONDS = float(env_str("PORTAL_PAUSE_SECONDS", "2"))
# Hora local (Buenos Aires) desde la que se encola la revisión diaria (ADR-0033).
PORTAL_REVIEW_HOUR = int(env_str("PORTAL_REVIEW_HOUR", "7"))
# Identificación que el cliente declara en cada solicitud.
PORTAL_USER_AGENT = env_str("PORTAL_USER_AGENT", "EVALUON/1.0 (lectura de procesos publicos)")

# --- Ofertas y ficha por oferta (plan 008, "Parámetros"; ADR-0026 y ADR-0027) ----------
# Valores iniciales. Se copian en cada ficha (`offers_sheet.parameters`); cambiarlos exige
# volver a medir (P7).

# Largo máximo de un pasaje de una oferta, en caracteres; un bloque más largo se parte en
# límite de oración. Un bloque de menos de OFFERS_PASSAGE_MIN_CHARS se une al siguiente de
# su página.
OFFERS_PASSAGE_MAX_CHARS = 1200
OFFERS_PASSAGE_MIN_CHARS = 200
# Pasajes por pedido de vectores al servicio de embeddings.
OFFERS_EMBED_BATCH = 16
# Candidatos por significado y por palabras, y los que pasan al modelo tras el reranker.
OFFERS_CANDIDATES_EMBEDDINGS = 20
OFFERS_CANDIDATES_WORDS = 20
OFFERS_CANDIDATES_TO_MODEL = 8
# Las filas por renglón conservan más candidatos (T-135): las tablas de la oferta parten el
# renglón en varios pasajes.
OFFERS_ITEM_CANDIDATES_TO_MODEL = 12
# Puntaje mínimo del reranker (entre 0 y 1) que un pasaje tiene que alcanzar para pasar al
# modelo en las filas que no son de renglón (T-136): por debajo, la fila queda "no se
# encontró" sin preguntarle al modelo. Las filas por renglón no lo usan. Calibrado con el
# reranker real (T-146) sobre textos inventados con la forma de lo que responden las ofertas
# (pólizas de caución, notas, formularios del Portal, declaraciones juradas, constancias): el
# puntaje de un pasaje es el mayor entre el de la cita del pliego y el de su reescritura como la
# diría una oferta. Los que responden puntuaron 0,47 o más; los del mismo tema que no responden,
# 0,33 o menos, salvo uno que ningún corte separa (0,58). 0,35 queda en el hueco. Se recalibra
# con la medición.
OFFERS_MIN_RERANK_SCORE = 0.35
# Fila por renglón (T-135): pasajes vecinos de la misma página (zona de tabla) que se suman a
# los candidatos de los `OFFERS_ITEM_NEIGHBOR_SEEDS` mejores, hasta `OFFERS_ITEM_NEIGHBORS`.
OFFERS_ITEM_NEIGHBOR_SEEDS = 3
OFFERS_ITEM_NEIGHBORS = 4
# Máximo de tokens de salida de cada pedido de la ficha y espera máxima de cada pedido.
OFFERS_MAX_OUTPUT_TOKENS = 400
OFFERS_REQUEST_TIMEOUT_SECONDS = GENERATION_BATCH_TIMEOUT_SECONDS
# Largo máximo de la consulta (cita del requisito) enviada a la recuperación.
OFFERS_QUERY_MAX_CHARS = 800
# Versión de cada instrucción: archivo `evaluon/offers/prompts/<versión>.md`.
OFFERS_PROMPT_VERSIONS = {
    "ficha": "ficha-v2",
    "ficha_renglon": "ficha-renglon-v4",
    # Reescritura del requisito como lo diría una oferta, para buscar (T-146).
    "reescritura": "reescritura-v1",
}

# --- Evaluación asistida de ofertas (plan 004, "Parámetros"; ADR-0037 a ADR-0040) ---------
# Texto de oferta por pedido al modelo, en tokens: instrucciones, requisito, fundamentos,
# salida y margen de plantilla (unos 6.000) caben en `GENERATION_BATCH_CONTEXT_TOKENS`.
ASSESSMENT_GROUP_TOKENS = 20000
# Máximo de grupos de documentos que se leen por oferta; más allá, el par queda con
# lectura incompleta.
ASSESSMENT_MAX_GROUPS = 4
# Máximo de tokens de salida de cada pedido de lectura y de contraste.
ASSESSMENT_MAX_OUTPUT_TOKENS = 1400
# Citas de la oferta por resultado y largo máximo de cada una, en caracteres.
ASSESSMENT_MAX_CITATIONS = 4
ASSESSMENT_CITATION_MAX_CHARS = 1000
# Contraste por cláusula (T-164): cláusulas por pedido, caracteres por pedido, tokens de salida
# y tokens del documento de la oferta que se muestra junto con la cita.
ASSESSMENT_CLAUSES_PER_REQUEST = 6
ASSESSMENT_CLAUSES_REQUEST_CHARS = 3500
ASSESSMENT_CLAUSES_MAX_OUTPUT_TOKENS = 2500
ASSESSMENT_CLAUSES_DOCUMENT_TOKENS = 6000
# Espera máxima de cada pedido al modelo.
ASSESSMENT_REQUEST_TIMEOUT_SECONDS = 300
# Unidades de norma que respaldan un requisito y respuestas de la Comisión que se le dan al
# modelo por par.
ASSESSMENT_NORM_UNITS_MAX = 4
ASSESSMENT_ANSWERS_MAX = 20
# Filas técnicas (REQ-061, T-167): el contraste por cláusula alimenta la opinión informativa
# del sistema; apagarlo la deja solo con la lectura por grupos (el resultado no cambia).
ASSESSMENT_TECHNICAL_OPINION = True
# Versión de las reglas que deciden sin el modelo (externos, técnico, ilegible, Portal); se
# copia al registro de cada evaluación (ADR-0043; T-165). Cambia cuando cambia una regla.
ASSESSMENT_RULES_VERSION = "reglas-v8"
# Versión de cada instrucción: archivo `evaluon/assessment/prompts/<versión>.md` (T-150).
ASSESSMENT_PROMPT_VERSIONS = {
    "evaluacion": "evaluacion-v5",
    "contraste": "contraste-v2",
    "clausulas": "clausulas-v2",
}

# Lectura con visión de las páginas dudosas (T-160; ADR-0041). Páginas por oferta que se mandan
# al motor de lotes con su imagen (0 la apaga: la evaluación sigue con la lectura que haya);
# resolución a la que se dibuja la página y lado mayor máximo de la imagen, en puntos; tokens
# por imagen con que se estima (lo fija el motor: se registra); máximo de tokens de la
# transcripción de una página; proporción de `[ilegible]` por encima de la cual la página no
# cuenta como leída; versión de la instrucción (`evaluon/assessment/prompts/<versión>.md`).
ASSESSMENT_VISION_MAX_PAGES = 40
ASSESSMENT_VISION_DPI = 150
ASSESSMENT_VISION_MAX_SIDE = 1800
ASSESSMENT_VISION_IMAGE_TOKENS = 280
ASSESSMENT_VISION_MAX_OUTPUT_TOKENS = 3000
ASSESSMENT_VISION_MAX_ILLEGIBLE_SHARE = 0.30
ASSESSMENT_VISION_PROMPT_VERSION = "vision-v3"
# T-177 (REQ-064): cómo se le pide al modelo. Salida en texto plano que termina con un
# marcador de fin (sin él, la salida se descarta: no se aceptan transcripciones parciales);
# penalización de repetición del motor; orientación (confianza mínima de OSD de Tesseract para
# fiarse de él y lado mayor de la copia reducida con que se detecta); franjas horizontales
# solapadas a 300 puntos por pulgada para páginas apaisadas o de lectura dudosa (cantidad,
# solape como proporción del alto de la franja y lado mayor de cada franja).
ASSESSMENT_VISION_END_MARKER = "<<FIN>>"
ASSESSMENT_VISION_REPEAT_PENALTY = float(env_str("ASSESSMENT_VISION_REPEAT_PENALTY", "1.15"))
ASSESSMENT_VISION_OSD_MIN_CONFIDENCE = 5.0
ASSESSMENT_VISION_ORIENTATION_MAX_SIDE = 1400
ASSESSMENT_VISION_TILE_DPI = 300
ASSESSMENT_VISION_TILES = 2
ASSESSMENT_VISION_TILE_OVERLAP = 0.05
ASSESSMENT_VISION_TILE_MAX_SIDE = 1600
