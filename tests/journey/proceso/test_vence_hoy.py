"""«Vence hoy» en la portada (REQ-157; plan 018; T-348): el mantenimiento que vence hoy y sin
dictamen deja el paso 7 y «Cargar el dictamen» en lila con su texto; sin vencimientos hoy no hay
nada en lila. `today()` se fija. Material inventado (P4)."""

import re
from datetime import date, timedelta

import pytest

from evaluon.journey.tablero import ingreso
from tests.journey.proceso.test_portada import html_de

pytestmark = pytest.mark.django_db

HOY = date(2026, 11, 18)


def mantenimiento(monkeypatch, due):
    monkeypatch.setattr(ingreso, "today", lambda: HOY)
    monkeypatch.setattr(ingreso, "maintenance", lambda p: ingreso.Maintenance(
        "computed", due=due, days_left=(due - HOY).days))


def fila(html, numero):
    desde = html[html.index(f'data-paso="{numero}"'):]
    return desde[:desde.index("</li>")]


def test_req157_mantenimiento_que_vence_hoy_marca_el_paso_7_y_cargar_el_dictamen(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157: vence hoy y falta el dictamen: el paso 7 y «Cargar el dictamen» en lila, con texto."""
    mantenimiento(monkeypatch, HOY)
    html = html_de(client, caso_varios_en_curso)
    assert '<span class="pr-hoy">Vence hoy</span>' in fila(html, 7)
    linea = re.search(r'<li class="pr-accion hoy" data-accion="7-cierre-dictamen".*?</li>',
                      html, re.S).group(0)
    assert "Cargar el dictamen" in linea and '<span class="pr-hoy">Vence hoy</span>' in linea
    assert 'class="pr-vencido"' not in html
    # lo que vence hoy va antes que los pendientes: es la primera línea de «Qué se puede hacer ahora»
    bloque = html[html.index('id="ahora-titulo"'):]
    assert re.findall(r'data-accion="([^"]+)"', bloque)[0] == "7-cierre-dictamen"


def test_req157_el_resumen_del_titulo_dice_vence_hoy(client, caso_varios_en_curso, monkeypatch):
    """REQ-157: el título nombra el próximo vencimiento con «Vence hoy» y el paso."""
    mantenimiento(monkeypatch, HOY)
    html = html_de(client, caso_varios_en_curso)
    titulo = html[html.index('id="portada-titulo"'):html.index("Abrir indicadores")]
    assert "Próximo vencimiento" in titulo and "Vence hoy" in titulo and "paso 7" in titulo


def test_req157_con_el_mantenimiento_manana_no_hay_nada_en_lila(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157: con el mantenimiento mañana ninguna etiqueta es lila."""
    mantenimiento(monkeypatch, HOY + timedelta(days=1))
    html = html_de(client, caso_varios_en_curso)
    assert 'class="pr-hoy"' not in html and "Vence hoy" not in html


def test_req157_sin_fecha_calculable_no_hay_nada_en_lila(client, caso_varios_en_curso, monkeypatch):
    """REQ-157: el caso chico no calcula el mantenimiento: ni lila ni rojo."""
    monkeypatch.setattr(ingreso, "today", lambda: HOY)
    html = html_de(client, caso_varios_en_curso)
    assert 'class="pr-hoy"' not in html and 'class="pr-vencido"' not in html
