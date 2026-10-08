"""Tema s1_datos: Datos del procedimiento con el origen de cada dato (sección «procedimiento»). Módulo mínimo del corte vertical (T-192);
lo completa T-194. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s1_datos"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_datos.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-194 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-194 lo complete."""
    return {}
