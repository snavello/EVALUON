"""El informe técnico del área, con una lectura mixta y con la cuenta de consultas (REQ-089, REQ-104;
P3; ADR-0041; O-264-1; plan 015, T-264).

- Una lectura mixta: la página 1 se leyó por visión, la 2 es legible y la 3 la visión la descartó
  (la página sigue como estaba). Solo la frase de la página 1 lleva la marca, el aviso y el enlace.
- La pantalla no consulta por frase: con 2 y con 6 frases hace las mismas consultas (T-223).
La propuesta del informe se guarda directo, como la deja `technical_report.propose`; todo el
material es inventado (P4)."""

import pytest

from tests.assessment.test_technical_report import offers  # noqa: F401 - fixture
from tests.journey.temas.test_s4_fundamento_pantallas import (
    LINK,
    MARK,
    NOTICE,
    original_of,
    propose_items,
    report_proposal,
)
from tests.journey.temas.test_s4_propuesta import log_in, page
from tests.journey.test_queries import count_queries

pytestmark = pytest.mark.django_db

ONE = "Renglón 1 del informe, en la página 1."
TWO = "Renglón 2 del informe, en la página 2."
THREE = "Renglón 3 del informe, en la página 3."


def informe_block(html):
    return html.split('id="s4-informe"', 1)[1]


def test_a_mixed_reading_marks_only_the_phrase_on_the_page_the_vision_read(
        client, offers, procedure, evaluator_user):  # noqa: F811
    """REQ-104, REQ-053, P3: de un informe cuya lectura es mixta, solo la frase de la página 1 (leída
    por visión) lleva la marca, el aviso y el enlace a la imagen; la de la página 2 (legible) y la
    de la 3 (que la visión descartó) no llevan nada."""
    a, _ = offers
    report = report_proposal(a, evaluator_user, reading_pages=(1,), reading_discarded=(3,),
                             items=[(1, ONE, 1), (2, TWO, 2), (3, THREE, 3)])
    log_in(client, evaluator_user)
    html = informe_block(page(client, procedure))
    assert html.count(NOTICE) == 1 and html.count(MARK) == 1
    assert html.index(ONE) < html.index(NOTICE) < html.index(TWO) < html.index(THREE)
    assert f'<a href="{original_of(report, 1)}">{LINK}</a>' in html


def test_the_report_block_does_not_query_per_phrase(
        client, offers, procedure, evaluator_user):  # noqa: F811
    """REQ-100, T-223: con 2 frases del informe y con 6 la pestaña hace las mismas consultas; las
    páginas leídas por visión de todas las frases se piden juntas."""
    a, b = offers
    first = report_proposal(a, evaluator_user, reading_pages=(1,), items=[(1, ONE, 1)])
    second = report_proposal(b, evaluator_user, reading_pages=(1,), items=[(1, ONE, 1)])
    log_in(client, evaluator_user)
    few = count_queries(client, procedure, "evaluacion")
    propose_items(a, evaluator_user, first, [(1, ONE, 1), (2, TWO, 2), (3, THREE, 3)])
    propose_items(b, evaluator_user, second, [(1, ONE, 1), (2, TWO, 2), (3, THREE, 3)])
    html = informe_block(page(client, procedure))
    assert html.count(THREE) == 2  # las 6 frases se ven
    many = count_queries(client, procedure, "evaluacion")
    assert many == few, f"{few} consultas con 2 frases y {many} con 6"
