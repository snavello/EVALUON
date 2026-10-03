"""Tabla `audit_event`: una fila por hecho registrado (REQ-012, P6; plan 001, "Modelo de
datos" y "Registro de auditoría").

Solo se insertan filas: un hecho registrado no se modifica ni se borra desde la
aplicación. El registro no guarda claves ni identificadores de sesión.
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class EventType(models.TextChoices):
    LOAD = "load", "Carga"
    REREAD = "reread", "Relectura"
    VALIDATION = "validation", "Validación"
    RELATION = "relation", "Relación"
    VERSION = "version", "Versión"
    PENDING_AMENDMENT = "pending_amendment", "Modificatorias sin cargar"
    QUERY = "query", "Consulta"
    SEARCH = "search", "Búsqueda"
    LOGIN = "login", "Ingreso"
    LOGIN_FAILED = "login_failed", "Ingreso fallido"
    REJECTED = "rejected", "Operación rechazada por rol"
    USER_CREATED = "user_created", "Alta de usuario"


class Outcome(models.TextChoices):
    OK = "ok", "Hecho"
    REJECTED = "rejected", "Rechazado"
    FAILED = "failed", "Fallido"


class Channel(models.TextChoices):
    SCREEN = "screen", "Pantalla"
    COMMAND = "command", "Comando"
    EVAL = "eval", "Evaluación"


class AuditEvent(models.Model):
    occurred_at = models.DateTimeField("momento", default=timezone.now, db_index=True)
    event_type = models.CharField("hecho", max_length=20, choices=EventType.choices)
    outcome = models.CharField("resultado", max_length=10, choices=Outcome.choices)
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    # Usuario que actuó; vacío en un ingreso fallido o en un alta hecha por quien
    # administra el equipo. PROTECT: un usuario con hechos registrados no se borra.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    # Nombre tal como se escribió; sirve cuando no hay usuario.
    username = models.CharField("nombre escrito", max_length=150, blank=True)
    # Número de versión de la normativa vigente en ese momento; lo completa T-008.
    corpus_version = models.PositiveIntegerField(
        "versión de la normativa", null=True, blank=True
    )
    detail = models.JSONField("detalle", default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        db_table = "audit_event"
        verbose_name = "hecho registrado"
        verbose_name_plural = "hechos registrados"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event_type__in=EventType.values),
                name="audit_event_event_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=Outcome.values),
                name="audit_event_outcome_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=Channel.values),
                name="audit_event_channel_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Un hecho registrado no se modifica.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Un hecho registrado no se borra.")

    def __str__(self):
        return f"{self.occurred_at:%Y-%m-%d %H:%M:%S} {self.event_type} {self.outcome}"
