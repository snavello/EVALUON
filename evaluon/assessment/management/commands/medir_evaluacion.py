"""Comando `medir_evaluacion`: mide la evaluación asistida de las ofertas contra una lista
esperada (REQ-052 a REQ-055, REQ-059, REQ-060; plan 004, "Medición"; ADR-0025; T-151).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.assessment.evaluation`.

Opciones:

- `--caso-chico`: arma en la base el caso chico y público de `tests/assessment/data/
  caso-chico/` (procedimiento, pliego leído, matriz validada, tres ofertas leídas; lo que ya
  existe no se vuelve a crear) y lo mide con su `evaluacion-esperada.yaml`.
- `--esperada` y `--procedimiento`: una lista (`evaluacion-esperada.yaml` o
  `dictamen-esperado.yaml`) y el procedimiento ya cargado con su matriz validada y sus
  ofertas leídas (el caso-00).
- `--fichas`: `fichas-esperadas.yaml` del caso. Da los fragmentos y las copias equivalentes
  para REQ-054 y, con el dictamen, el mapeo de `M-NNN` a la matriz.
- `--corridas`: carpeta donde se guarda la corrida (por omisión, `corridas/` junto a la lista).
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).
- `--verificar-esperada`: no usa el modelo. Comprueba la huella de cada documento, que cada
  ancla esté en su página y que cada página no legible lo sea, e informa las cuentas.

Se corre de a una medición, sin otra carga en la GPU (ADR-0025).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import evaluation
from evaluon.tenders.models import Procedure

CASO_CHICO = Path(settings.BASE_DIR) / "tests" / "assessment" / "data" / "caso-chico"


class Command(BaseCommand):
    help = "Mide la evaluación asistida de las ofertas contra una lista esperada."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--caso-chico", action="store_true", dest="caso_chico",
                            help="Arma y mide el caso chico y público.")
        parser.add_argument("--procedimiento", default=None, help="Número del procedimiento.")
        parser.add_argument("--esperada", default=None,
                            help="evaluacion-esperada.yaml o dictamen-esperado.yaml.")
        parser.add_argument("--fichas", default=None, help="fichas-esperadas.yaml del caso.")
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
            esperada = str(CASO_CHICO / "evaluacion-esperada.yaml")
        if not esperada:
            raise CommandError("Falta --esperada (o --caso-chico).")
        try:
            expected = evaluation.load_expected(esperada, require_approval=not verify_only)
            fichas = evaluation.load_fichas(options["fichas"]) if options["fichas"] else None
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
                                        fichas=fichas, commit=options["commit"])
        except (RoleRejected, evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None

        total = report.total
        lines = [f"Corrida guardada en {report.folder}"]
        for name in evaluation.LABELS:
            value = total[name]
            shown = (len(value) if name in evaluation.MAXIMUMS
                     else evaluation.proportion_text(value))
            lines.append(f"{evaluation.LABELS[name]}: {shown}")
        lines.append(f"Por resultado: {total['by_outcome']}; evaluación completa "
                     f"{report.seconds} s, {total['model_requests']} pedidos al modelo")
        failed = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(failed) if failed else "nada"))
        self.stdout.write("\n".join(lines))
