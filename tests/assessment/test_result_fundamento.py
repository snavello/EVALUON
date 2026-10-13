"""Pantalla de la 004: el dato del Portal que fundamenta un resultado trae su enlace y la fecha en
que se tomó (REQ-103; P3, constitución 1.3, ADR-0053; dictamen de la 015, hallazgo 1; plan 015,
T-264). La fecha es la de la página del Portal de la que sale el ítem (`PortalPage.fetched_at`),
con el formato de las pantallas del Portal. Datos inventados (P4); el modelo es un guion y no hay
red."""

from datetime import UTC, datetime

import pytest
from django.urls import reverse

from evaluon.portal import models as pm
from tests.assessment.fakes import model  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import requirement_of, results_of, run_all
from tests.assessment.test_portal_facts import GUARANTEE, portal_data
from tests.offers.test_screens import log_in

pytestmark = pytest.mark.django_db

# La página del Portal se consultó el 9/10/2026 a las 17:30 UTC: 14:30 en Buenos Aires.
FETCHED = datetime(2026, 10, 9, 17, 30, tzinfo=UTC)
SHOWN = "09/10/2026 14:30"
PAGE_URL = "https://portal.invalid/acta-de-apertura"
FILE_NAME = "acta-de-apertura.pdf"


def make_portal_item(procedure, user, *, with_file=False):
    """Un ítem de oferta del Portal, de una página consultada en `FETCHED`; con `with_file`, también
    su archivo (otra consulta, unos minutos después)."""
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="acta", url=PAGE_URL,
                                        fetched_at=FETCHED, sha256="a" * 64, content=b"x")
    stored = None
    if with_file:
        stored = pm.PortalFile.objects.create(
            link=link, exploration=1, url="https://portal.invalid/acta.pdf", file_name=FILE_NAME,
            file_format="pdf", sha256="c" * 64, content=b"%PDF-sintetico",
            fetched_at=datetime(2026, 10, 9, 17, 45, tzinfo=UTC), page=page)
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1, origin="importacion")
    return pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o", payload={},
                                        content_sha256="b" * 64, page=page, file=stored)


@pytest.fixture
def portal(procedure, operator_user):
    return make_portal_item(procedure, operator_user)


@pytest.fixture
def portal_with_file(procedure, operator_user):
    return make_portal_item(procedure, operator_user, with_file=True)


def portal_cumple(item, offer, user, procedure):
    """Un «cumple» cuyo único fundamento es el dato del Portal (la garantía de mantenimiento);
    devuelve el requisito."""
    portal_data(item, offer)
    _, runs = run_all(user, procedure)
    requirement = requirement_of(procedure, GUARANTEE)
    result = results_of(runs[0])[requirement.number]
    assert (result.outcome, result.doubt) == ("cumple", "")
    assert [c.kind for c in result.citations.filter(kind__in=["oferta", "portal"])] == ["portal"]
    return requirement


def test_the_result_page_gives_the_portal_page_and_the_date_the_datum_was_taken(
        offer, operator_user, procedure, model, portal, client):
    """REQ-103, REQ-104, P3: el «cumple» que sale del dato del Portal muestra el enlace a la página
    del Portal y la fecha en que se tomó el dato, en hora de Buenos Aires y con el formato de las
    pantallas del Portal; sin archivo, no ofrece ninguno."""
    requirement = portal_cumple(portal, offer, operator_user, procedure)
    log_in(client, operator_user)
    html = client.get(reverse("assessment:pair", args=[offer.pk, requirement.pk])
                      ).content.decode()
    assert "Garantía: tipo Garantía de mantenimiento de oferta" in html
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in html
    assert f"página consultada el {SHOWN}" in html
    assert "archivo del Portal" not in html


def test_the_result_page_gives_the_portal_file_when_the_item_has_one(
        offer, operator_user, procedure, model, portal_with_file, client):
    """REQ-103, REQ-104, P3: si el ítem del Portal tiene archivo, la pantalla suma el enlace al
    archivo."""
    requirement = portal_cumple(portal_with_file, offer, operator_user, procedure)
    log_in(client, operator_user)
    html = client.get(reverse("assessment:pair", args=[offer.pk, requirement.pk])
                      ).content.decode()
    link = portal_with_file.proposal.link_id
    download = reverse("portal:download", args=[link, portal_with_file.file_id])
    assert f'<a href="{download}">archivo del Portal</a>' in html
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in html
    assert f"página consultada el {SHOWN}" in html
