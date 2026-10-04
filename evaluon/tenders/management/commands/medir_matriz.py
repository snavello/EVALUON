"""Comando `medir_matriz`: mide la propuesta de matriz contra la lista de requisitos esperada
(REQ-024, REQ-025; plan 003, "Medición"; ADR-0014, punto 7).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.tenders.evaluation`.

Opciones:

- `--procedimiento`: número del procedimiento con el pliego ya leído.
- `--esperada`: la lista esperada (`matriz-esperada.yaml`).
- `--niveles`: niveles a medir, separados por comas; por omisión `media,alta,exigente`.
- `--corridas`: carpeta donde se guarda la corrida; por omisión, `corridas/` junto a la
  carpeta `esperado/` de la lista.
- `--comparar-con`: carpeta con corridas anteriores (puede repetirse). La comparación entre
  niveles usa el último resultado de cada nivel en esas carpetas y en `--corridas`, siempre que
  sea del mismo procedimiento y de la misma lista.
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).
- `--verificar-esperada`: no corre el modelo. Comprueba la huella de cada archivo, que cada
  ancla esté en su tramo y que cada tramo técnico exista, e informa las cuentas.

Cada nivel corre la propuesta con el canal `eval`; las versiones que crea quedan descartadas.
Se corre de a una, sin otra carga en la GPU.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.tenders import evaluation
from evaluon.tenders.models import Procedure
from evaluon.tenders.services.matrix import MatrixRefused

DEFAULT_LEVELS = "media,alta,exigente"


class Command(BaseCommand):
    help = "Mide la propuesta de la matriz contra la lista de requisitos esperada."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True,
                            help="Número del procedimiento.")
        parser.add_argument("--esperada", required=True,
                            help="Archivo matriz-esperada.yaml.")
        parser.add_argument("--niveles", default=DEFAULT_LEVELS,
                            help="Niveles a medir, separados por comas "
                                 f"(por omisión, {DEFAULT_LEVELS}).")
        parser.add_argument("--corridas", default=None,
                            help="Carpeta donde se guarda la corrida (por omisión, "
                                 "corridas/ junto a esperado/).")
        parser.add_argument("--comparar-con", action="append", default=[], dest="comparar_con",
                            help="Carpeta con corridas anteriores para comparar los niveles "
                                 "(puede repetirse; la carpeta de --corridas ya se usa).")
        parser.add_argument("--commit", default=None,
                            help="Commit del código con que se corre.")
        parser.add_argument("--verificar-esperada", action="store_true",
                            dest="verificar_esperada",
                            help="Solo comprueba la lista contra la lectura; no usa el "
                                 "modelo.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        verify_only = options["verificar_esperada"]
        try:
            expected = evaluation.load_expected(options["esperada"],
                                                require_approval=not verify_only)
        except evaluation.ExpectedError as error:
            raise CommandError(str(error)) from None

        if verify_only:
            verification = evaluation.verify_expected(expected, procedure)
            self.stdout.write("\n".join(evaluation.verification_lines(verification)))
            if not verification.ok:
                raise CommandError("La comprobación de la lista encontró fallas.")
            return

        levels = [n.strip() for n in options["niveles"].split(",") if n.strip()]
        runs_dir = options["corridas"] or str(Path(options["esperada"]).resolve().parent.parent
                                              / "corridas")
        try:
            report = evaluation.measure(user, procedure, expected, levels, runs_dir,
                                        commit=options["commit"],
                                        compare_with=options["comparar_con"])
        except (RoleRejected, evaluation.MeasurementRefused, evaluation.ExpectedError,
                MatrixRefused) as error:
            raise CommandError(str(error)) from None

        lines = [f"Corrida guardada en {report.folder}"]
        for result in report.results:
            if result.get("error"):
                lines.append(f"{result['level']}: la propuesta falló ({result['error']})")
                continue
            measures = result["measures"]
            lines.append(
                f"{result['level']}: encontrados "
                f"{evaluation.proportion_text(measures['found'])}; cita literal "
                f"{evaluation.proportion_text(measures['literal'])}; sobrantes "
                f"{measures['leftovers']}")
        for row in report.comparison:
            lines.append(f"{row['level']}: {row['verdict']}")
        blocking = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(blocking) if blocking
                                                  else "nada"))
        self.stdout.write("\n".join(lines))
