"""El listado de solo lectura de las decisiones guardadas sobre filas técnicas (REQ-162; plan 019;
T-365). Caso chico inventado (P4). Las decisiones se ponen directo, sin pasar por el servicio de
decisión: lo que se prueba es el listado."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.assessment import models as am
from evaluon.assessment.services import technical_decisions
from evaluon.audit.models import AuditEvent
from evaluon.offers.services import sheets
from tests.assessment.test_matrix import add_run, decide

pytestmark = pytest.mark.django_db


@pytest.fixture
def decided(procedure, offer, evaluator_user):
    """Una decisión sobre la fila técnica del renglón 1 y otra sobre cada fila que no es técnica
    por renglón."""
    version = procedure.matrix_versions.get(number=1)
    rows = list(version.requirements.order_by("number"))
    technical = [r for r in rows if sheets.is_item_row(r)]
    others = [r for r in rows if not sheets.is_item_row(r)]
    assert technical and others
    chosen = technical[0]
    saved = add_run(evaluator_user, procedure, offer,
                    {row: am.Outcome.CUMPLE for row in [chosen, *others]})
    decision = decide(evaluator_user, saved[chosen.pk], am.Action.CONFIRMAR)
    for row in others:
        decide(evaluator_user, saved[row.pk], am.Action.CONFIRMAR)
    return decision, chosen


def test_the_list_shows_the_technical_decision_and_not_the_others(
        decided, procedure, offer, evaluator_user):
    """REQ-162: el listado trae la decisión sobre la fila técnica, con su procedimiento, oferta,
    requisito, acción, usuario y fecha, y ninguna otra."""
    decision, chosen = decided
    assert am.Decision.objects.count() > 1

    listed = technical_decisions.technical_row_decisions()

    assert len(listed) == 1
    row = listed[0]
    assert row.procedure_number == procedure.number
    assert row.offer_number == offer.number
    assert row.bidder == offer.bidder
    assert row.requirement_number == chosen.number
    assert row.items == chosen.items
    assert row.action == am.Action.CONFIRMAR
    assert row.username == evaluator_user.get_username()
    assert row.at == decision.at


def test_the_list_includes_every_action(decided, evaluator_user):
    """REQ-162: no solo confirmar, corregir y rechazar: toda acción sobre la fila técnica."""
    decision, _ = decided
    decide(evaluator_user, decision.result, am.Action.CORREGIR,
           outcome_after=am.Outcome.NO_CUMPLE, note="Corrijo.")
    decide(evaluator_user, decision.result, am.Action.PEDIR_SUBSANACION, note="Falta la hoja.")

    actions = {row.action for row in technical_decisions.technical_row_decisions()}

    assert actions == {am.Action.CONFIRMAR, am.Action.CORREGIR, am.Action.PEDIR_SUBSANACION}


def test_the_list_changes_nothing(decided):
    """REQ-162: el listado y el comando no escriben en la base ni dejan hecho."""
    def counts():
        return (am.Decision.objects.count(), am.Result.objects.count(),
                AuditEvent.objects.count())

    before = counts()
    technical_decisions.technical_row_decisions()
    call_command("listar_decisiones_tecnicas", stdout=StringIO())
    assert counts() == before


def test_the_command_prints_the_total(decided, procedure, offer, evaluator_user):
    """REQ-162: el comando imprime la fila y «Total: 1»."""
    _, chosen = decided
    out = StringIO()

    call_command("listar_decisiones_tecnicas", stdout=out)

    lines = out.getvalue().strip().splitlines()
    assert lines[-1] == "Total: 1"
    assert len(lines) == 2
    for part in (procedure.number, offer.bidder, am.Action.CONFIRMAR,
                 evaluator_user.get_username()):
        assert str(part) in lines[0]


def test_the_command_prints_zero_when_there_are_none(procedure):
    """REQ-162: sin decisiones sobre filas técnicas, solo «Total: 0»."""
    out = StringIO()
    call_command("listar_decisiones_tecnicas", stdout=out)
    assert out.getvalue().strip() == "Total: 0"


def test_the_list_uses_a_fixed_number_of_queries(decided, procedure, offer, evaluator_user):
    """REQ-162: como mucho 2 consultas, con una decisión o con varias en otras ofertas."""
    from tests.offers.conftest import make_offer

    decision, chosen = decided
    with CaptureQueriesContext(connection) as few:
        technical_decisions.technical_row_decisions()
    for name in "XYZ":
        other = make_offer(procedure, evaluator_user, f"Oferente {name}",
                           {"oferta.pdf": [f"Texto de la oferta {name}."]})
        saved = add_run(evaluator_user, procedure, other, {chosen: am.Outcome.CUMPLE})
        decide(evaluator_user, saved[chosen.pk], am.Action.CONFIRMAR)

    with CaptureQueriesContext(connection) as many:
        listed = technical_decisions.technical_row_decisions()

    assert len(listed) == 4
    assert len(few) <= 2
    assert len(many) <= 2
