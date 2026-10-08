"""Tema «datos del procedimiento» de la sección Procedimiento (REQ-078, REQ-097; plan 014,
T-194). Todo el material es inventado (P4)."""

import datetime
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.journey.temas import s1_datos
from evaluon.offers.models import Offer
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    PortalItem,
    PortalLine,
    PortalOfferData,
    PortalProcedureData,
)
from evaluon.portal.services import approval
from evaluon.tenders.models import Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.portal.fakeportal import (  # noqa: F401
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)

pytestmark = pytest.mark.django_db

DATE = datetime.date(2025, 11, 14)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def page(client, procedure):
    return client.get(reverse("expedientes:procedimiento", args=[procedure.pk]))


@pytest.fixture
def from_portal(evaluator_user, explore_link, two_regimes):
    """Un procedimiento cargado desde el Portal de mentira, con sus renglones y su oferta."""
    link, _ = explore_link(evaluator_user)
    procedure_item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    lines_item = PortalItem.objects.get(kind=ItemKind.RENGLONES)
    approval.decide(evaluator_user, [procedure_item.pk, lines_item.pk], approval.APPROVE,
                    confirmations={procedure_item.pk: {"authorization_date": DATE}})
    procedure = Procedure.objects.get()
    offer = Offer.objects.create(procedure=procedure, number=1, bidder="Oferente Sintético S.A.",
                                 created_by=evaluator_user)
    PortalOfferData.objects.create(offer=offer, cuit="30-00000001-0", item=procedure_item)
    return procedure


@pytest.fixture
def by_hand(procedure, two_regimes):
    """El caso chico, cargado a mano, sin nada del Portal."""
    Procedure.objects.filter(pk=procedure.pk).update(authorization_date=datetime.date(2023, 3, 1))
    procedure.refresh_from_db()
    return procedure


def test_a_portal_procedure_shows_every_data_with_the_portal_as_origin(
        client, evaluator_user, from_portal):
    """REQ-078: número, expediente, tipo, objeto y fecha, cada uno con el Portal como origen
    y la hora de la exploración en hora local; los renglones con su cantidad."""
    log_in(client, evaluator_user)
    html = page(client, from_portal).content.decode()
    data = PortalProcedureData.objects.get()
    for text in (from_portal.number, data.file_number, from_portal.procedure_type,
                 from_portal.subject, "14/11/2025"):
        assert text in html
    block = html[html.index('id="s1-datos"'):html.index('id="s1-renglones"')]
    assert len(re.findall(r"<b>Portal</b>", block)) >= 6  # datos + expediente + encuadre
    moment = timezone.localtime(data.item.proposal.created_at)
    assert f"{moment:%d/%m %H:%M}" in html
    lines = PortalLine.objects.order_by("number")
    assert lines.count() >= 1
    for line in lines:
        assert line.description in html
    assert "Archivo</b>" not in html and "A mano</b>" not in html


def test_the_authorization_date_fixes_the_regime(client, evaluator_user, from_portal):
    """REQ-078: la fecha de autorización fija el régimen: 2025 rige la Disp. 247/2022."""
    log_in(client, evaluator_user)
    html = page(client, from_portal).content.decode()
    assert "Disposición AFIP 247/2022" in html and "297/03" not in html
    assert "Calculado" in html


def test_an_old_date_shows_the_other_regime(client, operator_user, by_hand):
    """REQ-078: una fecha anterior al 2023 muestra la Disp. 297/03."""
    Procedure.objects.filter(pk=by_hand.pk).update(authorization_date=datetime.date(2022, 6, 1))
    log_in(client, operator_user)
    html = page(client, by_hand).content.decode()
    assert "Disposición AFIP 297/03" in html and "247/2022" not in html


def test_a_hand_loaded_procedure_says_so_and_shows_what_is_missing(
        client, operator_user, by_hand):
    """REQ-078, REQ-097: cargado a mano, el origen es «A mano» con quién y cuándo; sin
    renglones, expediente ni cronograma, dice lo que falta y no inventa datos."""
    log_in(client, operator_user)
    html = page(client, by_hand).content.decode()
    assert "<b>A mano</b>" in html and "<b>Portal</b>" not in html
    assert timezone.localtime(by_hand.created_at).strftime("%d/%m %H:%M") in html
    assert "Todavía no hay renglones cargados." in html
    assert "Falta el expediente, el cronograma y las garantías" in html
    assert "Tomar del Portal" in html
    status = s1_datos.status(operator_user, by_hand)
    assert [m.text for m in status.missing] == [
        "Falta el expediente, el cronograma y las garantías",
        "Faltan los renglones con su cantidad"]
    assert status.pending == 0 and "A mano" in status.sources[0]


def test_a_document_origin_names_the_file(client, operator_user, by_hand):
    """REQ-078: si el dato salió de un pliego subido, el origen nombra el archivo."""
    document = by_hand.documents.first()
    PortalProcedureData.objects.create(procedure=by_hand, file_number="EX-SINT-1",
                                       schedule={"Apertura de ofertas": "22/09/2026 11:00"},
                                       guarantees=["Garantía de oferta 5 %"], document=document)
    PortalLine.objects.create(procedure=by_hand, number=1, description="Renglón sintético",
                              quantity=1200, unit="u.", document=document)
    log_in(client, operator_user)
    html = page(client, by_hand).content.decode()
    assert f"<b>Archivo</b> · {document.file_name}" in html
    assert "EX-SINT-1" in html and "22/09/2026 11:00" in html and "1.200 u." in html
    assert "Garantía de oferta 5 %" in html
    assert s1_datos.status(operator_user, by_hand).missing == ()


def test_a_missing_opening_is_reported(operator_user, by_hand):
    """REQ-078: con datos del Portal pero sin fecha de apertura, lo dice."""
    document = by_hand.documents.first()
    PortalProcedureData.objects.create(procedure=by_hand, file_number="EX-SINT-1",
                                       schedule={"Publicación": "20/08/2026"}, document=document)
    PortalLine.objects.create(procedure=by_hand, number=1, description="x", quantity=1,
                              document=document)
    texts = [m.text for m in s1_datos.status(operator_user, by_hand).missing]
    assert texts == ["Falta la fecha de apertura de ofertas"]


def test_the_offers_of_the_record_show_their_origin(client, evaluator_user, from_portal):
    """REQ-078: las ofertas del acta, con su CUIT y su origen."""
    log_in(client, evaluator_user)
    html = page(client, from_portal).content.decode()
    assert "Oferente Sintético S.A." in html and "30-00000001-0" in html
    assert 'id="s1-ofertas"' in html


def test_the_tab_has_no_links_to_old_screens_besides_the_portal_one(
        client, evaluator_user, from_portal):
    """REQ-097: el único enlace a una pantalla vieja es el del proceso del Portal (012)."""
    log_in(client, evaluator_user)
    html = page(client, from_portal).content.decode()
    block = html[html.index('id="s1-datos"'):html.index('id="s1-ofertas"')]
    hrefs = set(re.findall(r'href="([^"]+)"', block))
    assert all(h.startswith("/importar/") for h in hrefs), hrefs
