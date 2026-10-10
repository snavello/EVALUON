"""Sección 4, Evaluación y dictamen (plan 014). Insumo: las etapas de evaluación y de matriz de
evaluación."""

from django.urls import reverse

from evaluon.accounts.models import CommissionRole

KEY = "evaluacion"
LABEL = "Evaluación y dictamen"
SLUG = "evaluacion"
STAGE_KEYS = ("evaluacion", "matriz_evaluacion")
# El orden de los bloques de la pestaña es el de la maqueta aprobada: resultado y orden económico y
# descartes, propuesta, preguntas, informe, dictamen y exportar.
TEMA_KEYS = ("s4_descartes", "s4_propuesta", "s4_preguntas", "s4_informe", "s4_dictamen",
             "s4_exportar")


def legacy_links(procedure):
    return [("Matriz de evaluación", reverse("expedientes:evaluacion", args=[procedure.pk]))]


def upload_url(procedure, user=None):
    """«Subir archivo» del encabezado lleva a un formulario que quien lo toca puede usar, en esta
    misma pestaña: el evaluador, a la subida del informe técnico del área (T-209); el operador,
    que no sube el informe, a la subida del dictamen (T-227)."""
    anchor = ("#s4-informe"
              if getattr(user, "commission_role", "") == CommissionRole.EVALUATOR
              else "#dictamen-subir")
    return reverse("expedientes:evaluacion", args=[procedure.pk]) + anchor
