"""Comando `rol_comision`: cambia el rol de la Comisión de un usuario existente (T-088;
REQ-026; plan 003, "Roles").

    manage.py rol_comision <usuario> {operador,evaluador,ninguno} --usuario <quien cambia>

Quien cambia el rol se identifica como en los demás comandos: `--usuario` y la clave por
teclado, sin mostrarla. Tiene que tener rol de lectura y escritura. El cambio deja el
hecho `user_role_changed` con quién lo hizo, el usuario afectado y el valor de antes y de
después. Un usuario inexistente o un valor inválido se rechazan sin cambiar nada.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from evaluon.accounts import permissions
from evaluon.accounts.models import CommissionRole, Role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome

from .crear_usuario import COMMISSION_ROLES

VALUES = {**COMMISSION_ROLES, "ninguno": CommissionRole.NONE}


class Command(BaseCommand):
    help = (
        "Cambia el rol de la Comisión de un usuario existente y deja el cambio "
        "registrado. La clave de quien cambia se pide por teclado."
    )

    def add_arguments(self, parser):
        # `metavar` evita el choque de nombre con `--usuario` (quien cambia).
        parser.add_argument("afectado", metavar="usuario", help="Usuario a cambiar.")
        parser.add_argument(
            "rol",
            choices=sorted(VALUES),
            help="operador, evaluador o ninguno (quita el rol de la Comisión).",
        )
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        target_name = options["afectado"]
        value = options["rol"]
        if value not in VALUES:
            # `call_command` no controla los argumentos posicionales.
            raise CommandError(
                f"El rol tiene que ser {', '.join(sorted(VALUES))}. No se cambió nada."
            )
        User = get_user_model()
        username = User.normalize_username(target_name)
        if not User.objects.filter(username=username).exists():
            raise CommandError(f"No existe el usuario {target_name}. No se cambió nada.")

        actor = permissions.authenticate_command(options["usuario"])
        permissions.require_role(actor, Role.READ_WRITE)

        new_role = VALUES[value]
        with transaction.atomic():
            target = User.objects.select_for_update().get(username=username)
            old_role = target.commission_role
            target.commission_role = new_role
            target.save(update_fields=["commission_role"])
            audit.record(
                EventType.USER_ROLE_CHANGED,
                outcome=Outcome.OK,
                channel=Channel.COMMAND,
                user=actor,
                detail={
                    "changed_user": target.username,
                    "changed_user_id": target.pk,
                    "commission_role_before": old_role,
                    "commission_role_after": new_role,
                    "command": "rol_comision",
                },
            )
        label = CommissionRole(new_role).label.lower() if new_role else "ninguno"
        self.stdout.write(
            f"El rol de la Comisión de {target.username} es ahora: {label}."
        )
