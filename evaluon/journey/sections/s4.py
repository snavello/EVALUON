"""Sección 4, Evaluación y dictamen (plan 014). Insumo: las etapas de evaluación y de matriz de
evaluación."""

from django.urls import reverse

KEY = "evaluacion"
LABEL = "Evaluación y dictamen"
SLUG = "evaluacion"
STAGE_KEYS = ("evaluacion", "matriz_evaluacion")
# El orden de los bloques de la pestaña es el de la maqueta aprobada: resultado y orden económico y
# descartes, propuesta, preguntas, informe, dictamen y exportar.
TEMA_KEYS = ("s4_descartes", "s4_propuesta", "s4_preguntas", "s4_informe", "s4_dictamen",
             "s4_exportar")


def legacy_links(procedure):
    return [("Matriz de evaluación", reverse("assessment:matrix", args=[procedure.pk]))]


def upload_url(procedure):
    """«Subir archivo» del encabezado lleva a la subida del informe técnico del área, en esta
    misma pestaña (T-209)."""
    return reverse("expedientes:evaluacion", args=[procedure.pk]) + "#s4-informe"
