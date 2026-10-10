"""Sección 1, Procedimiento (plan 014). Insumo: la etapa del Portal. Sus temas los completan
T-194, T-195 y T-197."""

from django.urls import reverse

KEY = "procedimiento"
LABEL = "Procedimiento"
SLUG = "procedimiento"
STAGE_KEYS = ("portal",)
TEMA_KEYS = ("s1_datos", "s1_portal", "s1_pliego")
# Con algo que falta (datos, cronograma, garantías, renglones con su cantidad) la sección no queda
# «Lista»: su única etapa es el Portal, opcional, y no alcanza para decirlo (T-217, brecha 2).
MISSING_BLOCKS_READY = True


def legacy_links(procedure):
    return [("Datos y documentos del procedimiento",
             reverse("expedientes:pliego", args=[procedure.pk])),
            ("Importar del Portal", reverse("expedientes:nuevo"))]


def upload_url(procedure, user=None):
    """«Subir archivo» de la sección 1: el formulario de la propia pestaña que agrega el pliego
    al procedimiento abierto (T-227, D-2). No da de alta otro procedimiento ni manda a la 2."""
    return reverse("expedientes:procedimiento", args=[procedure.pk]) + "#s1-pliego-subir"
