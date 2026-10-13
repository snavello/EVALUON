"""Comando `releer_pliego`: vuelve a leer el pliego de un procedimiento con el código vigente y
deja una lectura nueva de cada documento, sin borrar las anteriores (REQ-016, REQ-104; T-259;
P6). Es el análogo de `releer_norma` para el pliego: el camino cuando cambia la lectura (el
texto «(cid:N)» que pasa a reconocimiento, las tablas con sus celdas) y hay que medir con ella.

Rol: lectura y escritura (operador o evaluador de la Comisión). Recibe el número del
procedimiento y `--usuario`; la clave se pide por teclado. Con `--documento` relee solo esos
documentos del procedimiento; sin él, todos los vigentes. No pide el archivo: lee el original
guardado. Cada documento deja su pedido `read_document` y su hecho `tender_read`. Solo traduce y
llama a `evaluon.tenders.services.documents.reread_procedure`.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.tenders.models import Procedure
from evaluon.tenders.services import documents


class Command(BaseCommand):
    help = ("Vuelve a leer el pliego de un procedimiento desde los originales guardados y deja "
            "una lectura nueva de cada documento; las anteriores quedan.")

    def add_arguments(self, parser):
        parser.add_argument("procedimiento", help="Número del procedimiento.")
        permissions.add_user_argument(parser)
        parser.add_argument("--documento", type=int, action="append", default=None,
                            help="Número de un documento del procedimiento (se puede repetir).")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        chosen = None
        if options["documento"]:
            chosen = list(procedure.documents.filter(pk__in=options["documento"])
                          .order_by("loaded_at", "id"))
            missing = set(options["documento"]) - {d.pk for d in chosen}
            if missing:
                raise CommandError("Esos documentos no son del procedimiento: "
                                   + ", ".join(str(n) for n in sorted(missing)) + ".")
        try:
            done = documents.reread_procedure(user, procedure, documents=chosen,
                                              channel=Channel.COMMAND)
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        failed = 0
        for item in done:
            if item.reading is None:
                failed += 1
                self.stdout.write(f"Documento {item.document.pk} ({item.document.title}): no se "
                                  f"pudo leer ({item.error}). Pedido {item.job.pk}.")
                continue
            report = item.reading.report
            self.stdout.write(
                f"Documento {item.document.pk} ({item.document.title}): lectura "
                f"{item.reading.pk} (número {item.reading.sequence} del documento), "
                f"{report.get('segments', 0)} tramos. Pedido {item.job.pk}.")
        self.stdout.write(f"Se releyeron {len(done) - failed} de {len(done)} documentos del "
                          f"procedimiento {procedure.number}; las lecturas anteriores quedan.")
        if failed:
            raise CommandError(f"{failed} documentos no se pudieron leer.")
