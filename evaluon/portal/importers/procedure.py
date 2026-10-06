"""Ítems `procedimiento` y `renglones` (T-141; REQ-046, REQ-048, REQ-049).

- `procedimiento`: los datos básicos de la página. Si el número ya está registrado (carga
  manual previa), la propuesta es "asociar" al existente y no "crear". Al cargarlo se llama a
  `register_procedure` de la 003 y lo que esa tabla no tiene (expediente, encuadre, cronograma,
  garantías) va a `portal_procedure_data`.
- `renglones`: los renglones con su cantidad; van a `portal_line`.

La fecha de autorización no figura en la página: se propone una candidata (la fecha de
vinculación de «Autorización llamado») y la confirma quien aprueba (no se inventa, P3).
"""

from datetime import date

from evaluon.audit.models import Channel
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
        return _load_lines(item, link)
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
    PortalProcedureData.objects.create(
        procedure=procedure, file_number=data.get("expediente") or "",
        legal_framework=data.get("encuadre_legal") or "",
        schedule=data.get("cronograma") or {}, guarantees=data.get("garantias") or [],
        item=item,
    )
    link.procedure = procedure
    link.save(update_fields=["procedure"])
    return LoadedModel.PROCEDURE, procedure.pk


def _load_lines(item, link):
    procedure = link.procedure
    for line in item.payload["renglones"]:
        PortalLine.objects.create(
            procedure=procedure, number=line["numero"],
            description=line["descripcion"] or "", quantity=line["cantidad"],
            unit=line["unidad"] or "", item=item,
        )
    return LoadedModel.PROCEDURE, procedure.pk
