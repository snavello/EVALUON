"""«Varios en curso» (REQ-144, REQ-146; plan 018, T-346): los pasos 3, 4, 5 y 6 están «En curso» a
la vez, el 7 espera a 4 y 6, y ninguna pantalla dice «va por el paso N». Datos inventados (P4)."""

import re

import pytest

from evaluon.journey.proceso import calculo, pasos

pytestmark = pytest.mark.django_db

EN_CURSO, HECHO, TODAVIA_NO = (pasos.Estado.EN_CURSO, pasos.Estado.HECHO,
                               pasos.Estado.TODAVIA_NO)
PASO_ACTUAL = re.compile(r"paso actual|va por el paso|vas por el paso|estás en el paso", re.I)


@pytest.fixture
def proceso(caso_varios_en_curso):
    caso = caso_varios_en_curso
    return calculo.proceso_de(caso.user, caso.procedure)


def test_req144_pasos_3_4_5_y_6_en_curso_a_la_vez(proceso):
    """REQ-144: con un documento nuevo, sin informe técnico y con puntos a decidir, los pasos 3, 4
    y 6 dicen «En curso» al mismo tiempo (y el 5, que espera el cumplimiento)."""
    estados = {p.numero: p.estado for p in proceso.pasos}
    assert estados == {1: HECHO, 2: HECHO, 3: EN_CURSO, 4: EN_CURSO, 5: EN_CURSO, 6: EN_CURSO,
                       7: TODAVIA_NO}


def test_req144_ninguna_cadena_dice_paso_actual(proceso):
    """REQ-144: ni el resultado ni ningún texto que arma el cálculo habla de un «paso actual»."""
    assert not hasattr(proceso, "paso_actual")
    textos = []
    for p in proceso.pasos:
        textos += [p.nombre, p.dato, p.resumen, p.espera, *p.advertencias, *(t.texto for t in p.tareas)]
    textos += [a.texto for a in proceso.acciones]
    assert [t for t in textos if PASO_ACTUAL.search(t)] == []


def test_req144_el_paso_5_dice_que_el_orden_esta_listo_y_falta_el_cumplimiento(proceso):
    """REQ-144 (spec, paso 5): con los totales cargados y el paso 4 incompleto, queda «En curso»
    y dice que el orden económico está listo y falta completar el cumplimiento; sin acciones
    propias y de qué paso depende."""
    cinco = proceso.pasos[4]
    assert cinco.estado is EN_CURSO
    assert cinco.resumen == "El orden económico está listo; falta completar el cumplimiento."
    assert cinco.espera == "depende del paso 4 (cumplimiento de ofertas)"
    assert cinco.tareas == [] and cinco.dato == "La más baja: Oferta 2"


def test_req144_el_paso_4_dice_que_falta_el_informe_tecnico(proceso):
    """REQ-144 (paso 4): falta el informe técnico del área en las dos ofertas; el sistema ya revisó
    las dos con la matriz vigente (hay cifras)."""
    cuatro = proceso.pasos[3]
    assert "Falta el informe técnico del área en 2 ofertas." in cuatro.resumen
    assert cuatro.dato == "5 cumplen · 1 no · 6 a decidir"
    assert "4-pendiente-informe_falta" in [t.id for t in cuatro.tareas]


def test_req144_el_paso_6_cuenta_los_puntos_decididos(proceso):
    """REQ-144 (paso 6): «D de T puntos decididos» desde las celdas no técnicas: ninguno decidido
    de 12 (6 no determinados, 1 «no cumple», 5 «cumple» propuestos); las 4 preguntas y el
    descarte salen en el resumen."""
    seis = proceso.pasos[5]
    assert seis.dato == "0 de 12 puntos decididos"
    assert "12 puntos sin confirmar" in seis.resumen and "4 preguntas abiertas" in seis.resumen


def test_req144_el_paso_7_espera_a_4_y_6(proceso):
    """REQ-144 (paso 7): sin dictamen y con 4 y 6 sin terminar, «Todavía no: depende de los pasos 4
    y 6»; no hay acción de cargarlo y el procedimiento sigue abierto."""
    siete = proceso.pasos[6]
    assert siete.estado is TODAVIA_NO and siete.espera == "depende de los pasos 4 y 6"
    assert siete.tareas == [] and siete.dato == "Sin dictamen"
    assert proceso.terminado is False and proceso.vencimiento is None


def test_req146_las_tareas_son_las_acciones_de_la_lista(proceso):
    """REQ-146: lo que muestran los pasos 3, 4 y 6 son las mismas acciones de la lista."""
    ids = {id(a) for a in proceso.acciones}
    assert all(id(t) in ids for p in proceso.pasos for t in p.tareas)
    assert [p.numero for p in proceso.pasos if p.tareas] == [1, 3, 4, 6]
