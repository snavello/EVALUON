"""Listado de normas e informe de lectura (REQ-001, REQ-004, REQ-017, REQ-020; plan 001,
"Pantalla, acceso y comandos": `listar_normas` y `ver_informe`).

- `list_norms`: las normas con sus datos, su nombre de cita y su marca de régimen
  general, y sus documentos con la parte, las fechas, la fuente y el estado de
  validación de su última lectura. Los vínculos entre normas se suman en T-029 y las
  modificatorias sin cargar en T-051.
- `reading_report`: el informe de lectura de una lectura, tal como está guardado. Su
  texto es exactamente `norms_reading.report_text`, el mismo cuya huella guarda la
  validación (T-015).

Las dos son para los dos roles: comprueban el rol de lectura, que incluye al de lectura
y escritura.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Prefetch

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.norms.models import BODY_PART, Document, Norm, Reading


class ReadingNotFound(Exception):
    """No existe la lectura pedida."""


@dataclass(frozen=True)
class DocumentItem:
    id: int
    part: str
    file_name: str
    file_format: str
    publication_date: date
    effective_from: date
    effective_to: date | None
    source: str
    in_use: bool
    version_number: int | None
    # Última lectura del documento y su estado (`pending`, `validated`, `superseded`).
    reading_id: int | None
    reading_status: str | None


@dataclass(frozen=True)
class NormItem:
    id: int
    citation: str
    category: str
    norm_type: str
    number: str
    year: int
    issuer: str
    title: str
    general_regime: bool
    documents: list[DocumentItem] = field(default_factory=list)


@dataclass(frozen=True)
class ReadingReport:
    reading_id: int
    sequence: int
    status: str
    citation: str
    title: str
    part: str
    file_name: str
    report_text: str

    @property
    def report_sha256(self):
        """Huella del informe en texto, la misma que guarda la validación."""
        return hashlib.sha256(self.report_text.encode("utf-8")).hexdigest()


def _part_order(document):
    """El cuerpo primero; después los anexos, por su clave."""
    return (document.part != BODY_PART, document.part, document.pk)


def _document_item(document):
    readings = list(document.readings.all())
    last = readings[-1] if readings else None
    return DocumentItem(
        id=document.pk,
        part=document.part,
        file_name=document.file_name,
        file_format=document.file_format,
        publication_date=document.publication_date,
        effective_from=document.effective_from,
        effective_to=document.effective_to,
        source=document.source,
        in_use=document.in_use,
        version_number=document.version_number,
        reading_id=last.pk if last else None,
        reading_status=last.status if last else None,
    )


def list_norms(user):
    """Las normas cargadas, ordenadas por nombre de cita, con sus documentos."""
    require_role(user, Role.READ)
    readings = Reading.objects.only("id", "document_id", "sequence", "status").order_by(
        "sequence"
    )
    documents =Document.objects.prefetch_related(Prefetch("readings", queryset=readings))
    norms = Norm.objects.prefetch_related(Prefetch("documents", queryset=documents))
    return [
        NormItem(
            id=norm.pk,
            citation=norm.citation,
            category=norm.category,
            norm_type=norm.norm_type,
            number=norm.number,
            year=norm.year,
            issuer=norm.issuer,
            title=norm.title,
            general_regime=norm.general_regime,
            documents=[
                _document_item(document)
                for document in sorted(norm.documents.all(), key=_part_order)
            ],
        )
        for norm in norms.order_by("citation", "pk")
    ]


def reading_report(user, reading_id):
    """El informe de lectura de `reading_id`, tal como está guardado."""
    require_role(user, Role.READ)
    try:
        reading = Reading.objects.select_related("document__norm").get(pk=reading_id)
    except Reading.DoesNotExist:
        raise ReadingNotFound(f"No existe la lectura {reading_id}.") from None
    document = reading.document
    return ReadingReport(
        reading_id=reading.pk,
        sequence=reading.sequence,
        status=reading.status,
        citation=document.norm.citation,
        title=document.norm.title,
        part=document.part,
        file_name=document.file_name,
        report_text=reading.report_text,
    )
