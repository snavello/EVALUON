"""Comando `medir_portal`: mide la importación del Portal con las páginas guardadas, sin
conexión (REQ-045 a REQ-051; plan 012, "Medición"; ADR-0025; T-145).

Rol: evaluador de la Comisión (aprueba lo propuesto para comprobar la carga). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.portal.evaluation`.

Opciones:

- `--caso`: carpeta de un caso (con `portal/` y `esperado/portal-esperado.yaml`); se puede
  repetir. Ejemplo: `--caso /casos/caso-00 --caso /casos/caso-05`.
- `--corridas`: carpeta donde se guarda la corrida.
- `--commit`: commit del código con que se corre (dentro del contenedor no hay `.git`).

Sin `--en-vivo` no abre ninguna conexión: el transporte sirve los archivos guardados.
`--en-vivo` es la pasada única con el enlace real: solo se corre desde `portal_worker` (único
servicio con salida), una vez y con el Coordinador presente. Cada escenario se
deshace al terminar, así que la base queda como estaba.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.portal import evaluation


class Command(BaseCommand):
    help = "Mide la importación del Portal con las páginas guardadas (sin conexión)."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--caso", action="append", required=True, dest="casos",
                            help="Carpeta de un caso (se puede repetir).")
        parser.add_argument("--corridas", required=True,
                            help="Carpeta donde se guarda la corrida.")
        parser.add_argument("--en-vivo", action="store_true", dest="en_vivo",
                            help="Pasada única con el enlace real (solo desde portal_worker, con el "
                                 "Coordinador presente): compara lo que sirve el Portal ahora.")
        parser.add_argument("--commit", default=None,
                            help="Commit del código con que se corre.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            report = evaluation.measure(user, options["casos"], options["corridas"],
                                        commit=options["commit"], live=options["en_vivo"])
        except (RoleRejected, evaluation.ExpectedError, evaluation.MeasurementRefused) as error:
            raise CommandError(str(error)) from None
        lines = [f"Corrida guardada en {report.folder}"]
        for expected, result in report.cases:
            lines.append(f"{expected.case} (visto bueno: {expected.approval or '—'})")
            for name in evaluation.MEASURES:
                lines.append(f"  {evaluation.LABELS[name]}: "
                             f"{evaluation.proportion_text(result.ratio(name))}")
        failed = report.blocking
        lines.append("Bloquea la aceptación: " + ("; ".join(failed) if failed else "nada"))
        self.stdout.write("\n".join(lines))
