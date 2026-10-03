"""Comando `correr_evals`: corre el conjunto de preguntas y guarda la corrida (P7; REQ-008,
REQ-009, REQ-020, REQ-021; plan 001, "Evals" y "Pantalla, acceso y comandos").

Rol: lectura (el de lectura y escritura lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.queries.evaluation.run`.

Opciones:

- `--casos`: carpeta de los casos `EV-NNN.yaml`; por omisión `evals/casos/`.
- `--corridas`: carpeta donde se crea la de la corrida; por omisión `evals/corridas/`.
- `--commit`: commit del código con que se corre. Dentro del contenedor no hay `.git`,
  así que conviene pasarlo desde el equipo (`git rev-parse --short HEAD`); si falta y
  no se puede averiguar, la carpeta lleva `sin-commit`.

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

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            report = evaluation.run(user, options["casos"], options["corridas"],
                                    commit=options["commit"])
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        except (FileNotFoundError, FileExistsError) as error:
            raise CommandError(str(error)) from None

        lines = [f"Corrida guardada en {report.folder}", evaluation.counts_line(report)]
        if not report.results:
            lines.append(evaluation.NOTHING_RAN)
        lines += [f"{name}: {value} (umbral: {threshold}; cumple: {meets})"
                  for name, value, threshold, meets
                  in evaluation.measure_rows(report.measures)]
        pairs = report.pairs
        failing_pairs = [p for p in pairs if p["status"] != evaluation.PAIR_PASSES]
        lines.append(f"Pares de REQ-020: {len(pairs) - len(failing_pairs)} de "
                     f"{len(pairs)} pasan")
        lines.append(f"Aviso de REQ-021: {report.notices['ok']} de "
                     f"{report.notices['total']} según lo esperado")
        failed = report.failed_ids()
        lines.append("Casos fallados: " + (", ".join(failed) if failed else "ninguno"))
        lines += [f"No corrido: {s.file}: {s.reason}" for s in report.skipped
                  if s.kind != evaluation.NOT_APPROVED]
        self.stdout.write("\n".join(lines))
