"""Filas técnicas por renglón (REQ-061; plan 004, "Filas técnicas por renglón"; ADR-0043; T-167).
Decisiones literales: «Lo tecnico verificamos que exista y que en caso de tener renglones si
tiene o no tiene oferta»; «La parte tecnica ya te dije que venia del area correspondiente»; «la
comision debiera dar el ok de que tiene el informe tecnico aprobado». Caso chico y cotizaciones
inventadas (P4); el modelo es un guion."""

from decimal import Decimal

import pytest
from django.urls import reverse

from evaluon.assessment import rules
from evaluon.assessment.services import technical as ok_service
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import offer_cites, results_of, run_all
from tests.assessment.test_matrix import requirement
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401 - `portal` es fixture
from tests.offers.conftest import make_offer
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db

ROW_ONE = "Renglón 1: resma de papel A4"


def reads_row_one(model, answer="cumple"):
    model.evaluates(lambda call: says(answer, call.quote(ROW_ONE), exigence="condicion")
                    if call.requirement.startswith("Renglón 1 del pliego") else None)


def row_result(procedure, runs, item=1):
    return results_of(runs[0])[requirement(procedure, item=item).number]


def test_the_rules_have_the_technical_one_between_external_and_unreadable():
    """REQ-061: la regla técnica va en su lugar del orden del plan (el Portal, al final)."""
    names = [rule.__module__.rsplit(".", 1)[-1] for rule in rules.RULES]
    assert names == ["externals", "technical", "unreadable", "portal_facts"]


@pytest.mark.decision_literal
def test_a_technical_row_with_document_and_portal_quote_is_pending_the_technical_report(
        operator_user, procedure, model, portal):
    """REQ-061, decisión 1: documento técnico y renglón con cotización del Portal quedan como
    hechos; el resultado es «no determinado», «pendiente del informe técnico»; la cotización
    se cita como dato del Portal. Desde T-172 la ficha técnica hace falta: la línea de precio
    de la oferta no es un documento técnico."""
    offer = make_offer(procedure, operator_user, "Oferente con ficha",
                       {"oferta.pdf": [ROW_ONE], "ficha-tecnica.pdf": ["Ficha técnica: A4."]})
    quote_data(portal, procedure, offer, total=Decimal("900"),
               prices={1: (Decimal("120.50"), Decimal("10"))})
    reads_row_one(model)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = row_result(procedure, runs)
    assert (result.outcome, result.doubt) == ("no_determinado", "pendiente_informe_tecnico")
    assert result.facts["regla"] == "tecnico_hechos"
    assert result.facts["version_reglas"] == "reglas-v4"
    assert result.facts["documento_tecnico"] == "hay"
    assert result.facts["renglon_ofertado"] == "si"
    assert result.facts["renglon"] == 1
    cite = result.citations.get(kind="portal")
    assert cite.portal_kind == "cotizacion" and cite.portal_item_id == portal.pk
    assert "Renglón 1" in cite.text and "120.5" in cite.text
    assert not result.questions.exists()
    assert runs[0].counts["by_rule"]["tecnico_hechos"] >= 1


@pytest.mark.decision_literal
def test_the_opinion_is_information_and_never_the_result(
        offer, operator_user, procedure, model, portal):
    """REQ-061, decisión 2: el «cumple» del modelo se guarda como opinión con sus citas de la
    oferta y del pliego; no es el resultado."""
    reads_row_one(model, "cumple")
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = row_result(procedure, runs)
    assert result.opinion == "cumple" and result.outcome == "no_determinado"
    assert offer_cites(result)[0].text == ROW_ONE
    assert result.citations.filter(kind="pliego").exists()


@pytest.mark.decision_literal
def test_a_no_cumple_opinion_never_changes_the_outcome_nor_discards(
        offer, operator_user, procedure, model):
    """REQ-061, decisión 2: una opinión «no cumple» (con la cláusula del pliego citada) no es
    `no_cumple` en `outcome`."""
    row = requirement(procedure, item=1)
    clause = row.quotes.order_by("order").first().text
    model.evaluates(lambda call: {**says("no_cumple", call.quote(ROW_ONE)), "clausula": clause}
                    if call.requirement.startswith("Renglón 1 del pliego") else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = row_result(procedure, runs)
    assert result.opinion == "no_cumple"
    assert (result.outcome, result.doubt) == ("no_determinado", "pendiente_informe_tecnico")


def test_a_row_without_a_quote_nor_a_mention_has_no_offer(offer, operator_user, procedure, model):
    """REQ-061: renglón sin cotización del Portal y sin mención en la oferta, con la lectura
    completa: `renglon_ofertado` es `no`."""
    model.evaluates(lambda call: says("no_consta", exigence="condicion"))
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = row_result(procedure, runs, item=2)
    assert result.facts["renglon_ofertado"] == "no"


def test_a_missing_technical_document_is_sin_documento_with_the_facts(
        operator_user, procedure, model):
    """REQ-061: el documento técnico no se encontró (regla 5 de `combine.py`): resultado
    `sin_documento`, con la cita del pliego y los hechos."""
    bare = make_offer(procedure, operator_user, "Oferente sin ficha",
                      {"nota.pdf": ["Nota de presentación."]})
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure, offers=[bare])
    result = row_result(procedure, runs)
    assert result.outcome == "sin_documento" and result.doubt == ""
    assert result.facts["documento_tecnico"] == "no_se_encontro"
    assert result.citations.filter(kind="pliego").exists()


def test_a_technical_typed_document_counts_as_the_technical_document(
        operator_user, procedure, model):
    """REQ-061: un documento de tipo técnico cuenta como documento técnico aunque la lectura
    del renglón no lo cite."""
    typed = make_offer(procedure, operator_user, "Oferente con ficha",
                       {"ficha.pdf": ["Ficha técnica general."]},
                       kinds={"ficha.pdf": "tecnica"})
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure, offers=[typed])
    result = row_result(procedure, runs)
    assert result.facts["documento_tecnico"] == "hay"
    assert result.outcome == "no_determinado"


def test_a_case_that_cannot_be_told_stays_not_determined(operator_user, procedure, model):
    """REQ-061: con partes sin leer no se afirma que el renglón no tiene oferta ni que el
    documento técnico falta."""
    unread = make_offer(procedure, operator_user, "Oferente con páginas sin leer",
                        {"x.pdf": ["Texto.", "Otra página."]}, unread=[("x.pdf", 2)])
    model.evaluates(lambda call: says("no_consta", exigence="condicion"))
    _, runs = run_all(operator_user, procedure, offers=[unread])
    result = row_result(procedure, runs, item=2)
    assert result.facts["renglon_ofertado"] == "no_determinado"
    assert result.facts["documento_tecnico"] == "no_determinado"
    assert (result.outcome, result.doubt) == ("no_determinado", "pendiente_informe_tecnico")


def test_the_non_technical_rows_are_not_touched(offer, operator_user, procedure, model):
    """REQ-061: la regla es por la categoría de la fila: una formal sigue su camino."""
    model.evaluates(lambda call: says("cumple", call.quote(
        "Declaro bajo juramento que me encuentro habilitado para contratar"))
        if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    formal = [r for r in runs[0].results.all() if r.requirement.category != "tecnico"]
    assert formal and all(r.opinion == "" for r in formal)
    assert all(r.facts.get("regla") != "tecnico_hechos" for r in formal)


def test_the_opinion_can_be_turned_off(offer, operator_user, procedure, model, settings):
    """REQ-061: con el parámetro apagado no corre el contraste por cláusula; la fila sigue
    pendiente del informe técnico."""
    settings.ASSESSMENT_TECHNICAL_OPINION = False
    reads_row_one(model)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert model.clause_calls == []
    assert row_result(procedure, runs).doubt == "pendiente_informe_tecnico"


def test_the_opinion_runs_the_clause_contrast_by_default(offer, operator_user, procedure, model):
    """REQ-061: por omisión el contraste por cláusula corre y alimenta la opinión."""
    reads_row_one(model)
    run_all(operator_user, procedure, offers=[offer])
    assert len(model.clause_calls) == 1


@pytest.mark.decision_literal
def test_a_current_ok_of_the_technical_report_is_applied_when_the_row_is_saved(
        offer, operator_user, evaluator_user, procedure, model):
    """REQ-061, decisión 3: con un ok vigente del informe técnico para el renglón, una
    reevaluación no lo pierde: apto → cumple y no apto → no cumple, con el fundamento del ok."""
    reads_row_one(model)
    run_all(operator_user, procedure, offers=[offer])
    ok_service.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "no_apto", 3: "apto"},
                       note="Informe inventado")
    _, runs = run_all(operator_user, procedure, offers=[offer])
    one, two = row_result(procedure, runs, 1), row_result(procedure, runs, 2)
    assert (one.outcome, one.doubt) == ("cumple", "")
    assert (two.outcome, two.doubt) == ("no_cumple", "")
    assert one.explanation.startswith("informe técnico aprobado, ok de la Comisión por ")
    assert one.facts["regla"] == "ok_informe_tecnico" and one.facts["dictamen"] == "apto"
    assert one.facts["technical_ok"] == ok_service.ok_of(offer, 1).pk
    assert one.opinion == "cumple"
    # La fila lleva `technical_ok`: el ok se puede retirar y la fila vuelve a pendiente.
    applied = ok_service.withdraw_ok(evaluator_user, offer, items=[1], note="Se retira")
    assert applied.results and applied.results[0].doubt == "pendiente_informe_tecnico"


@pytest.mark.decision_literal
def test_a_withdrawn_ok_is_not_applied(offer, operator_user, evaluator_user, procedure, model):
    """REQ-061, decisión 3: un ok retirado no rige; la fila vuelve a estar pendiente."""
    reads_row_one(model)
    run_all(operator_user, procedure, offers=[offer])
    ok_service.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    ok_service.withdraw_ok(evaluator_user, offer, note="Error de carga")
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert row_result(procedure, runs).doubt == "pendiente_informe_tecnico"


def test_the_result_page_labels_the_opinion_and_shows_the_facts(
        client, offer, operator_user, procedure, model):
    """REQ-061: la pantalla rotula la opinión («información, no es el resultado») y muestra
    los hechos."""
    reads_row_one(model)
    run_all(operator_user, procedure, offers=[offer])
    log_in(client, operator_user)
    row = requirement(procedure, item=1)
    page = text_of(client.get(reverse("assessment:pair", args=[offer.pk, row.pk])))
    assert "opinión del sistema (información, no es el resultado)" in page
    assert "Documento técnico" in page and "Renglón ofertado" in page
    assert "Pendiente del informe técnico" in page
