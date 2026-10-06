"""Página mínima de un par, en solo lectura (REQ-052, REQ-053, REQ-055, REQ-060; plan 004,
"Revisión y decisión" y "Pantalla"; T-150). Caso chico inventado; el modelo es un guion."""

import pytest
from django.urls import reverse

from evaluon.assessment.services import evaluate
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import DECLARATION, number_of, requirement_of, run_all
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db


def page_url(offer, procedure, needle):
    return reverse("assessment:pair", args=[offer.pk, requirement_of(procedure, needle).pk])


@pytest.fixture
def evaluated(offer, operator_user, procedure, model):
    def function(call):
        if "declaración jurada" in call.requirement:
            return says("cumple", call.quote(DECLARATION), explanation="Lo declara el oferente.")
        if "sesenta días" in call.requirement:
            return says("no_consta", exigence="condicion", question="¿Desde cuándo corre?")
        if "libre deuda" in call.requirement:
            return says("no_determinado", external=True)
        if "inscripción" in call.requirement:
            return says("no_consta", exigence="documento")

    model.evaluates(function)
    return run_all(operator_user, procedure)


def test_the_page_shows_the_proposal_with_its_quotes_and_the_link_to_the_original(
        client, evaluated, offer, procedure, operator_user):
    """REQ-053: requisito del pliego, texto de la oferta con documento y página (enlace al
    original en esa página), explicación del sistema rotulada y aviso de que decide la
    Comisión."""
    log_in(client, operator_user)
    response = client.get(page_url(offer, procedure, "declaración jurada"))
    assert response.status_code == 200
    page = text_of(response)
    assert "propuesta del sistema" in page and "La decisión es de la Comisión" in page
    assert "Cumple" in page
    assert "Presentar la declaración jurada" in page  # el texto del pliego
    assert DECLARATION in page  # el texto literal de la oferta
    assert "oferta.pdf · página 1" in page
    document = offer.documents.get(file_name="oferta.pdf")
    assert f"{reverse('offers:document_original', args=[document.pk])}#page=1" in \
        response.content.decode()
    assert "Explicación del sistema" in page and "Lo declara el oferente." in page
    assert "no es texto de la oferta ni del pliego" in page


def test_a_missing_document_is_shown_with_the_cita_of_the_pliego_and_without_offer_text(
        client, evaluated, offer, procedure, operator_user):
    """REQ-060: "no se encontró el documento" con el texto del pliego, sin texto de la oferta
    y sin presentarse como "no cumple"."""
    log_in(client, operator_user)
    page = text_of(client.get(page_url(offer, procedure, "inscripción")))
    assert "No se encontró el documento" in page
    assert "No es un «no cumple»" in page
    assert "Acompañar la constancia de inscripción" in page
    assert "No hay texto de la oferta que respalde una conclusión" in page


def test_an_undetermined_result_shows_its_reason_and_the_open_question(
        client, evaluated, offer, procedure, operator_user):
    """REQ-055: "no determinado" con su motivo y la pregunta a la Comisión, que sin respuesta
    no es fundamento; un requisito externo dice que falta la hoja de compliance."""
    log_in(client, operator_user)
    page = text_of(client.get(page_url(offer, procedure, "sesenta días")))
    assert "No determinado" in page and "Falta un dato" in page
    assert "¿Desde cuándo corre?" in page and "no es fundamento" in page
    external = text_of(client.get(page_url(offer, procedure, "libre deuda")))
    assert "falta la hoja de compliance" in external
    assert "Pregunta a la Comisión" in external


def test_the_page_warns_about_a_newer_matrix(
        client, evaluated, offer, procedure, operator_user, matrix):
    """REQ-057: se avisa si hay una versión posterior de la matriz."""
    from evaluon.tenders import models as m

    version = matrix.version
    newer = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, status="draft", created_by=operator_user,
        based_on=version)
    m.MatrixVersion.objects.filter(pk=newer.pk).update(
        status="validated", validated_by=operator_user, validated_at=newer.created_at)
    log_in(client, operator_user)
    page = text_of(client.get(page_url(offer, procedure, "declaración jurada")))
    assert "la versión vigente es la 2" in page


def test_a_user_without_a_commission_role_does_not_see_the_page(
        client, evaluated, offer, procedure, no_commission_user):
    """Roles: sin rol de la Comisión, 403."""
    log_in(client, no_commission_user)
    response = client.get(page_url(offer, procedure, "declaración jurada"))
    assert response.status_code == 403


def test_a_pair_that_was_not_evaluated_is_not_found(client, offer, procedure, operator_user):
    log_in(client, operator_user)
    assert client.get(page_url(offer, procedure, "declaración jurada")).status_code == 404


def test_the_page_is_read_only(client, evaluated, offer, procedure, operator_user):
    """La página no tiene acciones de decisión (las suma T-153) y no acepta cambios."""
    log_in(client, operator_user)
    url = page_url(offer, procedure, "declaración jurada")
    assert "<form" not in client.get(url).content.decode().split("</header>")[1]
    assert client.post(url).status_code == 405


def test_the_page_function_uses_the_current_result(evaluated, offer, procedure,
                                                   operator_user):
    """ADR-0039: la página muestra el resultado vigente del par."""
    requirement = requirement_of(procedure, "declaración jurada")
    page = evaluate.pair_page(operator_user, offer.pk, requirement.pk)
    assert page.result == evaluate.current_result(offer, requirement)
    assert number_of(procedure, "declaración jurada") == page.requirement.number
