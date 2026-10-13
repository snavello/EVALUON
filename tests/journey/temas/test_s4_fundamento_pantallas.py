"""El fundamento se ve en las pantallas de preguntas e informe técnico de la sección «Evaluación y
dictamen», no solo en la celda y el detalle del par (REQ-103, REQ-104; P3; dictamen de la 015,
hallazgos 1 y 2; plan 015, T-264, barrido de las pantallas).

- Preguntas e informe técnico: la cita de una página leída por visión lleva la marca «leída por
  visión», el aviso de comparar con el original y el enlace al original (ADR-0041).
- Preguntas: el dato del Portal que motiva la pregunta lleva el enlace a su página y la fecha en
  que se tomó (constitución 1.3, ADR-0053).
Los descartes están en `test_s4_descartes_fundamento.py`. Los resultados se guardan directo, sin el
modelo; todo el material es inventado (P4)."""

import hashlib

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers import models as om
from tests.assessment.test_matrix import evaluated, three  # noqa: F401 - fixtures de `asked`
from tests.assessment.test_result_fundamento import (  # noqa: F401 - `portal` es fixture
    PAGE_URL,
    SHOWN,
    portal,
)
from tests.assessment.test_technical_report import offers  # noqa: F401 - fixture
from tests.journey.conftest import make_run
from tests.journey.temas.test_s4_preguntas import asked, block as questions_block  # noqa: F401
from tests.journey.temas.test_s4_propuesta import log_in, page

pytestmark = pytest.mark.django_db

NOTICE = "Compare con el original antes de confirmar"
MARK = "leída por visión"


# --- Ayudas ----------------------------------------------------------------------------------


def vision_reading(document, pages=(2,)):
    """Una lectura nueva del documento cuyas `pages` se leyeron por visión (informe de la
    lectura: `report["vision"]`, ADR-0041)."""
    text = "Texto inventado de una página leída por visión."
    return om.Reading.objects.create(
        document=document, sequence=document.readings.count() + 1, pages={"pages": []},
        canonical_text=text, canonical_sha256=hashlib.sha256(text.encode()).hexdigest(),
        tool_versions={},
        report={"vision": {"pages": [{"page": p, "outcome": "read"} for p in pages]}})


def cite_offer(result, order, reading, page_number):
    """Una cita de la oferta sobre la página `page_number` de `reading`."""
    return am.Citation.objects.create(
        result=result, order=order, kind=am.CitationKind.OFERTA, document=reading.document,
        reading=reading, page=page_number, char_start=0, char_end=30,
        text=reading.canonical_text[:30])


def cite_portal(result, order, item, text="Garantía: tipo inventado, monto 1000.00"):
    """Un dato del Portal citado, con el ítem de origen `item`."""
    return am.Citation.objects.create(
        result=result, order=order, kind=am.CitationKind.PORTAL, portal_item=item,
        portal_kind=am.PortalKind.GARANTIA, label="Portal: acta de apertura", text=text)


def evaluate_with(user, procedure, offer, requirement_, outcome, *cites):
    """Una evaluación de `offer` con un solo resultado, con las citas dadas: `("oferta", lectura,
    página)` o `("portal", ítem)`."""
    version = procedure.matrix_versions.get(number=1)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[offer.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=user)
    run = make_run(request, offer, version)
    result = am.Result.objects.create(
        run=run, offer=offer, requirement=requirement_, outcome=outcome,
        exigence=am.Exigence.CONDICION, explanation="Inventado.")
    for order, cite in enumerate(cites, start=1):
        if cite[0] == "oferta":
            cite_offer(result, order, cite[1], cite[2])
        else:
            cite_portal(result, order, cite[1])
    return result


def original_of(document, page_number):
    return f"{reverse('offers:document_original', args=[document.pk])}#page={page_number}"


def section(html, anchor, tag):
    """Desde `anchor` hasta la siguiente etiqueta `tag` (o el final)."""
    start = html.index(f'id="{anchor}"')
    end = html.find(tag, start + 1)
    return html[start:] if end < 0 else html[start:end]


# --- Preguntas -------------------------------------------------------------------------------


@pytest.fixture
def asked_with_sources(asked, portal, operator_user, client):  # noqa: F811
    """La pregunta abierta (oferta C, garantía) cita una página legible, una leída por visión y el
    dato del Portal; la respondida (oferta B) cita solo una página legible."""
    open_, done, _ = asked
    document = open_.offer.documents.first()
    cite_offer(open_.result, 10, document.readings.get(), 1)
    cite_offer(open_.result, 11, vision_reading(document), 2)
    cite_portal(open_.result, 12, portal)
    log_in(client, operator_user)
    return open_, done


def test_a_question_marks_only_the_citation_read_by_vision(
        client, asked_with_sources, procedure):
    """REQ-104, REQ-053, P3: en «Preguntas», la cita de una página leída por visión lleva la
    marca, el aviso y el enlace al original; la de una página legible y la pregunta que no cita
    ninguna leída por visión no los llevan."""
    open_, done = asked_with_sources
    html = questions_block(client, procedure)
    line = section(html, f"preg-{open_.pk}", '<tbody class="linea"')
    document = open_.offer.documents.first()
    original = original_of(document, 2)
    assert line.count(NOTICE) == 1 and line.count(MARK) == 1
    assert f'<a href="{original}">Abrir el original</a>' in line
    other = section(html, f"preg-{done.pk}", '<tbody class="linea"')
    assert NOTICE not in other and MARK not in other


def test_a_question_gives_the_portal_page_and_the_date_of_its_datum(
        client, asked_with_sources, procedure):
    """REQ-103, P3: en «Preguntas», el dato del Portal que motiva la pregunta lleva el enlace a su
    página y la fecha en que se tomó."""
    open_, _ = asked_with_sources
    line = section(questions_block(client, procedure), f"preg-{open_.pk}",
                   '<tbody class="linea"')
    assert "Dato del Portal: Garantía: tipo inventado, monto 1000.00" in line
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in line
    assert f"página consultada el {SHOWN}" in line


# --- Informe técnico -------------------------------------------------------------------------


def report_proposal(offer, user, *, quote, page_number, reading_pages, item=1):
    """Un informe técnico cargado en `offer` y la propuesta del sistema para el renglón `item`,
    con la cita en la página `page_number` de su lectura (hecho `eval_build`, como lo deja
    `technical_report.propose`)."""
    sha = hashlib.sha256(f"informe-{offer.pk}".encode()).hexdigest()
    document = om.Document.objects.create(
        offer=offer, kind=om.DocumentKind.INFORME_TECNICO, title="Informe técnico · informe",
        file_name="informe.pdf", file_format="pdf", file_size=1, file_sha256=sha, loaded_by=user)
    om.DocumentFile.objects.create(document=document, content=b"%PDF-sintetico")
    text = f"{quote} (texto canónico inventado del informe)"
    reading = om.Reading.objects.create(
        document=document, sequence=1, pages={"pages": []}, canonical_text=text,
        canonical_sha256=hashlib.sha256(text.encode()).hexdigest(), tool_versions={},
        report=({"vision": {"pages": [{"page": p, "outcome": "read"} for p in reading_pages]}}
                if reading_pages else {}))
    audit.record(
        EventType.EVAL_BUILD, outcome=EventOutcome.OK, channel=Channel.SCREEN, user=user,
        detail={"kind": "technical_proposal", "offer": offer.pk, "document": document.pk,
                "document_title": document.title,
                "items": {str(item): {"verdict": "apto", "quote": quote, "page": page_number,
                                      "reading": reading.pk, "motive": ""}}})
    return document


def test_the_report_quote_is_marked_only_when_its_page_was_read_by_vision(
        client, offers, procedure, evaluator_user):  # noqa: F811
    """REQ-104, REQ-053, P3: en «Informe técnico», la frase del informe que sale de una página
    leída por visión lleva la marca, el aviso y el enlace al original; la de una página legible
    no."""
    a, b = offers
    seen = report_proposal(a, evaluator_user, quote="Oferente A - Renglón 1: apto.",
                           page_number=2, reading_pages=(2,))
    report_proposal(b, evaluator_user, quote="Oferente B - Renglón 1: apto.",
                    page_number=2, reading_pages=())
    log_in(client, evaluator_user)
    html = section(page(client, procedure), "s4-informe", "</section>")
    row = html[html.index("Oferente A - Renglón 1: apto."):]
    mine = row[:row.index("</td>")]
    assert mine.count(NOTICE) == 1 and MARK in mine
    assert f'<a href="{original_of(seen, 2)}">Abrir el original</a>' in mine
    cell = html[html.index("Oferente B - Renglón 1: apto."):]
    theirs = cell[:cell.index("</td>")]
    assert NOTICE not in theirs and MARK not in theirs
