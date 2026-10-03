"""Versiones de una norma (REQ-007, REQ-012; plan 001, "Versiones de una norma",
"Unidades consultables a una fecha" y "Registro de auditoría").

El primer documento validado de cada parte de una norma queda como versión 1 y en uso
al validarse (T-015). Otro documento validado de la misma norma y la misma parte no
entra en las consultas hasta que `register_version` diga qué es:

- **Versión nueva** (`replaces_version=None`): recibe el número siguiente de su parte,
  queda en uso y cierra la vigencia de la última versión de esa parte, cuyo
  `effective_to` pasa a ser el `effective_from` del documento nuevo (fin exclusivo: la
  anterior rige hasta el día anterior). El documento anterior sigue en uso para las
  fechas de su vigencia. Su `effective_from` tiene que ser posterior al de la versión
  que cierra.
- **Archivo en uso de una versión existente** (`replaces_version=N`): el documento pasa
  a ser el archivo en uso de la versión N de su parte, en lugar del que lo era, que deja
  de estar en uso y conserva su número. Toma el `effective_to` de la versión (vacío, o
  el que dejó la versión siguiente); su `effective_from` tiene que ser el mismo que el
  del documento que reemplaza. Las fechas las escribe la persona al cargar: aquí no se
  calculan ni se corrigen.

Las otras partes de la norma no se tocan. Pasos:

1. Comprueba el rol de lectura y escritura. El registro del rechazo por rol es de T-038.
2. Comprueba el documento (existe, tiene una lectura validada, no está en uso, no fue
   antes otra versión), la versión que se cierra o se reemplaza, las fechas y que
   ninguna clave de su lectura exista ya en otra parte en uso de la misma norma.
3. En una sola transacción, con los bloqueos en el mismo orden que la validación
   (T-015) para no cruzarse con ella: la norma, después la lectura y los documentos de
   esa parte, y al final `norms_corpus_version`. Vuelve a comprobar el paso 2, apaga el
   documento en uso que se reemplaza antes de prender el nuevo (el índice único de
   documento en uso no es diferible), cierra la vigencia de la anterior, y al final
   registra el hecho `version`, que crea la versión nueva de la normativa
   (`record(..., creates_corpus_version=True)`).

Un rechazo por el paso 2 queda registrado como hecho `version` con resultado `rejected`
y el motivo, sin nada guardado y sin versión nueva de la normativa.

Los mensajes de los errores son para la persona que registra: en español llano.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Document, Norm, Reading, ReadingStatus
from evaluon.norms.services.validation import _key_conflicts

MODE_NEW_VERSION = "new_version"
MODE_REPLACE_FILE = "replace_file"


class VersionRefused(Exception):
    """No se registró la versión. El mensaje dice por qué, en lenguaje llano."""

    reason = "refused"


class DocumentNotFound(VersionRefused):
    reason = "document_not_found"


class DocumentNotEligible(VersionRefused):
    """El documento no tiene lectura validada, ya está en uso o fue otra versión."""

    reason = "document_not_eligible"


class VersionNotFound(VersionRefused):
    reason = "version_not_found"


class InvalidDates(VersionRefused):
    reason = "invalid_dates"


class KeyConflict(VersionRefused):
    """Alguna clave de la lectura ya existe en otra parte en uso de la misma norma."""

    reason = "key_conflict"

    def __init__(self, message, conflicts):
        super().__init__(message)
        self.conflicts = conflicts


@dataclass(frozen=True)
class VersionResult:
    document: Document
    mode: str
    version_number: int
    # Versión nueva: el documento cuya vigencia se cerró, si había uno.
    previous_document: Document | None
    # Reemplazo: el documento que dejó de estar en uso.
    replaced_document: Document | None
    corpus_version: int
    event: object


def _fmt(day):
    return day.strftime("%d/%m/%Y")


def _iso(day):
    return day.isoformat() if isinstance(day, date) else None


def last_day(document):
    """Último día en que rigió un documento con vigencia cerrada (`effective_to` es el
    primer día en que ya no rige), o `None` si sigue rigiendo."""
    if document.effective_to is None:
        return None
    return document.effective_to - timedelta(days=1)


def _get_document(document_id, *, lock=False):
    queryset = Document.objects.select_related("norm")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    try:
        return queryset.get(pk=document_id)
    except Document.DoesNotExist:
        raise DocumentNotFound(
            f"No se registró la versión: no existe el documento {document_id}. Vea los "
            "números con listar_normas."
        ) from None


def _validated_reading(document, *, lock=False):
    queryset = Reading.objects.filter(document=document, status=ReadingStatus.VALIDATED)
    if lock:
        queryset = queryset.select_for_update()
    reading = queryset.order_by("-sequence").first()
    if reading is None:
        raise DocumentNotEligible(
            f"No se registró la versión: el documento {document.pk} no tiene una lectura "
            "validada. Valídela antes con validar_informe."
        )
    return reading


def _check_document(document, replaces_version):
    if document.in_use:
        raise DocumentNotEligible(
            f"No se registró la versión: el documento {document.pk} ya está en uso como "
            f"versión {document.version_number} de la parte {document.part}."
        )
    if document.version_number is not None and document.version_number != replaces_version:
        raise DocumentNotEligible(
            f"No se registró la versión: el documento {document.pk} fue el archivo de la "
            f"versión {document.version_number} de la parte {document.part}. Para volver "
            f"a usarlo, regístrelo como archivo de esa versión."
        )


def _part_documents(document, *, lock=False):
    """Documentos de la misma norma y parte, en orden de identificación."""
    queryset = Document.objects.filter(
        norm_id=document.norm_id, part=document.part
    ).order_by("pk")
    if lock:
        queryset = queryset.select_for_update()
    return list(queryset)


def _in_use_of(documents, version_number):
    for other in documents:
        if other.in_use and other.version_number == version_number:
            return other
    return None


def _plan_new_version(document, documents):
    """Devuelve (número nuevo, documento anterior o `None`)."""
    latest = max(
        (d.version_number for d in documents if d.version_number is not None),
        default=None,
    )
    if latest is None:
        return 1, None
    previous = _in_use_of(documents, latest)
    if previous is not None and document.effective_from <= previous.effective_from:
        raise InvalidDates(
            "No se registró la versión: el documento "
            f"{document.pk} rige desde el {_fmt(document.effective_from)}, y la versión "
            f"{latest} de la parte {document.part} (documento {previous.pk}) rige desde "
            f"el {_fmt(previous.effective_from)}. Una versión nueva tiene que empezar "
            "después de la anterior."
        )
    return latest + 1, previous


def _plan_replacement(document, documents, version_number):
    """Devuelve el documento en uso de la versión `version_number` que se reemplaza."""
    replaced = _in_use_of(documents, version_number)
    if replaced is None:
        raise VersionNotFound(
            f"No se registró la versión: la parte {document.part} de la norma no tiene "
            f"la versión {version_number} en uso."
        )
    if document.effective_from != replaced.effective_from:
        raise InvalidDates(
            "No se registró la versión: el documento "
            f"{document.pk} rige desde el {_fmt(document.effective_from)}, y la versión "
            f"{version_number} (documento {replaced.pk}) rige desde el "
            f"{_fmt(replaced.effective_from)}. El archivo que reemplaza al de una "
            "versión tiene que regir desde la misma fecha."
        )
    return replaced


def _check_keys(reading):
    conflicts = _key_conflicts(reading)
    if conflicts:
        listed = "; ".join(f"{key} (parte {part})" for key, part in conflicts)
        raise KeyConflict(
            "No se registró la versión: estas claves ya existen en otra parte en uso de "
            f"la misma norma: {listed}.",
            conflicts,
        )


def _check(document, replaces_version, *, lock=False):
    """Paso 2 completo. Devuelve (lectura, número, documento anterior, reemplazado)."""
    _check_document(document, replaces_version)
    reading = _validated_reading(document, lock=lock)
    documents = _part_documents(document, lock=lock)
    previous = replaced = None
    if replaces_version is None:
        number, previous = _plan_new_version(document, documents)
    else:
        number = replaces_version
        replaced = _plan_replacement(document, documents, replaces_version)
    _check_keys(reading)
    return reading, number, previous, replaced


def _record_refusal(user, channel, document_id, replaces_version, error):
    detail = {
        "reason": error.reason,
        "message": str(error),
        "document": document_id,
        "mode": MODE_NEW_VERSION if replaces_version is None else MODE_REPLACE_FILE,
        "replaces_version": replaces_version,
    }
    if isinstance(error, KeyConflict):
        detail["conflicting_keys"] = [key for key, _ in error.conflicts]
    audit.record(EventType.VERSION, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail=detail)


def register_version(user, document_id, *, replaces_version=None,
                     channel=Channel.COMMAND):
    """Registra el documento `document_id` como versión nueva de su parte de la norma
    (`replaces_version=None`) o como el archivo en uso de la versión `replaces_version`
    de esa parte. Devuelve un `VersionResult`.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `VersionRefused` si no se registró. En esos casos no se guarda nada
    salvo el hecho que lo registra.
    """
    require_role(user, Role.READ_WRITE)
    try:
        if replaces_version is not None and replaces_version < 1:
            raise VersionNotFound(
                "No se registró la versión: el número de versión a reemplazar tiene que "
                "ser 1 o mayor."
            )
        document = _get_document(document_id)
        _check(document, replaces_version)
    except VersionRefused as error:
        _record_refusal(user, channel, document_id, replaces_version, error)
        raise

    try:
        with transaction.atomic():
            # Mismo orden de bloqueos que la validación: norma, lectura y documentos, y
            # al final la versión de la normativa (en `record`).
            Norm.objects.select_for_update().get(pk=document.norm_id)
            document = _get_document(document_id, lock=True)
            reading, number, previous, replaced = _check(
                document, replaces_version, lock=True
            )

            if replaced is not None:
                # El índice único de documento en uso no es diferible: primero se apaga
                # el que estaba en uso.
                replaced.in_use = False
                replaced.save(update_fields=["in_use"])
                document.effective_to = replaced.effective_to
            if previous is not None:
                previous.effective_to = document.effective_from
                previous.save(update_fields=["effective_to"])

            document.version_number = number
            document.in_use = True
            document.save(update_fields=["version_number", "in_use", "effective_to"])

            # Al final de la transacción: crea la versión de la normativa y bloquea su
            # tabla hasta que la transacción termina.
            event = audit.record(
                EventType.VERSION,
                outcome=Outcome.OK,
                channel=channel,
                user=user,
                detail={
                    "mode": (MODE_NEW_VERSION if replaces_version is None
                             else MODE_REPLACE_FILE),
                    "document": document.pk,
                    "norm": document.norm_id,
                    "part": document.part,
                    "version_number": number,
                    "effective_from": _iso(document.effective_from),
                    "effective_to": _iso(document.effective_to),
                    "previous_document": previous.pk if previous else None,
                    "previous_version_number": (
                        previous.version_number if previous else None),
                    "previous_effective_to": (
                        _iso(previous.effective_to) if previous else None),
                    "replaced_document": replaced.pk if replaced else None,
                },
                creates_corpus_version=True,
            )
    except VersionRefused as error:
        _record_refusal(user, channel, document_id, replaces_version, error)
        raise

    return VersionResult(
        document=document,
        mode=MODE_NEW_VERSION if replaces_version is None else MODE_REPLACE_FILE,
        version_number=number,
        previous_document=previous,
        replaced_document=replaced,
        corpus_version=event.corpus_version,
        event=event,
    )
