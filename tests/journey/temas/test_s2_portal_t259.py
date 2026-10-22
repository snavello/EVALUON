"""Documentos que el Portal lista y no se pueden bajar, como faltantes de la portada (REQ-104;
T-259; informe del comité H7). El Pliego de Bases y Condiciones Generales y su Disposición
Aprobatoria nunca bajan: el Portal responde su pantalla de error (en los casos 00 y 05). La
exploración lo deja como anomalía; la portada tiene que contarlo como documento faltante, con
su aviso, hasta que se suba a mano. Todo el material es inventado (P4)."""

import datetime
import itertools

import pytest
from django.urls import reverse

from evaluon.journey.temas import s2_documentos
from evaluon.portal import models as p
from evaluon.tenders.models import Document, Procedure
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

GENERAL = "Pliego de Bases y Condiciones Generales"
DISPOSITION = "Disposición Aprobatoria del pliego general"
ERROR_SCREEN = ("El Portal respondió su pantalla de error en lugar del documento. Queda la "
                "carga manual.")
_n = itertools.count(1)


@pytest.fixture
def procedure(operator_user):
    return Procedure.objects.create(
        number=f"T259-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


@pytest.fixture
def explored(procedure, operator_user):
    link = p.PortalLink.objects.create(
        url=f"https://portal.ejemplo.test/x.aspx?qs={next(_n)}", procedure=procedure,
        created_by=operator_user)
    p.PortalProposal.objects.create(
        link=link, exploration=1, origin=p.Origin.IMPORTACION, anomalies=[
            {"parte": f"documento «{GENERAL}»", "motivo": ERROR_SCREEN},
            {"parte": f"documento «{DISPOSITION}»", "motivo": ERROR_SCREEN},
            {"parte": "renglones", "motivo": "la tabla de renglones no tiene filas"},
        ])
    return link


def texts(procedure, user):
    return [m.text for m in s2_documentos.status(user, procedure).missing]


def test_documents_the_portal_could_not_serve_are_missing_with_their_reason(
        procedure, explored, operator_user):
    """REQ-104 (T-259, H7; T-338): el Pliego general y su Disposición, que no bajaron, figuran como
    un solo faltante que los nombra; el motivo de cada uno va en el detalle de los documentos
    (`test_s2_t338`), no en la línea; una anomalía que no es de un documento no figura."""
    missing = texts(procedure, operator_user)
    assert len(missing) == 1
    assert GENERAL in missing[0] and DISPOSITION in missing[0]
    assert "no se pudieron bajar" in missing[0] and "pantalla de error" not in missing[0]
    assert not any("renglones" in t for t in missing)


def test_the_cover_shows_them_under_what_is_missing(client, procedure, explored, operator_user):
    """REQ-104 (T-259, H7): la sección los cuenta en «Falta» de «Pliego y matriz», no
    «Nada»."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    assert GENERAL in html and "no se pudo bajar" in html


def test_once_uploaded_by_hand_it_is_no_longer_missing(procedure, explored, operator_user):
    """REQ-104 (T-259): subido a mano un documento con ese título, deja de faltar; la
    Disposición, que sigue sin subir, sigue en la lista."""
    Document.objects.create(
        procedure=procedure, kind="anexo", title=GENERAL, file_name="pliego-general.pdf",
        file_format="pdf", file_size=10, file_sha256=f"{next(_n):064x}",
        loaded_by=operator_user)
    missing = texts(procedure, operator_user)
    assert not any(GENERAL in t for t in missing)
    assert any(DISPOSITION in t and "1 documento" in t for t in missing)
