"""Comando `listar_normas`: lista las normas con sus datos, sus documentos por parte, el
estado de validación y los vínculos con otras normas en los dos sentidos (REQ-001,
REQ-006, REQ-017, REQ-020; plan 001, "Pantalla, acceso y comandos").

Rol: los dos. Recibe `--usuario`; la clave se pide por teclado. Solo traduce y llama a
`evaluon.norms.services.listing`. Las modificatorias sin cargar se suman en T-051.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.norms.models import Category, ReadingStatus, RelationType
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


# Cómo se lee cada tipo de relación desde la norma de origen y desde la alcanzada.
LINK_TEXT = {
    RelationType.MODIFICA: ("Modifica a", "Modificada por"),
    RelationType.COMPLEMENTA: ("Complementa a", "Complementada por"),
    RelationType.REGLAMENTA: ("Reglamenta a", "Reglamentada por"),
    RelationType.DEROGA: ("Deroga a", "Derogada por"),
}

WHOLE_NORM = "la norma entera"


def _link_line(link):
    outgoing, incoming = LINK_TEXT.get(link.relation_type,
                                       (link.relation_type, link.relation_type))
    verb = outgoing if link.direction == "outgoing" else incoming
    return (
        f"  - {verb} {link.other_citation} (norma {link.other_norm_id}) · "
        f"origen: {link.source_unit_key or WHOLE_NORM} · "
        f"alcanza: {link.target_unit_key or WHOLE_NORM} · "
        f"desde el {_date(link.effective_date)} · relación {link.relation_id}"
    )


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
    if norm.links:
        lines.append("  Vínculos:")
        lines.extend(_link_line(link) for link in norm.links)
    else:
        lines.append("  Vínculos: ninguno")
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
