"""Fixtures de la feature 012 (T-138): un portal de mentira y usuarios de prueba.

`FakePortal` es el transporte de `PortalClient`: responde con contenido inventado según un
guion y anota cada solicitud. Nunca abre una conexión (P4). El host es inventado.
"""

import itertools
from datetime import date

import pytest

from evaluon.portal.client import PortalClient, Response
from evaluon.tenders import models as tenders

ALLOWED = "portal.ejemplo.test"
_counter = itertools.count(1)


class FakePortal:
    """Transporte de prueba: `routes` es `{(método, url): Response o función}`."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        route = self.routes.get((request.method, request.url))
        if route is None:
            return Response(request.url, 404, {}, b"no existe")
        return route(request) if callable(route) else route


def reply(url, body=b"", status=200, **headers):
    return Response(url, status, {k.lower().replace("_", "-"): v for k, v in headers.items()}, body)


@pytest.fixture
def fake_portal():
    return FakePortal()


@pytest.fixture
def make_client(fake_portal):
    """Cliente con la lista `[ALLOWED]`, sin pausa y con el portal de mentira."""

    def make(**kwargs):
        options = {
            "transport": fake_portal, "allowed_hosts": [ALLOWED], "pause": 0,
            "timeout": 5, "max_bytes": 1000,
        }
        options.update(kwargs)
        return PortalClient(**options)

    return make


@pytest.fixture
def procedure(read_write_user):
    return tenders.Procedure.objects.create(
        number=f"PROC-PORTAL-{next(_counter)}",
        procedure_type="Licitación pública",
        subject="Objeto sintético",
        authorization_date=date(2025, 11, 14),
        created_by=read_write_user,
    )
