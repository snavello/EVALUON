"""Comando `evi_preguntas`: corre las diez preguntas de prueba de «Pregúntele a Evi» contra la IA local real
(T-368; ADR-0082). Imprime, de cada una, la pregunta, la respuesta y el tiempo. Las tres preguntas trampa se
leen a mano: ninguna respuesta puede decidir ni recomendar.

Se corre una vez, de a una pregunta y sin otra medición en curso: comparte el motor con la evaluación.

    python manage.py evi_preguntas [--archivo tests/journey/evi_preguntas.yaml] [--procedimiento ID]

Sin `--procedimiento`, responde solo con la guía (sin estado). No deja registro de auditoría (no es una
persona preguntando) ni escribe nada. Con la IA ocupada o caída, lo dice y sigue.
"""

from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluon.journey.evi import preguntas

DEFAULT_FILE = Path(settings.BASE_DIR) / "tests" / "journey" / "evi_preguntas.yaml"


class Command(BaseCommand):
    help = "Corre las diez preguntas de prueba de Evi contra la IA local e imprime pregunta, respuesta y tiempo."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=str(DEFAULT_FILE), help="El archivo de preguntas (YAML).")
        parser.add_argument("--procedimiento", type=int, default=None,
                            help="Número interno de un procedimiento: suma su estado al contexto.")

    def handle(self, *args, **options):
        archivo = Path(options["archivo"])
        if not archivo.is_file():
            raise CommandError(f"No existe el archivo de preguntas: {archivo}")
        lista = yaml.safe_load(archivo.read_text(encoding="utf-8"))["preguntas"]
        proceso = self._proceso(options["procedimiento"])
        fallas = 0
        for n, item in enumerate(lista, 1):
            resultado = preguntas.preguntar(item["pregunta"], proceso)
            self.stdout.write(f"\n[{n}/{len(lista)}] ({item['tipo']}) {item['pregunta']}")
            if resultado.ok:
                self.stdout.write(resultado.respuesta)
            else:
                fallas += 1
                self.stdout.write(f"SIN RESPUESTA: {resultado.motivo}")
            self.stdout.write(f"-- {resultado.segundos} s · {resultado.modelo} · {resultado.version} · "
                              f"contexto de {resultado.contexto_caracteres} caracteres")
        self.stdout.write(f"\n{len(lista) - fallas} respondidas, {fallas} sin respuesta.")

    def _proceso(self, procedure_id):
        """El `Proceso` del procedimiento, visto por el primer usuario de la Comisión; `None` sin procedimiento."""
        if procedure_id is None:
            return None
        from evaluon.accounts.models import User
        from evaluon.journey.proceso import calculo
        from evaluon.tenders.models import Procedure
        procedure = Procedure.objects.filter(pk=procedure_id).first()
        if procedure is None:
            raise CommandError(f"No hay un procedimiento con el número interno {procedure_id}.")
        usuario = User.objects.filter(is_active=True).exclude(commission_role="").first()
        if usuario is None:
            raise CommandError("No hay un usuario de la Comisión para armar el estado.")
        return calculo.proceso_de(usuario, procedure)
