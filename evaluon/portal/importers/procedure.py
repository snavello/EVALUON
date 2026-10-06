"""Ítems `procedimiento` y `renglones` (T-141; REQ-046, REQ-048, REQ-049).

- `procedimiento`: los datos básicos de la página. Si el número ya está registrado (carga
  manual previa), la propuesta es "asociar" al existente y no "crear". Al cargarlo se llama a
  `register_procedure` de la 003 y lo que esa tabla no tiene (expediente, encuadre, cronograma,
  garantías) va a `portal_procedure_data`.
- `renglones`: los renglones con su cantidad; van a `portal_line`.

Un ítem que cambió respecto de lo ya cargado (REQ-050) actualiza lo cargado en lugar de crearlo
de nuevo y deja el antes y el después en el registro (P6). Un renglón cargado que el Portal ya
no trae no se borra: la carga falla con el motivo.

La fecha de autorización no figura en la página: se propone una candidata (la fecha de
vinculación de «Autorización llamado») y la confirma quien aprueba (no se inventa, P3).
"""

from datetime import date

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.portal.importers import Draft, jsonable
from evaluon.portal.models import (
    ItemKind,
    LoadedModel,
    PortalLine,
    PortalProcedureData,
)
from evaluon.tenders.models import Procedure
from evaluon.tenders.services.procedures import ProcedureRefused, register_procedure

KINDS = (ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES)

CREATE = "crear"
ASSOCIATE = "asociar"
PROCEDURE_KEY = "procedimiento"
LINES_KEY = "renglones"

# Datos de la página que van en el ítem `procedimiento`.
_FIELDS = ("numero", "nombre", "objeto", "tipo", "expediente", "unidad_operativa",
           "encuadre_legal", "moneda", "cronograma", "garantias")


def explore(context):
    page = context.parsed
    drafts = []
    missing = [key for key in ("numero", "tipo") if not page.data.get(key)]
    if missing:
        context.anomalies.append({
            "parte": "procedimiento",
            "motivo": "no se propone el procedimiento: falta " + ", ".join(missing),
        })
    else:
        drafts.append(_procedure_draft(page))
    if page.lines:
        drafts.append(_lines_draft(page))
    else:
        context.anomalies.append({"parte": "renglones",
                                  "motivo": "la página no trae renglones: carga a mano"})
    return drafts


def _procedure_draft(page):
    data = page.data
    authorization = data.get("fecha_autorizacion") or {}
    payload = {key: data.get(key) for key in _FIELDS}
    payload.update({
        "fecha_autorizacion": {
            "candidata": authorization.get("candidata"),
            "origen": authorization.get("origen_candidata"),
        },
    })
    damaged = [name for name in page.damaged if not name.startswith(("renglones.", "documentos."))]
    return Draft(ItemKind.PROCEDIMIENTO, f"{PROCEDURE_KEY}:{data['numero']}",
                 jsonable(payload), damaged)


def _lines_draft(page):
    lines = [
        {"numero": line["numero"], "codigo_item": line["codigo_item"],
         "descripcion": line["descripcion"], "cantidad": line["cantidad"],
         "unidad": line["unidad"], "danado": line["danado"]}
        for line in page.lines
    ]
    damaged = [name for name in page.damaged if name.startswith("renglones.")]
    return Draft(ItemKind.RENGLONES, LINES_KEY, jsonable({"renglones": lines}), damaged)


def action(item):
    """"asociar" si el número ya está registrado (carga manual previa); si no, "crear". Se
    decide al mostrar y al cargar, no al explorar: así el contenido del ítem (y su huella) no
    cambia por haberlo cargado, y una revisión no lo vuelve a proponer."""
    exists = Procedure.objects.filter(number=item.payload["numero"]).exists()
    return ASSOCIATE if exists else CREATE


def needs_authorization_date(item):
    """Un ítem `procedimiento` que se crea pide que quien aprueba confirme la fecha."""
    return item.kind == ItemKind.PROCEDIMIENTO and action(item) == CREATE


def load(user, item, confirmation=None, channel=Channel.SCREEN):
    """Carga el ítem aprobado. Devuelve `(modelo, id)`; levanta una excepción con el motivo."""
    link = item.proposal.link
    if item.kind == ItemKind.RENGLONES:
        return _load_lines(user, item, link, channel)
    return _load_procedure(user, item, link, confirmation or {}, channel)


def _load_procedure(user, item, link, confirmation, channel):
    data = item.payload
    if action(item) == ASSOCIATE:
        procedure = Procedure.objects.get(number=data["numero"])
    else:
        authorization_date = confirmation.get("authorization_date")
        if not isinstance(authorization_date, date):
            raise ProcedureRefused("Confirme la fecha de autorización del procedimiento.",
                                   "authorization_date")
        procedure = register_procedure(
            user, number=data["numero"], procedure_type=data["tipo"],
            subject=data["objeto"] or data["nombre"],
            authorization_date=authorization_date, channel=channel,
        ).procedure
    values = {
        "file_number": data.get("expediente") or "",
        "legal_framework": data.get("encuadre_legal") or "",
        "schedule": data.get("cronograma") or {}, "guarantees": data.get("garantias") or [],
    }
    existing = PortalProcedureData.objects.select_for_update().filter(procedure=procedure).first()
    if existing is None:
        PortalProcedureData.objects.create(procedure=procedure, item=item, **values)
    else:
        # Un cambio de lo ya cargado: se actualiza y queda el antes y el después (P6).
        before = {key: getattr(existing, key) for key in values} | {"item": existing.item_id}
        for key, value in values.items():
            setattr(existing, key, value)
        existing.item = item
        existing.save()
        _record_update(user, item, channel, procedure, before, values | {"item": item.pk})
    link.procedure = procedure
    link.save(update_fields=["procedure"])
    return LoadedModel.PROCEDURE, procedure.pk


def _record_update(user, item, channel, procedure, before, after):
    audit.record(EventType.PORTAL_DECISION, outcome=Outcome.OK, channel=channel, user=user,
                 detail={"action": "actualizar_cargado", "link": item.proposal.link_id,
                         "item": item.pk, "kind": item.kind, "key": item.key,
                         "procedure": procedure.pk, "before": jsonable(before),
                         "after": jsonable(after)})


def _load_lines(user, item, link, channel):
    procedure = link.procedure
    new = {line["numero"]: line for line in item.payload["renglones"]}
    current = {line.number: line for line in PortalLine.objects.filter(procedure=procedure)}
    gone = sorted(set(current) - set(new))
    if gone:
        raise ValueError(
            "El Portal ya no trae los renglones " + ", ".join(str(n) for n in gone)
            + ", que están cargados: corríjalos a mano.")
    before = {number: _line_values(line) for number, line in current.items()}
    for number, line in new.items():
        values = {"description": line["descripcion"] or "", "quantity": line["cantidad"],
                  "unit": line["unidad"] or ""}
        if number in current:
            row = current[number]
            for key, value in values.items():
                setattr(row, key, value)
            row.item = item
            row.save()
        else:
            PortalLine.objects.create(procedure=procedure, number=number, item=item, **values)
    if current:
        after = {line.number: _line_values(line)
                 for line in PortalLine.objects.filter(procedure=procedure)}
        _record_update(user, item, channel, procedure, before, after)
    return LoadedModel.PROCEDURE, procedure.pk


def _line_values(line):
    return {"descripcion": line.description, "cantidad": line.quantity, "unidad": line.unit,
            "item": line.item_id}
