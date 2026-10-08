"""Tema s3_ficha: Ficha de cada oferta (sección «ofertas»). Módulo mínimo del corte vertical (T-192);
lo completa T-203. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s3_ficha"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_ficha.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-203 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-203 lo complete."""
    return {}
