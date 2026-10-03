"""Comando `crear_usuario`: alta de un usuario con su rol (REQ-016, REQ-012; plan 001,
"Pantalla, acceso y comandos"; ADR-0005).

Lo corre quien administra el equipo, sin rol de EVALUON. La clave se pide por teclado
dos veces, sin mostrarla; no se pasa como argumento ni se guarda en forma legible. El
alta queda registrada como hecho `user_created`, sin usuario actuante.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from evaluon.accounts import permissions
from evaluon.accounts.models import Role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome

# Nombre del rol tal como lo escribe quien da el alta.
ROLES = {
    "lectura": Role.READ,
    "lectura-escritura": Role.READ_WRITE,
}


def password_problems(error):
    """Mensajes del validador de claves en lenguaje llano, con la palabra "clave"."""
    messages = []
    for item in error.error_list:
        if item.code == "password_too_short":
            messages.append(
                "La clave es demasiado corta: tiene que tener al menos "
                f"{item.params['min_length']} caracteres."
            )
        else:
            # Otros validadores, si se agregan: el texto de Django dice "contraseña".
            text = " ".join(item.messages)
            messages.append(
                text.replace("contraseña", "clave").replace("Contraseña", "Clave")
            )
    return " ".join(messages)


class Command(BaseCommand):
    help = (
        "Da de alta un usuario de EVALUON con su rol. La clave se pide por teclado, "
        "dos veces, y no se muestra."
    )

    def add_arguments(self, parser):
        parser.add_argument("usuario", help="Nombre del usuario nuevo.")
        parser.add_argument(
            "--rol",
            required=True,
            choices=sorted(ROLES),
            help=(
                "lectura: consulta y busca. lectura-escritura: además carga y valida "
                "normas y registra relaciones y versiones."
            ),
        )

    def handle(self, *args, **options):
        username = options["usuario"]
        role = ROLES[options["rol"]]
        User = get_user_model()

        username = User.normalize_username(username)
        try:
            User._meta.get_field("username").run_validators(username)
        except ValidationError:
            raise CommandError(
                "El nombre de usuario solo puede tener letras, números y los signos "
                "@ . + - _"
            ) from None
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Ya existe un usuario con el nombre {username}.")

        password = permissions.read_password("Clave del usuario nuevo: ")
        if permissions.read_password("Repita la clave: ") != password:
            raise CommandError("Las dos claves no coinciden. No se dio de alta el usuario.")
        try:
            validate_password(password, User(username=username, role=role))
        except ValidationError as error:
            raise CommandError(
                f"{password_problems(error)} No se dio de alta el usuario."
            ) from None

        with transaction.atomic():
            user = User.objects.create_user(
                username=username, password=password, role=role
            )
            audit.record(
                EventType.USER_CREATED,
                outcome=Outcome.OK,
                channel=Channel.COMMAND,
                detail={
                    "created_user": user.username,
                    "created_user_id": user.pk,
                    "role": user.role,
                },
            )

        self.stdout.write(
            f"Se dio de alta el usuario {user.username} con rol de "
            f"{Role(role).label.lower()}."
        )
