"""Comando `listar_decisiones_tecnicas`: imprime las decisiones guardadas sobre filas técnicas por
renglón y cierra con «Total: N» (REQ-162; plan 019; T-365).

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide por
teclado. Solo lee decisiones: no escribe ni cambia nada; el único hecho que deja es el de ingreso
por comando, como los demás comandos de gestión. Sin rol o con clave mala no imprime nada del
listado. Su salida es material reservado cuando corre sobre datos reales. Solo traduce y llama a
`evaluon.assessment.services.technical_decisions`.
"""

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import RoleRejected, require_commission_role

from evaluon.assessment.services import technical_decisions


class Command(BaseCommand):
    help = "Lista las decisiones guardadas sobre filas técnicas por renglón (solo lectura)."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            require_commission_role(user, CommissionRole.OPERATOR,
                                    operation="listar_decisiones_tecnicas")
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        rows = technical_decisions.technical_row_decisions()
        for row in rows:
            self.stdout.write(
                f"Procedimiento {row.procedure_number} · oferta {row.offer_number} "
                f"({row.bidder}) · requisito {row.requirement_number} "
                f"(renglón {', '.join(str(i) for i in row.items)}) · {row.action} · "
                f"{row.username} · {row.at.isoformat(timespec='seconds')}")
        self.stdout.write(f"Total: {len(rows)}")
