"""Acciones de la Comisión sobre la matriz, desde la pestaña «Pliego y matriz» (REQ-081; plan 014,
T-201).

Cada acción es un POST que llama al servicio de `evaluon.tenders.services` que ya usa la pantalla
de la matriz (el mismo cambio, el mismo hecho de auditoría y el mismo rol) y vuelve a la pestaña
con el mensaje de lo hecho. Si el servicio rechaza el pedido, no cambia nada y el mensaje dice por
qué. Sin el rol que la acción pide, «acceso denegado» (403) con el rechazo registrado, como en la
pantalla vieja. El sistema no decide nada: cada botón es una decisión de una persona (P3).

El mensaje viaja firmado en la dirección (`?aviso=`), sin guardar nada en la sesión, y vale
cinco minutos.
"""

from functools import wraps

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    Consequence,
    MatrixVersion,
    PendingItem,
    Procedure,
    Requirement,
    Segment,
    VersionStatus,
)
from evaluon.tenders.services import consequences, suggestions, validation
from evaluon.tenders.services import matrix as matrix_service
from evaluon.tenders.services import review as review_service

SALT = "journey.s2.aviso"
AVISO_MAX_AGE = 300
ANCHOR = "#s2-aviso"
CHANNEL = Channel.SCREEN


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


def back(procedure, text, ok=True):
    url = reverse("expedientes:pliego", args=[procedure.pk])
    return redirect(f"{url}?aviso={pack(text, ok)}{ANCHOR}")


# --- Lo que falta decidir ------------------------------------------------------------------------


def blockers(version):
    """Cuántas cosas quedan sin decidir en `version` (REQ-035 de la 003): requisitos sin
    confirmar, sugerencias, tramos sin revisar y consecuencias sin elegir."""
    live = version.requirements.exclude(state__in=("quitado", "sugerido"))
    chosen = Consequence.objects.filter(requirement__in=live, chosen=True).values("requirement")
    counts = {
        "unconfirmed": live.filter(state="propuesto").count(),
        "suggestions": version.requirements.filter(state="sugerido").count(),
        "segments": version.pending_items.filter(resolved_at__isnull=True).count(),
        "consequences": live.exclude(pk__in=chosen).count(),
    }
    counts["total"] = sum(counts.values())
    return counts


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def condition_text(counts, number):
    """La frase junto al botón «Validar la versión N»."""
    if not counts["total"]:
        return f"No queda nada sin decidir: ya puede validar la versión {number}."
    parts = []
    if counts["unconfirmed"]:
        parts.append(_plural(counts["unconfirmed"], "requisito sin confirmar",
                             "requisitos sin confirmar"))
    if counts["suggestions"]:
        parts.append(_plural(counts["suggestions"], "sugerencia", "sugerencias"))
    if counts["segments"]:
        parts.append(_plural(counts["segments"], "tramo", "tramos"))
    if counts["consequences"]:
        parts.append(_plural(counts["consequences"], "consecuencia sin elegir",
                             "consecuencias sin elegir"))
    return (f"Quedan {counts['total']} sin decidir: {', '.join(parts)}. "
            "No se valida mientras quede alguno.")


# --- Búsqueda de lo que se toca ------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _requirement(procedure, requirement_id):
    try:
        return Requirement.objects.select_related("version").get(
            pk=requirement_id, version__procedure=procedure)
    except Requirement.DoesNotExist:
        raise Http404("No hay un requisito con ese número en este procedimiento.")


def _version(procedure, version_id):
    try:
        return MatrixVersion.objects.get(pk=version_id, procedure=procedure)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número en este procedimiento.")


def _act(procedure, action, success):
    """Corre `action`; con rechazo del servicio, vuelve con el motivo y sin cambiar nada."""
    try:
        done = action()
    except review_service.ReviewRefused as error:  # incluye validación y consecuencias
        return back(procedure, str(error), ok=False)
    return back(procedure, success(done))


def _motive(user, requirement, action, motive):
    """El motivo de una corrección o de un quitar: el servicio de la pantalla vieja no lo guarda,
    así que queda en un hecho propio, con quién y cuándo (la decisión del 2026-10-07)."""
    audit.record(
        EventType.REQUIREMENT_CHANGE, outcome=Outcome.OK, channel=CHANNEL, user=user,
        detail={"action": "motivo", "of": action, "requirement": requirement.pk,
                "version": requirement.version_id, "number": requirement.number,
                "reason": motive})


def _needs_motive(procedure, post):
    motive = " ".join(post.get("motive", "").split())
    if not motive:
        return None, back(procedure, "Escriba el motivo: es obligatorio y queda registrado.",
                          ok=False)
    return motive, None


def _draft(procedure):
    """El borrador abierto del procedimiento, o `None`."""
    return (MatrixVersion.objects.filter(procedure=procedure, status=VersionStatus.DRAFT)
            .order_by("-number").first())


def _no_draft(procedure):
    return back(procedure, "La matriz ya está validada y no se puede cambiar: abra una "
                "versión nueva.", ok=False)


def evaluator_only(view):
    """Corregir, agregar, quitar, restituir y decidir sugerencias son del evaluador (decisión del
    2026-10-10): el operador recibe 403 y el rechazo queda registrado, antes de mirar el pedido."""
    @wraps(view)
    def gate(request, *args, **kwargs):
        require_commission_role(request.user, CommissionRole.EVALUATOR,
                                operation=f"{view.__module__}.{view.__name__}", channel=CHANNEL)
        return view(request, *args, **kwargs)
    return gate


# --- Vistas --------------------------------------------------------------------------------------


@require_POST
def confirm(request, procedure_id):
    procedure = _procedure(procedure_id)
    ids = [i for i in request.POST.getlist("requirement") if i.isdigit()]
    for requirement_id in ids:
        _requirement(procedure, requirement_id)
    return _act(procedure, lambda: review_service.confirm(request.user, ids, channel=CHANNEL),
                lambda done: (f"Se confirmó el requisito {done.requirements[0].number}."
                              if len(done.requirements) == 1 else
                              f"Se confirmaron {len(done.requirements)} requisitos."
                              if done.requirements else "No había nada para confirmar."))


@require_POST
@evaluator_only
def correct(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    post = request.POST
    motive, refused = _needs_motive(procedure, post)
    if refused:
        return refused

    def action():
        done = review_service.correct(
            request.user, requirement.pk,
            category=post.get("category") or None,
            items=post.get("items") if "items" in post else None,
            segment=post.get("segment") or None, quote=post.get("quote") or None,
            add_segments=post.getlist("add_segment"),
            remove_quotes=post.getlist("remove_quote"), channel=CHANNEL)
        _motive(request.user, requirement, "corregir", motive)
        return done

    return _act(procedure, action, lambda done: (
        f"Se corrigió el requisito {requirement.number}. Quedó registrado el motivo, quién y "
        "cuándo; si estaba confirmado, vuelve a quedar sin confirmar."))


@require_POST
@evaluator_only
def remove(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    motive, refused = _needs_motive(procedure, request.POST)
    if refused:
        return refused

    def action():
        done = review_service.remove(request.user, requirement.pk, channel=CHANNEL)
        _motive(request.user, requirement, "quitar", motive)
        return done

    return _act(procedure, action, lambda done: (
        f"Se quitó el requisito {requirement.number}. No se borra: queda entre los quitados, "
        "con su motivo."))


@require_POST
@evaluator_only
def restore(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    return _act(procedure, lambda: review_service.restore(
        request.user, requirement.pk, channel=CHANNEL),
        lambda done: f"Se restituyó el requisito {requirement.number}.")


@require_POST
@evaluator_only
def add(request, procedure_id):
    """Agrega un formal o económico desde un tramo del pliego. Sin fragmento escrito, toma el
    texto del tramo entero: no hace falta tipear nada."""
    procedure = _procedure(procedure_id)
    version = _draft(procedure)
    if version is None:
        return _no_draft(procedure)
    post = request.POST
    quote = post.get("quote", "")
    segment_id = post.get("segment", "")
    if not quote.strip() and segment_id.isdigit():
        found = Segment.objects.filter(pk=segment_id).first()
        quote = found.text if found else ""
    return _act(procedure, lambda: review_service.add_requirement(
        request.user, version.pk, segment=segment_id, quote=quote,
        category=post.get("category", ""),
        items=post.get("items") if post.get("items", "").strip() else None,
        pending=post.get("pending") or None, channel=CHANNEL),
        lambda done: f"Se agregó el requisito {done.requirements[0].number}, sin confirmar.")


@require_POST
@evaluator_only
def add_technical(request, procedure_id):
    procedure = _procedure(procedure_id)
    version = _draft(procedure)
    if version is None:
        return _no_draft(procedure)
    post = request.POST
    return _act(procedure, lambda: review_service.add_technical_row(
        request.user, version.pk, item=post.get("item", ""),
        segments=post.getlist("segment"), channel=CHANNEL),
        lambda done: f"Se agregó la fila técnica {done.requirements[0].number}, sin confirmar.")


@require_POST
@evaluator_only
def accept_suggestion(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    return _act(procedure, lambda: suggestions.accept_suggestion(
        request.user, requirement.pk, channel=CHANNEL),
        lambda done: f"La sugerencia pasó a requisito {requirement.number}, sin confirmar.")


@require_POST
@evaluator_only
def remove_suggestion(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    return _act(procedure, lambda: review_service.remove(
        request.user, requirement.pk, channel=CHANNEL),
        lambda done: f"Se quitó la sugerencia {requirement.number}. Queda entre los quitados.")


@require_POST
def resolve_segment(request, procedure_id, pending_id):
    procedure = _procedure(procedure_id)
    if not PendingItem.objects.filter(pk=pending_id, version__procedure=procedure).exists():
        raise Http404("No hay un tramo pendiente con ese número en este procedimiento.")
    return _act(procedure, lambda: review_service.resolve_pending(
        request.user, pending_id, channel=CHANNEL),
        lambda done: "El tramo quedó marcado como revisado, sin requisitos.")


@require_POST
def choose_consequence(request, procedure_id, requirement_id):
    procedure = _procedure(procedure_id)
    requirement = _requirement(procedure, requirement_id)
    post = request.POST
    return _act(procedure, lambda: consequences.choose(
        request.user, requirement.pk, option=post.get("option") or None,
        consequence_type=post.get("consequence_type") or None, note=post.get("note", ""),
        segment=post.get("segment") or None, quote=post.get("quote", ""), channel=CHANNEL),
        lambda picked: (f"Consecuencia del requisito {requirement.number}: "
                        f"{picked.get_consequence_type_display()}. Quedó registrado quién la "
                        "eligió y cuándo."))


@require_POST
def validate(request, procedure_id, version_id):
    procedure = _procedure(procedure_id)
    version = _version(procedure, version_id)
    # Sin el rol, el servicio rechaza y deja el hecho: no se adelanta con un mensaje.
    if (version.status == VersionStatus.DRAFT
            and request.user.commission_role == CommissionRole.EVALUATOR):
        counts = blockers(version)
        if counts["total"]:
            return back(procedure, "No se puede validar. "
                        + condition_text(counts, version.number), ok=False)
    return _act(procedure, lambda: validation.validate(request.user, version.pk,
                                                       channel=CHANNEL),
                lambda done: f"La versión {done.number} quedó validada: se registró quién y "
                "cuándo.")


@require_POST
@evaluator_only
def open_new(request, procedure_id):
    procedure = _procedure(procedure_id)
    return _act(procedure, lambda: validation.open_new_version(
        request.user, procedure.pk, channel=CHANNEL),
        lambda new: f"Se abrió la versión {new.number} en borrador, sobre la anterior. La "
        "anterior queda como estaba.")


@require_POST
def propose(request, procedure_id):
    """Pide la propuesta de la matriz (el mismo servicio que el botón de la pantalla vieja) y
    vuelve a la pestaña con el aviso."""
    procedure = _procedure(procedure_id)
    try:
        matrix_service.request_matrix(request.user, procedure, channel=CHANNEL)
    except matrix_service.MatrixRefused as error:
        return back(procedure, str(error), ok=False)
    return back(procedure, "Se pidió la propuesta de la matriz. El sistema la arma en segundo "
                           "plano; esta pestaña muestra el avance.")


urlpatterns = [
    path("matriz/proponer/", propose, name="s2_proponer"),
    path("matriz/confirmar/", confirm, name="s2_confirmar"),
    path("matriz/agregar/", add, name="s2_agregar"),
    path("matriz/agregar-tecnico/", add_technical, name="s2_agregar_tecnico"),
    path("matriz/nueva-version/", open_new, name="s2_nueva_version"),
    path("matriz/validar/<int:version_id>/", validate, name="s2_validar"),
    path("matriz/requisito/<int:requirement_id>/corregir/", correct, name="s2_corregir"),
    path("matriz/requisito/<int:requirement_id>/quitar/", remove, name="s2_quitar"),
    path("matriz/requisito/<int:requirement_id>/restituir/", restore, name="s2_restituir"),
    path("matriz/requisito/<int:requirement_id>/consecuencia/", choose_consequence,
         name="s2_consecuencia"),
    path("matriz/sugerencia/<int:requirement_id>/pasar/", accept_suggestion,
         name="s2_sugerencia_pasar"),
    path("matriz/sugerencia/<int:requirement_id>/quitar/", remove_suggestion,
         name="s2_sugerencia_quitar"),
    path("matriz/tramo/<int:pending_id>/revisado/", resolve_segment, name="s2_tramo_revisado"),
]
