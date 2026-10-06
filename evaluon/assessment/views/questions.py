"""Lista de preguntas a la Comisión, respuesta y "evaluar de nuevo" (REQ-055, REQ-056; plan 004,
"Pantalla"; ADR-0040; T-154).

Responder es un POST del evaluador; el rol y las reglas las comprueba la función de negocio
(`services/questions.py`): sin rol, "acceso denegado" (403); una respuesta inválida vuelve a la
lista con el motivo (422). La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.assessment.models import Answer, AnswerScope, Question
from evaluon.assessment.services import evaluate, questions
from evaluon.audit.models import Channel
from evaluon.tenders.models import Procedure

QUESTIONS_TEMPLATE = "assessment/questions.html"
ANSWERED_PARAM = "respondida"


def _page(request, procedure, *, error="", status=200):
    rows = questions.question_list(request.user, procedure, channel=Channel.SCREEN)
    answered = request.GET.get(ANSWERED_PARAM)
    offered = None
    if answered and answered.isdigit():
        found = Answer.objects.select_related("question").filter(
            pk=int(answered), question__procedure=procedure).first()
        if found is not None:
            pairs = questions.affected_pairs(found)
            offered = {"answer": found, "pairs": pairs,
                       "decided": questions.decided_pairs(found),
                       "whole": questions.is_rectangular(pairs),
                       "offers": list(dict.fromkeys(o for o, _ in pairs))}
    return render(request, QUESTIONS_TEMPLATE, {
        "procedure": procedure, "rows": rows, "error": error, "offered": offered,
        "can_answer": getattr(request.user, "commission_role", "") == CommissionRole.EVALUATOR,
        "scopes": AnswerScope.choices, "default_scope": AnswerScope.REQUISITO},
        status=status)


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


@require_GET
def question_list(request, procedure_id):
    """Las preguntas del procedimiento, abiertas y respondidas."""
    return _page(request, _procedure(procedure_id))


@require_POST
def answer(request, question_id):
    """Responde la pregunta `question_id` con el alcance elegido."""
    try:
        question = Question.objects.select_related("procedure").get(pk=question_id)
    except Question.DoesNotExist:
        raise Http404("No hay una pregunta con ese número.")
    try:
        answered = questions.answer(
            request.user, question_id, request.POST.get("text", ""),
            request.POST.get("scope", AnswerScope.REQUISITO), channel=Channel.SCREEN)
    except questions.AnswerRefused as error:
        return _page(request, question.procedure, error=str(error), status=422)
    return redirect(reverse("assessment:questions", args=[question.procedure_id])
                    + f"?{ANSWERED_PARAM}={answered.answer.pk}")


@require_POST
def reevaluate(request, answer_id):
    """Pide evaluar de nuevo los pares que la respuesta alcanza."""
    try:
        found = Answer.objects.select_related("question__procedure").get(pk=answer_id)
    except Answer.DoesNotExist:
        raise Http404("No hay una respuesta con ese número.")
    procedure = found.question.procedure
    try:
        questions.reevaluate(request.user, answer_id, offer_id=request.POST.get("offer") or None,
                             channel=Channel.SCREEN)
    except (questions.AnswerRefused, evaluate.EvaluationRefused) as error:
        return _page(request, procedure, error=str(error), status=422)
    return redirect(reverse("assessment:questions", args=[procedure.pk]) + "?pedida=1")
