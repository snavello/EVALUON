"""Sección 2, Pliego y matriz (plan 014). Insumo: las etapas del pliego y de la matriz."""

from django.urls import reverse

KEY = "pliego"
LABEL = "Pliego y matriz"
SLUG = "pliego"
STAGE_KEYS = ("pliego", "matriz")
TEMA_KEYS = ("s2_documentos", "s2_matriz")


def legacy_links(procedure):
    return [("Cargar documentos del pliego", reverse("tenders:procedure", args=[procedure.pk]))]


def upload_url(procedure):
    """Dónde se sube un archivo a esta sección hoy (T-192); las tareas de cada sección lo
    reemplazan por su propio componente. En la sección 2 es la subida de varios archivos de la
    propia pestaña (T-198)."""
    return reverse("expedientes:pliego", args=[procedure.pk]) + "#s2-subir"
