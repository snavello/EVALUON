"""Una aclaración no termina como supresión (REQ-031; plan 003, nota del 2026-10-05; T-127).

El respaldo recibe el efecto que decidió la extracción y no lo contradice; un `suprime` solo
es firme si el texto citado de la circular tiene una frase explícita de supresión; si no,
queda como sugerencia de revisión obligatoria y la fila no pasa a `quitado`. Todo el texto es
inventado (P4); sin modelo real.
"""

from datetime import date

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import circulars
from tests.tenders.test_circular_changes import (  # noqa: F401  (script y case son fixtures)
    ExtractionScript,
    case,
    change,
    script,
)
from tests.tenders.test_circulars import (
    VISITA_QUOTE,
    add_circular,
    requirement_with,
    row_of_item,
    run_proposal,
)

pytestmark = pytest.mark.django_db

PHRASES = ["Se suprime", "Queda sin efecto", "Se elimina", "Déjase sin efecto",
           "No será exigible", "Derógase", "Quedan sin efecto", "Se suprimen"]


def anomalies_of(run, kind):
    return [a for a in run.anomalies if a["type"] == kind]


@pytest.mark.parametrize("phrase", PHRASES)
def test_a_suppression_with_an_explicit_phrase_stays_firm(operator_user, case, script, phrase):
    """REQ-031: un `suprime` cuyo texto citado dice que algo queda sin efecto es firme."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 f"1. {phrase} la exigencia de la constancia de visita.")
    script.c_when("constancia de visita", efectos=[(
        "constancia de visita", "suprime", f"{phrase} la exigencia de la constancia")])

    version, run = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    assert requirement.sources.get().effect == "suprime"
    assert requirement.state == "quitado"
    assert not anomalies_of(run, circulars.ANOMALY_SUPPRESSION_WITHOUT_PHRASE)


def test_a_suppression_without_a_phrase_is_a_suggestion_and_the_row_is_not_removed(
        operator_user, case, script):
    """REQ-031, P3: un `suprime` sin frase explícita no es supresión firme ni deja la fila
    `quitado`; queda como revisión obligatoria con el efecto original y el resultado."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 "1. La constancia de visita se entrega por el portal en lugar de la mesa.")
    script.c_when("constancia de visita", efectos=[(
        "constancia de visita", "suprime", "La constancia de visita se entrega por el portal")])

    version, run = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    assert requirement.state == "propuesto"
    assert requirement.sources.get().effect != "suprime"
    (anomaly,) = anomalies_of(run, circulars.ANOMALY_SUPPRESSION_WITHOUT_PHRASE)
    assert anomaly["review_required"] is True
    assert anomaly["returned"] == "suprime" and anomaly["result"] == "aclara"
    assert "portal" in anomaly["text"] and anomaly["step"]


def test_a_phrase_in_an_unrelated_sentence_does_not_enable_the_suppression(
        operator_user, case, script):
    """REQ-031, caso adverso: la circular dice "sin efecto" en otra oración, no en la cita."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 "1. La constancia de visita se entrega por el portal. "
                 "Los plazos del otro trámite quedan sin efecto.")
    script.c_when("constancia de visita", efectos=[(
        "constancia de visita", "suprime", "La constancia de visita se entrega por el portal")])

    version, run = run_proposal(operator_user, case)

    assert requirement_with(version, VISITA_QUOTE).state == "propuesto"
    assert anomalies_of(run, circulars.ANOMALY_SUPPRESSION_WITHOUT_PHRASE)


def test_the_fallback_cannot_contradict_the_effect_the_extraction_decided(
        operator_user, case, script):
    """REQ-031: la extracción dijo `aclara` y no pudo anclarla; el respaldo devuelve `suprime`
    (con frase explícita incluso): queda `aclara`, la fila sigue vigente y se registra la
    anomalía con el efecto original, el devuelto y el resultado. El respaldo ve el efecto."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La constancia de visita queda sin efecto para quien la hizo antes.")
    script.x_when("constancia de visita", [change("aclara", "ninguno", "", "",
                                                    "para quien la hizo antes")])
    script.c_when("constancia de visita", efectos=[(
        "constancia de visita", "suprime", "La constancia de visita queda sin efecto")])

    version, run = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    assert requirement.state == "propuesto"
    assert requirement.sources.get().effect == "aclara"
    (anomaly,) = anomalies_of(run, circulars.ANOMALY_EFFECT_CONTRADICTED)
    assert (anomaly["decided"], anomaly["returned"], anomaly["result"]) == (
        ["aclara"], "suprime", "aclara")
    assert any("aclara" in r["context"] for r in script.requests)


def test_a_fallback_that_agrees_with_the_extraction_is_kept(operator_user, case, script):
    """REQ-031: sin contradicción no hay anomalía ni cambio."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria del equipo pasa a ser de 32 GB de RAM.")
    script.x_when("pasa a ser", [change("reemplaza", "ninguno", "", "", "32 GB de RAM")])
    script.c_when("pasa a ser", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, run = run_proposal(operator_user, case)

    assert row_of_item(version, 1).sources.get().effect == "modifica"
    assert not anomalies_of(run, circulars.ANOMALY_EFFECT_CONTRADICTED)


def test_the_explicit_phrases_are_found_on_folded_text():
    """REQ-031: la detección ignora mayúsculas y tildes, y no encuentra frases ajenas."""
    assert circulars.has_suppression_phrase("DÉJASE SIN EFECTO el punto 3")
    assert circulars.has_suppression_phrase("el requisito no será exigible")
    assert not circulars.has_suppression_phrase("se presenta por el portal")
    assert not circulars.has_suppression_phrase("el efecto de la suprema corte")
