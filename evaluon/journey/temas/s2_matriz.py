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

import re
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
from evaluon.portal.models import PortalLine
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
    lead: str = ""  # de un renglón técnico: el comienzo de su primera cita (T-338)
    quote_views: list = field(default_factory=list)  # las citas que se ven al abrir la fila
    commons_count: int = 0  # cuántas cláusulas comunes tiene (se ven una vez, en el grupo)


@dataclass
class QuoteView:
    """Una cita de la fila tal como se muestra al abrirla. `text` es el de la cita, salvo en la
    tabla de renglones, donde es el encabezado y la fila del renglón (T-338)."""

    quote: object
    text: str


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
        text = lead = _excerpt(first.text) if first else "Sin cita"
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
            technical=requirement.category == RequirementClass.TECNICO, lead=lead,
            quote_views=[QuoteView(quote, quote.text) for quote in source.quotes]))
    return rows

# --- Renglones técnicos: su bien y sus cláusulas comunes (T-338) ------------------------------------

_TABLE_HEADER = re.compile(r"r[eé]ngl|[ií]tem", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*(\d+)\s+(\S.*?)\s*$")
_ROW_QUANTITY = re.compile(
    r"^(?P<what>.*?)[\s.]+(?P<qty>\d[\d.,]*)\s+(?P<unit>[^\W\d_][\w.]*)\.?$")


def table_rows(text):
    """`{número de renglón: su fila}` de una cita que es la tabla de renglones del pliego: un
    encabezado que nombra el renglón o el ítem y, debajo, una fila por renglón que empieza con su
    número. Una cita que no es una tabla de al menos dos renglones da `{}`."""
    lines = text.split("\n")
    if len(lines) < 3 or not _TABLE_HEADER.search(lines[0]):
        return {}
    rows = {}
    for line in lines[1:]:
        found = _TABLE_ROW.match(line)
        if found:
            rows.setdefault(int(found.group(1)), line.strip())
    return rows if len(rows) >= 2 else {}


def _readable(text):
    """El bien como se lee: lo que el pliego escribe todo en mayúsculas, en minúsculas, con el
    nombre y la marca después de un guion largo («Alimento para perros — Royal Canin»)."""
    text = text.strip().rstrip(".").strip()
    if not text.isupper():
        return text
    head, *rest = re.split(r"\s+-\s+", text)
    rest = [re.sub(r"^MARCA\s+", "", part).title() for part in rest]
    words = [w if any(c.isdigit() for c in w) else w.lower() for w in head.split()]
    head = " ".join(words)
    head = head[:1].upper() + head[1:]
    return f"{head} — {' '.join(rest)}" if rest else head


def _row_parts(line):
    """`(bien, cantidad y unidad)` de la fila de la tabla: las celdas, si vienen separadas con
    tabulaciones (`tenders/tables.py`), o lo que sigue al número."""
    if "\t" in line:
        cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
        return (cells[1] if len(cells) > 1 else ""), " ".join(cells[2:])
    rest = _TABLE_ROW.match(line).group(2)
    found = _ROW_QUANTITY.match(rest)
    if found:
        return found.group("what"), f"{found.group('qty')} {found.group('unit')}"
    return rest, ""


def _quantity_of(line):
    """La cantidad y la unidad de un renglón del procedimiento."""
    if line.quantity is None:
        return ""
    value = line.quantity
    shown = (f"{int(value)}" if value == value.to_integral_value()
             else f"{value.normalize():f}".replace(".", ","))
    return f"{shown} {line.unit}".strip()


def renglon_text(number, tables, lines, fallback):
    """El renglón por su bien: «Renglón 1 · Alimento … · 2700 kilos». Sale de su fila en la tabla de
    renglones citada (`tables`: los textos de las citas) y, si no está, del renglón del
    procedimiento (`lines`: `{número: PortalLine}`). Si no se sabe, `fallback`: el texto de
    siempre (no se inventa); con `fallback` en `None`, la falta se informa con `None`."""
    what, quantity = "", ""
    for text in tables:
        row = table_rows(text).get(number)
        if row is not None:
            what, quantity = _row_parts(row)
            if what:
                break
    if not what:
        line = lines.get(number)
        what, quantity = (line.description, _quantity_of(line)) if line is not None else ("", "")
    if not what.strip():
        return None if fallback is None else f"Renglón {number} · {fallback}"
    quantity = quantity.lower() if quantity.isupper() else quantity
    text = f"Renglón {number} · {_readable(what)}"
    return f"{text} · {quantity}" if quantity else text


def _key(quote):
    return (quote.segment_id, quote.text)


def _plain(quote):
    """Una cita que ninguna circular tocó: la única que se puede mostrar una vez para todos."""
    return not (quote.current or quote.earlier or quote.voided or quote.notes
                or quote.side_notes or quote.covered)


def technical_views(rows, procedure_id):
    """Arma lo que se ve al abrir los renglones técnicos (T-338): cada renglón con su bien como
    texto, la fila de la tabla de renglones que le toca (no la tabla entera) y un enlace a las
    cláusulas comunes, que se muestran una sola vez en el grupo. Es común una cita «Común a todos
    los renglones» y la que cita todo renglón, sin cambios de circular. Devuelve
    `{"clauses": [...], "tables": [...]}`: las citas comunes y las tablas, completas (P3: el literal
    no se pierde, solo se deja de repetir). Cambia las filas en el lugar."""
    technical = [row for row in rows if row.technical]
    common = {"clauses": [], "tables": []}
    if not technical:
        return common
    everywhere = set()
    if len(technical) > 1:
        everywhere = set.intersection(*({_key(q) for q in row.page_row.quotes}
                                        for row in technical))
    seen_clauses, seen_tables, lines = set(), set(), None
    for row in technical:
        items = row.page_row.requirement.items
        number = items[0] if len(items) == 1 else None
        tables = [q.text for q in row.page_row.quotes if table_rows(q.text)]
        views, mine = [], set()
        for quote in row.page_row.quotes:
            key = _key(quote)
            of_table = table_rows(quote.text)
            if of_table:
                trimmed = number in of_table and _plain(quote)
                text = quote.text
                if trimmed:
                    text = f"{quote.text.split(chr(10))[0]}\n{of_table[number]}"
                    if key not in seen_tables:
                        seen_tables.add(key)
                        common["tables"].append(quote)
                views.append(QuoteView(quote, text))
            elif _plain(quote) and (quote.scope == "general" or key in everywhere):
                mine.add(key)
                if key not in seen_clauses:
                    seen_clauses.add(key)
                    common["clauses"].append(quote)
            else:
                views.append(QuoteView(quote, quote.text))
        row.quote_views, row.commons_count = views, len(mine)
        if number is not None:
            text = renglon_text(number, tables, {}, None)
            if text is None:
                if lines is None:
                    lines = memo.once(("s2_lines", procedure_id), lambda: {
                        line.number: line
                        for line in PortalLine.objects.filter(procedure_id=procedure_id)})
                text = renglon_text(number, tables, lines, row.lead)
            row.text = text
    return common


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


def _groups(rows, common=None):
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
        shared = common if (category == RequirementClass.TECNICO and common
                            and (common["clauses"] or common["tables"])) else None
        groups.append({"category": category, "label": TYPE_LABELS[category],
                       "count": len(mine), "unconfirmed": sum(r.unconfirmed for r in mine),
                       "subgroups": sub, "common": shared})
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
    common = technical_views(rows, procedure.pk)
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
        **base, "version": version, "draft": page.draft, "groups": _groups(chosen, common),
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
    """La tabla de calor y las cuentas: por tipo de requisito y oferta, cuántos requisitos cumple la
    propuesta vigente. Una oferta sin evaluar queda con las celdas vacías. Las cuentas (cumple, no
    cumple, no determinado, sin resultado) son las de la sección Evaluación (`figures_of`), para
    que las dos pantallas digan lo mismo. `None` si ninguna oferta fue evaluada (la sección
    Evaluación es la dueña de esos resultados, P3)."""
    from evaluon.journey.temas import s4_propuesta
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    figures = s4_propuesta.figures_of(page)
    if figures is None:
        return None
    evaluated = [status.evaluated for status in page.statuses]
    rows = []
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
            cells.append(charts.HeatCell(value, total))
        rows.append(charts.HeatRow(label, cells))
    heat = charts.Heat(uid="s2-cumplimiento", title="Cumplimiento por tipo y oferta",
                       columns=[f"Of. {offer.number}" for offer in page.offers], rows=rows)
    if not heat.has_data:
        return None
    waiting = sum(1 for status in page.statuses if status.evaluated
                  for r in page.requirements if r.category == RequirementClass.TECNICO
                  if s4_propuesta._bucket(page.cells[(status.offer.pk, r.pk)]) == "pe")
    counts = Compliance(
        ok=sum(o.ok for o in figures.offers), no=figures.no, nd=figures.nd,
        pe=sum(o.pe for o in figures.offers), na=figures.na, waiting=waiting,
        requirements=figures.requirements, offers=len(figures.offers))
    return heat, counts


@dataclass(frozen=True)
class Compliance:
    """Las cuentas del mosaico de cumplimiento: pares requisito-oferta por categoría, las de la
    sección Evaluación. `ok + no + nd + pe` es el total; `na` (no aplica) no se cuenta. `waiting`
    son los sin resultado que son técnicos y esperan el informe técnico del área."""

    ok: int
    no: int
    nd: int
    pe: int
    na: int
    waiting: int
    requirements: int
    offers: int

    @property
    def total(self):
        return self.ok + self.no + self.nd + self.pe

    def line(self):
        """La línea de apoyo: de cuántos se habla y cuántos hay en cada categoría."""
        base = f"De {self.total}"
        if not self.na:
            base += (f" ({self.requirements} {'requisito' if self.requirements == 1 else 'requisitos'}"
                     f" × {self.offers} {'oferta' if self.offers == 1 else 'ofertas'})")
        parts = [f"{self.no} no cumple", f"{self.nd} no {'determinado' if self.nd == 1 else 'determinados'}",
                 f"{self.pe} sin resultado"]
        if self.pe and self.waiting:
            parts[-1] += (" (técnicos: esperan el informe técnico del área)"
                          if self.waiting == self.pe else
                          f" ({self.waiting} técnicos esperan el informe técnico del área)")
        text = f"{base}: " + " · ".join(parts) + "."
        if self.na:
            text += (f" {self.na} no aplica y no se cuenta." if self.na == 1
                     else f" {self.na} no aplican y no se cuentan.")
        return text + " Propuesta del sistema; decide la Comisión."


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
        chart, counts = found
        heat = Tile(key="cumplimiento", title="Cumplimiento por tipo y oferta", width=4,
                    href=evaluation, big=counts.ok, unit="cumplen", sub=counts.line(),
                    chart=chart)
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
    state = (f"Validada el {_day(version.validated_at)}"
             if version.status == VersionStatus.VALIDATED else VERSION_LABELS[version.status])
    count = len([v for v in ctx["versions"] if v["version"].status != VersionStatus.DISCARDED])
    return [
        Tile(key="requisitos", title="Requisitos", detail=DETAIL, width=2, big=ctx["total"],
             unit="requisitos", sub=f"Versión {version.number} · {changes}", chart=stack),
        Tile(key="versiones", title="Versiones de la matriz", detail=DETAIL,
             big=f"v{version.number}",
             sub=f"{state} · {count} {'versión' if count == 1 else 'versiones'}"),
        heat]
