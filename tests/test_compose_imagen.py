"""Una imagen de la aplicación por proyecto de Compose (T-369; REQ-174, REQ-175; spec 021).

El piloto y las copias de trabajo construían la aplicación con el mismo nombre de imagen
(`evaluon-app:local`): una construcción desde una copia pisaba la imagen del piloto
(`specs/020-evi-guia-del-procedimiento/runbook.md`, «Fallas conocidas»). Desde la 021 el nombre
se arma con el nombre del proyecto de Compose, con `evaluon` por omisión: el piloto (proyecto
`evaluon`) sigue resolviendo `evaluon-app:local` y un proyecto `evaluon-t367` resuelve
`evaluon-t367-app:local`.

Estas pruebas leen los archivos de Compose de la raíz del repositorio, sin Docker ni base:

- `docker-compose.yml`: `x-app` y los servicios `app`, `migrate`, `worker` y `portal_worker`
  arman el nombre con el proyecto, y ninguno vuelve a fijar un nombre único (REQ-174);
- `docker-compose.clon.yml` y `docker-compose.demo.yml`: siguen usando, a propósito, la imagen
  ya construida del piloto, sin reconstruirla (REQ-175). `docker-compose.yml` no monta esos dos
  archivos en el contenedor: como en `test_clon_compose.py`, esas pruebas se saltan si no están
  (para correrlas, montarlos con `-v`).

No hay datos: solo configuración (P4).
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
BASE_COMPOSE = ROOT / "docker-compose.yml"
CLON_COMPOSE = ROOT / "docker-compose.clon.yml"
DEMO_COMPOSE = ROOT / "docker-compose.demo.yml"

PILOT_PROJECT = "evaluon"
PILOT_IMAGE = "evaluon-app:local"
EXPECTED_IMAGE = "${COMPOSE_PROJECT_NAME:-evaluon}-app:local"
APP_SERVICES = ("app", "migrate", "worker", "portal_worker")

# `${VARIABLE:-valor por omisión}`, la única forma de interpolación que se espera en el nombre.
_WITH_DEFAULT = re.compile(r"\$\{(?P<name>[A-Z_][A-Z0-9_]*):-(?P<default>[^}]*)\}")


def needs(*paths):
    """Salta la prueba si alguno de los archivos no está montado en este entorno."""
    missing = [p.name for p in paths if not p.is_file()]
    return pytest.mark.skipif(bool(missing), reason=f"no está montado: {', '.join(missing)}")


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resolve(image, env):
    """Interpola `${VAR:-omisión}` como Compose: vale la omisión si falta o está vacía."""
    return _WITH_DEFAULT.sub(lambda m: env.get(m["name"]) or m["default"], image)


@pytest.fixture(scope="module")
def base():
    assert BASE_COMPOSE.is_file(), f"No se encuentra {BASE_COMPOSE}: tiene que estar montado en app"
    return _load(BASE_COMPOSE)


def test_x_app_names_the_image_after_the_project(base):
    """REQ-174: el nombre de la imagen de `x-app` sale del proyecto, con `evaluon` por omisión."""
    assert base["x-app"]["image"] == EXPECTED_IMAGE, (
        "x-app tiene que armar la imagen con el nombre del proyecto de Compose: un nombre "
        "único hace que una copia de trabajo pise la imagen del piloto"
    )


@pytest.mark.parametrize("service", APP_SERVICES)
def test_app_services_do_not_pin_a_shared_image(base, service):
    """REQ-174: ningún servicio de la aplicación fija un nombre de imagen único para todos."""
    image = base["services"][service]["image"]
    assert image == EXPECTED_IMAGE, f"{service} no usa la imagen de x-app: {image}"
    assert "COMPOSE_PROJECT_NAME" in image
    assert _resolve(image, {"COMPOSE_PROJECT_NAME": "evaluon-t367"}) != PILOT_IMAGE


def test_no_other_service_uses_the_pilot_image_name(base):
    """REQ-174: fuera de los servicios de la aplicación, nadie construye ni usa esa imagen."""
    others = {
        name: service.get("image", "")
        for name, service in base["services"].items()
        if name not in APP_SERVICES
    }
    assert not {n: i for n, i in others.items() if "-app:" in i or "build" in base["services"][n]}


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"COMPOSE_PROJECT_NAME": PILOT_PROJECT}, PILOT_IMAGE),
        ({}, PILOT_IMAGE),
        ({"COMPOSE_PROJECT_NAME": ""}, PILOT_IMAGE),
        ({"COMPOSE_PROJECT_NAME": "evaluon-t367"}, "evaluon-t367-app:local"),
        ({"COMPOSE_PROJECT_NAME": "evaluon-ver369"}, "evaluon-ver369-app:local"),
    ],
)
def test_image_name_per_project(base, env, expected):
    """REQ-174: el piloto conserva `evaluon-app:local`; otro proyecto resuelve un nombre propio."""
    assert _resolve(base["x-app"]["image"], env) == expected


def test_base_project_name_is_the_pilot(base):
    """REQ-174: sin `-p`, el proyecto de `docker-compose.yml` es el del piloto y resuelve su imagen."""
    assert base["name"] == PILOT_PROJECT
    assert _resolve(base["x-app"]["image"], {"COMPOSE_PROJECT_NAME": base["name"]}) == PILOT_IMAGE


@pytest.mark.parametrize(
    "path, anchor",
    [
        pytest.param(CLON_COMPOSE, "x-clon-app", marks=needs(CLON_COMPOSE), id="clon"),
        pytest.param(DEMO_COMPOSE, "x-demo-app", marks=needs(DEMO_COMPOSE), id="demo"),
    ],
)
def test_clone_and_demo_keep_the_pilot_image(path, anchor):
    """REQ-175: el clon y la demo siguen usando la imagen ya construida del piloto, sin construirla."""
    data = _load(path)
    assert data["name"] != PILOT_PROJECT
    assert data[anchor]["image"] == PILOT_IMAGE
    assert data[anchor]["pull_policy"] == "never"
    app_services = {n: s for n, s in data["services"].items() if "-app:" in s.get("image", "")}
    assert app_services, f"{path.name} no tiene servicios de la aplicación"
    for name, service in app_services.items():
        assert service["image"] == PILOT_IMAGE, f"{name} cambió de imagen: {service['image']}"
        assert "build" not in service, f"{name} no tiene que reconstruir la imagen del piloto"
