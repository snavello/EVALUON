"""Las pantallas viejas de la 004 que siguen respondiendo en su dirección también avisan de la cita de
una página leída por visión (REQ-104, REQ-053; P3; decisión del responsable del 2026-10-13;
D-264-1; plan 015, T-264): el historial del par y la matriz vieja que se dibuja de nuevo cuando se
rechaza una acción (los motivos de descarte y las frases del informe técnico). Una consulta de las
lecturas con visión por pantalla, no una por fila (T-223). Resultados guardados directo, sin el
modelo; todo el material es inventado (P4)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from tests.assessment.test_matrix import add_run, requirement, three  # noqa: F401 - fixtures
from tests.journey.temas.test_s4_fundamento_pantallas import (
    LINK,
    MARK,
    NOTICE,
    cite_offer,
    original_of,
    report_proposal,
    vision_reading,
)
from tests.offers.test_screens import log_in

pytestmark = pytest.mark.django_db

PENDING = ("no_determinado", "pendiente_informe_tecnico")


def vision_queries(queries):
    """Las consultas que piden las lecturas con visión de las citas de una pantalla."""
    return [q for q in queries
            if 'FROM "offers_reading"' in q["sql"] and "? 'vision'" in q["sql"]]


def test_the_pair_history_marks_the_citation_read_by_vision_in_every_evaluation(
        three, procedure, operator_user, client):  # noqa: F811
    """REQ-104, REQ-053, P3: el historial del par (004) rotula, con el aviso y el enlace a la imagen,
    la cita de una página leída por visión de cada evaluación, con una sola consulta de lecturas;
    el historial de un par cuya cita es legible no lleva nada."""
    a, b, _ = three
    declaration = requirement(procedure, "declaración jurada")
    results = [add_run(operator_user, procedure, b, {declaration: "no_cumple"})[declaration.pk]
               for _ in range(2)]
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    document = b.documents.first()
    seen = vision_reading(document, pages=(2,))
    for result in results:
        cite_offer(result, 10, seen, 2)
    log_in(client, operator_user)
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("assessment:history", args=[b.pk, declaration.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert html.count(NOTICE) == 2 and html.count(MARK) == 2  # una por evaluación
    assert html.count(f'<a href="{original_of(document, 2)}">{LINK}</a>') == 2
    assert len(vision_queries(queries)) == 1
    plain = client.get(reverse("assessment:history", args=[a.pk, declaration.pk]))
    assert NOTICE not in plain.content.decode()


def test_the_old_matrix_marks_the_discard_quote_and_the_report_phrase_read_by_vision(
        three, procedure, operator_user, evaluator_user, client):  # noqa: F811
    """REQ-104, REQ-053, P3: la matriz vieja, que se dibuja de nuevo cuando se rechaza una acción,
    rotula la cita de la oferta de un motivo de descarte y la frase del informe técnico que salen de
    una página leída por visión, y no las de páginas legibles; una consulta de lecturas."""
    _, b, _ = three
    declaration = requirement(procedure, "declaración jurada")
    rows = {i: requirement(procedure, item=i) for i in (1, 2, 3)}
    result = add_run(operator_user, procedure, b, {
        declaration: "no_cumple", **{row: PENDING for row in rows.values()}})[declaration.pk]
    document = b.documents.first()
    cite_offer(result, 10, vision_reading(document, pages=(2,)), 2)
    report = report_proposal(
        b, evaluator_user, reading_pages=(2,),
        items=[(1, "Renglón 1: apto, en una página escaneada.", 2),
               (2, "Renglón 2: apto, en una página legible.", 1)])
    log_in(client, evaluator_user)
    with CaptureQueriesContext(connection) as queries:
        response = client.post(reverse("assessment:technical_give", args=[b.pk]),
                               {"item": ["1"], "verdict_1": ""})
    assert response.status_code == 422  # la acción se rechaza y se dibuja la matriz vieja
    html = response.content.decode()
    discards = html[html.index('class="matrix-discards"'):html.index('class="matrix-order"')]
    assert discards.count("Lo que dice la oferta") == 2  # la cita legible y la de visión
    assert discards.count(NOTICE) == 1
    assert f'<a href="{original_of(document, 2)}">{LINK}</a>' in discards
    technical = html[html.index('class="technical-ok"'):html.index('class="matrix-discards"')]
    first = technical.index("Renglón 1: apto, en una página escaneada.")
    second = technical.index("Renglón 2: apto, en una página legible.")
    assert technical.index(NOTICE) > first and technical.index(NOTICE) < second
    assert technical.count(NOTICE) == 1
    assert f'<a href="{original_of(report, 2)}">{LINK}</a>' in technical
    assert len(vision_queries(queries)) == 1
