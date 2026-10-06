"""Comando `evaluar_ofertas`: pide y corre la evaluación de las ofertas de un procedimiento
(REQ-052 a REQ-055, REQ-059; plan 004, "Pedido" y "Medición"; ADR-0037 a ADR-0039; T-150).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.assessment.services.evaluate`.

- `--procedimiento`: número del procedimiento, con su matriz validada y sus ofertas leídas.
- `--oferta` (repetible): número de la oferta; sin ella, todas.
- `--requisito` (repetible): número del requisito en la matriz validada; sin él, todos.

Pide la evaluación (el pedido queda registrado como cualquier otro, con su hecho
`eval_request`) y la corre acá mismo, sin esperar al `worker`, en el canal `eval`: cada oferta
queda guardada al terminar. Informa el resultado de cada par. Se corre de a una evaluación,
sin otra carga en la GPU (ADR-0025).
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment.models import Channel as RunChannel
from evaluon.assessment.models import Result
from evaluon.assessment.services import evaluate
from evaluon.audit.models import Channel
from evaluon.tenders import jobs
from evaluon.tenders.models import Job, JobStatus, Procedure
from evaluon.tenders.services.validation import latest_validated


class Command(BaseCommand):
    help = "Pide y corre la evaluación de las ofertas de un procedimiento."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")
        parser.add_argument("--oferta", action="append", type=int, default=None,
                            help="Número de una oferta (se puede repetir); sin ella, todas.")
        parser.add_argument("--requisito", action="append", type=int, default=None,
                            help="Número de un requisito de la matriz validada (se puede "
                                 "repetir); sin él, todos.")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        offers = self._offers(procedure, options["oferta"])
        requirements = self._requirements(procedure, options["requisito"])
        try:
            requested = evaluate.request_evaluation(
                user, procedure, offers=offers, requirements=requirements,
                channel=Channel.EVAL)
        except (RoleRejected, evaluate.EvaluationRefused) as error:
            raise CommandError(str(error)) from None

        job = requested.job
        taken = Job.objects.filter(pk=job.pk, status=JobStatus.QUEUED).update(
            status=JobStatus.RUNNING, started_at=timezone.now())
        if not taken:
            raise CommandError("Otro proceso tomó el pedido: espere a que termine.")
        job.refresh_from_db()
        failure = None
        try:
            evaluate.execute(requested.request, user, channel=RunChannel.EVAL,
                             audit_channel=Channel.EVAL, job=job)
        except Exception as error:  # noqa: BLE001 - se informa y el pedido queda fallido
            failure = error
            jobs.fail(job, f"{type(error).__name__}: {error}")
        else:
            jobs.finish(job)

        self._report(requested.request)
        if failure is not None:
            raise CommandError(f"La evaluación no terminó: {failure}")

    @staticmethod
    def _offers(procedure, numbers):
        if numbers is None:
            return None
        found = {o.number: o for o in procedure.offers.filter(number__in=numbers)}
        missing = [n for n in numbers if n not in found]
        if missing:
            raise CommandError(f"No hay oferta con el número {missing[0]}.")
        return [found[n] for n in numbers]

    @staticmethod
    def _requirements(procedure, numbers):
        if numbers is None:
            return None
        version = latest_validated(procedure)
        if version is None:
            return None  # el pedido se rechaza con su motivo
        found = {r.number: r for r in version.requirements.filter(number__in=numbers)}
        missing = [n for n in numbers if n not in found]
        if missing:
            raise CommandError(f"No hay requisito {missing[0]} en la matriz validada.")
        return [found[n] for n in numbers]

    def _report(self, request):
        lines = []
        results = (Result.objects.filter(run__request=request)
                   .select_related("offer", "requirement", "run")
                   .order_by("offer__number", "requirement__number"))
        for result in results:
            doubt = f" ({result.get_doubt_display()})" if result.doubt else ""
            cites = result.citations.filter(kind="oferta").count()
            lines.append(f"Oferta {result.offer.number} · requisito "
                         f"{result.requirement.number}: {result.get_outcome_display()}"
                         f"{doubt}; citas de la oferta: {cites}")
        for run in request.runs.order_by("offer__number"):
            lines.append(f"Oferta {run.offer.number}: evaluación {run.number}, "
                         f"{run.counts.get('model_requests', 0)} pedidos al modelo, "
                         f"{run.timings.get('total_seconds', 0)} s, "
                         f"por resultado {run.counts.get('by_outcome', {})}, "
                         f"preguntas {run.counts.get('questions', 0)}")
        self.stdout.write("\n".join(lines))
