"""Tema s4_exportar: Exportaciones de la evaluación (sección «evaluacion»). Módulo mínimo del corte vertical (T-192);
lo completa T-212. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s4_exportar"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_exportar.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-212 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-212 lo complete."""
    return {}
