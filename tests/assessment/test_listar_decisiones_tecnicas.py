"""El listado de solo lectura de las decisiones guardadas sobre filas técnicas (REQ-162; plan 019;
T-365). Caso chico inventado (P4). Las decisiones se ponen directo, sin pasar por el servicio de
decisión: lo que se prueba es el listado."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.apps import apps
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.assessment import models as am
from evaluon.assessment.services import technical_decisions
from evaluon.accounts import permissions
from evaluon.audit.models import AuditEvent
from evaluon.offers.services import sheets
from tests.assessment.test_matrix import add_run, decide
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def typed_password(monkeypatch):
    """Simula la clave escrita por teclado en el comando."""
    def type_(password):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: password)
    return type_


def run_command(username):
    out = StringIO()
    call_command("listar_decisiones_tecnicas", usuario=username, stdout=out, stderr=StringIO())
    return out.getvalue()


def all_counts():
    """La cuenta de filas de cada tabla de la aplicación."""
    return {model._meta.label: model.objects.count() for model in apps.get_models()}


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
    """REQ-162: el servicio no escribe en ninguna tabla de la aplicación ni deja hecho."""
    before = all_counts()
    technical_decisions.technical_row_decisions()
    assert all_counts() == before


def test_the_command_changes_nothing_but_the_login(decided, evaluator_user, typed_password):
    """REQ-162: el comando no cambia decisiones ni resultados; el único hecho nuevo es el de
    ingreso."""
    typed_password(TEST_PASSWORD)
    before = all_counts()
    run_command(evaluator_user.username)
    after = all_counts()
    audit_label = AuditEvent._meta.label
    assert {k: v for k, v in after.items() if k != audit_label}         == {k: v for k, v in before.items() if k != audit_label}
    assert after[audit_label] == before[audit_label] + 1
    assert AuditEvent.objects.latest("pk").event_type == "login"


def test_the_command_prints_the_total(decided, procedure, offer, evaluator_user,
                                      typed_password):
    """REQ-162: el comando imprime la fila y «Total: 1»."""
    typed_password(TEST_PASSWORD)

    lines = run_command(evaluator_user.username).strip().splitlines()

    assert lines[-1] == "Total: 1"
    assert len(lines) == 2
    for part in (procedure.number, offer.bidder, am.Action.CONFIRMAR,
                 evaluator_user.get_username()):
        assert str(part) in lines[0]


def test_the_command_does_not_list_without_a_commission_role(
        decided, no_commission_user, typed_password):
    """REQ-162: sin rol de la Comisión el comando no imprime nada del listado."""
    typed_password(TEST_PASSWORD)
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("listar_decisiones_tecnicas", usuario=no_commission_user.username,
                     stdout=out, stderr=StringIO())
    assert out.getvalue() == ""


def test_the_command_does_not_list_with_a_wrong_password(
        decided, evaluator_user, typed_password):
    """REQ-162: con la clave mala no imprime nada del listado."""
    typed_password("clave-equivocada")
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("listar_decisiones_tecnicas", usuario=evaluator_user.username,
                     stdout=out, stderr=StringIO())
    assert out.getvalue() == ""


def test_a_technical_row_without_items_is_not_listed(decided, evaluator_user):
    """REQ-162: una fila de clase técnica sin renglones no es una fila por renglón: su decisión
    no se lista."""
    decision, chosen = decided
    assert len(technical_decisions.technical_row_decisions()) == 1
    with connection.cursor() as cursor:  # la matriz validada no se edita; se deshace con la prueba
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("ALTER TABLE tenders_requirement DISABLE TRIGGER USER")
    chosen.items = []
    chosen.save(update_fields=["items"])
    assert not sheets.is_item_row(chosen)
    assert technical_decisions.technical_row_decisions() == []


def test_the_command_prints_zero_when_there_are_none(procedure, evaluator_user,
                                                     typed_password):
    """REQ-162: sin decisiones sobre filas técnicas, solo «Total: 0»."""
    typed_password(TEST_PASSWORD)
    assert run_command(evaluator_user.username).strip() == "Total: 0"


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
