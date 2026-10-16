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

from evaluon.assessment import combine, options
from evaluon.assessment import models as am
from evaluon.assessment.citations import Located
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_comite_t257 import apply, condition, pair_with
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    offer_cites,
    results_of,
    run_all,
)

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
    seen = located("Acepto la declaración jurada de aptitud.")
    groups = [combine.GroupResult(0, "no_consta", exigence="documento", found=True, seen=[seen]),
              combine.GroupResult(1, "no_consta", exigence="documento")]

    combined = combine.combine(groups, unread=[])

    assert (combined.outcome, combined.doubt) == ("no_determinado", "sin_dato")
    assert combined.citations == [seen]
    assert combined.explanation == combine.SEEN_NOTE and combined.question == combine.SEEN_QUESTION
    asked = combine.compose_question(3, "Presentar la declaración jurada.", combined)
    assert asked.endswith(combine.SEEN_QUESTION) and "Acepto la declaración jurada" in asked
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
