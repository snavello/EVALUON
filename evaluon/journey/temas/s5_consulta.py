"""Tema s5_consulta: consulta de normativa con citas literales, dentro de la pestaña Normativas
(sección «normativas»; REQ-096, REQ-097; plan 014, T-216).

Usa la consulta existente de `evaluon/queries` sin modificarla (`services.ask`): la fecha de
autorización es la del procedimiento, ya cargada, y la respuesta se muestra en la pestaña con sus
citas literales numeradas [1] [2] y la parte de la norma de cada una. Un «no determinado» o una
falla técnica se dicen en llano. La consulta corre con el modelo y puede tardar: el botón se
desactiva y la pestaña muestra el estado de la espera (`s5_consulta.js`).

Historial. La consulta guardada (`queries_query`) no sabe de procedimientos y no se modifica. Cada
consulta hecha desde una pestaña deja además un hecho `query` de auditoría (P6) con el vínculo
`{"kind": "procedure_query", "query_id", "procedure_id"}`; el historial del procedimiento sale de
esos hechos. Como en la pantalla global, cada persona ve solo sus consultas.
"""

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.journey.sections.base import TemaStatus
from evaluon.queries import services
from evaluon.queries import views as query_views
from evaluon.queries.models import Query, Reason, Status
from evaluon.tenders.models import Procedure

KEY = "s5_consulta"
SECTION = "normativas"
PARTIAL = "journey/temas/s5_consulta.html"

CHANNEL = Channel.SCREEN
SALT = "journey.s5.consulta"
AVISO_MAX_AGE = 300
LINK_KIND = "procedure_query"
HISTORY_LIMIT = 20

# Estado de una consulta guardada -> (símbolo del ícono, nombre).
STATES = {
    Status.GROUNDED: ("cumple", "Con fundamento"),
    Status.UNDETERMINED: ("nodet", "No determinado"),
    Status.ERROR: ("nocumple", "No se pudo completar"),
}

# Por qué quedó «no determinado», en llano.
UNDETERMINED_WHY = {
    Reason.NO_REGIME_AT_DATE: "Para la fecha de autorización de este procedimiento no hay un "
                              "régimen específico cargado en el sistema.",
    Reason.BELOW_THRESHOLD: "La normativa cargada no tiene nada pertinente para esta pregunta.",
    Reason.MODEL_ABSTAINED: "El sistema no encontró en la normativa cargada un fundamento para "
                            "responder.",
    Reason.INVALID_CITATION: "El sistema no pudo respaldar la respuesta con citas de la "
                             "normativa, así que no la muestra.",
}


# --- Aviso firmado en la dirección ---------------------------------------------------------------


def pack(text, ok=True):
    return signing.dumps({"ok": ok, "m": text}, salt=SALT, compress=True)


def unpack(value):
    """El aviso firmado de la dirección, o `None` si falta, está alterado o venció."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=AVISO_MAX_AGE)
    except signing.BadSignature:
        return None
    return {"ok": bool(data.get("ok")), "text": str(data.get("m", ""))}


def tab_url(procedure_id):
    return reverse("expedientes:normativas", args=[procedure_id])


def local(moment):
    """Fecha y hora locales (America/Argentina/Buenos_Aires), no las de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}" if moment else ""


# --- Estado del tema -----------------------------------------------------------------------------


def status(user, procedure):
    """Consultar no deja nada pendiente ni sugerido: el tema aporta cuentas en cero."""
    return TemaStatus()


# --- Historial -----------------------------------------------------------------------------------


def _linked_query_ids(user, procedure_id):
    """Los números de las consultas de `user` hechas desde la pestaña de este procedimiento."""
    ids = AuditEvent.objects.filter(
        event_type=EventType.QUERY, user=user, detail__kind=LINK_KIND,
        detail__procedure_id=procedure_id).values_list("detail__query_id", flat=True)
    return [int(one) for one in ids]


def _history(user, procedure_id):
    """Las consultas del procedimiento de esta persona, la más nueva primero."""
    ids = _linked_query_ids(user, procedure_id)
    if not ids:
        return []
    queries = (Query.objects.filter(pk__in=ids, user=user).order_by("-asked_at", "-pk")
               .only("id", "asked_at", "question", "status")[:HISTORY_LIMIT])
    rows = []
    for one in queries:
        icon, name = STATES.get(one.status, STATES[Status.ERROR])
        rows.append({"id": one.pk, "when": local(one.asked_at), "question": one.question,
                     "icon": icon, "state": name,
                     "url": f"{tab_url(procedure_id)}?consulta={one.pk}#s5-consulta-respuesta"})
    return rows


# --- Respuesta -----------------------------------------------------------------------------------


def _answer(query):
    """La consulta guardada como la muestra el parcial. Las citas se numeran por unidad en el
    orden en que aparecen; cada afirmación lleva los números de las suyas y el texto literal de
    cada una sale una sola vez, en la lista de citas."""
    result = query.result
    state = result.get("status")
    if state not in Status.values:
        state = Status.ERROR
    icon, name = STATES[state]
    answer = {"id": query.pk, "question": query.question, "state": state, "icon": icon,
              "state_name": name, "when": local(query.asked_at),
              "reference_date": query.reference_date,
              "regime": [item.get("name") for item in result.get("regime") or []
                         if item.get("name")],
              "statements": [], "sources": [], "notices": [], "why": ""}
    if state == Status.UNDETERMINED:
        answer["why"] = UNDETERMINED_WHY.get(result.get("reason"),
                                             UNDETERMINED_WHY[Reason.MODEL_ABSTAINED])
    if state != Status.GROUNDED:
        return answer
    answer["notices"] = query_views._notices(result)
    numbers = {}
    for statement in query_views._statements(result):
        refs = []
        for citation in statement["citations"]:
            key = citation["id"]
            if key not in numbers:
                numbers[key] = len(numbers) + 1
                answer["sources"].append({"n": numbers[key], "id": key, "citation": citation})
            elif citation.get("text") is not None:
                # La unidad volvió a mostrarse con su texto (regímenes que difieren).
                source = answer["sources"][numbers[key] - 1]
                if source["citation"].get("text") is None:
                    source["citation"] = citation
            refs.append(numbers[key])
        answer["statements"].append({"text": statement["text"], "refs": refs,
                                     "regimes_differ": statement["regimes_differ"]})
    return answer


def context(user, procedure, request):
    pid = procedure.pk if procedure is not None else None
    base = {"pid": pid, "aviso": unpack(request.GET.get("aviso")) if request else None,
            "can_ask": False, "answer": None, "history": [], "authorization_date": None}
    if procedure is None:
        return base
    base["authorization_date"] = procedure.authorization_date
    base["can_ask"] = (getattr(user, "commission_role", "")
                       in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR))
    history = _history(user, pid)
    base["history"] = history
    wanted = request.GET.get("consulta", "") if request else ""
    if wanted.isdigit() and int(wanted) in {row["id"] for row in history}:
        query = Query.objects.filter(pk=int(wanted), user=user).first()
        base["answer"] = _answer(query) if query is not None else None
    return base


# --- Acción --------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _back(procedure, text=None, ok=True, query=None):
    if query is not None:
        return redirect(f"{tab_url(procedure.pk)}?consulta={query.pk}#s5-consulta-respuesta")
    return redirect(f"{tab_url(procedure.pk)}?aviso={pack(text, ok)}#s5-consulta")


@require_POST
def ask(request, procedure_id):
    """Consulta la normativa con la fecha de autorización del procedimiento (`services.ask`),
    deja el vínculo con el procedimiento y vuelve a la pestaña con la respuesta."""
    procedure = _procedure(procedure_id)
    require_commission_role(request.user, CommissionRole.OPERATOR,
                            operation="evaluon.journey.temas.s5_consulta.ask", channel=CHANNEL)
    question = request.POST.get("question", "")
    try:
        query = services.ask(request.user, question, procedure.authorization_date,
                             channel=CHANNEL)
    except services.QueryRefused as error:  # incluye la fecha posterior al día
        return _back(procedure, str(error), ok=False)
    audit.record(EventType.QUERY, outcome=Outcome.OK, channel=CHANNEL, user=request.user,
                 detail={"kind": LINK_KIND, "query_id": query.pk, "procedure_id": procedure.pk})
    return _back(procedure, query=query)


urlpatterns = [
    path("normativas/consulta/", ask, name="s5_consultar"),
]
