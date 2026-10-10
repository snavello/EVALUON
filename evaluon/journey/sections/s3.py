"""Sección 3, Ofertas (plan 014). Insumo: la etapa de ofertas."""

from django.urls import reverse

KEY = "ofertas"
LABEL = "Ofertas"
SLUG = "ofertas"
STAGE_KEYS = ("ofertas",)
TEMA_KEYS = ("s3_ofertas", "s3_ficha", "s3_anexos", "s3_circulares")


def legacy_links(procedure):
    return [("Ofertas y sus documentos",
             reverse("expedientes:ofertas", args=[procedure.pk]))]


def upload_url(procedure):
    """Dónde se sube un archivo a esta sección hoy (T-192); las tareas de cada sección lo
    reemplazan por su propio componente."""
    return reverse("expedientes:ofertas", args=[procedure.pk])
