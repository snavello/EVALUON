"""Tablas de la evaluación asistida (plan 004, "Modelo de datos"; ADR-0039 y ADR-0040).

Un pedido de evaluación de un procedimiento genera una evaluación por oferta; cada una,
un resultado por requisito con sus citas (de la oferta, del pliego, de la norma o de una
respuesta de la Comisión) y los pedidos al modelo que lo produjeron. Una persona confirma,
corrige o rechaza cada propuesta (decisiones aparte); las preguntas a la Comisión y sus
respuestas tienen dos tablas mínimas.

**Todas las tablas son de solo inserción** (P6, P3): triggers de la migración
`0002_triggers` rechazan UPDATE y DELETE, venga el cambio del modelo, de `QuerySet.update()`
o de SQL directo. Por eso cada fila nace completa: el pedido de cola (`job`) se crea antes
que su `assessment_request` y se le anota `target_id` después (`tenders_job` sí admite el
cambio); el resultado vigente de un par y el estado de una decisión se calculan, no se
guardan.

Los valores de dominio van en español sin tildes, como en la 003 y la 008. Los datos del
oferente solo existen en la base (P4).
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import Offer, Reading
from evaluon.tenders.models import (
    Job,
    MatrixVersion,
    Procedure,
    Requirement,
    RequirementQuote,
)


def _user_fk(verbose_name, related_name):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=verbose_name, on_delete=models.PROTECT,
        related_name=related_name,
    )


def _valid(field, choices, name, blank=False):
    condition = Q(**{f"{field}__in": choices.values})
    if blank:
        condition |= Q(**{field: ""})
    return models.CheckConstraint(condition=condition, name=name)


# --- Pedido y evaluación -------------------------------------------------------------------


class Cause(models.TextChoices):
    MATRIZ = "matriz", "Evaluación de la matriz"
    SUBSANACION = "subsanacion", "Subsanación"
    RESPUESTA = "respuesta", "Respuesta de la Comisión"
    NUEVA_VERSION = "nueva_version", "Nueva versión de la matriz"
    MANUAL = "manual", "A mano"


class Channel(models.TextChoices):
    SCREEN = "screen", "Pantalla"
    EVAL = "eval", "Evaluación"


class Request(models.Model):
    """Un pedido de evaluación de un procedimiento. No se modifica."""

    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="assessment_requests",
    )
    matrix_version = models.ForeignKey(
        MatrixVersion, verbose_name="versión de la matriz", on_delete=models.PROTECT,
        related_name="assessment_requests",
    )
    # Ids de las ofertas pedidas; ids de los requisitos pedidos o nulo si son todos.
    offers = models.JSONField("ofertas")
    requirements = models.JSONField("requisitos", null=True, blank=True)
    cause = models.CharField("causa", max_length=15, choices=Cause.choices)
    # La decisión o la respuesta que originó el pedido (subsanación, respuesta).
    decision = models.ForeignKey(
        "assessment.Decision", verbose_name="decisión de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="requests",
    )
    answer = models.ForeignKey(
        "assessment.Answer", verbose_name="respuesta de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="requests",
    )
    requested_by = _user_fk("pedida por", "assessment_requests")
    requested_at = models.DateTimeField("pedida", default=timezone.now)
    # El pedido de la cola lleva el id de esta fila en `target_id`, sin clave foránea
    # (ADR-0026, ADR-0039).
    job = models.ForeignKey(
        Job, verbose_name="pedido de la cola", on_delete=models.PROTECT, null=True,
        blank=True, related_name="assessment_requests",
    )

    class Meta:
        db_table = "assessment_request"
        verbose_name = "pedido de evaluación"
        verbose_name_plural = "pedidos de evaluación"
        constraints = [
            _valid("cause", Cause, "assessment_request_cause_valid"),
        ]

    def __str__(self):
        return f"Pedido {self.pk} · {self.procedure}"


class Run(models.Model):
    """La evaluación de una oferta, guardada entera al terminar. No se modifica."""

    request = models.ForeignKey(
        Request, verbose_name="pedido", on_delete=models.PROTECT, related_name="runs"
    )
    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT,
        related_name="assessment_runs",
    )
    # Versión de la matriz con que se evaluó (REQ-057).
    matrix_version = models.ForeignKey(
        MatrixVersion, verbose_name="versión de la matriz", on_delete=models.PROTECT,
        related_name="assessment_runs",
    )
    number = models.PositiveIntegerField("número")
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    # Cada documento usado con su lectura, huella del texto canónico, páginas, tokens,
    # copias omitidas y ventanas.
    documents = models.JSONField("documentos")
    # Régimen, fecha de autorización y versión de la normativa de la propuesta (P8).
    norms = models.JSONField("normativa")
    models_used = models.JSONField("modelos", db_column="models")
    parameters = models.JSONField("parámetros")
    prompt_versions = models.JSONField("versiones de las instrucciones")
    counts = models.JSONField("cuentas", default=dict)
    timings = models.JSONField("tiempos", default=dict)
    anomalies = models.JSONField("anomalías", default=list)
    built_at = models.DateTimeField("armada", default=timezone.now)

    class Meta:
        db_table = "assessment_run"
        verbose_name = "evaluación de una oferta"
        verbose_name_plural = "evaluaciones de ofertas"
        constraints = [
            _valid("channel", Channel, "assessment_run_channel_valid"),
            models.UniqueConstraint(fields=["offer", "number"],
                                    name="assessment_run_number_unique"),
        ]

    def __str__(self):
        return f"{self.offer} · evaluación {self.number}"


# --- Resultado y fundamentos ---------------------------------------------------------------


class Outcome(models.TextChoices):
    CUMPLE = "cumple", "Cumple"
    NO_CUMPLE = "no_cumple", "No cumple"
    SIN_DOCUMENTO = "sin_documento", "No se encontró el documento"
    NO_DETERMINADO = "no_determinado", "No determinado"


class Doubt(models.TextChoices):
    """Motivo de un «no determinado» (ADR-0038)."""

    DUDA = "duda", "Duda"
    SIN_CORROBORAR = "sin_corroborar", "Sin corroborar"
    CONTRADICCION = "contradiccion", "Contradicción entre documentos"
    LECTURA_INCOMPLETA = "lectura_incompleta", "Lectura incompleta"
    EXTERNO = "externo", "Requisito que se verifica fuera de la oferta"
    SIN_CITA = "sin_cita", "Sin cita ubicada"
    SIN_DATO = "sin_dato", "Falta un dato"


class Exigence(models.TextChoices):
    DOCUMENTO = "documento", "Documento"
    CONDICION = "condicion", "Condición"


class Result(models.Model):
    """Lo que el sistema propone para un par (oferta y requisito). No se modifica; el
    vigente de un par es el de la evaluación más reciente."""

    run = models.ForeignKey(
        Run, verbose_name="evaluación", on_delete=models.PROTECT, related_name="results"
    )
    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT,
        related_name="assessment_results",
    )
    requirement = models.ForeignKey(
        Requirement, verbose_name="requisito", on_delete=models.PROTECT,
        related_name="assessment_results",
    )
    outcome = models.CharField("resultado", max_length=20, choices=Outcome.choices)
    # Vacío, o el motivo de un «no determinado».
    doubt = models.CharField("motivo de la duda", max_length=20, choices=Doubt.choices,
                             blank=True)
    exigence = models.CharField("exigencia", max_length=10, choices=Exigence.choices,
                                blank=True)
    # Texto breve del modelo; la pantalla lo rotula «explicación del sistema» y nunca lo
    # presenta como cita.
    explanation = models.TextField("explicación", blank=True)
    unread_pages_warning = models.BooleanField("hay páginas sin leer", default=False)
    # El resultado anterior del mismo par, para el recorrido (REQ-060).
    previous = models.ForeignKey(
        "self", verbose_name="resultado anterior", on_delete=models.PROTECT, null=True,
        blank=True, related_name="next_results",
    )

    class Meta:
        db_table = "assessment_result"
        verbose_name = "resultado propuesto"
        verbose_name_plural = "resultados propuestos"
        constraints = [
            _valid("outcome", Outcome, "assessment_result_outcome_valid"),
            _valid("doubt", Doubt, "assessment_result_doubt_valid", blank=True),
            _valid("exigence", Exigence, "assessment_result_exigence_valid", blank=True),
            # Un «no determinado» siempre dice por qué, y solo él (P3).
            models.CheckConstraint(
                condition=(Q(outcome=Outcome.NO_DETERMINADO) & ~Q(doubt=""))
                | (~Q(outcome=Outcome.NO_DETERMINADO) & Q(doubt="")),
                name="assessment_result_doubt_only_if_undetermined",
            ),
            models.UniqueConstraint(fields=["run", "requirement"],
                                    name="assessment_result_requirement_unique"),
        ]

    def __str__(self):
        return f"{self.offer} · {self.requirement} · {self.outcome}"


class CitationKind(models.TextChoices):
    OFERTA = "oferta", "Texto de la oferta"
    PLIEGO = "pliego", "Texto del pliego"
    NORMA = "norma", "Norma"
    RESPUESTA = "respuesta", "Respuesta de la Comisión"


# Campos propios de cada clase de cita: los de su clase se exigen y los demás quedan vacíos.
_OFFER_FIELDS = ("document", "reading", "page", "char_start", "char_end")
_OTHER_FIELDS = {
    CitationKind.OFERTA: ("requirement_quote", "norm_unit", "answer"),
    CitationKind.PLIEGO: _OFFER_FIELDS + ("norm_unit", "answer"),
    CitationKind.NORMA: _OFFER_FIELDS + ("requirement_quote", "answer"),
    CitationKind.RESPUESTA: _OFFER_FIELDS + ("requirement_quote", "norm_unit"),
}


def _only_if(kind, required, empty, extra=None):
    """Condición de una cita de la clase `kind`: `required` con valor, `empty` vacíos."""
    condition = Q(kind=kind)
    for name in required:
        condition &= Q(**{f"{name}__isnull": False})
    for name in empty:
        condition &= Q(**{f"{name}__isnull": True})
    if extra is not None:
        condition &= extra
    return ~Q(kind=kind) | condition


class Citation(models.Model):
    """Un fundamento de un resultado, con una restricción por clase. Solo las citas de la
    oferta habilitan «cumple» o «no cumple» (P3)."""

    result = models.ForeignKey(
        Result, verbose_name="resultado", on_delete=models.PROTECT,
        related_name="citations",
    )
    order = models.PositiveIntegerField("orden")
    kind = models.CharField("clase", max_length=10, choices=CitationKind.choices)
    # oferta
    document = models.ForeignKey(
        OfferDocument, verbose_name="documento", on_delete=models.PROTECT, null=True,
        blank=True, related_name="assessment_citations",
    )
    reading = models.ForeignKey(
        Reading, verbose_name="lectura", on_delete=models.PROTECT, null=True, blank=True,
        related_name="assessment_citations",
    )
    page = models.PositiveIntegerField("página", null=True, blank=True)
    char_start = models.PositiveIntegerField("inicio en el texto canónico", null=True,
                                             blank=True)
    char_end = models.PositiveIntegerField("fin en el texto canónico", null=True,
                                           blank=True)
    # oferta (igual al recorte del texto canónico), pliego (el vigente) y norma.
    text = models.TextField("texto literal", blank=True)
    # pliego
    requirement_quote = models.ForeignKey(
        RequirementQuote, verbose_name="cita del requisito", on_delete=models.PROTECT,
        null=True, blank=True, related_name="assessment_citations",
    )
    # pliego: el texto original, si una circular modificó la cita.
    original_text = models.TextField("texto original", blank=True)
    # norma
    norm_unit = models.ForeignKey(
        "norms.Unit", verbose_name="unidad de la normativa", on_delete=models.PROTECT,
        null=True, blank=True, related_name="assessment_citations",
    )
    label = models.CharField("norma y artículo", max_length=300, blank=True)
    # respuesta
    answer = models.ForeignKey(
        "assessment.Answer", verbose_name="respuesta", on_delete=models.PROTECT,
        null=True, blank=True, related_name="citations",
    )

    class Meta:
        db_table = "assessment_citation"
        verbose_name = "fundamento de un resultado"
        verbose_name_plural = "fundamentos de los resultados"
        constraints = [
            _valid("kind", CitationKind, "assessment_citation_kind_valid"),
            models.UniqueConstraint(fields=["result", "order"],
                                    name="assessment_citation_order_unique"),
            models.CheckConstraint(
                condition=_only_if(
                    CitationKind.OFERTA, _OFFER_FIELDS, _OTHER_FIELDS[CitationKind.OFERTA],
                    extra=Q(char_end__gte=F("char_start")) & ~Q(text="")),
                name="assessment_citation_oferta_fields",
            ),
            models.CheckConstraint(
                condition=_only_if(
                    CitationKind.PLIEGO, ("requirement_quote",),
                    _OTHER_FIELDS[CitationKind.PLIEGO], extra=~Q(text="")),
                name="assessment_citation_pliego_fields",
            ),
            models.CheckConstraint(
                condition=_only_if(
                    CitationKind.NORMA, ("norm_unit",), _OTHER_FIELDS[CitationKind.NORMA],
                    extra=~Q(text="") & ~Q(label="")),
                name="assessment_citation_norma_fields",
            ),
            models.CheckConstraint(
                condition=_only_if(
                    CitationKind.RESPUESTA, ("answer",),
                    _OTHER_FIELDS[CitationKind.RESPUESTA]),
                name="assessment_citation_respuesta_fields",
            ),
        ]


class Purpose(models.TextChoices):
    GRUPO = "grupo", "Lectura de un grupo de documentos"
    CONTRASTE = "contraste", "Contraste"
    REESCRITURA = "reescritura", "Reescritura del requisito"


class Step(models.Model):
    """Un pedido al modelo (P6): documentos que entraron, pedido completo, salida cruda y
    lo interpretado. No se modifica."""

    run = models.ForeignKey(
        Run, verbose_name="evaluación", on_delete=models.PROTECT, related_name="steps"
    )
    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT,
        related_name="assessment_steps",
    )
    # Nulo en la reescritura.
    requirement = models.ForeignKey(
        Requirement, verbose_name="requisito", on_delete=models.PROTECT, null=True,
        blank=True, related_name="assessment_steps",
    )
    purpose = models.CharField("para qué", max_length=15, choices=Purpose.choices)
    group_index = models.PositiveIntegerField("grupo", null=True, blank=True)
    documents = models.JSONField("documentos o ventanas", default=list)
    request = models.JSONField("pedido", null=True, blank=True)
    raw_output = models.TextField("salida cruda", blank=True)
    parsed = models.JSONField("interpretado", null=True, blank=True)
    anomalies = models.JSONField("anomalías", default=list)
    retry_of = models.ForeignKey(
        "self", verbose_name="reintento de", on_delete=models.PROTECT, null=True,
        blank=True, related_name="retries",
    )
    prompt_tokens = models.PositiveIntegerField("tokens del pedido", null=True, blank=True)
    completion_tokens = models.PositiveIntegerField("tokens de la salida", null=True,
                                                    blank=True)
    timings = models.JSONField("tiempos", default=dict)

    class Meta:
        db_table = "assessment_step"
        verbose_name = "pedido al modelo de la evaluación"
        verbose_name_plural = "pedidos al modelo de la evaluación"
        constraints = [
            _valid("purpose", Purpose, "assessment_step_purpose_valid"),
        ]


# --- Decisiones de una persona -------------------------------------------------------------


class Action(models.TextChoices):
    CONFIRMAR = "confirmar", "Confirmar"
    CORREGIR = "corregir", "Corregir"
    RECHAZAR = "rechazar", "Rechazar"
    PEDIR_SUBSANACION = "pedir_subsanacion", "Pedir la subsanación"
    SUBSANAR = "subsanar", "Documento agregado por subsanación"


# Acciones que exigen una nota (REQ-056).
NOTE_REQUIRED = (Action.CORREGIR, Action.RECHAZAR, Action.PEDIR_SUBSANACION)


class Decision(models.Model):
    """Lo que una persona hace con un resultado. No se modifica. El estado de un par sale
    de la última decisión entre confirmar, corregir y rechazar; pedir la subsanación y
    subsanar son el recorrido y no cambian el estado."""

    result = models.ForeignKey(
        Result, verbose_name="resultado", on_delete=models.PROTECT,
        related_name="decisions",
    )
    action = models.CharField("acción", max_length=20, choices=Action.choices)
    # En `corregir`: uno de los cuatro resultados.
    outcome_after = models.CharField("resultado después", max_length=20,
                                     choices=Outcome.choices, blank=True)
    note = models.TextField("nota", blank=True)
    # En `subsanar`: el documento agregado a la oferta.
    document = models.ForeignKey(
        OfferDocument, verbose_name="documento agregado", on_delete=models.PROTECT,
        null=True, blank=True, related_name="assessment_decisions",
    )
    user = _user_fk("usuario", "assessment_decisions")
    at = models.DateTimeField("momento", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent", verbose_name="hecho registrado", on_delete=models.PROTECT,
        related_name="assessment_decisions",
    )

    class Meta:
        db_table = "assessment_decision"
        verbose_name = "decisión sobre un resultado"
        verbose_name_plural = "decisiones sobre los resultados"
        constraints = [
            _valid("action", Action, "assessment_decision_action_valid"),
            _valid("outcome_after", Outcome, "assessment_decision_outcome_valid",
                   blank=True),
            models.CheckConstraint(
                condition=~Q(action__in=NOTE_REQUIRED) | ~Q(note=""),
                name="assessment_decision_note_required",
            ),
            models.CheckConstraint(
                condition=(Q(action=Action.CORREGIR) & ~Q(outcome_after=""))
                | (~Q(action=Action.CORREGIR) & Q(outcome_after="")),
                name="assessment_decision_outcome_after_only_if_corrected",
            ),
            models.CheckConstraint(
                condition=(Q(action=Action.SUBSANAR) & Q(document__isnull=False))
                | (~Q(action=Action.SUBSANAR) & Q(document__isnull=True)),
                name="assessment_decision_document_only_if_remedied",
            ),
        ]


# --- Preguntas a la Comisión (ADR-0040) ------------------------------------------------------


class Question(models.Model):
    """Una pregunta concreta a la Comisión. No se modifica."""

    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="assessment_questions",
    )
    requirement = models.ForeignKey(
        Requirement, verbose_name="requisito", on_delete=models.PROTECT,
        related_name="assessment_questions",
    )
    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT,
        related_name="assessment_questions",
    )
    # El resultado que la originó.
    result = models.ForeignKey(
        Result, verbose_name="resultado de origen", on_delete=models.PROTECT,
        related_name="questions",
    )
    text = models.TextField("pregunta")
    reason = models.CharField("motivo", max_length=300, blank=True)
    created_at = models.DateTimeField("formulada", default=timezone.now)

    class Meta:
        db_table = "assessment_question"
        verbose_name = "pregunta a la Comisión"
        verbose_name_plural = "preguntas a la Comisión"
        constraints = [
            models.CheckConstraint(condition=~Q(text=""),
                                   name="assessment_question_text_required"),
        ]


class AnswerScope(models.TextChoices):
    PAR = "par", "Solo esa oferta y ese requisito"
    REQUISITO = "requisito", "Todas las ofertas de ese requisito"
    PROCEDIMIENTO = "procedimiento", "Todo el procedimiento"


class Answer(models.Model):
    """La respuesta de la Comisión a una pregunta. No se modifica; la vigente es la
    última de la pregunta."""

    question = models.ForeignKey(
        Question, verbose_name="pregunta", on_delete=models.PROTECT,
        related_name="answers",
    )
    text = models.TextField("respuesta")
    scope = models.CharField("alcance", max_length=15, choices=AnswerScope.choices,
                             default=AnswerScope.REQUISITO)
    answered_by = _user_fk("respondida por", "assessment_answers")
    answered_at = models.DateTimeField("respondida", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent", verbose_name="hecho registrado", on_delete=models.PROTECT,
        related_name="assessment_answers",
    )

    class Meta:
        db_table = "assessment_answer"
        verbose_name = "respuesta de la Comisión"
        verbose_name_plural = "respuestas de la Comisión"
        constraints = [
            _valid("scope", AnswerScope, "assessment_answer_scope_valid"),
            models.CheckConstraint(condition=~Q(text=""),
                                   name="assessment_answer_text_required"),
        ]
