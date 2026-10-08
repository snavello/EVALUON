"""Tema s4_dictamen: Dictamen del Portal o subido (sección «evaluacion»). Módulo mínimo del corte vertical (T-192);
lo completa T-211. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s4_dictamen"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_dictamen.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-211 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-211 lo complete."""
    return {}
