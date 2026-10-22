"""Sección 2, Pliego y matriz (plan 014). Insumo: las etapas del pliego y de la matriz."""

from django.urls import reverse

KEY = "pliego"
LABEL = "Pliego y matriz"
SLUG = "pliego"
STAGE_KEYS = ("pliego", "matriz")
TEMA_KEYS = ("s2_documentos", "s2_matriz")


def legacy_links(procedure):
    return []


def _lower_first(text):
    """El detalle de una etapa como parte de una frase: sin el punto final y en minúscula."""
    text = text.strip().rstrip(".")
    return text[:1].lower() + text[1:]


def summary(user, procedure, stages):
    """Sin pliego, una sola línea que dice qué hacer; si no, el detalle de cada etapa. Si el Portal
    lista más documentos del pliego que los cargados, una sola línea que los cuenta contra lo que
    lista, para no decir «el documento del pliego está leído» como si fuera el único (T-338)."""
    from evaluon.journey.stages import base as stage_base
    from evaluon.journey.temas import s2_documentos, s2_matriz
    if not s2_documentos.documents_of(procedure):
        return (("Pliego y matriz", "Todavía no hay pliego: súbalo o tómelo del Portal "
                 "para que el sistema proponga la matriz."),)
    listed, loaded = s2_documentos.listed_count(procedure)
    if listed == loaded:
        return tuple((s.label, s.detail) for s in stages if s.detail)
    by_key = {s.key: s for s in stages}
    count = f"{loaded} de {listed} documentos del pliego"
    reading = by_key.get("pliego")
    if reading is not None and reading.state == stage_base.LISTA:
        parts = [f"{count} ({'leído' if loaded == 1 else 'leídos'})"]
    else:
        parts = [f"{count} cargados"]
        if reading is not None and reading.detail:
            parts.append(_lower_first(reading.detail))
    matrix = by_key.get("matriz")
    if matrix is not None and matrix.detail:
        version = s2_matriz.latest_version(procedure)
        if matrix.state == stage_base.LISTA and version is not None:
            parts.append(f"matriz versión {version.number} validada")
        else:
            parts.append(_lower_first(matrix.detail))
    return (("Pliego y matriz", " · ".join(parts) + "."),)


def upload_url(procedure, user=None):
    """Dónde se sube un archivo a esta sección hoy (T-192); las tareas de cada sección lo
    reemplazan por su propio componente. En la sección 2 es la subida de varios archivos de la
    propia pestaña (T-198)."""
    return reverse("expedientes:pliego", args=[procedure.pk]) + "#s2-subir"
