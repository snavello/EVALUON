"""Tema s2_matriz: la matriz de cumplimiento de la sección «Pliego y matriz» (REQ-081,
REQ-082; plan 014, T-192).

Muestra la última versión no descartada en una tabla agrupada por tipo (formales, económicos,
técnicos), con filtros (solo lo que falta decidir, por tipo, por estado, por texto), filas que
se abren con la cita literal del pliego y la lista de versiones con fecha y quién validó cada
una. Desde T-201 la Comisión decide todo acá (confirmar, corregir, quitar, restituir, agregar,
sugerencias, tramos, consecuencia, validar y abrir una versión nueva) con las acciones de
`s2_matriz_acciones`, que llaman a los mismos servicios que la pantalla vieja. Un operador no
ve botones de decisión: ve que la decide un evaluador. El tema no decide nada (P3).

Las cuentas de pendientes y sugerencias de la matriz las suma la etapa `matriz` de la 013;
este tema no las repite.
"""

from collections import defaultdict
from dataclasses import dataclass, field, fields

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.journey import memo
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Tile, detail_id
from evaluon.tenders.models import (
    Consequence,
    ConsequenceType,
    MatrixVersion,
    RequirementClass,
    RequirementOrigin,
    RequirementState,
    Segment,
    VersionStatus,
)
from evaluon.journey.temas import s2_matriz_acciones as acciones
from evaluon.tenders.services import consequences as consequence_service
from evaluon.tenders.services import matrix_page

KEY = "s2_matriz"
SECTION = "pliego"
PARTIAL = "journey/temas/s2_matriz.html"
urlpatterns = acciones.urlpatterns

TYPE_ORDER = (RequirementClass.FORMAL, RequirementClass.ECONOMICO, RequirementClass.TECNICO)
TYPE_LABELS = {
    RequirementClass.FORMAL: "Requisitos formales",
    RequirementClass.ECONOMICO: "Requisitos económicos",
    RequirementClass.TECNICO: "Requisitos técnicos por renglón",
}
TYPE_OPTIONS = (("formal", "Formales"), ("economico", "Económicos"),
                ("tecnico", "Técnicos por renglón"))
FILTERS = (("", "Todos"), ("falta", "Solo lo que falta decidir"), ("conf", "Confirmados"),
           ("circ", "Cambiados por circular"))
VERSION_LABELS = {VersionStatus.VALIDATED: "Validada", VersionStatus.DRAFT: "En revisión",
                  VersionStatus.DISCARDED: "Descartada"}
EXCERPT = 220


@dataclass
class Row:
    number: int
    category: str
    document: str
    text: str
    place: object
    consequence: str
    marks: list
    unconfirmed: bool
    changed: bool
    page_row: object  # la fila de `matrix_page`, con sus citas y cambios
    suggestions: list
    motives: list = field(default_factory=list)  # «Corregido por … · motivo: …»
    options: list = field(default_factory=list)  # consecuencias elegibles (solo quien decide)
    technical: bool = False
    no_indica: dict = field(default_factory=dict)  # «El pliego no indica consecuencia» (T-232)


def _day(moment):
    """La fecha en hora local (America/Argentina/Buenos_Aires), no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y}"


def _pliego_read(user, procedure):
    """Hay pliego y todo lo cargado está leído: se puede pedir la propuesta de la matriz."""
    from evaluon.journey.stages import base as stage_base
    from evaluon.journey.stages import pliego
    return pliego.compute(user, procedure).state == stage_base.LISTA


def latest_version(procedure):
    """La versión que cuenta: la última no descartada."""
    return (MatrixVersion.objects.filter(procedure=procedure)
            .exclude(status=VersionStatus.DISCARDED).order_by("-number").first())


PLAIN_REASONS = {
    "pagina_ilegible": "No se pudo leer esta página",
    "pagina_dudosa": "Esta página se leyó con dudas",
    "tabla": "Hay una tabla que el sistema no pudo interpretar",
    "no_ubicado": "El sistema no pudo ubicar este tramo en el pliego",
    "sin_disposicion": "El sistema no pudo decidir si este tramo contiene requisitos",
    "marcadores": "El sistema lo descartó, pero el tramo tiene marcas de obligación",
    "renglon_sin_especificaciones": "Este renglón no tiene especificaciones",
}


def _plain_reason(item):
    return PLAIN_REASONS.get(item.reason, item.get_reason_display())


def _where(segment):
    document = segment.reading.document.title
    return f"{document} › {segment.path}" if segment.path else document


WHY = {
    "req": "La matriz no se puede validar con requisitos sin confirmar, y la evaluación de "
           "las ofertas se hace sobre la matriz validada.",
    "tramo": "Un tramo del pliego sin revisar puede esconder un requisito que no entró a la "
             "matriz.",
    "consec": "Sin la consecuencia elegida, el sistema no sabe qué pasa si una oferta no "
              "cumple el requisito.",
    "sug": "Es algo que el sistema encontró y no está en la matriz: si nadie lo decide, "
           "queda fuera de la evaluación.",
}
# `Item.why` lo agrega la tarea de la lista de pendientes (T-318); hasta que entre, el renglón
# se arma sin él.
_ITEM_HAS_WHY = "why" in {f.name for f in fields(Item)}


def _item(kind, *args, **kwargs):
    """Un renglón de la matriz con su «por qué importa» cuando `Item` lo admite."""
    if _ITEM_HAS_WHY:
        kwargs["why"] = WHY[kind]
    return Item(*args, kind=kind, **kwargs)


def _decision_items(version):
    """Cada cosa que la Comisión debe decidir en el borrador, con su ancla en esta pestaña.
    Devuelve `(pendientes, sugerencias, cuántas consecuencias faltan)`."""
    base = reverse("expedientes:pliego", args=[version.procedure_id])
    live = version.requirements.exclude(state__in=("quitado", "sugerido")).order_by("number")
    chosen = set(Consequence.objects.filter(requirement__in=live, chosen=True)
                 .values_list("requirement_id", flat=True))
    pending = []
    for requirement in live.filter(state="propuesto"):
        pending.append(_item("req", f"Requisito {requirement.number} sin confirmar",
                            f"{base}#req-{requirement.number}", 1, "Resolver",
                            noun="requisitos sin confirmar",
                            group_url=f"{base}?filtro=falta#s2-matriz"))
    for item in version.pending_items.filter(resolved_at__isnull=True).select_related(
            "segment__reading__document").order_by("pk"):
        pending.append(_item("tramo", f"Tramo por revisar: {_where(item.segment)}",
                            f"{base}#tramo-{item.pk}", 1, "Resolver",
                            noun="tramos por revisar", group_url=f"{base}#s2-decidir"))
    missing = [r for r in live if r.pk not in chosen]
    for requirement in missing:
        pending.append(_item("consec", f"Consecuencia sin elegir: requisito {requirement.number}",
                            f"{base}#req-{requirement.number}", 1, "Resolver",
                            noun="consecuencias sin elegir",
                            group_url=f"{base}?filtro=falta#s2-matriz"))
    suggestions = []
    for requirement in version.requirements.filter(state="sugerido").order_by("number"):
        suggestions.append(_item("sug", f"Sugerencia {requirement.number} para decidir",
                                f"{base}#sug-{requirement.number}", 1, "Resolver",
                                noun="sugerencias para decidir", group_url=f"{base}#s2-decidir"))
    return pending, suggestions, len(missing)


def status(user, procedure):
    version = latest_version(procedure)
    if version is None:
        return TemaStatus()
    who = f" por {version.validated_by.username}" if version.validated_by_id else ""
    if version.status == VersionStatus.VALIDATED:
        source = (f"Matriz: versión {version.number} validada el "
                  f"{_day(version.validated_at)}{who}.")
    else:
        source = f"Matriz: versión {version.number} en revisión."
    if version.status == VersionStatus.DRAFT:
        pending, suggestions, no_consequence = _decision_items(version)
        # La etapa de la matriz ya cuenta los requisitos sin confirmar y los tramos; acá se
        # suman las consecuencias sin elegir, que también frenan la validación.
        return TemaStatus(sources=(source,), pending=no_consequence,
                          pending_items=tuple(pending), suggestion_items=tuple(suggestions),
                          detailed_stages=("matriz",))
    return TemaStatus(sources=(source,))


def _excerpt(text):
    text = " ".join(text.split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"


def _changed_by(row):
    """Los documentos (circulares) que cambiaron el texto de alguna cita del requisito, en el
    orden de fecha y sin repetir (REQ-085)."""
    titles = []
    for quote in row.quotes:
        for source in [*quote.earlier, *([quote.current] if quote.current else [])]:
            title = source.place.document_title
            if title not in titles:
                titles.append(title)
    return titles


def _marks(row):
    marks = []
    requirement = row.requirement
    if row.added_by:
        marks.append(f"Agregado por {row.added_by.document_title}")
    if requirement.origin == RequirementOrigin.AGREGADO:
        marks.append("Agregado por una persona")
    if requirement.origin == RequirementOrigin.DEVUELTO:
        marks.append("Devuelto de las descartadas")
    changers = _changed_by(row)
    if changers:
        marks.append(f"Cambiado por {', '.join(changers)} (versión {requirement.version.number})")
    if any(q.voided for q in row.quotes):
        marks.append("Sin efecto por circular")
    if any(q.wide for q in row.quotes):
        marks.append("Cita amplia, revisar")
    if row.review_notes:
        marks.append("Una circular podría dejarla sin efecto")
    return marks


def _changed(row):
    return bool(row.added_by or row.review_notes
                or any(q.current or q.earlier or q.voided for q in row.quotes))


def _consequences(requirement_ids):
    found = defaultdict(list)
    for consequence in Consequence.objects.filter(
            requirement_id__in=requirement_ids).select_related("chosen_by").order_by("pk"):
        found[consequence.requirement_id].append(consequence)
    return found


def _consequence_text(consequences):
    chosen = next((c for c in consequences if c.chosen), None)
    if chosen is not None:
        return chosen.get_consequence_type_display()
    return "Sin elegir"


def _suggested(consequences):
    return [c.get_consequence_type_display() for c in consequences
            if c.origin == "sistema" and c.consequence_type != "no_determinada"]


def _no_indica(options):
    """La opción «El pliego no indica consecuencia» de un requisito (T-232): se ofrece siempre.
    Queda marcada si ya se eligió o si lo único que propuso el sistema es «no determinada» y
    todavía no se eligió nada; la Comisión la confirma al registrar."""
    chosen = any(o.chosen and o.consequence.consequence_type == ConsequenceType.SIN_CONSECUENCIA
                 for o in options)
    proposed = (any(o.undetermined for o in options)
                and not any(o.from_system and not o.undetermined for o in options)
                and not any(o.chosen for o in options))
    return {"chosen": chosen, "proposed": proposed, "checked": chosen or proposed}


def _rows(page, with_options=False):
    every = [row for group in page.groups for row in group.rows] + list(page.technical)
    every.sort(key=lambda row: row.requirement.number)
    consequences = _consequences([row.requirement.pk for row in every])
    rows = []
    for source in every:
        requirement = source.requirement
        first = source.quotes[0] if source.quotes else None
        items = ", ".join(str(i) for i in requirement.items)
        text = _excerpt(first.text) if first else "Sin cita"
        if requirement.category == RequirementClass.TECNICO:
            text = f"Renglón {items or '—'} · {text}"
        mine = consequences.get(requirement.pk, [])
        every_option = consequence_service.options(requirement) if with_options else []
        rows.append(Row(
            number=requirement.number, category=requirement.category,
            document=first.place.document_title if first else "Sin cita", text=text,
            place=first.place if first else None, consequence=_consequence_text(mine),
            marks=_marks(source), unconfirmed=requirement.state == RequirementState.PROPUESTO,
            changed=_changed(source), page_row=source, suggestions=_suggested(mine),
            options=[o for o in every_option if not o.undetermined
                     and o.consequence.consequence_type != ConsequenceType.SIN_CONSECUENCIA],
            no_indica=_no_indica(every_option) if with_options else {},
            technical=requirement.category == RequirementClass.TECNICO))
    return rows


def _select(rows, query):
    """Aplica los filtros de la dirección. Un valor desconocido se ignora."""
    kind = query.get("tipo", "")
    state = query.get("filtro", "")
    text = " ".join(query.get("q", "").lower().split())
    if kind not in dict(TYPE_OPTIONS):
        kind = ""
    if state not in dict(FILTERS):
        state = ""
    chosen = []
    for row in rows:
        if kind and row.category != kind:
            continue
        if state == "falta" and not row.unconfirmed:
            continue
        if state == "conf" and row.unconfirmed:
            continue
        if state == "circ" and not row.changed:
            continue
        if text and text not in f"{row.number} {row.text} {row.document}".lower():
            continue
        chosen.append(row)
    return chosen, kind, state, text


def _groups(rows):
    """Por tipo (formales, económicos, técnicos) y, dentro, por documento del pliego."""
    groups = []
    for category in TYPE_ORDER:
        mine = [row for row in rows if row.category == category]
        if not mine:
            continue
        sub, last = [], None
        for row in mine:
            heading = "" if category == RequirementClass.TECNICO else row.document
            if heading != last:
                sub.append({"heading": heading, "rows": []})
                last = heading
            sub[-1]["rows"].append(row)
        groups.append({"category": category, "label": TYPE_LABELS[category],
                       "count": len(mine), "unconfirmed": sum(r.unconfirmed for r in mine),
                       "subgroups": sub})
    return groups


def _versions(procedure):
    versions = procedure.matrix_versions.select_related("validated_by", "based_on").annotate(
        total=Count("requirements", filter=~Q(requirements__state__in=(
            RequirementState.QUITADO, RequirementState.SUGERIDO)))).order_by("-number")
    rows = []
    for version in versions:
        if version.status == VersionStatus.VALIDATED:
            when, who = version.validated_at, version.validated_by
            when_text = _day(when)
        elif version.status == VersionStatus.DISCARDED:
            when_text, who = _day(version.discarded_at), version.discarded_by
        else:
            when_text, who = f"abierta el {_day(version.created_at)}", None
        reason = ("Propuesta del sistema sobre el pliego" if version.based_on is None
                  else f"Abierta sobre la versión {version.based_on.number}")
        rows.append({"version": version, "label": VERSION_LABELS[version.status],
                     "draft": version.status == VersionStatus.DRAFT, "reason": reason,
                     "when": when_text, "who": who.username if who else "",
                     "total": version.total})
    return rows


def _segment_choices(page, version):
    """Los tramos del pliego para elegir uno. Una versión sin propuesta (la del caso de
    medición) usa, como el servicio de revisión, las lecturas de los documentos del
    procedimiento."""
    if page.segment_options or not page.can_edit:
        return page.segment_options
    segments = (Segment.objects.filter(reading__document__procedure_id=version.procedure_id)
                .select_related("reading__document")
                .order_by("reading__document_id", "order"))
    return [(s.pk, f"{s.reading.document.title} · {s.path or s.label or s.key}: "
                   + " ".join(s.text.split())[:70]) for s in segments]


def _tramos(page):
    rows = [row for row in page.pending if row.item.resolved_at is None]
    for row in rows:
        row.reason = _plain_reason(row.item)
    return rows


def _motives(requirement_ids):
    """El motivo de cada corrección o quitar, con quién y cuándo, desde el hecho de auditoría."""
    found = defaultdict(list)
    verbs = {"corregir": "Corregido", "quitar": "Quitado"}
    events = AuditEvent.objects.filter(
        event_type=EventType.REQUIREMENT_CHANGE, detail__action="motivo",
        detail__requirement__in=list(requirement_ids)).select_related("user").order_by("pk")
    for event in events:
        who = event.user.username if event.user else event.username
        when = f"{timezone.localtime(event.occurred_at):%d/%m %H:%M}"
        verb = verbs.get(event.detail.get("of"), "Cambiado")
        found[event.detail["requirement"]].append(
            f"{verb} por {who} el {when} · motivo: {event.detail.get('reason', '')}")
    return found


def context(user, procedure, request):
    version = latest_version(procedure)
    base = {"version": None, "versions": _versions(procedure), "types": TYPE_OPTIONS,
            "filters": FILTERS, "can_propose": _pliego_read(user, procedure),
            "pid": procedure.pk, "aviso": acciones.unpack(request.GET.get("aviso"))}
    if version is None:
        return base
    page = matrix_page.matrix_page(user, version.pk, channel=Channel.SCREEN)
    is_evaluator = user.commission_role == CommissionRole.EVALUATOR
    decides = is_evaluator and version.status == VersionStatus.DRAFT
    rows = _rows(page, with_options=decides)
    motives = _motives([r.page_row.requirement.pk for r in rows]
                       + [r.requirement.pk for r in page.removed])
    for row in rows:
        row.motives = motives.get(row.page_row.requirement.pk, [])
    removed_motives = {r.requirement.pk: motives.get(r.requirement.pk, [])
                       for r in page.removed}
    chosen, kind, state, text = _select(rows, request.GET)
    unconfirmed = sum(r.unconfirmed for r in rows)
    changed = sum(r.changed for r in rows)
    counters = {"": len(rows), "falta": unconfirmed, "conf": len(rows) - unconfirmed,
                "circ": changed}
    counts = acciones.blockers(version) if version.status == VersionStatus.DRAFT else None
    segments = _tramos(page)
    return {
        **base, "version": version, "draft": page.draft, "groups": _groups(chosen),
        "shown": len(chosen), "total": len(rows), "kind": kind, "state": state, "q": text,
        "filter_buttons": [(value, label, counters[value], value == state)
                           for value, label in FILTERS],
        "summary": {"formal": page.counts["formal"], "economico": page.counts["economico"],
                    "tecnico": page.counts["tecnico"], "unconfirmed": unconfirmed,
                    "changed": changed},
        "print_url": reverse("tenders:print", args=[version.pk]),
        "pdf_url": reverse("tenders:pdf", args=[version.pk]),
        "coverage_url": reverse("tenders:coverage", args=[version.pk]) if page.run else "",
        "discarded_url": reverse("tenders:discarded", args=[version.pk]),
        # Decidir (solo el evaluador, en un borrador).
        "is_draft": version.status == VersionStatus.DRAFT,
        "is_evaluator": is_evaluator,
        "can_review": decides,
        "unconfirmed_ids": [r.page_row.requirement.pk for r in rows if r.unconfirmed],
        "suggestion_rows": page.suggestions, "segment_rows": segments,
        "to_decide": len(page.suggestions) + len(segments),
        "removed": [(r, removed_motives[r.requirement.pk]) for r in page.removed], "segment_options": _segment_choices(page, version),
        "technical_rows": [r for r in rows if r.technical],
        # «No determinada» no se elige y «El pliego no indica consecuencia» tiene su propia opción.
        "consequence_types": [(v, l) for v, l in ConsequenceType.choices
                              if v not in (ConsequenceType.NO_DETERMINADA.value,
                                           ConsequenceType.SIN_CONSECUENCIA.value)],
        "blockers": counts, "blocked": bool(counts and counts["blocking"]),
        "condition": acciones.condition_text(counts, version.number) if counts else "",
        "can_open_new": page.can_open_new,
        # Qué etapas de la propuesta corrieron fuera del equipo (REQ-122, T-291).
        "external_line": page.external_line,
    }


# --- Tablero (REQ-126, REQ-127, REQ-141; plan 017, «Pliego y matriz»; T-325) -----------------------

DETAIL = detail_id(KEY)
# Parámetros de la dirección que dejan la matriz filtrada o con el aviso de una acción.
OPENING_PARAMS = ("filtro", "tipo", "q", "aviso")
HEAT_TYPES = ((RequirementClass.FORMAL, "Formales"), (RequirementClass.ECONOMICO, "Económicos"),
              (RequirementClass.TECNICO, "Técnicos"))


def opens(request):
    """Un filtro de la matriz o el aviso de una acción llegan con su detalle ya desplegado."""
    if any(request.GET.get(name) for name in OPENING_PARAMS):
        return DETAIL
    return None


def _has_documents(procedure):
    from evaluon.journey.temas import s2_documentos
    return bool(s2_documentos.documents_of(procedure))


def _missing_matrix(procedure):
    return "Falta la matriz" if _has_documents(procedure) else "Falta el pliego"


def _heat(user, procedure):
    """La tabla de calor y la cifra: por tipo de requisito y oferta, cuántos requisitos cumple la
    propuesta vigente. Una oferta sin evaluar queda con las celdas vacías. `None` si ninguna
    oferta fue evaluada (la sección Evaluación es la dueña de esos resultados, P3)."""
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    evaluated = [status.evaluated for status in page.statuses]
    if not any(evaluated):
        return None
    rows, cumplen = [], 0
    for category, label in HEAT_TYPES:
        mine = [r for r in page.requirements if r.category == category]
        cells = []
        for offer, done in zip(page.offers, evaluated):
            if not done or not mine:
                cells.append(None)
                continue
            found = [page.cells[(offer.pk, r.pk)].effective_key for r in mine]
            total = sum(1 for key in found if key != "no_aplica")
            value = sum(1 for key in found if key == "cumple")
            cumplen += value
            cells.append(charts.HeatCell(value, total))
        rows.append(charts.HeatRow(label, cells))
    heat = charts.Heat(uid="s2-cumplimiento", title="Cumplimiento por tipo y oferta",
                       columns=[f"Of. {offer.number}" for offer in page.offers], rows=rows)
    total_cells = sum(c.total for row in rows for c in row.cells if c is not None)
    return (heat, cumplen, total_cells) if heat.has_data else None


def tiles(user, procedure, ctx):
    """«Requisitos», «Versiones de la matriz» y «Cumplimiento por tipo y oferta». Sin pliego
    dicen «Falta el pliego»; sin evaluación el de cumplimiento dice «Pendiente» y lleva a la
    propuesta (REQ-141): nunca una cifra que el sistema no tiene."""
    version = ctx["version"]
    evaluation = reverse("expedientes:evaluacion", args=[procedure.pk]) + "#d-s4-propuesta"
    found = _heat(user, procedure)
    if found is None:
        heat = Tile(key="cumplimiento", title="Cumplimiento por tipo y oferta", width=4,
                    href=evaluation, missing="Pendiente",
                    sub="Aparece cuando el sistema evalúa las ofertas")
    else:
        chart, cumplen, total = found
        heat = Tile(key="cumplimiento", title="Cumplimiento por tipo y oferta", width=4,
                    href=evaluation, big=cumplen, unit=f"de {total} cumplen",
                    sub="Propuesta del sistema; decide la Comisión", chart=chart)
    if version is None:
        missing = _missing_matrix(procedure)
        return [Tile(key="requisitos", title="Requisitos", detail=DETAIL, width=2,
                     missing=missing),
                Tile(key="versiones", title="Versiones de la matriz", detail=DETAIL,
                     missing=missing), heat]
    summary = ctx["summary"]
    changed = summary["changed"]
    changes = f"{changed} con cambios por circular" if changed else "sin cambios por circular"
    stack = charts.Stack(uid="s2-requisitos", title="Requisitos por tipo", parts=[
        charts.StackPart("Formales", summary["formal"], "ink"),
        charts.StackPart("Económicos", summary["economico"], "mute"),
        charts.StackPart("Técnicos", summary["tecnico"], "s3")])
    state = VERSION_LABELS[version.status]
    when = (f"validada el {_day(version.validated_at)}"
            if version.status == VersionStatus.VALIDATED else "todavía sin validar")
    count = len([v for v in ctx["versions"] if v["version"].status != VersionStatus.DISCARDED])
    return [
        Tile(key="requisitos", title="Requisitos", detail=DETAIL, width=2, big=ctx["total"],
             unit="requisitos", sub=f"Versión {version.number} · {changes}", chart=stack),
        Tile(key="versiones", title="Versiones de la matriz", detail=DETAIL,
             big=f"v{version.number}",
             sub=f"{state}, {when} · {count} {'versión' if count == 1 else 'versiones'}"),
        heat]
