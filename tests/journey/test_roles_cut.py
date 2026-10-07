"""Roles del recorrido (REQ-069) y entrada mínima (REQ-065, REQ-071)."""

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent
from evaluon.journey.stages import stages_for
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def test_the_operator_gets_no_decision_link(procedure, operator_user, evaluator_user):
    """REQ-069: el operador no recibe `decide_url`; el evaluador sí."""
    operator_stage = stages_for(operator_user, procedure).stages[4]
    evaluator_stage = stages_for(evaluator_user, procedure).stages[4]
    assert operator_stage.key == evaluator_stage.key == "evaluacion"
    assert operator_stage.view_url and operator_stage.decide_url is None
    assert evaluator_stage.decide_url == reverse("assessment:matrix", args=[procedure.pk])
    assert all(s.decide_url is None for s in stages_for(operator_user, procedure).stages)


def test_the_page_shows_go_to_decide_only_to_the_evaluator(client, procedure, operator_user,
                                                           evaluator_user):
    """REQ-069: "Ir a decidir" aparece solo para el evaluador."""
    url = reverse("journey:procedure", args=[procedure.pk])
    log_in(client, operator_user)
    assert "Ir a decidir" not in client.get(url).content.decode()
    client.logout()
    log_in(client, evaluator_user)
    assert "Ir a decidir" in client.get(url).content.decode()


def test_there_are_six_stages_in_order(procedure, operator_user):
    """REQ-066: seis etapas en el orden de la spec; las cinco reservadas están pendientes."""
    journey = stages_for(operator_user, procedure)
    assert [s.key for s in journey.stages] == [
        "portal", "pliego", "matriz", "ofertas", "evaluacion", "matriz_evaluacion"]
    assert journey.stages[0].optional
    assert all(s.state == "pendiente" for s in journey.stages if s.key != "evaluacion")


def test_without_commission_role_it_is_forbidden_and_recorded(client, procedure,
                                                              no_commission_user):
    """REQ-069/P3: sin rol de la Comisión, 403 en las tres vistas y el rechazo queda registrado."""
    log_in(client, no_commission_user)
    for name, args in (("journey:index", []), ("journey:procedure", [procedure.pk]),
                       ("journey:stages", [procedure.pk])):
        assert client.get(reverse(name, args=args)).status_code == 403
    assert AuditEvent.objects.filter(outcome="rejected").count() >= 3


def test_an_anonymous_visitor_is_sent_to_the_login(client, procedure):
    """REQ-016: sin sesión, el recorrido redirige al ingreso."""
    response = client.get(reverse("journey:procedure", args=[procedure.pk]))
    assert response.status_code == 302


def test_an_unknown_procedure_is_a_404(client, operator_user):
    """Un número de procedimiento que no existe da 404."""
    log_in(client, operator_user)
    assert client.get(reverse("journey:procedure", args=[99999])).status_code == 404
    assert client.get(reverse("journey:stages", args=[99999])).status_code == 404


def test_the_index_lists_procedures_and_offers_the_portal_first(client, procedure,
                                                                operator_user):
    """REQ-065/REQ-071: la entrada lista los procedimientos con su recorrido y ofrece primero
    explorar el Portal, con la carga a mano como alternativa."""
    log_in(client, operator_user)
    html = client.get(reverse("journey:index")).content.decode()
    assert procedure.number in html
    assert reverse("journey:procedure", args=[procedure.pk]) in html
    assert html.index("Explorar el Portal") < html.index("a mano")
    assert f'action="{reverse("portal:links")}"' in html
    assert reverse("tenders:procedures") in html


def test_the_menu_has_the_journey_before_procedures(client, operator_user):
    """El menú trae "Recorrido" delante de "Procedimientos"."""
    log_in(client, operator_user)
    html = client.get(reverse("journey:index")).content.decode()
    assert html.index(">Recorrido<") < html.index(">Procedimientos<")
