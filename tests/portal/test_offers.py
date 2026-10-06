"""Ofertas del Portal: acta y cuadro comparativo a ítems y a la 008 (REQ-047, REQ-048,
REQ-049, REQ-051; T-143). Sin red: el transporte es `FakePortal`."""

from datetime import date
from decimal import Decimal
from urllib.parse import urljoin

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    PageKind,
    PortalItem,
    PortalLine,
    PortalOfferData,
    PortalPage,
    PortalProposal,
    PortalQuote,
)
from evaluon.portal.parsing.pagina import parse_page
from evaluon.portal.services import approval
from evaluon.tenders.models import JobStatus, Procedure
from tests.conftest import TEST_PASSWORD
from tests.portal.conftest import reply
from tests.portal.fakeportal import (  # noqa: F401
    DATA,
    EXPECTED,
    LINK_URL,
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db

DATE = date(2025, 11, 14)
PROCESS = parse_page((DATA / "proceso.html").read_bytes())
ACTA_URL = urljoin(LINK_URL, PROCESS.acta["url"])


@pytest.fixture
def open_offers(fake_portal_calco):
    """El portal de mentira con el acta (GET directo) y el cuadro (envío de formulario)."""
    portal = fake_portal_calco
    portal.routes[("GET", ACTA_URL)] = reply(ACTA_URL, (DATA / "acta-apertura.html").read_bytes())
    portal.routes[("POST", LINK_URL)] = reply(
        LINK_URL, (DATA / "cuadro-comparativo.html").read_bytes())
    return portal


@pytest.fixture
def explored(operator_user, open_offers, explore_link):
    link, job = explore_link(operator_user)
    assert job.status == JobStatus.DONE, job.error
    return link


def offer_items():
    return PortalItem.objects.filter(kind=ItemKind.OFERTA)


def load_procedure(evaluator_user):
    procedure_item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    lines_item = PortalItem.objects.get(kind=ItemKind.RENGLONES)
    results = approval.decide(evaluator_user, [procedure_item.pk, lines_item.pk],
                              approval.APPROVE,
                              confirmations={procedure_item.pk: {"authorization_date": DATE}})
    assert [r.result for r in results] == [approval.LOADED, approval.LOADED]


def test_three_offers_are_proposed_with_total_and_guarantee(explored):
    """REQ-047: una oferta por oferente con su CUIT, total y garantía; nada cargado."""
    assert offer_items().count() == 3
    assert not Offer.objects.exists()
    for want in EXPECTED["ofertas"]:
        item = offer_items().get(key=f"oferta:{want['cuit']}")
        data = item.payload
        assert data["oferente"] == want["proveedor"]
        assert Decimal(data["total"]) == Decimal(str(want["total"]))
        assert Decimal(data["total_cuadro"]) == Decimal(str(want["total"]))
        assert data["moneda"] == want["moneda"]
        (guarantee,) = data["garantias"]
        assert (guarantee["tipo"], guarantee["forma"]) == (
            want["garantia"]["tipo"], want["garantia"]["forma"])
        assert Decimal(guarantee["monto"]) == Decimal(str(want["garantia"]["monto"]))
        assert data["anomalias"] == []
        assert item.page.kind == PageKind.ACTA


def test_eighteen_quotes_match_the_pairs(explored):
    """REQ-047: los 18 pares oferta y renglón con precio y cantidad iguales a los del calco."""
    pairs = {}
    for item in offer_items():
        for quote in item.payload["cotizaciones"]:
            pairs[(quote["renglon"], item.payload["cuit"])] = quote
    assert len(pairs) == 18
    for want in EXPECTED["pares_oferta_renglon"]:
        got = pairs[(want["renglon"], want["cuit"])]
        assert Decimal(got["precio"]) == Decimal(str(want["precio_unitario"]))
        assert Decimal(got["cantidad"]) == Decimal(str(want["cantidad"]))


def test_pages_are_kept_as_downloaded_with_their_fingerprint(explored):
    """REQ-049: el acta y el cuadro se guardan tal cual, con su huella."""
    acta = PortalPage.objects.get(kind=PageKind.ACTA)
    cuadro = PortalPage.objects.get(kind=PageKind.CUADRO)
    assert bytes(acta.content) == (DATA / "acta-apertura.html").read_bytes()
    assert bytes(cuadro.content) == (DATA / "cuadro-comparativo.html").read_bytes()
    assert acta.sha256 and cuadro.sha256 and acta.link == explored


def test_offers_wait_for_procedure_and_lines(explored, evaluator_user):
    """Un ítem de oferta exige el procedimiento y los renglones cargados."""
    item = offer_items().first()
    (result,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.PENDING
    assert "procedimiento" in result.reason
    assert not Offer.objects.exists()


def test_approved_offers_are_loaded_with_register_offer_and_quotes(explored, evaluator_user):
    """REQ-047, REQ-048: lo aprobado se carga con register_offer; datos y cotizaciones van a
    las tablas del Portal con su ítem de origen."""
    load_procedure(evaluator_user)
    ids = list(offer_items().values_list("pk", flat=True))
    results = approval.decide(evaluator_user, ids, approval.APPROVE)
    assert all(r.result == approval.LOADED for r in results), [r.reason for r in results]
    assert Offer.objects.count() == 3
    assert PortalQuote.objects.count() == 18
    assert PortalOfferData.objects.count() == 3
    for want in EXPECTED["ofertas"]:
        data = PortalOfferData.objects.get(cuit=want["cuit"])
        assert data.offer.bidder == want["proveedor"]
        assert data.offer.created_by == evaluator_user
        assert data.currency == "ARS"
        assert data.total == Decimal(str(want["total"]))
        assert data.guarantee_amount == Decimal(str(want["garantia"]["monto"]))
        assert data.guarantee_form == want["garantia"]["forma"]
        assert data.item.page.kind == PageKind.ACTA
    for want in EXPECTED["pares_oferta_renglon"]:
        quote = PortalQuote.objects.get(offer__portal_data__cuit=want["cuit"],
                                        line__number=want["renglon"])
        assert quote.price == Decimal(str(want["precio_unitario"]))
        assert quote.quantity == Decimal(str(want["cantidad"]))
        assert quote.line == PortalLine.objects.get(number=want["renglon"])
    item = offer_items().first()
    item.refresh_from_db()
    assert item.state == ItemState.CARGADO and item.loaded_model == "offers_offer"


def test_rejected_offer_is_not_loaded_and_approved_one_is(explored, evaluator_user):
    """REQ-048: aprobar una y rechazar otra: solo se carga lo aprobado."""
    load_procedure(evaluator_user)
    first, second, _third = offer_items().order_by("pk")
    approval.decide(evaluator_user, [first.pk], approval.APPROVE)
    approval.decide(evaluator_user, [second.pk], approval.REJECT)
    assert Offer.objects.count() == 1
    assert PortalQuote.objects.count() == 6
    second.refresh_from_db()
    assert second.state == ItemState.RECHAZADO and second.decided_by == evaluator_user


def test_operator_cannot_approve_offers(explored, operator_user):
    """REQ-048: el operador solo aprueba documentos."""
    item = offer_items().first()
    with pytest.raises(RoleRejected):
        approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert not Offer.objects.exists()


def test_a_duplicated_bidder_is_not_loaded_twice(explored, evaluator_user):
    """El mismo oferente no se carga dos veces: ni al aprobar de nuevo ni desde otro ítem."""
    load_procedure(evaluator_user)
    item = offer_items().first()
    approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    (again,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert again.result == approval.ALREADY
    clone = PortalItem.objects.create(
        proposal=PortalProposal.objects.create(
            link=item.proposal.link, exploration=99, origin="revision"),
        kind=ItemKind.OFERTA, key=item.key, payload={**item.payload, "total": "1"},
        content_sha256="0" * 64, page=item.page)
    (result,) = approval.decide(evaluator_user, [clone.pk], approval.APPROVE)
    assert result.result == approval.FAILED and "ya está cargada" in result.reason
    assert Offer.objects.count() == 1 and PortalQuote.objects.count() == 6


def test_acta_with_two_rows_per_guarantee_gives_one_item_per_bidder(
        operator_user, open_offers, explore_link):
    """El acta repite la oferta por cada garantía: un solo ítem por CUIT, con ambas."""
    html = (DATA / "acta-apertura.html").read_text(encoding="utf-8")
    start = html.index('id="ctl00_CPH1_UCVistaPreviaActa_gvOfertas"')
    end = html.index("</table>", start)
    cells = ["ALBERTO DEMO TRES", "20000000036", "30/11/2025", "Peso Argentino", "195823,50",
             "195823,50", "Mantenimiento oferta", "Pagare", "65000"]
    repeated = "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    page = (html[:end] + repeated + repeated + html[end:]).encode("utf-8")
    open_offers.routes[("GET", ACTA_URL)] = reply(ACTA_URL, page)
    explore_link(operator_user)
    assert offer_items().count() == 3
    item = offer_items().get(key="oferta:20000000036")
    assert len(item.payload["garantias"]) == 2
    assert any("2 garantías" in note for note in item.payload["anomalias"])


def test_total_that_differs_between_acta_and_cuadro_is_an_anomaly(
        operator_user, open_offers, explore_link):
    """Si el acta y el cuadro difieren en un total, se informa como anomalía del ítem."""
    cuadro = (DATA / "cuadro-comparativo.html").read_text(encoding="utf-8")
    assert "Total: $ 183.835,00" in cuadro
    open_offers.routes[("POST", LINK_URL)] = reply(
        LINK_URL, cuadro.replace("Total: $ 183.835,00", "Total: $ 183.000,00").encode("utf-8"))
    link, _ = explore_link(operator_user)
    item = offer_items().get(key="oferta:27000000014")
    assert any("difieren" in note for note in item.payload["anomalias"])
    assert offer_items().get(key="oferta:30999999919").payload["anomalias"] == []
    proposal = link.proposals.get()
    assert any(a["parte"] == "oferta 27000000014" for a in proposal.anomalies)


def test_unreachable_cuadro_is_an_anomaly_and_the_acta_still_proposes(
        operator_user, open_offers, explore_link):
    """REQ-051: una parte que no se puede bajar queda como anomalía y no frena el resto."""
    del open_offers.routes[("POST", LINK_URL)]
    link, job = explore_link(operator_user)
    assert job.status == JobStatus.DONE
    assert offer_items().count() == 3
    assert all(item.payload["cotizaciones"] == [] for item in offer_items())
    proposal = link.proposals.get()
    assert any(a["parte"] == "cuadro comparativo" for a in proposal.anomalies)
    assert not PortalPage.objects.filter(kind=PageKind.CUADRO).exists()


def test_process_without_open_offers_proposes_none(operator_user, portal_client, explore_link):
    """Sin acta ni cuadro (ofertas todavía cerradas) no hay ítems de oferta."""
    html = (DATA / "proceso.html").read_text(encoding="utf-8")
    stripped = html.replace("lnkVerCuadroComparativo", "otroEnlace").replace(
        "lnkVerActaApertura", "otroEnlaceActa")
    assert stripped != html
    portal_client.routes[("GET", LINK_URL)] = reply(LINK_URL, stripped.encode("utf-8"))
    explore_link(operator_user)
    assert not offer_items().exists()


def test_manual_document_sits_next_to_the_imported_offer(explored, evaluator_user,
                                                        operator_user):
    """REQ-051: el operador carga a mano un documento de la oferta importada; queda junto a
    lo importado y sin ítem del Portal (origen "carga manual")."""
    load_procedure(evaluator_user)
    item = offer_items().first()
    approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    offer = Offer.objects.get()
    loaded = offers_service.load_document(
        operator_user, offer, data=(DATA / "autorizacion-llamado.pdf").read_bytes(),
        file_name="oferta-a-mano.pdf")
    assert loaded.document.offer == offer
    assert offer.portal_data.item == item and offer.portal_quotes.count() == 6
    assert offer.documents.count() == 1


def test_offer_registered_by_hand_with_the_same_name_is_associated(
        explored, evaluator_user, operator_user):
    """REQ-051: si el operador ya registró a mano al oferente, el ítem se asocia a esa oferta."""
    load_procedure(evaluator_user)
    item = offer_items().get(key="oferta:27000000014")
    manual = offers_service.register_offer(
        operator_user, Procedure.objects.get(), bidder="marta  josefina demo uno")
    (result,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.LOADED, result.reason
    assert Offer.objects.count() == 1 and manual.portal_data.item == item


def test_proposal_screen_shows_the_offer_with_its_table(client, explored, operator_user):
    """El parcial de la oferta muestra oferente, CUIT, total, garantía y cotización."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:proposal", args=[explored.pk])).content.decode()
    assert "Cotización por renglón" in html
    assert "27000000014" in html and "Pagare" in html
    assert "Este ítem lo aprueba un evaluador." in html
