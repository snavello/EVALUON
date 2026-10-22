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
# El primer panel (plan 017, T-321): el encabezado con la foto y los datos principales. Su contexto
# y sus mosaicos salen de `tablero/ingreso.py`; se importa al usarlo (evita importaciones
# circulares con los temas).
INGRESO_TEMPLATE = "journey/_ingreso.html"


def ingreso_context(section, user, procedure, request=None, overview=None):
    from evaluon.journey.tablero import ingreso
    return ingreso.context(section, user, procedure, request, overview)


def tiles(section, user, procedure, contexts):
    from evaluon.journey.tablero import ingreso
    return ingreso.tiles(section, user, procedure, contexts)


def details(section, user, procedure, contexts):
    from evaluon.journey.tablero import ingreso
    return ingreso.details(section, user, procedure, contexts)


def legacy_links(procedure):
    return [("Datos y documentos del procedimiento",
             reverse("expedientes:pliego", args=[procedure.pk])),
            ("Importar del Portal", reverse("expedientes:nuevo"))]


def upload_url(procedure, user=None):
    """«Subir archivo» de la sección 1: el formulario de la propia pestaña que agrega el pliego
    al procedimiento abierto (T-227, D-2). No da de alta otro procedimiento ni manda a la 2."""
    return reverse("expedientes:procedimiento", args=[procedure.pk]) + "#s1-pliego-subir"
