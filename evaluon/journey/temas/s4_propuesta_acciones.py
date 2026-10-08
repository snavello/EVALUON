"""Acciones de la Comisión sobre la propuesta de evaluación, desde la pestaña «Evaluación y
dictamen» (REQ-089; plan 014, T-207).

Las rutas de `assessment:*` vuelven a la pantalla vieja del par o de la matriz. Estas vistas llaman
a los MISMOS servicios (`matrix.request_all` y `review.decide`: el mismo cambio, el mismo hecho de
auditoría y el mismo rol) y vuelven a la pestaña con el mensaje de lo hecho. Si el servicio
rechaza el pedido, no cambia nada y el mensaje dice por qué. Sin el rol que la acción pide,
«acceso denegado» (403) con el rechazo registrado, como en la pantalla vieja. El sistema no decide
nada: cada botón es una decisión de una persona (P3).

El mensaje viaja firmado en la dirección (`?aviso=`), sin guardar nada en la sesión, y vale
cinco minutos.
"""

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from evaluon.assessment.models import Action, Result
from evaluon.assessment.services import evaluate, review
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.tenders.models import Procedure

SALT = "journey.s4.aviso"
AVISO_MAX_AGE = 300
ANCHOR = "#s4-aviso"
CHANNEL = Channel.SCREEN

DECIDED = {Action.CONFIRMAR: "Se confirmó", Action.CORREGIR: "Se corrigió",
           Action.RECHAZAR: "Se rechazó"}


# --- Mensajes y regreso a la pestaña -------------------------------------------------------------


def pack(text, ok=True):
    return signing.dumps({"ok": ok, "m": text}, salt=SALT, compress=True)


def unpack(value):
    """El mensaje firmado de la dirección, o `None` si falta, está alterado o venció."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=AVISO_MAX_AGE)
    except signing.BadSignature:
        return None
    return {"ok": bool(data.get("ok")), "text": str(data.get("m", ""))}


def tab_url(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def pair_url(procedure, offer_id, requirement_id):
    return reverse("expedientes:s4_par", args=[procedure.pk, offer_id, requirement_id])


def back(procedure, text, ok=True, *, pair=None):
    """Vuelve a la pestaña (o al detalle del par, si la acción salió de ahí) con el mensaje."""
    if pair is not None:
        return redirect(f"{pair_url(procedure, *pair)}?aviso={pack(text, ok)}{ANCHOR}")
    return redirect(f"{tab_url(procedure)}?aviso={pack(text, ok)}{ANCHOR}")


# --- Vistas --------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


@require_POST
def evaluate_all(request, procedure_id):
    """«Evaluar todas las ofertas»: el pedido de `matrix.request_all` (un solo pedido con las
    ofertas que tienen documentos). Avisa cuáles quedaron afuera."""
    procedure = _procedure(procedure_id)
    try:
        requested, left_out = matrix_service.request_all(request.user, procedure,
                                                         channel=CHANNEL)
    except evaluate.EvaluationRefused as error:
        return back(procedure, str(error), ok=False)
    count = len(requested.request.offers)
    text = (f"Se pidió la evaluación de {_plural(count, 'oferta', 'ofertas')}. "
            "El avance se ve acá; le avisamos cuando termine.")
    if left_out:
        names = ", ".join(f"la oferta {o.number} ({o.bidder})" for o in left_out)
        text += f" No se evalúa: {names}, porque no tiene documentos."
    return back(procedure, text)


@require_POST
def decide(request, procedure_id, result_id):
    """Confirma, corrige o rechaza la propuesta `result_id` con `review.decide`. Corregir y
    rechazar exigen el motivo (el servicio lo rechaza sin él); queda quién y cuándo."""
    procedure = _procedure(procedure_id)
    result = (Result.objects.filter(pk=result_id, offer__procedure=procedure)
              .select_related("offer", "requirement").first())
    if result is None:
        raise Http404("No hay un resultado con ese número en este procedimiento.")
    post = request.POST
    pair = ((result.offer_id, result.requirement_id) if post.get("desde") == "par" else None)
    action = post.get("action", "")
    try:
        review.decide(request.user, result.pk, action,
                      outcome_after=post.get("outcome_after", ""), note=post.get("note", ""),
                      channel=CHANNEL)
    except review.ReviewRefused as error:
        return back(procedure, str(error), ok=False, pair=pair)
    text = (f"{DECIDED[action]} la propuesta de la oferta {result.offer.number} para el "
            f"requisito {result.requirement.number}. Quedó registrado quién y cuándo.")
    return back(procedure, text, pair=pair)


urlpatterns = [
    path("evaluacion/evaluar/", evaluate_all, name="s4_evaluar"),
    path("evaluacion/resultado/<int:result_id>/decidir/", decide, name="s4_decidir"),
]
