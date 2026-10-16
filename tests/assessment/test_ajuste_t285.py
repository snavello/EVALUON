"""Ajuste único del paso 2 en la evaluación (T-285; REQ-119, REQ-120; spec 016; plan 016, «Paso 2»;
ADR-0070, punto 5).

La medición T-283 mostró celdas que el código convertía mal (D-283-5 y D-283-6). Cada prueba
reproduce la forma de la celda con dobles y textos inventados (P4), nunca con texto de un caso:

- D-283-5: «no se encontró el documento» solo cuando el pliego exige un documento, se leyó todo y
  ninguno es ese (la lectura no señaló nada sobre él); la condición de una opción que la oferta no
  usa queda «no aplica» (decisión del 2026-10-10, «Requisito de la forma elegida»).
- D-283-6: (b) una condición con su dato citado no se pierde; (c) el Portal no deja abierta una
  condición que su dato resuelve ni cambia lo que dejó la lectura cuando no puede comparar; (d) la
  ausencia verificada corre cuando el modelo no encontró nada (decisión del 2026-10-12).
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from evaluon.assessment import absence, combine, options, portal_facts, prompting
from evaluon.assessment import models as am
from evaluon.assessment.citations import Located
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_comite_t257 import NEGATIVE, apply, condition, pair_with
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    offer_cites,
    results_of,
    run_all,
)
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import portal_data

pytestmark = pytest.mark.django_db

DOC = SimpleNamespace(pk=1, title="nota.pdf")


def located(text, start=0):
    return Located(document=DOC, reading=None, page=1, char_start=start,
                   char_end=start + len(text), text=text)


# --- D-283-5 (a): «no se encontró el documento» solo si la lectura no señaló nada sobre él ---------


def test_d283_5_a_document_the_reading_pointed_at_is_not_a_missing_document():
    """REQ-120, P3 (D-41: «no se encontró el documento» solo si el pliego exige un documento y la
    oferta leída no lo trae): si los grupos dicen «no consta» pero uno ubicó un texto de la oferta
    sobre el requisito, la celda es «no determinado» con ese texto citado y la pregunta de si el
    documento está, nunca «no se encontró el documento»."""
    seen = located("Adjuntamos la nota de conformidad con las bases.")
    groups = [combine.GroupResult(0, "no_consta", exigence="documento", found=True, seen=[seen]),
              combine.GroupResult(1, "no_consta", exigence="documento")]

    combined = combine.combine(groups, unread=[])

    assert (combined.outcome, combined.doubt) == ("no_determinado", "sin_dato")
    assert combined.citations == [seen]
    assert combined.explanation == combine.SEEN_NOTE and combined.question == combine.SEEN_QUESTION
    asked = combine.compose_question(3, "Presentar la declaración jurada.", combined)
    assert asked.endswith(combine.SEEN_QUESTION) and "Adjuntamos la nota de conformidad" in asked
    assert combine.combined_problem(replace(combined, question=asked)) == ""


def test_d283_5_nothing_pointed_at_is_still_the_missing_document():
    """REQ-120 (D-41): sin nada señalado y con la lectura completa sigue siendo «no se encontró el
    documento», con su pregunta (T-277)."""
    groups = [combine.GroupResult(0, "no_consta", exigence="documento"),
              combine.GroupResult(1, "no_consta", exigence="documento")]

    combined = combine.combine(groups, unread=[])

    assert combined.outcome == "sin_documento" and combined.citations == []


def test_d283_5_a_conclusion_without_its_citation_is_not_a_missing_document_either():
    """REQ-120 (D-41): un grupo «no consta» sobre el que el modelo había concluido (el modelo dijo
    «cumple» y sus condiciones no traen nada) muestra que algo leyó: «no determinado» con la
    pregunta, no «no se encontró el documento»."""
    groups = [combine.GroupResult(0, "no_consta", exigence="documento", found=True)]

    combined = combine.combine(groups, unread=[])

    assert combined.outcome == "no_determinado" and combined.question == combine.SEEN_QUESTION


def test_d283_5_the_reading_that_cites_a_text_about_the_document_is_asked(
        offer, operator_user, procedure, model):
    """REQ-120, P3 (de punta a punta con el doble): el pliego exige un documento, el modelo dice «no
    consta» pero cita una oración de la oferta: la celda queda «no determinado» con esa cita y la
    pregunta de si el documento está; sin la cita, «no se encontró el documento»."""
    def function(call):
        if "libre deuda" in call.requirement:
            return says("no_consta", call.quote(DECLARATION), exigence="documento",
                        conditions=[("Acompañar el certificado.", DECLARATION, 1, "no_consta")])
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "libre deuda")]

    assert (result.outcome, result.doubt) == ("no_determinado", "sin_dato")
    assert [c.text for c in offer_cites(result)] and DECLARATION in offer_cites(result)[0].text
    question = am.Question.objects.get(result=result)
    assert question.text.endswith(combine.SEEN_QUESTION)


# --- D-283-5 (a): la condición de una opción que la oferta no usa no es un documento faltante ------


def test_d283_5_the_condition_of_an_option_marked_unused_is_not_a_missing_document():
    """REQ-120, REQ-103 (D-13): con «no consta» en todos los grupos y el modelo marcando que la
    oración vale solo para quien usa una opción que la oferta no usa, la celda no es «no se encontró
    el documento»: queda «no determinado» con la nota de la opción, y la regla de la opción decide."""
    groups = [combine.GroupResult(0, "no_consta", exigence="documento", option_use="no")]

    combined = combine.combine(groups, unread=[])

    assert (combined.outcome, combined.doubt) == ("no_determinado", "sin_dato")
    assert combined.explanation == combine.OPTION_NOTE
    assert combined.question == combine.OPTION_QUESTION


def test_d283_5_without_the_option_in_the_matrix_the_mark_of_the_model_makes_it_not_applicable(
        offer):
    """REQ-103, REQ-120 (D-13; decisión del 2026-10-10, «Requisito de la forma elegida»): en una
    matriz sin `opcion` (validada antes de T-258), si el modelo marcó en todos los grupos que la
    oración vale solo para quien usa una opción y que la oferta no la usa, sin citar nada, la celda
    es «No aplica (opción no usada)», con el origen de la marca registrado (P6)."""
    text = ("Quien se presente como taller asociado acompañará la constancia de su asociación "
            "vigente.")
    combined = combine.combine([combine.GroupResult(0, "no_consta", exigence="documento",
                                                    option_use="no")], unread=[])
    pair = pair_with(text, combined, [condition("Acompañar la constancia", "no_consta")],
                     option_use="no")

    name, result = apply(offer, pair)

    assert name == "opcion_no_usada"
    assert result.facts["aplica"] is False
    assert result.facts["opcion"] == options.OTHER and result.facts["opcion_origen"] == "modelo"
    assert result.question == "" and not result.ask


def test_d283_5_without_the_option_and_without_the_mark_the_rule_still_says_nothing(offer):
    """REQ-103 (D-257-6): sin `opcion` en la matriz y sin la marca «no» del modelo, la regla de la
    opción no decide; con la marca «si» tampoco."""
    text = "Quien se presente como taller asociado acompañará la constancia de su asociación."
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato", exigence="documento")
    for marked in (None, "no_consta", "si"):
        name, _ = apply(offer, pair_with(text, combined, [condition("Acompañar", "no_consta")],
                                         option_use=marked))
        assert name != "opcion_no_usada", marked


# --- D-283-6 (b): una condición con su dato citado no se pierde -------------------------------------

SIGNED = "El presente formulario se firma y se adjunta a la oferta."


def test_d283_6_b_a_condition_whose_datum_is_inside_a_located_citation_keeps_it(
        offer, operator_user, procedure, model):
    """REQ-104, REQ-120 (D-39; D-237-2 sigue: no se presta la cita de otra condición): el modelo da
    por «cumple» varias condiciones con una sola oración citada y numera solo la primera; la otra
    trae como dato un trozo literal de esa misma oración. Esa es su cita: la celda no pasa a «sin
    dato» y queda la anomalía que lo registra (P6)."""
    def function(call):
        if "declaración jurada" in call.requirement:
            return says("cumple", call.quote(DECLARATION), exigence="documento", conditions=[
                ("Presentar la declaración.", DECLARATION, 1, "cumple"),
                ("Que esté habilitado.", "me encuentro habilitado para contratar", 0, "cumple")])
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]

    assert result.outcome == "cumple"
    second = result.facts["condiciones"][1]
    assert second["resultado"] == "cumple" and DECLARATION in second["cita"]["texto"]
    assert any(a["type"] == "condicion_citada_por_su_dato" for a in runs[0].anomalies)


@pytest.mark.parametrize("datum", ["", "sí", "Otro texto que no está en ninguna cita."])
def test_d283_6_b_a_datum_that_is_not_in_a_located_citation_is_still_without_its_citation(
        offer, operator_user, procedure, model, datum):
    """REQ-104, P3 (D-237-2): un dato vacío, trivial o que no está en la cita ubicada no la toma: la
    condición queda sin cita y la celda «no determinado»."""
    def function(call):
        if "declaración jurada" in call.requirement:
            return says("cumple", call.quote(DECLARATION), exigence="documento", conditions=[
                ("Presentar la declaración.", DECLARATION, 1, "cumple"),
                ("Que esté firmada.", datum, 0, "cumple")])
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]

    assert result.outcome == "no_determinado"


def test_d283_6_b_the_instruction_says_one_citation_can_hold_several_conditions():
    """REQ-119 (D-39, D-41): la instrucción vigente dice que una misma cita puede ser la de varias
    condiciones y que un documento está si alguno de los recibidos lo trae, aunque tenga otro
    título."""
    text = prompting.load_prompt("evaluacion")

    assert "una misma cita puede ser la de varias condiciones" in text
    assert "aunque tenga otro título o venga junto con otros" in text


# --- D-283-6 (c): el Portal ----------------------------------------------------------------------

THRESHOLD = ("Si el total de la oferta excede el tope de la cláusula previa, el oferente constituirá "
             "una garantía de oferta del cinco por ciento del monto total de la oferta.")


def _portal_pair(text, combined, records):
    return SimpleNamespace(
        combined=combined, text=SimpleNamespace(text=text), datos=[],
        requirement=SimpleNamespace(items=[], category="economico", number=9, proposed={}),
        groups=[SimpleNamespace(index=0, result="no_determinado", citations=[], portal=[])],
        conditions={0: records})


def test_d283_6_c_the_amount_threshold_of_the_guarantee_is_covered_when_the_portal_coincides(
        offer, portal):
    """REQ-103 (D-16, ADR-0053; regla de T-277: decide con la cita cuando el dato alcanza): con la
    garantía del Portal igual al porcentaje que exige el pliego, la condición que repite el umbral de
    monto que hace exigible la garantía no queda abierta: «cumple» con la cita del Portal."""
    portal_data(portal, offer)
    records = [condition("Que el total de la oferta exceda el tope de la cláusula previa",
                         "no_determinado"),
               condition("Constituir una garantía del cinco por ciento del monto total",
                         "no_consta")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    pair = _portal_pair(THRESHOLD, combined, records)

    decided = portal_facts.rule(pair, SimpleNamespace(offer=offer))

    assert decided.outcome == "cumple" and decided.facts["regla"] == "portal_cumple"
    assert [c.get("cubierta_por") for c in decided.facts["condiciones"]] == ["umbral", "portal"]
    assert decided.portal


def test_d283_6_c_the_threshold_is_not_covered_without_the_threshold_in_the_requirement(
        offer, portal):
    """REQ-103, P3: si la oración del pliego no empieza por ese umbral, la condición no se cubre
    por regla (no se adivina qué umbral es)."""
    portal_data(portal, offer)
    text = ("El oferente constituirá una garantía de oferta del cinco por ciento del monto total de "
            "la oferta.")
    records = [condition("Que el total de la oferta exceda el tope de otra cláusula", "no_determinado")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")

    decided = portal_facts.rule(_portal_pair(text, combined, records),
                                SimpleNamespace(offer=offer))

    assert decided.outcome == "no_determinado"
    assert not portal_facts.threshold_condition(records[0]["condicion"], text)


def test_d283_6_c_when_the_portal_cannot_compare_the_reading_keeps_its_motive_and_question(
        offer, portal):
    """REQ-120, REQ-103 (T-277): si el dato del Portal no responde a lo que pide el requisito, el
    Portal no cambia lo que dejó la lectura (un contraste que no corroboró, con su pregunta): solo
    agrega su cita."""
    portal_data(portal, offer)
    text = "La garantía deberá estar individualizada con el número del procedimiento."
    records = [condition("Individualizar la garantía con el número del procedimiento", "cumple")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_corroborar",
                                proposed="cumple", ask=True)

    decided = portal_facts.rule(_portal_pair(text, combined, records),
                                SimpleNamespace(offer=offer))

    assert (decided.outcome, decided.doubt, decided.proposed) == (
        "no_determinado", "sin_corroborar", "cumple")
    assert decided.facts["regla"] == "portal_cita_agregada" and decided.portal
    asked = combine.compose_question(9, text, decided)
    assert "contraste no lo corroboró" in asked and "porcentaje" not in asked


# --- D-283-6 (d): la ausencia verificada corre cuando el modelo no encontró nada -------------------

TERM = "Mantener la validez de la oferta por sesenta días corridos desde la apertura."


def test_d283_6_d_a_cumple_of_the_model_without_anything_found_goes_to_the_absence(
        offer, operator_user, procedure, model):
    """REQ-104, REQ-120 (D-18; decisión del 2026-10-12, «Cumple por ausencia, con fundamento»): para
    un requisito supletorio, el modelo concluye «cumple» y su condición dice «no consta», sin dato ni
    cita: no hay una conclusión que citar, así que no se pide el reintento por la cita ni queda «sin
    cita»; la regla de la ausencia propone «cumple» con los documentos leídos."""
    def function(call):
        if "sesenta días" in call.requirement:
            return says("cumple", exigence="condicion", conditions=[
                ("Mantener la oferta sesenta días.", "", 0, "no_consta")])
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "sesenta días")]

    assert result.outcome == "cumple" and result.facts["regla"] == "cumple_por_ausencia"
    assert "ninguno lo contradice" in result.explanation
    readings = [s for s in runs[0].steps.filter(requirement=result.requirement, purpose="grupo")]
    assert len(readings) == 1   # sin reintento por la cita


def test_d283_6_d_a_no_cumple_of_the_model_is_never_turned_into_absence(
        offer, operator_user, procedure, model):
    """REQ-104, P3 (D-18): si el modelo dice «no cumple» aunque sus condiciones no traigan nada, no
    es ausencia: se pide la cita y la celda queda «no determinado»."""
    def function(call):
        if "sesenta días" in call.requirement:
            return says("no_cumple", exigence="condicion", conditions=[
                ("Mantener la oferta sesenta días.", "", 0, "no_consta")])
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "sesenta días")]

    assert result.outcome == "no_determinado" and result.facts.get("regla") != "cumple_por_ausencia"


def _ctx(offer, page_text):
    documents = [SimpleNamespace(document=SimpleNamespace(title="Nota de presentación"),
                                 pages=[{"page": 1, "text": page_text}])]
    return SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=documents))


def _absence_pair(datum):
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato", exigence="condicion")
    return pair_with(NEGATIVE, combined, [
        condition("La oferta no está condicionada", "no_consta", datum)])


def test_d283_6_d_a_comment_of_the_model_as_datum_does_not_stop_the_absence(offer):
    """REQ-104 (D-18): el «dato» que solo dice que la oferta no trae nada y no está en sus
    documentos es un comentario del modelo: la ausencia corre."""
    pair = _absence_pair("La oferta no menciona ninguna condición.")

    decided = absence.rule(pair, _ctx(offer, "Ofrecemos los bienes pedidos al precio cotizado."))

    assert decided is not None and decided.outcome == "cumple"


@pytest.mark.parametrize("datum, page", [
    # un texto de la oferta, aunque diga «no»: es lo que la oferta dice
    ("los precios no se mantendrán", "Aclaramos que los precios no se mantendrán."),
    # algo que no dice que no haya nada
    ("Precios sujetos a la cotización del día.", "Ofrecemos los bienes pedidos."),
])
def test_d283_6_d_a_datum_from_the_offer_or_that_says_something_stops_the_absence(
        offer, datum, page):
    """REQ-104, P3 (D-18): un dato que está en la oferta, o que dice algo en lugar de decir que no
    hay nada, frena la ausencia."""
    assert absence.rule(_absence_pair(datum), _ctx(offer, page)) is None


def test_d283_6_d_without_the_pages_at_hand_a_datum_still_stops_the_absence(offer):
    """REQ-104, P3: sin las páginas de la oferta a mano no se puede saber si el dato es de la
    oferta: la regla no decide."""
    ctx = SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=[
        SimpleNamespace(document=SimpleNamespace(title="Nota"))]))

    assert absence.rule(_absence_pair("La oferta no menciona ninguna condición."), ctx) is None


# --- D-283-7: las preguntas nombran el dato que falta y no piden lo que no corresponde -------------

C = prompting.Condition


def test_d283_7_a_condition_with_a_datum_of_the_reading_is_not_asked_as_if_there_were_none():
    """REQ-105, REQ-120 (D-39, D-40): la condición que quedó sin resultado pero trae un dato de la
    lectura se le muestra a la Comisión con ese dato para que la confirme; no se dice que no hay
    dato. La que no trae dato sigue con su pregunta de siempre."""
    conditions = [C("Que esté firmada", "firmado por el apoderado", 0, "no_determinado"),
                  C("Que tenga fecha", "", 0, "no_consta")]

    asked = prompting.missing_question(conditions)
    note = prompting.missing_note(conditions)

    assert "¿La Comisión confirma la condición «Que esté firmada»" in asked
    assert "«firmado por el apoderado»" in asked
    assert "la condición «Que tenga fecha», de la que no hay dato" in asked
    assert "Falta el dato de la condición: «Que tenga fecha»." in note
    assert "«Que esté firmada» tiene un dato de la lectura" in note
    assert not combine.asks_the_offeror(asked)


def test_d283_7_the_default_question_names_the_missing_datum():
    """REQ-105, REQ-120 (D-39: «si falta el dato de alguna, "no determinado" diciendo cuál»): la
    pregunta que arma el código para un «no determinado» por falta de dato nombra las condiciones sin
    resultado; sin condiciones, remite a la oración del pliego de la pregunta. Nunca «el dato que
    falta» sin nombrarlo."""
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato",
                                explanation="Falta el dato.")
    records = [{"condicion": "Indicar el plazo de entrega", "resultado": "no_determinado"},
               {"condicion": "Cotizar en pesos", "resultado": "cumple"}]

    named = combine.compose_question(4, "Cotizar en pesos e indicar el plazo.", combined,
                                     conditions=records)
    bare = combine.compose_question(4, "Cotizar en pesos e indicar el plazo.", combined)

    assert named.endswith("¿Cómo resuelve la Comisión «Indicar el plazo de entrega»? La lectura de "
                          "la oferta no trae ese dato.")
    assert "Cotizar en pesos»?" not in named
    assert "la oración del pliego citada arriba" in bare
    for asked in (named, bare):
        assert "el dato que falta" not in asked and not combine.asks_the_offeror(asked)


def test_d283_7_a_lost_citation_asks_to_confirm_the_conclusion_not_for_a_text():
    """REQ-105 (D-18, D-40): cuando la cita de una conclusión no se ubicó, la pregunta pide confirmar
    lo que concluyó la lectura; no le pide a la Comisión un texto de la oferta (que para una
    prohibición no puede existir)."""
    combined = combine.Combined(outcome="no_determinado", doubt="sin_cita", explanation="X.")

    asked = combine.compose_question(5, "No se aceptarán ofertas condicionadas.", combined)

    assert "¿La Comisión confirma lo que concluyó la lectura de la oferta" in asked
    assert "Qué texto de la oferta" not in asked


VAT = "Las cotizaciones se expresarán en pesos argentinos e incluirán el IVA."


def _total_pair(datum):
    from tests.assessment.test_portal_facts import located as plain_located

    return SimpleNamespace(
        combined=combine.Combined(outcome="cumple", citations=[plain_located(datum)]),
        text=SimpleNamespace(text=VAT), datos=[plain_located(datum)],
        requirement=SimpleNamespace(items=[], category="economico"), groups=[])


def test_d283_7_an_amount_labelled_as_a_tax_is_not_compared_with_the_portal_total(offer, portal):
    """REQ-103, REQ-120 (D-42: se comparan el valor de la oferta y el dato del Portal de un mismo
    dato): un monto rotulado como impuesto o prima no es el total de la oferta; no hay falta de
    coincidencia ni la pregunta de «cuál rige». Un monto rotulado como total sí se compara."""
    portal_data(portal, offer)

    taxed = portal_facts.rule(_total_pair("Prima: $ 3.000,00; IVA: $ 4.132,58"),
                              SimpleNamespace(offer=offer))
    total = portal_facts.rule(_total_pair("Total de la oferta: $ 400.000,00"),
                              SimpleNamespace(offer=offer))

    assert taxed.doubt != "falta_coincidencia" and taxed.facts["regla"] != "portal_falta_coincidencia"
    assert total.doubt == "falta_coincidencia"
    assert portal_facts.amounts("IVA: $ 4.132,58", without_other_concepts=True) == []
    assert portal_facts.amounts("Total con IVA: $ 4.132,58", without_other_concepts=True)


def test_d283_7_the_instruction_says_what_a_question_names_and_does_not_ask():
    """REQ-105, REQ-119 (D-18, D-39, D-40, D-42): la instrucción vigente dice que la pregunta nombra
    el dato que falta, no pide resolver lo que el texto citado ya muestra ni un texto que la oferta no
    tiene por qué traer, y compara solo valores de un mismo dato."""
    text = prompting.load_prompt("evaluacion")

    assert ("Nombra el dato que falta; no pide resolver una condición que el texto citado ya "
            "muestra, ni un texto que la oferta no tiene por qué traer, y compara solo valores de "
            "un mismo dato.") in text


# --- H-277-1: `--recalcular` dice que no cuenta las tres salidas --------------------------------------


def test_h277_1_the_recompute_says_it_does_not_count_the_three_outputs(
        tmp_path, operator_user, monkeypatch):
    """REQ-120 (H-277-1 de la verificación de T-277): `medir_evaluacion --recalcular` no puede contar
    las tres salidas de una corrida guardada (no trae el dato) y lo dice en su salida, no solo en el
    código."""
    from io import StringIO

    from django.core.management import call_command

    from evaluon.accounts import permissions
    from evaluon.assessment import evaluation as ev
    from tests.assessment.test_medicion_t256 import _recompute_inputs, _saved_run
    from tests.tenders.conftest import TEST_PASSWORD

    folder = _saved_run(tmp_path)
    exclusions, portal, commission = _recompute_inputs(tmp_path)
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    monkeypatch.setattr(ev, "run_evaluation", lambda *a, **k: pytest.fail("usó el modelo"))
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--recalcular",
                 str(folder), "--celdas-portal", str(portal), "--celdas-comision",
                 str(commission), "--exclusiones-celdas", str(exclusions), stdout=out)

    assert ("Tres salidas (REQ-120): no se cuentan al recalcular; las cuenta la corrida de "
            "medir_evaluacion") in out.getvalue()


# --- H-277-2: los huecos de prueba de T-277 -----------------------------------------------------------


def test_h277_2_the_partial_portal_question_names_the_portal_datum_that_is_there(offer, portal):
    """REQ-120 (H-277-2, alteración D2): la pregunta de `portal_cubre_parte` con condiciones nombra
    la condición abierta **y el valor que informa el Portal**, no solo la palabra «Portal»."""
    from evaluon.assessment import rules
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
    assert "El Portal informa 21750.00" in pair.combined.question


def test_h277_2_the_first_threshold_row_fails_with_a_missing_document_without_a_question():
    """REQ-120, umbral 9 (H-277-2, alteración E3): la primera fila de `thresholds_016` («no se
    encontró el documento» sin pregunta) no cumple cuando hay una celda así, y cumple sin ninguna."""
    from evaluon.assessment import evaluation as ev

    base = {"cells": 3, "sin_documento": 2, "sin_documento_sin_pregunta": [], "no_determinado": 1,
            "no_determinado_sin_nombrar": [], "problems": []}
    bad = {**base, "sin_documento_sin_pregunta": [7]}

    assert [ok for _, _, ok in ev.thresholds_016({"three_outputs": base})] == [True, True, True]
    rows = ev.thresholds_016({"three_outputs": bad})
    assert rows[0][2] is False and rows[0][1] == "1 de 2"
