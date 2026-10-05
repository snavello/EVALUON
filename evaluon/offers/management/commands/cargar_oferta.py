"""Comando `cargar_oferta`: registra la oferta de un oferente en un procedimiento y carga sus
documentos (REQ-037; plan 008, "Carga y lectura"; T-130).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.offers.services.offers`.

- `--procedimiento`: número del procedimiento.
- `--oferente`: nombre del oferente. Si ya tiene oferta en el procedimiento, se le suman los
  documentos a esa oferta.
- Los archivos (PDF) son los argumentos que siguen. El tipo de documento no se elige: lo
  clasifica el sistema al leerlo. Cada carga deja su lectura en espera para el `worker`.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.offers.services import offers as services
from evaluon.tenders.models import Procedure


class Command(BaseCommand):
    help = "Registra una oferta y carga sus documentos."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")
        parser.add_argument("--oferente", required=True, help="Nombre del oferente.")
        parser.add_argument("archivos", nargs="+", help="Documentos de la oferta (PDF).")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        paths = [Path(name) for name in options["archivos"]]
        for path in paths:
            if not path.is_file():
                raise CommandError(f"No existe el archivo {path}.")
        bidder = " ".join(options["oferente"].split())
        try:
            offer = procedure.offers.filter(bidder=bidder).first()
            if offer is None:
                offer = services.register_offer(user, procedure, bidder=bidder,
                                                channel=Channel.COMMAND)
            self.stdout.write(f"Oferta {offer.number} (id {offer.pk}).")
            for path in paths:
                try:
                    loaded = services.load_document(user, offer, data=path.read_bytes(),
                                                    file_name=path.name,
                                                    channel=Channel.COMMAND)
                except services.DuplicateFile as refused:
                    self.stdout.write(f"{path.name}: {refused}")
                except services.OfferRefused as refused:
                    raise CommandError(f"{path.name}: {refused}") from None
                else:
                    self.stdout.write(f"{path.name}: cargado (documento {loaded.document.pk}, "
                                      f"lectura en espera, pedido {loaded.job.pk}).")
        except RoleRejected as error:
            raise CommandError(str(error)) from None
