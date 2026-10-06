"""Red del servicio del Portal (T-138; plan 012, "Red y conexión"; ADR-0031).

Lee `docker-compose.yml` y comprueba la regla que sostiene a P4: solo `portal_worker` tiene
salida a internet; el `worker` que lee pliegos y ofertas, la aplicación, la base y los
servicios de IA siguen sin ella.
"""

from pathlib import Path

import pytest
import yaml
from django.conf import settings

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"


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
