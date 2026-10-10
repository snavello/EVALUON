"""Los roles evaluador y operador en los cinco momentos del caso chico (T-217; REQ-075, REQ-091,
REQ-097, REQ-098). Todo el material es inventado (P4)."""

import re

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment.services import discards
from evaluon.audit.models import AuditEvent
from evaluon.journey import sections
from evaluon.tenders.services import validation
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.moments import MOMENTS, Case

pytestmark = pytest.mark.django_db

KEYS = ("procedimiento", "pliego", "ofertas", "evaluacion", "normativas")
# Acciones que son decisiones de la Comisión: solo el evaluador (plan 014, «Roles»).
DECISIONS = (
    r"/matriz/confirmar/", r"/matriz/requisito/\d+/(consecuencia|corregir|quitar)/",
    r"/matriz/validar/", r"/matriz/nueva-version/", r"/evaluacion/resultado/\d+/decidir/",
    r"/evaluacion/descarte/decidir/", r"/informe/subir/")


@pytest.fixture
def case(operator_user, evaluator_user, expected, fake_ai):
    return Case(operator_user, evaluator_user, expected)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def forms_of(client, user, procedure, key):
    client.logout()
    log_in(client, user)
    html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
    return html, set(re.findall(r'<form[^>]*action="([^"]+)"', html))


def is_decision(action):
    return any(re.search(pattern, action) for pattern in DECISIONS)


def test_the_operator_gets_no_decision_action_at_any_moment(client, case, operator_user,
                                                            evaluator_user):
    """REQ-091, REQ-097: el operador ve las cinco secciones con las mismas cuentas, pero en
    ninguna se dibuja una acción de decisión; el evaluador sí las tiene cuando hay algo para
    decidir (matriz propuesta: confirmar y validar; evaluación: decidir pares y descartes)."""
    evaluator_decisions = {}
    for moment in MOMENTS:
        case.go_to(moment)
        found = 0
        for key in KEYS:
            _, operator_forms = forms_of(client, operator_user, case.procedure, key)
            _, evaluator_forms = forms_of(client, evaluator_user, case.procedure, key)
            assert not [a for a in operator_forms if is_decision(a)], (moment, key)
            assert operator_forms <= evaluator_forms, (moment, key)
            found += len([a for a in evaluator_forms if is_decision(a)])
        evaluator_decisions[moment] = found
    assert evaluator_decisions["matriz_propuesta"] > 0
    assert evaluator_decisions["evaluacion_terminada"] > 0


def test_both_roles_see_the_same_state_and_counts_at_every_moment(case, operator_user,
                                                                  evaluator_user):
    """REQ-075, REQ-098: lo pendiente y las sugerencias no dependen del rol."""
    for moment in MOMENTS:
        case.go_to(moment)
        seen = {}
        for user in (operator_user, evaluator_user):
            overview = sections.sections_for(user, case.procedure)
            seen[user.username] = [(s.key, s.state, s.pending, s.suggestions)
                                   for s in overview.sections]
        assert seen["operador"] == seen["evaluador"], moment


def test_the_operator_cannot_decide_even_by_calling_the_services(case, operator_user,
                                                                  evaluator_user):
    """REQ-091 y P3: validar la matriz y decidir un descarte, con el operador, se rechaza y el
    rechazo queda registrado; con el evaluador la decisión queda con quién y cuándo."""
    case.go_to("matriz_propuesta")
    before = AuditEvent.objects.filter(outcome="rejected").count()
    with pytest.raises(RoleRejected):
        validation.validate(operator_user, case.version.pk)
    case.go_to("evaluacion_terminada")
    page = discards_page(operator_user, case)
    unit = discards.units(page)[0]
    with pytest.raises(RoleRejected):
        discards.confirm(operator_user, case.procedure.pk, unit.offer.pk, unit.line)
    assert AuditEvent.objects.filter(outcome="rejected").count() == before + 2
    decided = discards.confirm(evaluator_user, case.procedure.pk, unit.offer.pk, unit.line,
                               note="Confirmado en la prueba.")
    assert decided.decision.user_id == evaluator_user.pk and decided.decision.at


def discards_page(user, case):
    from evaluon.assessment.services import matrix
    return matrix.matrix_page(user, case.procedure.pk)


def test_the_access_to_upload_is_visible_to_both_roles_in_every_section(client, case,
                                                                         operator_user,
                                                                         evaluator_user):
    """REQ-097: «Subir archivo» está a la vista de los dos roles en las cinco secciones."""
    case.go_to("evaluacion_terminada")
    for user in (operator_user, evaluator_user):
        for key in KEYS:
            html, _ = forms_of(client, user, case.procedure, key)
            assert "Subir archivo" in html, (user.username, key)


def test_the_operator_is_told_why_there_is_no_button(client, case, operator_user):
    """REQ-091: donde el operador no puede subir el informe técnico, la pantalla le dice que es
    del evaluador y no le deja un botón que no funciona."""
    case.go_to("evaluacion_terminada")
    html, forms = forms_of(client, operator_user, case.procedure, "evaluacion")
    assert "Solo el evaluador de la Comisión sube el informe técnico" in html
    assert not [a for a in forms if "/informe/subir/" in a]


def test_a_user_without_commission_role_cannot_open_any_section_at_any_moment(
        client, case, no_commission_user):
    """REQ-075: sin rol de la Comisión, 403 en las cinco secciones y cada rechazo se registra."""
    for moment in MOMENTS:
        case.go_to(moment)
        log_in(client, no_commission_user)
        before = AuditEvent.objects.filter(outcome="rejected").count()
        for key in KEYS:
            response = client.get(reverse(f"expedientes:{key}", args=[case.procedure.pk]))
            assert response.status_code == 403, (moment, key)
        assert AuditEvent.objects.filter(outcome="rejected").count() == before + 5, moment
        client.logout()
