"""Comando `correr_evals`: corre el conjunto de preguntas y guarda la corrida (P7; REQ-008,
REQ-009, REQ-020, REQ-021; plan 001, "Evals" y "Pantalla, acceso y comandos").

Rol: lectura (el de lectura y escritura lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.queries.evaluation.run` o, con
`--recalificar`, a `evaluon.queries.evaluation.rescore`.

Opciones:

- `--casos`: carpeta de los casos `EV-NNN.yaml`; por omisión `evals/casos/`.
- `--corridas`: carpeta donde se crea la de la corrida; por omisión `evals/corridas/`.
- `--commit`: commit del código con que se corre. Dentro del contenedor no hay `.git`,
  así que conviene pasarlo desde el equipo (`git rev-parse --short HEAD`); si falta y
  no se puede averiguar, la carpeta lleva `sin-commit`.
- `--quitando-piezas`: corre además la comparación quitando piezas (ADR-0003: solo
  vectores, solo palabras, combinada sin reranker, completa). Se corre una vez.
- `--recalificar <carpeta de corrida>`: no corre nada; vuelve a medir esa corrida
  guardada con los casos de `--casos` y el corrector vigente, sin consultar ni llamar a
  los servicios de IA, y guarda una carpeta nueva terminada en `_recalificada` en
  `--corridas` (T-058; plan, "Recalificar una corrida guardada"). La carpeta original no
  se modifica. No se combina con `--quitando-piezas`.

El comando muestra las medidas exigidas con su margen de error: la cita literal y el
tiempo de toda la corrida, la respuesta correcta y la abstención del lote de aceptación,
y avisa si la corrida no tiene casos de ese lote (T-060; ADR-0014, punto 1). La corrida
se compara sola con la anterior de la carpeta de corridas, lote por lote, y propone el
umbral del reranker (provisorio) con la regla del hueco (ADR-0014, punto 2): el comando
muestra la misma línea que `resumen.md`, pero no cambia `settings.py`. Una
recalificación se compara con la corrida que recalifica.

Si ningún caso está bien formado y con visto bueno, no se corre ninguno, se dice así y
la corrida queda guardada igual, con las medidas sin valor.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.queries import evaluation


class Command(BaseCommand):
    help = "Corre el conjunto de preguntas de las evals y guarda la corrida."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument(
            "--casos",
            default=str(Path(settings.BASE_DIR) / "evals" / "casos"),
            help="Carpeta de los casos EV-NNN.yaml (por omisión, evals/casos).",
        )
        parser.add_argument(
            "--corridas",
            default=str(Path(settings.BASE_DIR) / "evals" / "corridas"),
            help="Carpeta donde se guarda la corrida (por omisión, evals/corridas).",
        )
        parser.add_argument(
            "--commit",
            default=None,
            help="Commit del código con que se corre (por ejemplo, la salida de "
                 "`git rev-parse --short HEAD`).",
        )
        parser.add_argument(
            "--quitando-piezas",
            action="store_true",
            dest="quitando_piezas",
            help="Corre además la comparación quitando piezas (solo vectores, solo "
                 "palabras, combinada sin reranker, completa).",
        )
        parser.add_argument(
            "--recalificar",
            default=None,
            metavar="CARPETA",
            help="No corre nada: vuelve a medir la corrida guardada en esa carpeta con "
                 "los casos de --casos, sin consultar, y guarda una carpeta nueva "
                 "terminada en _recalificada.",
        )

    def handle(self, *args, **options):
        source = options["recalificar"]
        if source and options["quitando_piezas"]:
            raise CommandError("--recalificar no se combina con --quitando-piezas: "
                               "recalificar no recupera ni consulta.")
        user = permissions.authenticate_command(options["usuario"])
        try:
            if source:
                report = evaluation.rescore(user, source, options["casos"],
                                            options["corridas"], commit=options["commit"])
            else:
                report = evaluation.run(user, options["casos"], options["corridas"],
                                        commit=options["commit"],
                                        ablation=options["quitando_piezas"])
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        except (FileNotFoundError, FileExistsError) as error:
            raise CommandError(str(error)) from None

        if source:
            saved = (f"Recalificación de {Path(source).name} guardada en {report.folder} "
                     "(no se hicieron consultas)")
        else:
            saved = f"Corrida guardada en {report.folder}"
        lines = [saved, evaluation.counts_line(report)]
        if not report.results:
            lines.append(evaluation.NOTHING_RAN)
        lines += [f"{name}: {value} (umbral: {threshold}; cumple: {meets})"
                  for name, value, threshold, meets
                  in evaluation.measure_rows(report.measures)]
        if not report.measures["acceptance_cases"]:
            lines.append(evaluation.ACCEPTANCE_MISSING)
        pairs = report.pairs
        failing_pairs = [p for p in pairs if p["status"] != evaluation.PAIR_PASSES]
        lines.append(f"Pares de REQ-020: {len(pairs) - len(failing_pairs)} de "
                     f"{len(pairs)} pasan")
        lines.append(f"Aviso de REQ-021: {report.notices['ok']} de "
                     f"{report.notices['total']} según lo esperado")
        lines.append(evaluation.threshold_line(report.calibration)
                     + " (no cambia la configuración del sistema)")
        lines += evaluation.comparison_lines(report.comparison)
        failed = report.failed_ids()
        lines.append("Casos fallados: " + (", ".join(failed) if failed else "ninguno"))
        lines += [f"No corrido: {s.file}: {s.reason}" for s in report.skipped
                  if s.kind != evaluation.NOT_APPROVED]
        self.stdout.write("\n".join(lines))
