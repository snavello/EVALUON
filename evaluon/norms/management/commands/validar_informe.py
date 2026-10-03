"""Comando `validar_informe`: valida una lectura, previa confirmación, y calcula sus
pasajes y vectores (REQ-005, REQ-012; plan 001, "Pantalla, acceso y comandos").

Rol: lectura y escritura. Recibe el número de la lectura (el que muestran
`listar_normas` y `ver_informe`) y `--usuario`; la clave se pide por teclado. Muestra
qué se va a validar y pide confirmación antes de validar. Solo traduce y llama a
`evaluon.norms.services.validation`.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.services import validation

YES_ANSWERS = {"si", "sí", "s"}


def ask_confirmation(prompt):
    """Pregunta por teclado y devuelve lo que la persona escribió."""
    return input(prompt)


class Command(BaseCommand):
    help = (
        "Valida el informe de una lectura, previa confirmación: la norma queda disponible "
        "para consultas. Necesita el servicio de embeddings."
    )

    def add_arguments(self, parser):
        parser.add_argument("lectura", type=int, help="Número de la lectura a validar.")
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        reading_id = options["lectura"]
        try:
            summary = validation.reading_summary(user, reading_id)
        except (RoleRejected, validation.ValidationRefused) as error:
            raise CommandError(str(error)) from None

        self.stdout.write(
            f"Lectura {summary['reading']} (lectura número {summary['sequence']} del "
            f"documento)\n"
            f"Norma: {summary['norm']} · {summary['title']}\n"
            f"Parte: {summary['part']}\n"
            f"Archivo: {summary['file_name']}\n"
            f"Unidades: {summary['units']}\n"
            f"Huella del informe: {summary['report_sha256']}\n"
            "Al validar, la norma queda disponible para consultas."
        )
        answer = ask_confirmation("¿Confirma la validación? Escriba si para confirmar: ")
        if answer.strip().lower() not in YES_ANSWERS:
            self.stdout.write("No se validó la lectura.")
            return

        try:
            result = validation.validate_reading(user, reading_id, channel=Channel.COMMAND)
        except (RoleRejected, validation.ValidationRefused) as error:
            raise CommandError(str(error)) from None

        if result.in_use:
            use = f"Quedó en uso como versión {result.version_number} de su parte."
        else:
            use = (
                "Ya hay otro documento validado de esta parte: este no se usa en las "
                "consultas hasta registrarlo como versión con registrar_version."
            )
        self.stdout.write(
            f"Se validó la lectura {result.reading.pk}, con {result.passages} pasajes. "
            f"{use} Se creó la versión {result.corpus_version} de la normativa."
        )
