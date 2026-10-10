"""El encabezado del punto se ve en la fila de la matriz (REQ-101; plan 015, T-234; ADR-0054,
regla 2).

Un inciso de una lista cuya oración sola no se entiende («copia certificada del estatuto
social;») muestra, sobre su cita, el encabezado de su punto («La oferta deberá incluir:»),
rotulado. El encabezado es contexto: la cita guardada no lo incluye. El pliego es sintético
(P4); el modelo, el doble con guion de `tests/tenders/scripted.py`.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.tenders import models as m
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.services import matrix_page
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (  # noqa: F401  (script es un fixture)
    item,
    load_and_read,
    make_procedure,
    propose,
    script,
)

pytestmark = pytest.mark.django_db

HEADING = "La oferta deberá incluir:"
PRICES = "Los precios incluyen impuestos y se expresan en pesos."


@pytest.fixture(autouse=True)
def only_the_extraction(monkeypatch, settings):
    """Estas pruebas son de lo que muestra la fila: ni la completitud ni el filtro."""
    monkeypatch.setattr(proposal, "completeness_candidates", lambda loaded, decisions: [])
    settings.FILTER_ENABLED = False


@pytest.fixture
def proposed(operator_user, script):  # noqa: F811
    """Una propuesta con un punto que tiene dos incisos y otro punto que se entiende solo."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PRESENTACIÓN", f"1.1. {HEADING}",
             "a) copia certificada del estatuto social;",
             "b) constancia de inscripción impositiva."),
        para("2. PRECIOS", f"2.1. {PRICES}"),
    ]], header=None))
    script.when("copia certificada", item([("copia certificada del estatuto", "formal")]))
    script.when("constancia de inscripción", item([("constancia de inscripción", "formal")]))
    script.when("impuestos", item([("incluyen impuestos", "economico")]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return procedure, requested.run.version


def headings(page):
    """`{texto de la cita: encabezado}` de cada fila formal o económica de la página."""
    return {row.quotes[0].text: row.quotes[0].heading
            for group in page.groups for row in group.rows}


def test_each_item_row_carries_the_heading_of_its_point(operator_user, proposed):
    """REQ-101: los incisos de la lista llevan el encabezado de su punto; la cláusula que se
    entiende sola no lleva ninguno."""
    _, version = proposed

    page = matrix_page.matrix_page(operator_user, version.pk)

    assert headings(page) == {
        "copia certificada del estatuto social;": HEADING,
        "constancia de inscripción impositiva.": HEADING,
        PRICES: "",
    }


def test_the_heading_is_not_part_of_the_stored_quote(operator_user, proposed):
    """REQ-101, REQ-025: el encabezado es contexto: la cita guardada es el inciso, un recorte
    literal del texto canónico, sin el encabezado."""
    _, version = proposed

    cited = m.RequirementQuote.objects.get(requirement__version=version,
                                           segment__key="sec-i/1.1/inc-a")

    assert cited.text == "copia certificada del estatuto social;"
    reading = cited.segment.reading
    assert reading.canonical_text[cited.char_start:cited.char_end] == cited.text


def test_the_headings_of_a_page_are_fetched_in_one_query(operator_user, proposed):
    """REQ-101: los tramos padre de todas las citas se traen de una vez, no uno por fila."""
    _, version = proposed

    with CaptureQueriesContext(connection) as queries:
        matrix_page.matrix_page(operator_user, version.pk)

    by_key = [q["sql"] for q in queries
              if 'FROM "tenders_segment"' in q["sql"] and '"key" IN' in q["sql"]]
    assert len(by_key) == 1


def test_the_matrix_tab_shows_the_heading_labelled_above_the_quote(
        client, operator_user, proposed):
    """REQ-101: la fila de la matriz de la sección «Pliego y matriz» muestra «Encabezado del
    punto: …» sobre la cita, una vez por cada inciso."""
    procedure, _ = proposed
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)

    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()

    assert html.count(f"Encabezado del punto: {HEADING}") == 2
    first = html.index(f"Encabezado del punto: {HEADING}")
    assert html.index("copia certificada del estatuto social;", first) > first
