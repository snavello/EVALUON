"""Emparejar las ofertas del Portal con las ya cargadas a mano (T-174; REQ-062, REQ-051).
Nombres inventados que reproducen las diferencias reales: solo el apellido, un acento
distinto, mayúsculas, y dos candidatos posibles. Sin red."""

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service
from evaluon.portal.importers.offers import match_offer
from evaluon.portal.models import PortalOfferData
from evaluon.portal.services import approval
from evaluon.tenders.models import Procedure
from tests.conftest import TEST_PASSWORD
from tests.portal.test_offers import (  # noqa: F401
    explored,
    load_procedure,
    offer_items,
    open_offers,
)
from tests.portal.fakeportal import (  # noqa: F401
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.tenders.conftest import evaluator_user, no_commission_user, operator_user  # noqa: F401

pytestmark = pytest.mark.django_db

MARTA = ("27000000014", "Marta Josefina Demo Uno")
ALBERTO = ("20000000036", "ALBERTO DEMO TRES")
NANDU = ("30999999919", "ÑANDÚ INSUMOS DEMO SRL")


@pytest.fixture
def procedure(explored, evaluator_user):
    load_procedure(evaluator_user)
    return Procedure.objects.get()


def by_hand(user, procedure, name):
    return offers_service.register_offer(user, procedure, bidder=name)


@pytest.mark.parametrize("portal, manual", [
    (MARTA, "Demo Uno"),                      # solo el apellido
    (NANDU, "Nandu Insumos Demo S.R.L."),     # acento y signos distintos
    (ALBERTO, "alberto demo tres"),           # mayúsculas
])
def test_hand_loaded_offer_is_proposed_by_name(procedure, operator_user, portal, manual):
    """REQ-062: apellido solo, acento o mayúsculas distintos se proponen por nombre."""
    offer = by_hand(operator_user, procedure, manual)
    found = match_offer(procedure, *portal)
    assert (found.offer, found.how) == (offer, "nombre")


def test_two_possible_candidates_are_not_matched(procedure, operator_user):
    """REQ-062: con dos candidatos posibles no se empareja y se informa."""
    by_hand(operator_user, procedure, "Demo Uno")
    by_hand(operator_user, procedure, "Marta Demo")
    found = match_offer(procedure, *MARTA)
    assert found.offer is None and found.how == "" and "más de una oferta" in found.note


def test_unrelated_name_is_not_matched(procedure, operator_user):
    by_hand(operator_user, procedure, "Otra Persona")
    assert match_offer(procedure, *MARTA).offer is None


def test_cuit_wins_over_name(procedure, operator_user, explored):
    """REQ-062: la oferta cargada que ya tiene el CUIT se empareja por CUIT, aunque otra
    se parezca más por nombre."""
    other = by_hand(operator_user, procedure, "Marta Josefina Demo Uno")
    with_cuit = by_hand(operator_user, procedure, "Apellido Distinto")
    PortalOfferData.objects.create(offer=with_cuit, cuit=MARTA[0], item=offer_items().first())
    found = match_offer(procedure, *MARTA)
    assert (found.offer, found.how) == (with_cuit, "cuit") and found.offer != other


def test_different_cuit_is_a_mismatch_and_not_matched(procedure, operator_user, explored):
    """REQ-062: nombre parecido pero CUIT distinto: falta de coincidencia, no se empareja."""
    other = by_hand(operator_user, procedure, "Demo Uno")
    PortalOfferData.objects.create(offer=other, cuit="20111111112", item=offer_items().first())
    found = match_offer(procedure, *MARTA)
    assert found.offer is None and "falta de coincidencia" in found.note
    assert "20111111112" in found.note


def test_approval_associates_without_renaming_and_logs_it(
        procedure, operator_user, evaluator_user):
    """REQ-062, P3, P6: al aprobar se asocia, el nombre cargado no cambia, los datos del
    Portal quedan enlazados y el registro dice cómo se emparejó."""
    manual = by_hand(operator_user, procedure, "Demo Uno")
    item = offer_items().get(key=f"oferta:{MARTA[0]}")
    (result,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.LOADED, result.reason
    manual.refresh_from_db()
    assert manual.bidder == "Demo Uno" and Offer.objects.count() == 1
    assert manual.portal_data.item == item and manual.portal_quotes.count() == 6
    event = AuditEvent.objects.filter(detail__item=item.pk, detail__result="cargado").get()
    assert event.detail["match"] == "nombre" and event.detail["match_offer"] == manual.pk


def test_approval_with_two_candidates_creates_a_new_offer(
        procedure, operator_user, evaluator_user):
    """REQ-062: ambiguo, no se asocia a ninguna: se da de alta la oferta del Portal."""
    by_hand(operator_user, procedure, "Demo Uno")
    by_hand(operator_user, procedure, "Marta Demo")
    item = offer_items().get(key=f"oferta:{MARTA[0]}")
    (result,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.LOADED, result.reason
    assert Offer.objects.count() == 3
    assert PortalOfferData.objects.get().offer.bidder == MARTA[1]


def test_screen_shows_the_proposed_association(client, procedure, operator_user):
    """REQ-062, P3: la pantalla de aprobación dice a qué oferta cargada se asocia y por qué."""
    by_hand(operator_user, procedure, "Demo Uno")
    by_hand(operator_user, procedure, "Nandu Insumos Demo SRL")
    link = offer_items().first().proposal.link
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:proposal", args=[link.pk])).content.decode()
    assert "Se asocia a la oferta cargada «Nandu Insumos Demo SRL»" in html
    assert "por nombre" in html


@pytest.mark.parametrize("generic, portal", [
    ("SRL", NANDU), ("S.R.L.", NANDU), ("de", ("20000000044", "Juan de la Cruz")),
    ("y", ("20000000052", "Pedro y Hermanos SA")), ("SA", ("20000000060", "Pedro y Hermanos SA")),
    ("de la", ("20000000044", "Juan de la Cruz")),
])
def test_generic_name_is_not_matched_by_words(procedure, operator_user, generic, portal):
    """REQ-062 (H-1): un nombre solo de palabras vacías o formas societarias no se empareja
    por contenido y se informa."""
    by_hand(operator_user, procedure, generic)
    found = match_offer(procedure, *portal)
    assert found.offer is None and "no tiene ningún término" in found.note


def test_short_term_is_not_enough(procedure, operator_user):
    """REQ-062 (H-1): un término de menos de 3 letras no alcanza."""
    by_hand(operator_user, procedure, "Li SRL")
    found = match_offer(procedure, "20000000078", "Li Wei Demo SA")
    assert found.offer is None and "no tiene ningún término" in found.note


def test_societary_form_is_ignored_when_matching(procedure, operator_user):
    """REQ-062 (H-1): con un término significativo y forma societaria distinta sigue
    emparejando por nombre."""
    offer = by_hand(operator_user, procedure, "Nandu Insumos Demo SA")
    found = match_offer(procedure, *NANDU)
    assert (found.offer, found.how) == (offer, "nombre")


def test_two_items_competing_for_one_offer_are_not_matched(
        client, procedure, operator_user, evaluator_user):
    """REQ-062 (H-2): dos ítems del Portal contra la misma oferta cargada: la pantalla avisa
    en ambos y al aprobar en lote ninguno se asocia."""
    manual = by_hand(operator_user, procedure, "Demo")
    link = offer_items().first().proposal.link
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:proposal", args=[link.pk])).content.decode()
    assert html.count("compite con otra oferta del Portal") >= 2
    assert "Se asocia a la oferta cargada «Demo»" not in html
    ids = list(offer_items().filter(key__in=[f"oferta:{MARTA[0]}", f"oferta:{ALBERTO[0]}"])
               .values_list("pk", flat=True))
    results = approval.decide(evaluator_user, ids, approval.APPROVE)
    assert all(r.result == approval.LOADED for r in results)
    assert not PortalOfferData.objects.filter(offer=manual).exists()
