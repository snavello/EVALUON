"""Una sola fuente para los servicios de IA y la aplicación (T-054).

Los servicios `generation`, `embeddings` y `reranker` arrancan con el alias, el archivo y
el contexto que `docker-compose.yml` arma con variables de `.env`. La aplicación registra
con cada consulta qué modelo respondió (P6, REQ-012) leyendo esas mismas variables desde
`settings.py`. Si `docker-compose.yml` no se las pasa a `app` y `migrate`, la aplicación
usa sus valores por omisión aunque `.env` cambie el modelo, y el registro nombra otro
modelo que el que respondió.

Estas pruebas leen `docker-compose.yml` (montado en el contenedor en `/app`) y comprueban:

- que `app` y `migrate` reciben cada variable de modelo con el mismo valor por omisión
  que usan los servicios;
- que lo que ve la aplicación (`settings.py`, con el entorno que le pasó Docker Compose)
  es lo mismo que resuelve el `command` de cada servicio con ese entorno;
- que los valores por omisión de `settings.py` son los del compose;
- que la compilación del motor registrada es la de la etiqueta de la imagen.
"""

import os
import re
import runpy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from django.conf import settings

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"

AI_SERVICES = ("generation", "embeddings", "reranker")
# Servicios de generación: `generation_batch` es el mismo motor con su propio contexto
# (plan 004, ADR-0037).
COMMAND_SERVICES = AI_SERVICES + ("generation_batch",)

# Variables de modelo que usan los servicios y que la aplicación tiene que recibir igual.
SHARED_VARIABLES = (
    "GENERATION_MODEL_ALIAS",
    "GENERATION_MODEL_FILE",
    "GENERATION_CTX_SIZE",
    "GENERATION_BATCH_CTX_SIZE",
    "EMBEDDINGS_MODEL_ALIAS",
    "EMBEDDINGS_MODEL_FILE",
    "RERANKER_MODEL_ALIAS",
    "RERANKER_MODEL_FILE",
)

# Variables propias del motor de lotes (plan 004, ADR-0041 y ADR-0042): el modelo, el alias
# y el proyector de imagen de `generation_batch`; por omisión, el modelo de `generation`.
BATCH_MODEL_VARIABLES = (
    "GENERATION_BATCH_MODEL_ALIAS",
    "GENERATION_BATCH_MODEL_FILE",
    "GENERATION_BATCH_MODEL_SHA256",
    "GENERATION_BATCH_MMPROJ_FILE",
    "GENERATION_BATCH_MMPROJ_SHA256",
)

# Variables propias de la aplicación (los servicios no las usan).
APP_ONLY_VARIABLES = (
    "GENERATION_URL",
    "EMBEDDINGS_URL",
    "RERANKER_URL",
    "GENERATION_MODEL_SHA256",
    "EMBEDDINGS_MODEL_SHA256",
    "RERANKER_MODEL_SHA256",
)

# `${NOMBRE:-valor}` o `${NOMBRE-valor}` (interpolación de Docker Compose).
# El valor por omisión puede ser otra interpolación (`${A:-${B:-c}}`): esta expresión toma
# la más interna; `resolve` repite hasta que no quedan.
INTERPOLATION = re.compile(r"\$\{(?P<name>\w+)(?P<op>:?-)(?P<default>[^}{$]*)\}")

# Imagen de los servicios de IA: la compilación es el final de la etiqueta.
IMAGE = re.compile(r"^ghcr\.io/ggml-org/llama\.cpp:server-cuda-(?P<build>b\d+)$")


@pytest.fixture(scope="module")
def compose():
    assert COMPOSE_FILE.is_file(), (
        f"No se encuentra {COMPOSE_FILE}: docker-compose.yml tiene que estar montado en "
        "app y migrate"
    )
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def resolve(text, environ):
    """Resuelve `${NOMBRE:-valor}` como Docker Compose: con `:-` toma el valor por omisión
    si la variable falta o está vacía; con `-`, solo si falta."""

    def replace(match):
        value = environ.get(match["name"])
        if match["op"] == ":-":
            return value or match["default"]
        return match["default"] if value is None else value

    text = str(text)
    while INTERPOLATION.search(text):
        text = INTERPOLATION.sub(replace, text)
    return text


def service_defaults(compose):
    """Valor por omisión de cada variable en los `command` de los servicios de IA. Una
    variable que aparece con dos valores por omisión distintos es un error del compose."""
    defaults = {}
    for service in COMMAND_SERVICES:
        for item in compose["services"][service]["command"]:
            for match in INTERPOLATION.finditer(str(item)):
                previous = defaults.setdefault(match["name"], match["default"])
                assert previous == match["default"], (
                    f"{match['name']} tiene dos valores por omisión en el compose: "
                    f"{previous!r} y {match['default']!r}"
                )
    return defaults


def argument(compose, service, flag, environ):
    """Valor resuelto con `environ` del argumento `flag` del `command` de `service`."""
    command = [str(item) for item in compose["services"][service]["command"]]
    return resolve(command[command.index(flag) + 1], environ)


def test_app_and_migrate_receive_the_model_variables_with_the_services_defaults(compose):
    """REQ-008, REQ-012: `app` y `migrate` reciben cada variable de modelo que usan los
    servicios de IA (alias, archivo y contexto de generación), escrita igual que en el
    `command` del servicio, con el mismo valor por omisión: servidor y aplicación leen una
    sola fuente, `.env`, y caen en el mismo valor si falta."""
    defaults = service_defaults(compose)
    for service in ("app", "migrate"):
        environment = compose["services"][service]["environment"]
        for name in SHARED_VARIABLES:
            assert name in defaults, f"{name} no lo usa ningún servicio de IA"
            assert environment.get(name) == f"${{{name}:-{defaults[name]}}}", (
                f"{service} no recibe {name} con el valor por omisión del servicio"
            )
        for name in APP_ONLY_VARIABLES:
            assert INTERPOLATION.fullmatch(str(environment.get(name, ""))), (
                f"{service} no recibe {name} desde .env"
            )


def test_application_sees_what_the_services_use(compose):
    """REQ-008, REQ-012: con el entorno que recibió la aplicación, el alias, el archivo y
    el contexto que lee `settings.py` son los que resuelve el `command` de cada servicio.
    Dentro del contenedor `app`, ese entorno es el que Docker Compose armó desde `.env`."""
    env = os.environ
    assert settings.GENERATION_MODEL == argument(compose, "generation", "--alias", env)
    assert settings.EMBEDDINGS_MODEL == argument(compose, "embeddings", "--alias", env)
    assert settings.RERANKER_MODEL == argument(compose, "reranker", "--alias", env)

    for service, file_name in [
        ("generation", settings.GENERATION_MODEL_FILE),
        ("embeddings", settings.EMBEDDINGS_MODEL_FILE),
        ("reranker", settings.RERANKER_MODEL_FILE),
    ]:
        assert "/models/" + file_name == argument(compose, service, "--model", env)

    assert settings.GENERATION_CONTEXT_TOKENS == int(
        argument(compose, "generation", "--ctx-size", env)
    )
    assert settings.GENERATION_BATCH_CONTEXT_TOKENS == int(
        argument(compose, "generation_batch", "--ctx-size", env)
    )


def test_settings_defaults_are_the_compose_defaults(compose, monkeypatch):
    """REQ-008, REQ-012: sin ninguna variable de modelo ni de servicio en el entorno,
    `settings.py` toma los mismos valores por omisión que el compose, así fuera de Docker
    la aplicación tampoco nombra otro modelo que el que arranca el servidor."""
    app_environment = compose["services"]["app"]["environment"]
    for name in SHARED_VARIABLES + APP_ONLY_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))

    no_env = {}
    assert fresh["GENERATION_MODEL"] == argument(compose, "generation", "--alias", no_env)
    assert fresh["EMBEDDINGS_MODEL"] == argument(compose, "embeddings", "--alias", no_env)
    assert fresh["RERANKER_MODEL"] == argument(compose, "reranker", "--alias", no_env)
    assert "/models/" + fresh["GENERATION_MODEL_FILE"] == argument(
        compose, "generation", "--model", no_env)
    assert "/models/" + fresh["EMBEDDINGS_MODEL_FILE"] == argument(
        compose, "embeddings", "--model", no_env)
    assert "/models/" + fresh["RERANKER_MODEL_FILE"] == argument(
        compose, "reranker", "--model", no_env)
    assert fresh["GENERATION_CONTEXT_TOKENS"] == int(
        argument(compose, "generation", "--ctx-size", no_env))
    assert fresh["GENERATION_BATCH_CONTEXT_TOKENS"] == int(
        argument(compose, "generation_batch", "--ctx-size", no_env))
    assert fresh["GENERATION_BATCH_CONTEXT_TOKENS"] == 32768
    # Direcciones y huellas: el nombre en settings.py es el de la variable.
    for name in APP_ONLY_VARIABLES:
        assert fresh[name] == resolve(app_environment[name], no_env), name


def test_the_batch_engine_context_reaches_every_service_of_the_app_image(compose):
    """REQ-054 (ADR-0037, P6): `app`, `migrate` y `worker` reciben el contexto del motor de
    lotes desde `.env`, con el mismo valor por omisión (32.768) que el servicio, para
    registrar el contexto real con cada propuesta y evaluación."""
    for name in ("app", "migrate", "worker"):
        environment = compose["services"][name]["environment"]
        assert environment["GENERATION_BATCH_CTX_SIZE"] == (
            "${GENERATION_BATCH_CTX_SIZE:-32768}")


def test_engine_build_is_the_image_tag(compose):
    """REQ-008, REQ-012: la compilación del motor que se registra con cada consulta
    (`GENERATION_ENGINE_BUILD`) es la de la etiqueta de la imagen de los tres servicios de
    IA, que es la misma en los tres."""
    builds = set()
    for service in AI_SERVICES:
        image = compose["services"][service]["image"]
        match = IMAGE.match(image)
        assert match, f"{service}: imagen inesperada {image!r}"
        builds.add(match["build"])

    assert builds == {settings.GENERATION_ENGINE_BUILD}


# Variables del Portal de Compras (plan 012, ADR-0031): el compose las pasa a todos los
# servicios de la imagen y `settings.py` las lee con el mismo valor por omisión.
PORTAL_VARIABLES = (
    "PORTAL_ALLOWED_HOSTS",
    "PORTAL_TIMEOUT_SECONDS",
    "PORTAL_MAX_BYTES",
    "PORTAL_PAUSE_SECONDS",
    "PORTAL_REVIEW_HOUR",
    "PORTAL_USER_AGENT",
)


def test_portal_variables_reach_app_and_portal_worker(compose):
    """REQ-045: la aplicación (que valida el enlace) y `portal_worker` (que conecta) reciben
    la misma lista de destinos y los mismos límites."""
    for service in ("app", "migrate", "worker", "portal_worker"):
        environment = compose["services"][service]["environment"]
        for name in PORTAL_VARIABLES:
            assert name in environment, f"{service} no recibe {name}"
    app = compose["services"]["app"]["environment"]
    worker = compose["services"]["portal_worker"]["environment"]
    for name in PORTAL_VARIABLES:
        assert app[name] == worker[name]


def test_portal_settings_defaults_are_the_compose_defaults(compose, monkeypatch):
    """REQ-045: sin variables en el entorno, `settings.py` toma los mismos valores por
    omisión que el compose, y el destino por omisión es solo el host del Portal."""
    environment = compose["services"]["portal_worker"]["environment"]
    for name in PORTAL_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))

    assert fresh["PORTAL_ALLOWED_HOSTS"] == ["afipcompras.afip.gob.ar"]
    assert fresh["PORTAL_ALLOWED_HOSTS"] == resolve(
        environment["PORTAL_ALLOWED_HOSTS"], {}).split(",")
    assert fresh["PORTAL_TIMEOUT_SECONDS"] == int(
        resolve(environment["PORTAL_TIMEOUT_SECONDS"], {}))
    assert fresh["PORTAL_MAX_BYTES"] == int(resolve(environment["PORTAL_MAX_BYTES"], {}))
    assert fresh["PORTAL_PAUSE_SECONDS"] == float(
        resolve(environment["PORTAL_PAUSE_SECONDS"], {}))
    assert fresh["PORTAL_REVIEW_HOUR"] == int(resolve(environment["PORTAL_REVIEW_HOUR"], {}))
    assert fresh["PORTAL_USER_AGENT"] == resolve(environment["PORTAL_USER_AGENT"], {})


# --- Uso externo de la feature 016 (plan 016, "Plataforma externa"; ADR-0066 y ADR-0068) ----

EXTERNAL_VARIABLES = (
    "EXTERNAL_ENABLED",
    "EXTERNAL_STAGE_MATRIZ",
    "EXTERNAL_STAGE_VERIFICADOR",
    "EXTERNAL_MODEL_MATRIZ",
    "EXTERNAL_MODEL_VERIFICADOR",
    "EXTERNAL_EFFORT_MATRIZ",
    "EXTERNAL_EFFORT_VERIFICADOR",
    "EXTERNAL_THINKING_MATRIZ",
    "EXTERNAL_THINKING_VERIFICADOR",
    "EXTERNAL_MODE",
    "EXTERNAL_BATCH_POLL_SECONDS",
    "EXTERNAL_BATCH_MAX_WAIT_SECONDS",
    "EXTERNAL_CASE_CAP_USD",
    "EXTERNAL_MONTH_CAP_USD",
    "EXTERNAL_STAGE_ESTIMATE_MATRIZ_USD",
    "EXTERNAL_STAGE_ESTIMATE_VERIFICADOR_USD",
    "EXTERNAL_STAGE_STOP_FACTOR",
)
ENV_EXAMPLE = Path(settings.BASE_DIR) / ".env.example"


def test_external_variables_reach_every_service_of_the_app_image(compose):
    """REQ-122: la aplicación, `migrate` y `worker` (que son los que piden) reciben las mismas
    variables del uso externo; `portal_worker`, que tiene salida, también las ve y por
    omisión todo está apagado."""
    for service in ("app", "migrate", "worker", "portal_worker"):
        environment = compose["services"][service]["environment"]
        for name in EXTERNAL_VARIABLES:
            assert name in environment, f"{service} no recibe {name}"
    app = compose["services"]["app"]["environment"]
    assert resolve(app["EXTERNAL_ENABLED"], {}) == "false"
    assert resolve(app["EXTERNAL_STAGE_MATRIZ"], {}) == "local"
    assert resolve(app["EXTERNAL_STAGE_VERIFICADOR"], {}) == "local"


def test_the_api_key_is_not_in_the_base_compose(compose):
    """REQ-122, P4: la clave del proveedor no va en el compose base; la pone, en su caso, el
    archivo de salida (T-289) desde el entorno del clon."""
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" not in text
    for service in compose["services"].values():
        assert "ANTHROPIC_API_KEY" not in (service.get("environment") or {})


def test_external_settings_defaults_are_the_compose_defaults(compose, monkeypatch):
    """REQ-122: sin variables en el entorno, `settings.py` toma los mismos valores por
    omisión que el compose, y con ellos el uso externo está apagado (umbral 20)."""
    environment = compose["services"]["app"]["environment"]
    for name in EXTERNAL_VARIABLES + ("ANTHROPIC_API_KEY",):
        monkeypatch.delenv(name, raising=False)

    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))

    def default(name):
        return resolve(environment[name], {})

    assert fresh["EXTERNAL_ENABLED"] is False
    assert fresh["EXTERNAL_STAGES"] == {"matriz": "local", "verificador": "local"}
    for stage in ("matriz", "verificador"):
        upper = stage.upper()
        assert fresh["EXTERNAL_STAGES"][stage] == default(f"EXTERNAL_STAGE_{upper}")
        assert fresh["EXTERNAL_MODELS"][stage] == default(f"EXTERNAL_MODEL_{upper}")
        assert fresh["EXTERNAL_EFFORT"][stage] == default(f"EXTERNAL_EFFORT_{upper}")
        assert fresh["EXTERNAL_THINKING"][stage] == default(f"EXTERNAL_THINKING_{upper}")
        assert fresh["EXTERNAL_STAGE_ESTIMATE_USD"][stage] == Decimal(
            default(f"EXTERNAL_STAGE_ESTIMATE_{upper}_USD"))
    assert fresh["EXTERNAL_MODE"] == default("EXTERNAL_MODE") == "lotes"
    assert fresh["EXTERNAL_BATCH_POLL_SECONDS"] == int(default("EXTERNAL_BATCH_POLL_SECONDS"))
    assert fresh["EXTERNAL_BATCH_MAX_WAIT_SECONDS"] == int(
        default("EXTERNAL_BATCH_MAX_WAIT_SECONDS"))
    assert fresh["EXTERNAL_CASE_CAP_USD"] == Decimal(default("EXTERNAL_CASE_CAP_USD"))
    assert fresh["EXTERNAL_MONTH_CAP_USD"] == Decimal(default("EXTERNAL_MONTH_CAP_USD"))
    assert fresh["EXTERNAL_STAGE_STOP_FACTOR"] == Decimal(default("EXTERNAL_STAGE_STOP_FACTOR"))
    # La clave no se lee de `settings` por omisión (ADR-0066): la lee el cliente del entorno.
    assert not any("API_KEY" in name for name in fresh if name.startswith("EXTERNAL"))
    assert "ANTHROPIC_API_KEY" not in fresh


def test_external_defaults_are_the_ones_the_responsible_decided(monkeypatch):
    """REQ-122: topes de 2 USD por caso y 10 por mes, etapas de 0,30 USD que se frenan al
    doble, lotes cada 30 segundos con espera máxima de 2 horas (plan 016, "Costo y tope")."""
    for name in EXTERNAL_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))
    assert fresh["EXTERNAL_CASE_CAP_USD"] == Decimal("2.00")
    assert fresh["EXTERNAL_MONTH_CAP_USD"] == Decimal("10.00")
    assert fresh["EXTERNAL_STAGE_ESTIMATE_USD"] == {
        "matriz": Decimal("0.30"), "verificador": Decimal("0.30")}
    assert fresh["EXTERNAL_STAGE_STOP_FACTOR"] == 2
    assert fresh["EXTERNAL_BATCH_POLL_SECONDS"] == 30
    assert fresh["EXTERNAL_BATCH_MAX_WAIT_SECONDS"] == 7200
    assert set(fresh["EXTERNAL_MODELS"].values()) == {"claude-sonnet-5-5"}
    assert fresh["EXTERNAL_EFFORT"] == {"matriz": "medium", "verificador": "low"}
    assert fresh["EXTERNAL_THINKING"]["verificador"] == "between_tools"


def test_the_price_table_is_versioned_with_date_and_source(monkeypatch):
    """REQ-122: la tabla de precios lleva versión, fecha y fuente, y los precios de lista
    del 2026-10-15 (ADR-0068, punto 3)."""
    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))
    prices = fresh["EXTERNAL_PRICES"]
    assert prices["version"] and prices["fecha"] == "2026-10-15"
    assert prices["fuente"].startswith("https://")
    sonnet = prices["modelos"]["claude-sonnet-5-5"]
    opus = prices["modelos"]["claude-opus-5-5"]
    assert (sonnet["entrada"], sonnet["salida"]) == (Decimal("2"), Decimal("10"))
    assert (opus["entrada"], opus["salida"]) == (Decimal("4"), Decimal("20"))
    assert prices["lotes"] == Decimal("0.5")
    assert prices["cache_lectura"] == Decimal("0.05")
    assert prices["cache_escritura_1h"] == 2


@pytest.mark.parametrize("name,value", [
    ("EXTERNAL_STAGE_MATRIZ", "nube"),
    ("EXTERNAL_MODE", "inmediato"),
    ("EXTERNAL_THINKING_VERIFICADOR", "siempre"),
    ("EXTERNAL_EFFORT_MATRIZ", "enorme"),
])
def test_an_invalid_external_value_stops_the_start(monkeypatch, name, value):
    """REQ-122: un valor inválido no se interpreta en silencio; detiene el arranque."""
    from django.core.exceptions import ImproperlyConfigured
    monkeypatch.setenv(name, value)
    with pytest.raises(ImproperlyConfigured):
        runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))


def test_env_example_lists_every_external_variable_without_a_key():
    """REQ-122, P4: `.env.example` nombra cada variable del uso externo y no trae ninguna clave."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for name in EXTERNAL_VARIABLES:
        assert re.search(rf"^#?\s*{name}=", text, re.MULTILINE), f"falta {name}"
    assert "sk-ant" not in text
    assert not re.search(r"^ANTHROPIC_API_KEY=\S", text, re.MULTILINE)


# --- Modelo propio del motor de lotes (plan 004, ADR-0041 y ADR-0042) ---------------------

REPO = Path(settings.BASE_DIR)
LARGE_COMPOSE_FILE = REPO / "docker-compose.modelo-grande.yml"
CHECKSUMS = REPO / "scripts" / "models.sha256"
FETCH_SCRIPT = REPO / "scripts" / "fetch_models.sh"
BATCH_ENV_SERVICES = ("app", "migrate", "worker")


def _checksums():
    """Nombre de archivo y huella de `scripts/models.sha256`."""
    rows = [line.split() for line in CHECKSUMS.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return {name: digest for digest, name in rows}


def _argument(command, flag):
    command = [str(item) for item in command]
    return command[command.index(flag) + 1]


@pytest.fixture(scope="module")
def large_compose():
    assert LARGE_COMPOSE_FILE.is_file(), (
        f"No se encuentra {LARGE_COMPOSE_FILE}: tiene que estar montado en app"
    )
    return yaml.safe_load(LARGE_COMPOSE_FILE.read_text(encoding="utf-8"))


def test_batch_model_variables_reach_the_app_image_and_default_to_generation(compose):
    """REQ-052: `app`, `migrate` y `worker` reciben las variables propias del lote; sin
    ellas en `.env` valen las de `generation` (alias, archivo y huella), y el proyector es
    el del 12B."""
    for service in BATCH_ENV_SERVICES:
        environment = compose["services"][service]["environment"]
        for name in BATCH_MODEL_VARIABLES:
            assert name in environment, f"{service} no recibe {name}"
    environment = compose["services"]["app"]["environment"]
    for name, generation_name in [
        ("GENERATION_BATCH_MODEL_ALIAS", "GENERATION_MODEL_ALIAS"),
        ("GENERATION_BATCH_MODEL_FILE", "GENERATION_MODEL_FILE"),
        ("GENERATION_BATCH_MODEL_SHA256", "GENERATION_MODEL_SHA256"),
    ]:
        assert resolve(environment[name], {}) == resolve(environment[generation_name], {})
        # Si .env cambia el modelo de generation, el lote lo sigue salvo que tenga el suyo.
        assert resolve(environment[name], {generation_name: "otro"}) == "otro"
        assert resolve(environment[name], {generation_name: "otro", name: "propio"}) == (
            "propio")
    assert resolve(environment["GENERATION_BATCH_MMPROJ_FILE"], {}) == (
        "mmproj-gemma-4-12b-it-qat-q4_0.gguf")


def test_the_batch_engine_loads_its_own_model_and_the_image_projector(compose):
    """REQ-052: `generation_batch` toma el modelo y el alias de las variables del lote y
    suma `--mmproj` con el proyector del 12B por omisión; `generation` no cambia."""
    batch = compose["services"]["generation_batch"]["command"]
    assert "--mmproj" in [str(item) for item in batch]
    assert resolve(_argument(batch, "--mmproj"), {}) == (
        "/models/mmproj-gemma-4-12b-it-qat-q4_0.gguf")
    assert resolve(_argument(batch, "--model"), {}) == "/models/gemma-4-12b-it-qat-q4_0.gguf"
    assert resolve(_argument(batch, "--alias"), {}) == "gemma-4-12b-it-qat-q4_0"
    assert resolve(_argument(batch, "--model"), {"GENERATION_BATCH_MODEL_FILE": "x.gguf"}) == (
        "/models/x.gguf")
    assert resolve(_argument(batch, "--alias"), {"GENERATION_BATCH_MODEL_ALIAS": "x"}) == "x"
    interactive = [str(item) for item in compose["services"]["generation"]["command"]]
    assert "--mmproj" not in interactive
    assert resolve(_argument(interactive, "--model"),
                   {"GENERATION_BATCH_MODEL_FILE": "x.gguf"}) == (
        "/models/gemma-4-12b-it-qat-q4_0.gguf")


def test_application_records_the_model_the_batch_engine_loads(compose):
    """REQ-052 (P6): con el entorno que recibió la aplicación, el alias, el archivo y el
    proyector que lee `settings.py` para registrar las evaluaciones son los que resuelve el
    `command` de `generation_batch`."""
    env = os.environ
    command = compose["services"]["generation_batch"]["command"]
    assert settings.GENERATION_BATCH_MODEL == resolve(_argument(command, "--alias"), env)
    assert "/models/" + settings.GENERATION_BATCH_MODEL_FILE == resolve(
        _argument(command, "--model"), env)
    assert "/models/" + settings.GENERATION_BATCH_MMPROJ_FILE == resolve(
        _argument(command, "--mmproj"), env)


def test_batch_settings_defaults_are_the_compose_defaults(compose, monkeypatch):
    """REQ-052: sin variables en el entorno, `settings.py` toma para el lote los mismos
    valores por omisión que el compose (los de `generation` y el proyector del 12B), y las
    huellas son las de `scripts/models.sha256`."""
    for name in BATCH_MODEL_VARIABLES + SHARED_VARIABLES + APP_ONLY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    fresh = runpy.run_path(str(REPO / "evaluon" / "settings.py"))
    environment = compose["services"]["app"]["environment"]
    for setting, variable in [
        ("GENERATION_BATCH_MODEL", "GENERATION_BATCH_MODEL_ALIAS"),
        ("GENERATION_BATCH_MODEL_FILE", "GENERATION_BATCH_MODEL_FILE"),
        ("GENERATION_BATCH_MODEL_SHA256", "GENERATION_BATCH_MODEL_SHA256"),
        ("GENERATION_BATCH_MMPROJ_FILE", "GENERATION_BATCH_MMPROJ_FILE"),
        ("GENERATION_BATCH_MMPROJ_SHA256", "GENERATION_BATCH_MMPROJ_SHA256"),
    ]:
        assert fresh[setting] == resolve(environment[variable], {}), setting
    checksums = _checksums()
    assert checksums[fresh["GENERATION_BATCH_MODEL_FILE"]] == fresh[
        "GENERATION_BATCH_MODEL_SHA256"]
    assert checksums[fresh["GENERATION_BATCH_MMPROJ_FILE"]] == fresh[
        "GENERATION_BATCH_MMPROJ_SHA256"]

    # Con solo el modelo de generation cambiado, el lote lo sigue (misma regla del compose).
    monkeypatch.setenv("GENERATION_MODEL_FILE", "otro.gguf")
    fresh = runpy.run_path(str(REPO / "evaluon" / "settings.py"))
    assert fresh["GENERATION_BATCH_MODEL_FILE"] == "otro.gguf"


def test_large_model_file_only_replaces_the_batch_engine(compose, large_compose):
    """REQ-052 (ADR-0042): `docker-compose.modelo-grande.yml` sobrescribe `generation_batch`
    con el 26B-A4B y su proyector, con los mismos argumentos que el compose base salvo el
    modelo, el alias y el proyector; `app` y `worker` registran ese modelo, y no toca
    `generation`, `embeddings`, `reranker`, `db` ni `portal_worker`."""
    assert set(large_compose["services"]) == {"generation_batch", "worker", "app"}
    base = [str(item) for item in compose["services"]["generation_batch"]["command"]]
    large = [str(item) for item in large_compose["services"]["generation_batch"]["command"]]
    assert _argument(large, "--model") == "/models/gemma-4-26B_q4_0-it.gguf"
    assert _argument(large, "--mmproj") == "/models/gemma-4-26B-it-mmproj.gguf"

    def common(command):
        out = list(command)
        for flag in ("--model", "--alias", "--mmproj"):
            position = out.index(flag)
            del out[position:position + 2]
        return out

    assert common(large) == common(base)
    assert _argument(large, "--alias") != resolve(_argument(base, "--alias"), {})
    for service in ("app", "worker"):
        assert "command" not in large_compose["services"][service]
        environment = large_compose["services"][service]["environment"]
        assert environment["GENERATION_BATCH_MODEL_FILE"] == "gemma-4-26B_q4_0-it.gguf"
        assert environment["GENERATION_BATCH_MODEL_ALIAS"] == _argument(large, "--alias")
        assert environment["GENERATION_BATCH_MMPROJ_FILE"] == "gemma-4-26B-it-mmproj.gguf"


def test_large_model_hashes_are_the_pinned_ones(large_compose):
    """REQ-052 (P6): las huellas del 26B-A4B y su proyector que registra el compose son las
    de `scripts/models.sha256`, que el descargador verifica."""
    checksums = _checksums()
    environment = large_compose["services"]["app"]["environment"]
    assert checksums[environment["GENERATION_BATCH_MODEL_FILE"]] == (
        environment["GENERATION_BATCH_MODEL_SHA256"])
    assert checksums[environment["GENERATION_BATCH_MMPROJ_FILE"]] == (
        environment["GENERATION_BATCH_MMPROJ_SHA256"])
    assert checksums["gemma-4-26B_q4_0-it.gguf"] == (
        "3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d")
    assert checksums["gemma-4-26B-it-mmproj.gguf"] == (
        "a359953a076b877db30c31dbbb4c6d93b4a6e017ee5db5784247e4d4c0dd4f3b")
    assert checksums["mmproj-gemma-4-12b-it-qat-q4_0.gguf"] == (
        "cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7")


def test_fetch_script_lists_every_model_file_with_a_pinned_revision():
    """REQ-052: `fetch_models.sh` baja el proyector del 12B en la lista normal y el 26B-A4B
    con su proyector solo con `--modelo-grande`, cada archivo con revisión fijada y huella
    en `scripts/models.sha256`."""
    text = FETCH_SCRIPT.read_text(encoding="utf-8")
    assert "--modelo-grande" in text
    normal_block, large_block = text.split("LARGE_SOURCES=(", 1)
    large_block = large_block.split("\n)\n", 1)[0]
    pattern = re.compile(
        r'"(\S+) https://huggingface\.co/(\S+)/resolve/([0-9a-f]{40})/(\S+)"')
    normal = {m[1]: (m[2], m[3], m[4]) for m in pattern.finditer(normal_block)}
    large = {m[1]: (m[2], m[3], m[4]) for m in pattern.finditer(large_block)}
    assert set(normal) == {
        "gemma-4-12b-it-qat-q4_0.gguf", "mmproj-gemma-4-12b-it-qat-q4_0.gguf",
        "bge-m3-FP16.gguf", "bge-reranker-v2-m3-FP16.gguf"}
    assert set(large) == {"gemma-4-26B_q4_0-it.gguf", "gemma-4-26B-it-mmproj.gguf"}
    assert normal["mmproj-gemma-4-12b-it-qat-q4_0.gguf"][1:] == (
        "29d097773436b69ff9feafd636ab4cf873786537", "mmproj-gemma-4-12b-it-qat-q4_0.gguf")
    for name, (repo, revision, remote_name) in large.items():
        assert repo == "google/gemma-4-26B-A4B-it-qat-q4_0-gguf"
        assert revision == "d1c082be9cf3c8a514acf63b8761f4b41935842e"
        assert remote_name == name
    checksums = _checksums()
    for name in list(normal) + list(large):
        assert name in checksums, f"{name} no figura en scripts/models.sha256"


# --- Modelos candidatos de la 015 (ADR-0056, T-242) ---------------------------------------

CANDIDATES = {
    "qwen38-27b": {
        "option": "--qwen38-27b",
        "sources": "QWEN38_SOURCES",
        "alias": "qwen3.8-27b-ud-q4_k_m",
        "model": "Qwen3.8-27B-UD-Q4_K_M.gguf",
        "model_sha256": "322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482",
        "mmproj": "mmproj-Qwen3.8-27B-F16.gguf",
        "mmproj_sha256": "cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e",
        "repo": "unsloth/Qwen3.8-27B-GGUF",
        "revision": "4ca720788d1e01f1bff70c033e0d0028fd02e502",
        # La espera de la carga que suma su archivo (T-247): lo único, además del `command`, que
        # sobrescribe en `generation_batch`.
        "healthcheck": {"start_period": "900s"},
    },
    "qwen36-35b": {
        "option": "--qwen36-35b",
        "sources": "QWEN36_SOURCES",
        "alias": "qwen3.6-35b-a3b-ud-iq4_xs",
        "model": "Qwen3.6-35B-A3B-UD-IQ4_XS.gguf",
        "model_sha256": "649d7508507b84638732c4f52c24c8b15843c6dca2f3ff793ae07c14a67ebbb3",
        "mmproj": "mmproj-Qwen3.6-35B-A3B-F16.gguf",
        "mmproj_sha256": "8971ee4f331ff0a4c609374f32984b3d4e6dc086c0aa35f1d637fad1829e887f",
        "repo": "unsloth/Qwen3.6-35B-A3B-GGUF",
        "revision": "a483e9e6cbd595906af30beda3187c2663a1118c",
    },
}

# Banderas de la caché de prefijo que declaran los candidatos (ADR-0056, punto 4): lo único,
# además del modelo, el alias y el proyector, que los distingue del compose base.
PREFIX_CACHE_FLAGS = {"--ctx-checkpoints": "32", "--checkpoint-min-step": "1024"}


def _candidate_compose(name):
    path = REPO / f"docker-compose.{name}.yml"
    assert path.is_file(), f"No se encuentra {path}: tiene que estar montado en app"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _without(command, flags):
    """El `command` sin las banderas dadas y sus valores."""
    out = [str(item) for item in command]
    for flag in flags:
        if flag in out:
            position = out.index(flag)
            del out[position:position + 2]
    return out


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_candidate_file_only_replaces_the_batch_engine(compose, name):
    """REQ-107 (ADR-0056, P4): el archivo de cada candidato sobrescribe solo el `command`
    de `generation_batch` y el `environment` de `app` y `worker`; no toca la imagen, las
    redes (el motor sigue en la red interna, sin salida) ni los puertos; el del 27B suma además
    la espera de la carga (`start_period`, T-247). Su `command` es el
    del compose base salvo el modelo, el alias, el proyector y las banderas de la caché de
    prefijo; sigue con `--parallel 1`, `--offline`, sin pensamiento y con el mismo
    contexto y el mismo tope de caché de pedidos."""
    spec = CANDIDATES[name]
    candidate = _candidate_compose(name)
    assert set(candidate["services"]) == {"generation_batch", "worker", "app"}
    engine = candidate["services"]["generation_batch"]
    assert set(engine) == {"command"} | ({"healthcheck"} if "healthcheck" in spec else set())
    assert engine.get("healthcheck") == spec.get("healthcheck")
    for service in ("worker", "app"):
        assert set(candidate["services"][service]) == {"environment"}

    base = [str(item) for item in compose["services"]["generation_batch"]["command"]]
    command = [str(item) for item in candidate["services"]["generation_batch"]["command"]]
    assert _argument(command, "--model") == "/models/" + spec["model"]
    assert _argument(command, "--mmproj") == "/models/" + spec["mmproj"]
    assert _argument(command, "--alias") == spec["alias"]
    assert _argument(command, "--alias") != resolve(_argument(base, "--alias"), {})
    own = ("--model", "--alias", "--mmproj")
    assert _without(command, own + tuple(PREFIX_CACHE_FLAGS)) == _without(base, own)
    for flag, value in PREFIX_CACHE_FLAGS.items():
        assert _argument(command, flag) == value
        assert flag not in base
    assert _argument(command, "--parallel") == "1"
    assert _argument(command, "--reasoning") == "off"
    assert _argument(command, "--reasoning-budget") == "0"
    assert "--offline" in command
    assert "--no-context-shift" in command


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_candidate_environment_names_what_the_engine_loads(name):
    """REQ-107 (P6): `app` y `worker` reciben el alias, el archivo, el proyector y las
    huellas del candidato, los mismos que carga el motor y que figuran en
    `scripts/models.sha256`; con ellos se registra el modelo de cada evaluación."""
    spec = CANDIDATES[name]
    candidate = _candidate_compose(name)
    command = [str(item) for item in candidate["services"]["generation_batch"]["command"]]
    checksums = _checksums()
    assert candidate["services"]["app"]["environment"] == (
        candidate["services"]["worker"]["environment"])
    environment = candidate["services"]["app"]["environment"]
    assert set(environment) == set(BATCH_MODEL_VARIABLES)
    assert environment["GENERATION_BATCH_MODEL_ALIAS"] == _argument(command, "--alias")
    assert "/models/" + environment["GENERATION_BATCH_MODEL_FILE"] == _argument(
        command, "--model")
    assert "/models/" + environment["GENERATION_BATCH_MMPROJ_FILE"] == _argument(
        command, "--mmproj")
    assert environment["GENERATION_BATCH_MODEL_FILE"] == spec["model"]
    assert environment["GENERATION_BATCH_MMPROJ_FILE"] == spec["mmproj"]
    assert environment["GENERATION_BATCH_MODEL_SHA256"] == spec["model_sha256"]
    assert environment["GENERATION_BATCH_MMPROJ_SHA256"] == spec["mmproj_sha256"]
    assert checksums[spec["model"]] == spec["model_sha256"]
    assert checksums[spec["mmproj"]] == spec["mmproj_sha256"]


def test_candidate_files_are_mounted_in_the_app_for_these_tests():
    """REQ-107: `docker-compose.yml` monta los archivos de los candidatos en la aplicación,
    solo para que estas pruebas los lean (como el del 26B-A4B)."""
    base = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    for volumes in (base["x-app"]["volumes"], base["services"]["app"]["volumes"]):
        for name in CANDIDATES:
            assert (f"./docker-compose.{name}.yml:/app/docker-compose.{name}.yml:ro"
                    in volumes)


def _sources_block(text, variable):
    """Las líneas `"nombre-local URL"` de la lista `variable=( ... )` de fetch_models.sh."""
    block = text.split(variable + "=(", 1)[1].split("\n)\n", 1)[0]
    pattern = re.compile(
        r'"(\S+) https://huggingface\.co/(\S+)/resolve/([0-9a-f]{40})/(\S+)"')
    return {m[1]: (m[2], m[3], m[4]) for m in pattern.finditer(block)}


@pytest.mark.parametrize("name", sorted(CANDIDATES))
def test_fetch_script_lists_each_candidate_with_a_pinned_revision(name):
    """REQ-107 (ADR-0056, P5): `fetch_models.sh` baja cada candidato solo con su opción, en
    una lista aparte con el repositorio de Unsloth, la revisión completa fijada y el
    nombre local del proyector con el modelo (los dos se llaman `mmproj-F16.gguf` en su
    repositorio); cada archivo tiene su huella en `scripts/models.sha256`."""
    spec = CANDIDATES[name]
    text = FETCH_SCRIPT.read_text(encoding="utf-8")
    assert spec["option"] in text
    listed = _sources_block(text, spec["sources"])
    assert set(listed) == {spec["model"], spec["mmproj"]}
    assert listed[spec["model"]] == (spec["repo"], spec["revision"], spec["model"])
    assert listed[spec["mmproj"]] == (spec["repo"], spec["revision"], "mmproj-F16.gguf")
    checksums = _checksums()
    assert checksums[spec["model"]] == spec["model_sha256"]
    assert checksums[spec["mmproj"]] == spec["mmproj_sha256"]
    # Ninguna otra lista los repite: no se bajan en la instalación normal.
    normal_block = text.split("LARGE_SOURCES=(", 1)[0]
    assert spec["model"] not in normal_block and spec["mmproj"] not in normal_block


def test_candidate_file_names_do_not_collide_with_the_other_models():
    """REQ-107: los nombres locales de los cuatro archivos de los candidatos son distintos
    entre sí y de los demás de `scripts/models.sha256` (los dos proyectores se llaman igual
    en su repositorio)."""
    names = [spec[key] for spec in CANDIDATES.values() for key in ("model", "mmproj")]
    assert len(set(names)) == 4
    checksums = _checksums()
    assert len(checksums) == 10
    assert all(name in checksums for name in names)


# --- T-247 · configuración de uso por omisión: el Qwen3.8-27B, razonamiento en el contraste, sin
# el motor de la Consulta (ADR-0057) --------------------------------------------------------------

ENV_EXAMPLE = REPO / ".env.example"
NO_QUERY_ENGINE_FILE = REPO / "docker-compose.sin-consulta.yml"
# T-255: la Consulta va al motor del 27B. Reemplaza en la configuración de uso al archivo anterior,
# que sigue siendo válido para el 27B sin Consulta.
QUERY_27B_FILE = REPO / "docker-compose.consulta-27b.yml"
DEFAULT_FILES = ("docker-compose.yml", "docker-compose.qwen38-27b.yml",
                 "docker-compose.razonamiento.yml", "docker-compose.consulta-27b.yml")


def _env_example():
    """Las asignaciones sin comentar de `.env.example`: `{variable: valor}`."""
    values = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            values[name] = value
    return values


def test_the_default_install_is_the_27b_with_reasoning_only_in_the_contrast():
    """REQ-107 (T-247, T-255): `.env.example` trae lo que hace que `docker compose up` desde cero
    levante el Qwen3.8-27B con el razonamiento solo en el contraste y la Consulta en ese mismo motor
    (sin `generation`): `COMPOSE_FILE` con los cuatro archivos en ese orden (el de razonamiento
    después del que fija el modelo), el separador `:` explícito (en Windows el de Compose es `;`) y
    una sola variable de razonamiento encendida."""
    env = _env_example()
    assert env["COMPOSE_PATH_SEPARATOR"] == ":"
    assert tuple(env["COMPOSE_FILE"].split(":")) == DEFAULT_FILES
    for name in DEFAULT_FILES:
        assert (REPO / name).is_file(), name
    on = {name: value for name, value in env.items()
          if name.startswith("GENERATION_BATCH_REASONING") and value not in ("", "off")}
    assert on == {"GENERATION_BATCH_REASONING_CONTRAST": "low"}
    # la clave y la contraseña siguen vacías: ningún secreto va al repositorio
    assert env["POSTGRES_PASSWORD"] == "" and env["DJANGO_SECRET_KEY"] == ""


def test_the_default_files_are_mounted_in_the_app_for_these_tests():
    """REQ-107 (T-247, T-255): `docker-compose.yml` monta en la aplicación el archivo que apaga la
    Consulta, el que la lleva al motor del 27B y `.env.example`, solo para que estas pruebas los
    lean."""
    base = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    for volumes in (base["x-app"]["volumes"], base["services"]["app"]["volumes"]):
        assert "./docker-compose.sin-consulta.yml:/app/docker-compose.sin-consulta.yml:ro" in volumes
        assert "./docker-compose.consulta-27b.yml:/app/docker-compose.consulta-27b.yml:ro" in volumes
        assert "./.env.example:/app/.env.example:ro" in volumes


def test_the_file_without_the_query_engine_only_switches_it_off():
    """REQ-107 (T-247): `docker-compose.sin-consulta.yml` pone `generation` en un perfil (no
    arranca con `docker compose up`) y hace que `app` no lo espere (`required: false`); no
    toca redes, puertos, imágenes, volúmenes ni a los demás servicios. Con perfil y sin la
    dependencia opcional, Compose rechazaría el proyecto o `app` esperaría para siempre."""
    file = yaml.safe_load(NO_QUERY_ENGINE_FILE.read_text(encoding="utf-8"))
    assert set(file) == {"services"}
    assert set(file["services"]) == {"generation", "app"}
    assert file["services"]["generation"] == {"profiles": ["consulta-12b"]}
    assert file["services"]["app"] == {"depends_on": {"generation": {
        "condition": "service_healthy", "required": False}}}
    # el servicio y su dependencia existen en el compose base, con la misma condición
    base = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert base["services"]["app"]["depends_on"]["generation"] == {
        "condition": "service_healthy"}
    assert "profiles" not in base["services"]["generation"]  # el base sigue levantando la Consulta


def test_the_default_install_keeps_the_batch_engine_off_the_internet(compose):
    """P4 (T-247, T-255): ningún archivo de la configuración de uso (ni el que apaga la Consulta)
    agrega redes, puertos ni salida a `generation_batch`: sigue solo en la red interna, sin
    puertos, y la red interna no tiene salida a internet."""
    assert compose["networks"]["internal"]["internal"] is True
    batch = compose["services"]["generation_batch"]
    assert batch["networks"] == ["internal"] and "ports" not in batch
    for name in (*DEFAULT_FILES[1:], "docker-compose.sin-consulta.yml"):
        file = yaml.safe_load((REPO / name).read_text(encoding="utf-8"))
        for service, body in (file.get("services") or {}).items():
            assert not {"networks", "ports", "image", "extra_hosts", "network_mode"} & set(body),                 (name, service)
        assert "networks" not in file, name


def _seconds(duration):
    """Los segundos de una duración de Compose como `120s` o `900s`."""
    assert re.fullmatch(r"\d+s", str(duration)), duration
    return int(str(duration)[:-1])


def test_the_27b_file_waits_for_the_model_load_before_counting_failed_health_checks(compose):
    """REQ-107 (T-247, P5): el 27B tarda de 3 a 10 minutos en cargar (T-244, T-244d); con los
    120 s del compose base `generation_batch` pasaba a `unhealthy` durante la carga y
    `docker compose up -d` desde cero (el `worker` espera su salud) terminaba con error. El archivo
    del 27B sube solo el `start_period` a 900 s, más que la carga más lenta medida (600 s), y
    deja el comando, el intervalo, la espera y los reintentos del chequeo a los del compose base
    (Compose fusiona el chequeo campo por campo)."""
    base = compose["services"]["generation_batch"]["healthcheck"]
    assert _seconds(base["start_period"]) == 120
    assert {"test", "interval", "timeout", "retries"} <= set(base)

    override = _candidate_compose("qwen38-27b")["services"]["generation_batch"]["healthcheck"]
    assert override == {"start_period": "900s"}
    assert _seconds(override["start_period"]) > 600  # la carga más lenta medida: 10 minutos (T-244)

    # el del 35B-A3B no cambia: sigue con los 120 s del base
    assert "healthcheck" not in _candidate_compose("qwen36-35b")["services"]["generation_batch"]
    # el motor de la Consulta y los demás servicios conservan su chequeo
    assert _seconds(compose["services"]["generation"]["healthcheck"]["start_period"]) == 120


def test_the_app_service_mounts_everything_the_anchor_mounts(compose):
    """P7 (T-264, dictamen de la 015, hallazgo 4): `app` repite la lista de volúmenes de `x-app`
    (una lista de YAML no se puede extender) y le suma sus propios montajes. Todo montaje del ancla
    tiene que estar en la lista de `app`: a `app` le faltaba `specs/`, y con el comando documentado
    (`docker compose run --rm app pytest`) el test de cobertura de REQ-106 se salteaba."""
    anchor = compose["x-app"]["volumes"]
    mine = compose["services"]["app"]["volumes"]
    assert [volume for volume in anchor if volume not in mine] == []
    assert "./specs:/app/specs:ro" in mine
    # lo que `app` suma a propósito sigue ahí (corridas de `medir_matriz`, con escritura)
    cases = "./corpus/casos:/app/corpus/casos"
    assert cases in mine and cases not in anchor


# --- T-255 · la Consulta de normativa con el Qwen3.8-27B del motor de lotes (ADR-0057) ---------------
#
# `docker-compose.consulta-27b.yml` reemplaza en la configuración de uso a `docker-compose.sin-consulta.yml`
# (que queda como está: sirve para el 27B sin Consulta si las evals no pasan). `generation` sigue sin
# arrancar y la Consulta (`app`) va a `generation_batch` por variables de entorno.

# Servicios de la imagen de la aplicación que reciben a qué motor va la Consulta.
QUERY_27B_SERVICES = ("app", "worker")


@pytest.fixture(scope="module")
def query_27b():
    assert QUERY_27B_FILE.is_file(), f"No se encuentra {QUERY_27B_FILE}: tiene que estar montado en app"
    return yaml.safe_load(QUERY_27B_FILE.read_text(encoding="utf-8"))


def test_the_query_27b_file_only_points_the_consulta_to_the_batch_engine(query_27b):
    """REQ-107 (T-255, P4): `docker-compose.consulta-27b.yml` pone `generation` en el perfil
    `consulta-12b` (no arranca), hace que `app` no lo espere (`required: false`) y suma variables de
    entorno a `app` y `worker`. No toca redes, puertos, imágenes, volúmenes, comandos ni chequeos de
    ningún servicio: el motor sigue en la red interna, sin salida a internet."""
    assert {key for key in query_27b if not key.startswith("x-")} == {"services"}
    services = query_27b["services"]
    assert set(services) == {"generation", "app", "worker"}
    assert services["generation"] == {"profiles": ["consulta-12b"]}
    assert set(services["app"]) == {"depends_on", "environment"}
    assert services["app"]["depends_on"] == {"generation": {
        "condition": "service_healthy", "required": False}}
    assert set(services["worker"]) == {"environment"}
    # el servicio y su dependencia existen en el compose base, y el base sigue levantando la Consulta
    base = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert base["services"]["app"]["depends_on"]["generation"] == {"condition": "service_healthy"}
    assert "profiles" not in base["services"]["generation"]


def test_the_query_27b_file_points_to_the_batch_engine_and_names_its_model(compose, query_27b):
    """REQ-107 (T-255, P6): `app` y `worker` mandan la Consulta a `GENERATION_BATCH_URL` (de la
    misma variable y con el mismo valor por omisión que `generation_batch`) y registran el modelo
    que carga ese motor: el alias, el archivo y la huella son los de `docker-compose.qwen38-27b.yml`
    y los de `scripts/models.sha256`; el alias es el `--alias` con que arranca el motor."""
    qwen = _candidate_compose("qwen38-27b")
    batch_environment = qwen["services"]["app"]["environment"]
    batch_command = qwen["services"]["generation_batch"]["command"]
    base_environment = compose["services"]["app"]["environment"]
    for service in QUERY_27B_SERVICES:
        environment = query_27b["services"][service]["environment"]
        assert environment["GENERATION_URL"] == "${GENERATION_BATCH_URL:-http://generation_batch:8080}"
        assert resolve(environment["GENERATION_URL"], {}) == resolve(
            base_environment["GENERATION_BATCH_URL"], {})
        assert resolve(environment["GENERATION_URL"], {"GENERATION_BATCH_URL": "http://otro:1"}) == (
            "http://otro:1")
        assert environment["GENERATION_MODEL_ALIAS"] == batch_environment[
            "GENERATION_BATCH_MODEL_ALIAS"] == _argument(batch_command, "--alias")
        assert environment["GENERATION_MODEL_FILE"] == batch_environment["GENERATION_BATCH_MODEL_FILE"]
        assert "/models/" + environment["GENERATION_MODEL_FILE"] == _argument(batch_command, "--model")
        assert environment["GENERATION_MODEL_SHA256"] == batch_environment[
            "GENERATION_BATCH_MODEL_SHA256"]
        assert _checksums()[environment["GENERATION_MODEL_FILE"]] == environment[
            "GENERATION_MODEL_SHA256"]


def test_the_consulta_context_is_the_real_one_of_the_batch_engine_but_only_in_the_app(
        compose, query_27b):
    """REQ-107 (T-255): `app` registra y usa para la Consulta el contexto real del motor de lotes
    (`--ctx-size` de `generation_batch`, de la misma variable y con el mismo valor por omisión:
    32.768). El `worker` NO lo recibe: la matriz (consecuencias y circulares) dimensiona sus pedidos
    con `GENERATION_CONTEXT_TOKENS`, y con 32.768 en lugar de 16.384 propondría otra matriz que la
    medida (P7)."""
    batch_context = _argument(compose["services"]["generation_batch"]["command"], "--ctx-size")
    app_environment = query_27b["services"]["app"]["environment"]
    assert app_environment["GENERATION_CTX_SIZE"] == batch_context == "${GENERATION_BATCH_CTX_SIZE:-32768}"
    assert resolve(app_environment["GENERATION_CTX_SIZE"], {}) == "32768"
    assert resolve(app_environment["GENERATION_CTX_SIZE"], {"GENERATION_BATCH_CTX_SIZE": "24576"}) == "24576"
    assert "GENERATION_CTX_SIZE" not in query_27b["services"]["worker"]["environment"]


def _merged_environment(compose, service, files):
    """El `environment` de `service` al sumar `files` en orden, como lo arma Compose (cada archivo
    pisa por clave), con las interpolaciones resueltas sin variables de entorno."""
    environment = {}
    for name in files:
        data = compose if name == "docker-compose.yml" else yaml.safe_load(
            (REPO / name).read_text(encoding="utf-8"))
        environment.update(((data.get("services") or {}).get(service) or {}).get("environment") or {})
    return {key: resolve(value, {}) for key, value in environment.items()}


def _settings_with(monkeypatch, environment):
    """`settings.py` evaluado con las variables de IA de `environment` (y solo esas)."""
    for name, value in environment.items():
        if name.startswith(("GENERATION_", "EMBEDDINGS_", "RERANKER_")):
            monkeypatch.setenv(name, value)
    return runpy.run_path(str(REPO / "evaluon" / "settings.py"))


def test_with_the_default_files_the_app_sends_the_consulta_to_the_27b_of_the_batch_engine(
        compose, monkeypatch):
    """REQ-107 (T-255, P6): con los cuatro archivos de `.env.example`, lo que ve la aplicación es
    un solo motor: `GENERATION_URL` es `GENERATION_BATCH_URL`, el modelo de la Consulta (alias,
    archivo y huella) es el del motor de lotes y su contexto es el real, 32.768. Por eso el registro
    de cada consulta nombra el modelo y el motor que la atendieron."""
    fresh = _settings_with(monkeypatch, _merged_environment(compose, "app", DEFAULT_FILES))

    assert fresh["GENERATION_URL"] == fresh["GENERATION_BATCH_URL"] == "http://generation_batch:8080"
    assert fresh["GENERATION_MODEL"] == fresh["GENERATION_BATCH_MODEL"] == "qwen3.8-27b-ud-q4_k_m"
    assert fresh["GENERATION_MODEL_FILE"] == fresh["GENERATION_BATCH_MODEL_FILE"]
    assert fresh["GENERATION_MODEL_SHA256"] == fresh["GENERATION_BATCH_MODEL_SHA256"]
    assert fresh["GENERATION_CONTEXT_TOKENS"] == fresh["GENERATION_BATCH_CONTEXT_TOKENS"] == 32768
    # y el razonamiento sigue siendo cosa de los pasos de lotes: la Consulta no lo pide (T-253)
    assert fresh["GENERATION_THINKING"] is False


def test_with_the_default_files_the_worker_keeps_the_matrix_context(compose, monkeypatch):
    """REQ-107 (T-255, P7): el `worker` apunta la Consulta al motor del 27B pero conserva el
    contexto de 16.384 con que se midió la matriz."""
    fresh = _settings_with(monkeypatch, _merged_environment(compose, "worker", DEFAULT_FILES))

    assert fresh["GENERATION_URL"] == fresh["GENERATION_BATCH_URL"]
    assert fresh["GENERATION_MODEL"] == fresh["GENERATION_BATCH_MODEL"] == "qwen3.8-27b-ud-q4_k_m"
    assert fresh["GENERATION_CONTEXT_TOKENS"] == 16384
    assert fresh["GENERATION_BATCH_CONTEXT_TOKENS"] == 32768


def test_without_the_query_27b_file_the_consulta_stays_where_it_was(compose, monkeypatch):
    """REQ-107 (T-255): con el 27B sin Consulta (`docker-compose.sin-consulta.yml`) o con el 12B de
    siempre (sin ninguno de los dos) la Consulta sigue apuntando a `generation` con el modelo y el
    contexto de la 001: la vuelta al 12B no cambia."""
    for files in ((*DEFAULT_FILES[:3], "docker-compose.sin-consulta.yml"), DEFAULT_FILES[:1]):
        environment = _merged_environment(compose, "app", files)
        for name in ("GENERATION_URL", "GENERATION_MODEL_ALIAS", "GENERATION_MODEL_FILE",
                     "GENERATION_MODEL_SHA256", "GENERATION_CTX_SIZE"):
            monkeypatch.delenv(name, raising=False)  # cada caso parte del entorno por omisión
        fresh = _settings_with(monkeypatch, environment)

        assert fresh["GENERATION_URL"] == "http://generation:8080", files
        assert fresh["GENERATION_MODEL"] == "gemma-4-12b-it-qat-q4_0", files
        assert fresh["GENERATION_CONTEXT_TOKENS"] == 16384, files


def test_the_consulta_request_waits_less_than_gunicorn(compose):
    """REQ-107 (T-255, ADR-0005): la Consulta es interactiva. Gunicorn corta a los 120 s (espera de
    `app` en el compose); el pedido al modelo espera `AI_TIMEOUT_SECONDS`, que tiene que ser
    menor: una generación colgada termina en una falla técnica `timeout` con su registro, y no
    con el proceso cortado a mitad de la consulta sin registro. El 27B es más lento que el 12B
    (24 tokens por segundo contra unos 70), así que el margen importa."""
    command = [str(item) for item in compose["services"]["app"]["command"]]
    gunicorn_timeout = int(command[command.index("--timeout") + 1])

    assert gunicorn_timeout == 120
    assert settings.AI_TIMEOUT_SECONDS < gunicorn_timeout
