"""Entrada del recorrido (REQ-065, REQ-071): procedimientos con etapa actual, pendientes y
sugerencias; el alta empieza por explorar el Portal y la carga a mano es la alternativa."""

from dataclasses import replace
from datetime import date

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent
from evaluon.journey.views import index as index_view
from evaluon.portal.models import PortalLink
from evaluon.tenders.models import Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.portal.fakeportal import LINK_URL, portal_settings  # noqa: F401

pytestmark = pytest.mark.django_db

INDEX = "journey:index"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def make_procedure(operator_user, number, subject):
    return Procedure.objects.create(number=number, subject=subject,
                                    authorization_date=date(2026, 1, 5),
                                    created_by=operator_user)


def test_lists_every_procedure_with_its_current_stage_newest_first(client, procedure,
                                                                   operator_user):
    """REQ-065: el 100 % de los procedimientos, con etapa actual y estado, el más nuevo primero."""
    second = make_procedure(operator_user, "PRUEBA-2/2026", "Segundo objeto inventado")
    third = make_procedure(operator_user, "PRUEBA-3/2026", "Tercer objeto inventado")
    log_in(client, operator_user)
    response = client.get(reverse(INDEX))
    assert response.status_code == 200
    rows = response.context["rows"]
    assert [r.procedure.pk for r in rows] == [third.pk, second.pk, procedure.pk]
    html = response.content.decode()
    for number in (procedure.number, "PRUEBA-2/2026", "PRUEBA-3/2026"):
        assert number in html
    for row in rows:
        assert reverse("journey:procedure", args=[row.procedure.pk]) in html
        assert row.journey.current is not None
        assert row.journey.current.label in html


def test_shows_pending_count_and_suggestions(client, procedure, operator_user, monkeypatch):
    """REQ-065/REQ-072: la cuenta de pendientes y de sugerencias de cada procedimiento."""
    real = index_view.stages_for

    def fake(user, proc, **kwargs):
        return replace(real(user, proc, **kwargs), pending=7, suggestions=3)

    monkeypatch.setattr(index_view, "stages_for", fake)
    log_in(client, operator_user)
    html = client.get(reverse(INDEX)).content.decode()
    assert "7 pendientes" in html
    assert "3 sugerencias" in html


def test_a_new_procedure_shows_its_current_stage_as_pending(client, operator_user):
    """REQ-065: un procedimiento sin etapas calculadas todavía se muestra como pendiente."""
    make_procedure(operator_user, "PRUEBA-9/2026", "Nuevo")
    log_in(client, operator_user)
    response = client.get(reverse(INDEX))
    assert response.context["rows"][0].journey.current.state_label == "Pendiente"
    assert "(Pendiente)" in response.content.decode()


def test_empty_list_says_so(client, operator_user):
    log_in(client, operator_user)
    assert "Todavía no hay procedimientos" in client.get(reverse(INDEX)).content.decode()


def test_portal_comes_first_and_manual_load_is_the_alternative(client, operator_user):
    """REQ-071: "Explorar el Portal" va antes que "cargar a mano"; el formulario envía a
    `portal:links` con el campo `url`."""
    log_in(client, operator_user)
    html = client.get(reverse(INDEX)).content.decode()
    assert f'action="{reverse("portal:links")}"' in html
    assert 'name="url"' in html
    assert html.index("Explorar el Portal") < html.index("cargar a mano")
    assert reverse("tenders:procedures") in html


def test_a_valid_link_leads_to_the_portal_proposal(client, operator_user, portal_settings):
    """REQ-071: pegar el enlace explora el Portal y lleva a la propuesta."""
    log_in(client, operator_user)
    response = client.post(reverse("portal:links"), {"url": LINK_URL})
    link = PortalLink.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("portal:proposal", args=[link.pk])


def test_an_invalid_link_comes_back_with_the_portal_reason(client, operator_user):
    """REQ-071: un enlace inválido vuelve con el motivo que da el Portal."""
    log_in(client, operator_user)
    response = client.post(reverse("portal:links"), {"url": "http://otro.test/x"})
    assert response.status_code == 200
    assert "No se puede usar ese enlace" in response.content.decode()
    assert not PortalLink.objects.exists()


def test_portal_links_are_listed_and_lead_to_proposal_or_journey(client, operator_user,
                                                                 procedure):
    """REQ-071: lo que trajo el Portal se ve en la entrada; con procedimiento importado el
    enlace lleva al recorrido; si no, a la propuesta."""
    free = PortalLink.objects.create(url="https://portal.ejemplo.test/a?qs=1",
                                     process_number="PORTAL-1", created_by=operator_user)
    PortalLink.objects.create(url="https://portal.ejemplo.test/b?qs=2",
                              process_number="PORTAL-2", procedure=procedure,
                              created_by=operator_user)
    log_in(client, operator_user)
    html = client.get(reverse(INDEX)).content.decode()
    assert "PORTAL-1" in html and "PORTAL-2" in html
    assert reverse("portal:proposal", args=[free.pk]) in html
    assert html.count(reverse("journey:procedure", args=[procedure.pk])) >= 2


def test_without_commission_role_it_is_forbidden_and_recorded(client, no_commission_user):
    """REQ-069: sin rol de la Comisión, 403 y el rechazo queda registrado."""
    log_in(client, no_commission_user)
    before = AuditEvent.objects.count()
    assert client.get(reverse(INDEX)).status_code == 403
    assert AuditEvent.objects.count() > before
