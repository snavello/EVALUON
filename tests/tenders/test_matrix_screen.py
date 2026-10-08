"""Pantallas de la matriz: formulario "Proponer matriz", matriz con la franja de borrador,
cobertura y aviso de fin (REQ-025, REQ-028, REQ-030, REQ-032; plan 003, "Pantalla"; T-074).

Pliegos sintéticos y el doble del modelo con guion (`tests/tenders/scripted.py`); sin datos
de personas (P4). Las pantallas se prueban con el cliente de pruebas de Django.
"""

import html
import re
from datetime import date

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.services import matrix_page
from tests.conftest import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    ENTREGA,
    GARANTIA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    run_jobs,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db

BANNER = "BORRADOR INCOMPLETO"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    return html.unescape(response.content.decode())


def squash(text):
    return " ".join(text.split())


@pytest.fixture
def case(operator_user, script):
    """Un pliego de tres renglones leído y propuesto con un modelo que acierta: una
    garantía y un pago como requisitos y el renglón 2 como técnico."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when("Bolsa de diez kilogramos", item(technical=["2"]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return procedure, document, requested.run.version, requested.run


def matrix_url(version):
    return reverse("tenders:matrix", args=[version.pk])


def recorte(quote):
    reading = quote.segment.reading
    return reading.canonical_text[quote.char_start:quote.char_end]


# --- Matriz y franja (REQ-032) ------------------------------------------------------------------


def test_validated_version_has_no_banner_and_shows_who_and_when(client, operator_user,
                                                                 evaluator_user, case):
    """REQ-032: una versión validada sale sin la franja, con su versión, fecha y quién la
    validó."""
    _, _, version, _ = case
    version.status = m.VersionStatus.VALIDATED
    version.validated_at = timezone.now()
    version.validated_by = evaluator_user
    version.save()
    log_in(client, operator_user)
    page = text_of(client.get(matrix_url(version), follow=True))

    assert BANNER not in page
    assert "Validada" in page and evaluator_user.username in page
    assert version.validated_at.astimezone().strftime("%d/%m/%Y") in page


# --- Requisitos con su texto literal (REQ-025) ---------------------------------------------------


def test_wide_quote_is_marked_for_review(client, operator_user, script):
    """REQ-025: una cita que el modelo no copió bien queda como cita amplia y la pantalla
    la marca."""
    script.when(GARANTIA, item([("un texto que el pliego no tiene", "formal")]))
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    quote = m.RequirementQuote.objects.get(requirement__version=requested.run.version,
                                           requirement__category="formal")
    assert quote.quote_flag == "cita_amplia"
    log_in(client, operator_user)
    page = text_of(client.get(matrix_url(requested.run.version), follow=True))

    assert "Cita amplia, revisar" in page
    assert quote.text in page


# --- Pendientes (REQ-028) ------------------------------------------------------------------------


# --- Circulares y respuestas (REQ-031) -----------------------------------------------------------


# --- Cobertura ------------------------------------------------------------------------------------


def test_coverage_lists_every_stretch_with_disposition_origin_and_reason(
        client, operator_user, case):
    """REQ-028: la cobertura lista todos los tramos con su disposición, su origen y el
    motivo de descarte o de pendiente."""
    _, _, version, run = case
    log_in(client, operator_user)
    response = client.get(reverse("tenders:coverage", args=[version.pk]))
    page = text_of(response)

    segments = m.Segment.objects.filter(reading_id__in=[d["reading"] for d in run.documents])
    assert segments.count() == len(response.context["page"].rows) > 5
    assert f"Tramos del pliego: {segments.count()}" in page
    assert page.count("<tr class=\"coverage-") == segments.count()
    assert BANNER in page
    for disposition in run.dispositions.all():
        assert disposition.get_outcome_display() in page
        assert disposition.get_source_display() in page
    discarded = run.dispositions.filter(outcome="descartado").first()
    assert discarded is not None and discarded.get_discard_reason_display() in page
    pending = version.pending_items.get()
    assert f"Pendiente: {pending.get_reason_display()}" in page


# --- Páginas de las citas ------------------------------------------------------------------------


def test_rebuilt_canonical_text_matches_the_stored_one(case):
    """REQ-025: la página de una cita que abarca varias páginas se ubica en el texto
    canónico, que se arma de nuevo igual al guardado."""
    _, document, _, _ = case
    reading = document.readings.get()
    pages = matrix_page._Pages()
    canonical = pages._canonical_of(reading)

    assert canonical is not None and canonical.text == reading.canonical_text
    segment = m.Segment.objects.filter(reading=reading, text__contains="Rótulo").get()
    assert segment.page_start == 3
    # Un tramo que (en la prueba) abarca de la página 1 a la 3 ubica la cita en su línea.
    garantia = m.Segment.objects.get(reading=reading, text__contains="garantía del 5")
    garantia.page_start, garantia.page_end = 1, 3
    assert pages.of(garantia, garantia.char_start, garantia.char_end) == (1, 1)
    segment.page_start, segment.page_end = 3, 3
    assert pages.of(segment) == (3, 3)


# --- Pedir la matriz ------------------------------------------------------------------------------


@pytest.fixture
def read_only(operator_user, script):
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    return procedure


def request_url(procedure):
    return reverse("tenders:request_matrix", args=[procedure.pk])


def test_a_level_in_the_form_is_ignored(client, operator_user, read_only):
    """REQ-030: un nivel que llegue en el pedido se ignora: no hay niveles."""
    log_in(client, operator_user)
    client.post(request_url(read_only), {"level": "exigente"})

    run = m.MatrixRun.objects.get(procedure=read_only)
    assert (run.process, run.level) == ("completo", "")


def test_a_refused_request_shows_the_reason_and_queues_nothing(client, operator_user,
                                                                script):
    """REQ-030: un pedido rechazado (sin documentos) vuelve a la página con el motivo."""
    procedure = make_procedure(operator_user)
    log_in(client, operator_user)
    response = client.post(request_url(procedure), {})

    assert response.status_code == 200
    assert "no tiene ningún documento del pliego" in text_of(response)
    assert not m.MatrixRun.objects.exists()
    assert AuditEvent.objects.filter(event_type=EventType.MATRIX_REQUEST,
                                     outcome=Outcome.REJECTED).count() == 1


def test_the_print_page_shows_the_process_and_no_level(client, operator_user, case):
    """REQ-030: la impresión muestra el proceso y no un nivel."""
    _, _, version, _ = case
    log_in(client, operator_user)

    printed = text_of(client.get(reverse("tenders:print", args=[version.pk])))

    assert "Proceso</dt><dd>Completo" in printed
    assert "Nivel de revisión" not in printed


def test_user_without_commission_role_is_refused(client, no_commission_user, case):
    """Sin rol de la Comisión, ninguna de las páginas ni el pedido: 403."""
    procedure, _, version, _ = case
    log_in(client, no_commission_user)

    assert client.get(matrix_url(version), follow=True).status_code == 403
    assert client.get(reverse("tenders:coverage", args=[version.pk])).status_code == 403
    assert client.post(request_url(procedure), {}).status_code == 403


# --- Aviso de fin -----------------------------------------------------------------------------------


def test_finished_notice_is_only_for_who_asked_and_shows_on_every_page(
        client, operator_user, evaluator_user, script):
    """El aviso es de quien pidió, y sale en cualquier página con la base común."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    log_in(client, evaluator_user)
    other = text_of(client.get(reverse("tenders:procedures")))
    client.logout()

    log_in(client, operator_user)
    page = text_of(client.get(reverse("queries:screen")))

    assert "terminó" not in other
    assert "La lectura de «Pliego sintético»" in page


def test_failed_job_notice_says_it_failed_and_why(client, operator_user, script):
    """El aviso de un pedido fallido lo distingue del terminado y muestra el motivo."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    jobs.mark_seen(operator_user, [j.pk for j in m.Job.objects.all()])
    script.fail("timeout")
    log_in(client, operator_user)
    client.post(request_url(procedure), {})
    run_jobs()
    job = m.Job.objects.get(kind="propose_matrix")
    assert job.status == "failed"

    page = text_of(client.get(reverse("tenders:procedures"), follow=True))

    assert "falló" in page and job.error in page
    assert "notice-failed" in page
    assert "Ver la matriz" not in page


# --- Sin direcciones externas y navegación ----------------------------------------------------------


def test_no_page_refers_to_an_external_address(client, operator_user, case):
    """P4: ninguna página de la matriz referencia direcciones externas."""
    procedure, _, version, _ = case
    log_in(client, operator_user)
    urls = [
        reverse("tenders:procedure", args=[procedure.pk]),
        matrix_url(version),
        reverse("tenders:coverage", args=[version.pk]),
    ]
    for url in urls:
        body = client.get(url).content.decode()
        assert not re.search(r"(https?:)?//[a-z0-9]", body, re.IGNORECASE), url
    css = open("evaluon/static/tenders/matrix.css", encoding="utf8").read()
    assert "http" not in css and "@import" not in css and "url(" not in css


def test_site_nav_has_a_style():
    """La navegación del encabezado tiene estilo en la hoja común."""
    css = open("evaluon/static/css/evaluon.css", encoding="utf8").read()
    assert ".site-nav" in css
