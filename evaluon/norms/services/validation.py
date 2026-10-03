"""Validación de una lectura (REQ-005, REQ-012; plan 001, "Ingesta", "Una norma en más
de un archivo", "Versiones de una norma" y "Registro de auditoría").

Una norma queda disponible para consultas solo después de que una persona valida su
informe de lectura. `validate_reading` hace, en este orden:

1. Comprueba el rol de lectura y escritura.
2. Comprueba que la lectura exista, esté `pending` y sea la más nueva de su documento
   (una relectura posterior la dejó atrás, T-027), y que ninguna de sus claves exista
   ya en otra parte en uso de la misma norma.
3. Arma los pasajes y pide sus vectores al servicio `embeddings`, fuera de toda
   transacción: si el servicio no responde, no se escribió nada.
4. En una sola transacción: bloquea la norma y la lectura, vuelve a comprobar el paso 2,
   busca las relaciones que quedan apuntando a una clave que la lectura nueva no tiene,
   guarda los pasajes, pasa la lectura a `validated` y la lectura validada anterior del
   mismo documento, si la hay, a `superseded` (sus unidades no se tocan), deja al primer
   documento validado de su parte como versión 1 y en uso, pasa a cargadas las
   modificatorias que correspondan (T-051) y al final registra el hecho `validation`,
   que crea la versión nueva de la normativa (`record(..., creates_corpus_version=True)`).

Un documento incorporado con confirmación de "misma norma" (`same_norm_confirmation`
no vacío, T-026) nunca queda en uso al validarse: entra en las consultas solo con
`registrar_version`. Tampoco cuenta entre los otros documentos validados de su parte al
decidir cuál es el primero; sí cuenta si ya fue registrado como versión.

Un rechazo por clave repetida o por lectura que no es la más nueva y una falla del
servicio `embeddings` también quedan registrados como hecho `validation`, con resultado
`rejected` o `failed`, sin crear versión de la normativa. El rechazo por rol lo registra
T-038.

Los mensajes de los errores son para la persona que valida: en español llano.
"""

import hashlib
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.ai import AIServiceError, InputTooLongError
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms import indexing
from evaluon.norms.models import Document, Norm, Reading, ReadingStatus, Relation, Unit
from evaluon.norms.services import amendments

# Primer número de versión de cada parte de una norma.
FIRST_VERSION = 1


class ValidationRefused(Exception):
    """No se validó la lectura. El mensaje dice por qué, en lenguaje llano."""


class ReadingNotFound(ValidationRefused):
    pass


class ReadingNotPending(ValidationRefused):
    pass


class ReadingNotLatest(ValidationRefused):
    """El documento tiene una lectura más nueva que esta (una relectura)."""

    def __init__(self, message, latest):
        super().__init__(message)
        self.latest = latest


class KeyConflict(ValidationRefused):
    """Alguna clave de la lectura ya existe en otra parte en uso de la misma norma."""

    def __init__(self, message, conflicts):
        super().__init__(message)
        self.conflicts = conflicts


class EmbeddingsFailed(ValidationRefused):
    """El servicio `embeddings` no calculó los vectores."""

    def __init__(self, message, error):
        super().__init__(message)
        self.error = error


@dataclass(frozen=True)
class ValidationResult:
    reading: Reading
    passages: int
    in_use: bool
    version_number: int | None
    corpus_version: int
    event: object
    # Lecturas validadas del mismo documento que esta reemplazó (`superseded`).
    superseded_readings: list = field(default_factory=list)
    # Relaciones que quedaron apuntando a una clave que la lectura nueva no tiene.
    relations_without_unit: list = field(default_factory=list)


def _get_reading(reading_id, *, lock=False):
    queryset = Reading.objects.select_related("document__norm")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    try:
        return queryset.get(pk=reading_id)
    except Reading.DoesNotExist:
        raise ReadingNotFound(f"No existe la lectura {reading_id}.") from None


def _require_pending(reading):
    if reading.status != ReadingStatus.PENDING:
        raise ReadingNotPending(
            f"La lectura {reading.pk} no está pendiente de validación "
            f"(estado: {ReadingStatus(reading.status).label.lower()})."
        )


def _require_latest(reading):
    """La lectura tiene que ser la más nueva de su documento: una lectura pendiente que
    una relectura dejó atrás no se valida, para que no vuelva a las consultas."""
    latest = (
        Reading.objects.filter(document_id=reading.document_id, sequence__gt=reading.sequence)
        .order_by("-sequence")
        .values_list("pk", flat=True)
        .first()
    )
    if latest is not None:
        raise ReadingNotLatest(
            f"No se validó la lectura {reading.pk}: el documento tiene una lectura más "
            f"nueva, la lectura {latest}. Revise y valide esa.",
            latest,
        )


def _key_conflicts(reading):
    """Claves de `reading` que ya existen en otra parte en uso de la misma norma, como
    pares (clave, parte), ordenados."""
    document = reading.document
    keys = set(reading.units.values_list("key", flat=True))
    rows = (
        Unit.objects.filter(
            key__in=keys,
            reading__status=ReadingStatus.VALIDATED,
            reading__document__norm_id=document.norm_id,
            reading__document__in_use=True,
        )
        .exclude(reading__document__part=document.part)
        .values_list("key", "reading__document__part")
        .distinct()
    )
    return sorted(rows)


def _check_keys(reading):
    conflicts = _key_conflicts(reading)
    if conflicts:
        listed = "; ".join(f"{key} (parte {part})" for key, part in conflicts)
        raise KeyConflict(
            "No se validó: estas claves ya existen en otra parte en uso de la misma "
            f"norma: {listed}.",
            conflicts,
        )


def _is_first_of_its_part(document):
    """Verdadero si ningún otro documento de la misma norma y parte fue registrado como
    versión, ni fue validado sin confirmación de "misma norma". Un documento confirmado
    como misma norma y todavía sin versión no cuenta (T-026): solo entra en las
    consultas con `registrar_version`, y entonces ya tiene número de versión."""
    others = Document.objects.filter(norm_id=document.norm_id, part=document.part).exclude(
        pk=document.pk
    )
    return not (
        others.filter(version_number__isnull=False).exists()
        or Reading.objects.filter(
            document__in=others.filter(same_norm_confirmation=""),
            status__in=(ReadingStatus.VALIDATED, ReadingStatus.SUPERSEDED),
        ).exists()
    )


def _goes_in_use(document):
    """Verdadero si al validar una lectura de `document` el documento pasa a estar en
    uso como versión 1 de su parte. Un documento confirmado como misma norma nunca."""
    return (
        document.version_number is None
        and not document.same_norm_confirmation
        and _is_first_of_its_part(document)
    )


def _replaced_readings(reading):
    """Lecturas validadas del mismo documento, que esta reemplaza al validarse."""
    return list(
        Reading.objects.filter(document_id=reading.document_id, status=ReadingStatus.VALIDATED)
        .exclude(pk=reading.pk)
        .order_by("sequence")
        .values_list("pk", flat=True)
    )


def _relations_without_unit(reading):
    """Relaciones de la norma que apuntan a una clave que tenía la lectura validada del
    mismo documento y que la lectura nueva no tiene, si ningún otro documento en uso de
    la norma la conserva. Cada una con un texto en lenguaje llano."""
    document = reading.document
    norm_id = document.norm_id
    previous = set(
        Unit.objects.filter(
            reading__document_id=document.pk, reading__status=ReadingStatus.VALIDATED
        )
        .exclude(reading_id=reading.pk)
        .values_list("key", flat=True)
    )
    lost = previous - set(reading.units.values_list("key", flat=True))
    if not lost:
        return []
    kept_elsewhere = set(
        Unit.objects.filter(
            key__in=lost,
            reading__status=ReadingStatus.VALIDATED,
            reading__document__norm_id=norm_id,
            reading__document__in_use=True,
        )
        .exclude(reading__document_id=document.pk)
        .values_list("key", flat=True)
    )
    missing = lost - kept_elsewhere
    relations = (
        Relation.objects.select_related("source_norm", "target_norm")
        .filter(
            Q(source_norm_id=norm_id, source_unit_key__in=missing)
            | Q(target_norm_id=norm_id, target_unit_key__in=missing)
        )
        .order_by("pk")
    )
    warnings = []
    for relation in relations:
        for role, key in (("source", relation.source_unit_key),
                          ("target", relation.target_unit_key)):
            norm = relation.source_norm if role == "source" else relation.target_norm
            if norm.pk != norm_id or key not in missing:
                continue
            warnings.append({
                "relation": relation.pk,
                "relation_type": relation.relation_type,
                "role": role,
                "key": key,
                "text": (
                    f"La relación {relation.pk} ({relation.source_norm.citation} "
                    f"{relation.relation_type} {relation.target_norm.citation}) apunta a "
                    f"la unidad {key}, que la lectura nueva no tiene."
                ),
            })
    return warnings


def _base_detail(reading):
    document = reading.document
    return {
        "reading": reading.pk,
        "reading_sequence": reading.sequence,
        "document": document.pk,
        "norm": document.norm_id,
        "part": document.part,
    }


def _record_refusal(user, reading, channel, outcome, extra):
    audit.record(
        EventType.VALIDATION,
        outcome=outcome,
        channel=channel,
        user=user,
        detail={**_base_detail(reading), **extra},
    )


def reading_summary(user, reading_id):
    """Lo que se le muestra a la persona antes de pedirle confirmación. Comprueba el rol
    y que la lectura esté pendiente."""
    require_role(user, Role.READ_WRITE)
    reading = _get_reading(reading_id)
    _require_pending(reading)
    _require_latest(reading)
    document = reading.document
    return {
        "reading": reading.pk,
        "sequence": reading.sequence,
        "norm": indexing.norm_name(document.norm),
        "title": document.norm.title,
        "part": document.part,
        "file_name": document.file_name,
        "units": reading.units.count(),
        "report_sha256": _report_sha256(reading),
        # Qué pasa al validar: si el documento queda (o sigue) en uso, qué lecturas
        # reemplaza y qué relaciones quedan sin su unidad.
        "in_use": document.in_use or _goes_in_use(document),
        "same_norm_confirmation": document.same_norm_confirmation,
        "replaces": _replaced_readings(reading),
        "relations_without_unit": _relations_without_unit(reading),
    }


def _report_sha256(reading):
    """Huella del informe en texto, el que la persona ve con `ver_informe`."""
    return hashlib.sha256(reading.report_text.encode("utf-8")).hexdigest()


def validate_reading(user, reading_id, *, channel=Channel.COMMAND):
    """Valida la lectura `reading_id` y devuelve un `ValidationResult`.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `ValidationRefused` si no se validó: lectura inexistente o no pendiente,
    clave repetida en otra parte en uso, o falla del servicio `embeddings`. En todos los
    casos de rechazo la base queda como estaba, salvo el hecho que lo registra.
    """
    require_role(user, Role.READ_WRITE)
    reading = _get_reading(reading_id)
    _require_pending(reading)
    try:
        _require_latest(reading)
        _check_keys(reading)
    except ValidationRefused as error:
        _record_refusal(user, reading, channel, Outcome.REJECTED, _refusal_detail(error))
        raise

    # Trabajo largo, fuera de la transacción: si el servicio falla no hay nada escrito.
    # La partición en pasajes ya usa el servicio (cuenta tokens, T-031).
    try:
        drafts = indexing.build_passages(reading)
        vectors = indexing.embed_passages(drafts)
    except AIServiceError as error:
        _record_refusal(user, reading, channel, Outcome.FAILED, {
            "reason": error.reason,
            "service": error.service,
            "status": error.status,
            "message": str(error),
        })
        if isinstance(error, InputTooLongError):
            cause = (
                "el texto de alguna unidad es demasiado largo para que el servicio de "
                "embeddings calcule su vector"
            )
        else:
            cause = "el servicio de embeddings no respondió"
        raise EmbeddingsFailed(
            f"No se validó la lectura {reading.pk}: {cause}. No se guardó ningún cambio.",
            error,
        ) from error

    try:
        with transaction.atomic():
            # La norma bloqueada ordena las validaciones de sus documentos: la
            # comprobación de claves y la de "primero de su parte" no se cruzan.
            Norm.objects.select_for_update().get(pk=reading.document.norm_id)
            reading = _get_reading(reading_id, lock=True)
            _require_pending(reading)
            _require_latest(reading)
            _check_keys(reading)
            # Antes de reemplazar la lectura anterior: compara sus claves con las nuevas.
            relations_without_unit = _relations_without_unit(reading)

            indexing.save_passages(drafts, vectors)

            now = timezone.now()
            superseded = _replaced_readings(reading)
            # La lectura anterior deja de ser consultable; sus unidades no se tocan.
            Reading.objects.filter(pk__in=superseded).update(
                status=ReadingStatus.SUPERSEDED, superseded_at=now
            )
            reading.status = ReadingStatus.VALIDATED
            reading.validated_at = now
            reading.validated_by = user
            reading.save(update_fields=["status", "validated_at", "validated_by"])

            document = Document.objects.select_for_update().get(pk=reading.document_id)
            if _goes_in_use(document):
                document.version_number = FIRST_VERSION
                document.in_use = True
                document.save(update_fields=["version_number", "in_use"])

            # Paso a cargada de las modificatorias anotadas de esta norma (T-051,
            # REQ-021), con la norma bloqueada y antes del registro del hecho.
            loaded_amendments = amendments.mark_loaded_for_norm(reading.document.norm_id)

            model, revision = indexing.embedding_model()
            # Al final de la transacción: crea la versión de la normativa y bloquea su
            # tabla hasta que la transacción termina.
            event = audit.record(
                EventType.VALIDATION,
                outcome=Outcome.OK,
                channel=channel,
                user=user,
                detail={
                    **_base_detail(reading),
                    "report_sha256": _report_sha256(reading),
                    "units": reading.units.count(),
                    "passages": len(drafts),
                    "embedding_model": model,
                    "embedding_revision": revision,
                    "in_use": document.in_use,
                    "version_number": document.version_number,
                    "same_norm_confirmation": document.same_norm_confirmation,
                    "superseded_readings": superseded,
                    "relations_without_unit": relations_without_unit,
                    "amendments_loaded": [
                        amendments.loaded_detail(entry) for entry in loaded_amendments
                    ],
                },
                creates_corpus_version=True,
            )
    except (KeyConflict, ReadingNotLatest) as error:
        _record_refusal(user, reading, channel, Outcome.REJECTED, _refusal_detail(error))
        raise

    return ValidationResult(
        reading=reading,
        passages=len(drafts),
        in_use=document.in_use,
        version_number=document.version_number,
        corpus_version=event.corpus_version,
        event=event,
        superseded_readings=superseded,
        relations_without_unit=relations_without_unit,
    )


def _refusal_detail(error):
    """Datos del rechazo para el hecho `validation`."""
    if isinstance(error, KeyConflict):
        return {"conflicting_keys": [key for key, _ in error.conflicts]}
    if isinstance(error, ReadingNotLatest):
        return {"reason": "not_latest", "latest_reading": error.latest}
    return {"reason": "refused", "message": str(error)}
