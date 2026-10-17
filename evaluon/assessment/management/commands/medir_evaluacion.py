"""Comando `medir_evaluacion`: mide la evaluación asistida de las ofertas contra una lista
esperada (REQ-052 a REQ-055, REQ-059, REQ-060; plan 004, "Medición"; ADR-0025; T-151).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado, también con `--recalcular` (REQ-016). Solo traduce y llama a
`evaluon.assessment.evaluation`.

Opciones:

- `--caso-chico`: arma en la base el caso chico y público de `tests/assessment/data/
  caso-chico/` (procedimiento, pliego leído, matriz validada, tres ofertas leídas; lo que ya
  existe no se vuelve a crear) y lo mide con su `evaluacion-esperada.yaml`.
- `--esperada` y `--procedimiento`: una lista (`evaluacion-esperada.yaml` o
  `dictamen-esperado.yaml`) y el procedimiento ya cargado con su matriz validada y sus
  ofertas leídas (el caso-00).
- `--fichas`: `fichas-esperadas.yaml` del caso. Da los fragmentos y las copias equivalentes
  para REQ-054 y, con el dictamen, el mapeo de `M-NNN` a la matriz.
- `--celdas-portal`: archivo aparte con las celdas cuyo dato está en el Portal (oferta, fila de la
  matriz validada, tipo, valor y si el dato coincide con lo que exige el pliego; T-238, REQ-103).
  Se suman a los pares de la lista que traen `portal`.
- `--celdas-comision`: las decisiones de la Comisión de prueba por celda (oferta, fila,
  resultado), con su huella y visto bueno (T-256). Da la exactitud por celda: exactas (con cita o
  sin cita; si la cita sostiene lo afirmado se lee en `muestra-exactas.md`), abstenciones y
  erradas. Acepta también la verdad ampliada `verdad-celdas.yaml` (T-271, REQ-118; ADR-0069):
  las celdas vienen por oferta y requisito (M-NNN), se traducen a la fila de la matriz y solo
  cuentan las que tienen revisión; «no determinado» contra «no determinado» es exacto.
- `--exclusiones-celdas`: las filas de la matriz evaluada que la medida no cuenta (las agregadas
  solo para la medida), con su motivo y visto bueno (T-256). Se informan aparte.
- Toda medición cuenta también las tres salidas de cada celda (T-277, REQ-120, umbral 9): las
  celdas «no se encontró el documento» sin pregunta y los «no determinado» sin pregunta ni
  documento nombrado, con sus filas (`evaluation.three_outputs`).
- `--recalcular`: carpeta de una corrida ya hecha. No usa el modelo, la GPU ni la evaluación:
  vuelve a contar desde `resultados.jsonl` y `celdas-todas.txt`, con las reglas de antes y con
  las corregidas de T-256, y escribe las dos cifras. La lista de la Comisión se acepta sin visto
  bueno y se dice.
- `--corridas`: carpeta donde se guarda la corrida (por omisión, `corridas/` junto a la lista).
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).
- `--verificar-esperada`: no usa el modelo. Comprueba la huella de cada documento, que cada
  ancla esté en su página y que cada página no legible lo sea, e informa las cuentas.
- `--verificar-verdad`: no usa el modelo ni la GPU (T-271). Con `--caso-chico`, comprueba la verdad
  del caso chico; con `--esperada`, `--procedimiento` y `--celdas-comision`, la de un caso. Cuenta
  las celdas, las decididas, las revisadas (quién y cuándo), las citas ubicadas en la lectura de la
  oferta (`quotes.locate`) o el ítem del Portal, los «no determinado» con pregunta o documento
  nombrado, el `congelado-016.txt` de los casos de aceptación y las corridas de evaluación
  guardadas del procedimiento (0 en los de aceptación). Una celda sin revisión no se cuenta. Si
  algo falla, termina con error.
- `--verificar-decisiones`: no usa el modelo ni la GPU. Corre los tests marcados
  `decision_literal` (uno por decisión del responsable, ADR-0043) y comprueba que la lista
  esperada trae los campos de la regla nueva (`documento_tecnico` y `renglon_ofertado` en cada
  fila técnica, `ilegible` donde dice «no se pudo leer»). Si un test falla o falta un campo, la
  medición se rechaza (error). Si todavía ningún test lleva la marca, lo informa y no bloquea.
  Toda medición vuelve a comprobar los campos de la lista antes de empezar.
- `--verificador-sobre`: carpeta de una corrida ya guardada (T-299; plan 016, «Medición del paso 4»).
  No usa la GPU: aplica el verificador externo de citas a sus evaluaciones con la misma función que
  la evaluación (`verifier.verify`), guarda una evaluación nueva derivada por oferta (la base es de
  solo inserción: las de la corrida no cambian) y la mide como cualquier corrida, con las cifras sin
  el verificador (`facts["verificador"]["antes"]`) y con él. Necesita el uso externo encendido y la
  etapa `verificador` en `externo`; con `--medicion NOMBRE`, un pedido igual a uno ya respondido en
  esa medición reusa su respuesta (sin costo). Toda corrida con celdas verificadas trae esas cifras.

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
        parser.add_argument("--celdas-portal", default=None, dest="celdas_portal",
                            help="Archivo con las celdas del Portal (oferta, fila, tipo, valor "
                                 "y si coincide), con visto bueno.")
        parser.add_argument("--celdas-comision", default=None, dest="celdas_comision",
                            help="Decisiones de la Comisión de prueba por celda (huella y visto "
                                 "bueno), para la exactitud por celda.")
        parser.add_argument("--exclusiones-celdas", default=None, dest="exclusiones_celdas",
                            help="Filas de la matriz evaluada que la medida no cuenta, con su "
                                 "motivo y visto bueno.")
        parser.add_argument("--recalcular", default=None,
                            help="Carpeta de una corrida ya hecha: recalcula sin el modelo ni "
                                 "la GPU, antes y después de las correcciones de T-256.")
        parser.add_argument("--corridas", default=None,
                            help="Carpeta donde se guarda la corrida (por omisión, "
                                 "corridas/ junto a la lista).")
        parser.add_argument("--commit", default=None, help="Commit del código con que se corre.")
        parser.add_argument("--verificar-esperada", action="store_true",
                            dest="verificar_esperada",
                            help="Solo comprueba la lista contra la lectura; no usa el modelo.")
        parser.add_argument("--verificar-verdad", action="store_true", dest="verificar_verdad",
                            help="Comprueba la verdad celda por celda (con --celdas-comision, o "
                                 "la del caso chico); no usa el modelo.")
        parser.add_argument("--verificador-sobre", default=None, dest="verificador_sobre",
                            help="Carpeta de una corrida ya guardada: le aplica el verificador "
                                 "externo de citas, sin la GPU, y mide sin y con.")
        parser.add_argument("--medicion", default=None,
                            help="Nombre de la medición del libro de pedidos externos (reuso por "
                                 "huella), con --verificador-sobre.")
        parser.add_argument("--verificar-decisiones", action="store_true",
                            dest="verificar_decisiones",
                            help="Corre los tests `decision_literal` y comprueba los campos de "
                                 "la lista; rechaza la medición si algo falla.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        if options["recalcular"]:
            self._recompute(options)
            return
        verify_only = options["verificar_esperada"]
        verify_decisions = options["verificar_decisiones"]
        verify_truth = options["verificar_verdad"]
        esperada = options["esperada"]
        if options["caso_chico"] and not esperada:
            esperada = str(CASO_CHICO / "evaluacion-esperada.yaml")
        if not esperada:
            raise CommandError("Falta --esperada (o --caso-chico).")
        try:
            expected = evaluation.load_expected(
                esperada, require_approval=not (verify_only or verify_decisions or verify_truth))
            if verify_decisions:
                self._verify_decisions(expected)
                return
            fichas = evaluation.load_fichas(options["fichas"]) if options["fichas"] else None
            portal_cells = (evaluation.load_portal_cells(
                options["celdas_portal"], require_approval=not verify_only)
                if options["celdas_portal"] else None)
            if options["caso_chico"]:
                procedure, offers = evaluation.build_case(user, expected)
            else:
                number = options["procedimiento"] or expected.matrix["procedimiento"]
                try:
                    procedure = Procedure.objects.get(number=number)
                except Procedure.DoesNotExist:
                    raise CommandError("No hay un procedimiento con ese número.") from None
                offers = evaluation.resolve_offers(expected, procedure)

            if verify_truth:
                self._verify_truth(options, procedure, expected)
                return

            if verify_only:
                verification = evaluation.verify_expected(expected, offers)
                lines = list(verification.lines)
                cells_ok = True
                if portal_cells:
                    cell_lines, cells_ok = evaluation.verify_portal_cells(portal_cells, procedure)
                    lines += cell_lines
                self.stdout.write("\n".join(lines))
                if not (verification.ok and cells_ok):
                    raise CommandError("La comprobación de la lista encontró fallas.")
                return

            runs_dir = options["corridas"] or str(Path(esperada).resolve().parent / "corridas")
            commission = (evaluation.load_commission_cells(options["celdas_comision"])
                          if options["celdas_comision"] else None)
            exclusions = (evaluation.load_cell_exclusions(options["exclusiones_celdas"])
                          if options["exclusiones_celdas"] else None)
            if options["verificador_sobre"]:
                report = evaluation.measure_verifier(
                    user, procedure, expected, offers, runs_dir, options["verificador_sobre"],
                    measurement=options["medicion"], fichas=fichas, commit=options["commit"],
                    portal_cells=portal_cells, commission_cells=commission,
                    cell_exclusions=exclusions)
            else:
                report = evaluation.measure(user, procedure, expected, offers, runs_dir,
                                            fichas=fichas, commit=options["commit"],
                                            portal_cells=portal_cells,
                                            commission_cells=commission,
                                            cell_exclusions=exclusions)
        except (RoleRejected, evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None

        self._report(report)

    def _recompute(self, options):
        """`--recalcular`: las cifras de una corrida guardada, antes y después de T-256."""
        try:
            portal = (evaluation.load_portal_cells(options["celdas_portal"])
                      if options["celdas_portal"] else None)
            commission = (evaluation.load_commission_cells(options["celdas_comision"],
                                                           require_approval=False)
                          if options["celdas_comision"] else None)
            exclusions = (evaluation.load_cell_exclusions(options["exclusiones_celdas"])
                          if options["exclusiones_celdas"] else None)
            result = evaluation.recompute_run(options["recalcular"], portal_cells=portal,
                                              commission=commission, cell_exclusions=exclusions)
        except (evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None
        text = evaluation.proportion_text
        lines = [f"Corrida recalculada sin el modelo: {Path(result['folder']).name} "
                 f"({result['cells']} celdas; pares ubicados por fila: "
                 f"{'sí' if result['pairs_mapped'] else 'no'})"]
        for moment, label in (("before", "antes"), ("after", "después")):
            figures = result[moment]
            cells = figures["cells"]
            lines += [
                f"[{label}] Coincidencia con el dictamen: {text(figures['match'])}; conclusiones "
                f"erradas: {figures['contradictions']}; «cumple» sin cita: "
                f"{figures['no_citation']}",
                f"[{label}] «No determinado» que cuenta sobre todas las celdas: "
                f"{cells['ratio']['ok']} de {cells['ratio']['total']}; "
                f"«No determinado» sobre las decidibles: {cells['ratio_decidable']['ok']} de "
                f"{cells['ratio_decidable']['total']}; «externo» del modelo que cuenta: "
                f"{cells['model_external']}",
                f"[{label}] Portal «cumple» con su cita: {text(figures['portal_cumple'])}; "
                f"«cumple» con un dato que no coincide: {figures['portal_wrong']}",
                f"[{label}] Filas excluidas: {figures['excluded_cells']} celdas y "
                f"{figures['excluded_pairs']} pares"]
        if exclusions is not None:
            lines.append(evaluation.excluded_rows_line({
                "rows": sorted(exclusions.rows), "motives": exclusions.rows,
                "cells": result["after"]["excluded_cells"],
                "pairs": result["after"]["excluded_pairs"]}).lstrip("- "))
        if commission is not None:
            approval = commission.approval or "visto bueno pendiente"
            for moment, label in (("accuracy_before", "antes"), ("accuracy_after", "después")):
                lines += [f"[{label}] " + line.lstrip("- ")
                          for line in evaluation.accuracy_lines(result[moment])]
            lines.append(f"Lista de la Comisión: huella {commission.fingerprint[:12]}; "
                         f"{approval}")
        # T-285 (H-277-1): la cuenta de las tres salidas sale de las celdas que guarda la evaluación;
        # una corrida guardada no la trae y el recálculo no la inventa.
        lines.append("Tres salidas (REQ-120): no se cuentan al recalcular; las cuenta la corrida de "
                     "medir_evaluacion (las líneas «(016)»).")
        self.stdout.write("\n".join(lines))

    def _verify_truth(self, options, procedure, expected):
        """`--verificar-verdad`: los conteos y las comprobaciones de la verdad de un caso."""
        path = options["celdas_comision"] or (str(CASO_CHICO / evaluation.TRUTH_FILE)
                                              if options["caso_chico"] else None)
        if not path:
            raise CommandError("Falta --celdas-comision (o --caso-chico) con la verdad.")
        truth = evaluation.load_commission_cells(path, require_approval=False)
        check = evaluation.verify_truth(truth, expected, procedure)
        lines = check.lines()
        lines.append(evaluation.truth_total([check])["line"])
        self.stdout.write("\n".join(lines))
        if not check.ok:
            raise CommandError("La comprobación de la verdad encontró fallas.")

    def _verify_decisions(self, expected):
        status, output = evaluation.run_decision_tests(cwd=settings.BASE_DIR)
        lines = [f"Tests decision_literal: {status}", output]
        missing = evaluation.check_fields(expected)
        lines.append("Lista esperada: " + ("trae los campos nuevos" if not missing
                                           else f"faltan {len(missing)} campos"))
        lines += missing
        if status == "ausente":
            lines.append("Ningún test lleva todavía la marca `decision_literal`: se informa, "
                         "no bloquea.")
        self.stdout.write("\n".join(lines))
        if status == "fallo":
            raise CommandError("Un test de las decisiones literales falla: la medición se "
                               "rechaza.")
        if missing:
            raise CommandError("La lista esperada no trae los campos de la regla nueva: la "
                               "medición se rechaza.")

    def _report(self, report):
        total = report.total
        lines = [f"Corrida guardada en {report.folder}"]
        for name in evaluation.LABELS:
            value = total[name]
            shown = (len(value) if name in evaluation.MAXIMUMS
                     else evaluation.proportion_text(value))
            lines.append(f"{evaluation.LABELS[name]}: {shown}")
        lines.append(f"Por resultado: {total['by_outcome']}; evaluación completa "
                     f"{report.seconds} s, {total['model_requests']} pedidos al modelo")
        for name, measured, ok in evaluation.thresholds_015(total, report.expected.case,
                                                            report.video):
            lines.append(f"{name} (015): {measured} · {'cumple' if ok else 'no cumple'}")
        for name, measured, ok in evaluation.thresholds_016(total):
            lines.append(f"{name} (016): {measured} · {'cumple' if ok else 'no cumple'}")
        lines += [line.lstrip("- ") for line in evaluation.verifier_lines(
            total.get(evaluation.VERIFIER_KEY), total.get("verifier_run"))]
        if report.verification is not None:
            lines += [line for line in report.verification.lines if line.startswith("AVISO")]
        failed = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(failed) if failed else "nada"))
        self.stdout.write("\n".join(lines))
