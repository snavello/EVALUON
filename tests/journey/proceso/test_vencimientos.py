"""La marca «Vence hoy» / «Vencido» (REQ-157; plan 018; T-343).

Sin base: los plazos se arman con los mismos tipos de `tablero/ingreso.py`, y `today()` se fija.
"""

from datetime import date, timedelta

import pytest

from evaluon.journey.proceso import pasos, vencimientos
from evaluon.journey.tablero import ingreso

HOY = date(2026, 10, 21)


@pytest.fixture(autouse=True)
def hoy(monkeypatch):
    monkeypatch.setattr(ingreso, "today", lambda: HOY)


def plazos(apertura=None, vence=None, dictamen=None, estado="computed"):
    """Los plazos como los arma `ingreso._plazos`: cada hito con su día o sin él."""
    def evento(clave, dia):
        return ingreso.Terms(clave, clave, clave, dia, "x", "pending" if dia is None else "future")
    due = vence if estado == "computed" else None
    estado = "missing" if estado == "computed" and due is None else estado
    return ingreso.Plazos(
        events=[evento("apertura", apertura), evento("vence", due), evento("dictamen", dictamen)],
        maintenance=ingreso.Maintenance(state=estado, due=due), chart=None)


PASO_3 = pasos.Paso.vacio(pasos.PASOS[2])
PASO_7 = pasos.Paso.vacio(pasos.PASOS[6])
PASO_4 = pasos.Paso.vacio(pasos.PASOS[3])
DICTAMEN = pasos.Accion(7, pasos.CIERRE, pasos.KIND_DICTAMEN, "Cargar el dictamen")
APROBAR = pasos.Accion(7, pasos.PENDIENTE, pasos.KIND_DICTAMEN, "Aprobar el dictamen")
ACTA = pasos.Accion(3, pasos.CIERRE, pasos.KIND_ACTA, "Agregar las ofertas del acta")


def test_req157_mantenimiento_hoy_marca_paso_7_y_su_accion():
    """REQ-157: el mantenimiento que vence hoy y sin dictamen marca el paso 7 y el dictamen."""
    p = plazos(vence=HOY)
    for objeto in (PASO_7, DICTAMEN, APROBAR):
        assert vencimientos.marca_de(objeto, p, HOY) == "hoy"
    assert vencimientos.marca_de(PASO_4, p, HOY) == ""
    assert vencimientos.marca_de(PASO_3, p, HOY) == ""


def test_req157_mantenimiento_ayer_es_vencido():
    """REQ-157: al día siguiente, si sigue faltando el dictamen, es «vencido»."""
    p = plazos(vence=HOY - timedelta(days=1))
    for objeto in (PASO_7, DICTAMEN):
        assert vencimientos.marca_de(objeto, p, HOY) == "vencido"


def test_req157_mantenimiento_futuro_no_marca():
    """REQ-157: un mantenimiento futuro no marca nada."""
    assert vencimientos.marca_de(PASO_7, plazos(vence=HOY + timedelta(days=3)), HOY) == ""


def test_req157_con_el_dictamen_cargado_no_hay_marca():
    """REQ-157: con el dictamen cargado el procedimiento termina y no hay nada que marcar."""
    for dia in (HOY, HOY - timedelta(days=5)):
        p = plazos(vence=dia, dictamen=HOY - timedelta(days=6))
        assert vencimientos.marca_de(PASO_7, p, HOY) == ""
        assert vencimientos.marca_de(DICTAMEN, p, HOY) == ""
    assert vencimientos.marca_de(PASO_7, plazos(vence=HOY), HOY, dictamen_cargado=True) == ""


def test_req157_apertura_pasada_o_futura_nunca_marca():
    """REQ-157: la apertura ya ocurrida es un hecho, no un plazo incumplido."""
    for dia in (HOY - timedelta(days=30), HOY + timedelta(days=2)):
        p = plazos(apertura=dia)
        assert vencimientos.marca_de(PASO_3, p, HOY) == ""
        assert vencimientos.marca_de(ACTA, p, HOY) == ""


def test_req157_apertura_hoy_marca_paso_3_y_su_accion_en_lila():
    """REQ-157: una apertura que es hoy va en lila, en el paso 3 y en «Agregar las ofertas»."""
    p = plazos(apertura=HOY)
    assert vencimientos.marca_de(PASO_3, p, HOY) == "hoy"
    assert vencimientos.marca_de(ACTA, p, HOY) == "hoy"
    assert vencimientos.marca_de(PASO_7, p, HOY) == ""


def test_req157_mantenimiento_sin_fecha_calculable_nunca_vencido():
    """REQ-157: estado `calendar` o `missing` (sin fecha calculable): nada."""
    for estado in ("calendar", "missing"):
        p = plazos(vence=HOY - timedelta(days=9), estado=estado)
        assert vencimientos.marca_de(PASO_7, p, HOY) == ""
        assert vencimientos.proximo(p, HOY) is None


def test_req157_dictamen_no_tiene_vencimiento():
    """REQ-157: el dictamen no tiene fecha prevista: no vence, aunque su fecha sea hoy."""
    assert vencimientos.marca_de(PASO_7, plazos(dictamen=HOY), HOY) == ""


def test_req157_hoy_por_omision_usa_today():
    """REQ-157: sin `hoy`, se usa `ingreso.today()`."""
    assert vencimientos.marca_de(PASO_7, plazos(vence=HOY)) == "hoy"


def test_req157_proximo_ordena_vencido_hoy_futuro():
    """REQ-157: el más próximo es el vencido; si no, el de hoy; si no, el futuro."""
    vencido = vencimientos.proximo(plazos(vence=HOY - timedelta(days=2)), HOY)
    assert (vencido.marca, vencido.paso, vencido.texto) == ("vencido", 7, "Vencido hace 2 días")
    hoy = vencimientos.proximo(plazos(vence=HOY), HOY)
    assert (hoy.marca, hoy.texto) == ("hoy", "Vence hoy")
    futuro = vencimientos.proximo(plazos(apertura=HOY + timedelta(days=4),
                                         vence=HOY + timedelta(days=9)), HOY)
    assert (futuro.marca, futuro.paso, futuro.dia) == ("", 3, HOY + timedelta(days=4))
    assert vencido.orden < hoy.orden < futuro.orden


def test_req157_proximo_sin_fechas_o_terminado_es_nada():
    """REQ-157: sin fechas, o con el dictamen cargado, no hay vencimiento próximo."""
    assert vencimientos.proximo(plazos(), HOY) is None
    assert vencimientos.proximo(plazos(vence=HOY, dictamen=HOY), HOY) is None
    assert vencimientos.proximo(plazos(apertura=HOY - timedelta(days=1)), HOY) is None
