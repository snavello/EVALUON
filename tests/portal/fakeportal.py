"""Portal de mentira para las pruebas de la importación (T-141): sirve el calco de
`tests/portal/data/portal-chico/` (datos inventados, P4) por un transporte falso. Nunca abre
una conexión.

Fixtures para importar en los tests:

- `portal_settings`: la lista de destinos de la aplicación apunta al host inventado.
- `fake_portal_calco`: el `FakePortal` con la página del proceso; `serve(name)` cambia qué
  versión del calco responde.
- `portal_client`: reemplaza el cliente de la exploración por uno con ese transporte.
- `explore_link`: registra un enlace y atiende el pedido, como lo haría `portal_worker`.
"""

from pathlib import Path

import pytest
import yaml
from django.conf import settings as django_settings

from evaluon.portal.client import PortalClient
from evaluon.portal.services import explore, links
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS
from tests.portal.conftest import ALLOWED, FakePortal, reply

DATA = Path(django_settings.BASE_DIR) / "tests" / "portal" / "data" / "portal-chico"
LINK_URL = f"https://{ALLOWED}/PLIEGO/VistaPreviaPliegoCiudadano.aspx?qs=ENLACE-INVENTADO"
EXPECTED = yaml.safe_load((DATA / "portal-esperado.yaml").read_text(encoding="utf-8"))


class Calco(FakePortal):
    """El portal de mentira con el calco: `serve(archivo)` elige la página del proceso."""

    def serve(self, name, status=200):
        body = (DATA / name).read_bytes()
        self.routes[("GET", LINK_URL)] = reply(LINK_URL, body, status=status)


@pytest.fixture
def portal_settings(settings):
    settings.PORTAL_ALLOWED_HOSTS = [ALLOWED]
    return settings


@pytest.fixture
def fake_portal_calco(portal_settings):
    portal = Calco()
    portal.serve("proceso.html")
    return portal


@pytest.fixture
def portal_client(monkeypatch, fake_portal_calco):
    def make():
        return PortalClient(transport=fake_portal_calco, allowed_hosts=[ALLOWED], pause=0,
                            timeout=5, max_bytes=5_000_000)

    monkeypatch.setattr(explore, "new_client", make)
    return fake_portal_calco


@pytest.fixture
def explore_link(portal_client):
    """`explore_link(user, url=LINK_URL)`: registra el enlace y atiende su pedido."""

    def run(user, url=LINK_URL):
        link = links.register_link(user, url)
        job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
        link.refresh_from_db()
        return link, job

    return run
