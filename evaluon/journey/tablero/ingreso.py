"""El primer panel de la sección Procedimiento (REQ-128, REQ-129, REQ-132, REQ-135, REQ-138,
REQ-141; plan 017, «Primer panel» y «De dónde sale cada dato»; ADR-0077; T-321).

Es el ingreso de un procedimiento: la foto de fondo, sus datos principales, el pendiente general,
el avance y los mosaicos que llevan a otras secciones. La normativa no aparece acá (D-3 del
plan): se consulta en su sección. Lo arma `sections/s1.py` con estas funciones.

- **Datos principales**: objeto, tipo y número, expediente (`PortalProcedureData.file_number`,
  «Falta» si no se cargó), fecha de autorización, cantidad de ofertas y de pendientes.
- **Avance** (ADR-0077, avance A): «N de 5 secciones listas». Sin porcentajes: los pesos de cada
  pendiente no existen y no se inventan (REQ-141).
- **Mosaicos de otra sección** (resultado por oferta, descartes propuestos, preguntas): enlazan
  a `evaluacion/#d-s4-…` y no repiten el detalle (D-4 del plan). Sin evaluación dicen «Pendiente».

- **Orden económico** (T-322, REQ-130): la más alta y la más baja como indicadores y el mosaico
  con su detalle, de `economico.py`. Sin ofertas: el día de la apertura y «Pendiente».
- **Plazos** (T-322, REQ-131): apertura, hoy, vencimiento del mantenimiento y dictamen. El
  vencimiento se calcula al vuelo (ADR-0077, alternativa A): se lee `mantenimiento_oferta` de la
  última página del proceso guardada del Portal (`parse_page`) y, si es en días corridos desde la
  apertura, se suma a la apertura del cronograma. En días hábiles, o contado desde otro hecho, se
  dice el plazo y «Falta el calendario»: no hay calendario de feriados. Se memoiza por pedido.

Solo lee: no decide nada (P3). Lo que el sistema no tiene se dice, nunca se inventa (REQ-141).
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from evaluon.accounts import photos
from evaluon.assessment.services import discards as discard_service
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.stages import base as stage_base
from evaluon.journey.tablero import charts, economico
from evaluon.journey.tablero.tiles import Detail, Tile
from evaluon.journey.temas import s1_datos
from evaluon.journey.window import window_for
from evaluon.portal.models import PageKind, PortalPage
from evaluon.portal.parsing.pagina import parse_page

# Dónde guarda la vista el contexto del primer panel, para que los mosaicos lo lean.
KEY = "ingreso"

DETAIL_AVANCE = "d-s1-avance"
DETAIL_ORDER = "d-s1-orden"
DETAIL_TERMS = "d-s1-plazos"
SECTIONS_TOTAL = 5
MISSING_SHOWN = 3  # faltantes que se nombran por sección en el detalle del avance


@dataclass(frozen=True)
class Number:
    """Un dato principal del encabezado. Sin `value`, el encabezado dice `missing` («Falta …»,
    «Pendiente»): nunca una cifra de relleno (REQ-141)."""

    key: str
    label: str
    value: str = ""
    missing: str = ""
    highlight: bool = False  # lima: solo la cantidad de pendientes (REQ-133)
    tag: str = ""  # una etiqueta aparte junto al rótulo, p. ej. «Pendiente»


@dataclass
class AvanceRow:
    label: str
    url: str
    icon: str
    state_label: str
    pending: int
    missing: list = field(default_factory=list)
    more: int = 0  # faltantes que no entran en el renglón


@dataclass
class Avance:
    """Cuántas de las cinco secciones están listas y el estado de cada una."""

    done: int
    total: int
    pending: int
    rows: list

    @property
    def text(self):
        return f"{self.done} de {self.total} secciones listas"


def avance_of(overview):
    """El avance a partir de las cinco secciones del procedimiento."""
    rows = []
    for section in overview.sections:
        found = [m.text for m in (section.tema_missing or section.missing)]
        rows.append(AvanceRow(
            label=section.label, url=section.url, icon=section.icon,
            state_label=section.state_label, pending=section.pending,
            missing=found[:MISSING_SHOWN], more=max(len(found) - MISSING_SHOWN, 0)))
    done = sum(1 for s in overview.sections if s.state == stage_base.LISTA)
    return Avance(done=done, total=len(overview.sections), pending=overview.pending, rows=rows)


# --- Datos principales ---------------------------------------------------------------------------


def portal_data(procedure):
    """Los datos del procedimiento del Portal (expediente, cronograma), leídos una vez por pedido."""
    return memo.once(("s1", "datos", procedure.pk), lambda: s1_datos._portal_data(procedure))


def offers_of(user, procedure):
    """Las ofertas del procedimiento por número: las de la matriz que ya se leyó en este pedido
    (una consulta menos)."""
    return memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN).offers


def file_number(procedure):
    """El expediente cargado desde el Portal o desde el pliego, o `None` si no se cargó."""
    data = portal_data(procedure)
    return (data.file_number or None) if data is not None else None


def _plural(count, one, many):
    return one if count == 1 else many


def numbers(offers, overview, avance, extra_before=(), extra_after=()):
    """Los datos principales del encabezado, en el orden de la maqueta: ofertas, lo que agregue
    T-322 (la más baja, la más alta), avance, lo que agregue T-322 (vencimiento) y pendientes."""
    count = len(offers)
    found = [Number("ofertas", _plural(count, "oferta", "ofertas"), str(count))]
    found += list(extra_before)
    if avance is not None:
        found.append(Number("avance", f"de {avance.total} secciones listas", str(avance.done)))
    found += list(extra_after)
    if overview is not None:
        found.append(Number("pendientes", _plural(overview.pending, "pendiente", "pendientes"),
                            str(overview.pending), highlight=True))
    return found


# --- Mosaicos de otra sección ---------------------------------------------------------------------


@dataclass
class Evaluation:
    """Lo que la evaluación ya tiene para el primer panel: resultado por oferta, descartes
    propuestos sin decidir y preguntas abiertas. `evaluated` es falso si ninguna oferta se evaluó."""

    evaluated: bool = False
    donuts: list = field(default_factory=list)
    discards: int = 0
    questions: int = 0


def evaluation(user, procedure):
    """La evaluación del procedimiento, calculada una vez por pedido (`memo`)."""
    def build():
        page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
        done = [s for s in page.statuses if s.evaluated]
        if not done:
            return Evaluation()
        total = len(page.requirements)
        donuts = []
        for status in done:
            outcomes = status.by_outcome
            ok = outcomes.get("cumple", 0)
            no = outcomes.get("no_cumple", 0) + outcomes.get("sin_documento", 0)
            nd = outcomes.get("no_determinado", 0)
            donuts.append(charts.DonutItem(
                f"Oferta {status.offer.number}", ok=ok, no=no, nd=nd,
                pe=max(total - ok - no - nd - outcomes.get("no_aplica", 0), 0)))
        proposed = sum(1 for unit in discard_service.units(page)
                       if unit.state == discard_service.PROPOSED)
        return Evaluation(evaluated=True, donuts=donuts, discards=proposed,
                          questions=sum(len(s.open_questions) for s in page.statuses))
    return memo.once(("s1", "evaluacion", getattr(user, "pk", None), procedure.pk), build)


def _evaluation_url(procedure, detail):
    return reverse("expedientes:evaluacion", args=[procedure.pk]) + f"#{detail}"


def evaluation_tiles(user, procedure):
    """«Resultado por oferta», «Descartes propuestos» y «Preguntas a la Comisión»: enlazan a la
    sección Evaluación; sin evaluación dicen «Pendiente» y no muestran ni cifra ni gráfico."""
    found = evaluation(user, procedure)
    chart = charts.Donuts(uid="resultado-ingreso", items=found.donuts,
                          title="Resultado de cada oferta por requisito")
    resultado = Tile(
        key="resultado", title="Resultado por oferta", width=2,
        href=_evaluation_url(procedure, "d-s4-propuesta"),
        big=len(found.donuts) if found.evaluated and chart.has_data else None,
        unit=_plural(len(found.donuts), "oferta evaluada", "ofertas evaluadas"),
        sub="Requisitos que cumple cada una, según la propuesta del sistema",
        chart=chart if chart.has_data else None, missing="Pendiente")
    descartes = Tile(
        key="descartes", title="Descartes propuestos",
        href=_evaluation_url(procedure, "d-s4-descartes"),
        big=found.discards if found.evaluated else None, sub="Esperan la decisión de la Comisión",
        missing="Pendiente")
    preguntas = Tile(
        key="preguntas", title="Preguntas a la Comisión",
        href=_evaluation_url(procedure, "d-s4-preguntas"),
        big=found.questions if found.evaluated else None, sub="Sin responder", missing="Pendiente")
    return [resultado, descartes, preguntas]


# --- Orden económico: indicadores y mosaico (T-322, REQ-130) --------------------------------------


def today():
    """El día de hoy; una función aparte para que las pruebas lo fijen."""
    return timezone.localdate()


def economic(user, procedure):
    """El orden económico, calculado una sola vez por pedido y compartido por los indicadores, el
    mosaico y el detalle (aviso de T-314)."""
    return memo.once(
        ("s1", "economico", procedure.pk),
        lambda: economico.economic_view(procedure, offers_of(user, procedure), uid="orden"))


def _compact(row):
    """El monto para el encabezado: en millones desde un millón («$ 15,56 M»), completo si no."""
    if row.amount >= 1_000_000:
        symbol = row.amount_text.rsplit(" ", 1)[0] if " " in row.amount_text else ""
        millions = f"{row.amount / 1_000_000:,.2f}".replace(",", "X").replace(".", ",") \
            .replace("X", ".")
        return f"{symbol} {millions} M".strip()
    return row.amount_text


def economic_numbers(view):
    """Los indicadores del encabezado: la más baja y la más alta. Sin ofertas con total, el
    encabezado dice el día de la apertura con su «Pendiente» (o «Falta» si no hay cronograma); con
    ofertas sin total, «Falta el total»; con un solo total, la más alta dice que falta otra."""
    if view.state == economico.STATE_PENDING:
        if view.opening_day:
            return [Number("apertura", "apertura de ofertas", view.opening_day[:5],
                           tag=view.missing)]
        return [Number("apertura", "fecha de apertura de ofertas", missing="Falta")]
    found = []
    for key, row, label in (("baja", view.low, "la más baja"), ("alta", view.high, "la más alta")):
        if row is not None:
            found.append(Number(key, f"{label}: {row.name}", _compact(row)))
        elif view.state != economico.STATE_ORDERED:
            found.append(Number(key, label, missing=view.missing))
        elif view.warning:
            found.append(Number(key, label, missing="No se comparan: monedas distintas"))
        else:
            found.append(Number(key, label, missing="Falta otra oferta con un total distinto"))
    return found


def orden_tile(view):
    """«Orden económico»: el gráfico y la diferencia; sin total, lo que falta (REQ-141)."""
    if view.state != economico.STATE_ORDERED:
        sub = (f"Apertura de ofertas: {view.opening_day}"
               if view.state == economico.STATE_PENDING and view.opening_day else "")
        return Tile(key="orden", title="Orden económico", detail=DETAIL_ORDER, width=2,
                    missing=view.missing, sub=sub)
    if view.warning:
        sub = view.warning
    elif view.high is not None:
        sub = (f"Entre la más baja, {view.low.name}, y la más alta, {view.high.name}, hay "
               f"{view.high.diff_text.lstrip('+')} de diferencia.")
    else:
        sub = "Todos los totales cargados son iguales."
    return Tile(key="orden", title="Orden económico", detail=DETAIL_ORDER, width=2,
                big=view.count, unit="ofertas ordenadas", sub=sub,
                chart=view.chart if view.chart.has_data else None)


# --- Plazo de mantenimiento de las ofertas (T-322, REQ-131; ADR-0077, vencimiento A) ---------------

_TERM = re.compile(r"^\s*(\d+)\s*d[ií]as?\s+(corridos?|h[aá]biles?)\b\s*(.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class Term:
    """El plazo como lo escribe el Portal: «60 Días corridos Acto de apertura»."""

    days: int
    kind: str  # «corridos» o «hábiles»
    origin: str  # «Acto de apertura», «Notificación de …»
    from_opening: bool

    @property
    def text(self):
        unit = "día" if self.days == 1 else "días"
        kind = self.kind[:-1] if self.days == 1 else self.kind
        return f"{self.days} {unit} {kind}"


def parse_term(text):
    """El plazo escrito por el Portal, o `None` si no trae días y tipo (no se inventa)."""
    found = _TERM.match(text or "")
    if not found:
        return None
    days, kind, origin = found.groups()
    kind = "hábiles" if kind.lower().startswith("h") else "corridos"
    return Term(int(days), kind, origin.strip(), "apertura" in origin.lower())


@dataclass(frozen=True)
class Maintenance:
    """El mantenimiento de las ofertas. `state`: `computed` (hay fecha de vencimiento),
    `calendar` (se conoce el plazo pero no se puede contar: faltan feriados o su origen es otro
    hecho) o `missing` (no hay plazo o no hay apertura)."""

    state: str
    due: date | None = None
    days_left: int | None = None
    term: str = ""  # «30 días hábiles desde la apertura»
    note: str = ""  # qué falta
    source: str = ""  # «Fuente: Portal, tomado el 20/10/2026»


def opening_moment(procedure):
    """La fecha de la apertura de ofertas según el cronograma del Portal, o `None`."""
    found = s1_datos._opening(s1_datos._schedule(portal_data(procedure)))
    if found is None:
        return None
    moment, _ = s1_datos._stamp(found[1])
    return moment.date() if moment else None


def _read_term(procedure):
    """El plazo de la última página del proceso guardada y el día en que se tomó; `(None, None)`
    si no hay página."""
    page = (PortalPage.objects.filter(link__procedure=procedure, kind=PageKind.PROCESO)
            .order_by("-fetched_at", "-pk").only("fetched_at", "content").first())
    if page is None:
        return None, None
    raw = parse_page(bytes(page.content)).data.get("mantenimiento_oferta")
    return raw, timezone.localtime(page.fetched_at).date()


def maintenance(procedure):
    """El mantenimiento de las ofertas, leído una sola vez por pedido."""
    return memo.once(("s1", "mantenimiento", procedure.pk), lambda: _maintenance(procedure))


def _maintenance(procedure):
    raw, taken = _read_term(procedure)
    if taken is None:
        return Maintenance("missing", note="Falta la página del proceso del Portal")
    source = f"Fuente: Portal, tomado el {taken:%d/%m/%Y}"
    if not raw:
        return Maintenance("missing", note="El Portal no informa el plazo de mantenimiento",
                           source=source)
    term = parse_term(raw)
    if term is None:
        return Maintenance("missing", note=f"No se entiende el plazo del Portal: «{raw}»",
                           source=source)
    start = "la apertura" if term.from_opening else (term.origin or "otro hecho")
    text = f"{term.text} desde {start}"
    if term.kind != "corridos" or not term.from_opening:
        return Maintenance("calendar", term=text, note="Falta el calendario", source=source)
    opening = opening_moment(procedure)
    if opening is None:
        return Maintenance("missing", term=text, note="Falta la apertura en el cronograma",
                           source=source)
    due = opening + timedelta(days=term.days)
    return Maintenance("computed", due=due, days_left=(due - today()).days, term=text,
                       source=source)


def vence_number(found):
    """El dato del encabezado: días hasta el vencimiento del mantenimiento, o lo que falta."""
    if found.state == "computed":
        due = _short_date(found.due)
        if found.days_left > 0:
            return Number("vence", f"vence el mantenimiento ({due})", _days(found.days_left))
        if found.days_left == 0:
            return Number("vence", f"vence hoy el mantenimiento ({due})", "Hoy")
        return Number("vence", f"el mantenimiento venció el {due}", "Venció")
    if found.state == "calendar":
        return Number("vence", f"mantenimiento: {found.term}", missing=found.note)
    return Number("vence", "vencimiento del mantenimiento", missing="Falta")


def _days(count):
    return f"{count} {'día' if count == 1 else 'días'}"


def _short_date(value):
    """«21/11»; con otro año que el de hoy, «21/11/2027»."""
    return f"{value:%d/%m}" if value.year == today().year else f"{value:%d/%m/%Y}"


def _state_of(day):
    now = today()
    return "now" if day == now else "past" if day < now else "future"


def _distance(day):
    delta = (day - today()).days
    if delta > 0:
        return "falta 1 día" if delta == 1 else f"faltan {delta} días"
    if delta == 0:
        return "es hoy"
    return f"hace {-delta} {'día' if delta == -1 else 'días'}"


@dataclass(frozen=True)
class Terms:
    """Un hito de los plazos importantes."""

    key: str
    label: str  # «Vence el mantenimiento de las ofertas»
    sentence: str  # lo mismo, en minúscula, para «21/11 · vence el mantenimiento …»
    day: date | None
    date_text: str  # «21/11»; «Pendiente» o «Falta» si no hay fecha
    state: str  # past | now | future | pending
    note: str = ""


@dataclass
class Plazos:
    events: list
    maintenance: Maintenance
    chart: charts.Timeline


def dictamen_day(procedure):
    """La fecha del dictamen: la del documento subido o la que publicó el Portal; `None` si no
    hay (el sistema no tiene una fecha prevista)."""
    from evaluon.journey.temas import s4_dictamen

    dates = [d.issued_on for d in s4_dictamen.uploaded_dictamenes(procedure) if d.issued_on]
    if dates:
        return max(dates)
    item = s4_dictamen.portal_dictamen(procedure)
    if item is not None:
        try:
            return date.fromisoformat(item.payload.get("fecha") or "")
        except ValueError:
            return None
    return None


def plazos(procedure):
    """Los plazos importantes del procedimiento, una vez por pedido."""
    return memo.once(("s1", "plazos", procedure.pk), lambda: _plazos(procedure))


def _dated(key, label, sentence, day, note=""):
    state = _state_of(day)
    return Terms(key, label, sentence, day, _short_date(day), state,
                 note or ("" if state == "now" else _distance(day)))


def _plazos(procedure):
    found = maintenance(procedure)
    opening, dictamen, now = opening_moment(procedure), dictamen_day(procedure), today()
    events = [
        _dated("apertura", "Apertura de ofertas", "apertura de ofertas", opening)
        if opening else Terms("apertura", "Apertura de ofertas", "apertura de ofertas", None,
                              "Falta", "pending", "Falta la apertura en el cronograma"),
        Terms("hoy", "Hoy", "hoy", now, _short_date(now), "now"),
    ]
    if found.state == "computed":
        note = ("venció " + _distance(found.due)) if found.days_left < 0 else _distance(found.due)
        events.append(_dated("vence", "Vence el mantenimiento de las ofertas",
                             "vence el mantenimiento de las ofertas", found.due, note))
    else:
        events.append(Terms("vence", "Vence el mantenimiento de las ofertas",
                            "vence el mantenimiento de las ofertas", None, "Falta", "pending",
                            " · ".join(p for p in (found.term, found.note) if p)))
    events.append(
        _dated("dictamen", "Dictamen de la Comisión", "dictamen de la Comisión", dictamen)
        if dictamen else Terms("dictamen", "Dictamen de la Comisión", "dictamen de la Comisión",
                               None, "Pendiente", "pending"))
    # En orden de fecha (a igual fecha, el orden de arriba); lo que no tiene fecha, al final.
    order = {e.key: n for n, e in enumerate(events)}
    events.sort(key=lambda e: (e.day is None, e.day or date.max, order[e.key]))
    chart = charts.Timeline(uid="plazos-grafico", title="Plazos importantes", events=[
        charts.TimelineEvent(e.label, e.date_text, e.state) for e in events])
    return Plazos(events=events, maintenance=found, chart=chart)


def plazos_tile(found):
    """«Plazos importantes»: los días hasta el vencimiento, con la línea de tiempo. Sin
    vencimiento, la apertura; sin apertura, lo que falta (REQ-141)."""
    due = found.maintenance
    if due.state == "computed":
        left = due.days_left
        if left >= 0:
            sub = f"{_short_date(due.due)} · vence el mantenimiento de las ofertas"
            big, unit = left, "día" if left == 1 else "días"
        else:
            # Ya venció: la cifra grande no puede leerse como «faltan» (T-336).
            big, unit = "Venció", ""
            sub = (f"{_distance(due.due)} · el {_short_date(due.due)} · "
                   "venció el mantenimiento de las ofertas")
    else:
        apertura = next(e for e in found.events if e.key == "apertura")
        if apertura.day is None:
            return Tile(key="plazos", title="Plazos importantes", detail=DETAIL_TERMS, width=2,
                        missing="Falta el cronograma", sub=apertura.note)
        big, unit, sub = apertura.date_text, "apertura", due.note or "Falta el vencimiento"
    chart = found.chart if found.chart.has_data else None
    return Tile(key="plazos", title="Plazos importantes", detail=DETAIL_TERMS, width=2,
                big=big, unit=unit, sub=sub, chart=chart)


# --- Lo que usa s1.py ----------------------------------------------------------------------------


def context(section, user, procedure, request=None, overview=None):
    """El contexto del encabezado: la foto, los datos principales, el pendiente general, el
    avance y la ventana del proceso. `overview` son las cinco secciones (la vista ya las tiene)."""
    avance = avance_of(overview) if overview is not None else None
    found = {
        "foto": photos.pick_for(request) if request is not None
        else photos.Picked(photo_id=None, label=photos.HOUSE_LABEL),
        "expediente": file_number(procedure),
        "avance": avance,
        "numeros": numbers(offers_of(user, procedure), overview, avance,
                           extra_before=economic_numbers(economic(user, procedure)),
                           extra_after=[vence_number(maintenance(procedure))]),
        "window": memo.once(("window", procedure.pk), lambda: window_for(procedure)),
        "window_url": reverse("expedientes:ventana", args=[procedure.pk]),
    }
    if overview is not None:
        found["pending_total"] = overview.pending
        found["suggestion_total"] = overview.suggestions
        found["pending_items"] = [(s, i) for s in overview.sections for i in s.pending_items]
        found["suggestion_items"] = [(s, i) for s in overview.sections
                                     for i in s.suggestion_items]
    return found


def tiles(section, user, procedure, contexts):
    """Los mosaicos propios del primer panel, en el orden de la maqueta: orden económico, plazos,
    avance por sección y los de la evaluación. Los temas de la sección 1 suman los suyos
    después."""
    own = (contexts or {}).get(KEY) or {}
    found = [orden_tile(economic(user, procedure)), plazos_tile(plazos(procedure))]
    if own.get("avance") is not None:
        avance = own["avance"]
        found.append(Tile(
            key="avance", title="Avance por sección", detail=DETAIL_AVANCE, width=2,
            big=avance.done, unit=f"de {avance.total} secciones listas",
            sub=f"{avance.pending} {_plural(avance.pending, 'pendiente', 'pendientes')} "
                "de decidir en total"))
    return found + evaluation_tiles(user, procedure)


def details(section, user, procedure, contexts):
    own = (contexts or {}).get(KEY) or {}
    found = [Detail(DETAIL_ORDER, "Orden económico", "journey/_economico.html",
                    {"orden": economic(user, procedure)}),
             Detail(DETAIL_TERMS, "Plazos importantes", "journey/_ingreso_plazos.html",
                    {"plazos": plazos(procedure)})]
    if own.get("avance") is not None:
        found.append(Detail(DETAIL_AVANCE, "Avance por sección", "journey/_ingreso_avance.html",
                            {"avance": own["avance"]}))
    return found
