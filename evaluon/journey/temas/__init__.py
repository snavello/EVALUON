"""Los 18 temas de las cinco secciones (plan 014, «Estructura común»).

Cada tema es una pieza chica de una sección, con su `status()`, su `context()`, el nombre de su
parcial (`PARTIAL`) y sus `urlpatterns` (relativos a `expedientes/<procedure_id>/`). Cada tarea
posterior a T-192 toca solo su módulo, su parcial y su test: el registro de rutas ya está hecho
acá y no se vuelve a tocar.
"""

from functools import wraps
from importlib import import_module

from django.urls import URLPattern, include, path

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel

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


def _gated(pattern):
    """Toda acción (POST) exige primero un rol de la Comisión: el usuario de lectura ve las
    pestañas pero ninguna acción le responde, ni siquiera con el formulario vacío (403 y el
    rechazo registrado). Las lecturas (GET) pasan; cada acción además exige su rol propio."""
    view = pattern.callback
    operation = f"{view.__module__}.{view.__name__}"

    @wraps(view)
    def gate(request, *args, **kwargs):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            require_commission_role(request.user, CommissionRole.OPERATOR,
                                    operation=operation, channel=Channel.SCREEN)
        return view(request, *args, **kwargs)

    return URLPattern(pattern.pattern, gate, pattern.default_args, pattern.name)


def url_patterns():
    """Las rutas de acción de todos los temas, colgadas del procedimiento."""
    return [path("<int:procedure_id>/", include([_gated(p) for p in tema.urlpatterns]))
            for tema in TEMAS if tema.urlpatterns]
