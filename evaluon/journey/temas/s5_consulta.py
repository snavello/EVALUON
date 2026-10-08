"""Tema s5_consulta: Consulta de normativa con citas (sección «normativas»). Módulo mínimo del corte vertical (T-192);
lo completa T-216. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s5_consulta"
SECTION = "normativas"
PARTIAL = "journey/temas/s5_consulta.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-216 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-216 lo complete."""
    return {}
