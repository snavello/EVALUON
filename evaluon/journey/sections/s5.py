"""Sección 5, Normativas (plan 014). No tiene etapa de la 013: su estado sale de sus temas."""

from django.urls import reverse

KEY = "normativas"
LABEL = "Normativas"
SLUG = "normativas"
STAGE_KEYS = ()
TEMA_KEYS = ("s5_normas", "s5_rigen", "s5_consulta")


def legacy_links(procedure):
    return [("Consulta de normativa", reverse("queries:screen"))]


def upload_url(procedure):
    """Dónde se sube un archivo a esta sección hoy (T-192); las tareas de cada sección lo
    reemplazan por su propio componente."""
    return None
