"""Imprimir y exportar la matriz a PDF con la leyenda de borrador (REQ-032; plan 003,
"Salidas: impresión y PDF"; ADR-0020; principio P4; T-086).

Matriz sintética de varias páginas (los requisitos de un pliego de tres renglones, copiados
hasta pasar de una página). El texto de cada página del PDF se lee con pdfplumber.
"""

import hashlib
import html
import io
import socket

import pdfplumber
import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import export
from evaluon.tenders.services import consequences, review
from evaluon.tenders.services import validation as validation_service
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import (
    GARANTIA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db

LEGEND = "BORRADOR INCOMPLETO"
COPIES = 25


@pytest.fixture
def case(operator_user, script):
    """Un borrador con una matriz larga: los requisitos propuestos y copias de ellos."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when("Bolsa de diez kilogramos", item(technical=["2"]))
    requested, job = propose(operator_user, procedure, level="alta")
    assert job.status == "done", job.error
    version = requested.run.version
    originals = list(version.requirements.filter(category="economico").order_by("number"))
    number = version.requirements.count()
    for _ in range(COPIES):
        for original in originals:
            quotes = list(original.quotes.all())
            number += 1
            original.pk = None
            original.number = number
            original.save()
            for quote in quotes:
                quote.pk = None
                quote.requirement = original
                quote.save()
    return version


def finish_review(evaluator, version):
    for pending in version.pending_items.filter(resolved_at__isnull=True):
        review.resolve_pending(evaluator, pending.pk)
    for requirement in version.requirements.exclude(state="quitado"):
        consequences.choose(evaluator, requirement.pk, consequence_type="aprobar_igual",
                            note="Motivo de prueba")


@pytest.fixture
def validated(case, evaluator_user):
    finish_review(evaluator_user, case)
    return validation_service.validate(evaluator_user, case.pk)


def pdf_pages(data):
    with pdfplumber.open(io.BytesIO(data)) as document:
        return [" ".join((page.extract_text() or "").split()) for page in document.pages]


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


# --- La leyenda en cada página (REQ-032) --------------------------------------------------------


def test_every_page_of_a_draft_pdf_has_the_legend(operator_user, case):
    """REQ-032: cada página del PDF de un borrador muestra "BORRADOR INCOMPLETO" y
    "Página N de M"."""
    data, name = export.export_pdf(operator_user, case.pk)

    pages = pdf_pages(data)
    assert len(pages) >= 3
    for number, text in enumerate(pages, start=1):
        assert LEGEND in text, f"falta la leyenda en la página {number}"
        assert f"Página {number} de {len(pages)}" in text
    assert name.endswith("-v1-borrador.pdf") and name.startswith("matriz-SINT-MAT-")


def test_no_page_of_a_validated_pdf_has_the_legend_and_all_show_the_validation(
        operator_user, evaluator_user, validated):
    """REQ-032: el PDF de la validada no lleva la leyenda; cada página muestra versión,
    fecha y evaluador."""
    data, name = export.export_pdf(operator_user, validated.pk)

    pages = pdf_pages(data)
    assert len(pages) >= 3
    date_text = validated.validated_at.astimezone().strftime("%d/%m/%Y")
    for number, text in enumerate(pages, start=1):
        assert LEGEND not in text
        assert f"Matriz validada · versión {validated.number}" in text
        assert f"validada el {date_text} por {evaluator_user.username}" in text
        assert f"Página {number} de {len(pages)}" in text
    assert "borrador" not in name


def test_a_discarded_version_carries_the_legend(operator_user, evaluator_user, case):
    """REQ-032: una versión descartada no está validada: lleva la leyenda."""
    validation_service.discard(evaluator_user, case.pk)

    data, _ = export.export_pdf(operator_user, case.pk)

    assert all(LEGEND in text for text in pdf_pages(data))


def test_a_version_opened_over_another_exports_without_a_run(
        operator_user, evaluator_user, validated):
    """REQ-032: una versión abierta sobre otra no tiene propuesta propia; igual se exporta
    con la leyenda."""
    new = validation_service.open_new_version(operator_user, validated.procedure_id)
    assert new.run_id is None

    data, _ = export.export_pdf(operator_user, new.pk)

    assert all(LEGEND in text for text in pdf_pages(data))


# --- Vista de impresión ---------------------------------------------------------------------------


def test_print_view_of_a_draft_has_the_fixed_legend_and_the_print_button(
        client, operator_user, case):
    """REQ-032: la vista de impresión de un borrador tiene la leyenda fija y el botón
    "Imprimir"; sin formularios de edición."""
    log_in(client, operator_user)

    response = client.get(reverse("tenders:print", args=[case.pk]))

    page = html.unescape(response.content.decode())
    assert response.status_code == 200
    assert 'class="fixed-mark draft"' in page and LEGEND in page
    assert 'id="print-button"' in page and "Imprimir" in page
    assert reverse("tenders:pdf", args=[case.pk]) in page
    assert "<form" not in page and "<script>" not in page
    assert "tenders/print.css" in page
    assert AuditEvent.objects.filter(event_type=EventType.MATRIX_EXPORT).count() == 0


def test_print_view_of_a_validated_version_shows_the_validation_without_legend(
        client, operator_user, evaluator_user, validated):
    """REQ-032: la vista de impresión de la validada no lleva la leyenda y muestra versión,
    fecha y evaluador."""
    log_in(client, operator_user)

    page = html.unescape(
        client.get(reverse("tenders:print", args=[validated.pk])).content.decode())

    assert LEGEND not in page
    assert "Matriz validada · versión 1" in page
    assert f"por {evaluator_user.username}" in page


def test_matrix_page_has_the_print_and_pdf_buttons(client, operator_user, case):
    """REQ-032: la página de la matriz ofrece "Vista de impresión" y "Exportar PDF"."""
    log_in(client, operator_user)

    page = html.unescape(
        client.get(reverse("tenders:matrix", args=[case.pk])).content.decode())

    assert reverse("tenders:print", args=[case.pk]) in page and "Vista de impresión" in page
    assert reverse("tenders:pdf", args=[case.pk]) in page and "Exportar PDF" in page


# --- El PDF no pide nada afuera (P4) ---------------------------------------------------------------


def test_an_external_address_fails_the_generation_instead_of_being_fetched(
        operator_user, case):
    """REQ-032, P4: una plantilla con una dirección externa hace fallar la generación; no
    se busca."""
    html_text, _ = export.render_html(operator_user, case.pk, pdf=True)
    bad = html_text.replace("</body>", '<img src="http://example.invalid/x.png"></body>')

    with pytest.raises(export.ExportFailed) as error:
        export.html_to_pdf(bad)

    assert error.value.reason == "external_resource"
    assert "example.invalid" in str(error.value)


def test_a_local_file_outside_the_print_sheet_is_refused_too(operator_user, case):
    """P4: tampoco se lee un archivo del disco que no sea la hoja de impresión."""
    html_text, _ = export.render_html(operator_user, case.pk, pdf=True)
    bad = html_text.replace("</body>", '<img src="file:///etc/passwd"></body>')

    with pytest.raises(export.ExportFailed):
        export.html_to_pdf(bad)


def test_generating_the_pdf_opens_no_network_connection(operator_user, case, monkeypatch):
    """REQ-032, P4: con toda conexión de red prohibida, el PDF se genera igual."""
    def forbidden(*args, **kwargs):
        raise AssertionError("se intentó abrir una conexión")

    html_text, _ = export.render_html(operator_user, case.pk, pdf=True)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)

    data, pages = export.html_to_pdf(html_text)

    assert data.startswith(b"%PDF") and pages >= 3


def test_the_fetcher_serves_only_the_print_sheet():
    """ADR-0020: el `URLFetcher` entrega `print.css` y rechaza el resto."""
    fetcher = export.LocalOnlyFetcher()

    assert b"@page" in fetcher.fetch(export.PRINT_CSS_URL).read()
    for url in ("https://example.invalid/a.css", "file:///evaluon-print/otra.css",
                "data:text/css,body{}"):
        with pytest.raises(export.FatalURLFetchingError):
            fetcher.fetch(url)


# --- Registro y descarga (P6) ----------------------------------------------------------------------


def test_the_export_is_recorded_with_the_hash_of_the_delivered_file(
        client, operator_user, case):
    """REQ-032, P6: la descarga deja `matrix_export` con versión, estado, leyenda, páginas
    y la huella del archivo entregado."""
    log_in(client, operator_user)

    response = client.get(reverse("tenders:pdf", args=[case.pk]))

    body = b"".join(response.streaming_content)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]
    assert "-v1-borrador.pdf" in response["Content-Disposition"]
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_EXPORT)
    assert event.outcome == Outcome.OK and event.user == operator_user
    assert event.detail["version"] == case.pk and event.detail["status"] == "draft"
    assert event.detail["legend"] is True
    assert event.detail["pages"] == len(pdf_pages(body))
    assert event.detail["sha256"] == hashlib.sha256(body).hexdigest()


def test_the_export_of_a_validated_version_records_no_legend(operator_user, validated):
    """REQ-032, P6: la exportación de la validada queda registrada sin leyenda."""
    export.export_pdf(operator_user, validated.pk)

    event = AuditEvent.objects.get(event_type=EventType.MATRIX_EXPORT)
    assert event.detail["status"] == "validated" and event.detail["legend"] is False


def test_a_failed_generation_is_recorded_and_answers_500(
        client, operator_user, case, monkeypatch):
    """P6: si el generador falla, la persona recibe un aviso y queda el hecho `failed`."""
    def broken(html_text):
        raise export.ExportFailed("falla de prueba")

    monkeypatch.setattr(export, "html_to_pdf", broken)
    log_in(client, operator_user)

    response = client.get(reverse("tenders:pdf", args=[case.pk]))

    assert response.status_code == 500
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_EXPORT)
    assert event.outcome == Outcome.FAILED and event.detail["reason"] == "render_failed"


def test_users_without_commission_role_get_no_print_view_and_no_pdf(
        client, no_commission_user, case):
    """Sin rol de la Comisión, ni la vista de impresión ni el PDF: 403, sin hecho de
    exportación."""
    log_in(client, no_commission_user)

    assert client.get(reverse("tenders:print", args=[case.pk])).status_code == 403
    assert client.get(reverse("tenders:pdf", args=[case.pk])).status_code == 403
    assert not AuditEvent.objects.filter(event_type=EventType.MATRIX_EXPORT).exists()


def test_the_service_rejects_a_user_without_role(no_commission_user, case):
    """El servicio comprueba el rol antes de generar nada."""
    with pytest.raises(RoleRejected):
        export.export_pdf(no_commission_user, case.pk)


def test_a_missing_version_answers_404(client, operator_user):
    """Una versión inexistente responde 404 en las dos salidas."""
    log_in(client, operator_user)

    assert client.get(reverse("tenders:pdf", args=[999999])).status_code == 404
    assert client.get(reverse("tenders:print", args=[999999])).status_code == 404


# --- Consecuencias en la impresión y el PDF (REQ-032, plan 003 "Salidas") ------------------------


def _suggest(requirement, kind):
    from evaluon.tenders import models as m
    quote = requirement.quotes.first()
    ground = {"source": "pliego", "reading": quote.segment.reading_id,
              "segment": quote.segment_id, "key": quote.segment.key,
              "char_start": quote.char_start, "char_end": quote.char_end}
    return m.Consequence.objects.create(requirement=requirement, consequence_type=kind,
                                        grounds=[ground], origin="sistema")


def _first_requirement(case):
    return case.requirements.filter(category="economico").order_by("number").first()


def _print_text(client, user, version):
    log_in(client, user)
    return html.unescape(
        client.get(reverse("tenders:print", args=[version.pk])).content.decode())


def test_print_without_a_chosen_consequence_shows_the_suggested_ones_with_their_place(
        client, operator_user, case):
    """REQ-032: sin consecuencia elegida, la impresión muestra las sugeridas con su
    fundamento resumido por la ubicación, sin el texto completo ni formularios."""
    requirement = _first_requirement(case)
    _suggest(requirement, "desestimacion")
    _suggest(requirement, "consultar_oferente")

    page = _print_text(client, operator_user, case)

    assert "Desestimación sin posibilidad de subsanar" in page
    assert "Consultar al oferente" in page
    assert "Sugerida por el sistema · Sin elegir" in page
    assert "Fundamento en el pliego" in page
    assert page.count('<span class="place">Pliego sintético · Página 1') >= 2
    assert "Aceptar esta sugerencia" not in page and "Elegir la consecuencia" not in page


def test_print_with_a_chosen_consequence_shows_only_that_one_with_who_when_and_why(
        client, operator_user, evaluator_user, case):
    """REQ-032: con consecuencia elegida, solo esa, con su motivo, quién y cuándo."""
    requirement = _first_requirement(case)
    _suggest(requirement, "desestimacion")
    _suggest(requirement, "consultar_oferente")
    consequences.choose(evaluator_user, requirement.pk, consequence_type="aprobar_igual",
                        note="Motivo elegido de prueba")

    page = _print_text(client, operator_user, case)
    block = page.split(f"Requisito {requirement.number} ")[1].split("<article")[0]

    assert "Aprobar de todas maneras" in block
    assert f"Elegida por {evaluator_user.username} el" in block
    assert "Motivo: Motivo elegido de prueba" in block
    assert "Desestimación sin posibilidad" not in block
    assert "Consultar al oferente" not in block


def test_the_screen_still_shows_all_the_options_and_the_choice_form(
        client, evaluator_user, case):
    """La pantalla de la matriz no cambia: todas las opciones y el formulario de elección."""
    requirement = _first_requirement(case)
    _suggest(requirement, "desestimacion")
    _suggest(requirement, "consultar_oferente")
    log_in(client, evaluator_user)

    page = html.unescape(
        client.get(reverse("tenders:matrix", args=[case.pk])).content.decode())

    assert "Desestimación sin posibilidad de subsanar" in page
    assert "Consultar al oferente" in page
    assert "Aceptar esta sugerencia" in page and "Elegir la consecuencia" in page
