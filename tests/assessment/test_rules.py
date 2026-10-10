"""El punto de enganche de las reglas (REQ-063, REQ-064; plan 004, "Qué se decide sin el modelo y
en qué orden"; ADR-0043; T-166). Sin base ni modelo."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, externals, portal_facts, rules, technical, unreadable

pytestmark = pytest.mark.django_db


def pair_with(text, combined, *groups):
    return SimpleNamespace(
        combined=combined, text=SimpleNamespace(text=text), requirement=0,
        groups=list(groups))


CTX = SimpleNamespace(offer=0)
FOUND = {"documento": "pagare.pdf", "documento_id": 1, "archivo": "pagare.pdf", "pagina": 2,
         "paginas": [2]}


def test_the_rules_come_in_the_planned_order():
    """El externo va primero, después el técnico (T-167), la ilegible y la del Portal (T-169)."""
    assert rules.RULES == (externals.rule, technical.rule, unreadable.rule, portal_facts.rule)


def test_a_pair_no_rule_covers_follows_the_normal_flow():
    """Lo que no entra en ninguna regla queda como estaba, sin `facts`."""
    combined = combine.Combined(outcome="cumple")
    pair = pair_with("El plazo de entrega será de diez días.", combined)
    assert rules.apply(pair, CTX) is None
    assert pair.combined is combined and pair.combined.facts == {}


@pytest.mark.decision_literal
def test_external_wins_over_an_unreadable_page():
    """REQ-063, REQ-064: si el requisito es externo y además hay una página ilegible, gana
    «falta la hoja de compliance»: el orden del plan."""
    group = combine.GroupResult(0, "no_determinado", unreadable=FOUND)
    pair = pair_with("Se verificará la inexistencia de deuda exigible.",
                     combine.Combined(outcome="no_determinado", doubt="lectura_incompleta"),
                     group)
    assert rules.apply(pair, CTX) == "externo_catalogo"
    assert pair.combined.doubt == "externo"


@pytest.mark.decision_literal
def test_an_unreadable_page_applies_to_an_undetermined_pair_and_stamps_the_version():
    """REQ-064: la regla de ilegible deja `regla`, `version_reglas` y `ilegible` en `facts`."""
    group = combine.GroupResult(0, "no_determinado", unreadable=FOUND)
    pair = pair_with("Acompañar el pagaré.",
                     combine.Combined(outcome="no_determinado", doubt="lectura_incompleta"),
                     group)
    assert rules.apply(pair, CTX) == "ilegible_informe"
    facts = pair.combined.facts
    assert facts["regla"] == "ilegible_informe" and facts["version_reglas"] == "reglas-v8"
    assert (facts["ilegible"]["documento"], facts["ilegible"]["pagina"]) == ("pagare.pdf", 2)
    assert "página 2" in pair.combined.question and "«pagare.pdf»" in pair.combined.question


def test_an_unreadable_page_does_not_override_a_contradiction_between_documents():
    """REQ-064: una contradicción entre documentos se queda como está."""
    group = combine.GroupResult(0, "no_determinado", unreadable=FOUND)
    pair = pair_with("Acompañar el pagaré.",
                     combine.Combined(outcome="no_determinado", doubt="contradiccion"), group)
    assert rules.apply(pair, CTX) is None
