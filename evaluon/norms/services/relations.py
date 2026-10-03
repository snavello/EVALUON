"""Registro de relaciones entre normas (REQ-006, REQ-007, REQ-012, REQ-020; plan 001,
`norms_relation`, "Unidades consultables a una fecha" y "Registro de auditoría").

`register_relation` registra que una norma modifica, complementa, reglamenta o deroga a
otra, en este orden:

1. Comprueba el rol de lectura y escritura. El registro del rechazo por rol es de T-038.
2. Comprueba los datos: el tipo (uno de `RelationType`), la fecha de vigencia del cambio
   (obligatoria: la escribe la persona, el sistema no la calcula ni la completa) y las
   dos normas, que tienen que existir y ser distintas.
3. Si se indican claves de unidad, comprueba que existan en los documentos en uso de su
   norma, en cualquiera de sus partes, con su lectura validada. Una clave vacía quiere
   decir la norma entera.
4. En una sola transacción: bloquea las dos normas (en orden de identificación, el mismo
   primer paso que la validación, para no cruzarse con ella), vuelve a comprobar las
   claves, guarda la relación y al final registra el hecho `relation`, que crea la
   versión nueva de la normativa (`record(..., creates_corpus_version=True)`).

Un rechazo por los datos, por una norma inexistente o por una clave inexistente queda
registrado como hecho `relation` con resultado `rejected` y el motivo, sin nada guardado
y sin versión nueva de la normativa.

Una relación sobre la norma entera no aparece en `unit_changes(fecha)`: se ve como
vínculo de la norma (`listing.py`) y, si es `deroga`, en `repealed` de
`consultable_units(fecha)` (T-009).

Los mensajes de los errores son para la persona que registra: en español llano.
"""

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Norm, ReadingStatus, Relation, RelationType, Unit


class RelationRefused(Exception):
    """No se registró la relación. El mensaje dice por qué, en lenguaje llano."""

    reason = "refused"


class InvalidRelation(RelationRefused):
    reason = "invalid_data"


class NormNotFound(RelationRefused):
    reason = "norm_not_found"


class UnitKeyNotFound(RelationRefused):
    """Alguna clave no existe en los documentos en uso de su norma. `missing` son los
    pares (papel, clave): papel `source` o `target`."""

    reason = "unit_key_not_found"

    def __init__(self, message, missing):
        super().__init__(message)
        self.missing = missing


@dataclass(frozen=True)
class RelationResult:
    relation: Relation
    corpus_version: int
    event: object


def _clean_key(value):
    return (value or "").strip().lower()


def _data_detail(values):
    return {
        "relation_type": values["relation_type"],
        "source_norm": values["source_norm"],
        "target_norm": values["target_norm"],
        "source_unit_key": values["source_unit_key"],
        "target_unit_key": values["target_unit_key"],
        "effective_date": (
            values["effective_date"].isoformat()
            if isinstance(values["effective_date"], date)
            else values["effective_date"]
        ),
    }


def _check_data(values):
    if values["relation_type"] not in RelationType.values:
        raise InvalidRelation(
            "No se registró la relación: el tipo "
            f"({values['relation_type'] or 'vacío'}) tiene que ser uno de: "
            f"{', '.join(RelationType.values)}."
        )
    if not isinstance(values["effective_date"], date):
        raise InvalidRelation(
            "No se registró la relación: falta la fecha desde la que rige el cambio. "
            "La escribe la persona; el sistema no la calcula."
        )
    if values["source_norm"] == values["target_norm"]:
        raise InvalidRelation(
            "No se registró la relación: la norma de origen y la alcanzada son la misma."
        )


def _get_norms(values, *, lock=False):
    ids = {values["source_norm"], values["target_norm"]}
    queryset = Norm.objects.filter(pk__in=ids).order_by("pk")
    if lock:
        queryset = queryset.select_for_update()
    norms = {norm.pk: norm for norm in queryset}
    for role, label in (("source_norm", "de origen"), ("target_norm", "alcanzada")):
        if values[role] not in norms:
            raise NormNotFound(
                f"No se registró la relación: no existe la norma {label} "
                f"{values[role]}. Vea los números con listar_normas."
            )
    return norms[values["source_norm"]], norms[values["target_norm"]]


def _key_exists(norm, key):
    """Verdadero si `key` es la clave de una unidad de un documento en uso de `norm`,
    de cualquiera de sus partes, con su lectura validada."""
    return Unit.objects.filter(
        key=key,
        reading__status=ReadingStatus.VALIDATED,
        reading__document__norm=norm,
        reading__document__in_use=True,
    ).exists()


def _check_keys(values, source, target):
    missing = [
        (role, values[f"{role}_unit_key"], norm)
        for role, norm in (("source", source), ("target", target))
        if values[f"{role}_unit_key"] and not _key_exists(norm, values[f"{role}_unit_key"])
    ]
    if missing:
        listed = "; ".join(f"{key} en la {norm.citation}" for _, key, norm in missing)
        raise UnitKeyNotFound(
            "No se registró la relación: estas claves no existen en los documentos en "
            f"uso de su norma: {listed}. Vea las claves con ver_informe.",
            [(role, key) for role, key, _ in missing],
        )


def _record_refusal(user, channel, values, error):
    detail = {"reason": error.reason, "message": str(error), **_data_detail(values)}
    if isinstance(error, UnitKeyNotFound):
        detail["missing_keys"] = [list(pair) for pair in error.missing]
    audit.record(EventType.RELATION, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail=detail)


def register_relation(user, *, relation_type, source_norm, target_norm, effective_date,
                      source_unit_key="", target_unit_key="", channel=Channel.COMMAND):
    """Registra que la norma `source_norm` (identificación) modifica, complementa,
    reglamenta o deroga (`relation_type`) a la norma `target_norm`, desde
    `effective_date` (un `date`). Las claves de unidad son opcionales: vacías, la
    relación es desde o hacia la norma entera. Devuelve un `RelationResult`.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `RelationRefused` si no se registró: datos que faltan o no son válidos,
    norma inexistente o clave de unidad inexistente. En esos casos no se guarda nada
    salvo el hecho que lo registra.
    """
    require_role(user, Role.READ_WRITE)
    values = {
        "relation_type": (relation_type or "").strip().lower(),
        "source_norm": source_norm,
        "target_norm": target_norm,
        "source_unit_key": _clean_key(source_unit_key),
        "target_unit_key": _clean_key(target_unit_key),
        "effective_date": effective_date,
    }

    try:
        _check_data(values)
        source, target = _get_norms(values)
        _check_keys(values, source, target)
    except RelationRefused as error:
        _record_refusal(user, channel, values, error)
        raise

    try:
        with transaction.atomic():
            # Las normas bloqueadas ordenan este registro con las validaciones, que
            # pueden cambiar qué documentos están en uso: las claves se comprueban de
            # nuevo con las normas bloqueadas.
            source, target = _get_norms(values, lock=True)
            _check_keys(values, source, target)
            relation = Relation.objects.create(
                relation_type=values["relation_type"],
                source_norm=source,
                target_norm=target,
                source_unit_key=values["source_unit_key"],
                target_unit_key=values["target_unit_key"],
                effective_date=values["effective_date"],
                registered_by=user,
            )
            # Al final de la transacción: crea la versión de la normativa y bloquea su
            # tabla hasta que la transacción termina.
            event = audit.record(
                EventType.RELATION,
                outcome=Outcome.OK,
                channel=channel,
                user=user,
                detail={
                    "relation": relation.pk,
                    **_data_detail(values),
                    "source_citation": source.citation,
                    "target_citation": target.citation,
                },
                creates_corpus_version=True,
            )
    except RelationRefused as error:
        _record_refusal(user, channel, values, error)
        raise

    return RelationResult(relation=relation, corpus_version=event.corpus_version,
                          event=event)
