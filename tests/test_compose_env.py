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
