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

Solo lee: no decide nada (P3). Lo que el sistema no tiene se dice, nunca se inventa (REQ-141).
"""

from dataclasses import dataclass, field

from django.urls import reverse

from evaluon.accounts import photos
from evaluon.assessment.services import discards as discard_service
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.stages import base as stage_base
from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Detail, Tile
from evaluon.journey.temas import s1_datos
from evaluon.journey.window import window_for

# Dónde guarda la vista el contexto del primer panel, para que los mosaicos lo lean.
KEY = "ingreso"

DETAIL_AVANCE = "d-s1-avance"
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


def file_number(procedure):
    """El expediente cargado desde el Portal o desde el pliego, o `None` si no se cargó."""
    data = s1_datos._portal_data(procedure)
    return (data.file_number or None) if data is not None else None


def _plural(count, one, many):
    return one if count == 1 else many


def numbers(procedure, overview, avance, extra_before=(), extra_after=()):
    """Los datos principales del encabezado, en el orden de la maqueta: ofertas, lo que agregue
    T-322 (la más baja, la más alta), avance, lo que agregue T-322 (vencimiento) y pendientes."""
    count = procedure.offers.count()
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
        "numeros": numbers(procedure, overview, avance),
        "window": window_for(procedure),
        "window_url": reverse("expedientes:ventana", args=[procedure.pk]),
        "portal_link": procedure.portal_links.order_by("-pk").first(),
    }
    if overview is not None:
        found["pending_items"] = [(s, i) for s in overview.sections for i in s.pending_items]
        found["suggestion_items"] = [(s, i) for s in overview.sections
                                     for i in s.suggestion_items]
    return found


def tiles(section, user, procedure, contexts):
    """Los mosaicos propios del primer panel: el avance por sección y los de la evaluación. Los
    temas de la sección 1 suman los suyos después."""
    own = (contexts or {}).get(KEY) or {}
    found = []
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
    found = []
    if own.get("avance") is not None:
        found.append(Detail(DETAIL_AVANCE, "Avance por sección", "journey/_ingreso_avance.html",
                            {"avance": own["avance"]}))
    return found
