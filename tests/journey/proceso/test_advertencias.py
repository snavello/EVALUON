"""Las advertencias de un paso «Hecho» (REQ-146; plan 018, R2 y N1; T-348): un faltante menor no
cambia el estado; el paso dice «N advertencias», con su detalle, y la misma línea está en «Qué se
puede hacer ahora». Material inventado (P4)."""

import re

import pytest

from evaluon.portal.models import PortalLine, PortalProcedureData
from tests.journey.proceso.test_portada import html_de

pytestmark = pytest.mark.django_db


@pytest.fixture
def sin_expediente(caso_recien_cargado):
    """Pliego cargado y leído, con cronograma y renglones, al que le falta el número de expediente."""
    caso = caso_recien_cargado
    documento = caso.procedure.documents.first()
    PortalProcedureData.objects.create(
        procedure=caso.procedure, file_number="", document=documento,
        schedule={"Apertura de ofertas": "22/09/2026 11:00"}, guarantees=["Garantía de oferta 5 %"])
    PortalLine.objects.create(procedure=caso.procedure, number=1, description="Renglón sintético",
                              quantity=1, unit="u.", document=documento)
    return caso


def test_req146_pliego_sin_numero_de_expediente_es_hecho_con_una_advertencia(client, sin_expediente):
    """REQ-146: el paso 1 dice «Hecho» y «1 advertencia»; al abrirla, «Falta el número de expediente»."""
    html = html_de(client, sin_expediente)
    uno = html[html.index('data-paso="1"'):html.index('data-paso="2"')]
    assert ">Hecho</span>" in uno
    assert re.search(r'<summary class="pr-advertencia">1 advertencia</summary>', uno)
    detalle = re.search(r'<ul class="pr-advertencia-detalle">(.*?)</ul>', uno, re.S).group(1)
    assert "Falta el número de expediente" in detalle


def test_req146_la_misma_linea_esta_en_que_se_puede_hacer_ahora(client, sin_expediente):
    """REQ-146: la advertencia es también una línea de «Qué se puede hacer ahora», con su botón."""
    html = html_de(client, sin_expediente)
    bloque = html[html.index('id="ahora-titulo"'):html.index('id="pasos-titulo"')]
    assert "Falta el número de expediente" in bloque
    assert 'data-accion="1-faltante-datos"' in bloque


def test_req146_varias_advertencias_se_cuentan_en_plural(client, caso_recien_cargado):
    """REQ-146: el recién cargado tiene dos faltantes sueltos en el paso 1: «2 advertencias»."""
    html = html_de(client, caso_recien_cargado)
    uno = html[html.index('data-paso="1"'):html.index('data-paso="2"')]
    assert re.search(r'<summary class="pr-advertencia">\d advertencias</summary>', uno)


def test_req146_un_paso_sin_faltantes_no_muestra_advertencias(client, caso_todo_hecho):
    """REQ-146: sin faltantes no hay «advertencia» en un paso sin nada que advertir."""
    html = html_de(client, caso_todo_hecho)
    dos = html[html.index('data-paso="2"'):html.index('data-paso="3"')]
    assert "advertencia" not in dos
