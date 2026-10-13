"""El fundamento de cada conclusión se ve en la pestaña «Evaluación y dictamen» y en el detalle del
par (REQ-103, REQ-104; P3; dictamen de la 015, hallazgos 1 y 2; plan 015, T-264).

- El dato del Portal que fundamenta un «cumple» trae el enlace a la página del Portal (y al archivo,
  si lo hay) y la fecha en que se tomó (constitución 1.3, ADR-0053).
- La cita de una página leída por visión trae la marca «leída por visión», el aviso de comparar con
  el original y el enlace al original (ADR-0041). La imagen de la página va solo en el detalle del
  par.
- La pestaña no hace una consulta por celda para nada de eso (T-223).

«La celda» es el bloque de cada oferta dentro del detalle plegado de la fila del requisito. Las
evaluaciones corren con el modelo simulado; todo el material es inventado (P4)."""

import hashlib

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate
from evaluon.journey import memo
from evaluon.journey.temas import s4_propuesta
from evaluon.offers import models as om
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import (
    DECLARATION,
    cumple_declaration,
    requirement_of,
    run_all,
)
from tests.assessment.test_result_fundamento import (  # noqa: F401 - `portal*` son fixtures
    FETCHED,
    PAGE_URL,
    SHOWN,
    portal,
    portal_cumple,
    portal_with_file,
)
from tests.assessment.test_vision_flow import (  # noqa: F401 - fixtures de la lectura con visión
    SEEN,
    scanned,
    seen_page,
    whole_pages,
)
from tests.journey.test_queries import (
    SCALE_GROWTH,
    SCALE_LIMIT,
    count_queries,
    grow_case,
    make_case,
)

pytestmark = pytest.mark.django_db

NOTICE = ("Proviene de una página con dificultades de lectura: el texto citado es la "
          "transcripción que hizo el sistema mirando su imagen y puede tener errores. "
          "Conviene que la Comisión lo vuelva a chequear.")
LINK = "Ver la imagen de la página"
MARK = "leída por visión"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def detail(client, procedure, offer, requirement):
    """El HTML del detalle del par dentro de la pestaña."""
    response = client.get(reverse("expedientes:s4_par",
                                  args=[procedure.pk, offer.pk, requirement.pk]))
    assert response.status_code == 200
    return response.content.decode()


def cell(client, procedure, offer, requirement):
    """El HTML de la celda del par en la pestaña: del bloque de la oferta hasta el final de su
    lista de datos."""
    response = client.get(reverse("expedientes:evaluacion", args=[procedure.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    start = html.index(f'id="par-{offer.number}-{requirement.number}"')
    return html[start:html.index("</dl>", start)]


def original_of(document, page):
    return f"{reverse('offers:document_original', args=[document.pk])}#page={page}"


def image_of(offer, requirement, document, page):
    return reverse("assessment:vision_page", args=[offer.pk, requirement.pk, document.pk, page])


# --- El dato del Portal ----------------------------------------------------------------------


@pytest.fixture
def cumple_by_portal(offer, operator_user, procedure, model, portal, client):
    """Un «cumple» que se apoya solo en el dato del Portal, con la sesión de un operador abierta."""
    requirement = portal_cumple(portal, offer, operator_user, procedure)
    log_in(client, operator_user)
    return offer, requirement


def test_the_pair_detail_gives_the_portal_page_and_the_date_the_datum_was_taken(
        cumple_by_portal, client, procedure):
    """REQ-103, REQ-104, P3: el detalle del par muestra el dato del Portal con el enlace a su página
    y la fecha en que se tomó (hora de Buenos Aires, formato de las pantallas del Portal)."""
    offer, requirement = cumple_by_portal
    html = detail(client, procedure, offer, requirement)
    assert "Dato del Portal: Garantía: tipo Garantía de mantenimiento de oferta" in html
    assert "Portal: acta de apertura" in html
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in html
    assert f"página consultada el {SHOWN}" in html
    assert "archivo del Portal" not in html


def test_the_cell_gives_the_portal_page_and_the_date_the_datum_was_taken(
        cumple_by_portal, client, procedure):
    """REQ-103, REQ-104, P3: la celda de la pestaña muestra el dato del Portal (hoy no lo muestra)
    con el enlace a su página y la fecha en que se tomó."""
    offer, requirement = cumple_by_portal
    html = cell(client, procedure, offer, requirement)
    assert "Dato del Portal: Garantía: tipo Garantía de mantenimiento de oferta" in html
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in html
    assert f"página consultada el {SHOWN}" in html
    assert "archivo del Portal" not in html


def test_the_detail_and_the_cell_give_the_portal_file_when_the_item_has_one(
        offer, operator_user, procedure, model, portal_with_file, client):
    """REQ-103, REQ-104, P3: si el ítem del Portal tiene archivo, el detalle y la celda suman su
    enlace, con la fecha de la página como en las pantallas del Portal."""
    requirement = portal_cumple(portal_with_file, offer, operator_user, procedure)
    log_in(client, operator_user)
    download = reverse("portal:download",
                       args=[portal_with_file.proposal.link_id, portal_with_file.file_id])
    for html in (detail(client, procedure, offer, requirement),
                 cell(client, procedure, offer, requirement)):
        assert f'<a href="{download}">archivo del Portal</a>' in html
        assert f'<a href="{PAGE_URL}">página del Portal</a>' in html
        assert f"página consultada el {SHOWN}" in html


def test_a_result_without_a_portal_datum_shows_no_portal_source(
        offer, operator_user, procedure, model, portal, client):
    """REQ-103, REQ-104, P3: un resultado que no cita el Portal no muestra fuente del Portal, ni en
    el detalle ni en la celda, aunque el procedimiento tenga datos del Portal."""
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    log_in(client, operator_user)
    requirement = requirement_of(procedure, "declaración jurada")
    for html in (detail(client, procedure, offer, requirement),
                 cell(client, procedure, offer, requirement)):
        assert "Dato del Portal" not in html and "página del Portal" not in html
        assert "página consultada el" not in html


def test_the_tab_loads_the_portal_citations_without_the_stored_page(
        cumple_by_portal, procedure, operator_user):
    """REQ-100, REQ-104, T-231: la pestaña trae del Portal el enlace y la fecha, no la página bajada
    entera (cientos de miles de caracteres por cita)."""
    views = s4_propuesta._cell_views(memo.matrix_page(operator_user, procedure.pk), operator_user)
    cites = [c for view in views.values() for c in view.portal]
    assert len(cites) == 1
    page = cites[0].portal_item.page
    assert {"content"} <= page.get_deferred_fields()
    assert page.url == PAGE_URL and page.fetched_at == FETCHED  # lo que sí se muestra


# --- La lectura con visión --------------------------------------------------------------------


def test_the_pair_detail_marks_the_vision_citation_with_notice_original_and_image(
        seen_page, client, procedure):
    """REQ-104, REQ-053, P3: el detalle del par rotula la cita de una página leída por visión
    («leída por visión»), avisa que se compare con el original antes de confirmar, enlaza al
    original en esa página y muestra la imagen de la página como la vio el sistema."""
    offer, requirement = seen_page
    document = offer.documents.get()
    html = detail(client, procedure, offer, requirement)
    assert MARK in html and NOTICE in html
    assert f'<a href="{original_of(document, 2)}">{LINK}</a>' in html
    image = image_of(offer, requirement, document, 2)
    assert f'src="{image}"' in html
    picture = client.get(image)
    assert picture.status_code == 200 and picture["Content-Type"] == "image/jpeg"


def test_the_cell_marks_the_citation_read_by_vision_without_the_image(
        seen_page, client, procedure):
    """REQ-104, REQ-053, P3: la celda de la pestaña rotula la cita leída por visión, avisa que se
    compare con el original y enlaza al original; la imagen va solo en el detalle del par."""
    offer, requirement = seen_page
    document = offer.documents.get()
    html = cell(client, procedure, offer, requirement)
    assert MARK in html and NOTICE in html
    assert f'<a href="{original_of(document, 2)}">{LINK}</a>' in html
    assert image_of(offer, requirement, document, 2) not in html and "<img" not in html


def test_a_citation_that_was_not_read_by_vision_shows_no_mark(
        offer, operator_user, procedure, model, client):
    """REQ-104, REQ-053, P3: una cita de una página que no se leyó por visión no lleva marca, aviso
    ni imagen, ni en el detalle del par ni en la celda."""
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    log_in(client, operator_user)
    requirement = requirement_of(procedure, "declaración jurada")
    document = offer.documents.get(file_name="oferta.pdf")
    for html in (detail(client, procedure, offer, requirement),
                 cell(client, procedure, offer, requirement)):
        assert DECLARATION in html
        assert MARK not in html and NOTICE not in html
        assert LINK not in html
        assert image_of(offer, requirement, document, 1) not in html


@pytest.fixture
def two_pages(scanned, operator_user, procedure, model, client):
    """Un «cumple» que cita dos páginas del mismo documento: la primera, legible; la segunda, leída
    por visión."""
    model.sees(lambda seen: SEEN)

    def cites_both(call):
        if "declaración jurada" in call.requirement:
            return says("cumple", call.quote("Nota de presentación de la oferta."),
                        call.quote(DECLARATION), exigence="condicion")

    model.evaluates(cites_both)
    run_all(operator_user, procedure)
    log_in(client, operator_user)
    return scanned, requirement_of(procedure, "declaración jurada")


def test_only_the_citation_on_the_vision_page_is_marked_and_the_tab_agrees_with_the_service(
        two_pages, client, procedure, operator_user):
    """REQ-104, REQ-053, P3: de dos citas del mismo resultado solo la de la página leída por visión
    lleva la marca, el aviso y el enlace al original; la pestaña marca las mismas citas que el
    servicio de la 004 (`pair_page`)."""
    offer, requirement = two_pages
    document = offer.documents.get()
    served = evaluate.pair_page(operator_user, offer.pk, requirement.pk).offer_citations
    assert [(c.page, c.by_vision) for c in served] == [(1, False), (2, True)]
    views = s4_propuesta._cell_views(memo.matrix_page(operator_user, procedure.pk), operator_user)
    mine = views[(offer.pk, requirement.pk)].quotes
    assert [(c.page, c.by_vision) for c in mine] == [(c.page, c.by_vision) for c in served]
    for html in (detail(client, procedure, offer, requirement),
                 cell(client, procedure, offer, requirement)):
        assert html.count(NOTICE) == 1 and html.count(LINK) == 1
        assert f'<a href="{original_of(document, 2)}">{LINK}</a>' in html
        # La marca y el aviso vienen después de la cita de la página 2, no de la de la página 1.
        assert html.index("Nota de presentación de la oferta.") < html.index(DECLARATION)
        assert html.index(DECLARATION) < html.index(MARK) < html.index(NOTICE)


# --- Sin una consulta por celda ---------------------------------------------------------------


def ground_results(item):
    """Cada resultado que todavía no cita nada pasa a citar una página leída por visión de su
    oferta y el dato del Portal `item`. Citas directas, sin el modelo (P4: todo inventado)."""
    readings = {}
    for result in am.Result.objects.filter(citations__isnull=True).select_related("offer"):
        offer = result.offer
        if offer.pk not in readings:
            document = offer.documents.first()
            text = "Texto inventado de la página leída por visión."
            readings[offer.pk] = om.Reading.objects.create(
                document=document, sequence=document.readings.count() + 1, pages={"pages": []},
                canonical_text=text, canonical_sha256=hashlib.sha256(text.encode()).hexdigest(),
                tool_versions={},
                report={"vision": {"pages": [{"page": 1, "outcome": "read"}]}})
        reading = readings[offer.pk]
        am.Citation.objects.create(
            result=result, order=1, kind=am.CitationKind.OFERTA, document=reading.document,
            reading=reading, page=1, char_start=0, char_end=10, text=reading.canonical_text[:10])
        am.Citation.objects.create(
            result=result, order=2, kind=am.CitationKind.PORTAL, portal_item=item,
            portal_kind=am.PortalKind.GARANTIA, label="Portal: acta de apertura",
            text="Garantía: tipo inventado, monto 1000.00")


def test_the_tab_does_not_query_per_cell_for_the_portal_or_the_vision(
        client, procedure, operator_user, simulate, portal):
    """REQ-100, REQ-104, T-223: con 3 ofertas y 50 requisitos, todos con una cita leída por visión y
    el dato del Portal, la pestaña hace menos de 150 consultas; con el doble de requisitos, como
    máximo un 10 % más (no hay consultas por celda ni por cita)."""
    log_in(client, operator_user)
    offers, runs = make_case(procedure, operator_user, simulate)
    grow_case(procedure, operator_user, offers, runs, 50)
    ground_results(portal)
    html = client.get(reverse("expedientes:evaluacion", args=[procedure.pk])).content.decode()
    assert html.count(MARK) >= 50 and html.count(f'<a href="{PAGE_URL}">') >= 50
    small = count_queries(client, procedure, "evaluacion")
    assert small < SCALE_LIMIT, f"{small} consultas con 50 requisitos"
    grow_case(procedure, operator_user, offers, runs, 100)
    ground_results(portal)
    big = count_queries(client, procedure, "evaluacion")
    assert big <= small * SCALE_GROWTH, f"{small} con 50 y {big} con 100 requisitos"
