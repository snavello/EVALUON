"""La ficha vieja y la historia de su fila, que siguen respondiendo en su dirección, también avisan del
fragmento de una página leída por visión (REQ-086, REQ-104; P3; decisión del responsable del
2026-10-13; D-264-1; plan 015, T-264): el fragmento vigente y el quitado de la ficha; en la historia
de la fila, además, lo que propuso el sistema y el antes y el después de cada cambio. Una consulta
de las lecturas con visión por pantalla, no una por fila (T-223). Material inventado (P4)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers import models as om
from tests.journey.temas.test_s3_ficha_vision import SEEN, card, fragment_of  # noqa: F401
from tests.journey.temas.test_s4_fundamento_pantallas import LINK, MARK, NOTICE, original_of

pytestmark = pytest.mark.django_db


def vision_queries(queries):
    return [q for q in queries
            if 'FROM "offers_reading"' in q["sql"] and "? 'vision'" in q["sql"]]


def row_of(html, entry):
    """La fila de la ficha vieja (`<tr id="fila-N">`) hasta la siguiente."""
    start = html.index(f'id="fila-{entry.pk}"')
    end = html.find("</tr>", start)
    return html[start:end]


def test_the_old_sheet_marks_the_fragments_read_by_vision_with_one_query(
        client, card):  # noqa: F811
    """REQ-086, REQ-104, P3: la ficha vieja rotula, con el aviso y el enlace a la imagen, el fragmento
    vigente de una página leída por visión y el quitado que salía de ella; el fragmento de una
    página legible no lleva nada. Una consulta de lecturas con visión para toda la ficha."""
    sheet, one, two, document = card
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse("offers:sheet", args=[sheet.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    link = f'<a href="{original_of(document, 1)}">{LINK}</a>'
    mine = row_of(html, one)
    assert mine.count(NOTICE) == 1 and MARK in mine and link in mine
    other = row_of(html, two)  # el vigente es legible; el quitado sale de la página de visión
    assert other.count(NOTICE) == 1
    assert other.index(NOTICE) > other.index("Quitados:")
    assert html.count(NOTICE) == 2
    assert len(vision_queries(queries)) == 1


def test_the_history_of_a_row_marks_the_current_and_the_removed_fragment(
        client, card):  # noqa: F811
    """REQ-086, REQ-104, P3: la historia de la fila rotula el fragmento vigente de una página leída
    por visión y el quitado; el vigente de una página legible, no."""
    _, one, two, document = card
    link = f'<a href="{original_of(document, 1)}">{LINK}</a>'
    html = client.get(reverse("offers:entry_history", args=[one.pk])).content.decode()
    assert html.count(NOTICE) == 1 and link in html
    html = client.get(reverse("offers:entry_history", args=[two.pk])).content.decode()
    vigentes, quitados = html.split("Fragmentos quitados")
    assert NOTICE not in vigentes and quitados.count(NOTICE) == 1


def test_the_history_of_a_row_marks_what_the_system_proposed_and_each_change(
        client, card, operator_user):  # noqa: F811
    """REQ-086, REQ-104, P3: en la historia de la fila, lo que propuso el sistema y el antes y el
    después de un cambio llevan el aviso solo cuando su pasaje es de una página leída por visión;
    una consulta de lecturas para todos."""
    _, one, _, document = card
    by_vision = om.Passage.objects.get(text_origin="vision")
    plain = om.Passage.objects.filter(text_origin="pdf_text", reading__document__offer=
                                      document.offer, page=1).exclude(
        reading__document=document).get()
    # La persona corrigió el fragmento: ahora cita la página legible; el sistema había propuesto la
    # de visión.
    fixed = om.Fragment.objects.create(
        entry=one, order=2, passage=plain, char_start=plain.char_start, char_end=plain.char_end,
        text=plain.text, origin="persona", state="confirmado",
        proposed={"passage": by_vision.pk, "char_start": 0, "char_end": len(SEEN), "text": SEEN})
    event = audit.record(EventType.SHEET_CHANGE, outcome=EventOutcome.OK, channel=Channel.SCREEN,
                         user=operator_user, detail={"action": "corregir"})
    om.Change.objects.create(
        entry=one, fragment=fixed, action="corregir", user=operator_user, event=event,
        before={"fragment": fixed.pk, "passage": by_vision.pk, "page": 1, "text": SEEN},
        after={"fragment": fixed.pk, "passage": plain.pk, "page": 1, "text": plain.text})
    with CaptureQueriesContext(connection) as queries:
        html = client.get(reverse("offers:entry_history", args=[one.pk])).content.decode()
    proposed = html[html.index("Lo que propuso el sistema"):html.index("Historial</h2>")]
    assert proposed.count(NOTICE) == 1
    changes = html[html.index("Historial</h2>"):]
    antes, despues = changes.split("Después:")
    assert antes.count(NOTICE) == 1 and NOTICE not in despues
    # Vigentes: el fragmento de visión (1) y el corregido, de página legible (0); más el propuesto
    # (1) y el «antes» (1).
    assert html.count(NOTICE) == 3
    assert len(vision_queries(queries)) == 1
