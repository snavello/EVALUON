"""Acciones de la Comisión sobre preguntas y subsanación, desde la pestaña «Evaluación y dictamen»
(REQ-090; plan 014, T-208).

Las rutas de `assessment:*` vuelven a la pantalla vieja. Estas vistas llaman a los MISMOS servicios
(`questions.answer`, `remedy.request_remedy`, `remedy.decline_remedy`, `remedy.add_document` y
`remedy.reevaluate`: el mismo cambio, el mismo hecho de auditoría y el mismo rol) y vuelven a la
pestaña con el aviso de lo hecho, que dibuja `s4_propuesta`. Si el servicio rechaza el pedido no cambia nada y el aviso dice
por qué. Sin el rol de evaluador, «acceso denegado» (403) con el rechazo registrado por el
servicio (P6). El sistema no decide nada: cada botón es de una persona (P3).
"""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.http import require_POST

from evaluon.assessment.models import AnswerScope, Question, Result
from evaluon.assessment.services import evaluate, questions, remedy
from evaluon.audit.models import Channel
from evaluon.journey.temas import s4_propuesta_acciones as base
from evaluon.offers.services import offers as offers_service
from evaluon.tenders.models import Procedure

CHANNEL = Channel.SCREEN
ANCHOR = "#s4-preguntas"


def _back(procedure, text, ok=True):
    return redirect(f"{base.tab_url(procedure)}?aviso={base.pack(text, ok)}{ANCHOR}")


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _result(procedure, result_id):
    found = (Result.objects.filter(pk=result_id, offer__procedure=procedure)
             .select_related("offer", "requirement").first())
    if found is None:
        raise Http404("No hay un resultado con ese número en este procedimiento.")
    return found


@require_POST
def answer(request, procedure_id, question_id):
    """Responde la pregunta con su alcance (`questions.answer`); queda quién y cuándo."""
    procedure = _procedure(procedure_id)
    question = (Question.objects.filter(pk=question_id, procedure=procedure)
                .select_related("offer", "requirement").first())
    if question is None:
        raise Http404("No hay una pregunta con ese número en este procedimiento.")
    try:
        questions.answer(request.user, question.pk, request.POST.get("text", ""),
                         request.POST.get("scope", AnswerScope.REQUISITO), channel=CHANNEL)
    except questions.AnswerRefused as error:
        return _back(procedure, str(error), ok=False)
    return _back(procedure, f"Se registró la respuesta a la pregunta de la oferta "
                            f"{question.offer.number} sobre el requisito "
                            f"{question.requirement.number}. Quedó registrado quién y cuándo.")


@require_POST
def ask_remedy(request, procedure_id, result_id):
    """Pide que se subsane el resultado, con su motivo (`remedy.request_remedy`)."""
    procedure = _procedure(procedure_id)
    result = _result(procedure, result_id)
    try:
        remedy.request_remedy(request.user, result.pk, request.POST.get("note", ""),
                              channel=CHANNEL)
    except remedy.RemedyRefused as error:
        return _back(procedure, str(error), ok=False)
    return _back(procedure, f"Se pidió la subsanación de la oferta {result.offer.number} para "
                            f"el requisito {result.requirement.number}.")


@require_POST
def decline_remedy(request, procedure_id, result_id):
    """Decide no pedir la subsanación del resultado, con su motivo (`remedy.decline_remedy`)."""
    procedure = _procedure(procedure_id)
    result = _result(procedure, result_id)
    try:
        remedy.decline_remedy(request.user, result.pk, request.POST.get("note", ""),
                              channel=CHANNEL)
    except remedy.RemedyRefused as error:
        return _back(procedure, str(error), ok=False)
    return _back(procedure, f"Se decidió no pedir la subsanación de la oferta "
                            f"{result.offer.number} para el requisito "
                            f"{result.requirement.number}. Quedó registrado quién, cuándo y el "
                            "motivo.")


@require_POST
def add_document(request, procedure_id, result_id):
    """Agrega a la oferta el documento de la subsanación (`remedy.add_document`)."""
    procedure = _procedure(procedure_id)
    result = _result(procedure, result_id)
    upload = request.FILES.get("file")
    try:
        remedy.add_document(
            request.user, result.pk, data=upload.read() if upload is not None else b"",
            file_name=upload.name if upload is not None else "",
            note=request.POST.get("note", ""), channel=CHANNEL)
    except (remedy.RemedyRefused, offers_service.OfferRefused) as error:
        return _back(procedure, str(error), ok=False)
    return _back(procedure, f"Se agregó el documento a la oferta {result.offer.number}. "
                            "Cuando termine de leerse, se puede evaluar de nuevo el requisito.")


@require_POST
def reevaluate(request, procedure_id, result_id):
    """Pide evaluar de nuevo el requisito con el documento agregado (`remedy.reevaluate`)."""
    procedure = _procedure(procedure_id)
    result = _result(procedure, result_id)
    try:
        remedy.reevaluate(request.user, result.pk, channel=CHANNEL)
    except (remedy.RemedyRefused, evaluate.EvaluationRefused) as error:
        return _back(procedure, str(error), ok=False)
    return _back(procedure, f"Se pidió evaluar de nuevo el requisito {result.requirement.number}"
                            f" de la oferta {result.offer.number}.")


urlpatterns = [
    path("evaluacion/pregunta/<int:question_id>/responder/", answer, name="s4_responder"),
    path("evaluacion/resultado/<int:result_id>/subsanar/pedir/", ask_remedy,
         name="s4_pedir_subsanacion"),
    path("evaluacion/resultado/<int:result_id>/subsanar/no-pedir/", decline_remedy,
         name="s4_no_pedir_subsanacion"),
    path("evaluacion/resultado/<int:result_id>/subsanar/documento/", add_document,
         name="s4_agregar_documento"),
    path("evaluacion/resultado/<int:result_id>/subsanar/evaluar/", reevaluate,
         name="s4_evaluar_subsanacion"),
]
