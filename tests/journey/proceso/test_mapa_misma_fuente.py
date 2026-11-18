"""El mapa, la lista y las acciones leen el MISMO `Proceso` (REQ-146, REQ-158; plan 018, «Un solo
cálculo para el mapa, la lista y las acciones»; T-350). Material inventado (P4)."""

import re

import pytest

from evaluon.journey.proceso import calculo
from evaluon.journey.views import portada as vista
from tests.journey.proceso.test_mapa import estado_de_fila, tarjetas
from tests.journey.proceso.test_portada import FIXTURE, entrar, html_de, url_de

pytestmark = pytest.mark.django_db


def test_req158_una_sola_llamada_a_sections_for_y_a_proceso_de(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-158: con el mapa, una llamada a `sections_for` desde la vista, ninguna desde `calculo` y
    una a `proceso_de`; el contexto de la plantilla trae un único `Proceso`."""
    cuenta = {"vista": 0, "calculo": 0, "proceso_de": 0}
    reales = (vista.sections_for, calculo.sections_for, calculo.proceso_de)

    def envolver(clave, real):
        def f(*a, **k):
            cuenta[clave] += 1
            return real(*a, **k)
        return f

    monkeypatch.setattr(vista, "sections_for", envolver("vista", reales[0]))
    monkeypatch.setattr(calculo, "sections_for", envolver("calculo", reales[1]))
    monkeypatch.setattr(calculo, "proceso_de", envolver("proceso_de", reales[2]))
    entrar(client, caso_varios_en_curso.user)
    respuesta = client.get(url_de(caso_varios_en_curso))
    assert cuenta == {"vista": 1, "calculo": 0, "proceso_de": 1}
    procesos = [c["proceso"] for c in respuesta.context if "proceso" in c]
    assert procesos and all(p is procesos[0] for p in procesos)


@pytest.mark.parametrize("nombre", sorted(FIXTURE))
def test_req158_mismas_tareas_y_estados_en_mapa_lista_y_acciones(nombre, client, request):
    """REQ-158: toda tarea de tarjeta está en la lista de su paso; las de «Qué se puede hacer
    ahora» son las del cálculo; el estado de la tarjeta es el de la fila."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    html = html_de(client, caso)
    cartas = tarjetas(html)
    lista = html[html.index('id="pasos"'):]
    for n, carta in cartas.items():
        fila = lista[lista.index(f'data-paso="{n}"'):]
        siguiente = fila.find('data-pieza="paso"', 10)
        fila = fila if siguiente == -1 else fila[:siguiente]
        de_tarjeta = re.findall(r'data-accion="([^"]+)"', carta)
        de_lista = re.findall(r'data-accion="([^"]+)"', fila)
        assert len(de_tarjeta) <= 3 and set(de_tarjeta) <= set(de_lista), n
        clase, texto = estado_de_fila(html, n)
        assert f'class="mp-estado {clase}">{texto}</span>' in carta
    ahora = html[html.index('id="ahora-titulo"'):html.index('id="pasos"')]
    en_ahora = set(re.findall(r'data-accion="([^"]+)"', ahora))
    todas = {a.id for a in calculo.proceso_de(caso.user, caso.procedure).acciones}
    assert en_ahora == todas
    en_mapa = {i for c in cartas.values() for i in re.findall(r'data-accion="([^"]+)"', c)}
    assert en_mapa <= en_ahora
