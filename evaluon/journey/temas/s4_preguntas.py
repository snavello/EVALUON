"""Tema s4_preguntas: preguntas a la Comisión y pedidos de subsanación de la sección «Evaluación y
dictamen» (REQ-090; plan 014, T-208).

Una sola tabla: asunto, oferta y requisito, estado y la respuesta registrada o la acción que
corresponde. Las preguntas abiertas se responden desde la fila (texto y alcance) y las respondidas
muestran su respuesta, quién y cuándo. Los resultados que se pueden subsanar (no se encontró el
documento o falta la hoja de compliance) muestran su recorrido: por decidir, pedida, documento
agregado. Todo sale de los servicios de `assessment` (`questions`, `remedy`): el tema no decide
nada (P3) y las acciones (`s4_preguntas_acciones`) llaman a los mismos servicios y vuelven a la
pestaña con el aviso de lo hecho.

Los pendientes de preguntas (con su enlace «Resolver») los lista `s4_propuesta`, que ya los suma a
la cuenta de la sección; este tema no agrega pendientes propios para no duplicarlos. El servicio
de subsanación no tiene «No pedir»: un resultado subsanable sin pedido queda «por decidir» y la
decisión de no pedir no se registra.
"""

from dataclasses import dataclass, field

from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.assessment.models import Action, AnswerScope, Decision, Doubt, Outcome
from evaluon.assessment.services import questions as questions_service
from evaluon.assessment.services import remedy as remedy_service
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections.base import TemaStatus
from evaluon.journey.temas import s4_preguntas_acciones as acciones
from evaluon.offers.services import offers as offers_service

KEY = "s4_preguntas"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_preguntas.html"

OPEN = ("nodet", "Abierta")
ANSWERED = ("cumple", "Respondida")
TO_DECIDE = ("nodet", "Por decidir")
REQUESTED = ("pend", "Pedida, falta el documento")
ADDED = ("pend", "Documento agregado")
CLOSED = ("cumple", "Subsanada")


def when(moment):
    """Fecha y hora locales (America/Argentina/Buenos_Aires), no las de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


@dataclass
class Line:
    """Una fila de la tabla."""

    anchor: str
    subject: str
    where: str
    icon: str
    name: str
    kind: str  # «pregunta» o «subsanacion»
    registered: list = field(default_factory=list)  # líneas de lo ya registrado
    question_id: int | None = None
    result_id: int | None = None
    can_answer: bool = False
    can_ask: bool = False  # pedir la subsanación
    can_add: bool = False  # agregar el documento
    can_reevaluate: bool = False
    reevaluate_waits: bool = False
    reason: str = ""


def _where(offer, requirement):
    return f"Oferta {offer.number} · requisito {requirement.number}"


def _question_lines(user, procedure, is_evaluator):
    lines = []
    for row in questions_service.question_list(user, procedure, channel=Channel.SCREEN):
        question = row.question
        state = ANSWERED if row.answer else OPEN
        line = Line(anchor=f"preg-{question.pk}", subject=f"Pregunta: {question.text}",
                    where=_where(question.offer, question.requirement), kind="pregunta",
                    icon=state[0], name=state[1], question_id=question.pk,
                    reason=question.reason, can_answer=is_evaluator)
        if row.answer is not None:
            who = row.answer.answered_by.username if row.answer.answered_by_id else "—"
            line.registered = [f"«{row.answer.text}»",
                               f"{who} · {when(row.answer.answered_at)} · "
                               f"{AnswerScope(row.answer.scope).label}"]
            if row.previous_answers:
                line.registered.append(
                    f"Reemplaza {len(row.previous_answers)} respuesta(s) anterior(es), "
                    "que quedan en el registro.")
        lines.append(line)
    return lines


def _is_remediable(result, effective):
    """`remedy_service.is_remediable(result)` con el resultado que rige ya conocido."""
    if effective == Outcome.SIN_DOCUMENTO:
        return True
    return (effective == Outcome.NO_DETERMINADO == result.outcome
            and result.doubt == Doubt.EXTERNO)


def _remedy_lines(user, procedure, is_evaluator):
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    lines = []
    live = set()
    for requirement in page.requirements:
        for offer in page.offers:
            cell = page.cells[(offer.pk, requirement.pk)]
            result = cell.result
            # `cell.effective_outcome` es `review.effective_outcome(result)` ya calculado por la
            # matriz: así no se consulta la decisión de nuevo por cada par (T-221).
            if result is None or not _is_remediable(result, cell.effective_outcome):
                continue
            state = remedy_service.state(result)
            if not state.applicable:
                continue
            live.add(result.pk)
            what = ("falta la hoja de compliance" if result.outcome == "no_determinado"
                    else "falta el documento")
            line = Line(anchor=f"sub-{result.pk}", subject=f"Subsanación: {what}",
                        where=_where(offer, requirement), kind="subsanacion",
                        icon=TO_DECIDE[0], name=TO_DECIDE[1], result_id=result.pk)
            if state.requested is not None:
                line.icon, line.name = REQUESTED
                line.registered.append(
                    f"Pedida por {state.requested.user.username} el {when(state.requested.at)}"
                    f" · motivo: {state.requested.note}")
            if state.added is not None:
                line.icon, line.name = ADDED
                reading = ("ya leído" if state.reading == offers_service.STATE_READ
                           else "se está leyendo")
                line.registered.append(
                    f"Documento agregado: «{state.added.document.title}» por "
                    f"{state.added.user.username} el {when(state.added.at)} ({reading})")
                line.can_reevaluate = is_evaluator
                line.reevaluate_waits = not state.can_reevaluate
            line.can_ask = is_evaluator and state.requested is None
            line.can_add = is_evaluator and state.requested is not None
            lines.append(line)
    lines.extend(_closed_lines(procedure, live))
    return lines


def _closed_lines(procedure, live):
    """Las subsanaciones de resultados que ya no rigen (se evaluaron de nuevo): quedan a la
    vista con lo que se pidió y lo que se agregó."""
    decisions = (Decision.objects.filter(
        result__offer__procedure=procedure,
        action__in=(Action.PEDIR_SUBSANACION, Action.SUBSANAR))
        .exclude(result_id__in=live)
        .select_related("user", "document", "result__offer", "result__requirement")
        .order_by("at", "pk"))
    by_result = {}
    for decision in decisions:
        by_result.setdefault(decision.result_id, []).append(decision)
    lines = []
    for result_id, mine in by_result.items():
        result = mine[0].result
        line = Line(anchor=f"sub-{result_id}", subject="Subsanación: ya se evaluó de nuevo",
                    where=_where(result.offer, result.requirement), kind="subsanacion",
                    icon=CLOSED[0], name=CLOSED[1], result_id=result_id)
        for decision in mine:
            if decision.action == Action.PEDIR_SUBSANACION:
                line.registered.append(
                    f"Pedida por {decision.user.username} el {when(decision.at)}"
                    f" · motivo: {decision.note}")
            else:
                line.registered.append(
                    f"Documento agregado: «{decision.document.title}» por "
                    f"{decision.user.username} el {when(decision.at)}")
        lines.append(line)
    return lines


def status(user, procedure):
    """Sin cuentas propias: los pendientes de preguntas ya los lista `s4_propuesta`."""
    return TemaStatus()


def context(user, procedure, request):
    is_evaluator = getattr(user, "commission_role", "") == CommissionRole.EVALUATOR
    lines = (_question_lines(user, procedure, is_evaluator)
             + _remedy_lines(user, procedure, is_evaluator))
    total = len(lines)
    to_decide = sum(1 for line in lines if line.icon == "nodet")
    only_open = request is not None and request.GET.get("preg") == "abiertas"
    if only_open:  # filtro simple por dirección: solo lo que espera una respuesta o decisión
        # exactamente las que cuenta el panel: abiertas de la matriz vigente, sin subsanaciones
        counted = {q.pk for status in memo.matrix_page(
            user, procedure.pk, channel=Channel.SCREEN).statuses
            for q in status.open_questions}
        lines = [line for line in lines
                 if line.kind == "pregunta" and line.question_id in counted]
    return {
        "only_open": only_open,
        "pid": procedure.pk, "lines": lines, "to_decide": to_decide,
        "resolved": total - to_decide, "is_evaluator": is_evaluator,
        "scopes": AnswerScope.choices, "default_scope": AnswerScope.REQUISITO,
    }


urlpatterns = acciones.urlpatterns
