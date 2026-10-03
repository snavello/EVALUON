"""Comando `listar_normas`: lista las normas con sus datos, sus documentos por parte y
el estado de validación (REQ-001, REQ-017, REQ-020; plan 001, "Pantalla, acceso y
comandos").

Rol: los dos. Recibe `--usuario`; la clave se pide por teclado. Solo traduce y llama a
`evaluon.norms.services.listing`. Los vínculos entre normas se suman en T-029 y las
modificatorias sin cargar en T-051.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.norms.models import Category, ReadingStatus
from evaluon.norms.services import listing

STATUS_TEXT = {
    ReadingStatus.PENDING: "pendiente de validación",
    ReadingStatus.VALIDATED: "validada",
    ReadingStatus.SUPERSEDED: "reemplazada",
}


def _date(value):
    return value.strftime("%d/%m/%Y") if value else ""


def _document_lines(document):
    lines = [
        f"  - Parte {document.part} · documento {document.id} · {document.file_name} "
        f"({document.file_format})",
        f"    Publicada el {_date(document.publication_date)} · Vigente desde "
        f"{_date(document.effective_from)}"
        + (f" hasta {_date(document.effective_to)}" if document.effective_to else ""),
        f"    Fuente: {document.source}",
    ]
    if document.reading_id is None:
        state = "sin lectura"
    else:
        state = (
            f"Lectura {document.reading_id}: "
            f"{STATUS_TEXT.get(document.reading_status, document.reading_status)}"
        )
    if document.in_use:
        use = f"en uso, versión {document.version_number}"
    else:
        use = "no está en uso"
    lines.append(f"    {state} · {use}")
    return lines


def norm_lines(norm):
    lines = [
        f"{norm.citation} · norma {norm.id}",
        f"  Título: {norm.title}",
        f"  Tipo: {norm.norm_type} · Número: {norm.number} · Año: {norm.year} · "
        f"Organismo: {norm.issuer}",
        f"  Categoría: {Category(norm.category).label} · Régimen general: "
        f"{'sí' if norm.general_regime else 'no'}",
        "  Documentos:",
    ]
    for document in norm.documents:
        lines.extend(_document_lines(document))
    return lines


class Command(BaseCommand):
    help = "Lista las normas cargadas con sus datos, sus documentos y su estado de validación."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            norms = listing.list_norms(user)
        except RoleRejected as error:
            raise CommandError(str(error)) from None

        if not norms:
            self.stdout.write("No hay normas cargadas.")
            return
        blocks = ["\n".join(norm_lines(norm)) for norm in norms]
        self.stdout.write("\n\n".join(blocks))
