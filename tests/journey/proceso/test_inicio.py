"""El inicio de la aplicación (REQ-143, REQ-150, REQ-151, REQ-157; plan 018; T-357): `/` y
`expedientes/` muestran la misma lista de procedimientos abiertos, cada uno en un `<details open>`
con su barra de siete pasos, sus acciones y su vencimiento; `?ver=terminados` lista los que tienen
dictamen; no hay cookie del último visto. Material inventado (P4)."""

import dataclasses
import html as htmllib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey.proceso import calculo
from evaluon.journey.tablero import ingreso
from evaluon.offers import evaluation
from evaluon.tenders import models as tm
from evaluon.tenders.models import Procedure
from evaluon.tenders.services import document_history
from evaluon.tenders.services import documents as tender_documents
from tests.journey.proceso.test_portada import entrar

pytestmark = pytest.mark.django_db

HOY = date(2026, 11, 18)
RAIZ = "/"
LISTA = reverse("expedientes:index")
CSS = Path(__file__).resolve().parents[3] / "evaluon" / "static" / "journey" / "inicio.css"


def copias(user, expected, cantidad, prefijo="INI"):
    """`cantidad` copias del caso chico (pliego leído y matriz validada, sin ofertas) con otro
    número. Devuelve los `Procedure` en el orden en que se crearon."""
    bare = dataclasses.replace(expected, offers=[])
    hechas = []
    for i in range(cantidad):
        Procedure.objects.filter(number=expected.matrix["procedimiento"]).update(
            number=f"{prefijo}-previo-{i}")
        procedure, _ = evaluation.build_case(user, bare)
        Procedure.objects.filter(pk=procedure.pk).update(number=f"{prefijo}-{i}")
        hechas.append(Procedure.objects.get(pk=procedure.pk))
    return hechas


def mantenimientos(monkeypatch, por_procedimiento):
    """Fija `today()` y el mantenimiento de cada procedimiento: `{pk: fecha}` (sin entrada: sin fecha)."""
    monkeypatch.setattr(ingreso, "today", lambda: HOY)

    def mantenimiento(procedure):
        due = por_procedimiento.get(procedure.pk)
        if due is None:
            return ingreso.Maintenance("pending")
        return ingreso.Maintenance("computed", due=due, days_left=(due - HOY).days)
    monkeypatch.setattr(ingreso, "maintenance", mantenimiento)


def detalles(html):
    """Cada `<details class="ini-proc" …>` del inicio, con su pk de procedimiento."""
    return re.findall(r'(<details class="ini-proc"[^>]*data-procedimiento="(\d+)".*?</details>)',
                      html, re.S)


def orden_de(html):
    return [int(pk) for _, pk in detalles(html)]


def test_req150_entrar_muestra_la_lista_y_no_el_ultimo_procedimiento(
        client, caso_varios_en_curso):
    """REQ-150: `/` y `expedientes/` dan la misma lista y no fijan ninguna cookie de «último visto»."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    assert client.get(reverse("expedientes:pliego", args=[caso.procedure.pk])).status_code == 200
    entrada, lista = client.get(RAIZ), client.get(LISTA)
    assert entrada.status_code == lista.status_code == 200
    for respuesta in (entrada, lista):
        assert not [c for c in respuesta.cookies if c.startswith("evaluon_ultimo")]
    html_a, html_b = entrada.content.decode(), lista.content.decode()
    assert detalles(html_a) == detalles(html_b) and len(detalles(html_a)) == 1
    assert "Expedientes" not in html_a and 'id="lista-abiertos"' in html_a


def test_req150_cada_procedimiento_trae_su_barra_sus_acciones_y_su_cuenta(
        client, caso_varios_en_curso):
    """REQ-150, REQ-151: nombre y número, ofertas, los siete pasos con su estado escrito, «N
    acciones» y cada acción con el enlace de la portada del procedimiento."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = client.get(RAIZ).content.decode()
    (bloque, _), = detalles(html)
    assert re.match(r'<details class="ini-proc" open ', bloque)
    assert caso.procedure.subject[:30] in bloque and caso.procedure.number in bloque
    assert "2 ofertas" in bloque
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    assert f">{len(proceso.acciones)} acciones<" in bloque
    assert len(re.findall(r'class="pr-foto-paso"', bloque)) == 7
    assert re.findall(r'data-accion="([^"]+)"', bloque) == [a.id for a in proceso.acciones]
    portada = client.get(reverse("expedientes:portada", args=[caso.procedure.pk])).content.decode()
    for accion in proceso.acciones:
        if accion.url:
            enlace = f'href="{htmllib.escape(accion.url)}"'
            assert enlace in bloque and enlace in portada
    assert "En curso:" in bloque


def test_req151_cuatro_abiertos_agrupan_todas_sus_acciones(client, evaluator_user, expected,
                                                           fake_ai, monkeypatch):
    """REQ-151: cuatro procedimientos abiertos; cada acción cae bajo su procedimiento y el total
    es la suma de las del cálculo de cada uno. Colapsado quedan la línea, «N acciones» y el
    vencimiento dentro del `<summary>`."""
    procs = copias(evaluator_user, expected, 4)
    mantenimientos(monkeypatch, {procs[0].pk: HOY, procs[1].pk: HOY - timedelta(days=3)})
    entrar(client, evaluator_user)
    html = client.get(RAIZ).content.decode()
    total = 0
    for bloque, pk in detalles(html):
        procedure = Procedure.objects.get(pk=pk)
        esperado = calculo.proceso_de(evaluator_user, procedure).acciones
        total += len(esperado)
        assert re.findall(r'data-accion="([^"]+)"', bloque) == [a.id for a in esperado]
        resumen = bloque[bloque.index("<summary"):bloque.index("</summary>")]
        assert procedure.number in resumen and "pr-foto" in resumen
        assert re.search(r">(\d+ acciones|1 acción|Sin acciones)<", resumen)
    assert len(detalles(html)) == 4 and total >= 4
    assert f"{total} acciones para hacer" in html


def test_req157_vencidos_primero_luego_hoy_luego_futuros_y_sin_fecha(
        client, evaluator_user, expected, fake_ai, monkeypatch):
    """REQ-157: el vencido hace más días primero, después lo que vence hoy, los futuros por
    fecha y al final los sin fecha; con texto («Vencido hace N días», «Vence hoy», la fecha)."""
    p = copias(evaluator_user, expected, 6)
    mantenimientos(monkeypatch, {
        p[0].pk: HOY + timedelta(days=9), p[1].pk: HOY, p[2].pk: HOY - timedelta(days=2),
        p[4].pk: HOY - timedelta(days=5), p[5].pk: HOY + timedelta(days=1)})
    entrar(client, evaluator_user)
    html = client.get(LISTA).content.decode()
    assert orden_de(html) == [p[4].pk, p[2].pk, p[1].pk, p[5].pk, p[0].pk, p[3].pk]
    por_pk = {int(pk): bloque for bloque, pk in detalles(html)}
    assert '<span class="pr-vencido">Vencido hace 5 días</span>' in por_pk[p[4].pk]
    assert '<span class="pr-vencido">Vencido hace 2 días</span>' in por_pk[p[2].pk]
    assert '<span class="pr-hoy">Vence hoy</span>' in por_pk[p[1].pk]
    assert "19/11/2026 · faltan 1 día" in por_pk[p[5].pk]
    assert "Sin fecha de vencimiento" in por_pk[p[3].pk]


def test_req150_a_igual_vencimiento_se_ordena_por_numero(client, evaluator_user, expected,
                                                         fake_ai, monkeypatch):
    """REQ-150: a igual fecha manda el número del procedimiento."""
    p = copias(evaluator_user, expected, 3)
    mantenimientos(monkeypatch, {x.pk: HOY + timedelta(days=4) for x in p})
    entrar(client, evaluator_user)
    html = client.get(RAIZ).content.decode()
    assert orden_de(html) == [p[0].pk, p[1].pk, p[2].pk]


def test_req150_cargar_el_dictamen_pasa_a_terminados_y_quitarlo_lo_devuelve(
        client, evaluator_user, expected, fake_ai):
    """REQ-150: con el dictamen cargado el procedimiento sale de los abiertos y figura en
    «Terminados» (sin sus pasos); si se retira, vuelve."""
    una, otra = copias(evaluator_user, expected, 2)
    entrar(client, evaluator_user)
    documento = tender_documents.load_document(
        evaluator_user, una, data=b"%PDF-1.4 dictamen sintetico", file_name="dictamen.pdf",
        kind=tm.DocumentKind.DICTAMEN, title="Dictamen (inventado)", issued_on=date(2026, 10, 6)
    ).document
    html = client.get(RAIZ).content.decode()
    assert orden_de(html) == [otra.pk] and "Terminados (1)" in html
    terminados = client.get(LISTA + "?ver=terminados").content.decode()
    terminados = terminados[terminados.index('id="lista-terminados"'):]
    assert una.number in terminados and otra.number not in terminados
    assert "Dictamen del 06/10/2026" in terminados and "pr-foto" not in terminados
    assert f'href="{reverse("expedientes:portada", args=[una.pk])}"' in terminados
    document_history.withdraw(evaluator_user, documento, "error de carga")
    html = client.get(RAIZ).content.decode()
    assert sorted(orden_de(html)) == sorted([una.pk, otra.pk]) and "Terminados" not in html
    assert "Todavía no hay procedimientos terminados" in client.get(
        LISTA + "?ver=terminados").content.decode()


def test_req143_el_lector_ve_el_inicio_sin_botones(client, caso_varios_en_curso, read_user):
    """REQ-143: el usuario de lectura ve la lista y no los formularios de acción."""
    entrar(client, read_user)
    html = client.get(LISTA).content.decode()
    assert len(detalles(html)) == 1 and "<form" not in html.split("</header>")[1]
    assert "data-accion" in html


def test_req156_el_inicio_no_trae_estilos_en_linea_ni_colores_sueltos(client, caso_varios_en_curso):
    """REQ-156: sin `style=` ni colores en hexadecimal; la hoja del inicio usa solo tokens."""
    entrar(client, caso_varios_en_curso.user)
    html = client.get(RAIZ).content.decode()
    assert " style=" not in html and "<style" not in html
    assert "journey/inicio.css" in html
    css = CSS.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", css)
    assert "--hoy" not in css and "--vencido" not in css
    assert not [t for t in re.findall(r"font-size:\s*([\d.]+)rem", css) if float(t) < .75]
