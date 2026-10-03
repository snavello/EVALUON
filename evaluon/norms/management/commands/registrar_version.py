"""Comando `registrar_version`: deja un documento validado como versión de su parte de la
norma, o como el archivo en uso de una versión existente (REQ-007; plan 001, "Versiones
de una norma" y "Pantalla, acceso y comandos").

Rol: lectura y escritura. El documento se indica por su número, el que muestra
`listar_normas` ("documento 7"). Hay que elegir una de dos opciones:

- `--nueva`: el documento es la versión siguiente de su parte. Queda en uso y la
  versión anterior de esa parte deja de regir el día anterior a la fecha de vigencia
  del documento nuevo.
- `--reemplaza N`: el documento es otro archivo de la versión N de su parte (otro
  formato del mismo texto) y pasa a ser el que se usa para consultarla, en lugar del
  que lo era.

Las fechas de vigencia son las que se escribieron al cargar cada documento: el comando
no las pide ni las calcula. Recibe `--usuario`; la clave se pide por teclado. Solo
traduce y llama a `evaluon.norms.services.versions`.

Ejemplo, una rectificación cargada como documento 7:

    python manage.py registrar_version 7 --nueva --usuario responsable
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.services import versions


def _fmt(day):
    return day.strftime("%d/%m/%Y")


class Command(BaseCommand):
    help = (
        "Deja un documento validado como versión nueva de su parte de la norma, o como "
        "el archivo en uso de una versión existente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "documento", type=int,
            help="Número del documento, como lo muestra listar_normas.",
        )
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--nueva", action="store_true",
            help="El documento es la versión siguiente de su parte de la norma.",
        )
        mode.add_argument(
            "--reemplaza", type=int, metavar="VERSION",
            help="El documento pasa a ser el archivo en uso de esa versión de su parte, "
            "en lugar del que lo era.",
        )
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            result = versions.register_version(
                user,
                options["documento"],
                replaces_version=options["reemplaza"],
                channel=Channel.COMMAND,
            )
        except (RoleRejected, versions.VersionRefused) as error:
            raise CommandError(str(error)) from None

        document = result.document
        lines = [
            f"El documento {document.pk} ({document.file_name}) quedó en uso como versión "
            f"{result.version_number} de la parte {document.part} de la "
            f"{document.norm.citation}, vigente desde el {_fmt(document.effective_from)}"
            + (
                f" hasta el {_fmt(versions.last_day(document))}."
                if document.effective_to else "."
            )
        ]
        previous = result.previous_document
        if previous is not None:
            lines.append(
                f"La versión {previous.version_number} (documento {previous.pk}) rige "
                f"hasta el {_fmt(versions.last_day(previous))}."
            )
        replaced = result.replaced_document
        if replaced is not None:
            lines.append(
                f"El documento {replaced.pk} deja de estar en uso; se conserva."
            )
        lines.append(f"Se creó la versión {result.corpus_version} de la normativa.")
        self.stdout.write("\n".join(lines))
