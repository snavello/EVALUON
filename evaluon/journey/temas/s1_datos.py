"""Tema s1_datos: los datos del procedimiento con el origen de cada uno (REQ-078, REQ-097;
plan 014, T-194).

Muestra número, expediente, tipo, objeto, fecha de autorización y el régimen que esa fecha
fija (Disp. 247/2022 o 297/03, calculado con `regime_for`), los renglones con su cantidad, el
cronograma con la apertura, las garantías y las ofertas del acta. Cada dato dice de dónde salió:
el Portal (con la hora de la exploración), un archivo subido (con su nombre) o la carga a mano
(con quién y cuándo). Solo lee (P3): no corrige ni aprueba nada; la carga está en los temas
`s1_portal` y `s1_pliego`. Las fechas se muestran en hora local.
"""

import datetime
import re
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


_STAMP = re.compile(r"^(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap])?\.?\s*m?\.?)?\s*$",
                    re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _stamp(value):
    """Fecha y hora de un hito como `datetime` (o `None` si no es una fecha) y su texto en
    24 horas. El Portal escribe «03/12/2025 04:00:00 p.m.»."""
    match = _STAMP.match(value.strip())
    if match is None:
        return None, value
    day, month, year, hour, minute, half = match.groups()
    try:
        moment = datetime.datetime(int(year), int(month), int(day))
        if hour is not None:
            h = int(hour) % 12 + (12 if half.lower() == "p" else 0) if half else int(hour)
            moment = moment.replace(hour=h, minute=int(minute))
    except ValueError:
        return None, value
    text = f"{moment:%d/%m/%Y}" + (f" {moment:%H:%M}" if hour is not None else "")
    return moment, text


def _schedule(data):
    """El cronograma como lista de `(concepto, valor)` en orden cronológico, con la hora en 24 h.
    Los renglones sin fecha (por ejemplo, una cantidad de días) van al final. Acepta el dict
    del Portal o una lista."""
    raw = data.schedule if data is not None else None
    if isinstance(raw, dict):
        pairs = [(str(k), str(v)) for k, v in raw.items()]
    elif isinstance(raw, list):
        pairs = [(str(r.get("concepto", "")), str(r.get("valor", "")))
                 if isinstance(r, dict) else (str(r), "") for r in raw]
    else:
        return []
    dated, undated = [], []
    for concept, value in pairs:
        moment, text = _stamp(value)
        label = concept
        if concept.lower().startswith("fecha y hora "):
            label = concept[len("Fecha y hora "):]
            label = label[:1].upper() + label[1:]
        (dated if moment else undated).append((moment, label, text))
    dated.sort(key=lambda row: row[0])
    return [(label, text) for _, label, text in dated + undated]


def _opening(schedule):
    return next(((k, v) for k, v in schedule
                 if any(word in k.lower() for word in OPENING_WORDS)), None)


def _fragments(data):
    raw = data.guarantees if data is not None else None
    if not isinstance(raw, list):
        return []
    return [" ".join((r if isinstance(r, str) else " ".join(
        str(v) for v in r.values() if v)).split()) for r in raw]


_REQUIRES = re.compile(r"^(si|no)\s+requiere\.?$", re.IGNORECASE)
_PREFIX = "este proceso de compra"


def _guarantees(data):
    """Las garantías del Portal, una por fila. El Portal las entrega como una lista de
    fragmentos: título («Garantía de …»), texto, «Este proceso de compra», «Si/No requiere» y
    aclaraciones. Un título abre una garantía; «Este proceso de compra» + «Si/No requiere»
    dice si se requiere; si ya se había dicho, abre otra garantía sin título (la
    contragarantía). Todo fragmento que no encaja va al detalle de la garantía anterior, nunca
    como fila suelta. Devuelve `[{"name", "required", "percent", "detail"}]`."""
    groups = []
    fragments = _fragments(data)
    i = 0
    while i < len(fragments):
        text = fragments[i]
        nxt = fragments[i + 1] if i + 1 < len(fragments) else ""
        current = groups[-1] if groups else None
        if text.lower().startswith("garantía") or text.lower().startswith("garantia"):
            groups.append({"name": text, "required": None, "details": []})
        elif text.lower().rstrip(".") == _PREFIX and _REQUIRES.match(nxt):
            answer = nxt.lower().startswith("si")
            if current is None or current["required"] is not None:
                rest = fragments[i + 2] if i + 2 < len(fragments) else ""
                name = "Contragarantía" if "contragarant" in rest.lower() else "Otra garantía"
                current = {"name": name, "required": answer,
                           "details": [f"{nxt.rstrip('.').capitalize()} {rest}".strip()]}
                groups.append(current)
                i += 1  # el fragmento siguiente ya quedó en el detalle
                if rest:
                    i += 1
            else:
                current["required"] = answer
            i += 1
        else:
            if current is None:
                current = {"name": "Garantía", "required": None, "details": []}
                groups.append(current)
            current["details"].append(text)
        i += 1
    for group in groups:
        group["detail"] = " ".join(group.pop("details"))
        match = _PERCENT.search(group["detail"])
        group["percent"] = f"{match.group(1)} %" if match else ""
    return groups


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


def _damaged(data, lines):
    """Los campos que el Portal publicó con caracteres dañados (`damaged_fields` del ítem):
    de los datos del procedimiento y, por renglón, de la descripción."""
    fields = set(data.item.damaged_fields) if data is not None and data.item_id else set()
    for line in lines:
        if line.item_id and f"renglones.{line.number}.descripcion" in line.item.damaged_fields:
            fields.add(f"renglones.{line.number}")
    return fields


def context(user, procedure, request):
    data = _portal_data(procedure)
    lines = _lines(procedure)
    damaged = _damaged(data, lines)
    main_origin = _procedure_origin(procedure, data)
    data_origin = _origin(data.item, data.document) if data is not None else None
    schedule = _schedule(data)
    link = procedure.portal_links.order_by("-pk").first()
    return {
        "pid": procedure.pk,
        "portal_url": _portal_link_url(procedure),
        "portal_number": link.process_number if link else "",
        "rows": [
            ("Número", procedure.number, True, main_origin, "numero" in damaged),
            ("Expediente", data.file_number if data else "", True, data_origin,
             "expediente" in damaged),
            ("Tipo", procedure.procedure_type, False, main_origin, "tipo" in damaged),
            ("Objeto", procedure.subject, False, main_origin, "objeto" in damaged),
            ("Fecha de autorización", f"{procedure.authorization_date:%d/%m/%Y}", True,
             main_origin, False),
        ],
        "regimes": [r["name"] for r in procedures.regime_for(procedure.authorization_date)],
        "legal_framework": data.legal_framework if data else "",
        "lines": [{"number": line.number, "description": line.description,
                   "quantity": _quantity(line), "origin": _origin(line.item, line.document),
                   "damaged": f"renglones.{line.number}" in damaged}
                  for line in lines],
        "damaged_legal": "encuadre_legal" in damaged,
        "damaged_schedule": "cronograma" in damaged,
        "damaged_guarantees": "garantias" in damaged,
        "damage_url": _portal_link_url(procedure) if procedure.portal_links.exists() else "",
        "schedule": schedule,
        "opening": _opening(schedule),
        "guarantees": _guarantees(data),
        "data_origin": data_origin,
        "offers": _offers(procedure),
    }
