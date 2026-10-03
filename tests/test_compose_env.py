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
from pathlib import Path

import pytest
import yaml
from django.conf import settings

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"

AI_SERVICES = ("generation", "embeddings", "reranker")

# Variables de modelo que usan los servicios y que la aplicación tiene que recibir igual.
SHARED_VARIABLES = (
    "GENERATION_MODEL_ALIAS",
    "GENERATION_MODEL_FILE",
    "GENERATION_CTX_SIZE",
    "EMBEDDINGS_MODEL_ALIAS",
    "EMBEDDINGS_MODEL_FILE",
    "RERANKER_MODEL_ALIAS",
    "RERANKER_MODEL_FILE",
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
INTERPOLATION = re.compile(r"\$\{(?P<name>\w+)(?P<op>:?-)(?P<default>[^}]*)\}")

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

    return INTERPOLATION.sub(replace, str(text))


def service_defaults(compose):
    """Valor por omisión de cada variable en los `command` de los servicios de IA. Una
    variable que aparece con dos valores por omisión distintos es un error del compose."""
    defaults = {}
    for service in AI_SERVICES:
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
    # Direcciones y huellas: el nombre en settings.py es el de la variable.
    for name in APP_ONLY_VARIABLES:
        assert fresh[name] == resolve(app_environment[name], no_env), name


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
