"""Validación de una lectura (REQ-005, REQ-012; plan 001, "Ingesta", "Una norma en más
de un archivo", "Versiones de una norma" y "Registro de auditoría").

Una norma queda disponible para consultas solo después de que una persona valida su
informe de lectura. `validate_reading` hace, en este orden:

1. Comprueba el rol de lectura y escritura.
2. Comprueba que la lectura exista y esté `pending`, y que ninguna de sus claves exista
   ya en otra parte en uso de la misma norma.
3. Arma los pasajes y pide sus vectores al servicio `embeddings`, fuera de toda
   transacción: si el servicio no responde, no se escribió nada.
4. En una sola transacción: bloquea la norma y la lectura, vuelve a comprobar el paso 2,
   guarda los pasajes, pasa la lectura a `validated`, deja al primer documento validado
   de su parte como versión 1 y en uso, y al final registra el hecho `validation`, que
   crea la versión nueva de la normativa (`record(..., creates_corpus_version=True)`).

Un rechazo por clave repetida y una falla del servicio `embeddings` también quedan
registrados como hecho `validation`, con resultado `rejected` o `failed`, sin crear
versión de la normativa. El rechazo por rol lo registra T-038.

Los mensajes de los errores son para la persona que valida: en español llano.
"""

import hashlib
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.ai import AIServiceError, InputTooLongError
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms import indexing
from evaluon.norms.models import Document, Norm, Reading, ReadingStatus, Unit

# Primer número de versión de cada parte de una norma.
FIRST_VERSION = 1


class ValidationRefused(Exception):
    """No se validó la lectura. El mensaje dice por qué, en lenguaje llano."""


class ReadingNotFound(ValidationRefused):
    pass


class ReadingNotPending(ValidationRefused):
    pass


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
    """Verdadero si ningún otro documento de la misma norma y parte fue validado ni
    registrado como versión."""
    others = Document.objects.filter(norm_id=document.norm_id, part=document.part).exclude(
        pk=document.pk
    )
    return not (
        others.filter(version_number__isnull=False).exists()
        or Reading.objects.filter(
            document__in=others,
            status__in=(ReadingStatus.VALIDATED, ReadingStatus.SUPERSEDED),
        ).exists()
    )


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
        _check_keys(reading)
    except KeyConflict as error:
        _record_refusal(user, reading, channel, Outcome.REJECTED,
                        {"conflicting_keys": [key for key, _ in error.conflicts]})
        raise

    # Trabajo largo, fuera de la transacción: si el servicio falla no hay nada escrito.
    drafts = indexing.build_passages(reading)
    try:
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
            _check_keys(reading)

            indexing.save_passages(drafts, vectors)

            reading.status = ReadingStatus.VALIDATED
            reading.validated_at = timezone.now()
            reading.validated_by = user
            reading.save(update_fields=["status", "validated_at", "validated_by"])

            document = Document.objects.select_for_update().get(pk=reading.document_id)
            if document.version_number is None and _is_first_of_its_part(document):
                document.version_number = FIRST_VERSION
                document.in_use = True
                document.save(update_fields=["version_number", "in_use"])

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
                },
                creates_corpus_version=True,
            )
    except KeyConflict as error:
        _record_refusal(user, reading, channel, Outcome.REJECTED,
                        {"conflicting_keys": [key for key, _ in error.conflicts]})
        raise

    return ValidationResult(
        reading=reading,
        passages=len(drafts),
        in_use=document.in_use,
        version_number=document.version_number,
        corpus_version=event.corpus_version,
        event=event,
    )
