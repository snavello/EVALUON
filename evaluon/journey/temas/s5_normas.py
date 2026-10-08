"""Tema s5_normas: Subir una norma y validarla (sección «normativas»). Módulo mínimo del corte vertical (T-192);
lo completa T-214. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s5_normas"
SECTION = "normativas"
PARTIAL = "journey/temas/s5_normas.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-214 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-214 lo complete."""
    return {}
