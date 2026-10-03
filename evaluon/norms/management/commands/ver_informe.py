"""Comando `ver_informe`: muestra el informe de lectura de una lectura, con sus unidades
y sus claves (REQ-004; plan 001, "Pantalla, acceso y comandos").

Rol: los dos. Recibe el número de la lectura (el que muestran `cargar_norma` y
`listar_normas`) y `--usuario`; la clave se pide por teclado. Solo traduce y llama a
`evaluon.norms.services.listing`.

Después de unas líneas de encabezado muestra el informe exactamente como está guardado:
es el texto cuya huella guarda `validar_informe` al validar, y la huella se muestra en
el encabezado para poder compararla.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.norms.management.commands.listar_normas import STATUS_TEXT
from evaluon.norms.services import listing


class Command(BaseCommand):
    help = "Muestra el informe de lectura de una lectura, con sus unidades y sus claves."

    def add_arguments(self, parser):
        parser.add_argument("lectura", type=int, help="Número de la lectura.")
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            report = listing.reading_report(user, options["lectura"])
        except (RoleRejected, listing.ReadingNotFound) as error:
            raise CommandError(str(error)) from None

        self.stdout.write(
            f"Lectura {report.reading_id} (lectura número {report.sequence} del "
            f"documento): {STATUS_TEXT.get(report.status, report.status)}\n"
            f"Norma: {report.citation} · {report.title}\n"
            f"Parte: {report.part} · Archivo: {report.file_name}\n"
            f"Huella del informe: {report.report_sha256}\n"
        )
        self.stdout.write(report.report_text, ending="")
