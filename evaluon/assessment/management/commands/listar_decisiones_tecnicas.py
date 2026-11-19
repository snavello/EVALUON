"""Comando `listar_decisiones_tecnicas`: imprime las decisiones guardadas sobre filas técnicas por
renglón y cierra con «Total: N» (REQ-162; plan 019; T-365).

Solo lee: no escribe en la base ni deja hecho de auditoría, y por eso no pide ingreso. Su salida
es material reservado cuando corre sobre datos reales. Solo traduce y llama a
`evaluon.assessment.services.technical_decisions`.
"""

from django.core.management.base import BaseCommand

from evaluon.assessment.services import technical_decisions


class Command(BaseCommand):
    help = "Lista las decisiones guardadas sobre filas técnicas por renglón (solo lectura)."

    def handle(self, *args, **options):
        rows = technical_decisions.technical_row_decisions()
        for row in rows:
            self.stdout.write(
                f"Procedimiento {row.procedure_number} · oferta {row.offer_number} "
                f"({row.bidder}) · requisito {row.requirement_number} "
                f"(renglón {', '.join(str(i) for i in row.items)}) · {row.action} · "
                f"{row.username} · {row.at.isoformat(timespec='seconds')}")
        self.stdout.write(f"Total: {len(rows)}")
