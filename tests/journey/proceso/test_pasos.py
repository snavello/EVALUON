"""Los siete pasos, sus nombres y los tipos del contrato (REQ-143, REQ-157; plan 018; T-343)."""

from dataclasses import fields

from evaluon.journey.proceso import pasos

NOMBRES = [
    "Carga de pliego",
    "Matriz de requisitos de pliego",
    "Recepción de ofertas",
    "Cumplimiento de ofertas (matriz)",
    "Comparación de ofertas",
    "Evaluación Comisión",
    "Dictamen",
]
CLAVES = ["pliego", "matriz", "ofertas", "cumplimiento", "comparacion", "evaluacion", "dictamen"]


def test_req143_siete_nombres_exactos_y_en_orden():
    """REQ-143: siete pasos, con estos nombres y este orden."""
    assert [p.nombre for p in pasos.PASOS] == NOMBRES
    assert [p.numero for p in pasos.PASOS] == [1, 2, 3, 4, 5, 6, 7]
    assert [p.clave for p in pasos.PASOS] == CLAVES


def test_req143_estados_con_su_texto():
    """REQ-143: los cuatro estados se escriben con su texto."""
    assert [e.texto for e in pasos.Estado] == ["Hecho", "En curso", "Todavía no", "Con error"]


def test_req143_campos_del_contrato():
    """REQ-143: los tipos tienen los campos que fijan las Definiciones compartidas."""
    assert [f.name for f in fields(pasos.Accion)] == [
        "paso", "tipo", "kind", "texto", "cuenta", "boton", "url", "post", "marca"]
    assert [f.name for f in fields(pasos.Paso)] == [
        "numero", "nombre", "estado", "dato", "resumen", "espera", "advertencias", "tareas",
        "marca", "destino"]
    assert [f.name for f in fields(pasos.Proceso)] == [
        "procedure", "pasos", "acciones", "terminado", "vencimiento"]


def test_req143_id_estable_de_la_accion():
    """REQ-143: el id es «<paso>-<tipo>-<kind>»."""
    accion = pasos.Accion(paso=7, tipo=pasos.CIERRE, kind=pasos.KIND_DICTAMEN, texto="x")
    assert accion.id == "7-cierre-dictamen"


def test_req143_paso_vacio_y_tareas_independientes():
    """REQ-143: un paso nuevo está «Todavía no» y no comparte listas con otro."""
    uno, otro = (pasos.Paso.vacio(d) for d in pasos.PASOS[:2])
    assert uno.estado is pasos.Estado.TODAVIA_NO and uno.nombre == NOMBRES[0]
    uno.tareas.append(1)
    assert otro.tareas == []
