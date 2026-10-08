"""Tema s3_anexos: Anexos técnicos y hoja de compliance (sección «ofertas»). Módulo mínimo del corte vertical (T-192);
lo completa T-204. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s3_anexos"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_anexos.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-204 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-204 lo complete."""
    return {}
