"""Comando `medir_fichas`: mide la ficha de cada oferta contra la lista de fragmentos esperados
(REQ-038, REQ-039, REQ-040, REQ-041, REQ-044; plan 008, "Medición"; ADR-0025; T-130).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.offers.evaluation`.

Opciones:

- `--caso-chico`: arma en la base el caso chico y público de `tests/offers/data/caso-chico/`
  (procedimiento, pliego leído, matriz validada, oferta y documentos leídos; lo que ya existe
  no se vuelve a crear) y lo mide. Con él, `--procedimiento` y `--esperada` salen de la lista.
- `--procedimiento` y `--esperada`: el procedimiento con su matriz validada y sus ofertas
  cargadas, y su lista `fichas-esperadas.yaml` (casos con ofertas ya cargadas, como el caso-00).
- `--corridas`: carpeta donde se guarda la corrida; por omisión, `corridas/` junto a la lista.
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).
- `--verificar-esperada`: no corre el modelo. Comprueba la huella de cada documento, que cada
  ancla esté en su página y que cada página no legible lo sea, e informa las cuentas.

Se corre de a una, sin otra carga en la GPU (ADR-0025).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.offers import evaluation
from evaluon.tenders.models import Procedure

CASO_CHICO = Path(settings.BASE_DIR) / "tests" / "offers" / "data" / "caso-chico"


class Command(BaseCommand):
    help = "Mide la ficha de cada oferta contra la lista de fragmentos esperados."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--caso-chico", action="store_true", dest="caso_chico",
                            help="Arma y mide el caso chico y público.")
        parser.add_argument("--procedimiento", default=None, help="Número del procedimiento.")
        parser.add_argument("--esperada", default=None, help="Archivo fichas-esperadas.yaml.")
        parser.add_argument("--corridas", default=None,
                            help="Carpeta donde se guarda la corrida (por omisión, "
                                 "corridas/ junto a la lista).")
        parser.add_argument("--commit", default=None, help="Commit del código con que se corre.")
        parser.add_argument("--verificar-esperada", action="store_true",
                            dest="verificar_esperada",
                            help="Solo comprueba la lista contra la lectura; no usa el modelo.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        verify_only = options["verificar_esperada"]
        esperada = options["esperada"]
        if options["caso_chico"] and not esperada:
            esperada = str(CASO_CHICO / "fichas-esperadas.yaml")
        if not esperada:
            raise CommandError("Falta --esperada (o --caso-chico).")
        try:
            expected = evaluation.load_expected(esperada, require_approval=not verify_only)
            if options["caso_chico"]:
                procedure, offers = evaluation.build_case(user, expected)
            else:
                number = options["procedimiento"] or expected.matrix["procedimiento"]
                try:
                    procedure = Procedure.objects.get(number=number)
                except Procedure.DoesNotExist:
                    raise CommandError("No hay un procedimiento con ese número.") from None
                offers = {o.bidder: o for o in procedure.offers.all()}

            if verify_only:
                verification = evaluation.verify_expected(expected, offers)
                self.stdout.write("\n".join(verification.lines))
                if not verification.ok:
                    raise CommandError("La comprobación de la lista encontró fallas.")
                return

            runs_dir = options["corridas"] or str(Path(esperada).resolve().parent / "corridas")
            report = evaluation.measure(user, procedure, expected, offers, runs_dir,
                                        commit=options["commit"])
        except (RoleRejected, evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None

        total = report.total
        lines = [f"Corrida guardada en {report.folder}"]
        for name in evaluation.THRESHOLDS:
            lines.append(f"{evaluation.LABELS[name]}: "
                         f"{evaluation.proportion_text(total[name])}")
        lines.append(f"Páginas sin texto ni lista: {len(total['pages_unlisted'])}; "
                     f"renglones «no se pudo leer»: {len(total['items_unreadable'])}; "
                     f"fragmentos sin pareja: {total['extra_fragments']}; "
                     f"falsos hallazgos: {len(total['false_findings'])}; "
                     f"anomalías: {len(total['anomalies'])}")
        failed = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(failed) if failed else "nada"))
        self.stdout.write("\n".join(lines))
