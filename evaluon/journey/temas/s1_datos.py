"""Tema s1_datos: los datos del procedimiento con el origen de cada uno (REQ-078, REQ-097;
plan 014, T-194).

Muestra número, expediente, tipo, objeto, fecha de autorización y el régimen que esa fecha
fija (Disp. 247/2022 o 297/03, calculado con `regime_for`), los renglones con su cantidad, el
cronograma con la apertura, las garantías y las ofertas del acta. Cada dato dice de dónde salió:
el Portal (con la hora de la exploración), un archivo subido (con su nombre) o la carga a mano
(con quién y cuándo). Solo lee (P3): no corrige ni aprueba nada; la carga está en los temas
`s1_portal` y `s1_pliego`. Las fechas se muestran en hora local.
"""

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from evaluon.journey.sections.base import Missing, TemaStatus
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    LoadedModel,
    PortalItem,
    PortalLine,
    PortalOfferData,
    PortalProcedureData,
)
from evaluon.tenders.services import procedures

KEY = "s1_datos"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_datos.html"
urlpatterns = []

OPENING_WORDS = ("apertura",)
NOT_STATED = "No consta"


@dataclass(frozen=True)
class Origin:
    """De dónde salió un dato: `kind` es «Portal», «Archivo» o «A mano»."""

    kind: str
    detail: str = ""
    url: str = ""


def _moment(value):
    """Fecha y hora en hora local, no la de la base en UTC."""
    return f"{timezone.localtime(value):%d/%m %H:%M}"


def _portal_origin(item):
    link = item.proposal.link
    return Origin("Portal", _moment(item.proposal.created_at),
                  reverse("portal:proposal", args=[link.pk]))


def _origin(item=None, document=None):
    if item is not None:
        return _portal_origin(item)
    if document is not None:
        return Origin("Archivo", document.file_name)
    return None


def _procedure_origin(procedure, data):
    """El origen de número, tipo, objeto y fecha: el ítem del Portal que creó el procedimiento,
    el pliego del que salieron o, si no hay ninguno, la carga a mano."""
    item = (PortalItem.objects.filter(
        kind=ItemKind.PROCEDIMIENTO, state=ItemState.CARGADO,
        loaded_model=LoadedModel.PROCEDURE, loaded_id=procedure.pk)
        .select_related("proposal__link").order_by("-pk").first())
    if item is not None:
        return _portal_origin(item)
    if data is not None and data.document_id:
        return Origin("Archivo", data.document.file_name)
    who = procedure.created_by.username if procedure.created_by_id else ""
    return Origin("A mano", " · ".join(p for p in (who, _moment(procedure.created_at)) if p))


def _portal_data(procedure):
    return (PortalProcedureData.objects.filter(procedure=procedure)
            .select_related("item__proposal__link", "document").first())


def _lines(procedure):
    return list(PortalLine.objects.filter(procedure=procedure)
                .select_related("item__proposal__link", "document").order_by("number"))


def _number(value):
    """Un decimal en formato argentino: sin ceros de más, punto de miles y coma decimal."""
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    whole, _, decimals = f"{value.normalize():f}".partition(".")
    return f"{int(whole):,}".replace(",", ".") + "," + decimals


def _quantity(line):
    if line.quantity is None:
        return NOT_STATED
    return f"{_number(line.quantity)} {line.unit}".strip()


def _money(value):
    whole = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {whole}"


def _schedule(data):
    """El cronograma como lista de `(concepto, valor)`; acepta el dict del Portal o una lista."""
    raw = data.schedule if data is not None else None
    if isinstance(raw, dict):
        return [(str(k), str(v)) for k, v in raw.items()]
    if isinstance(raw, list):
        return [(str(r.get("concepto", "")), str(r.get("valor", "")))
                if isinstance(r, dict) else (str(r), "") for r in raw]
    return []


def _opening(schedule):
    return next(((k, v) for k, v in schedule
                 if any(word in k.lower() for word in OPENING_WORDS)), None)


def _guarantees(data):
    raw = data.guarantees if data is not None else None
    if not isinstance(raw, list):
        return []
    return [r if isinstance(r, str) else " · ".join(str(v) for v in r.values() if v)
            for r in raw]


def _offers(procedure):
    rows = []
    qs = (PortalOfferData.objects.filter(offer__procedure=procedure)
          .select_related("offer", "item__proposal__link", "document")
          .prefetch_related("guarantees").order_by("offer__number"))
    for data in qs:
        guarantees = [" · ".join(part for part in (
            g.guarantee_type, g.guarantee_form,
            _money(g.amount) if g.amount is not None else "") if part)
            for g in data.guarantees.all()]
        rows.append({
            "number": data.offer.number, "bidder": data.offer.bidder, "cuit": data.cuit,
            "total": _money(data.total) if data.total is not None else NOT_STATED,
            "guarantees": guarantees, "origin": _origin(data.item, data.document),
        })
    return rows


def _portal_link_url(procedure):
    """Dónde tomar los datos del Portal: el proceso seguido o, si no hay, el alta de enlaces.
    Es la pantalla actual de la 012 hasta que exista el explorador de la sección (T-195)."""
    link = procedure.portal_links.order_by("-pk").first()
    return reverse("portal:proposal", args=[link.pk]) if link else reverse("portal:links")


def status(user, procedure):
    """Lo que hay, de dónde vino y lo que falta. No suma pendientes: nada espera decisión acá."""
    data = _portal_data(procedure)
    schedule = _schedule(data)
    take = _portal_link_url(procedure)
    missing = []
    if data is None:
        missing.append(Missing("Falta el expediente, el cronograma y las garantías", take,
                               "Tomar del Portal"))
    else:
        if not data.file_number:
            missing.append(Missing("Falta el número de expediente", take, "Tomar del Portal"))
        if _opening(schedule) is None:
            missing.append(Missing("Falta la fecha de apertura de ofertas", take,
                                   "Tomar del Portal"))
    if not PortalLine.objects.filter(procedure=procedure).exists():
        missing.append(Missing("Faltan los renglones con su cantidad", take, "Tomar del Portal"))
    origin = _procedure_origin(procedure, data)
    where = origin.kind + (f", {origin.detail}" if origin.detail else "")
    return TemaStatus(missing=tuple(missing),
                      sources=(f"Datos del procedimiento: {where}.",))


def context(user, procedure, request):
    data = _portal_data(procedure)
    main_origin = _procedure_origin(procedure, data)
    data_origin = _origin(data.item, data.document) if data is not None else None
    schedule = _schedule(data)
    link = procedure.portal_links.order_by("-pk").first()
    return {
        "pid": procedure.pk,
        "portal_url": _portal_link_url(procedure),
        "portal_number": link.process_number if link else "",
        "rows": [
            ("Número", procedure.number, True, main_origin),
            ("Expediente", data.file_number if data else "", True, data_origin),
            ("Tipo", procedure.procedure_type, False, main_origin),
            ("Objeto", procedure.subject, False, main_origin),
            ("Fecha de autorización", f"{procedure.authorization_date:%d/%m/%Y}", True,
             main_origin),
        ],
        "regimes": [r["name"] for r in procedures.regime_for(procedure.authorization_date)],
        "legal_framework": data.legal_framework if data else "",
        "lines": [{"number": line.number, "description": line.description,
                   "quantity": _quantity(line), "origin": _origin(line.item, line.document)}
                  for line in _lines(procedure)],
        "schedule": schedule,
        "opening": _opening(schedule),
        "guarantees": _guarantees(data),
        "data_origin": data_origin,
        "offers": _offers(procedure),
    }
