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
    """«Subir archivo» de la sección: el alta de una oferta subiendo sus archivos, dentro de la
    pestaña (T-202). Los documentos de una oferta ya cargada se suben en su fila."""
    return (reverse("expedientes:ofertas", args=[procedure.pk])
            + "?alta=archivos#s3-alta-archivos")
