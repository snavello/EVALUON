"""Pantalla de la revisión por grupos: encabezados por cláusula y por tramo, página de
confirmación previa y roles (REQ-034, REQ-026, REQ-032; plan 003, "Revisión por grupos";
ADR-0021; T-105).

Pliego y datos sintéticos (P4). Las pantallas se prueban con el cliente de pruebas.
"""

import html

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import review, validation
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import script  # noqa: F401  (fixture)
from tests.tenders.test_review_group import case, make_row  # noqa: F401
from tests.tenders.test_validation import finish_review

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    return html.unescape(response.content.decode())


def squash(text):
    return " ".join(text.split())


def matrix_url(version):
    return reverse("tenders:matrix", args=[version.pk])


def group_url(version):
    return reverse("tenders:group_review", args=[version.pk])


@pytest.fixture
def grouped(case):
    """Una versión con tres filas propuestas en el tramo 3.1 y una en el 4.1; las demás
    de la propuesta, quitadas para que las cuentas sean las de la prueba."""
    case.requirements.update(state="quitado")
    rows = [make_row(case, "sec-i/3.1", start=i * 6) for i in range(3)]
    other = make_row(case, "sec-i/4.1")
    return case, rows, other


def state(requirement):
    return m.Requirement.objects.get(pk=requirement.pk).state


# --- Encabezados ---------------------------------------------------------------------------------


def test_a_validated_version_has_no_group_buttons(client, evaluator_user, case):
    """REQ-034: una versión validada no se revisa: sin encabezados de grupo con botones."""
    finish_review(evaluator_user, case)
    validation.validate(evaluator_user, case.pk)
    log_in(client, evaluator_user)

    page = text_of(client.get(matrix_url(case)))

    assert "las propuestas" not in page and "Confirmar las" not in page


# --- La página de confirmación previa ------------------------------------------------------------


def test_the_group_button_first_shows_the_rows_and_only_accept_applies(
        client, evaluator_user, grouped):
    """REQ-034: el botón del grupo lleva a una página con las N filas y su texto literal;
    no cambia nada hasta "Aceptar", que confirma cada fila con su historial."""
    version, rows, other = grouped
    log_in(client, evaluator_user)

    response = client.get(group_url(version), {"group": "sec-i/3", "action": "confirmar"})

    assert response.status_code == 200
    page = squash(text_of(response))
    assert "Confirmar las 3 propuestas" in page
    for row in rows:
        quote = row.quotes.get()
        assert squash(quote.text) in page
    assert set(map(state, rows)) == {"propuesto"}
    assert "Aceptar" in page and "Cancelar" in page

    applied = client.post(group_url(version), {"group": "sec-i/3", "action": "confirmar"})

    assert applied.status_code == 302
    assert set(map(state, rows)) == {"confirmado"} and state(other) == "propuesto"
    assert all(r.changes.filter(action="confirmar").exists() for r in rows)


def test_removing_a_group_follows_the_same_two_steps(client, operator_user, grouped):
    """REQ-034/026: "Quitar las N propuestas" también pide confirmación y lo puede hacer el
    operador; las filas quedan `quitado`."""
    version, rows, other = grouped
    log_in(client, operator_user)

    page = squash(text_of(client.get(group_url(version),
                                     {"group": "sec-i/3.1", "action": "quitar"})))
    assert "Quitar las 3 propuestas" in page
    assert set(map(state, rows)) == {"propuesto"}

    assert client.post(group_url(version),
                       {"group": "sec-i/3.1", "action": "quitar"}).status_code == 302
    assert set(map(state, rows)) == {"quitado"} and state(other) == "propuesto"


def test_an_operator_cannot_see_or_apply_the_group_confirmation(
        client, operator_user, grouped):
    """REQ-026/P6: confirmar por grupo es del evaluador: el operador recibe 403 en la
    página previa y al aplicar, el rechazo queda registrado y no cambia nada."""
    version, rows, _other = grouped
    log_in(client, operator_user)
    query = {"group": "sec-i/3", "action": "confirmar"}

    assert client.get(group_url(version), query).status_code == 403
    assert client.post(group_url(version), query).status_code == 403
    assert set(map(state, rows)) == {"propuesto"}
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).exists()


def test_a_user_without_commission_role_gets_403_on_the_group_page(
        client, no_commission_user, grouped):
    """REQ-026/P6: sin rol de la Comisión, ni siquiera se ve la página."""
    version, rows, _other = grouped
    log_in(client, no_commission_user)

    assert client.get(group_url(version), {"group": "sec-i/3",
                                           "action": "quitar"}).status_code == 403
    assert client.post(group_url(version), {"group": "sec-i/3",
                                            "action": "quitar"}).status_code == 403
    assert set(map(state, rows)) == {"propuesto"}


def test_an_empty_group_an_unknown_action_or_a_missing_version_are_refused(
        client, evaluator_user, grouped):
    """REQ-034: un grupo sin filas propuestas o una acción desconocida vuelven con el
    motivo (400) y sin cambios; una versión inexistente da 404."""
    version, rows, _other = grouped
    log_in(client, evaluator_user)

    empty = client.get(group_url(version), {"group": "sec-i/9", "action": "confirmar"})
    assert empty.status_code == 400 and "no tiene filas propuestas" in text_of(empty)
    assert client.post(group_url(version), {"group": "sec-i/9",
                                            "action": "confirmar"}).status_code == 400
    assert client.get(group_url(version), {"group": "sec-i/3",
                                           "action": "borrar"}).status_code == 400
    assert client.get(reverse("tenders:group_review", args=[999999]),
                      {"group": "sec-i/3", "action": "quitar"}).status_code == 404
    assert set(map(state, rows)) == {"propuesto"}


def test_corrected_rows_are_marked_in_the_confirmation_page(client, evaluator_user, grouped):
    """REQ-034/026 (aviso de T-104): una fila corregida vuelve a `propuesto` y entra en el
    grupo; la página previa la marca para que se vea antes de confirmar, y las demás no."""
    version, rows, _other = grouped
    review.confirm(evaluator_user, [rows[0].pk])
    review.correct(evaluator_user, rows[0].pk, category="economico")
    assert state(rows[0]) == "propuesto"
    log_in(client, evaluator_user)

    page = squash(text_of(client.get(group_url(version),
                                     {"group": "sec-i/3", "action": "confirmar"})))

    assert page.count("Corregida por una persona") == 1
    chunks = page.split('group-row"')[1:]
    marked = [c for c in chunks if "Corregida por una persona" in c]
    assert len(chunks) == 3 and f"Requisito {rows[0].number} " in marked[0]


def test_the_confirmation_page_has_no_external_addresses(client, evaluator_user, grouped):
    """REQ-034: la página previa no referencia direcciones externas."""
    version, _rows, _other = grouped
    log_in(client, evaluator_user)

    page = text_of(client.get(group_url(version), {"group": "sec-i/3",
                                                   "action": "confirmar"}))

    assert "http://" not in page and "https://" not in page
