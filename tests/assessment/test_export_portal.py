"""La exportación dice de qué página del Portal sale cada dato del Portal que muestra y cuándo se
tomó (REQ-093, REQ-103; P3, constitución 1.3, ADR-0053; observación O-264-4 de la verificación de
T-264; plan 015, T-264).

- Planilla: al pie de los requisitos de cada oferta, una nota por página del Portal que citan sus
  resultados, con los requisitos que la citan, la dirección de la página y la fecha en que se
  consultó. La dirección va escrita, porque el archivo se imprime.
- Cuadro comparativo: al pie del orden económico, una nota por página del Portal de la que salen los
  precios y totales, con las ofertas que dependen de ella.
La dirección y la fecha son las de `portal/_fuente_dato.html` (la página del ítem de origen). Las
páginas se leen con una consulta para todos los resultados y otra para los datos de todas las
ofertas, no una por fila. Material inventado (P4)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.assessment.services import export as service
from evaluon.portal import models as pm
from tests.assessment.test_export import flat, read_xlsx
from tests.assessment.test_export_vision import pdf_text
from tests.assessment.test_matrix import add_run, requirement, three  # noqa: F401 - fixtures
from tests.assessment.test_ordering import quote_data
from tests.assessment.test_result_fundamento import (  # noqa: F401 - `portal` es fixture
    PAGE_URL,
    SHOWN,
    portal,
)
from tests.journey.temas.test_s4_fundamento_pantallas import cite_portal
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

# La otra página del Portal se consultó el 10/10/2026 a las 12:05 UTC: 09:05 en Buenos Aires.
SECOND_URL = "https://portal.invalid/cuadro-comparativo"
SECOND_FETCHED = datetime(2026, 10, 10, 12, 5, tzinfo=UTC)
SECOND_SHOWN = "10/10/2026 09:05"


def source(url=PAGE_URL, shown=SHOWN):
    """Lo que dice el archivo de dónde sale el dato: lo de `portal/_fuente_dato.html`, con la
    dirección escrita."""
    return f"fuente: Portal · página del Portal: {url} · página consultada el {shown}"


def sheet_note(which, **kwargs):
    """La nota de la hoja de una oferta: `which` son los requisitos que citan la página."""
    numbers = sorted(r.number for r in which)
    if len(numbers) == 1:
        text = f"el requisito {numbers[0]}"
    else:
        text = f"los requisitos {', '.join(map(str, numbers[:-1]))} y {numbers[-1]}"
    return f"Datos del Portal citados en {text} · {source(**kwargs)}"


def prices_note(offers, **kwargs):
    """La nota al pie del orden económico: de qué ofertas son los precios y totales."""
    numbers = [str(o.number) for o in offers]
    if len(numbers) == 1:
        text = f"la oferta {numbers[0]}"
    else:
        text = f"las ofertas {', '.join(numbers[:-1])} y {numbers[-1]}"
    return f"Precios y totales de {text} · {source(**kwargs)}"


def notes_of(texts, start):
    """Las notas del archivo que empiezan con `start`, en el orden en que salen."""
    return [text for text in texts if text.startswith(start)]


def second_item(first):
    """Otro ítem del Portal, de otra página (otra dirección, otro día)."""
    page = pm.PortalPage.objects.create(
        link=first.proposal.link, exploration=1, kind="cuadro", url=SECOND_URL,
        fetched_at=SECOND_FETCHED, sha256="d" * 64, content=b"y")
    return pm.PortalItem.objects.create(proposal=first.proposal, kind="oferta", key="o2",
                                        payload={}, content_sha256="e" * 64, page=page)


@pytest.fixture
def rows(procedure):
    """Los tres requisitos formales de la matriz: declaración jurada, inscripción y garantía."""
    return (requirement(procedure, "declaración jurada"),
            requirement(procedure, "constancia de inscripción"),
            requirement(procedure, "garantía de mantenimiento"))


@pytest.fixture
def with_portal(three, portal, rows, procedure, operator_user):  # noqa: F811
    """Tres ofertas con sus datos del Portal (total y cotizaciones de la misma página), evaluadas
    en los tres requisitos. Los resultados de A en la declaración y en la garantía citan el Portal;
    el de B en la inscripción también; los de C no."""
    declaration, registry, guarantee = rows
    saved = {}
    for offer, total in zip(three, ("900", "100", "500"), strict=True):
        saved[offer.pk] = add_run(operator_user, procedure, offer,
                                  {row: "cumple" for row in rows})
        quote_data(portal, procedure, offer, total=Decimal(total),
                   prices={1: (Decimal("10"), 1), 2: (Decimal("10"), 1)})
    a, b, _ = three
    cite_portal(saved[a.pk][declaration.pk], 10, portal)
    cite_portal(saved[a.pk][guarantee.pk], 10, portal)
    cite_portal(saved[b.pk][registry.pk], 10, portal)
    return three, saved


def test_the_planilla_names_the_portal_page_and_the_date_in_each_sheet_that_cites_it(
        with_portal, rows, procedure, operator_user):
    """REQ-093, REQ-103, P3: en la planilla en Excel, la hoja de cada oferta cuyos resultados citan
    el Portal trae una nota con los requisitos que lo citan, la dirección de la página del Portal y
    la fecha en que se consultó; la hoja de la oferta que no cita nada del Portal, ninguna."""
    declaration, registry, guarantee = rows
    (a, b, c), _ = with_portal
    sheets = read_xlsx(service.export(operator_user, procedure.pk, "planilla", "xlsx")[0])
    mine = flat(sheets[f"Oferta {a.number}"])
    assert notes_of(mine, "Datos del Portal") == [sheet_note([declaration, guarantee])]
    other = flat(sheets[f"Oferta {b.number}"])
    assert notes_of(other, "Datos del Portal") == [sheet_note([registry])]
    assert not any("fuente: Portal" in text for text in flat(sheets[f"Oferta {c.number}"]))


def test_the_cuadro_names_the_portal_page_the_prices_and_totals_come_from(
        with_portal, procedure, operator_user):
    """REQ-093, REQ-103, P3: en el cuadro en Excel, el orden económico (totales y precios del
    Portal) lleva al pie la página del Portal de la que salen, la fecha en que se consultó y de qué
    ofertas; los resultados citados de la grilla no traen la nota de la planilla."""
    offers, _ = with_portal
    sheets = read_xlsx(service.export(operator_user, procedure.pk, "cuadro", "xlsx")[0])
    texts = flat(sheets["Cuadro comparativo"])
    assert notes_of(texts, "Precios y totales") == [prices_note(offers)]
    assert not any("Datos del Portal citados" in text for text in texts)


def test_the_pdf_of_the_planilla_and_of_the_cuadro_name_the_portal_page_too(
        with_portal, rows, procedure, operator_user):
    """REQ-093, REQ-103, P3: el PDF (el HTML con que se arma y el texto del archivo entregado) trae
    la nota por oferta de la planilla y la del orden económico del cuadro."""
    declaration, _, guarantee = rows
    offers, _ = with_portal
    data = service.collect(operator_user, procedure.pk)
    planilla = service.build_html(data, "planilla")
    assert planilla.count(sheet_note([declaration, guarantee])) == 1
    cuadro = service.build_html(data, "cuadro")
    assert cuadro.count(prices_note(offers)) == 1
    for document in ("planilla", "cuadro"):
        # Una dirección larga puede partirse en el renglón del PDF: se compara sin espacios.
        words = pdf_text(service.export(operator_user, procedure.pk, document, "pdf")[0])
        words = words.replace(" ", "")
        assert PAGE_URL in words and SHOWN.replace(" ", "") in words


def test_each_portal_page_has_its_own_note_with_its_own_date(
        with_portal, rows, procedure, operator_user, portal):  # noqa: F811
    """REQ-093, REQ-103, P3: si los datos salen de dos páginas del Portal, la planilla y el cuadro
    traen una nota por página, cada una con su dirección y su fecha: la hoja de B cita las dos, y
    los precios y totales de B salen de la segunda."""
    declaration, registry, _ = rows
    (a, b, c), saved = with_portal
    other = second_item(portal)
    cite_portal(saved[b.pk][declaration.pk], 11, other)
    pm.PortalOfferData.objects.filter(offer=b).update(item=other)
    sheets = read_xlsx(service.export(operator_user, procedure.pk, "planilla", "xlsx")[0])
    notes = notes_of(flat(sheets[f"Oferta {b.number}"]), "Datos del Portal")
    # Una nota por página, en el orden en que la cita el primer requisito de la hoja.
    expected = {registry.number: sheet_note([registry]),
                declaration.number: sheet_note([declaration], url=SECOND_URL,
                                               shown=SECOND_SHOWN)}
    assert notes == [expected[number] for number in sorted(expected)]
    cuadro = read_xlsx(service.export(operator_user, procedure.pk, "cuadro", "xlsx")[0])
    assert notes_of(flat(cuadro["Cuadro comparativo"]), "Precios y totales") == [
        prices_note([a, c]), prices_note([b], url=SECOND_URL, shown=SECOND_SHOWN)]


def test_without_portal_data_the_exports_name_no_portal_page(
        three, rows, procedure, operator_user):  # noqa: F811
    """REQ-093, P3: sin datos ni citas del Portal, ni la planilla ni el cuadro traen la nota."""
    for offer in three:
        add_run(operator_user, procedure, offer, {row: "cumple" for row in rows})
    for document in ("planilla", "cuadro"):
        sheets = read_xlsx(service.export(operator_user, procedure.pk, document, "xlsx")[0])
        texts = [text for sheet in sheets.values() for text in flat(sheet)]
        assert not any("fuente: Portal" in text for text in texts)
        html = service.build_html(service.collect(operator_user, procedure.pk), document)
        assert "fuente: Portal" not in html


def test_the_portal_pages_are_read_with_the_same_queries_for_any_number_of_offers(
        with_portal, rows, procedure, operator_user, portal):  # noqa: F811
    """REQ-100, T-223: con 3 y con 6 ofertas (y con más resultados que citan el Portal), la
    exportación lee los ítems y las páginas del Portal con las mismas consultas, una con las citas
    de todos los resultados y otra con los datos de todas las ofertas: no hay una por oferta ni por
    resultado."""
    def portal_reads():
        with CaptureQueriesContext(connection) as queries:
            service.collect(operator_user, procedure.pk)
        return sum(1 for q in queries
                   if '"portal_page"' in q["sql"] or '"portal_item"' in q["sql"])

    few = portal_reads()
    for number in range(4, 7):
        offer = make_offer(procedure, operator_user, f"Oferente {number}",
                           {"oferta.pdf": ["Texto de la oferta."]})
        saved = add_run(operator_user, procedure, offer, {row: "cumple" for row in rows})
        quote_data(portal, procedure, offer, total=Decimal("100"), prices={1: (Decimal("5"), 1)})
        for row in rows:
            cite_portal(saved[row.pk], 10, portal)
    many = portal_reads()
    assert few == many == 2, f"{few} consultas con 3 ofertas y {many} con 6"
