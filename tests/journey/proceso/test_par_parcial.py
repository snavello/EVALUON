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
    assert "seccion-titulo" not in html
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


# --- Cierre de huecos de la verificación (H1, H2) y contexto reutilizable -------------------------


CSRF = re.compile(r'<input type="hidden" name="csrfmiddlewaretoken"[^>]*>')


def test_a_refused_decision_from_the_cuadro_returns_to_it_with_the_filter(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: corregir sin motivo desde el cuadro vuelve al cuadro con el mismo filtro y un
    aviso de error; no se crea ninguna decisión."""
    from evaluon.journey.temas import s4_propuesta_acciones as acciones

    b = evaluated[1]
    req = requirement(procedure, "declaración jurada")
    result = result_of(b, req)
    log_in(client, evaluator_user)
    response = client.post(decide_url(procedure, result), {
        "action": "corregir", "outcome_after": "cumple", "note": "",
        "desde": "cuadro", "filtro": "no-cumple"})
    base = reverse("expedientes:portada", args=[procedure.pk]) + "cuadro/"
    location = response["Location"]
    assert location.startswith(f"{base}?celda={b.pk}-{req.pk}&filtro=no-cumple&aviso=")
    packed = re.search(r"aviso=([^#&]+)", location).group(1)
    notice = acciones.unpack(packed)
    assert notice is not None and notice["ok"] is False and notice["text"]
    assert not am.Decision.objects.filter(result=result).exists()


def test_the_par_body_keeps_its_blocks_and_three_submit_buttons(
        client, evaluated, procedure, evaluator_user):
    """REQ-154: `_par.html` conserva Estado, «Lo que exige el pliego», «Propuesta del sistema» e
    «Historial del par», y cada uno de los tres formularios de decisión tiene su botón de envío."""
    b = evaluated[1]
    req = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    html = client.get(par_url(procedure, b, req)).content.decode()
    for heading in ("<h3>Estado</h3>", "<h3>Lo que exige el pliego</h3>",
                    "<h3>Propuesta del sistema</h3>", "<h3>Historial del par"):
        assert heading in html
    forms = re.findall(r'<form[^>]*action="[^"]*decidir/"[^>]*>(.*?)</form>', html, re.S)
    assert len(forms) == 3
    actions = []
    for body in forms:
        assert re.search(r'<button[^>]*type="submit"', body)
        actions.append(re.search(r'name="action" value="(\w+)"', body).group(1))
    assert actions == ["confirmar", "corregir", "rechazar"]


def test_par_context_renders_the_same_body_as_the_page(
        client, evaluated, procedure, evaluator_user, rf):
    """REQ-154: el cuerpo que arma `par_context` con `_par.html` es el mismo que muestra la página
    del par; con `desde=cuadro` no repite el título con id ni el enlace de volver, y un filtro
    desconocido se descarta."""
    from evaluon.journey.temas import s4_propuesta

    b = evaluated[1]
    req = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    page_html = CSRF.sub("", client.get(par_url(procedure, b, req)).content.decode())
    request = rf.get(par_url(procedure, b, req))
    request.user = evaluator_user
    context = s4_propuesta.par_context(request, procedure, b.pk, req.pk)
    assert context["desde"] == "par" and context["filtro"] is None
    body = CSRF.sub("", render_to_string("journey/_par.html", context))
    assert body.strip() and body in page_html
    assert 'id="seccion-titulo"' in body
    cuadro = s4_propuesta.par_context(request, procedure, b.pk, req.pk,
                                      desde="cuadro", filtro="no-cumple")
    panel = render_to_string("journey/_par.html", cuadro)
    assert 'id="seccion-titulo"' not in panel and "Volver a Evaluación" not in panel
    assert panel.count('name="filtro" value="no-cumple"') == 3
    hostile = s4_propuesta.par_context(request, procedure, b.pk, req.pk,
                                       desde="x", filtro="<b>")
    assert hostile["desde"] == "par" and hostile["filtro"] is None
