"""No se pudo leer, con documento y página (REQ-064; plan 004, "No se pudo leer"; ADR-0043;
T-166). Textos inventados (P4); el modelo es un guion."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import models as am
from evaluon.assessment import prompting, unreadable
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import number_of, results_of, run_all
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

GUARANTEE = "garantía de mantenimiento"
NOTE = "Pagaré sin protesto a la orden del organismo por la suma de la garantía."


@pytest.fixture
def pagare(procedure, operator_user):
    """Una oferta con un pagaré cuya página 2 no se pudo leer y un documento legible."""
    return make_offer(procedure, operator_user, "Con el pagaré ilegible", {
        "pagare.pdf": [NOTE, ""],
        "nota.pdf": ["Nota de presentación de la oferta."]},
        unread=[("pagare.pdf", 2)])


def points_at(name):
    def function(call):
        if GUARANTEE in call.requirement:
            return says("no_determinado", ilegible=call.alias_with(name))
        return None
    return function


@pytest.mark.decision_literal
def test_an_unreadable_page_is_reported_with_document_and_page_for_the_commission(
        pagare, operator_user, procedure, model):
    """REQ-064: el modelo señala el documento; el informe de lectura lo avala; el resultado es
    "no se pudo leer" con documento y página, y la pregunta fija para la Comisión."""
    model.evaluates(points_at("Pagaré sin protesto"))
    _, runs = run_all(operator_user, procedure, offers=[pagare])
    number = number_of(procedure, GUARANTEE)
    result = results_of(runs[0])[number]
    assert (result.outcome, result.doubt) == ("no_determinado", "no_se_pudo_leer")
    assert result.facts["regla"] == "ilegible_informe"
    assert result.facts["version_reglas"] == "reglas-v9"
    assert (result.facts["ilegible"]["documento"], result.facts["ilegible"]["pagina"]) == (
        "pagare.pdf", 2)
    question = am.Question.objects.get(requirement__number=number)
    # T-235 (REQ-105): la pregunta de la regla va al final, con el requisito, la conclusión y
    # el texto de la oferta delante.
    assert question.text.splitlines()[-1] == (
        "¿Lo que exige este requisito está en la página 2 de «pagare.pdf»? "
        "Hay que revisar el original.")
    assert question.text.startswith("Requisito ") and "Conclusión del sistema:" in question.text
    assert "Texto de la oferta:" in question.text
    assert question.reason == "no_se_pudo_leer"
    assert runs[0].counts["by_rule"]["ilegible_informe"] == 1


@pytest.mark.decision_literal
def test_an_unreadable_document_is_not_a_missing_document(
        pagare, operator_user, procedure, model):
    """REQ-064: un documento ilegible no es un documento ausente: aunque el modelo diga "no
    consta" un documento, el resultado no es "no se encontró el documento"."""
    model.evaluates(lambda call: says("no_consta", exigence="documento",
                                      ilegible=call.alias_with("Pagaré sin protesto"))
                    if GUARANTEE in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[pagare])
    result = results_of(runs[0])[number_of(procedure, GUARANTEE)]
    assert (result.outcome, result.doubt) == ("no_determinado", "no_se_pudo_leer")


@pytest.mark.decision_literal
def test_an_alias_the_reading_report_does_not_back_is_discarded_as_an_anomaly(
        pagare, operator_user, procedure, model):
    """REQ-064: un alias de un documento que el informe no marca como no leído se descarta con
    una anomalía y el par sigue su camino: `lectura_incompleta` (hay otra página sin leer)."""
    model.evaluates(points_at("Nota de presentación"))
    _, runs = run_all(operator_user, procedure, offers=[pagare])
    result = results_of(runs[0])[number_of(procedure, GUARANTEE)]
    assert (result.outcome, result.doubt) == ("no_determinado", "lectura_incompleta")
    assert "ilegible" not in result.facts
    assert any(a["type"] == "ilegible_no_avalado" for a in runs[0].anomalies)


def test_without_the_alias_the_pair_is_an_incomplete_reading(
        pagare, operator_user, procedure, model):
    """REQ-064: sin el alias `ilegible`, `lectura_incompleta` es solo "hay partes sin leer sin
    relación visible con este requisito"."""
    model.evaluates(lambda call: says("no_determinado") if GUARANTEE in call.requirement
                    else None)
    _, runs = run_all(operator_user, procedure, offers=[pagare])
    result = results_of(runs[0])[number_of(procedure, GUARANTEE)]
    assert (result.outcome, result.doubt) == ("no_determinado", "lectura_incompleta")
    assert result.facts == {}


def test_a_conclusion_with_a_located_citation_is_not_overridden(
        pagare, operator_user, procedure, model):
    """REQ-064: si otro grupo o documento permite concluir con cita ubicada, el alias
    `ilegible` no pisa la conclusión."""
    model.evaluates(lambda call: says("cumple", call.quote("Nota de presentación de la oferta."),
                                      ilegible=call.alias_with("Pagaré sin protesto"))
                    if GUARANTEE in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[pagare])
    result = results_of(runs[0])[number_of(procedure, GUARANTEE)]
    assert result.outcome == "cumple" and "ilegible" not in result.facts


def test_the_resolution_prefers_a_page_of_the_window_shown_to_the_model():
    """REQ-064: con un documento leído por ventanas, la página es una de la ventana que vio el
    modelo; si ninguna lo es, la primera sin leer."""
    document = SimpleNamespace(pk=7, title="pagare.pdf", file_name="pagare.pdf")
    unread = [{"document": 7, "title": "pagare.pdf", "page": p} for p in (2, 9)]
    window = SimpleNamespace(doc=SimpleNamespace(document=document), windowed=True,
                             first_page=8, last_page=12)
    assert unreadable.resolve(window, unread)["pagina"] == 9
    elsewhere = SimpleNamespace(doc=SimpleNamespace(document=document), windowed=True,
                                first_page=20, last_page=25)
    assert unreadable.resolve(elsewhere, unread)["pagina"] == 2
    other = SimpleNamespace(doc=SimpleNamespace(
        document=SimpleNamespace(pk=8, title="otro.pdf", file_name="otro.pdf")),
        windowed=False)
    assert unreadable.resolve(other, unread) is None


def test_the_ilegible_field_is_optional_in_the_models_output():
    """El campo `ilegible` es opcional: una salida de la versión anterior sigue siendo válida,
    y el esquema lo limita a los alias del grupo (o vacío)."""
    base = ('{"resultado": "no_consta", "exigencia": "documento", "citas": [], '
            '"fundamentos": [], "explicacion": "x", "externo": false, "pregunta": ""')
    assert prompting.parse_evaluation(base + "}", ["D1"], []).unreadable == ""
    parsed = prompting.parse_evaluation(base + ', "ilegible": "D1"}', ["D1"], [])
    assert parsed.unreadable == "D1"
    with pytest.raises(prompting.InvalidOutput):
        prompting.parse_evaluation(base + ', "ilegible": 3}', ["D1"], [])
    schema = prompting.evaluation_schema(["D1", "D2"], [])
    assert schema["properties"]["ilegible"]["enum"] == ["", "D1", "D2"]
    assert "ilegible" not in schema["required"]
