"""Externos como regla: «falta la hoja de compliance», nunca «duda» (REQ-063; plan 004, "Qué se
decide sin el modelo y en qué orden", regla 1; ADR-0043; T-166). Textos inventados (P4); el modelo
es un guion."""

import re
from types import SimpleNamespace

import pytest

from evaluon.assessment import externals, rules
from evaluon.assessment import models as am
from evaluon.assessment.combine import Combined
from evaluon.assessment.services import evaluate, remedy
from evaluon.tenders import jobs
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    requirement_of,
    results_of,
    run_all,
)
from tests.assessment.test_remedy import POLICY, policy, read_documents

pytestmark = pytest.mark.django_db

DEBT = "libre deuda"

# Una entrada del catálogo por tipo de verificación: el texto que la reconoce y uno parecido
# que se resuelve con la oferta (no debe reconocerla).
ENTRIES = {
    "registro_proveedores": (
        "El oferente deberá estar inscripto en el Registro de Proveedores del organismo.",
        "Acompañar la constancia de inscripción del oferente en el registro de proveedores."),
    "sancionados": (
        "No podrán presentarse oferentes incluidos en el REPSAL o sancionados.",
        "Informar el domicilio del oferente en el registro de la actividad comercial."),
    "deuda": (
        "La inexistencia de deuda exigible del oferente se verificará al evaluar.",
        "Informar el plazo de pago de las deudas con proveedores del oferente."),
    "seguros": (
        "La póliza deberá ser de una aseguradora autorizada por la Superintendencia de Seguros "
        "de la Nación.",
        "La póliza de caución se presentará en original firmada por el representante."),
    "habilidad_contratar": (
        "La habilidad para contratar del oferente se verificará en la etapa de evaluación.",
        "Presentar la declaración jurada de habilidad para contratar firmada por el oferente."),
}

# Otras formas del mismo tipo (hallazgo 1 de la verificación): el texto que se reconoce y un
# parecido que sigue siendo un documento de la oferta.
EXTRA_FORMS = [
    # T-231 (E-6): la declaración que el oferente completa y adjunta ya no es externa; lo externo
    # es la verificación de la habilidad por la Comisión.
    ("habilidad_contratar",
     "La Comisión verificará la habilidad para contratar del oferente (causales del artículo "
     "18, causas penales) en la etapa de evaluación.",
     "Declaración jurada de habilidad para contratar: no estar comprendido en las causales "
     "del artículo 18 ni tener causas penales, completada y firmada por el oferente."),
    ("registro_proveedores",
     "El oferente deberá haber culminado el trámite de inscripción en el Registro de "
     "Proveedores antes de la adjudicación.",
     "Acompañar el formulario del trámite de inscripción del oferente en su cámara empresaria."),
    ("registro_proveedores",
     "Se controlará el estado de la inscripción del oferente en el Registro de Proveedores.",
     "Acompañar la constancia de inscripción del oferente en el registro de proveedores."),
    ("deuda",
     "La existencia de deuda del oferente también deberá constatarse al evaluar.",
     "Informar la existencia de contratos vigentes del oferente con otros organismos."),
]


@pytest.mark.decision_literal
@pytest.mark.parametrize("key,external,similar", EXTRA_FORMS)
def test_the_catalog_recognizes_the_other_forms_of_the_same_check(key, external, similar):
    """REQ-063: habilidad con causales, trámite o estado de inscripción y existencia de deuda
    son externos; un parecido que pide un documento de la oferta no lo es."""
    assert key in [c.key for c in externals.match(external)]
    assert key not in [c.key for c in externals.match(similar)]


def test_the_catalog_has_one_entry_per_kind_of_external_check():
    """REQ-063: un tipo por verificación externa de la decisión del responsable."""
    assert {c.key for c in externals.CATALOG} == set(ENTRIES)
    assert all(c.label for c in externals.CATALOG)


@pytest.mark.decision_literal
@pytest.mark.parametrize("key", sorted(ENTRIES))
def test_each_catalog_entry_recognizes_its_requirement_and_not_a_similar_one(key):
    """REQ-063: cada entrada reconoce su requisito del pliego y no uno parecido que se resuelve
    con la oferta (el catálogo no marca de más)."""
    external, similar = ENTRIES[key]
    assert key in [c.key for c in externals.match(external)]
    assert key not in [c.key for c in externals.match(similar)]


def test_an_offer_requirement_is_not_in_the_catalog():
    """REQ-063: un requisito que se resuelve con la oferta no es externo."""
    assert externals.match("El plazo de entrega será de diez días corridos.") == []
    assert externals.match("") == []


def test_the_catalog_ignores_accents_case_and_spacing():
    """El texto vigente del pliego se compara sin acentos, sin mayúsculas y con espacios
    colapsados."""
    found = externals.match("LA  INEXISTENCIA DE DEUDA EXIGIBLE\n se verificará")
    assert [c.key for c in found] == ["deuda"]


@pytest.fixture
def debt_in_catalog(monkeypatch):
    """El requisito del libre deuda del caso chico entra al catálogo: prueba que lo decide la
    regla del catálogo y no la marca del modelo."""
    extra = externals.ExternalCheck("libre_deuda", "constancia fiscal de deuda",
                                    re.compile("libre deuda"))
    monkeypatch.setattr(externals, "CATALOG", (*externals.CATALOG, extra))


def not_flagged(call):
    """El modelo no marca nada como externo: la oferta declara y el resto "no consta"."""
    if "declaración jurada" in call.requirement or DEBT in call.requirement:
        return says("cumple", call.quote(DECLARATION))
    return None


def execute_remedy(requested, user):
    try:
        return evaluate.execute(requested.request, user, job=requested.job,
                                channel=am.Channel.EVAL, audit_channel=requested.event.channel)
    finally:
        jobs.finish(requested.job)


@pytest.mark.decision_literal
def test_a_catalog_requirement_is_a_missing_compliance_sheet_even_if_the_offer_declares_it(
        offer, operator_user, procedure, model, debt_in_catalog):
    """REQ-063: el catálogo gana sobre un "cumple" del modelo: "falta la hoja de compliance"
    (`externo`), sin pregunta, con la regla y su versión en `facts`."""
    model.evaluates(not_flagged)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, DEBT)
    result = results_of(runs[0])[number]
    assert (result.outcome, result.doubt) == ("no_determinado", "externo")
    assert result.facts["regla"] == "externo_catalogo"
    assert result.facts["version_reglas"] == "reglas-v8"
    assert result.facts["externo"]["tipos"] == ["libre_deuda"]
    assert "constancia fiscal de deuda" in result.explanation
    assert "hoja de compliance" in result.explanation
    assert not am.Question.objects.filter(requirement__number=number).exists()
    assert runs[0].counts["by_rule"]["externo_catalogo"] == 1
    assert runs[0].prompt_versions["reglas"] == "reglas-v8"


@pytest.mark.decision_literal
@pytest.mark.parametrize("answer", [
    lambda call: says("no_consta", exigence="documento"),
    lambda call: says("no_determinado", question="¿Qué pasa con la deuda?"),
])
def test_an_external_is_never_a_missing_document_nor_a_doubt(
        answer, offer, operator_user, procedure, model, debt_in_catalog):
    """REQ-063: un externo que antes salía "no se encontró el documento" (oferta leída entera)
    o "duda" con pregunta ahora dice "falta la hoja de compliance", sin pregunta."""
    model.evaluates(lambda call: answer(call) if DEBT in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, DEBT)]
    assert (result.outcome, result.doubt) == ("no_determinado", "externo")
    assert not am.Question.objects.filter(requirement=result.requirement).exists()


@pytest.mark.decision_literal
def test_the_model_mark_decides_when_the_catalog_does_not_know_the_requirement(
        offer, operator_user, procedure, model):
    """REQ-063: la marca `externo` del modelo es la segunda vía: la regla es `externo_modelo`
    y la explicación no inventa qué consulta falta."""
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION), external=True)
                    if DEBT in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, DEBT)]
    assert (result.outcome, result.doubt) == ("no_determinado", "externo")
    assert result.facts["regla"] == "externo_modelo" and result.facts["externo"]["tipos"] == []
    assert result.explanation.startswith("Falta la hoja de compliance")


@pytest.mark.decision_literal
def test_the_sheet_loaded_by_subsanation_is_read_and_cited(
        offer, operator_user, evaluator_user, procedure, model, debt_in_catalog):
    """REQ-063, P9: con la hoja subida por la Comisión la regla no rige: la hoja es un documento
    más, se lee y la conclusión (aunque diga "no cumple") queda con su cita."""
    model.evaluates(not_flagged)
    run_all(operator_user, procedure)
    external = evaluate.current_result(offer, requirement_of(procedure, DEBT))
    assert (external.outcome, external.doubt) == ("no_determinado", "externo")
    remedy.request_remedy(evaluator_user, external.pk, "Se pide la hoja de compliance.")
    remedy.add_document(evaluator_user, external.pk, data=policy(), file_name="compliance.pdf")
    read_documents()
    model.evaluates(lambda call: says("no_cumple", call.quote(POLICY), exigence="documento")
                    if DEBT in call.requirement and call.alias_with(POLICY)
                    else not_flagged(call))
    runs = execute_remedy(remedy.reevaluate(evaluator_user, external.pk), evaluator_user)
    result = results_of(runs[0])[number_of(procedure, DEBT)]
    assert result.outcome == "no_cumple" and result.doubt == ""
    assert "regla" not in result.facts
    cited = list(result.citations.filter(kind="oferta"))
    assert cited and cited[0].document.file_name == "compliance.pdf"


@pytest.mark.decision_literal
def test_the_model_mark_does_not_rule_once_the_sheet_is_loaded(
        offer, operator_user, evaluator_user, procedure, model):
    """REQ-063: aunque el modelo siga marcando `externo`, con la hoja cargada no se vuelve a
    "falta la hoja": la marca no rige y el requisito se evalúa por lectura."""
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION), external=True)
                    if DEBT in call.requirement else None)
    run_all(operator_user, procedure)
    external = evaluate.current_result(offer, requirement_of(procedure, DEBT))
    remedy.request_remedy(evaluator_user, external.pk, "Se pide la hoja de compliance.")
    remedy.add_document(evaluator_user, external.pk, data=policy(), file_name="compliance.pdf")
    read_documents()
    model.evaluates(lambda call: says("cumple", call.quote(POLICY), exigence="documento",
                                      external=True)
                    if DEBT in call.requirement and call.alias_with(POLICY) else None)
    runs = execute_remedy(remedy.reevaluate(evaluator_user, external.pk), evaluator_user)
    assert results_of(runs[0])[number_of(procedure, DEBT)].outcome == "cumple"


@pytest.mark.decision_literal
def test_external_is_the_first_rule_and_wins_over_a_missing_document():
    """REQ-063: en `rules.apply` el externo es la primera regla: gana sobre "no se encontró el
    documento"."""
    assert rules.RULES[0] is externals.rule
    pair = SimpleNamespace(
        combined=Combined(outcome="sin_documento", exigence="documento"),
        text=SimpleNamespace(text=ENTRIES["seguros"][0]), requirement=0,
        groups=[])
    ctx = SimpleNamespace(offer=0)
    assert rules.apply(pair, ctx) == "externo_catalogo"
    assert pair.combined.doubt == "externo" and pair.combined.question == ""
    assert pair.combined.facts["version_reglas"] == "reglas-v8"
    assert pair.combined.facts["externo"]["tipos"] == ["seguros"]
