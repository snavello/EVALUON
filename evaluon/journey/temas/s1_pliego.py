"""Tema s1_pliego: Alta del procedimiento desde el pliego subido (sección «procedimiento»). Módulo mínimo del corte vertical (T-192);
lo completa T-197. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s1_pliego"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_pliego.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-197 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-197 lo complete."""
    return {}
