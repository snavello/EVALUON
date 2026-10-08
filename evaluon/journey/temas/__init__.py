"""Los 18 temas de las cinco secciones (plan 014, «Estructura común»).

Cada tema es una pieza chica de una sección, con su `status()`, su `context()`, el nombre de su
parcial (`PARTIAL`) y sus `urlpatterns` (relativos a `expedientes/<procedure_id>/`). Cada tarea
posterior a T-192 toca solo su módulo, su parcial y su test: el registro de rutas ya está hecho
acá y no se vuelve a tocar.
"""

from importlib import import_module

from django.urls import include, path

NAMES = (
    "s1_datos", "s1_portal", "s1_pliego",
    "s2_documentos", "s2_matriz",
    "s3_ofertas", "s3_ficha", "s3_anexos", "s3_circulares",
    "s4_propuesta", "s4_preguntas", "s4_informe", "s4_descartes", "s4_dictamen",
    "s4_exportar",
    "s5_normas", "s5_rigen", "s5_consulta",
)

TEMAS = tuple(import_module(f"{__name__}.{name}") for name in NAMES)
_BY_KEY = {tema.KEY: tema for tema in TEMAS}


def by_key(key):
    return _BY_KEY[key]


def for_section(section_key):
    """Los temas de una sección, en orden."""
    return tuple(tema for tema in TEMAS if tema.SECTION == section_key)


def url_patterns():
    """Las rutas de acción de todos los temas, colgadas del procedimiento."""
    return [path("<int:procedure_id>/", include(tema.urlpatterns))
            for tema in TEMAS if tema.urlpatterns]
