"""La evaluación con la lectura con visión de las páginas dudosas (REQ-052, REQ-053, REQ-054;
plan 004, enmienda 2026-10-06; ADR-0038, ADR-0041; T-160). Una página y una foto inventadas
(P4); el modelo es un guion (`fakes.py`)."""

import pytest
from django.test import override_settings
from django.urls import reverse

from evaluon.assessment.services import evaluate
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.offers import vision
from evaluon.offers.services import offers as offers_service
from tests.assessment.fakes import (  # noqa: F401 - `model` es una fixture
    VISION_DATA,
    make_read_document,
    model,
    says,
)
from tests.assessment.test_evaluate import (
    DECLARATION,
    cumple_declaration,
    number_of,
    offer_cites,
    requirement_of,
    results_of,
    run_all,
)
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db

SEEN = f"CONSTANCIA INVENTADA\n{DECLARATION}, según la planilla 7."


@pytest.fixture
def scanned(procedure, operator_user, fake_ai):
    """Una oferta con un documento de dos páginas: la primera legible; la segunda, un escaneo
    ilegible que solo la visión puede leer."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Oferente escaneado",
                                          channel=Channel.COMMAND)
    make_read_document(offer, operator_user, "pagare.pdf", [
        ("legible", "Nota de presentación de la oferta."), ("ilegible", "")])
    return offer


def declaration_result(run, procedure):
    return results_of(run)[number_of(procedure, "declaración jurada")]


def test_a_citation_on_a_vision_page_is_equal_to_the_canonical_slice_of_the_vision_reading(
        scanned, operator_user, procedure, model):
    """REQ-053: la cita sobre una página leída por visión es igual al recorte del canónico de
    la lectura por visión (ADR-0038), y el resultado cumple con su cita."""
    model.sees(lambda seen: SEEN)
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs[0], procedure)
    assert result.outcome == "cumple"
    citation = offer_cites(result)[0]
    reading = scanned.documents.get().readings.order_by("-sequence").first()
    assert reading.sequence == 2 and citation.reading == reading and citation.page == 2
    assert citation.text == reading.canonical_text[citation.char_start:citation.char_end]
    assert citation.text == DECLARATION
    assert vision.vision_pages(reading) == {2}


def test_an_invented_quote_on_a_vision_page_degrades_to_undetermined(
        scanned, operator_user, procedure, model):
    """REQ-053: una cita que no está en el canónico de la lectura por visión no se ubica y el
    resultado no concluye: "no determinado"."""
    model.sees(lambda seen: SEEN)
    model.evaluates(lambda call: says("cumple", (call.alias_with(DECLARATION),
                                                  "Declaro que tengo un seguro inventado"))
                    if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs[0], procedure)
    assert result.outcome == "no_determinado" and not offer_cites(result)
    assert any(a["type"] == "cita_no_ubicada" for a in runs[0].anomalies)


def test_the_evaluation_text_reads_the_vision_page_as_read_and_the_run_records_it(
        scanned, operator_user, procedure, model):
    """REQ-054: la página dudosa se reemplaza por su transcripción en el texto por página; no
    figura "no se pudo leer"; el registro de la evaluación dice qué lectura por visión usó."""
    model.sees(lambda seen: SEEN)
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure)
    run = runs[0]
    document = scanned.documents.get()
    reading = document.readings.order_by("-sequence").first()
    sent = model.calls[0].documents
    assert any("--- página 2 ---" in text and DECLARATION in text for text in sent.values())
    assert not any("no se pudo leer" in text for text in sent.values())
    record = run.documents[0]
    assert record["reading"] == reading.pk and record["sha256"] == reading.canonical_sha256
    assert record["vision_pages"] == [2] and record["unread_pages"] == []
    assert run.counts["vision"]["read"] == 1 and run.counts["vision"]["readings"] == [reading.pk]
    assert run.counts["vision"]["citations"] >= 1
    assert AuditEvent.objects.get(event_type=EventType.EVAL_BUILD).detail[
        "documents"][0]["vision_pages"] == [2]
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_READ,
                                     detail__action="vision").count() == 1
    # La lectura anterior sigue ahí.
    assert document.readings.filter(sequence=1).exists()
    assert not run.results.get(requirement=requirement_of(procedure, "declaración jurada")
                               ).unread_pages_warning


def test_a_page_the_vision_could_not_read_stays_unread_and_warns(
        scanned, operator_user, procedure, model):
    """REQ-052 y P3: una transcripción con demasiado `[ilegible]` deja la página "no se pudo
    leer" y el resultado lleva el aviso de páginas sin leer."""
    model.sees(lambda seen: "[ilegible] [ilegible] [ilegible] firma")
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure)
    sent = model.calls[0].documents
    assert any("--- página 2: no se pudo leer ---" in text for text in sent.values())
    assert runs[0].documents[0]["unread_pages"] == [2] and runs[0].documents[0][
        "vision_pages"] == []
    assert runs[0].counts["vision"]["discarded"] == 1


@pytest.mark.parametrize("settings_change", [
    {"ASSESSMENT_VISION_MAX_PAGES": 0}, {"GENERATION_BATCH_MMPROJ_FILE": ""}])
def test_without_vision_the_flow_is_the_same_as_before(
        scanned, operator_user, procedure, model, settings_change):
    """REQ-052: con el tope en 0 o sin proyector el flujo sigue igual: ningún pedido con
    imagen, la lectura de siempre y la página ilegible como "no se pudo leer"."""
    model.sees(lambda seen: SEEN)
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    with override_settings(**settings_change):
        _, runs = run_all(operator_user, procedure)
    assert not model.vision_calls
    assert scanned.documents.get().readings.count() == 1
    assert runs[0].documents[0]["unread_pages"] == [2]
    assert runs[0].counts["vision"]["disabled"] is True


def test_an_engine_that_does_not_take_images_does_not_stop_the_evaluation(
        scanned, operator_user, procedure, model):
    """REQ-052: si el motor rechaza la imagen (sin `--mmproj`) la evaluación sigue con la
    lectura que hay y deja la anomalía."""
    from evaluon.ai import ServiceUnavailableError

    def refuse(seen):
        raise ServiceUnavailableError("generation_batch: sin proyector", service="generation")

    model.sees(refuse)
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure)
    assert any(a["type"] == "vision_con_errores" for a in runs[0].anomalies)
    assert runs[0].documents[0]["unread_pages"] == [2]
    assert scanned.documents.get().readings.count() == 1


def test_the_vision_runs_once_per_page_across_evaluations(
        scanned, operator_user, procedure, model):
    """REQ-052: una segunda evaluación no vuelve a pedir las páginas ya leídas por visión."""
    model.sees(lambda seen: SEEN)
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    asked = len(model.vision_calls)
    _, runs = run_all(operator_user, procedure)
    assert asked == 1 and len(model.vision_calls) == 1
    assert runs[0].counts["vision"]["attempted"] == 0
    assert runs[0].documents[0]["vision_pages"] == [2]


def test_a_photo_of_a_table_is_read_by_vision_and_its_rows_can_be_cited(
        procedure, operator_user, model, fake_ai):
    """REQ-053, REQ-054: la foto de una tabla (inventada) se transcribe fila por fila y la
    cita de una fila es igual al recorte del canónico."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Oferente de la foto",
                                          channel=Channel.COMMAND)
    make_read_document(offer, operator_user, "cuadro.png", [("legible", "Cuadro 3150")],
                       file_format="png", content=(VISION_DATA / "foto-tabla.png").read_bytes())
    row = "1 | Resma de papel A4 75 g | 100 | $ 3.150,00"
    model.sees(lambda seen: f"CUADRO DE PRECIOS INVENTADO\n{row}\n2 | Carpeta oficio | 40 | $ 820,50")
    model.evaluates(lambda call: says("cumple", call.quote(row))
                    if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs[0], procedure)
    citation = offer_cites(result)[0]
    assert citation.text == row
    assert citation.reading.canonical_text[citation.char_start:citation.char_end] == row
    assert model.vision_calls[0].size[0] > 500


# --- Pantalla ----------------------------------------------------------------------------------


@pytest.fixture
def seen_page(scanned, operator_user, procedure, model, client):
    model.sees(lambda seen: SEEN)
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    log_in(client, operator_user)
    requirement = requirement_of(procedure, "declaración jurada")
    return scanned, requirement


def test_the_screen_labels_the_citation_as_read_by_vision_with_the_image_and_the_original(
        seen_page, client):
    """REQ-053, P3: la pantalla rotula "leída por visión", marca el resultado, muestra la
    imagen de la página y el enlace al original."""
    offer, requirement = seen_page
    response = client.get(reverse("assessment:pair", args=[offer.pk, requirement.pk]))
    assert response.status_code == 200
    page = text_of(response)
    assert "leída por visión" in page and "Compare con el original antes de confirmar" in page
    assert DECLARATION in page
    document = offer.documents.get()
    html = response.content.decode()
    image = reverse("assessment:vision_page",
                    args=[offer.pk, requirement.pk, document.pk, 2])
    assert f'src="{image}"' in html
    assert f"{reverse('offers:document_original', args=[document.pk])}#page=2" in html
    picture = client.get(image)
    assert picture.status_code == 200 and picture["Content-Type"] == "image/jpeg"
    assert picture.content[:2] == b"\xff\xd8"


def test_the_screen_does_not_label_a_result_without_vision_pages(
        offer, operator_user, procedure, model, client):
    """REQ-053: una cita sobre una página que no es de visión no lleva el rótulo, y su imagen
    no se sirve."""
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    log_in(client, operator_user)
    requirement = requirement_of(procedure, "declaración jurada")
    response = client.get(reverse("assessment:pair", args=[offer.pk, requirement.pk]))
    assert "leída por visión" not in text_of(response)
    document = offer.documents.get(file_name="oferta.pdf")
    image = reverse("assessment:vision_page", args=[offer.pk, requirement.pk, document.pk, 1])
    assert client.get(image).status_code == 404


def test_the_page_image_is_only_served_for_a_role_of_the_commission(
        seen_page, client, no_commission_user):
    """Roles: sin rol de la Comisión no se sirve la imagen de una página de la oferta."""
    offer, requirement = seen_page
    document = offer.documents.get()
    client.logout()
    log_in(client, no_commission_user)
    image = reverse("assessment:vision_page", args=[offer.pk, requirement.pk, document.pk, 2])
    assert client.get(image).status_code == 403


def test_the_pair_page_service_marks_the_result_cited_on_a_vision_page(
        seen_page, operator_user):
    """REQ-053: `pair_page` marca el resultado y sus citas cuando alguna cae en una página
    leída por visión."""
    offer, requirement = seen_page
    page = evaluate.pair_page(operator_user, offer.pk, requirement.pk)
    assert page.by_vision and page.offer_citations[0].by_vision
