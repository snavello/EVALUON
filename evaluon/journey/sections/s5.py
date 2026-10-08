"""Sección 5, Normativas (plan 014). No tiene etapa de la 013: su estado sale de sus temas."""

from django.urls import reverse

from evaluon.norms.models import Norm, NormUpload, PendingAmendment, ProposalState

KEY = "normativas"
LABEL = "Normativas"
SLUG = "normativas"
STAGE_KEYS = ()
TEMA_KEYS = ("s5_normas", "s5_rigen", "s5_consulta")


def legacy_links(procedure):
    return [("Consulta de normativa", reverse("queries:screen"))]


def upload_url(procedure):
    """«Subir archivo» de la sección: lleva al formulario de subir una norma (T-214)."""
    return f"{reverse('expedientes:normativas', args=[procedure.pk])}#s5-subir"


def summary(user, procedure, stages):
    """Qué hay cargado y qué falta, en una línea (REQ-097). Las normas son comunes a todos los
    procedimientos. Los pendientes de validar los cuenta el tema `s5_normas`."""
    from evaluon.journey.temas import s5_normas

    loaded = Norm.objects.count()
    unvalidated = s5_normas._pending_readings().count()
    waiting = NormUpload.objects.filter(state=ProposalState.PROPUESTO).count()
    missing = PendingAmendment.objects.filter(loaded_norm__isnull=True).count()
    parts = [f"{loaded} {'norma cargada' if loaded == 1 else 'normas cargadas'}"]
    if unvalidated:
        parts.append(f"{unvalidated} sin validar")
    if waiting:
        parts.append(f"{waiting} subida espera confirmar sus datos" if waiting == 1
                     else f"{waiting} subidas esperan confirmar sus datos")
    if missing:
        parts.append(f"{missing} modificatoria sin cargar" if missing == 1
                     else f"{missing} modificatorias sin cargar")
    return (("Normas", ", ".join(parts) + ". Las normas se cargan subiendo su archivo."),)
