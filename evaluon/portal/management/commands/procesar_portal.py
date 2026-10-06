"""Comando `procesar_portal`: atiende los pedidos del Portal de Compras (plan 012,
"Componentes"; ADR-0031). Lo corre el servicio `portal_worker`, el único con salida a
internet.

Igual que `procesar_pedidos`, pero solo de los tipos `portal_explore` y `portal_review`: al
arrancar pasa a `failed` "interrumpido" solo los suyos que quedaron `running`, y no toma
nunca un pedido del `worker`. En cada vuelta, antes de tomar un pedido, encola las revisiones
diarias que corresponden (`schedule.enqueue_due`, ADR-0033). Con la cola vacía espera
`WORKER_POLL_SECONDS`; con `--hasta-vaciar` termina cuando no quedan pedidos en espera.

La orden de detenerse (`docker compose stop`, Ctrl-C) corta el pedido en curso, que queda
`failed` "interrumpido", y termina. Solo traduce y llama a `evaluon.tenders.jobs`.
"""

import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from evaluon.portal.services import schedule
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS


def _stop(signum, frame):
    raise SystemExit(0)


class Command(BaseCommand):
    clock = staticmethod(timezone.now)  # los tests lo reemplazan por un reloj falso

    help = "Atiende los pedidos del Portal de Compras (explorar y revisar un proceso)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hasta-vaciar",
            action="store_true",
            help="Termina cuando no quedan pedidos en espera, en lugar de seguir esperando.",
        )

    def handle(self, *args, **options):
        previous = signal.signal(signal.SIGTERM, _stop)
        try:
            self._loop(options["hasta_vaciar"])
        except (KeyboardInterrupt, SystemExit):
            self._say("Detenido.")
        finally:
            signal.signal(signal.SIGTERM, previous)

    def _loop(self, until_empty):
        interrupted = jobs.fail_interrupted(kinds=PORTAL_JOB_KINDS)
        if interrupted == 1:
            self._say("1 pedido interrumpido pasó a fallido.")
        elif interrupted:
            self._say(f"{interrupted} pedidos interrumpidos pasaron a fallidos.")
        self._say("Esperando pedidos del Portal.")
        while True:
            for review in schedule.enqueue_due(self.clock()):
                self._say(f"Revisión pedida para el enlace {review.target_id} (pedido {review.pk}).")
            job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
            if job is not None:
                line = f"Pedido {job.pk} ({job.kind}): {job.status}"
                self._say(f"{line}. {job.error}" if job.error else f"{line}.")
            elif until_empty:
                return
            else:
                time.sleep(settings.WORKER_POLL_SECONDS)

    def _say(self, text):
        self.stdout.write(text)
        self.stdout.flush()
