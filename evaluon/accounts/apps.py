"""Usuarios, roles, ingreso y salida (REQ-016), con el registro de los ingresos
(REQ-012; T-038).

Al arrancar conecta dos señales de Django:

- `user_logged_in` (ingreso por pantalla): deja el hecho `login` con el usuario y el
  canal `screen`. El ingreso por comando no pasa por esta señal; su `login` lo deja
  `permissions.authenticate_command`.
- `user_login_failed` (clave incorrecta, usuario inexistente o dado de baja): deja el
  hecho `login_failed` con el nombre tal como se escribió y el canal, sin usuario. El
  canal es `screen` si la autenticación vino con un pedido web y `command` si no: la
  única autenticación sin pedido es la de los comandos. De las credenciales solo se
  toma el nombre; la clave (que Django ya entrega enmascarada) no se lee.

Ninguno de los dos hechos guarda el identificador de sesión.
"""

from django.apps import AppConfig

# Largo del campo `audit_event.username`.
_USERNAME_MAX_LENGTH = 150


def record_login(sender, request, user, **kwargs):
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, EventType, Outcome

    audit.record(EventType.LOGIN, outcome=Outcome.OK, channel=Channel.SCREEN, user=user)


def record_login_failed(sender, credentials, request=None, **kwargs):
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, EventType, Outcome

    username = str(credentials.get("username") or "")[:_USERNAME_MAX_LENGTH]
    audit.record(
        EventType.LOGIN_FAILED,
        outcome=Outcome.FAILED,
        channel=Channel.SCREEN if request is not None else Channel.COMMAND,
        username=username,
    )


class AccountsConfig(AppConfig):
    name = "evaluon.accounts"
    label = "accounts"
    verbose_name = "Usuarios"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        user_logged_in.connect(record_login, dispatch_uid="evaluon_record_login")
        user_login_failed.connect(
            record_login_failed, dispatch_uid="evaluon_record_login_failed"
        )
