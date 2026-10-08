"""Tema s1_portal: Explorador y cargador del Portal (sección «procedimiento»). Módulo mínimo del corte vertical (T-192);
lo completa T-195. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s1_portal"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_portal.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-195 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-195 lo complete."""
    return {}
