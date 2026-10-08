"""Tema s2_documentos: Documentos del pliego, anexos y especificaciones (sección «pliego»). Módulo mínimo del corte vertical (T-192);
lo completa T-198. Solo toca este módulo, su parcial y su test (plan 014, «Estructura
común»)."""

from evaluon.journey.sections.base import TemaStatus

KEY = "s2_documentos"
SECTION = "pliego"
PARTIAL = "journey/temas/s2_documentos.html"
urlpatterns = []


def status(user, procedure):
    """Cuentas y faltantes del tema; en cero hasta que T-198 lo complete."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial; vacío hasta que T-198 lo complete."""
    return {}
