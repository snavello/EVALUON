"""Comando `medir_tamanos`: mide los tamaños de las ofertas de un procedimiento con el
tokenizador del modelo (plan 004, "Qué se lee y cómo se agrupa"; ADR-0037; T-148).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide
por teclado. Solo traduce y llama a `evaluon.assessment.sizing`.

Por oferta: páginas, tokens por documento y por página, documentos de texto idéntico y
cuántos grupos salen con `ASSESSMENT_GROUP_TOKENS` en orden de carga. Informa además el
contexto real del motor de lotes y la memoria de video usada (los mismos datos que se
registran con una evaluación).

- `--procedimiento`: número del procedimiento con sus ofertas ya cargadas y leídas.
- `--corridas`: carpeta (fuera del repositorio) donde se guarda el detalle por documento y
  por página, en `<carpeta>/<fecha>/tamanos.json`. Sin ella, no se guarda nada. En pantalla
  salen solo las cuentas por oferta, las que pueden ir al repositorio.
- `--presupuesto`: tokens por grupo, si no es `ASSESSMENT_GROUP_TOKENS`.

No usa el modelo para generar: solo su tokenizador. No guarda nada en la base.
"""

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import sizing
from evaluon.tenders.evaluation import video_memory
from evaluon.tenders.models import Procedure


class Command(BaseCommand):
    help = "Mide los tamaños de las ofertas de un procedimiento con el tokenizador del modelo."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--procedimiento", required=True, help="Número del procedimiento.")
        parser.add_argument("--corridas", default=None,
                            help="Carpeta donde se guarda el detalle por documento "
                                 "(fuera del repositorio).")
        parser.add_argument("--presupuesto", type=int, default=None,
                            help="Tokens por grupo (por omisión, ASSESSMENT_GROUP_TOKENS).")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            permissions.require_commission_role(
                user, "operator", operation="medir_tamanos")
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        try:
            procedure = Procedure.objects.get(number=options["procedimiento"])
        except Procedure.DoesNotExist:
            raise CommandError("No hay un procedimiento con ese número.") from None
        budget = options["presupuesto"] or settings.ASSESSMENT_GROUP_TOKENS
        offers = list(procedure.offers.order_by("number"))
        if not offers:
            raise CommandError("El procedimiento no tiene ofertas cargadas.")

        measures = [sizing.measure_offer(offer, budget=budget) for offer in offers]
        engine = {"context_configured": settings.GENERATION_BATCH_CONTEXT_TOKENS,
                  "context_real": sizing.engine_context(),
                  "video_memory": video_memory()}

        lines = [f"Procedimiento {procedure.number}; presupuesto {budget} tokens por grupo; "
                 f"contexto del motor de lotes: configurado "
                 f"{engine['context_configured']}, real {engine['context_real']}."]
        for position, measure in enumerate(measures, start=1):
            lines.append(
                f"Oferta {position} (número {offers[position - 1].number}): "
                f"{measure['documents_count']} documentos "
                f"({measure['copies']} copias de texto idéntico, "
                f"{measure['without_reading']} sin lectura), {measure['pages']} páginas, "
                f"{measure['unread_pages']} sin leer, {measure['tokens']} tokens "
                f"({measure['tokens_with_copies']} con las copias), documento mayor "
                f"{measure['largest_document_tokens']}, {measure['groups']} grupo(s) "
                f"{measure['group_tokens']}"
                + (f", partidos en ventanas: {len(measure['windowed'])}"
                   if measure["windowed"] else "") + ".")
        memory = engine["video_memory"]
        lines.append("Memoria de video: " + (
            f"{memory['used_mib']} de {memory['total_mib']} MiB." if memory["available"]
            else f"no disponible ({memory['reason']})."))

        if options["corridas"]:
            folder = Path(options["corridas"]) / datetime.now().strftime("%Y%m%d-%H%M%S")
            folder.mkdir(parents=True, exist_ok=True)
            detail = {"procedure": procedure.number, "budget": budget, "engine": engine,
                      "offers": measures}
            (folder / "tamanos.json").write_text(
                json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")
            lines.append(f"Detalle guardado en {folder}")
        self.stdout.write("\n".join(lines))
