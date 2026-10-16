"""Toda celda termina en una de tres salidas (REQ-120; plan 016, «Paso 2 · Reglas de decisión a tres
salidas»; ADR-0070, punto 5; T-277).

Una celda es: «cumple» con fundamento, «no cumple» con cita (o decidida por una regla), o «no
determinado» con la pregunta a la Comisión o el documento que falta nombrado. «No se encontró el
documento» y «no aplica» son formas de «no determinado» con el documento o la razón nombrados
(ADR-0038, ADR-0043); «no se encontró el documento» lleva siempre su pregunta. Los pares O2 R16
(T-263) y O3 R22 (T-268) de la 015 eran «no se encontró el documento» sin la pregunta que el modelo
había escrito: `test_the_questions_of_t263_and_t268_are_kept` los reproduce con el doble.

Umbral 9 (escrito antes de medir): 0 «no se encontró el documento» sin pregunta; 100 % de los «no
determinado» con la pregunta o el documento nombrado, en las combinaciones de abajo y en los casos
de prueba. Textos inventados (P4); el modelo es un guion (`fakes.py`).

1. Las combinaciones: todos los resultados de grupo, con y sin contraste, con y sin lectura
   completa, y el contraste por cláusula (funciones puras de `combine.py`).
2. La comprobación `cell_problem`, que detecta cada forma que falla.
3. Las reglas: el doble contesta lo mismo a todos los requisitos del caso chico, con el Portal
   cargado y sin él, y se mira cada celda guardada (`evaluation.three_outputs`).
4. Cada conversión del código (`evaluate.CONVERSIONS`) deja su motivo y su pregunta o documento.
5. La medida de `medir_evaluacion`.
"""

import itertools
import re
from dataclasses import replace
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from evaluon.assessment import combine, evaluation, grounds, prompting, rules
from evaluon.assessment import models as am
from evaluon.assessment.citations import Located
from evaluon.assessment.services import evaluate
from evaluon.portal import models as pm
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_contexto_t261 import engine  # noqa: F401 - fixture del motor chico
from tests.assessment.test_evaluate import (  # noqa: F401 - `big_offer` es una fixture
    DECLARATION,
    big_offer,
    number_of,
    results_of,
    run_all,
    sheets_firm,
)
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import with_policy  # noqa: F401 - fixture
from tests.conftest import count_words

DOC = SimpleNamespace(pk=1, title="oferta.pdf")
REQUIREMENT = "El oferente presentará la declaración jurada de habilidad para contratar."
CLAUSE = "5.1 Bolsas de 20 kilos."
CLAUSES_TEXT = f"{CLAUSE} 5.2 Proteína mínima 24 %."
UNREAD = [{"document": 1, "title": "doc.pdf", "page": 2}]


def cite(start=0, text="texto citado"):
    return Located(document=DOC, reading=None, page=1, char_start=start,
                   char_end=start + len(text), text=text)


# --- 1. Las combinaciones de resultados de grupo, contraste y cláusulas -----------------------

ASKED = "¿Qué documento prueba la habilitación para contratar?"
TO_OFFEROR = "Aclare el oferente su habilitación para contratar."
WHY = "El modelo lo explica."

# Lo que puede decir un grupo (`GroupResult`): cada uno es una salida válida de `_group_result`
# (una conclusión siempre trae su cita ubicada; una salida inválida o sin cita ya llegó como
# «no determinado»).
GROUP_KINDS = {
    "cumple": dict(result="cumple", cites=[cite(0, "uno")], explanation=WHY),
    "no_cumple": dict(result="no_cumple", cites=[cite(100, "dos")], explanation=WHY),
    "no_consta_documento": dict(result="no_consta", exigence="documento"),
    "no_consta_documento_pregunta": dict(result="no_consta", exigence="documento",
                                          question=ASKED),
    "no_consta_condicion": dict(result="no_consta", exigence="condicion"),
    "duda": dict(result="no_determinado", doubt="duda"),
    "duda_explicada": dict(result="no_determinado", doubt="duda", explanation=WHY),
    "duda_pregunta": dict(result="no_determinado", doubt="duda", question=ASKED, explanation=WHY),
    "duda_pregunta_al_oferente": dict(result="no_determinado", doubt="duda",
                                      question=TO_OFFEROR, explanation=WHY),
    "sin_cita": dict(result="no_determinado", doubt="sin_cita"),
    "sin_dato": dict(result="no_determinado", doubt="sin_dato", explanation=WHY),
    "lectura_incompleta": dict(result="no_determinado", doubt="lectura_incompleta"),
    "externo": dict(result="no_determinado", doubt="duda", external=True),
}


def a_group(index, kind):
    spec = dict(GROUP_KINDS[kind])
    cites = spec.pop("cites", [])
    return combine.GroupResult(index, citations=list(cites), **spec)


UNREAD_CASES = {
    "lectura completa": dict(unread=[], unread_groups=0),
    "páginas sin leer": dict(unread=UNREAD, unread_groups=0),
    "grupos sin leer": dict(unread=[], unread_groups=1),
}

CLAUSE_ROWS = {
    "coinciden": [(CLAUSE, "coincide", "")],
    "no aparece": [(CLAUSE, "no_aparece", "")],
    "ilegible": [(CLAUSE, "no_legible", "")],
    "contradice sin cita": [(CLAUSE, "contradice", "dice otra cosa")],
    "contradice con cita": [(CLAUSE, "contradice", "dice otra cosa", cite(300, "otra cosa"))],
    "una coincide y otra no": [(CLAUSE, "coincide", ""),
                               ("5.2 Proteína mínima 24 %.", "no_aparece", "")],
}


def final_form(combined, *, unread=()):
    """El resultado como queda guardado: con la pregunta que arma el código (`compose_question`)."""
    asked = combine.compose_question(1, REQUIREMENT, combined, documents=["oferta.pdf"],
                                     unread=unread)
    return replace(combined, question=asked)


def explain(groups, combined, extra=""):
    return (f"{[(g.result, g.doubt, g.exigence, bool(g.question), g.external) for g in groups]} "
            f"-> {combined.outcome}/{combined.doubt} {extra}")


@pytest.mark.parametrize("case", list(UNREAD_CASES))
def test_every_combination_of_group_results_ends_in_one_of_the_three_outputs(case):
    """REQ-120: de 1 a 3 grupos, cada uno con cualquiera de sus salidas posibles, con lectura
    completa o con partes sin leer: el resultado del par, con la pregunta que arma el código, es
    «cumple» con fundamento, «no cumple» con cita o «no determinado» con su motivo y su pregunta o
    su documento. «No se encontró el documento» lleva siempre su pregunta."""
    config = UNREAD_CASES[case]
    seen, failures = set(), []
    for size in (1, 2, 3):
        for kinds in itertools.product(GROUP_KINDS, repeat=size):
            groups = [a_group(i, kind) for i, kind in enumerate(kinds)]
            combined = combine.combine(groups, **config, without_reading=())
            seen.add((combined.outcome, combined.doubt))
            final = final_form(combined, unread=config["unread"])
            problem = combine.combined_problem(final)
            if problem:
                failures.append((kinds, problem))
    assert not failures, failures[:5]
    # El recorrido pasa por las cuatro salidas del par (no es un recorrido vacío).
    assert {"cumple", "no_cumple", "sin_documento", "no_determinado"} <= {o for o, _ in seen} or (
        case != "lectura completa")
    assert ("no_determinado", "contradiccion") in seen and ("no_determinado", "externo") in seen


@pytest.mark.parametrize("answer", ["si", "no", "parcial"])
@pytest.mark.parametrize("case", list(UNREAD_CASES))
def test_every_combination_after_the_contrast_ends_in_one_of_the_three_outputs(case, answer):
    """REQ-120: después del contraste (`si`, `no`, `parcial`) un «cumple» o «no cumple» sigue
    siendo conclusión con su cita, o es «no determinado» `sin_corroborar` con la pregunta de
    confirmarlo, corregirlo o rechazarlo."""
    config = UNREAD_CASES[case]
    failures, downgraded = [], 0
    for size in (1, 2, 3):
        for kinds in itertools.product(GROUP_KINDS, repeat=size):
            combined = combine.combine([a_group(i, k) for i, k in enumerate(kinds)], **config,
                                       without_reading=())
            if not combined.needs_contrast:
                continue
            after = combine.apply_contrast(combined, answer, "el texto no lo muestra")
            downgraded += after.outcome == "no_determinado"
            problem = combine.combined_problem(final_form(after, unread=config["unread"]))
            if problem:
                failures.append((kinds, problem))
    assert not failures, failures[:5]
    assert bool(downgraded) == (answer != "si")


@pytest.mark.parametrize("asked", ["", ASKED, TO_OFFEROR])
@pytest.mark.parametrize("rows", list(CLAUSE_ROWS))
def test_every_combination_of_the_clause_contrast_ends_in_one_of_the_three_outputs(rows, asked):
    """REQ-120: el contraste por cláusula de un «cumple» técnico da «cumple», «no cumple» con la
    cláusula y la cita, o «no determinado» `sin_dato` con las cláusulas no confirmadas nombradas en
    la explicación y en la pregunta, también si el modelo no escribió la pregunta o la dirigió al
    oferente."""
    cumple = combine.combine([a_group(0, "cumple")], unread=[], without_reading=())
    after = combine.apply_clauses(cumple, CLAUSE_ROWS[rows], asked, CLAUSES_TEXT)
    final = final_form(after)
    assert combine.combined_problem(final) == ""
    if after.outcome == "no_determinado":
        missing = [c for c, state, *_ in CLAUSE_ROWS[rows] if state != "coincide"]
        assert after.doubt == "sin_dato" and all(c in after.explanation for c in missing)
        closing = final.question.splitlines()[-1]
        if asked == ASKED:
            assert closing == ASKED     # la pregunta del modelo, dirigida a la Comisión, queda
        else:
            assert all(c in after.question for c in missing)
            assert "Comisión" in closing and not combine.addresses_offeror(closing)


# --- 2. La comprobación de la forma -----------------------------------------------------------


def problem(outcome, **kwargs):
    return combine.cell_problem(outcome, **kwargs)


@pytest.mark.parametrize("outcome, kwargs, expected", [
    # «cumple» con fundamento
    ("cumple", dict(has_citation=True), ""),
    ("cumple", dict(facts={"criterios": [{"nombre": "ausencia_verificada"}]}), ""),
    ("cumple", dict(facts={"aplica": False}, explanation="No aplica: otra forma de garantía."), ""),
    ("cumple", dict(facts={"technical_ok": 3}), ""),
    ("cumple", dict(), "cumple_sin_fundamento"),
    ("cumple", dict(facts={"aplica": False}), "cumple_sin_fundamento"),
    # «no cumple» con cita o decidido por una regla
    ("no_cumple", dict(has_citation=True), ""),
    ("no_cumple", dict(facts={"regla": "presentacion_fisica_no_consta"}), ""),
    ("no_cumple", dict(), "no_cumple_sin_cita"),
    # «no determinado» con motivo y pregunta, o con el documento nombrado
    ("no_determinado", dict(explanation="Falta el dato.", has_question=True), ""),
    ("no_determinado", dict(doubt="externo", explanation="Falta la hoja de compliance."), ""),
    ("no_determinado", dict(doubt="pendiente_informe_tecnico",
                            explanation="Lo resuelve el informe técnico del área."), ""),
    ("no_determinado", dict(doubt="no_se_pudo_leer",
                            explanation="No se pudo leer la página 3 de «x»."), ""),
    ("no_determinado", dict(doubt="duda", explanation="El modelo dudó."),
     "no_determinado_sin_nombrar"),
    ("no_determinado", dict(doubt="externo", explanation="Algo."), "no_determinado_sin_nombrar"),
    ("no_determinado", dict(has_question=True), "no_determinado_sin_motivo"),
    # «no se encontró el documento» siempre con su pregunta
    ("sin_documento", dict(has_question=True), ""),
    ("sin_documento", dict(explanation="No está."), "sin_documento_sin_pregunta"),
])
def test_the_form_check_accepts_the_three_outputs_and_rejects_what_does_not_fit(
        outcome, kwargs, expected):
    """REQ-120: `cell_problem` es la comprobación que usan los tests y `medir_evaluacion`: acepta
    cada una de las tres formas y nombra lo que falla en las demás."""
    assert problem(outcome, **kwargs) == expected


def test_an_undetermined_without_a_question_or_a_named_document_would_be_caught():
    """REQ-120: la comprobación detecta la falla que T-277 corrige: el resultado de `combine` sin
    pregunta (antes de `compose_question`) queda como «no determinado» sin nombrar."""
    combined = combine.combine([a_group(0, "duda")], unread=[], without_reading=())
    assert combine.combined_problem(combined) == combine.PROBLEM_UNNAMED
    assert combine.combined_problem(final_form(combined)) == ""
    missing = combine.combine([a_group(0, "no_consta_documento")], unread=[], without_reading=())
    assert missing.outcome == "sin_documento"
    assert combine.combined_problem(missing) == combine.PROBLEM_NO_QUESTION
    assert combine.combined_problem(final_form(missing)) == ""


# --- Las preguntas ------------------------------------------------------------------------------


def test_the_missing_document_keeps_the_question_the_model_wrote_and_names_the_document():
    """REQ-120 (T-263, T-268): «no se encontró el documento» conserva la pregunta que el modelo
    escribió, dirigida a la Comisión, y el documento que el pliego exige queda nombrado (el
    requisito, con la cita del pliego). Antes `done()` la descartaba."""
    combined = combine.combine([a_group(0, "no_consta_documento_pregunta"),
                                a_group(1, "no_consta_documento")], unread=[],
                               without_reading=())
    assert combined.outcome == "sin_documento" and combined.exigence == "documento"
    assert combined.question == ASKED
    asked = combine.compose_question(16, REQUIREMENT, combined, documents=["oferta.pdf"])
    lines = asked.splitlines()
    assert lines[0] == f"Requisito 16: «{REQUIREMENT}»."
    assert "no se encontró el documento que el pliego exige" in lines[1]
    assert lines[-1] == ASKED


def test_the_missing_document_without_a_question_from_the_model_gets_one_from_the_code():
    """REQ-120: si el modelo no escribió la pregunta, o la dirigió al oferente, la arma el código,
    dirigida a la Comisión y con el requisito."""
    for kind in ("no_consta_documento", "duda_pregunta_al_oferente"):
        combined = combine.combine([a_group(0, "no_consta_documento")], unread=[],
                                   without_reading=())
        if kind == "duda_pregunta_al_oferente":
            combined = replace(combined, question=TO_OFFEROR)
        asked = combine.compose_question(3, REQUIREMENT, combined, documents=["oferta.pdf"])
        closing = asked.splitlines()[-1]
        assert asked.startswith("Requisito 3") and "Comisión" in closing
        assert not combine.addresses_offeror(closing) and TO_OFFEROR not in asked


@pytest.mark.parametrize("doubt", [
    "duda", "sin_corroborar", "contradiccion", "lectura_incompleta", "sin_cita", "sin_dato",
    "falta_coincidencia", "en_portal", "no_se_pudo_leer", "pendiente_informe_tecnico"])
def test_every_default_question_is_addressed_to_the_commission(doubt):
    """REQ-120, REQ-105: el texto por motivo de `_default_ask` nunca se dirige al oferente."""
    for citations in ([], [cite()]):
        combined = combine.Combined(outcome="no_determinado", doubt=doubt, proposed="cumple",
                                    explanation="Motivo.", citations=citations)
        closing = combine._default_ask(combined)
        assert "Comisión" in closing and not combine.addresses_offeror(closing), closing
    sin_documento = combine.Combined(outcome="sin_documento", exigence="documento")
    assert not combine.addresses_offeror(combine._default_ask(sin_documento))


def test_an_undetermined_that_names_a_missing_document_asks_nothing_unless_its_rule_wrote_it():
    """REQ-063, REQ-120: `externo` nunca lleva pregunta (la acción es subir la hoja); el informe
    técnico pendiente y la página ilegible nombran su documento y solo llevan la pregunta que escribe
    su regla."""
    for doubt in combine.DOCUMENT_DOUBTS:
        bare = combine.Combined(outcome="no_determinado", doubt=doubt, explanation="Motivo.")
        assert combine.compose_question(1, "x", bare) == ""
    asked = combine.Combined(outcome="no_determinado", doubt="no_se_pudo_leer",
                             question="¿Está en la página 4?", explanation="No se pudo leer.")
    assert "¿Está en la página 4?" in combine.compose_question(1, "x", asked)
    external = replace(asked, doubt="externo")
    assert combine.compose_question(1, "x", external) == ""


def test_an_undetermined_without_an_explanation_gets_its_reason():
    """REQ-120: una celda sin decidir siempre dice por qué, aunque el modelo no haya escrito la
    explicación."""
    for kind in ("duda", "sin_cita", "sin_dato", "lectura_incompleta", "externo"):
        combined = combine.combine([a_group(0, kind)], unread=[], without_reading=())
        assert combined.outcome == "no_determinado" and combined.explanation.strip(), kind


# --- 3. Las reglas -------------------------------------------------------------------------------

BEHAVIORS = {
    "no consta el documento": lambda call: None,
    "no consta la condición": lambda call: says(
        "no_consta", exigence="condicion", conditions=[("Lo que exige.", "", 0, "no_consta")]),
    "duda sin pregunta": lambda call: says("no_determinado"),
    "duda con pregunta": lambda call: says("no_determinado", question=ASKED),
    "duda con pregunta al oferente": lambda call: says("no_determinado", question=TO_OFFEROR),
    "no consta con pregunta": lambda call: says("no_consta", exigence="documento", question=ASKED,
                                                conditions=[("Lo que exige.", "", 0, "no_consta")]),
    "marca externo": lambda call: says("no_determinado", external=True),
    "salida inválida": lambda call: "esto no es un objeto JSON",
}

QUOTE = re.compile(r"[A-ZÁÉÍÓÚ][^.\n]{25,}\.")


def first_sentence(call):
    """Una oración de verdad de los documentos del grupo, para citarla."""
    for alias, text in call.documents.items():
        found = QUOTE.search(text)
        if found:
            return alias, found.group(0)
    return None


def concludes(result):
    def script(call):
        quote = first_sentence(call)
        if quote is None:
            return None
        return says(result, quote, exigence="condicion", conditions=[
            ("Lo que exige.", quote[1], 1, result)])
    return script


def concludes_without_a_located_citation(call):
    alias = next(iter(call.documents), None)
    if alias is None:
        return None
    return says("cumple", (alias, "Una oración que no está en ningún documento."),
                exigence="condicion", conditions=[
                    ("Lo que exige.", "Una oración que no está en ningún documento.", 1,
                     "cumple")])


CONCLUSIONS = {
    "cumple con cita": concludes("cumple"),
    "no cumple con cita": concludes("no_cumple"),
    "cumple con una cita que no se ubica": concludes_without_a_located_citation,
}


def portal_data(item, offer):
    """Los datos del Portal de la oferta: garantía, total y CUIT (inventados)."""
    data = pm.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", currency="ARS", total=Decimal("435000.00"), item=item)
    pm.PortalGuarantee.objects.create(
        offer_data=data, guarantee_type="Garantía de mantenimiento de oferta",
        guarantee_form="Póliza de caución", amount=Decimal("21750.00"), item=item)


def assert_three_outputs(run):
    found = evaluation.three_outputs(run)
    assert found["cells"] == len(sheets_firm(run.matrix_version.procedure)) or found["cells"]
    assert not found["sin_documento_sin_pregunta"], found
    assert not found["no_determinado_sin_nombrar"], found
    assert not found["problems"], found
    return found


@pytest.mark.parametrize("with_portal", [False, True], ids=["sin Portal", "con Portal"])
@pytest.mark.parametrize("behavior", list(BEHAVIORS))
def test_every_cell_the_rules_leave_is_one_of_the_three_outputs(
        offer, operator_user, procedure, model, portal, behavior, with_portal):
    """REQ-120: el doble contesta lo mismo a todos los requisitos del caso chico y las reglas
    (forma de garantía, opción, presentación, externos, técnico, ilegible, Portal, ausencia) hacen
    lo suyo, con el Portal cargado y sin él: toda celda guardada es «cumple» con fundamento, «no
    cumple» con cita o «no determinado» con su pregunta o su documento nombrado."""
    if with_portal:
        portal_data(portal, offer)
    model.evaluates(BEHAVIORS[behavior])
    _, runs = run_all(operator_user, procedure, offers=[offer])
    found = assert_three_outputs(runs[0])
    assert found["cells"] == len(sheets_firm(procedure))


@pytest.mark.parametrize("answer", ["si", "no", "parcial"])
@pytest.mark.parametrize("with_portal", [False, True], ids=["sin Portal", "con Portal"])
@pytest.mark.parametrize("conclusion", list(CONCLUSIONS))
def test_every_cell_after_a_conclusion_and_its_contrast_is_one_of_the_three_outputs(
        offer, operator_user, procedure, model, portal, conclusion, with_portal, answer):
    """REQ-120: las conclusiones del modelo (con su cita, sin cita ubicada), con cada respuesta del
    contraste, pasan por las reglas: toda celda guardada es una de las tres formas."""
    if with_portal:
        portal_data(portal, offer)
    model.evaluates(CONCLUSIONS[conclusion])
    model.contrasts(lambda call: {"razonamiento": "Porque sí.", "respuesta": answer})
    _, runs = run_all(operator_user, procedure, offers=[offer])
    found = assert_three_outputs(runs[0])
    outcomes = {r.outcome for r in runs[0].results.all()}
    if conclusion != "cumple con una cita que no se ubica" and answer == "si":
        assert outcomes & {"cumple", "no_cumple"}


def test_the_difference_between_the_offer_and_the_portal_asks_the_commission_with_both_positions(
        with_policy, operator_user, procedure, model, portal):
    """REQ-120 y ADR-0053 (decisión 4, enmienda del 2026-10-15): el valor de la oferta distinto del
    dato del Portal es «no determinado» `falta_coincidencia` con las dos citas, la diferencia en la
    explicación y una pregunta a la Comisión con las dos posturas: la oferta con su cita de
    documento y página, el Portal con su enlace y fecha, la contradicción y cuál rige. Cumple la
    forma de `question_form` y la medida no la exceptúa."""
    from tests.assessment.test_portal_facts import (
        AMOUNT,
        GUARANTEE,
        POLICY,
        portal_data as guarantee_data,
    )

    guarantee_data(portal, with_policy, amount="25000.00")
    model.evaluates(lambda call: says(
        "cumple", call.quote(POLICY.split(", el ")[0]), exigence="documento",
        datos=[(call.alias_with(POLICY[:20]), AMOUNT)]) if GUARANTEE in call.requirement
        else None)
    _, runs = run_all(operator_user, procedure, offers=[with_policy])
    result = results_of(runs[0])[number_of(procedure, GUARANTEE)]
    assert (result.outcome, result.doubt) == ("no_determinado", "falta_coincidencia")
    assert result.citations.filter(kind="oferta").exists() and result.citations.filter(
        kind="portal").exists()
    assert "25000.00" in result.explanation
    question = am.Question.objects.get(result=result).text
    closing = question.splitlines()[-1]
    assert "se contradicen" in closing and "¿Cuál rige" in closing
    assert "poliza.pdf, página 1" in closing and "https://portal.invalid/cuadro" in closing
    # La forma de la medida (REQ-105): requisito, conclusión, texto de la oferta y dirigida a la Comisión.
    form = evaluation.question_form(
        question, requirement_text=result.citations.filter(kind="pliego").first().text,
        requirement_number=result.requirement.number, outcome_label="No determinado",
        doubt_label="Falta de coincidencia con el Portal",
        offer_texts=list(result.citations.filter(kind__in=("oferta", "portal"))
                         .order_by("kind", "order").values_list("text", flat=True)))
    assert form["conforme"], form
    found = assert_three_outputs(runs[0])
    assert "falta_coincidencia_sin_pregunta" not in found


def finished(pair, number=1, documents=("oferta.pdf",)):
    """La pregunta final del par, como la guarda `evaluate_offer`."""
    asked = combine.compose_question(number, pair.text.text, pair.combined,
                                     documents=list(documents))
    return replace(pair.combined, question=asked)


def test_portal_cubre_parte_asks_naming_the_condition_and_the_portal_datum(offer, portal):
    """REQ-120 (`portal_cubre_parte`): el dato del Portal cubre una parte del requisito y el resto
    queda abierto: «no determinado» con una pregunta a la Comisión que nombra lo que pide el pliego
    y el dato del Portal que sí hay. Sin las condiciones del modelo (antes: la pregunta del modelo o
    ninguna)."""
    from tests.assessment.test_ajuste_t240 import POLICY_UPLOAD, chosen_form
    from tests.assessment.test_portal_facts import pair_of

    chosen_form(portal, offer, "Seguros")
    pair = pair_of(POLICY_UPLOAD, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cubre_parte"
    assert pair.combined.outcome == "no_determinado"
    question = pair.combined.question
    assert "21750.00" in question and "Portal" in question and "Comisión" in question
    assert "cargar el documento electrónico de la póliza" in question
    assert not combine.asks_the_offeror(question)
    assert question in combine.compose_question(1, pair.text.text, pair.combined)
    assert combine.combined_problem(finished(pair)) == ""


def test_portal_cubre_parte_with_conditions_names_each_open_condition_and_the_portal_datum(
        offer, portal):
    """REQ-120 (`portal_cubre_parte`): con las condiciones del modelo, la pregunta nombra las que
    quedan abiertas (no las que el Portal cubre) y el dato del Portal que sí hay."""
    from tests.assessment.test_ajuste_t240 import POLICY_UPLOAD, chosen_form
    from tests.assessment.test_portal_facts import pair_of

    chosen_form(portal, offer, "Seguros")
    pair = pair_of(POLICY_UPLOAD, combine.Combined(outcome="no_determinado", doubt="sin_dato"))
    pair.conditions = {0: [
        {"condicion": "Cargar el documento de la póliza", "dato": "", "cita": None,
         "resultado": "no_consta", "resultado_modelo": "no_consta"}]}
    pair.groups = [SimpleNamespace(index=0, result="no_determinado", citations=[], unreadable=None,
                                   external=False)]
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cubre_parte"
    question = pair.combined.question
    assert "Cargar el documento de la póliza" in question and "Portal" in question
    assert combine.combined_problem(finished(pair)) == ""


def test_a_portal_that_agrees_against_an_offer_that_does_not_comply_asks_which_rules(
        offer, portal):
    """REQ-120 (`falta_coincidencia` por conflicto con el texto): el Portal cumple lo que exige el
    pliego y el texto de la oferta concluyó que no cumple: «no determinado» `falta_coincidencia` con
    una pregunta que nombra la condición y el dato del Portal."""
    from tests.assessment.test_t231 import GUARANTEE_REQ
    from tests.assessment.test_t231 import portal_data as guarantee_data
    from tests.assessment.test_portal_facts import pair_of

    guarantee_data(portal, offer, amount="4620585.50", total="92411710.00")
    pair = pair_of(GUARANTEE_REQ, combine.Combined(
        outcome="no_cumple", citations=[cite(0, "No se constituye garantía.")]))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert pair.combined.doubt == "falta_coincidencia"
    question = pair.combined.question
    assert "garantía de mantenimiento" in question and "4620585.50" in question
    assert "Comisión" in question and not combine.addresses_offeror(question)
    assert combine.combined_problem(finished(pair)) == ""


# --- 4. Cada conversión del código ---------------------------------------------------------------


def declaration_call(call):
    return "declaración jurada" in call.requirement


def declaration_result(runs, procedure):
    return results_of(runs[0])[number_of(procedure, "declaración jurada")]


def two_conditions(call, *, second="cumple", datum="firmada", cite=1, model_result="cumple"):
    alias = call.alias_with(DECLARATION)
    return says(model_result, (alias, DECLARATION), conditions=[
        ("El oferente declara que está habilitado para contratar.", DECLARATION, 1, "cumple"),
        ("La declaración está firmada por el representante.", datum, cite, second)])


def run_declaration(user, procedure, offer, model, script, **kwargs):
    model.evaluates(lambda call: script(call) if declaration_call(call) else None)
    _, runs = run_all(user, procedure, offers=[offer], **kwargs)
    return runs[0], declaration_result([runs[0]], procedure)


def conforms(run, result):
    """La celda guardada cumple una de las tres formas."""
    found = evaluation.three_outputs(run)
    assert not (found["sin_documento_sin_pregunta"] or found["no_determinado_sin_nombrar"]
                or found["problems"]), found
    return result


def question_of(result):
    return am.Question.objects.get(result=result).text


def assert_asks_about(result, *needles):
    """La celda tiene su pregunta, dirigida a la Comisión, y nombra lo que se pide."""
    text = question_of(result)
    closing = text.splitlines()[-1]
    assert "Comisión" in closing and not combine.addresses_offeror(closing), text
    for needle in needles:
        assert needle in text, (needle, text)


def anomalies(run, kind):
    return [a for a in run.anomalies if a["type"] == kind]


def condition_case(**kwargs):
    return lambda call: two_conditions(call, **kwargs)


def test_conversion_condicion_sin_cita(offer, operator_user, procedure, model):
    """REQ-120: la condición «cumple» cuya cita no se ubicó pasa a «no determinado»: la explicación
    nombra la condición y la pregunta a la Comisión también."""
    run, result = run_declaration(operator_user, procedure, offer, model,
                                  condition_case(cite=5))
    assert anomalies(run, "condicion_sin_cita")
    assert result.outcome == "no_determinado"
    assert "La declaración está firmada" in result.explanation
    assert_asks_about(result, "La declaración está firmada")
    conforms(run, result)


def test_conversion_condicion_sin_dato(offer, operator_user, procedure, model):
    """REQ-120: la condición «cumple» sin dato pasa a «no determinado» y se nombra."""
    run, result = run_declaration(operator_user, procedure, offer, model,
                                  condition_case(datum=""))
    assert anomalies(run, "condicion_sin_dato")
    assert result.outcome == "no_determinado"
    assert "La declaración está firmada" in result.explanation
    assert_asks_about(result, "La declaración está firmada")
    conforms(run, result)


def test_conversion_condicion_no_aplica(offer, operator_user, procedure, model):
    """REQ-120: la condición «cumple» con el dato «no aplica…» la decide una regla, no el modelo:
    pasa a «no determinado» y se nombra."""
    run, result = run_declaration(operator_user, procedure, offer, model, condition_case(
        datum="No aplica: la oferta eligió otra forma."))
    assert anomalies(run, "condicion_no_aplica")
    assert result.outcome == "no_determinado"
    assert_asks_about(result, "La declaración está firmada")
    conforms(run, result)


def test_conversion_resultado_derivado(offer, operator_user, procedure, model):
    """REQ-120: el modelo dice «cumple» y una condición no se determinó: gana el más conservador,
    la explicación nombra la condición que falta y se pregunta por ella."""
    run, result = run_declaration(operator_user, procedure, offer, model, condition_case(
        second="no_determinado", datum="", cite=0))
    assert anomalies(run, "resultado_derivado")
    assert result.outcome == "no_determinado"
    assert "Falta el dato de la condición" in result.explanation
    assert_asks_about(result, "La declaración está firmada")
    conforms(run, result)


def test_conversion_resultado_no_sostenido(offer, operator_user, procedure, model):
    """REQ-120: el modelo dice «no determinado» y sus condiciones concluyen «cumple»: no se da por
    concluido; la explicación lo dice y la pregunta también."""
    alias_script = lambda call: says(  # noqa: E731
        "no_determinado", (call.alias_with(DECLARATION), DECLARATION), conditions=[
            ("El oferente declara que está habilitado.", DECLARATION, 1, "cumple")])
    run, result = run_declaration(operator_user, procedure, offer, model, alias_script)
    assert anomalies(run, "resultado_no_sostenido")
    assert "no coincide con el de sus condiciones" in result.explanation
    assert_asks_about(result, "no coincide")
    conforms(run, result)


def test_conversion_salida_invalida(offer, operator_user, procedure, model):
    """REQ-120: una salida que no es un objeto válido (también en el reintento) deja el grupo
    «no determinado» `duda` con el motivo en la explicación y la pregunta por defecto."""
    run, result = run_declaration(operator_user, procedure, offer, model,
                                  lambda call: "esto no es JSON")
    assert result.outcome == "no_determinado" and result.doubt == "duda"
    assert "no devolvió una salida válida" in result.explanation
    assert_asks_about(result)
    conforms(run, result)


def test_conversion_conclusion_sin_cita(offer, operator_user, procedure, model):
    """REQ-120: una conclusión cuya cita no se ubica (también en el reintento) queda «no
    determinado» `sin_cita`, con la pregunta por el texto que muestre lo exigido."""
    run, result = run_declaration(operator_user, procedure, offer, model, lambda call: says(
        "cumple", (call.alias_with(DECLARATION), "Una oración que no está en la oferta.")))
    assert result.outcome == "no_determinado" and result.doubt == "sin_cita"
    assert result.explanation.strip()
    assert_asks_about(result, "cita")
    conforms(run, result)


def test_conversion_contraste_invalido(offer, operator_user, procedure, model):
    """REQ-120: un contraste con salida inválida deja el «cumple» sin corroborar: la explicación
    dice que el contraste no lo corroboró y la pregunta pide confirmarlo, corregirlo o
    rechazarlo."""
    model.contrasts(lambda call: "{}")
    run, result = run_declaration(operator_user, procedure, offer, model,
                                  lambda call: says("cumple", call.quote(DECLARATION)))
    assert anomalies(run, "contraste_invalido")
    assert result.outcome == "no_determinado" and result.doubt == "sin_corroborar"
    assert "El contraste no corroboró" in result.explanation
    assert_asks_about(result, "confirma, corrige o rechaza")
    conforms(run, result)


def test_conversion_pedido_fuera_de_contexto(offer, operator_user, procedure, model, engine,
                                             settings):
    """REQ-120: si ni sin documentos entra el pedido, nada se manda y el requisito queda «no
    determinado» `lectura_incompleta` con la nota del pedido y la pregunta por las partes sin
    leer."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = count_words(prompting.load_prompt("evaluacion"))
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = declaration_result(runs, procedure)
    assert anomalies(runs[0], "pedido_fuera_de_contexto")
    assert result.outcome == "no_determinado" and result.doubt == "lectura_incompleta"
    assert evaluate.TOO_LONG_NOTE in result.explanation
    assert_asks_about(result, "partes sin leer")
    conforms(runs[0], result)


def test_conversion_requisito_sin_cita(offer, operator_user, procedure, model, monkeypatch):
    """REQ-120: un requisito sin texto citado del pliego no se puede evaluar: «no determinado» con
    esa explicación y la pregunta por el texto del pliego."""
    real = grounds.requirement_text
    number = number_of(procedure, "declaración jurada")
    monkeypatch.setattr(grounds, "requirement_text", lambda requirement: (
        replace(real(requirement), quotes=[]) if requirement.number == number
        else real(requirement)))
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = declaration_result(runs, procedure)
    assert anomalies(runs[0], "requisito_sin_cita")
    assert result.outcome == "no_determinado" and result.doubt == "duda"
    assert evaluate.NO_QUOTE_NOTE in result.explanation
    assert_asks_about(result, "texto del pliego")
    assert question_of(result).startswith(f"Requisito {number}.")
    conforms(runs[0], result)


def test_conversion_no_cumple_sin_clausula(offer, operator_user, procedure, model):
    """REQ-120: un «no cumple» técnico sin cláusula del pliego pasa a «no determinado» `sin_dato`
    con la nota de la cláusula faltante; la fila técnica queda pendiente del informe del área, que
    nombra el documento, y la explicación conserva la nota (la opinión del sistema)."""
    row = next(r for r in sheets_firm(procedure) if r.category == "tecnico" and r.items == [1])

    def script(call):
        if "Renglón 1 del pliego" in call.requirement:
            quote = first_sentence(call)
            if quote:
                return {**says("no_cumple", quote, exigence="condicion",
                               conditions=[("Lo que exige.", quote[1], 1, "no_cumple")]),
                        "clausula": ""}
        return None

    model.evaluates(script)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    assert anomalies(runs[0], "no_cumple_sin_clausula")
    assert result.outcome == "no_determinado" and result.doubt == "pendiente_informe_tecnico"
    assert combine.NO_CLAUSE_NOTE in result.explanation
    assert "informe" in result.explanation
    conforms(runs[0], result)


def test_no_cumple_sin_clausula_asks_for_the_clause_when_the_group_is_read(
        offer, operator_user, procedure, model):
    """REQ-120: el grupo que el código baja por la cláusula faltante lleva su pregunta por la cláusula
    del pliego (la del modelo vale solo si se dirige a la Comisión)."""
    from evaluon.assessment.services import evaluate as ev

    assert "cláusula" in ev.NO_CLAUSE_QUESTION and "pliego" in ev.NO_CLAUSE_QUESTION
    assert not combine.addresses_offeror(ev.NO_CLAUSE_QUESTION)
    assert not combine.addresses_offeror(ev.NO_QUOTE_QUESTION)
    groups = [combine.GroupResult(0, "no_determinado", doubt="sin_dato", explanation=WHY,
                                  question=ev.NO_CLAUSE_QUESTION)]
    combined = combine.combine(groups, unread=[], without_reading=())
    assert combine.combined_problem(final_form(combined)) == ""


def test_the_conversions_table_lists_every_conversion_the_tests_cover():
    """REQ-120: el inventario de `evaluate.CONVERSIONS` es el de las pruebas de arriba (una por
    conversión) y cada nombre es una anomalía que el código registra (`ANOMALY_*` de `evaluate` o de
    `prompting`) o el contraste por cláusula."""
    covered = {name.removeprefix("test_conversion_") for name in globals()
               if name.startswith("test_conversion_")} | {"clausulas"}
    assert covered == set(evaluate.CONVERSIONS)
    registered = {value for module in (evaluate, prompting) for name, value in vars(module).items()
                  if name.startswith("ANOMALY_") and isinstance(value, str)}
    # `salida_invalida` y `conclusion_sin_cita` son las anomalías de `prompting`.
    assert set(evaluate.CONVERSIONS) - {"clausulas"} <= registered


# --- Los pares de la 015 --------------------------------------------------------------------------


def test_the_questions_of_t263_and_t268_are_kept(big_offer, operator_user, procedure, model):
    """REQ-120 (T-263, T-268): O2 R16 (el modelo contesta «no consta» con exigencia «documento» y
    escribió una pregunta) y O3 R22 (dos lecturas de grupo que dicen que el documento no está)
    eran «no se encontró el documento» sin la pregunta del modelo. Ahora la celda es «no se
    encontró el documento» con la pregunta del modelo, el requisito y el documento nombrados."""
    wrote = "¿Las declaraciones juradas escaneadas cuentan como los anexos que pide el pliego?"

    def script(call):
        if declaration_call(call):
            return says("no_consta", exigence="documento", question=wrote, conditions=[
                ("Suscribir y adjuntar los anexos.", "", 0, "no_consta")])

    model.evaluates(script)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    groups = [c for c in model.calls if declaration_call(c)]
    assert len(groups) == 3   # tres grupos de documentos, los tres «no consta»
    assert result.outcome == "sin_documento" and result.exigence == "documento"
    question = question_of(result)
    assert question.splitlines()[-1] == wrote
    assert question.startswith(f"Requisito {number_of(procedure, 'declaración jurada')}: «")
    assert "no se encontró el documento que el pliego exige" in question
    assert evaluation.three_outputs(runs[0])["sin_documento_sin_pregunta"] == []


def test_the_missing_document_without_a_model_question_still_asks(
        offer, operator_user, procedure, model):
    """REQ-120: aunque el modelo no haya escrito pregunta, «no se encontró el documento» lleva la
    que arma el código."""
    _, runs = run_all(operator_user, procedure, offers=[offer])
    missing = [r for r in runs[0].results.all() if r.outcome == "sin_documento"]
    assert missing, "el doble por omisión contesta «no consta» al documento"
    for result in missing:
        assert_asks_about(result, "Requisito", "documento")
    assert evaluation.three_outputs(runs[0])["sin_documento_sin_pregunta"] == []


# --- 5. La medida de medir_evaluacion ------------------------------------------------------------


def a_run_with(offer, procedure, operator_user, model, script=lambda call: None):
    model.evaluates(script)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    return runs[0]


def test_the_measure_counts_a_missing_document_without_a_question(
        offer, operator_user, procedure, model):
    """REQ-120, umbral 9: `three_outputs` cuenta las celdas «no se encontró el documento» sin
    pregunta, con su requisito. Se altera la corrida guardada: una evaluación nueva del par
    «no se encontró el documento» sin pregunta propia; mientras la pregunta de la anterior siga
    abierta vale, y respondida ya no."""
    run = a_run_with(offer, procedure, operator_user, model)
    clean = evaluation.three_outputs(run)
    assert clean["sin_documento"] and not clean["sin_documento_sin_pregunta"]
    victim = am.Question.objects.filter(result__run=run, result__outcome="sin_documento").first()
    other = am.Run.objects.create(
        request=run.request, offer=offer, matrix_version=run.matrix_version, number=run.number + 1,
        channel=run.channel, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    am.Result.objects.create(
        run=other, offer=offer, requirement=victim.requirement, outcome="sin_documento",
        exigence="documento", explanation=victim.result.explanation)
    assert evaluation.three_outputs(other)["sin_documento_sin_pregunta"] == []
    am.Answer.objects.create(question=victim, text="Sí.", answered_by=operator_user,
                             event=_event(operator_user))
    counted = evaluation.three_outputs(other)
    assert counted["sin_documento_sin_pregunta"] == [victim.requirement.number]
    assert counted["sin_documento"] == 1


def _event(user):
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, EventType, Outcome

    return audit.record(EventType.EVAL_ANSWER, outcome=Outcome.OK, channel=Channel.SCREEN,
                        user=user)


def test_the_measure_counts_an_undetermined_without_a_question_or_a_named_document(
        offer, operator_user, procedure, model):
    """REQ-120, umbral 9: un «no determinado» `duda` sin pregunta ni documento nombrado se cuenta
    con su requisito; `thresholds_016` lo marca como «no cumple» y el comando lo informa."""
    run = a_run_with(offer, procedure, operator_user, model, lambda call: says("no_determinado"))
    # La pregunta de un par ya respondida no vale para la evaluación nueva del par.
    victim = am.Question.objects.filter(result__run=run, result__outcome="no_determinado").first()
    requirement = victim.requirement
    am.Answer.objects.create(question=victim, text="Sí.", answered_by=operator_user,
                             event=_event(operator_user))
    other = am.Run.objects.create(
        request=run.request, offer=offer, matrix_version=run.matrix_version, number=run.number + 1,
        channel=run.channel, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    am.Result.objects.create(
        run=other, offer=offer, requirement=requirement, outcome="no_determinado", doubt="duda",
        exigence="condicion", explanation="El modelo dudó.")
    found = evaluation.three_outputs(other)
    assert found["no_determinado_sin_nombrar"] == [requirement.number]
    measure = {"three_outputs": evaluation.aggregate_three_outputs(
        [{"offer_number": 1, "three_outputs": found}])}
    rows = evaluation.thresholds_016(measure)
    assert [ok for _, _, ok in rows] == [True, False, True]
    assert rows[1][1] == "0 de 1"
    assert evaluation.thresholds_016({}) == []


def test_the_measure_of_a_real_run_meets_the_threshold(offer, operator_user, procedure, model):
    """REQ-120, umbral 9: en la corrida del caso chico con el doble, 0 «no se encontró el
    documento» sin pregunta y el 100 % de los «no determinado» con pregunta o documento."""
    run = a_run_with(offer, procedure, operator_user, model)
    found = evaluation.three_outputs(run)
    total = {"three_outputs": evaluation.aggregate_three_outputs(
        [{"offer_number": offer.number, "three_outputs": found}])}
    assert found["cells"] == len(sheets_firm(procedure))
    assert all(ok for _, _, ok in evaluation.thresholds_016(total))


def test_the_command_reports_the_three_outputs(db, operator_user, fake_ai, model, tmp_path,
                                               monkeypatch):
    """REQ-120: `medir_evaluacion --caso-chico` cuenta las tres salidas de cada celda y las informa
    contra el umbral 9 (016), con el doble del caso chico."""
    import yaml

    from evaluon.accounts import permissions
    from tests.assessment.test_evaluation import LIST, oracle_for
    from tests.tenders.conftest import TEST_PASSWORD

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    model.evaluates(oracle_for(yaml.safe_load(LIST.read_text(encoding="utf-8"))))
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--caso-chico",
                 "--corridas", str(tmp_path), "--commit", "abc1234", stdout=out)
    lines = [line for line in out.getvalue().splitlines() if "(016)" in line]
    measured = [line for line in lines if line.endswith(("· cumple", "· no cumple"))]
    assert len(measured) == 3 and all(line.endswith("· cumple") for line in measured), lines
    assert "sin pregunta (REQ-120) (016): 0 de" in measured[0]
    summary = next(tmp_path.glob("*/resumen*.md"), None)
    assert summary is None or "REQ-120" in summary.read_text(encoding="utf-8")
