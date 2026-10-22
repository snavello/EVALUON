"""Pendientes con acción a mano y el dictamen del Portal en Evaluación (T-318; REQ-129, REQ-141;
plan 017, «Pendientes con acción a mano» y «Cambios de comportamiento»). Todo inventado (P4)."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.sections.base import Item
from evaluon.journey.stages import portal as stage_portal
from evaluon.portal import models as pm
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s4_dictamen import portal_dictamen

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2]
TEXTO = "Aprobar el dictamen publicado en el Portal"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def portada_url(procedure):
    """La pantalla del pendiente general: la portada ya no dibuja nada, redirige a «Procedimiento»
    (T-312), así que se pide y se vuelve a esa pantalla directamente."""
    return reverse("expedientes:procedimiento", args=[procedure.pk])


def seccion_url(procedure, key="evaluacion"):
    return reverse(f"expedientes:{key}", args=[procedure.pk])


def bloque(html, ident):
    """El `<section class="panel" id="…">` de un bloque de pendientes."""
    return re.search(rf'<section class="panel" id="{ident}".*?</section>', html, re.S).group(0)


def formulario_de_aprobar(panel):
    """`(action, campos)` del formulario del pendiente, tal como lo enviaría el navegador."""
    form = re.search(r'<form[^>]*method="post"[^>]*action="([^"]+)"[^>]*>(.*?)</form>', panel, re.S)
    assert form, "el pendiente no trae un botón que haga POST"
    campos = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form.group(2)))
    return form.group(1), campos


# --- Item ----------------------------------------------------------------------------------------


def test_item_suma_why_open_y_post_opcionales():
    """REQ-129: los tres campos nuevos son opcionales y por omisión no hay (nunca se inventan)."""
    item = Item("algo", "/x/")
    assert item.why == "" and item.open == "" and item.post is None
    con = Item("algo", "/x/", why="porque sí", open="d-algo", post=("/y/", (("aprobar", "item:1"),)))
    assert con.post == ("/y/", (("aprobar", "item:1"),))


# --- La plantilla ---------------------------------------------------------------------------------


def _dibujar(filas, sugerencias=None, show_section=True, total=None):
    pedido = RequestFactory().get("/expedientes/7/")
    pedido.user = AnonymousUser()
    return render_to_string("journey/_pendientes.html", {
        "pending_total": len(filas) if total is None else total,
        "suggestion_total": len(sugerencias or []),
        "pending_rows": filas, "suggestion_rows": sugerencias, "show_section": show_section,
        "next_url": "/expedientes/7/",
    }, request=pedido)


SECCION = SimpleNamespace(label="Evaluación y dictamen", url="/expedientes/7/evaluacion/")


def test_la_fila_dice_que_falta_por_que_importa_la_seccion_y_la_accion():
    """REQ-129: cada fila trae qué falta, por qué importa, su sección y su acción."""
    html = _dibujar([(SECCION, Item("Falta subir el informe", "/x/", action="Subir",
                                     why="Sin el informe no se puede decidir."))])
    assert "Falta subir el informe" in html
    assert "Sin el informe no se puede decidir." in html
    assert "Evaluación y dictamen" in html
    assert 'href="/x/">Subir</a>' in html


def test_sin_texto_de_why_no_se_dibuja_la_linea():
    """REQ-141: lo que el tema no sabe no se inventa."""
    html = _dibujar([(SECCION, Item("Falta algo", "/x/"))])
    assert "por-que" not in html


def test_una_accion_de_un_clic_es_un_formulario_post_con_su_next():
    """REQ-129: `post` se dibuja como botón de formulario POST con CSRF y con `next`."""
    item = Item("Aprobar algo", "/x/", action="Aprobar",
                post=("/expedientes/7/portal/3/decidir/", (("aprobar", "item:5"),)))
    html = _dibujar([(SECCION, item)])
    action, campos = formulario_de_aprobar(html)
    assert action == "/expedientes/7/portal/3/decidir/"
    assert campos["aprobar"] == "item:5" and campos["next"] == "/expedientes/7/"
    assert "csrfmiddlewaretoken" in html
    assert re.search(r"<button[^>]*>[^<]*Aprobar", html)


def test_una_accion_que_abre_un_detalle_es_un_enlace_a_la_seccion_con_el_ancla():
    """REQ-129: `open` lleva al detalle donde está el formulario."""
    html = _dibujar([(SECCION, Item("Falta responder", "/x/", action="Responder",
                                     open="d-s3-circulares"))])
    assert 'href="/expedientes/7/evaluacion/#d-s3-circulares">Responder</a>' in html
    assert "<form" not in html


def test_en_la_seccion_el_detalle_se_abre_en_la_misma_pagina():
    """REQ-129: dentro de la sección el enlace es un ancla local, sin nombrar la sección."""
    html = _dibujar([(SECCION, Item("Falta responder", "/x/", action="Responder",
                                     open="d-s3-circulares"))], show_section=False)
    assert 'href="#d-s3-circulares">Responder</a>' in html
    assert "Evaluación y dictamen" not in html


def test_las_sugerencias_siguen_en_su_bloque_aparte():
    """REQ-098: las sugerencias del sistema siguen aparte, con el mismo estilo."""
    html = _dibujar([(SECCION, Item("Falta algo", "/x/"))],
                    [(SECCION, Item("Sugiere algo", "/y/"))])
    assert html.index('id="pendientes"') < html.index('id="sugerencias"')
    assert "Pendientes de decidir" in html and "Sugerencias del sistema" in html
    assert "no frenan nada" in bloque(html, "sugerencias")
    assert "Sugiere algo" not in bloque(html, "pendientes")
    assert '<span class="cta">1</span>' in bloque(html, "pendientes")


def test_sin_pendientes_lo_dice():
    html = _dibujar([], total=0)
    assert "No hay nada pendiente de decidir." in html


def test_la_hoja_de_estilos_no_usa_opacidad_ni_ink3_ni_estilos_en_linea():
    """ADR-0076 y guía visual: sin opacidad en el texto, sin --ink-3 (no tiene par con
    --tile-h) y la política de contenido no admite `style=`."""
    css = (RAIZ / "evaluon/static/journey/pendientes.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # los comentarios pueden nombrarlos
    assert "opacity" not in css and "--ink-3" not in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "todo color sale de var(--…)"
    plantilla = (RAIZ / "evaluon/templates/journey/_pendientes.html").read_text(encoding="utf-8")
    assert "style=" not in plantilla and "<script" not in plantilla
    assert "journey/pendientes.css" in plantilla


def test_paneles_se_retira_y_seccion_llena_su_hueco():
    """T-318: `_paneles.html` ya no existe y `seccion.html` incluye el pendiente de la sección
    en el hueco, entre Hay/Falta y el tablero."""
    assert not (RAIZ / "evaluon/templates/journey/_paneles.html").exists()
    for plantilla in (RAIZ / "evaluon/templates").rglob("*.html"):
        assert "_paneles.html" not in plantilla.read_text(encoding="utf-8"), plantilla
    texto = (RAIZ / "evaluon/templates/journey/seccion.html").read_text(encoding="utf-8")
    hueco = re.search(r"\{% block pendientes %\}(.*?)\{% endblock %\}", texto, re.S).group(1)
    assert "journey/_pendientes.html" in hueco
    assert texto.index("block hay_falta") < texto.index("block pendientes") < texto.index(
        "journey/_tablero.html")


# --- El dictamen del Portal en Evaluación ----------------------------------------------------------


def test_el_dictamen_se_cuenta_en_evaluacion_y_no_en_el_portal(procedure, operator_user):
    """REQ-129: el ítem de tipo dictamen es un pendiente de la sección 4; la 1 no lo cuenta y el
    total del procedimiento no cambia."""
    item = portal_dictamen(procedure, operator_user)
    secciones = sections_for(operator_user, procedure)
    assert secciones.get("evaluacion").pending == 1
    assert secciones.get("procedimiento").pending == 0
    assert stage_portal.compute(operator_user, procedure).pending == 0
    assert secciones.pending == 1
    textos = [i.text for i in secciones.get("evaluacion").pending_items]
    assert textos == [TEXTO]
    assert not secciones.get("procedimiento").pending_items
    assert item.state == pm.ItemState.PROPUESTO


def test_otros_documentos_del_portal_siguen_en_la_seccion_1(procedure, operator_user):
    """REQ-129: solo el dictamen se mueve; un pliego publicado sin aprobar sigue contando en la 1."""
    item = portal_dictamen(procedure, operator_user)
    pm.PortalItem.objects.create(
        proposal=item.proposal, kind=pm.ItemKind.DOCUMENTO, key="pliego-1",
        payload={"nombre": "Pliego inventado", "clase": "pliego"}, content_sha256="e" * 64,
        page=item.page, file=item.file, state=pm.ItemState.PROPUESTO)
    secciones = sections_for(operator_user, procedure)
    assert secciones.get("procedimiento").pending == 1
    assert secciones.get("evaluacion").pending == 1
    assert secciones.pending == 2


def test_el_dictamen_decidido_ya_no_cuenta_en_ninguna(procedure, operator_user):
    portal_dictamen(procedure, operator_user, state=pm.ItemState.APROBADO)
    secciones = sections_for(operator_user, procedure)
    assert secciones.pending == 0 and not secciones.get("evaluacion").pending_items


@pytest.mark.parametrize("fixture", ["operator_user", "evaluator_user"])
def test_quien_decide_el_dictamen_tiene_el_boton(procedure, operator_user, request, fixture):
    """REQ-129: el pendiente trae `post` al POST de siempre del Portal, con el ítem."""
    usuario = request.getfixturevalue(fixture)
    item = portal_dictamen(procedure, operator_user)
    (pendiente,) = sections_for(usuario, procedure).get("evaluacion").pending_items
    assert pendiente.post is not None
    url, campos = pendiente.post
    assert url == reverse("expedientes:s1_portal_decidir",
                          args=[procedure.pk, item.proposal.link_id])
    assert dict(campos) == {"aprobar": f"item:{item.pk}"}
    assert pendiente.action == "Aprobar"
    assert pendiente.why  # el tema sabe el motivo y lo dice


def test_sin_rol_el_pendiente_cuenta_pero_no_trae_el_boton(procedure, operator_user,
                                                          no_commission_user):
    """REQ-129, P3: el usuario de lectura ve el pendiente (la cuenta es la misma) pero sin
    acción de decisión."""
    portal_dictamen(procedure, operator_user)
    seccion = sections_for(no_commission_user, procedure).get("evaluacion")
    assert seccion.pending == 1
    (pendiente,) = seccion.pending_items
    assert pendiente.post is None


# --- REQ-129 de punta a punta ------------------------------------------------------------------------


def test_aprobar_el_dictamen_desde_el_pendiente_general(client, procedure, operator_user):
    """REQ-129: aprobar «el dictamen publicado en el Portal» desde el pendiente general lo quita
    de las dos listas, baja en uno el contador de Evaluación y deja el hecho de auditoría con
    usuario y momento; el total del procedimiento no cambia por haberlo movido."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, operator_user)

    antes = client.get(portada_url(procedure)).content.decode()
    general = bloque(antes, "pendientes")
    assert TEXTO in general and "Evaluación y dictamen" in general
    assert '<span class="cta">1</span>' in general
    seccion_antes = client.get(seccion_url(procedure)).content.decode()
    assert TEXTO in bloque(seccion_antes, "pendientes")
    assert sections_for(operator_user, procedure).get("evaluacion").pending == 1

    action, campos = formulario_de_aprobar(general)
    assert campos["next"] == portada_url(procedure)
    respuesta = client.post(action, campos)

    assert respuesta.status_code == 302 and respuesta["Location"] == portada_url(procedure)
    despues = client.get(respuesta["Location"]).content.decode()
    assert TEXTO not in bloque(despues, "pendientes")
    assert '<span class="cta">0</span>' in bloque(despues, "pendientes")
    assert TEXTO not in bloque(client.get(seccion_url(procedure)).content.decode(), "pendientes")
    assert sections_for(operator_user, procedure).get("evaluacion").pending == 0

    item.refresh_from_db()
    assert item.state == pm.ItemState.APROBADO
    assert item.decided_by == operator_user and item.decided_at is not None
    hecho = AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION,
                                      outcome=AuditOutcome.OK).latest("pk")
    assert hecho.user_id == operator_user.pk and hecho.occurred_at is not None


def test_el_next_externo_se_ignora_y_vuelve_a_la_pestana_del_portal(client, procedure,
                                                                    operator_user):
    """El `next` se valida: solo dentro de EVALUON. Una dirección de afuera no se sigue."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, operator_user)
    action = reverse("expedientes:s1_portal_decidir", args=[procedure.pk, item.proposal.link_id])
    for malo in ("https://malo.example/robar", "//malo.example/robar", "javascript:alert(1)"):
        pm.PortalItem.objects.filter(pk=item.pk).update(state=pm.ItemState.PROPUESTO,
                                                        decided_by=None, decided_at=None)
        respuesta = client.post(action, {"aprobar": f"item:{item.pk}", "next": malo})
        assert respuesta.status_code == 302
        assert "malo.example" not in respuesta["Location"] and "javascript" not in respuesta["Location"]
        assert respuesta["Location"].startswith(
            reverse("expedientes:procedimiento", args=[procedure.pk]))


def test_sin_next_sigue_como_hoy(client, procedure, operator_user):
    """El POST de la pestaña del Portal no cambia: vuelve a la pestaña con su mensaje."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, operator_user)
    action = reverse("expedientes:s1_portal_decidir", args=[procedure.pk, item.proposal.link_id])
    respuesta = client.post(action, {"aprobar": f"item:{item.pk}"})
    assert respuesta.status_code == 302
    assert respuesta["Location"].startswith(
        reverse("expedientes:procedimiento", args=[procedure.pk]))
    assert "portal=" in respuesta["Location"]


def test_el_usuario_de_lectura_no_ve_el_boton_y_el_servicio_igual_lo_rechaza(
        client, procedure, operator_user, no_commission_user):
    """REQ-129, P3: sin el botón, y un POST armado a mano da 403 sin decidir nada."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, no_commission_user)
    html = client.get(portada_url(procedure)).content.decode()
    general = bloque(html, "pendientes")
    assert TEXTO in general
    assert "<form" not in general and "item:" not in general
    action = reverse("expedientes:s1_portal_decidir", args=[procedure.pk, item.proposal.link_id])
    respuesta = client.post(action, {"aprobar": f"item:{item.pk}",
                                     "next": portada_url(procedure)})
    assert respuesta.status_code == 403
    item.refresh_from_db()
    assert item.state == pm.ItemState.PROPUESTO and item.decided_by is None
