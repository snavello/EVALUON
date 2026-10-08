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
from dataclasses import dataclass, field

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import TemaStatus
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
    options: list = field(default_factory=list)  # consecuencias elegibles (solo quien decide)
    technical: bool = False


def _day(moment):
    """La fecha en hora local (America/Argentina/Buenos_Aires), no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y}"


def latest_version(procedure):
    """La versión que cuenta: la última no descartada."""
    return (MatrixVersion.objects.filter(procedure=procedure)
            .exclude(status=VersionStatus.DISCARDED).order_by("-number").first())


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
    return TemaStatus(sources=(source,))


def _excerpt(text):
    text = " ".join(text.split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"


def _marks(row):
    marks = []
    requirement = row.requirement
    if row.added_by:
        marks.append(f"Agregado por {row.added_by.document_title}")
    if requirement.origin == RequirementOrigin.AGREGADO:
        marks.append("Agregado por una persona")
    if requirement.origin == RequirementOrigin.DEVUELTO:
        marks.append("Devuelto de las descartadas")
    if any(q.current or q.earlier for q in row.quotes):
        marks.append("Texto cambiado por circular")
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
        rows.append(Row(
            number=requirement.number, category=requirement.category,
            document=first.place.document_title if first else "Sin cita", text=text,
            place=first.place if first else None, consequence=_consequence_text(mine),
            marks=_marks(source), unconfirmed=requirement.state == RequirementState.PROPUESTO,
            changed=_changed(source), page_row=source, suggestions=_suggested(mine),
            options=([o for o in consequence_service.options(requirement)
                      if not o.undetermined] if with_options else []),
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
    return [row for row in page.pending if row.item.resolved_at is None]


def context(user, procedure, request):
    version = latest_version(procedure)
    base = {"version": None, "versions": _versions(procedure), "types": TYPE_OPTIONS,
            "filters": FILTERS, "propose_url": reverse("tenders:procedure", args=[procedure.pk]),
            "pid": procedure.pk, "aviso": acciones.unpack(request.GET.get("aviso"))}
    if version is None:
        return base
    page = matrix_page.matrix_page(user, version.pk, channel=Channel.SCREEN)
    is_evaluator = user.commission_role == CommissionRole.EVALUATOR
    decides = is_evaluator and version.status == VersionStatus.DRAFT
    rows = _rows(page, with_options=decides)
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
        "removed": page.removed, "segment_options": _segment_choices(page, version),
        "technical_rows": [r for r in rows if r.technical],
        "consequence_types": [(v, l) for v, l in ConsequenceType.choices
                              if v != ConsequenceType.NO_DETERMINADA.value],
        "blockers": counts, "blocked": bool(counts and counts["total"]),
        "condition": acciones.condition_text(counts, version.number) if counts else "",
        "can_open_new": page.can_open_new,
    }
