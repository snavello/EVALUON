"""Comando `procesar_pedidos`: atiende la cola de pedidos en segundo plano (plan 003,
"Componentes"; ADR-0018). Lo corre el servicio `worker`.

Al arrancar pasa a `failed` "interrumpido" los pedidos que quedaron `running`. Después
toma los pedidos de a uno, en orden de llegada, y los ejecuta con el manejador de su
tipo; con la cola vacía espera `WORKER_POLL_SECONDS` y vuelve a mirar. Con
`--hasta-vaciar` termina cuando no quedan pedidos en espera.

La orden de detenerse (`docker compose stop`, Ctrl-C) corta el pedido en curso, que queda
`failed` "interrumpido", y termina. Solo traduce y llama a `evaluon.tenders.jobs`.
"""

import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from evaluon.tenders import jobs


def _stop(signum, frame):
    raise SystemExit(0)


class Command(BaseCommand):
    help = "Atiende los pedidos en segundo plano (leer documentos, proponer matrices)."

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
        interrupted = jobs.fail_interrupted()
        if interrupted == 1:
            self._say("1 pedido interrumpido pasó a fallido.")
        elif interrupted:
            self._say(f"{interrupted} pedidos interrumpidos pasaron a fallidos.")
        self._say("Esperando pedidos.")
        while True:
            job = jobs.run_next()
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
