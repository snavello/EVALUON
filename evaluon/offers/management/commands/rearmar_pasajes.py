"""Comando `rearmar_pasajes`: arma de nuevo los pasajes de los documentos ya leídos de un
procedimiento con el particionado de hoy, sin OCR (REQ-038, REQ-039; plan 008, "Pasajes";
T-136).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.offers.services.offers.rebuild_passages`.
Parte de las páginas de la última lectura de cada documento y guarda una lectura nueva (las
anteriores quedan). Calcula los vectores con el servicio de embeddings; no usa OCR. Un
documento cuyo particionado no cambia no recibe lectura nueva.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.offers.models import Document
from evaluon.offers.services import offers as services
from evaluon.tenders.models import Procedure


class Command(BaseCommand):
    help = "Rearma los pasajes de los documentos ya leídos de un procedimiento, sin OCR."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        documents = (Document.objects.filter(offer__procedure=procedure, readings__isnull=False)
                     .select_related("offer__procedure").distinct()
                     .order_by("offer__number", "loaded_at", "id"))
        rebuilt = 0
        try:
            for document in documents:
                saved = services.rebuild_passages(user, document, channel=Channel.COMMAND)
                if saved is None:
                    self.stdout.write(f"Documento {document.pk}: sin cambios.")
                    continue
                rebuilt += 1
                self.stdout.write(f"Documento {document.pk} (oferta {document.offer.number}): "
                                  f"lectura {saved.sequence} con {saved.passages.count()} "
                                  "pasajes.")
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"{rebuilt} documentos con lectura nueva.")
