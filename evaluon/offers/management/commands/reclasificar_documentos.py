"""Comando `reclasificar_documentos`: vuelve a aplicar la clasificación de tipo a los documentos
ya cargados de un procedimiento (REQ-044; plan 008, "Carga y lectura"; T-136).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.offers.services.offers.reclassify_documents`.
No lee ni usa OCR ni GPU: usa el nombre del archivo y el texto de la última lectura. Cada
cambio de tipo queda en el registro.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.offers.services import offers as services
from evaluon.tenders.models import Procedure


class Command(BaseCommand):
    help = "Vuelve a clasificar el tipo de los documentos ya cargados de un procedimiento."

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
            changed = services.reclassify_documents(user, procedure, channel=Channel.COMMAND)
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        for document, before, after in changed:
            self.stdout.write(f"Documento {document.pk} (oferta {document.offer.number}): "
                              f"{before or 'sin tipo'} -> {after}.")
        self.stdout.write(f"{len(changed)} documentos cambiaron de tipo.")
