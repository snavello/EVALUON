"""Red del servicio del Portal (T-138; plan 012, "Red y conexión"; ADR-0031).

Lee `docker-compose.yml` y comprueba la regla que sostiene a P4: solo `portal_worker` tiene
salida a internet; el `worker` que lee pliegos y ofertas, la aplicación, la base y los
servicios de IA siguen sin ella.

T-289 (REQ-122, ADR-0066): la salida a internet del uso externo es `docker-compose.externo.yml`,
que se usa solo junto con `docker-compose.clon.yml` y le da `egress` únicamente a `clon_worker` y
`clon_app`. Esas pruebas se saltan si los dos archivos no están montados en el contenedor (como
las de `tests/test_clon_compose.py`).
"""

from pathlib import Path

import pytest
import yaml
from django.conf import settings

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"
CLON_FILE = Path(settings.BASE_DIR) / "docker-compose.clon.yml"
EXTERNAL_FILE = Path(settings.BASE_DIR) / "docker-compose.externo.yml"
EXTERNAL_SERVICES = {"clon_worker", "clon_app"}

needs_external_files = pytest.mark.skipif(
    not (CLON_FILE.is_file() and EXTERNAL_FILE.is_file()),
    reason="docker-compose.clon.yml y docker-compose.externo.yml no están montados")


@pytest.fixture(scope="module")
def compose():
    assert COMPOSE_FILE.is_file(), f"No se encuentra {COMPOSE_FILE}"
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def networks_of(compose, service):
    networks = compose["services"][service].get("networks", [])
    return set(networks if isinstance(networks, list) else networks.keys())


def test_only_portal_worker_uses_egress(compose):
    """REQ-045: de todos los servicios, solo `portal_worker` está en la red `egress`."""
    assert "egress" in compose["networks"]
    using = {name for name in compose["services"] if "egress" in networks_of(compose, name)}
    assert using == {"portal_worker"}


def test_internal_network_stays_internal(compose):
    """REQ-045, P4: la red `internal` sigue sin salida, y `egress` es la única otra red
    que no es solo de publicación de puertos (`web` es la de `app`)."""
    assert compose["networks"]["internal"] == {"internal": True}
    assert not (compose["networks"]["egress"] or {}).get("internal", False)


def test_portal_worker_reaches_the_database_but_not_the_ai(compose):
    """ADR-0031: `portal_worker` está en `internal` (base) y en `egress`; no depende de
    los servicios de IA ni usa la GPU."""
    service = compose["services"]["portal_worker"]
    assert networks_of(compose, "portal_worker") == {"internal", "egress"}
    assert service["command"] == ["python", "manage.py", "procesar_portal"]
    assert set(service["depends_on"]) == {"db", "migrate"}
    assert "deploy" not in service
    assert service["image"] == compose["services"]["worker"]["image"]


def test_worker_and_app_cannot_reach_the_internet(compose):
    """P4: el servicio que lee pliegos y ofertas (`worker`) y los demás no están en
    `egress`; la base y la IA quedan solo en `internal`."""
    for name in ("worker", "db", "generation", "generation_batch", "embeddings",
                 "reranker", "migrate"):
        assert networks_of(compose, name) == {"internal"}, name
    assert networks_of(compose, "app") == {"internal", "web"}


def merged_clon(clon, external):
    """Las redes de cada servicio del clon con el archivo externo encima, como las une
    `docker compose -f clon -f externo` (las listas de redes se suman)."""
    merged = {name: networks_of(clon, name) for name in clon["services"]}
    for name, service in external["services"].items():
        merged[name] = merged.get(name, set()) | networks_of(external, name)
    return merged


def test_the_base_compose_never_mentions_the_external_key(compose):
    """REQ-122, P4: el compose base no pasa la clave del proveedor a ningún servicio."""
    assert "ANTHROPIC_API_KEY" not in COMPOSE_FILE.read_text(encoding="utf-8")


@needs_external_files
def test_the_clon_alone_has_no_egress():
    """REQ-122, P4: sin `docker-compose.externo.yml` el clon no tiene ruta a internet por
    `egress`: ningún servicio del clon está en esa red."""
    clon = yaml.safe_load(CLON_FILE.read_text(encoding="utf-8"))
    assert "egress" not in (clon.get("networks") or {})
    assert all("egress" not in networks_of(clon, name) for name in clon["services"])


@needs_external_files
def test_with_the_external_file_egress_reaches_only_the_clon_worker_and_app():
    """REQ-122, P4, ADR-0066 punto 6: con el clon más el archivo externo, la red `egress`
    llega solo a `clon_worker` y `clon_app`; la base, la migración y el motor del clon no."""
    clon = yaml.safe_load(CLON_FILE.read_text(encoding="utf-8"))
    external = yaml.safe_load(EXTERNAL_FILE.read_text(encoding="utf-8"))
    assert "egress" in external["networks"]
    assert not (external["networks"]["egress"] or {}).get("internal", False)
    merged = merged_clon(clon, external)
    assert {name for name, networks in merged.items() if "egress" in networks}         == EXTERNAL_SERVICES
    assert set(external["services"]) == EXTERNAL_SERVICES
    for name in ("clon_db", "clon_migrate", "clon_generation_batch"):
        assert "egress" not in merged[name], name
    # Lo que ya tenían no se pierde: la base y los servicios compartidos siguen alcanzables.
    assert {"clon_internal", "evaluon_internal"} <= merged["clon_worker"]
    assert {"clon_internal", "evaluon_internal", "clon_web"} <= merged["clon_app"]


@needs_external_files
def test_the_external_file_adds_only_egress_and_the_key():
    """REQ-122, P4: de cada servicio solo toca las redes y la variable de la clave, y la clave
    se pide del `--env-file` sin ningún valor escrito en el archivo."""
    external = yaml.safe_load(EXTERNAL_FILE.read_text(encoding="utf-8"))
    for name, service in external["services"].items():
        assert set(service) == {"environment", "networks"}, name
        assert service["networks"] == ["egress"], name
        assert set(service["environment"]) == {"ANTHROPIC_API_KEY"}, name
        value = service["environment"]["ANTHROPIC_API_KEY"]
        assert value.startswith("${ANTHROPIC_API_KEY:?") and value.endswith("}"), name
    assert "sk-ant" not in EXTERNAL_FILE.read_text(encoding="utf-8")
