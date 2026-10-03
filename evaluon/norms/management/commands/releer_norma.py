"""Comando `releer_norma`: vuelve a leer y partir un documento ya cargado y deja una
lectura nueva sin validar (REQ-004, REQ-005, REQ-012; plan 001, "Pantalla, acceso y
comandos" e "Ingesta", punto 6).

Rol: lectura y escritura. Recibe el número del documento (el que muestra
`listar_normas`) y `--usuario`; la clave se pide por teclado. No pide el archivo: lee el
original guardado. Es el camino cuando se corrige una regla de partición. Solo traduce y
llama a `evaluon.norms.services.loading`.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.services import loading


class Command(BaseCommand):
    help = (
        "Vuelve a leer y partir un documento ya cargado, desde el original guardado. Deja "
        "una lectura nueva pendiente de validación; hasta validarla, en las consultas "
        "sigue la lectura anterior."
    )

    def add_arguments(self, parser):
        parser.add_argument("documento", type=int, help="Número del documento a releer.")
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            result = loading.reread_document(user, options["documento"],
                                             channel=Channel.COMMAND)
        except (RoleRejected, loading.RereadRefused) as error:
            raise CommandError(str(error)) from None

        reading = result.reading
        report = reading.report
        current = result.validated_reading
        if current is None:
            still = "Ninguna lectura de este documento estaba validada."
        elif result.document.in_use:
            still = f"Mientras no se valide, en las consultas sigue la lectura {current.pk}."
        else:
            still = f"Mientras no se valide, sigue validada la lectura {current.pk}."
        username = user.get_username()
        self.stdout.write(
            f"Se releyó el documento {result.document.pk}: parte {result.document.part} "
            f"de la {result.document.norm.citation}.\n"
            f"Lectura {reading.pk} (lectura número {reading.sequence} del documento), "
            f"pendiente de validación: {result.units} unidades, "
            f"{report['pages']['total']} páginas, {len(report['unlocated'])} tramos no "
            f"ubicados.\n"
            f"{still}\n"
            f"Revise el informe con: ver_informe {reading.pk} --usuario {username}\n"
            f"Para reemplazar la lectura anterior, valídela con: validar_informe "
            f"{reading.pk} --usuario {username}"
        )
