"""Modificatorias sin cargar de una norma (REQ-012, REQ-021; plan 001,
`norms_pending_amendment`, "Modificatorias sin cargar" y "Registro de auditoría").

- `register_amendments` y `register_amendments_file` anotan las modificatorias de una
  norma que todavía no están cargadas: de a una (o en una lista) o en lote desde un CSV
  con las columnas `tipo`, `numero`, `anio`, `organismo` y `referencia`. Tipo, número y
  organismo se guardan normalizados igual que en `norms_norm`
  (`loading.normalize_identity`). Una modificatoria ya anotada (mismos tipo, número,
  año y organismo normalizados) no se anota otra vez: se informa y se sigue. Un renglón
  incompleto o con un año que no es un número rechaza la lista entera sin anotar
  ninguna. Al final se llama a `mark_loaded` y se deja el hecho `pending_amendment`.
  Si se anotó alguna o alguna quedó cargada en el acto, el hecho crea una versión nueva
  de la normativa; si no cambió nada, lleva la vigente.
- `mark_loaded` es el único lugar del paso a cargada: una modificatoria anotada queda
  cargada (`loaded_norm`) cuando hay una norma con el mismo tipo, número y año, con un
  documento en uso cuya lectura está validada, y con al menos una relación registrada
  hacia la norma alcanzada. El organismo solo desempata: se exige que coincida cuando
  hay más de una norma candidata o más de una modificatoria anotada con esos tres
  datos, con AFIP y ARCA como el mismo organismo (ADR-0010). Se llama al final de `register_amendments` y al final de
  `relations.register_relation`, dentro de su transacción y antes del registro del
  hecho. `mark_loaded_for_norm` lo aplica al validar una lectura
  (`validation.validate_reading`), para cada norma alcanzada que tiene anotada a la
  norma validada; así el orden en que se hagan la carga, la validación, la relación y
  la anotación no importa.
- `pending_count` es la cuenta del aviso de REQ-021: cuántas filas de esa norma tienen
  `loaded_norm` vacío. No depende de la fecha consultada.

Un rechazo por los datos o por una norma inexistente queda registrado como hecho
`pending_amendment` con resultado `rejected` y el motivo, sin nada guardado y sin
versión nueva de la normativa. El registro del rechazo por rol es de T-038.

Los mensajes de los errores son para la persona que anota: en español llano.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass

from django.db import transaction

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Norm, PendingAmendment, ReadingStatus
from evaluon.norms.services.loading import normalize_identity

# Columnas del CSV, en el orden del archivo, y el campo de `norms_pending_amendment` que
# llenan.
COLUMNS = {
    "tipo": "norm_type",
    "numero": "number",
    "anio": "year",
    "organismo": "issuer",
    "referencia": "source_ref",
}
_FIELDS = {field: column for column, field in COLUMNS.items()}
_IDENTITY = ("norm_type", "number", "year", "issuer")
# El año, con cuatro cifras.
_YEAR = re.compile(r"[1-9][0-9]{3}")


class AmendmentsRefused(Exception):
    """No se anotó ninguna modificatoria. El mensaje dice por qué, en lenguaje llano."""

    reason = "refused"


class InvalidAmendments(AmendmentsRefused):
    reason = "invalid_data"


class NormNotFound(AmendmentsRefused):
    reason = "norm_not_found"


@dataclass(frozen=True)
class AmendmentsResult:
    target_norm: Norm
    # Filas creadas.
    added: list
    # Las que ya estaban anotadas, como diccionarios con los datos normalizados y
    # `existing`, el número de la fila que ya estaba.
    already: list
    # Renglones que repiten una modificatoria de un renglón anterior de la misma lista:
    # los datos normalizados, `line`, `first_line` y `different_ref` (si la referencia
    # es otra). No se anotan; vale el primer renglón.
    repeated: list
    # Filas que quedaron cargadas en el acto.
    loaded: list
    # Cuántas quedan sin cargar de la norma alcanzada.
    pending: int
    corpus_version: int | None
    event: object


def pending_count(norm):
    """Cuántas modificatorias sin cargar tiene `norm` (una norma o su número): las
    filas de `norms_pending_amendment` de esa norma con `loaded_norm` vacío."""
    norm_id = getattr(norm, "pk", norm)
    return PendingAmendment.objects.filter(
        target_norm_id=norm_id, loaded_norm__isnull=True
    ).count()


def _qualifies(norm_ids, target_id):
    """De `norm_ids`, las normas con un documento en uso con su lectura validada y con
    al menos una relación registrada hacia `target_id`."""
    return set(
        Norm.objects.filter(
            pk__in=norm_ids,
            documents__in_use=True,
            documents__readings__status=ReadingStatus.VALIDATED,
        )
        .filter(relations_from__target_norm_id=target_id)
        .values_list("pk", flat=True)
        .distinct()
    )


def _same_identity(entry, norm):
    return (entry.norm_type, entry.number, entry.year) == (
        norm.norm_type, norm.number, norm.year
    )


def _same_issuer(entry, norm):
    """Mismo organismo, con AFIP y ARCA como uno solo (ADR-0010). Se vuelve a normalizar
    lo guardado, así coinciden también las filas guardadas antes de esa equivalencia
    (por ejemplo, "arca" o el nombre largo de la AFIP)."""
    return normalize_identity(entry.issuer) == normalize_identity(norm.issuer)


def matching_entry(target_norm, norm):
    """La modificatoria anotada de `target_norm` que corresponde a `norm`, cargada o
    no, o `None` si `norm` no figura entre las anotadas. Coincide por tipo, número y
    año; si hay más de una con esos tres datos, desempata el organismo."""
    entries = [
        entry
        for entry in PendingAmendment.objects.filter(
            target_norm_id=getattr(target_norm, "pk", target_norm),
            norm_type=norm.norm_type, number=norm.number, year=norm.year,
        ).order_by("pk")
    ]
    if len(entries) > 1:
        entries = [entry for entry in entries if _same_issuer(entry, norm)]
    return entries[0] if len(entries) == 1 else None


def mark_loaded(target_norm):
    """Deja cargadas las modificatorias sin cargar de `target_norm` (una norma o su
    número) que ya tienen su norma cargada, con lectura validada y en uso, y una
    relación hacia `target_norm`. Devuelve las filas que quedaron cargadas.

    Se llama dentro de la transacción de quien registra, con la norma alcanzada
    bloqueada, y antes de `audit.record`.
    """
    target_id = getattr(target_norm, "pk", target_norm)
    entries = list(
        PendingAmendment.objects.filter(target_norm_id=target_id).order_by("pk")
    )
    pending = [entry for entry in entries if entry.loaded_norm_id is None]
    if not pending:
        return []

    triples = {(e.norm_type, e.number, e.year) for e in pending}
    candidates = list(
        Norm.objects.filter(
            norm_type__in={t[0] for t in triples},
            number__in={t[1] for t in triples},
            year__in={t[2] for t in triples},
        ).exclude(pk=target_id)
    )
    qualified = _qualifies([norm.pk for norm in candidates], target_id)
    candidates = [norm for norm in candidates if norm.pk in qualified]

    loaded = []
    for entry in pending:
        matches = [norm for norm in candidates if _same_identity(entry, norm)]
        siblings = [other for other in entries
                    if (other.norm_type, other.number, other.year)
                    == (entry.norm_type, entry.number, entry.year)]
        if len(matches) > 1 or len(siblings) > 1:
            matches = [norm for norm in matches if _same_issuer(entry, norm)]
        if len(matches) != 1:
            continue
        entry.loaded_norm = matches[0]
        entry.save(update_fields=["loaded_norm"])
        loaded.append(entry)
    return loaded


def mark_loaded_for_norm(norm):
    """Al validar una lectura de `norm` (una norma o su número): busca las modificatorias
    sin cargar con su mismo tipo, número y año, en cualquier norma alcanzada, y llama a
    `mark_loaded` para cada norma alcanzada. Devuelve las filas que quedaron cargadas.

    Se llama dentro de la transacción de la validación, con `norm` bloqueada, y antes
    de `audit.record`. No bloquea las normas alcanzadas: el bloqueo de `norm` alcanza
    para ordenar la validación con el registro de una relación desde `norm`, que
    también la bloquea, y así no se invierte el orden de bloqueo de las normas.
    """
    if not isinstance(norm, Norm):
        norm = Norm.objects.get(pk=norm)
    targets = (
        PendingAmendment.objects.filter(
            norm_type=norm.norm_type, number=norm.number, year=norm.year,
            loaded_norm__isnull=True,
        )
        .exclude(target_norm_id=norm.pk)
        .values_list("target_norm_id", flat=True)
        .distinct()
        .order_by("target_norm_id")
    )
    loaded = []
    for target_id in list(targets):
        loaded.extend(mark_loaded(target_id))
    return loaded


def amendment_detail(entry):
    """Datos de una fila para el registro de auditoría."""
    return {
        "id": entry.pk,
        "norm_type": entry.norm_type,
        "number": entry.number,
        "year": entry.year,
        "issuer": entry.issuer,
        "source_ref": entry.source_ref,
    }


def loaded_detail(entry):
    """Datos de una fila que quedó cargada, para el registro de auditoría."""
    return {
        "id": entry.pk,
        "norm_type": entry.norm_type,
        "number": entry.number,
        "year": entry.year,
        "issuer": entry.issuer,
        "loaded_norm": entry.loaded_norm_id,
    }


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _clean(rows, first_line):
    """Comprueba y normaliza la lista. Devuelve pares (renglón, datos). `first_line` es
    el número de renglón del primer elemento, para los mensajes (en un CSV, 2: el 1 es
    el encabezado)."""
    if not rows:
        raise InvalidAmendments(
            "No se anotó ninguna modificatoria: la lista no trae ninguna."
        )
    cleaned = []
    problems = []
    for line, row in enumerate(rows, start=first_line):
        missing = [_FIELDS[name] for name in COLUMNS.values() if _blank(row.get(name))]
        if missing:
            problems.append(f"renglón {line}: falta {', '.join(missing)}")
            continue
        year = str(row["year"]).strip()
        if not _YEAR.fullmatch(year):
            problems.append(
                f"renglón {line}: el anio ({year}) no es válido; escríbalo con cuatro "
                "cifras, por ejemplo 2005"
            )
            continue
        cleaned.append((line, {
            "norm_type": normalize_identity(row["norm_type"]),
            "number": normalize_identity(row["number"]),
            "year": int(year),
            "issuer": normalize_identity(row["issuer"]),
            "source_ref": str(row["source_ref"]).strip(),
        }))
    if problems:
        raise InvalidAmendments(
            "No se anotó ninguna modificatoria, porque hay renglones incompletos o con "
            "errores: " + "; ".join(problems) + "."
        )
    return cleaned


def parse_csv(data):
    """Las filas de un CSV en bytes, como diccionarios con los campos de
    `norms_pending_amendment`. Lanza `InvalidAmendments` si no se puede leer o le falta
    alguna columna."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidAmendments(
            "No se anotó ninguna modificatoria: el archivo no está en UTF-8. Guárdelo "
            "como CSV UTF-8."
        ) from None
    first = text.split("\n", 1)[0]
    # Una planilla en español guarda el CSV separado por punto y coma: el separador es
    # el que aparece más en el encabezado.
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
    missing = [column for column in COLUMNS if column not in header]
    if missing:
        raise InvalidAmendments(
            "No se anotó ninguna modificatoria: al archivo le faltan las columnas "
            f"{', '.join(missing)}. Tiene que traer {', '.join(COLUMNS)}."
        )
    reader.fieldnames = header
    return [
        {field: row.get(column) for column, field in COLUMNS.items()}
        for row in reader
    ]


def _get_target(target_norm, *, lock=False):
    queryset = Norm.objects.filter(pk=target_norm)
    if lock:
        queryset = queryset.select_for_update()
    norm = queryset.first()
    if norm is None:
        raise NormNotFound(
            f"No se anotó ninguna modificatoria: no existe la norma alcanzada "
            f"{target_norm}. Vea los números con listar_normas."
        )
    return norm


def _record_refusal(user, channel, target_norm, file_info, error):
    audit.record(
        EventType.PENDING_AMENDMENT,
        outcome=Outcome.REJECTED,
        channel=channel,
        user=user,
        detail={
            "reason": error.reason,
            "message": str(error),
            "target_norm": target_norm,
            "file": file_info,
        },
    )


def _register(user, target_norm, rows, first_line, file_info, channel):
    try:
        cleaned = _clean(rows, first_line)
        _get_target(target_norm)
    except AmendmentsRefused as error:
        _record_refusal(user, channel, target_norm, file_info, error)
        raise

    with transaction.atomic():
        # La norma alcanzada bloqueada ordena este registro con los de relaciones y con
        # otros registros de modificatorias de la misma norma.
        target = _get_target(target_norm, lock=True)
        existing = {
            tuple(getattr(entry, name) for name in _IDENTITY): entry.pk
            for entry in PendingAmendment.objects.filter(target_norm=target)
        }
        added, already, repeated = [], [], []
        # Primer renglón de la lista con cada modificatoria, y su referencia.
        seen = {}
        for line, values in cleaned:
            identity = tuple(values[name] for name in _IDENTITY)
            if identity in seen:
                first_line, first_ref = seen[identity]
                repeated.append({**values, "line": line, "first_line": first_line,
                                 "different_ref": values["source_ref"] != first_ref})
                continue
            seen[identity] = (line, values["source_ref"])
            if identity in existing:
                already.append({**values, "existing": existing[identity]})
                continue
            added.append(PendingAmendment.objects.create(
                target_norm=target, registered_by=user, **values
            ))
        loaded = mark_loaded(target)
        pending = pending_count(target)
        # Al final de la transacción: si crea la versión de la normativa, bloquea su
        # tabla hasta que la transacción termina.
        event = audit.record(
            EventType.PENDING_AMENDMENT,
            outcome=Outcome.OK,
            channel=channel,
            user=user,
            detail={
                "target_norm": target.pk,
                "target_citation": target.citation,
                "added": [amendment_detail(entry) for entry in added],
                "already": already,
                "repeated": repeated,
                "loaded": [loaded_detail(entry) for entry in loaded],
                "file": file_info,
                "pending": pending,
            },
            creates_corpus_version=bool(added or loaded),
        )

    return AmendmentsResult(
        target_norm=target, added=added, already=already, repeated=repeated,
        loaded=loaded, pending=pending, corpus_version=event.corpus_version, event=event,
    )


def register_amendments(user, *, target_norm, amendments, channel=Channel.COMMAND):
    """Anota las modificatorias sin cargar `amendments` de la norma `target_norm`
    (número). Cada una es un diccionario con `norm_type`, `number`, `year`, `issuer` y
    `source_ref`, todos obligatorios. Devuelve un `AmendmentsResult`.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `AmendmentsRefused` si no anotó ninguna: algún dato falta o no es
    válido, o la norma alcanzada no existe.
    """
    require_role(user, Role.READ_WRITE)
    return _register(user, target_norm, list(amendments), 1, None, channel)


def register_amendments_file(user, *, target_norm, data, file_name,
                             channel=Channel.COMMAND):
    """Como `register_amendments`, con las modificatorias de un CSV (`data`, en bytes)
    con las columnas de `COLUMNS`. El hecho guarda el nombre y la huella del archivo."""
    require_role(user, Role.READ_WRITE)
    file_info = {"name": file_name, "sha256": hashlib.sha256(data).hexdigest()}
    try:
        rows = parse_csv(data)
    except AmendmentsRefused as error:
        _record_refusal(user, channel, target_norm, file_info, error)
        raise
    return _register(user, target_norm, rows, 2, file_info, channel)
