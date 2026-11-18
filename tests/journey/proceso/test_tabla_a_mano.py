"""REQ-143, REQ-144 (T-341): la tabla de 21 estados firmada del anexo del plan 018, como test, antes
del cálculo. Arma cada procedimiento con los fixtures de T-340, llama a `proceso_de` y compara los
siete estados de cada uno. Mientras `evaluon.journey.proceso.calculo` no exista, las 21 quedan
saltadas (no en rojo); **T-346 no cierra hasta que corren y pasan 21 de 21**. Datos inventados (P4).
"""

import pytest

from evaluon.journey.temas import s4_dictamen
from evaluon.journey.tablero import ingreso

from .tabla_a_mano import CASOS, TABLA

pytestmark = pytest.mark.django_db

FIXTURE = {"recien_cargado": "caso_recien_cargado", "varios_en_curso": "caso_varios_en_curso",
           "todo_hecho": "caso_todo_hecho"}
CLAVES = ("pliego", "matriz", "ofertas", "cumplimiento", "comparacion", "evaluacion", "dictamen")


def _texto(estado):
    # El texto que se muestra («Hecho»); `value` es la clave para las hojas de estilo (T-343).
    return str(getattr(estado, "texto", getattr(estado, "value", estado)))


def _casos_y_pasos():
    return [(caso, numero) for caso in CASOS for numero, _, _ in TABLA]


# --- La tabla en sí (corre siempre) ---------------------------------------------------------------


def test_tabla_tiene_siete_filas_por_tres_casos():
    """REQ-143: 7 pasos x 3 casos = 21 valores, numerados 1 a 7 y con estados permitidos."""
    assert [n for n, _, _ in TABLA] == list(range(1, 8))
    assert len(_casos_y_pasos()) == 21
    for _, _, celdas in TABLA:
        assert set(celdas) == set(CASOS)
        for estado, _ in celdas.values():
            assert estado in {"Hecho", "En curso", "Todavía no"}   # ninguno «Con error» (anexo iv)


def test_nombres_de_la_tabla_son_los_de_pasos_py():
    """REQ-143: los siete nombres y su orden son los de `pasos.py` (única fuente)."""
    pasos = pytest.importorskip("evaluon.journey.proceso.pasos")
    assert [(p.numero, p.nombre) for p in pasos.PASOS] == [(n, nombre) for n, nombre, _ in TABLA]
    assert tuple(p.clave for p in pasos.PASOS) == CLAVES


# --- Los 21 estados (saltados hasta que exista el cálculo) ----------------------------------------


@pytest.fixture
def proceso_del(request):
    """`Proceso` del caso pedido por `caso` (parámetro indirecto): un solo fixture por prueba,
    porque los tres crean el mismo procedimiento (aviso de T-340)."""
    calculo = pytest.importorskip("evaluon.journey.proceso.calculo")
    caso = request.getfixturevalue(FIXTURE[request.param])
    return calculo.proceso_de(caso.user, caso.procedure)


@pytest.mark.parametrize("proceso_del", CASOS, indirect=True)
def test_siete_estados_del_caso(proceso_del, request):
    """REQ-144: cada caso da los siete estados de la tabla firmada."""
    caso = request.node.callspec.params["proceso_del"]
    obtenido = [(p.numero, p.nombre, _texto(p.estado)) for p in proceso_del.pasos]
    esperado = [(n, nombre, celdas[caso][0]) for n, nombre, celdas in TABLA]
    assert obtenido == esperado


@pytest.mark.parametrize("proceso_del", CASOS, indirect=True)
def test_sin_paso_actual(proceso_del):
    """REQ-144: no existe un «paso actual» en el resultado del cálculo."""
    assert not hasattr(proceso_del, "paso_actual")


# --- Precisiones que fija la tabla y T-340 dejó para acá (datos, con lo que ya existe) -------------


def test_varios_en_curso_un_documento_de_tres_sin_leer(caso_varios_en_curso):
    """REQ-144 (paso 3, «1 documento sin leer»): entre las dos ofertas hay 3 documentos y
    solo el nuevo no tiene lectura."""
    documentos = [d for o in caso_varios_en_curso.offers for d in o.documents.all()]
    sin_leer = [d for d in documentos if not d.readings.exists()]
    assert len(documentos) == 3
    assert sin_leer == [caso_varios_en_curso.sin_leer]


@pytest.mark.parametrize("fixture", ["caso_recien_cargado", "caso_varios_en_curso",
                                     "caso_todo_hecho"])
def test_mantenimiento_no_vence_ni_vencio(fixture, request):
    """REQ-144 (anexo iii): el caso chico no tiene mantenimiento cargado, así que ningún caso
    tiene un plazo calculable que venza hoy o haya vencido (sin lila ni rojo)."""
    caso = request.getfixturevalue(fixture)
    assert ingreso.maintenance(caso.procedure).state != "computed"


def test_todo_hecho_tiene_dictamen(caso_todo_hecho):
    """REQ-144: «todo hecho» tiene dictamen cargado."""
    assert s4_dictamen.uploaded_dictamenes(caso_todo_hecho.procedure)
