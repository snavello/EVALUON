"""«Vencido» en la portada (REQ-157; plan 018; T-348): al día siguiente, si sigue faltando el
dictamen, el paso 7 y «Cargar el dictamen» van en rojo brillante con el texto «Vencido»; con el
dictamen cargado, nada. Material inventado (P4)."""

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


def test_req157_al_dia_siguiente_el_paso_7_y_el_dictamen_estan_vencidos(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157: venció ayer y sigue sin dictamen: «Vencido» (con los días) en el paso 7 y en la línea."""
    mantenimiento(monkeypatch, HOY - timedelta(days=1))
    html = html_de(client, caso_varios_en_curso)
    siete = html[html.index('data-paso="7"'):].split("</li>")[0]
    assert '<span class="pr-vencido">Vencido</span>' in siete
    linea = re.search(r'<li class="pr-accion vencido" data-accion="7-cierre-dictamen".*?</li>',
                      html, re.S).group(0)
    assert "Cargar el dictamen" in linea and '<span class="pr-vencido">Vencido</span>' in linea
    titulo = html[html.index('id="portada-titulo"'):html.index("Abrir indicadores")]
    assert '<span class="pr-vencido">Vencido</span> hace 1 día' in titulo
    assert 'class="pr-hoy"' not in html


def test_req157_lo_vencido_va_primero(client, caso_varios_en_curso, monkeypatch):
    """REQ-157: la línea vencida es la primera de «Qué se puede hacer ahora»."""
    mantenimiento(monkeypatch, HOY - timedelta(days=4))
    html = html_de(client, caso_varios_en_curso)
    bloque = html[html.index('id="ahora-titulo"'):]
    assert re.findall(r'data-accion="([^"]+)"', bloque)[0] == "7-cierre-dictamen"
    assert "Vencido</span> hace 4 días" in html


def test_req157_con_el_dictamen_cargado_no_queda_nada_vencido(client, caso_todo_hecho, monkeypatch):
    """REQ-157: con el dictamen cargado el mantenimiento vencido no marca nada."""
    mantenimiento(monkeypatch, HOY - timedelta(days=3))
    html = html_de(client, caso_todo_hecho)
    assert 'class="pr-vencido"' not in html and 'class="pr-hoy"' not in html
