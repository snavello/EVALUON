"""Tema s4_propuesta: Propuesta de evaluación por oferta y requisito (sección «evaluacion»). Módulo mínimo del corte vertical (T-192);
lo completa T-207. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s4_propuesta"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_propuesta.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-207 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-207 lo complete."""
    return {}
