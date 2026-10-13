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
- `--recalcular`: carpeta de una corrida ya hecha (T-256). No usa el modelo ni la GPU, no pide
  `--procedimiento` y no escribe nada; pide usuario y clave como todo comando (REQ-016): vuelve a contar desde su `resultados.jsonl` con las reglas de antes
  y con las de T-256 (lo que está a revisión aparte, las suprimidas por una circular en otra fila,
  las filas técnicas aparte) y con el archivo de `--exclusiones`, y escribe las dos cifras.
- `--regenerar-resumen`: carpeta de una corrida ya hecha. No corre el modelo: vuelve a medir las
  propuestas que nombra `parametros.json` (siguen en la base) y reescribe `resumen.md` y
  `resumen-publico.md` (T-096).
- `--reanclar`: no usa el modelo ni la GPU (T-262, D-260-2). Reubica cada entrada de la lista en
  la lectura vigente del pliego: una formal o económica por su ancla, una clave técnica por el
  texto que ocupaba en la lectura anterior. Escribe un archivo NUEVO al lado de la lista
  (`matriz-esperada.reanclada-AAAA-MM-DD.yaml`) con la huella de la lista original y de cada
  lectura y el visto bueno vacío para el Coordinador; la lista original no se modifica y un
  archivo que ya existe no se pisa. Informa cuántas entradas se reubicaron y cuáles no se
  pudieron reubicar (esas conservan su clave: no se inventa), sin texto del pliego.

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
from django.utils import timezone

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.tenders import evaluation
from evaluon.tenders.models import Procedure
from evaluon.tenders.services.matrix import MatrixRefused


class Command(BaseCommand):
    help = "Mide la propuesta de la matriz contra la lista de requisitos esperada."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", default=None,
                            help="Número del procedimiento (no hace falta con --recalcular).")
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
        parser.add_argument("--recalcular", default=None,
                            help="Carpeta de una corrida ya hecha: recalcula sin el modelo ni la "
                                 "base, antes y después de las correcciones de T-256.")
        parser.add_argument("--regenerar-resumen", default=None, dest="regenerar_resumen",
                            help="Carpeta de una corrida ya hecha: reescribe sus resúmenes "
                                 "sin usar el modelo.")
        parser.add_argument("--verificar-esperada", action="store_true",
                            dest="verificar_esperada",
                            help="Solo comprueba la lista contra la lectura; no usa el "
                                 "modelo.")
        parser.add_argument("--reanclar", action="store_true",
                            help="No usa el modelo: reubica las entradas de la lista en la "
                                 "lectura vigente y escribe la lista re-anclada en un archivo "
                                 "nuevo, al lado de la original.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        if options["recalcular"]:
            self._recompute(options)
            return
        if not options["procedimiento"]:
            raise CommandError("Falta --procedimiento.")
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        verify_only = options["verificar_esperada"]
        if options["reanclar"]:
            self._reanchor(options, procedure)
            return
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

    def _reanchor(self, options, procedure):
        """`--reanclar`: la lista re-anclada a la lectura vigente, en un archivo nuevo."""
        try:
            expected = evaluation.load_expected(options["esperada"], require_approval=False)
            result = evaluation.reanchor_expected(expected, procedure)
            path = evaluation.write_reanchored(result, timezone.localdate())
            reanchored = evaluation.load_expected(path, require_approval=False)
        except evaluation.ExpectedError as error:
            raise CommandError(str(error)) from None
        verification = evaluation.verify_expected(reanchored, procedure)
        lines = [f"Lista re-anclada escrita en {path}", *evaluation.reanchoring_lines(result),
                 "Comprobación de la lista re-anclada contra la lectura vigente (sin visto bueno "
                 "todavía):", *evaluation.verification_lines(verification),
                 "Visto bueno: vacío. La lista re-anclada se usa cuando el Coordinador lo "
                 "complete."]
        self.stdout.write("\n".join(lines))

    def _recompute(self, options):
        """`--recalcular`: las cifras de la 015 de una corrida guardada, antes y después."""
        try:
            expected = evaluation.load_expected(options["esperada"], require_approval=False)
            exclusions = (evaluation.load_exclusions(options["exclusiones"], expected)
                          if options["exclusiones"] else None)
            result = evaluation.recompute_matrix_run(options["recalcular"], expected, exclusions)
        except (evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None
        text = evaluation.proportion_text
        lines = [f"Corrida recalculada sin el modelo: {Path(result['folder']).name}"]
        for moment, label in (("before", "antes"), ("after", "después")):
            figures = result[moment]
            lines.append(
                f"[{label}] lista presente {text(figures['recall'])} (con lo que está a revisión "
                f"{text(figures['found_with_review'])}); filas conservadas "
                f"{text(figures['kept'])}; sin las técnicas: lista "
                f"{text(figures['found_without_technical'])}, conservadas "
                f"{text(figures['kept_without_technical'])}; excluidas {figures['excluded']}")
        after = result["after"]
        lines.append(f"Suprimidas por una circular en otra fila: {after['suppressed_elsewhere']}; "
                     "entradas que el archivo ya no excluye y no se pueden medir sin la base: "
                     + (", ".join(after["without_line"]) or "ninguna"))
        self.stdout.write("\n".join(lines))
