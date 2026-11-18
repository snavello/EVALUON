"""REQ-154 (T-351): el cuerpo del par se reutiliza (`_par.html`) y la decisión acepta
`desde=cuadro` sin cambiar el registro (P3, P6). Material inventado (P4)."""

import re

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.audit.models import AuditEvent
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import evaluated, requirement, three  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def result_of(offer, req):
    return am.Result.objects.filter(offer=offer, requirement=req).get()


def decide_url(procedure, result):
    return reverse("expedientes:s4_decidir", args=[procedure.pk, result.pk])


def par_url(procedure, offer, req):
    return reverse("expedientes:s4_par", args=[procedure.pk, offer.pk, req.pk])


def test_the_pair_page_still_shows_its_body_and_forms(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: la página del par sigue con su volver, sus tres formularios con desde=par y su
    historial; el cuerpo sale de `_par.html`."""
    b = evaluated[1]
    req = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    html = client.get(par_url(procedure, b, req)).content.decode()
    assert "← Volver a Evaluación" in html and "Historial del par" in html
    assert html.count('name="desde" value="par"') == 3 and 'name="filtro"' not in html
    for text in ("Confirmar", "Corregir", "Rechazar", "Propuesta del sistema"):
        assert text in html
    assert html.count('class="seccion seccion-evaluacion s4-prop"') == 1


def test_the_body_with_desde_cuadro_has_no_back_link_and_carries_the_filter(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: con desde=cuadro el cuerpo no ofrece volver a la pestaña y los formularios
    llevan desde=cuadro y el filtro vigente."""
    b = evaluated[1]
    req = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    context = client.get(par_url(procedure, b, req)).context
    keys = ("page", "review", "points", "conditions", "technical", "can_decide", "stages",
            "aviso", "external_line", "read_note", "pid", "tab_url", "decided")
    flat = {key: context[key] for key in keys}
    flat.update({"desde": "cuadro", "filtro": "a-decidir"})
    html = render_to_string("journey/_par.html", flat)
    assert "Volver a Evaluación" not in html
    assert html.count('name="desde" value="cuadro"') == 3
    assert html.count('name="filtro" value="a-decidir"') == 3


def _fact(result):
    event = am.Decision.objects.get(result=result).event
    detail = {k: v for k, v in event.detail.items() if k not in ("result", "offer")}
    return event.event_type, event.outcome, event.channel, detail


def test_a_decision_from_the_cuadro_leaves_the_same_fact_and_returns_to_it(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: confirmar con desde=cuadro deja la misma decisión y el mismo hecho que con
    desde=par, y vuelve al cuadro con la celda, el filtro y el aviso."""
    a, b, _ = evaluated
    req = requirement(procedure, "constancia de inscripción")
    log_in(client, evaluator_user)
    par = client.post(decide_url(procedure, result_of(a, req)),
                      {"action": "confirmar", "desde": "par"})
    cuadro = client.post(decide_url(procedure, result_of(b, req)),
                         {"action": "confirmar", "desde": "cuadro", "filtro": "a-decidir"})
    base = reverse("expedientes:portada", args=[procedure.pk]) + "cuadro/"
    assert par["Location"].startswith(reverse("expedientes:s4_par",
                                              args=[procedure.pk, a.pk, req.pk]))
    assert cuadro["Location"].startswith(f"{base}?celda={b.pk}-{req.pk}&filtro=a-decidir&aviso=")
    assert cuadro["Location"].endswith("#s4-aviso")
    first, second = (am.Decision.objects.get(result=result_of(o, req)) for o in (a, b))
    for field in ("action", "outcome_after", "note", "user_id"):
        assert getattr(first, field) == getattr(second, field)
    assert _fact(result_of(a, req)) == _fact(result_of(b, req))


def test_without_evaluator_role_the_cuadro_decision_is_refused_and_recorded(
        client, evaluated, procedure, operator_user):
    """REQ-154: sin rol de evaluador se rechaza igual, no cambia nada y queda el hecho."""
    b = evaluated[1]
    req = requirement(procedure, "constancia de inscripción")
    result = result_of(b, req)
    log_in(client, operator_user)
    before = AuditEvent.objects.count()
    response = client.post(decide_url(procedure, result),
                           {"action": "confirmar", "desde": "cuadro"})
    assert response.status_code in (302, 403)
    assert not am.Decision.objects.filter(result=result).exists()
    assert AuditEvent.objects.count() > before


@pytest.mark.parametrize("desde", ["https://malo.example/", "//malo.example", "cuadro/../x",
                                   "", "PAR"])
def test_desde_cannot_redirect_outside_the_site(
        client, evaluated, procedure, evaluator_user, desde):
    """REQ-154: solo `par` y `cuadro` cambian el destino; cualquier otro valor vuelve a la
    pestaña, siempre dentro del sitio."""
    b = evaluated[1]
    req = requirement(procedure, "constancia de inscripción")
    log_in(client, evaluator_user)
    response = client.post(decide_url(procedure, result_of(b, req)),
                           {"action": "confirmar", "desde": desde})
    assert response["Location"].startswith(
        reverse("expedientes:evaluacion", args=[procedure.pk]))


def test_an_unknown_filter_is_dropped_from_the_return_url(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: el filtro de regreso solo vale si es uno conocido."""
    b = evaluated[1]
    req = requirement(procedure, "constancia de inscripción")
    log_in(client, evaluator_user)
    response = client.post(decide_url(procedure, result_of(b, req)), {
        "action": "confirmar", "desde": "cuadro", "filtro": "http://malo.example/&x=1"})
    location = response["Location"]
    assert location.startswith("/") and "malo.example" not in location
    assert not re.search(r"filtro=", location)
