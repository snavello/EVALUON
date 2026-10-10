"""Comando `medir_matriz`: mide la propuesta de matriz contra la lista de requisitos esperada
(REQ-024, REQ-025; plan 003, "Medición"; ADR-0014, punto 7).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.tenders.evaluation`.

Opciones:

- `--procedimiento`: número del procedimiento con el pliego ya leído.
- `--esperada`: la lista esperada (`matriz-esperada.yaml`).
- `--corridas`: carpeta donde se guarda la corrida; por omisión, `corridas/` junto a la
  carpeta `esperado/` de la lista.
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).
- `--verificar-esperada`: no corre el modelo. Comprueba la huella de cada archivo, que cada
  ancla esté en su tramo, que cada tramo técnico exista y que cada bloque `circulares`
  (documento, fecha, ancla, texto original y vigente) esté en la lectura, e informa las
  cuentas.
- `--exclusiones`: archivo aparte con las entradas de la lista que excluyen las decisiones del
  2026-10-10 (pago, moneda de pago, factura, forma de presentar por el Portal, compromisos al
  presentarse), con la huella de la lista y el visto bueno del Coordinador (T-238). La lista no
  se modifica; sin este archivo el recall y las filas conservadas se miden contra la lista
  entera. Con `--verificar-esperada` informa cuántas entradas excluye.
- `--regenerar-resumen`: carpeta de una corrida ya hecha. No corre el modelo: vuelve a medir las
  propuestas que nombra `parametros.json` (siguen en la base) y reescribe `resumen.md` y
  `resumen-publico.md` (T-096).

Mide el proceso único (REQ-030 enmendado: ya no hay niveles ni comparación entre ellos):
corre la propuesta con el canal `eval`; la versión que crea queda descartada.
REQ-031 se mide por fila con el bloque `circulares` de la lista (T-117): efecto, texto
original, texto vigente, documento y fecha; una lista con `alcance: circulares` mide solo eso.
Las sugerencias de condición no entran en el tope; se informan aparte (T-111), con la
plantilla local `muestra-sugerencias.md` para el verificador.
Se corre de a una, sin otra carga en la GPU.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.tenders import evaluation
from evaluon.tenders.models import Procedure
from evaluon.tenders.services.matrix import MatrixRefused


class Command(BaseCommand):
    help = "Mide la propuesta de la matriz contra la lista de requisitos esperada."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True,
                            help="Número del procedimiento.")
        parser.add_argument("--esperada", required=True,
                            help="Archivo matriz-esperada.yaml.")
        parser.add_argument("--corridas", default=None,
                            help="Carpeta donde se guarda la corrida (por omisión, "
                                 "corridas/ junto a esperado/).")
        parser.add_argument("--exclusiones", default=None,
                            help="Archivo con las entradas de la lista que excluyen las "
                                 "decisiones del 2026-10-10 (huella de la lista y visto bueno).")
        parser.add_argument("--commit", default=None,
                            help="Commit del código con que se corre.")
        parser.add_argument("--regenerar-resumen", default=None, dest="regenerar_resumen",
                            help="Carpeta de una corrida ya hecha: reescribe sus resúmenes "
                                 "sin usar el modelo.")
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
            if options["exclusiones"]:
                expected.exclusions = evaluation.load_exclusions(
                    options["exclusiones"], expected, require_approval=not verify_only)
        except evaluation.ExpectedError as error:
            raise CommandError(str(error)) from None

        if verify_only:
            verification = evaluation.verify_expected(expected, procedure)
            self.stdout.write("\n".join(evaluation.verification_lines(verification)
                                        + evaluation.exclusion_lines(expected)))
            if not verification.ok:
                raise CommandError("La comprobación de la lista encontró fallas.")
            return

        if options["regenerar_resumen"]:
            try:
                report = evaluation.regenerate_summaries(
                    procedure, expected, options["regenerar_resumen"])
            except evaluation.MeasurementRefused as error:
                raise CommandError(str(error)) from None
            self.stdout.write(f"Resúmenes reescritos en {report.folder}")
            return

        runs_dir = options["corridas"] or str(Path(options["esperada"]).resolve().parent.parent
                                              / "corridas")
        try:
            report = evaluation.measure(user, procedure, expected, runs_dir,
                                        commit=options["commit"])
        except (RoleRejected, evaluation.MeasurementRefused, evaluation.ExpectedError,
                MatrixRefused) as error:
            raise CommandError(str(error)) from None

        lines = [f"Corrida guardada en {report.folder}"]
        for result in report.results:
            if result.get("error"):
                lines.append(f"{result['process']}: la propuesta falló ({result['error']})")
                continue
            measures = result["measures"]
            circulars = measures.get("circulars")
            if circulars:
                lines.append(
                    f"{result['process']}: REQ-031, filas de circular que cumplen los cuatro "
                    f"puntos {evaluation.proportion_text(circulars['met'])}; fuentes ajenas "
                    f"{circulars['noise']['sources']}; sin medir (circular declarada sin "
                    f"cargar) {len(circulars['unmeasured'])}")
            if measures.get("scope") == evaluation.SCOPE_CIRCULARS:
                continue
            lines.append(
                f"{result['process']}: encontrados "
                f"{evaluation.proportion_text(measures['found'])}; cita literal "
                f"{evaluation.proportion_text(measures['literal'])}; sobrantes "
                f"{evaluation.proportion_text(measures['leftover_ratio'])}; descartadas "
                f"{measures['discarded']['count']}; sugerencias "
                f"{measures['suggestions']['count']} (a revisión obligatoria: "
                f"{measures['suggestion_review']['count']}); tope de sobrantes "
                f"{'cumple' if measures['cap']['met'] else 'no cumple'}")
        unmet = report.unmet_015
        lines.append("Umbrales de la 015 que no llegan: " + ("; ".join(unmet) if unmet
                                                              else "ninguno"))
        blocking = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(blocking) if blocking
                                                  else "nada"))
        self.stdout.write("\n".join(lines))
