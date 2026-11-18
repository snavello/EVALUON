"""La tabla de estados escrita a mano (feature 018, T-341): 7 pasos x 3 procedimientos de prueba.

Copia literal del anexo «Tabla de estados escrita a mano» del plan 018, firmada por el responsable
el 2026-11-17, con los nombres nuevos de los pasos. **No se edita sin la firma del responsable**
(ni un valor, ni un nombre). Cada celda es `(estado, detalle)`: el estado es lo que compara
`test_tabla_a_mano.py`; el detalle es la nota de la firma (lo que el paso debería decir) y se
conserva como documentación.
"""

CASOS = ("recien_cargado", "varios_en_curso", "todo_hecho")

HECHO = "Hecho"
EN_CURSO = "En curso"
TODAVIA_NO = "Todavía no"

# (numero, nombre, {caso: (estado, detalle)})
TABLA = (
    (1, "Carga de pliego", {
        "recien_cargado": (HECHO, ""),
        "varios_en_curso": (HECHO, ""),
        "todo_hecho": (HECHO, "")}),
    (2, "Matriz de requisitos de pliego", {
        "recien_cargado": (EN_CURSO, "acción «Proponer la matriz»"),
        "varios_en_curso": (HECHO, ""),
        "todo_hecho": (HECHO, "")}),
    (3, "Recepción de ofertas", {
        "recien_cargado": (TODAVIA_NO, ""),
        "varios_en_curso": (EN_CURSO, "1 documento sin leer"),
        "todo_hecho": (HECHO, "")}),
    (4, "Cumplimiento de ofertas (matriz)", {
        "recien_cargado": (TODAVIA_NO, "depende de la matriz"),
        "varios_en_curso": (EN_CURSO, "falta el informe técnico"),
        "todo_hecho": (HECHO, "")}),
    (5, "Comparación de ofertas", {
        "recien_cargado": (TODAVIA_NO, "sin ofertas"),
        "varios_en_curso": (EN_CURSO, "orden económico listo; falta completar el cumplimiento"),
        "todo_hecho": (HECHO, "")}),
    (6, "Evaluación Comisión", {
        "recien_cargado": (TODAVIA_NO, "sin evaluación"),
        "varios_en_curso": (EN_CURSO, "puntos por decidir, 1 «no cumple», 4 preguntas"),
        "todo_hecho": (HECHO, "")}),
    (7, "Dictamen", {
        "recien_cargado": (TODAVIA_NO, ""),
        "varios_en_curso": (TODAVIA_NO, "depende de los pasos 4 y 6"),
        "todo_hecho": (HECHO, "")}),
)
