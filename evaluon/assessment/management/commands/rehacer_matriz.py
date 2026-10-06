"""Comando `rehacer_matriz`: crea una versión nueva y validada de la matriz de un procedimiento
con todas las cláusulas de cada renglón en sus filas técnicas (REQ-052; T-156).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide por
teclado. La versión anterior no se toca y el cambio queda en el registro (P6). Solo traduce y
llama a `evaluon.assessment.evaluation.rebuild_matrix`.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import evaluation
from evaluon.tenders.models import Procedure


class Command(BaseCommand):
    help = "Rehace la matriz validada con las cláusulas completas de cada renglón técnico."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        try:
            version, rows = evaluation.rebuild_matrix(user, procedure)
        except (RoleRejected, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"Versión {version.number} validada (copiada de la "
                          f"{version.based_on.number}): {rows} filas técnicas con todas sus "
                          "cláusulas.")
