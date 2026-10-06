"""Comando `leer_con_vision`: lee con visión las páginas dudosas de una oferta, a mano (REQ-052,
REQ-053, REQ-054; plan 004, enmienda 2026-10-06; ADR-0041; T-160).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.offers.vision.read_offer_for`: la evaluación hace
lo mismo sola antes de armar los documentos de la oferta. Cada documento con páginas leídas
recibe una lectura nueva (las anteriores quedan); una página ya intentada no se repite. Usa el
motor de lotes con su proyector de imagen.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.offers import vision
from evaluon.offers.models import Offer


class Command(BaseCommand):
    help = "Lee con visión las páginas de lectura dudosa de una oferta."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")
        parser.add_argument("--oferta", required=True, type=int,
                            help="Número de la oferta dentro del procedimiento.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            offer = Offer.objects.select_related("procedure").get(
                procedure__number=options["procedimiento"], number=options["oferta"])
        except Offer.DoesNotExist:
            raise CommandError("No hay una oferta con ese número en ese procedimiento.") \
                from None
        try:
            summary = vision.read_offer_for(user, offer, channel=Channel.COMMAND)
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        if summary.disabled:
            self.stdout.write("La lectura con visión está apagada (tope en 0 o sin proyector).")
            return
        for reading in summary.readings:
            self.stdout.write(
                f"Documento {reading.document_id}: lectura {reading.sequence} con "
                f"{len(vision.vision_pages(reading))} páginas leídas por visión.")
        for error in summary.errors:
            self.stdout.write(f"Error: {error}")
        self.stdout.write(
            f"{summary.candidates} páginas dudosas, {summary.attempted} pedidas, "
            f"{summary.read} leídas, {summary.discarded} descartadas, {summary.over_limit} "
            f"sobre el tope, {summary.seconds:.1f} s.")
