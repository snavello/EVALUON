"""Sección 4, Evaluación y dictamen (plan 014). Insumo: las etapas de evaluación y de matriz de
evaluación."""

from django.urls import reverse

KEY = "evaluacion"
LABEL = "Evaluación y dictamen"
SLUG = "evaluacion"
STAGE_KEYS = ("evaluacion", "matriz_evaluacion")
TEMA_KEYS = ("s4_propuesta", "s4_preguntas", "s4_informe", "s4_descartes", "s4_dictamen",
             "s4_exportar")


def legacy_links(procedure):
    return [("Matriz de evaluación", reverse("assessment:matrix", args=[procedure.pk]))]


def upload_url(procedure):
    """Dónde se sube un archivo a esta sección hoy (T-192); las tareas de cada sección lo
    reemplazan por su propio componente."""
    return reverse("assessment:matrix", args=[procedure.pk])
