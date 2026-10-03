"""Tabla `queries_query`: detalle de cada consulta en lenguaje natural (REQ-012, P6;
plan 001, "Modelo de datos", sección `queries`, "Forma de la respuesta" y "Registro de
auditoría").

La fila se inserta una vez, al terminar la consulta, y apunta a su hecho `query` de
`audit_event`. Como `audit_event` solo admite inserciones, el hecho se registra completo
antes que esta fila, dentro de la misma transacción (T-019). Esta fila tampoco se
modifica ni se borra: un trigger de la base lo rechaza (migración `0002_insert_only`).

Los estados y motivos son los de "Forma de la respuesta". Las columnas JSON guardan lo
que arma la función de consulta (T-019, T-040); su forma interna la definen esas tareas,
salvo `result`, que tiene la forma de "Forma de la respuesta".
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Status(models.TextChoices):
    """Resultado de la consulta."""

    GROUNDED = "grounded", "Con fundamento"
    UNDETERMINED = "undetermined", "No determinado"
    ERROR = "error", "Falla técnica"


class Reason(models.TextChoices):
    """Motivo de un "no determinado" o de una falla técnica. Una respuesta con fundamento
    no lleva motivo (`reason` vacío)."""

    # No determinado (plan, "Abstención").
    NO_REGIME_AT_DATE = "no_regime_at_date", "Sin régimen a la fecha"
    BELOW_THRESHOLD = "below_threshold", "Nada pertinente"
    MODEL_ABSTAINED = "model_abstained", "El modelo se abstuvo"
    INVALID_CITATION = "invalid_citation", "Cita inválida"
    # Falla técnica.
    TIMEOUT = "timeout", "Espera agotada"
    SERVICE_UNAVAILABLE = "service_unavailable", "Servicio que no responde"
    INVALID_OUTPUT = "invalid_output", "Salida inválida"
    INPUT_TOO_LONG = "input_too_long", "Pedido que no entra en el contexto"


UNDETERMINED_REASONS = [
    Reason.NO_REGIME_AT_DATE,
    Reason.BELOW_THRESHOLD,
    Reason.MODEL_ABSTAINED,
    Reason.INVALID_CITATION,
]
ERROR_REASONS = [
    Reason.TIMEOUT,
    Reason.SERVICE_UNAVAILABLE,
    Reason.INVALID_OUTPUT,
    Reason.INPUT_TOO_LONG,
]


class Query(models.Model):
    """Una fila por consulta terminada, en cualquiera de sus tres estados."""

    # Hecho `query` de `audit_event` que corresponde a esta consulta; uno por consulta.
    event = models.OneToOneField(
        "audit.AuditEvent",
        verbose_name="hecho registrado",
        on_delete=models.PROTECT,
        related_name="query",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.PROTECT,
        related_name="queries",
    )
    asked_at = models.DateTimeField("consultada", default=timezone.now, db_index=True)
    question = models.TextField("pregunta")
    # Fecha de autorización del procedimiento para la que se consultó (REQ-020).
    reference_date = models.DateField("fecha de autorización del procedimiento")
    # Número de versión de la normativa vigente, como en `audit_event.corpus_version`;
    # vacío si todavía no había ninguna.
    corpus_version = models.PositiveIntegerField(
        "versión de la normativa", null=True, blank=True
    )
    status = models.CharField("resultado", max_length=20, choices=Status.choices)
    reason = models.CharField(
        "motivo", max_length=30, choices=Reason.choices, blank=True
    )
    # Copia de todos los parámetros usados.
    parameters = models.JSONField(
        "parámetros", default=dict, encoder=DjangoJSONEncoder
    )
    # Cada candidato con su camino de entrada, su puntaje y el origen de su texto.
    candidates = models.JSONField(
        "candidatos", default=list, encoder=DjangoJSONEncoder
    )
    # Unidades enviadas al modelo, agregadas por relación y dejadas afuera por espacio.
    selected = models.JSONField(
        "unidades seleccionadas", default=dict, encoder=DjangoJSONEncoder
    )
    # Puntaje más alto del reranker, entre 0 y 1; vacío si no se llegó a puntuar.
    max_score = models.FloatField("puntaje más alto", null=True, blank=True)
    # Versión de las instrucciones; vacía si no se llamó al modelo.
    prompt_version = models.CharField(
        "versión de las instrucciones", max_length=50, blank=True
    )
    # Pedido completo enviado al motor; vacío si no se llamó al modelo.
    request = models.JSONField(
        "pedido", null=True, blank=True, encoder=DjangoJSONEncoder
    )
    # Lo que devolvió el modelo, sin tocar: texto, porque puede no ser un JSON válido.
    raw_output = models.TextField("salida sin tocar", blank=True)
    # Respuesta validada, con la forma de "Forma de la respuesta".
    result = models.JSONField("resultado guardado", encoder=DjangoJSONEncoder)
    # Fallas de formato o de cita detectadas al validar.
    anomalies = models.JSONField(
        "anomalías", default=list, encoder=DjangoJSONEncoder
    )
    # Tiempo de cada etapa y total.
    timings = models.JSONField("tiempos", default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        db_table = "queries_query"
        verbose_name = "consulta"
        verbose_name_plural = "consultas"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=Status.values),
                name="queries_query_status_valid",
            ),
            # El motivo corresponde al estado: ninguno con fundamento, uno de los
            # cuatro de "no determinado" o uno de los cuatro de falla técnica.
            models.CheckConstraint(
                condition=(
                    Q(status=Status.GROUNDED, reason="")
                    | Q(status=Status.UNDETERMINED, reason__in=UNDETERMINED_REASONS)
                    | Q(status=Status.ERROR, reason__in=ERROR_REASONS)
                ),
                name="queries_query_reason_matches_status",
            ),
            models.CheckConstraint(
                condition=Q(max_score__isnull=True)
                | Q(max_score__gte=0, max_score__lte=1),
                name="queries_query_max_score_range",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Una consulta registrada no se modifica.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Una consulta registrada no se borra.")

    def __str__(self):
        return f"consulta {self.pk} {self.asked_at:%Y-%m-%d %H:%M:%S} {self.status}"
