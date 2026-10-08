"""Tablas de procedimientos, pliegos y matriz de cumplimiento (plan 003, "Modelo de
datos"; ADR-0018 y ADR-0019).

Un procedimiento tiene documentos (cada archivo del pliego final, con su original byte
por byte); cada documento, sus lecturas; cada lectura, sus tramos. Un pedido en segundo
plano lee un documento o propone una matriz; cada propuesta guarda sus pedidos al modelo
y la disposición de cada tramo. Una versión de la matriz tiene requisitos, cada uno con
sus citas, las fuentes que le suman circulares y respuestas, sus consecuencias posibles
y su historial; y tramos pendientes de revisión.

Las restricciones que el plan fija van en la base, para que valgan venga de donde venga
la escritura. Las que cruzan tablas (un formal o económico con exactamente una cita), el
registro de solo inserción de `tenders_run_step` y `tenders_requirement_change`, y la
inmutabilidad de una versión validada son triggers de la migración `0002_triggers`.

Los valores que nombran un concepto del dominio van en español sin tildes; los estados
propios del sistema, en inglés, como en la 001.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Func, Q
from django.db.models.lookups import Exact, LessThanOrEqual
from django.utils import timezone

from evaluon.norms.models import SHA256_REGEX, FileFormat, ProposalState, TextOrigin


def _user_fk(verbose_name, related_name, null=False):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        related_name=related_name,
        null=null,
        blank=null,
    )


def _valid(field, choices, name, blank=False):
    """Restricción de valores válidos; con `blank`, también el vacío."""
    condition = Q(**{f"{field}__in": choices.values})
    if blank:
        condition |= Q(**{field: ""})
    return models.CheckConstraint(condition=condition, name=name)


def _is_json_array(field, name):
    """El campo JSON es una lista."""
    return models.CheckConstraint(
        condition=Q(
            Exact(
                Func(F(field), function="jsonb_typeof", output_field=models.TextField()),
                "array",
            )
        ),
        name=name,
    )


def _char_range(prefix):
    return models.CheckConstraint(
        condition=Q(char_end__gte=F("char_start")), name=f"{prefix}_char_range_valid"
    )


# --- Procedimiento y documentos -------------------------------------------------------


class Procedure(models.Model):
    """Un procedimiento de compra (REQ-022). El régimen no se guarda: se calcula con
    `applicable_regimes(fecha)` de la 001 cada vez que se muestra."""

    number = models.CharField("número", max_length=100, unique=True)
    procedure_type = models.CharField("tipo", max_length=200)
    subject = models.TextField("objeto")
    # No puede ser posterior al día; lo controla la función de negocio (T-069).
    authorization_date = models.DateField("fecha de autorización")
    created_at = models.DateTimeField("alta", default=timezone.now)
    created_by = _user_fk("dado de alta por", "procedures_created")

    class Meta:
        db_table = "tenders_procedure"
        verbose_name = "procedimiento"
        verbose_name_plural = "procedimientos"

    def __str__(self):
        return self.number


class DocumentKind(models.TextChoices):
    PLIEGO = "pliego", "Pliego"
    ANEXO = "anexo", "Anexo"
    ESPECIFICACIONES = "especificaciones", "Especificaciones técnicas"
    CIRCULAR_MODIFICATORIA = "circular_modificatoria", "Circular modificatoria"
    CIRCULAR_ACLARATORIA = "circular_aclaratoria", "Circular aclaratoria"
    RESPUESTA_CONSULTA = "respuesta_consulta", "Respuesta a consulta"
    # Feature 014 (REQ-092): el dictamen que la Comisión sube cuando el Portal no lo publica.
    DICTAMEN = "dictamen", "Dictamen"


# Tipos de documento que llevan fecha obligatoria (REQ-031).
DATED_DOCUMENT_KINDS = (
    DocumentKind.CIRCULAR_MODIFICATORIA,
    DocumentKind.CIRCULAR_ACLARATORIA,
    DocumentKind.RESPUESTA_CONSULTA,
)


class Document(models.Model):
    """Un archivo cargado del pliego final (REQ-023)."""

    procedure = models.ForeignKey(
        Procedure,
        verbose_name="procedimiento",
        on_delete=models.PROTECT,
        related_name="documents",
    )
    kind = models.CharField("tipo", max_length=30, choices=DocumentKind.choices)
    title = models.TextField("título")
    issued_on = models.DateField("fecha del documento", null=True, blank=True)
    file_name = models.CharField("nombre del archivo", max_length=255)
    file_format = models.CharField("formato", max_length=10, choices=FileFormat.choices)
    file_size = models.PositiveBigIntegerField("tamaño")
    file_sha256 = models.CharField("huella del archivo", max_length=64)
    loaded_at = models.DateTimeField("cargado", default=timezone.now)
    loaded_by = _user_fk("cargado por", "tender_documents_loaded")

    class Meta:
        db_table = "tenders_document"
        verbose_name = "documento del pliego"
        verbose_name_plural = "documentos del pliego"
        constraints = [
            _valid("kind", DocumentKind, "tenders_document_kind_valid"),
            _valid("file_format", FileFormat, "tenders_document_file_format_valid"),
            models.CheckConstraint(
                condition=Q(file_sha256__regex=SHA256_REGEX),
                name="tenders_document_file_sha256_valid",
            ),
            # El mismo archivo dos veces en un procedimiento se rechaza (plan 003).
            models.UniqueConstraint(
                fields=["procedure", "file_sha256"],
                name="tenders_document_sha256_unique_in_procedure",
            ),
            models.CheckConstraint(
                condition=~Q(kind__in=DATED_DOCUMENT_KINDS) | Q(issued_on__isnull=False),
                name="tenders_document_dated_kinds_have_date",
            ),
        ]

    def __str__(self):
        return f"{self.procedure} · {self.title}"


class DocumentFile(models.Model):
    """El archivo original, byte por byte (REQ-023), en tabla aparte como en la 001."""

    document = models.OneToOneField(
        Document,
        verbose_name="documento",
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="file",
    )
    content = models.BinaryField("contenido")

    class Meta:
        db_table = "tenders_document_file"
        verbose_name = "archivo original del pliego"
        verbose_name_plural = "archivos originales del pliego"


class Reading(models.Model):
    """Una lectura de un documento del pliego. No se modifica."""

    document = models.ForeignKey(
        Document,
        verbose_name="documento",
        on_delete=models.PROTECT,
        related_name="readings",
    )
    sequence = models.PositiveIntegerField("número de lectura")
    # La lectura de la 001, página por página.
    pages = models.JSONField("lectura")
    # Zonas de tabla por página (`tables.py`).
    tables = models.JSONField("zonas de tabla", default=list)
    canonical_text = models.TextField("texto canónico")
    canonical_sha256 = models.CharField("huella del texto canónico", max_length=64)
    # Renglones reconocidos: número y clave del tramo de su encabezado.
    items = models.JSONField("renglones", default=list)
    # Las de la 001 más la versión de las reglas de tramos.
    tool_versions = models.JSONField("versiones de las herramientas")
    report = models.JSONField("informe")
    created_at = models.DateTimeField("leída", default=timezone.now)
    job = models.ForeignKey(
        "Job",
        verbose_name="pedido",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="readings",
    )

    class Meta:
        db_table = "tenders_reading"
        verbose_name = "lectura del pliego"
        verbose_name_plural = "lecturas del pliego"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "sequence"],
                name="tenders_reading_sequence_unique",
            ),
            _is_json_array("items", "tenders_reading_items_is_list"),
        ]

    def __str__(self):
        return f"{self.document} · lectura {self.sequence}"


class SegmentType(models.TextChoices):
    TITULO = "titulo", "Título"
    CLAUSULA = "clausula", "Cláusula"
    VINETA = "vineta", "Viñeta o inciso"
    PARRAFO = "parrafo", "Párrafo"
    TABLA = "tabla", "Tabla"
    PAGINA = "pagina", "Página sin texto legible"
    NO_UBICADO = "no_ubicado", "No ubicado"


class RequirementClass(models.TextChoices):
    """Clase de un requisito; también la clase que nombra el título de una sección."""

    FORMAL = "formal", "Formal"
    ECONOMICO = "economico", "Económico"
    TECNICO = "tecnico", "Técnico"


class ReadingReviewReason(models.TextChoices):
    """Por qué la lectura deja un tramo pendiente de revisión (REQ-028)."""

    PAGINA_ILEGIBLE = "pagina_ilegible", "Página ilegible"
    PAGINA_DUDOSA = "pagina_dudosa", "Página dudosa"
    TABLA = "tabla", "Tabla"
    NO_UBICADO = "no_ubicado", "Tramo no ubicado"


class Segment(models.Model):
    """Un tramo del pliego (ADR-0019). No se modifica. `text` es igual a
    `canonical_text[char_start:char_end]` de su lectura."""

    reading = models.ForeignKey(
        Reading, verbose_name="lectura", on_delete=models.PROTECT, related_name="segments"
    )
    order = models.PositiveIntegerField("orden")
    key = models.CharField("clave", max_length=255)
    label = models.TextField("encabezado", blank=True)
    path = models.TextField("ruta", blank=True)
    segment_type = models.CharField("tipo", max_length=20, choices=SegmentType.choices)
    section_class = models.CharField(
        "clase de la sección", max_length=20, choices=RequirementClass.choices, blank=True
    )
    # Renglones a los que pertenece; vacía si es general.
    items = models.JSONField("renglones", default=list)
    page_start = models.PositiveIntegerField("página inicial", null=True, blank=True)
    page_end = models.PositiveIntegerField("página final", null=True, blank=True)
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal", blank=True)
    # Vacío en un tramo `pagina`, que no tiene texto.
    text_origin = models.CharField(
        "origen del texto", max_length=10, choices=TextOrigin.choices, blank=True
    )
    ocr_confidence_min = models.FloatField("confianza mínima", null=True, blank=True)
    ocr_confidence_avg = models.FloatField("confianza promedio", null=True, blank=True)
    review_reason = models.CharField(
        "motivo de revisión",
        max_length=20,
        choices=ReadingReviewReason.choices,
        blank=True,
    )

    class Meta:
        db_table = "tenders_segment"
        verbose_name = "tramo"
        verbose_name_plural = "tramos"
        constraints = [
            _valid("segment_type", SegmentType, "tenders_segment_segment_type_valid"),
            _valid(
                "section_class",
                RequirementClass,
                "tenders_segment_section_class_valid",
                blank=True,
            ),
            _valid(
                "text_origin", TextOrigin, "tenders_segment_text_origin_valid", blank=True
            ),
            _valid(
                "review_reason",
                ReadingReviewReason,
                "tenders_segment_review_reason_valid",
                blank=True,
            ),
            _is_json_array("items", "tenders_segment_items_is_list"),
            _char_range("tenders_segment"),
            models.UniqueConstraint(
                fields=["reading", "key"], name="tenders_segment_key_unique_in_reading"
            ),
            models.UniqueConstraint(
                fields=["reading", "order"],
                name="tenders_segment_order_unique_in_reading",
            ),
        ]

    def __str__(self):
        return self.key


# --- Pedidos y propuestas ---------------------------------------------------------------


class JobKind(models.TextChoices):
    READ_DOCUMENT = "read_document", "Leer un documento"
    PROPOSE_MATRIX = "propose_matrix", "Proponer la matriz"
    # Feature 008 (ADR-0026): pedidos de ofertas; `target_id` nombra el documento de la
    # oferta o la oferta.
    READ_OFFER_DOCUMENT = "read_offer_document", "Leer un documento de una oferta"
    BUILD_SHEET = "build_sheet", "Armar la ficha de una oferta"
    # Feature 012 (ADR-0030, ADR-0031): pedidos del Portal de Compras; `target_id` es el
    # enlace (`portal_link`) y el procedimiento puede no existir todavía.
    PORTAL_EXPLORE = "portal_explore", "Explorar un proceso del Portal"
    PORTAL_REVIEW = "portal_review", "Revisar un proceso del Portal"
    # Feature 004 (ADR-0039): evaluar las ofertas de un procedimiento; `target_id` es el
    # pedido de evaluación (`assessment_request`), sin clave foránea.
    EVALUATE_OFFERS = "evaluate_offers", "Evaluar las ofertas"
    # Feature 014 (ADR-0049, REQ-077 y REQ-083): leer un pliego o los archivos de una oferta y
    # proponer sus datos; `target_id` es el borrador (`tenders_procedure_draft` u
    # `offers_offer_draft`), sin clave foránea.
    PROPOSE_PROCEDURE = "propose_procedure", "Proponer el procedimiento desde el pliego"
    PROPOSE_OFFER = "propose_offer", "Proponer la oferta desde sus archivos"


# Tipos que atiende el servicio `portal_worker` y no el `worker` (ADR-0031).
PORTAL_JOB_KINDS = (JobKind.PORTAL_EXPLORE, JobKind.PORTAL_REVIEW)

# Pedidos que nombran un borrador (feature 014). Solo `propose_procedure` puede no tener
# procedimiento: el borrador de una oferta ya cuelga de uno.
PROPOSAL_JOB_KINDS = (JobKind.PROPOSE_PROCEDURE, JobKind.PROPOSE_OFFER)


class JobStatus(models.TextChoices):
    QUEUED = "queued", "En espera"
    RUNNING = "running", "En curso"
    DONE = "done", "Terminado"
    FAILED = "failed", "Fallido"


class Job(models.Model):
    """Un pedido en segundo plano (ADR-0018). Lo atiende `procesar_pedidos` (T-071)."""

    kind = models.CharField("tipo", max_length=20, choices=JobKind.choices)
    status = models.CharField(
        "estado", max_length=10, choices=JobStatus.choices, default=JobStatus.QUEUED
    )
    # Nulo solo en los pedidos del Portal, que pueden ser anteriores al procedimiento
    # (restricción `tenders_job_procedure_required`).
    procedure = models.ForeignKey(
        Procedure,
        verbose_name="procedimiento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="jobs",
    )
    document = models.ForeignKey(
        Document,
        verbose_name="documento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="jobs",
    )
    # Id del documento de oferta (`read_offer_document`) o de la oferta (`build_sheet`).
    # Sin clave foránea (ADR-0026): lo comprueba la función de negocio de `offers`.
    target_id = models.PositiveBigIntegerField("objeto del pedido", null=True, blank=True)
    requested_by = _user_fk("pedido por", "tender_jobs_requested")
    requested_at = models.DateTimeField("pedido", default=timezone.now)
    started_at = models.DateTimeField("empezado", null=True, blank=True)
    finished_at = models.DateTimeField("terminado", null=True, blank=True)
    error = models.TextField("motivo de la falla", blank=True)
    # Cuándo vio el aviso de fin quien lo pidió.
    seen_at = models.DateTimeField("aviso visto", null=True, blank=True)
    # Avance fino del pedido en curso (REQ-067, ADR-0045 3.B): paso actual, cuenta y una lista
    # corta de los últimos pasos. Dato descartable que escribe `jobs.report`; no es registro
    # de auditoría.
    progress = models.JSONField("avance", default=dict, blank=True)

    class Meta:
        db_table = "tenders_job"
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        constraints = [
            _valid("kind", JobKind, "tenders_job_kind_valid"),
            _valid("status", JobStatus, "tenders_job_status_valid"),
            # Leer un documento es siempre sobre un documento.
            models.CheckConstraint(
                condition=~Q(kind=JobKind.READ_DOCUMENT) | Q(document__isnull=False),
                name="tenders_job_read_document_has_document",
            ),
            # Un pedido de ofertas nombra su objeto (ADR-0026).
            models.CheckConstraint(
                condition=~Q(kind__in=[JobKind.READ_OFFER_DOCUMENT, JobKind.BUILD_SHEET])
                | Q(target_id__isnull=False),
                name="tenders_job_offer_kinds_have_target",
            ),
            # Solo los pedidos del Portal (ADR-0030) y la propuesta de procedimiento desde el
            # pliego (ADR-0049) pueden no tener procedimiento.
            models.CheckConstraint(
                condition=Q(procedure__isnull=False)
                | Q(kind__in=[*PORTAL_JOB_KINDS, JobKind.PROPOSE_PROCEDURE]),
                name="tenders_job_procedure_required",
            ),
            # Un pedido de propuesta nombra su borrador.
            models.CheckConstraint(
                condition=~Q(kind__in=PROPOSAL_JOB_KINDS) | Q(target_id__isnull=False),
                name="tenders_job_proposal_kinds_have_target",
            ),
            # Un pedido del Portal nombra su enlace.
            models.CheckConstraint(
                condition=~Q(kind__in=PORTAL_JOB_KINDS) | Q(target_id__isnull=False),
                name="tenders_job_portal_kinds_have_target",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.status}"


class Level(models.TextChoices):
    """Nivel de revisión de una propuesta de matriz (REQ-030)."""

    MEDIA = "media", "Media"
    ALTA = "alta", "Alta"
    EXIGENTE = "exigente", "Exigente"


class Process(models.TextChoices):
    """Proceso de una propuesta de matriz (REQ-030 enmendado: uno solo)."""

    COMPLETO = "completo", "Completo"


class RunChannel(models.TextChoices):
    SCREEN = "screen", "Pantalla"
    EVAL = "eval", "Evaluación"


class MatrixRun(models.Model):
    """Una propuesta de matriz. Fecha, régimen, versión de la normativa, modelos,
    parámetros e instrucciones se toman al empezar (P6, P8)."""

    procedure = models.ForeignKey(
        Procedure,
        verbose_name="procedimiento",
        on_delete=models.PROTECT,
        related_name="matrix_runs",
    )
    # Vacío en una corrida de medición, que no pasa por la cola.
    job = models.ForeignKey(
        Job,
        verbose_name="pedido",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matrix_runs",
    )
    # Dato histórico: las propuestas nuevas lo dejan vacío (REQ-030 enmendado).
    level = models.CharField("nivel", max_length=10, choices=Level.choices, blank=True)
    # Vacío en las propuestas hechas antes del proceso único.
    process = models.CharField(
        "proceso", max_length=10, choices=Process.choices, blank=True
    )
    channel = models.CharField("canal", max_length=10, choices=RunChannel.choices)
    # Cada documento usado con su lectura y su huella.
    documents = models.JSONField("documentos", default=list)
    authorization_date = models.DateField("fecha de autorización")
    # Regímenes aplicables a la fecha (norma y nombre de cita); vacío si no hay.
    regime = models.JSONField("régimen", default=list)
    corpus_version = models.PositiveIntegerField(
        "versión de la normativa", null=True, blank=True
    )
    parameters = models.JSONField("parámetros", default=dict)
    prompt_versions = models.JSONField("versiones de instrucciones", default=dict)
    counts = models.JSONField("cuentas", default=dict)
    timings = models.JSONField("tiempos", default=dict)
    anomalies = models.JSONField("anomalías", default=list)
    # Versión de matriz que creó; vacío hasta terminar.
    version = models.OneToOneField(
        "MatrixVersion",
        verbose_name="versión creada",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_by_run",
    )
    # Nombre, huella y compilación de los modelos usados. Va al final: el nombre del
    # campo tapa al módulo `models` en el resto del cuerpo de la clase.
    models = models.JSONField("modelos", default=dict)

    class Meta:
        db_table = "tenders_matrix_run"
        verbose_name = "propuesta de matriz"
        verbose_name_plural = "propuestas de matriz"
        constraints = [
            _valid("level", Level, "tenders_matrix_run_level_valid", blank=True),
            _valid("process", Process, "tenders_matrix_run_process_valid", blank=True),
            _valid("channel", RunChannel, "tenders_matrix_run_channel_valid"),
        ]


class PassName(models.TextChoices):
    EXTRACCION = "extraccion", "Extracción"
    EXTRACCION_2 = "extraccion_2", "Segunda extracción"
    COMPLETITUD = "completitud", "Completitud"
    CONSECUENCIAS = "consecuencias", "Consecuencias"
    CIRCULARES = "circulares", "Circulares"
    UNIFICACION = "unificacion", "Unificación de repetidas"
    FILTRO = "filtro", "Filtro de sobrantes"
    FILTRO_2 = "filtro_2", "Filtro de sobrantes, segunda opinión"
    RESPALDO_NORMATIVO = "respaldo_normativo", "Respaldo normativo"
    CIRCULARES_CAMBIOS = "circulares_cambios", "Extracción de cambios de circulares"


class RunStep(models.Model):
    """Un pedido al modelo dentro de una propuesta. Solo se insertan filas: con esta
    tabla se reconstruye por qué el sistema propuso cada requisito (P6)."""

    run = models.ForeignKey(
        MatrixRun, verbose_name="propuesta", on_delete=models.PROTECT, related_name="steps"
    )
    pass_name = models.CharField("pasada", max_length=20, choices=PassName.choices)
    batch = models.PositiveIntegerField("lote")
    segment_keys = models.JSONField("claves de los tramos", default=list)
    request = models.JSONField("pedido")
    raw_output = models.TextField("salida", blank=True)
    parsed = models.JSONField("salida interpretada", null=True, blank=True)
    anomalies = models.JSONField("anomalías", default=list)
    retry_of = models.ForeignKey(
        "self",
        verbose_name="reintento de",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retries",
    )
    timings = models.JSONField("tiempos", default=dict)

    class Meta:
        db_table = "tenders_run_step"
        verbose_name = "pedido al modelo"
        verbose_name_plural = "pedidos al modelo"
        constraints = [
            _valid("pass_name", PassName, "tenders_run_step_pass_name_valid"),
        ]


class DispositionOutcome(models.TextChoices):
    REQUISITOS = "requisitos", "Con requisitos"
    TECNICO = "tecnico", "Fila técnica"
    DESCARTADO = "descartado", "Descartado"
    PENDIENTE = "pendiente", "Pendiente de revisión"


class DiscardReason(models.TextChoices):
    """Motivos de descarte de un tramo: la lista cerrada del ADR-0019."""

    TITULO = "titulo", "Título"
    DATO_PROCEDIMIENTO = "dato_procedimiento", "Definición o dato del procedimiento"
    NORMA_APLICABLE = "norma_aplicable", "Norma aplicable"
    OBLIGACION_ORGANISMO = (
        "obligacion_organismo",
        "Obligación del organismo que la oferta no puede contradecir ni condicionar",
    )
    EJECUCION_CONTRATO = "ejecucion_contrato", "Obligación de la ejecución del contrato"
    FORMULARIO = "formulario", "Formulario a completar"
    INDICE_CARATULA = "indice_caratula", "Índice o carátula"


class DispositionSource(models.TextChoices):
    MODELO = "modelo", "Modelo"
    REGLA = "regla", "Regla"
    FILTRO = "filtro", "Filtro"


class Disposition(models.Model):
    """Qué pasó con cada tramo en una propuesta: el control de cobertura (ADR-0019)."""

    run = models.ForeignKey(
        MatrixRun,
        verbose_name="propuesta",
        on_delete=models.PROTECT,
        related_name="dispositions",
    )
    segment = models.ForeignKey(
        Segment, verbose_name="tramo", on_delete=models.PROTECT, related_name="dispositions"
    )
    outcome = models.CharField(
        "disposición", max_length=20, choices=DispositionOutcome.choices
    )
    discard_reason = models.CharField(
        "motivo de descarte", max_length=30, choices=DiscardReason.choices, blank=True
    )
    source = models.CharField("origen", max_length=10, choices=DispositionSource.choices)
    step = models.ForeignKey(
        RunStep,
        verbose_name="pedido al modelo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dispositions",
    )

    class Meta:
        db_table = "tenders_disposition"
        verbose_name = "disposición de un tramo"
        verbose_name_plural = "disposiciones de tramos"
        constraints = [
            _valid("outcome", DispositionOutcome, "tenders_disposition_outcome_valid"),
            _valid(
                "discard_reason",
                DiscardReason,
                "tenders_disposition_discard_reason_valid",
                blank=True,
            ),
            _valid("source", DispositionSource, "tenders_disposition_source_valid"),
            # Un descarte siempre lleva su motivo.
            models.CheckConstraint(
                condition=~Q(outcome=DispositionOutcome.DESCARTADO)
                | ~Q(discard_reason=""),
                name="tenders_disposition_discard_has_reason",
            ),
            models.UniqueConstraint(
                fields=["run", "segment"], name="tenders_disposition_one_per_segment"
            ),
        ]


# --- Matriz ---------------------------------------------------------------------------


class VersionStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    VALIDATED = "validated", "Validada"
    DISCARDED = "discarded", "Descartada"


class MatrixVersion(models.Model):
    """Una versión de la matriz de cumplimiento (REQ-027). Una validada no cambia:
    triggers rechazan UPDATE y DELETE sobre sus requisitos, citas, fuentes,
    consecuencias y pendientes, y sobre su propia fila. Solo un borrador recibe filas
    nuevas y cambia de estado (a validada o descartada)."""

    procedure = models.ForeignKey(
        Procedure,
        verbose_name="procedimiento",
        on_delete=models.PROTECT,
        related_name="matrix_versions",
    )
    number = models.PositiveIntegerField("número")
    status = models.CharField(
        "estado", max_length=10, choices=VersionStatus.choices, default=VersionStatus.DRAFT
    )
    # El de la propuesta de la que sale; una versión abierta sobre otra conserva el de
    # su origen (REQ-030).
    level = models.CharField("nivel", max_length=10, choices=Level.choices, blank=True)
    process = models.CharField(
        "proceso", max_length=10, choices=Process.choices, blank=True
    )
    run = models.ForeignKey(
        MatrixRun,
        verbose_name="propuesta",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    based_on = models.ForeignKey(
        "self",
        verbose_name="copiada de",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="later_versions",
    )
    created_at = models.DateTimeField("creada", default=timezone.now)
    created_by = _user_fk("creada por", "matrix_versions_created")
    validated_at = models.DateTimeField("validada", null=True, blank=True)
    validated_by = _user_fk("validada por", "matrix_versions_validated", null=True)
    discarded_at = models.DateTimeField("descartada", null=True, blank=True)
    discarded_by = _user_fk("descartada por", "matrix_versions_discarded", null=True)

    class Meta:
        db_table = "tenders_matrix_version"
        verbose_name = "versión de la matriz"
        verbose_name_plural = "versiones de la matriz"
        constraints = [
            _valid("status", VersionStatus, "tenders_matrix_version_status_valid"),
            _valid("level", Level, "tenders_matrix_version_level_valid", blank=True),
            _valid(
                "process", Process, "tenders_matrix_version_process_valid", blank=True
            ),
            models.UniqueConstraint(
                fields=["procedure", "number"],
                name="tenders_matrix_version_number_unique",
            ),
            # A lo sumo un borrador por procedimiento.
            models.UniqueConstraint(
                fields=["procedure"],
                condition=Q(status=VersionStatus.DRAFT),
                name="tenders_matrix_version_one_draft",
            ),
            models.CheckConstraint(
                condition=~Q(status=VersionStatus.VALIDATED)
                | Q(validated_at__isnull=False, validated_by__isnull=False),
                name="tenders_matrix_version_validated_has_who_when",
            ),
            models.CheckConstraint(
                condition=~Q(status=VersionStatus.DISCARDED)
                | Q(discarded_at__isnull=False, discarded_by__isnull=False),
                name="tenders_matrix_version_discarded_has_who_when",
            ),
        ]

    def __str__(self):
        return f"{self.procedure} · versión {self.number}"


class RequirementOrigin(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto por el sistema"
    AGREGADO = "agregado", "Agregado por una persona"
    CIRCULAR = "circular", "Agregado por una circular"
    DEVUELTO = "devuelto", "Devuelto de las descartadas"


class RequirementState(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto"
    CONFIRMADO = "confirmado", "Confirmado"
    QUITADO = "quitado", "Quitado"
    SUGERIDO = "sugerido", "Sugerido"


class DoubtReason(models.TextChoices):
    """Por qué una fila es una sugerencia y no un requisito firme (REQ-035)."""

    NO_COINCIDEN = "no_coinciden", "Las dos respuestas no coinciden"
    DUDA = "duda", "El modelo dudó"
    DESCARTE_SIN_SUSTENTO = "descarte_sin_sustento", "Descarte sin indicio verificable"
    OPINION_INCOMPLETA = "opinion_incompleta", "Opinión incompleta"


class FilterMotive(models.TextChoices):
    """Motivos de descarte de una fila: la lista cerrada del ADR-0021 (los del ADR-0019
    más consecuencia o sanción y derecho posterior a la oferta)."""

    TITULO = "titulo", "Título"
    DATO_PROCEDIMIENTO = "dato_procedimiento", "Definición o dato del procedimiento"
    NORMA_APLICABLE = "norma_aplicable", "Norma aplicable"
    OBLIGACION_ORGANISMO = "obligacion_organismo", "Obligación del organismo"
    EJECUCION_CONTRATO = "ejecucion_contrato", "Obligación de la ejecución del contrato"
    FORMULARIO = "formulario", "Formulario a completar"
    INDICE_CARATULA = "indice_caratula", "Índice o carátula"
    CONSECUENCIA_SANCION = "consecuencia_sancion", "Consecuencia o sanción"
    DERECHO_POSTERIOR = "derecho_posterior", "Derecho posterior a la oferta"


class Requirement(models.Model):
    """Un requisito de la matriz (REQ-024). Un formal o económico tiene exactamente una
    cita; un técnico, un renglón como máximo."""

    version = models.ForeignKey(
        MatrixVersion,
        verbose_name="versión",
        on_delete=models.PROTECT,
        related_name="requirements",
    )
    number = models.PositiveIntegerField("número")
    category = models.CharField("clase", max_length=20, choices=RequirementClass.choices)
    items = models.JSONField("renglones", default=list)
    origin = models.CharField("origen", max_length=20, choices=RequirementOrigin.choices)
    state = models.CharField(
        "estado",
        max_length=20,
        choices=RequirementState.choices,
        default=RequirementState.PROPUESTO,
    )
    # Copia de lo propuesto por el sistema (clase, renglones y citas); no cambia (REQ-026).
    proposed = models.JSONField("propuesto", default=dict)
    previous = models.ForeignKey(
        "self",
        verbose_name="en la versión anterior",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="next_versions",
    )
    step = models.ForeignKey(
        RunStep,
        verbose_name="pedido al modelo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requirements",
    )
    passes = models.JSONField("pasadas", default=list)
    # Solo en un requisito sugerido (REQ-035); se conserva si pasa a requisito.
    doubt_reason = models.CharField(
        "motivo de la duda", max_length=30, choices=DoubtReason.choices, blank=True
    )
    # Las dos respuestas validadas, el indicio literal con su ubicación y los pedidos
    # (`step_a`, `step_b`) que las produjeron.
    doubt = models.JSONField("duda", default=dict)
    # La fila descartada de la que sale un requisito devuelto (REQ-033).
    restored_from = models.ForeignKey(
        "DiscardedRow",
        verbose_name="devuelto de",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="restored_requirements",
    )

    class Meta:
        db_table = "tenders_requirement"
        verbose_name = "requisito"
        verbose_name_plural = "requisitos"
        constraints = [
            _valid("category", RequirementClass, "tenders_requirement_category_valid"),
            _valid("origin", RequirementOrigin, "tenders_requirement_origin_valid"),
            _valid("state", RequirementState, "tenders_requirement_state_valid"),
            _is_json_array("items", "tenders_requirement_items_is_list"),
            _valid(
                "doubt_reason", DoubtReason, "tenders_requirement_doubt_reason_valid",
                blank=True,
            ),
            # Un sugerido tiene motivo de duda y no es técnico (REQ-035).
            models.CheckConstraint(
                condition=~Q(state=RequirementState.SUGERIDO)
                | (~Q(doubt_reason="") & ~Q(category=RequirementClass.TECNICO)),
                name="tenders_requirement_suggestion_has_reason",
            ),
            # Una descartada se devuelve una sola vez por versión.
            models.UniqueConstraint(
                fields=["version", "restored_from"],
                condition=Q(restored_from__isnull=False),
                name="tenders_requirement_restored_from_unique_in_version",
            ),
            # Un técnico es la fila de un renglón: uno como máximo.
            models.CheckConstraint(
                condition=~Q(category=RequirementClass.TECNICO)
                | Q(
                    LessThanOrEqual(
                        Func(
                            F("items"),
                            function="jsonb_array_length",
                            output_field=models.IntegerField(),
                        ),
                        1,
                    )
                ),
                name="tenders_requirement_technical_one_item",
            ),
            models.UniqueConstraint(
                fields=["version", "number"],
                name="tenders_requirement_number_unique_in_version",
            ),
        ]

    def __str__(self):
        return f"{self.version} · requisito {self.number}"


class QuoteScope(models.TextChoices):
    """Alcance de una cita de un requisito técnico."""

    PROPIA = "propia", "Del renglón"
    GENERAL = "general", "Común a todos los renglones"
    REPETIDA = "repetida", "Cita adicional de la misma condición"


class QuoteFlag(models.TextChoices):
    CITA_AMPLIA = "cita_amplia", "Cita amplia, revisar"


class RequirementQuote(models.Model):
    """Una cita de un requisito (REQ-025). `text` es igual al recorte del texto canónico
    de la lectura del tramo."""

    requirement = models.ForeignKey(
        Requirement,
        verbose_name="requisito",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    order = models.PositiveIntegerField("orden")
    segment = models.ForeignKey(
        Segment, verbose_name="tramo", on_delete=models.PROTECT, related_name="quotes"
    )
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal")
    # Vacío en un formal o económico, salvo `repetida` (cita adicional de la misma
    # condición, que no cuenta como la cita principal).
    scope = models.CharField(
        "alcance", max_length=10, choices=QuoteScope.choices, blank=True
    )
    quote_flag = models.CharField(
        "marca", max_length=20, choices=QuoteFlag.choices, blank=True
    )

    class Meta:
        db_table = "tenders_requirement_quote"
        verbose_name = "cita de un requisito"
        verbose_name_plural = "citas de requisitos"
        constraints = [
            _valid("scope", QuoteScope, "tenders_requirement_quote_scope_valid", blank=True),
            _valid(
                "quote_flag",
                QuoteFlag,
                "tenders_requirement_quote_flag_valid",
                blank=True,
            ),
            _char_range("tenders_requirement_quote"),
            models.UniqueConstraint(
                fields=["requirement", "order"],
                name="tenders_requirement_quote_order_unique",
            ),
        ]


class SourceEffect(models.TextChoices):
    MODIFICA = "modifica", "Modifica"
    ACLARA = "aclara", "Aclara"
    SUPRIME = "suprime", "Suprime"


class RequirementSource(models.Model):
    """Texto que una circular o una respuesta suma a una cita de un requisito (REQ-031).
    El texto vigente de una cita es el del último `modifica` por fecha."""

    requirement = models.ForeignKey(
        Requirement,
        verbose_name="requisito",
        on_delete=models.PROTECT,
        related_name="sources",
    )
    quote = models.ForeignKey(
        RequirementQuote,
        verbose_name="cita alcanzada",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sources",
    )
    effect = models.CharField("efecto", max_length=10, choices=SourceEffect.choices)
    segment = models.ForeignKey(
        Segment,
        verbose_name="tramo de la circular",
        on_delete=models.PROTECT,
        related_name="requirement_sources",
    )
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal")
    issued_on = models.DateField("fecha del documento")
    step = models.ForeignKey(
        RunStep,
        verbose_name="pedido al modelo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requirement_sources",
    )
    # Dónde está el texto que la circular reemplaza cuando no es la cita alcanzada: un
    # anexo sin requisitos. Los tres campos van juntos o ninguno.
    original_segment = models.ForeignKey(
        Segment,
        verbose_name="tramo del original",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="requirement_source_originals",
    )
    original_char_start = models.PositiveIntegerField(
        "inicio del original en el texto canónico", null=True, blank=True
    )
    original_char_end = models.PositiveIntegerField(
        "fin del original en el texto canónico", null=True, blank=True
    )

    class Meta:
        db_table = "tenders_requirement_source"
        verbose_name = "fuente de circular"
        verbose_name_plural = "fuentes de circulares"
        constraints = [
            _valid("effect", SourceEffect, "tenders_requirement_source_effect_valid"),
            _char_range("tenders_requirement_source"),
            models.CheckConstraint(
                condition=(
                    Q(original_segment__isnull=True, original_char_start__isnull=True,
                      original_char_end__isnull=True)
                    | Q(original_segment__isnull=False,
                        original_char_start__isnull=False,
                        original_char_end__isnull=False,
                        original_char_end__gte=F("original_char_start"))
                ),
                name="tenders_requirement_source_original_valid",
            ),
        ]


class ConsequenceType(models.TextChoices):
    """Tipos de consecuencia del incumplimiento: la lista cerrada de la spec (REQ-029)."""

    DESESTIMACION = "desestimacion", "Desestimación sin posibilidad de subsanar"
    INTIMACION_SUBSANAR = (
        "intimacion_subsanar",
        "Intimación a subsanar; si no se subsana, desestimación",
    )
    CONSULTAR_OFERENTE = "consultar_oferente", "Consultar al oferente"
    APROBACION_CONDICIONADA = "aprobacion_condicionada", "Aprobación condicionada"
    APROBAR_IGUAL = "aprobar_igual", "Aprobar de todas maneras"
    OTRA_PLIEGO = "otra_pliego", "Otra consecuencia prevista en el pliego"
    NO_DETERMINADA = "no_determinada", "No determinada"


# Solo los elige un evaluador; el sistema no los sugiere.
EVALUATOR_ONLY_TYPES = (
    ConsequenceType.APROBACION_CONDICIONADA,
    ConsequenceType.APROBAR_IGUAL,
)


class ConsequenceOrigin(models.TextChoices):
    SISTEMA = "sistema", "Sistema"
    PERSONA = "persona", "Persona"


class Consequence(models.Model):
    """Una consecuencia posible de no cumplir un requisito (REQ-029). La elige siempre
    un evaluador, con su motivo."""

    requirement = models.ForeignKey(
        Requirement,
        verbose_name="requisito",
        on_delete=models.PROTECT,
        related_name="consequences",
    )
    consequence_type = models.CharField(
        "tipo", max_length=30, choices=ConsequenceType.choices
    )
    # Tramos del pliego con sus posiciones, o unidades de la norma por su `id`.
    grounds = models.JSONField("fundamentos", default=list)
    origin = models.CharField("origen", max_length=10, choices=ConsequenceOrigin.choices)
    step = models.ForeignKey(
        RunStep,
        verbose_name="pedido al modelo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="consequences",
    )
    chosen = models.BooleanField("elegida", default=False)
    chosen_by = _user_fk("elegida por", "consequences_chosen", null=True)
    chosen_at = models.DateTimeField("elegida el", null=True, blank=True)
    # El motivo del evaluador; en una aprobación condicionada, la condición.
    chosen_note = models.TextField("motivo", blank=True)

    class Meta:
        db_table = "tenders_consequence"
        verbose_name = "consecuencia"
        verbose_name_plural = "consecuencias"
        constraints = [
            _valid(
                "consequence_type", ConsequenceType, "tenders_consequence_type_valid"
            ),
            _valid("origin", ConsequenceOrigin, "tenders_consequence_origin_valid"),
            _is_json_array("grounds", "tenders_consequence_grounds_is_list"),
            # El sistema no sugiere aprobación condicionada ni aprobar de todas maneras.
            models.CheckConstraint(
                condition=~Q(
                    origin=ConsequenceOrigin.SISTEMA,
                    consequence_type__in=EVALUATOR_ONLY_TYPES,
                ),
                name="tenders_consequence_evaluator_only_types",
            ),
            # "No determinada" es el estado de un requisito sin sugerencia: la pone el
            # sistema y no se elige.
            models.CheckConstraint(
                condition=~Q(consequence_type=ConsequenceType.NO_DETERMINADA)
                | Q(origin=ConsequenceOrigin.SISTEMA, chosen=False),
                name="tenders_consequence_undetermined_not_chosen",
            ),
            models.CheckConstraint(
                condition=Q(chosen=False)
                | Q(chosen_by__isnull=False, chosen_at__isnull=False),
                name="tenders_consequence_chosen_has_who_when",
            ),
            models.UniqueConstraint(
                fields=["requirement"],
                condition=Q(chosen=True),
                name="tenders_consequence_one_chosen",
            ),
        ]


class PendingReason(models.TextChoices):
    """Por qué un tramo queda pendiente de revisión en una versión (REQ-028)."""

    PAGINA_ILEGIBLE = "pagina_ilegible", "Página ilegible"
    PAGINA_DUDOSA = "pagina_dudosa", "Página dudosa"
    TABLA = "tabla", "Tabla"
    NO_UBICADO = "no_ubicado", "Tramo no ubicado"
    SIN_DISPOSICION = "sin_disposicion", "Sin disposición del modelo"
    MARCADORES = "marcadores", "Descartado con marcadores de obligación"
    RENGLON_SIN_ESPECIFICACIONES = (
        "renglon_sin_especificaciones",
        "Renglón sin especificaciones",
    )


class PendingResolution(models.TextChoices):
    SIN_REQUISITOS = "sin_requisitos", "Revisado, sin requisitos"
    REQUISITO_AGREGADO = "requisito_agregado", "Requisito agregado"


class PendingItem(models.Model):
    """Un tramo pendiente de revisión dentro de una versión (REQ-028)."""

    version = models.ForeignKey(
        MatrixVersion,
        verbose_name="versión",
        on_delete=models.PROTECT,
        related_name="pending_items",
    )
    segment = models.ForeignKey(
        Segment,
        verbose_name="tramo",
        on_delete=models.PROTECT,
        related_name="pending_items",
    )
    reason = models.CharField("motivo", max_length=30, choices=PendingReason.choices)
    resolved_by = _user_fk("resuelto por", "pending_items_resolved", null=True)
    resolved_at = models.DateTimeField("resuelto", null=True, blank=True)
    resolution = models.CharField(
        "resolución", max_length=20, choices=PendingResolution.choices, blank=True
    )

    class Meta:
        db_table = "tenders_pending_item"
        verbose_name = "pendiente de revisión"
        verbose_name_plural = "pendientes de revisión"
        constraints = [
            _valid("reason", PendingReason, "tenders_pending_item_reason_valid"),
            _valid(
                "resolution",
                PendingResolution,
                "tenders_pending_item_resolution_valid",
                blank=True,
            ),
            # Resuelto es: con resolución, quién y cuándo; o sin ninguna de las tres.
            models.CheckConstraint(
                condition=Q(
                    resolution="", resolved_by__isnull=True, resolved_at__isnull=True
                )
                | (
                    ~Q(resolution="")
                    & Q(resolved_by__isnull=False, resolved_at__isnull=False)
                ),
                name="tenders_pending_item_resolution_has_who_when",
            ),
        ]


class ChangeAction(models.TextChoices):
    CONFIRMAR = "confirmar", "Confirmar"
    CORREGIR = "corregir", "Corregir"
    QUITAR = "quitar", "Quitar"
    RESTITUIR = "restituir", "Restituir"
    AGREGAR = "agregar", "Agregar"
    ELEGIR_CONSECUENCIA = "elegir_consecuencia", "Elegir la consecuencia"
    DEVOLVER = "devolver", "Devolver de las descartadas"
    ACEPTAR_SUGERENCIA = "aceptar_sugerencia", "Pasar una sugerencia a requisito"


class RequirementChange(models.Model):
    """Historial de un requisito (REQ-026). Solo se insertan filas."""

    requirement = models.ForeignKey(
        Requirement,
        verbose_name="requisito",
        on_delete=models.PROTECT,
        related_name="changes",
    )
    action = models.CharField("acción", max_length=20, choices=ChangeAction.choices)
    before = models.JSONField("antes", null=True, blank=True)
    after = models.JSONField("después", null=True, blank=True)
    user = _user_fk("usuario", "requirement_changes")
    at = models.DateTimeField("momento", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent",
        verbose_name="hecho registrado",
        on_delete=models.PROTECT,
        related_name="requirement_changes",
    )

    class Meta:
        db_table = "tenders_requirement_change"
        verbose_name = "cambio de un requisito"
        verbose_name_plural = "cambios de requisitos"
        constraints = [
            _valid("action", ChangeAction, "tenders_requirement_change_action_valid"),
        ]


class DiscardedRow(models.Model):
    """Una fila descartada por el sistema (REQ-033, ADR-0021). Solo se insertan filas:
    devolverla no la modifica, crea un requisito con `restored_from`."""

    run = models.ForeignKey(
        MatrixRun,
        verbose_name="propuesta",
        on_delete=models.PROTECT,
        related_name="discarded_rows",
    )
    version = models.ForeignKey(
        MatrixVersion,
        verbose_name="versión",
        on_delete=models.PROTECT,
        related_name="discarded_rows",
    )
    order = models.PositiveIntegerField("orden en el pliego")
    segment = models.ForeignKey(
        Segment,
        verbose_name="tramo",
        on_delete=models.PROTECT,
        related_name="discarded_rows",
    )
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal")
    # Citas de las repetidas unificadas: lista de tramo, posiciones y texto.
    extra_quotes = models.JSONField("citas adicionales", default=list)
    category = models.CharField("clase", max_length=20, choices=RequirementClass.choices)
    items = models.JSONField("renglones", default=list)
    reason = models.CharField("motivo", max_length=30, choices=FilterMotive.choices)
    evidence_segment = models.ForeignKey(
        Segment,
        verbose_name="tramo del indicio",
        on_delete=models.PROTECT,
        related_name="+",
    )
    evidence_start = models.PositiveIntegerField("inicio del indicio")
    evidence_end = models.PositiveIntegerField("fin del indicio")
    evidence_text = models.TextField("indicio literal")
    vote_a = models.JSONField("respuesta A")
    vote_b = models.JSONField("respuesta B")
    step_a = models.ForeignKey(
        RunStep, verbose_name="pedido A", on_delete=models.PROTECT, related_name="+"
    )
    step_b = models.ForeignKey(
        RunStep, verbose_name="pedido B", on_delete=models.PROTECT, related_name="+"
    )
    source_pass = models.CharField("pasada que la propuso", max_length=20)
    passes = models.JSONField("pasadas que la encontraron", default=list)
    created_at = models.DateTimeField("momento", default=timezone.now)

    class Meta:
        db_table = "tenders_discarded_row"
        verbose_name = "fila descartada por el sistema"
        verbose_name_plural = "filas descartadas por el sistema"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    category__in=[RequirementClass.FORMAL, RequirementClass.ECONOMICO]
                ),
                name="tenders_discarded_row_category_valid",
            ),
            _valid("reason", FilterMotive, "tenders_discarded_row_reason_valid"),
            _valid("source_pass", PassName, "tenders_discarded_row_source_pass_valid"),
            _is_json_array("items", "tenders_discarded_row_items_is_list"),
            _is_json_array("extra_quotes", "tenders_discarded_row_extra_quotes_is_list"),
            _is_json_array("passes", "tenders_discarded_row_passes_is_list"),
            _char_range("tenders_discarded_row"),
            models.CheckConstraint(
                condition=Q(evidence_end__gte=F("evidence_start")),
                name="tenders_discarded_row_evidence_range_valid",
            ),
        ]


class NormSupport(models.Model):
    """El respaldo normativo de una sugerencia (REQ-036, ADR-0022). Solo se insertan
    filas; nunca cambia el estado de la sugerencia."""

    requirement = models.ForeignKey(
        Requirement,
        verbose_name="requisito",
        on_delete=models.PROTECT,
        related_name="norm_supports",
    )
    unit = models.ForeignKey(
        "norms.Unit",
        verbose_name="unidad de la norma",
        on_delete=models.PROTECT,
        related_name="+",
    )
    unit_label = models.CharField("norma y ruta", max_length=500)
    char_start = models.PositiveIntegerField("inicio en la unidad")
    char_end = models.PositiveIntegerField("fin en la unidad")
    text = models.TextField("cita literal")
    score = models.FloatField("puntaje del reranker")
    regime = models.CharField("régimen", max_length=200)
    corpus_version = models.PositiveIntegerField("versión de la normativa")
    step = models.ForeignKey(
        RunStep,
        verbose_name="pedido al modelo",
        on_delete=models.PROTECT,
        related_name="norm_supports",
    )
    created_at = models.DateTimeField("momento", default=timezone.now)

    class Meta:
        db_table = "tenders_norm_support"
        verbose_name = "respaldo normativo"
        verbose_name_plural = "respaldos normativos"
        constraints = [
            _char_range("tenders_norm_support"),
        ]


# --- Feature 014: historial de documentos y alta desde el pliego ---------------------------


class DocumentChangeAction(models.TextChoices):
    """Qué se hizo con un documento (ADR-0048, REQ-099). Los comparten el historial del
    pliego y el de las ofertas."""

    REEMPLAZAR = "reemplazar", "Reemplazar"
    RETIRAR = "retirar", "Retirar"
    RESTITUIR = "restituir", "Restituir"


class DocumentChange(models.Model):
    """Un cambio de un documento del pliego. Solo se insertan filas (P6): el documento y su
    archivo original nunca se modifican ni se borran. "Vigente", "reemplazado" y "retirado" se
    calculan del último cambio del documento. En `reemplazar`, `new_document` es la versión
    nueva, que ya existe como documento (se cargó con la carga de siempre)."""

    document = models.ForeignKey(
        Document, verbose_name="documento", on_delete=models.PROTECT, related_name="changes"
    )
    action = models.CharField(
        "acción", max_length=12, choices=DocumentChangeAction.choices
    )
    new_document = models.ForeignKey(
        Document, verbose_name="documento nuevo", on_delete=models.PROTECT, null=True,
        blank=True, related_name="replaces",
    )
    note = models.TextField("nota", blank=True)
    user = _user_fk("usuario", "tender_document_changes")
    at = models.DateTimeField("momento", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent", verbose_name="hecho registrado", on_delete=models.PROTECT,
        related_name="tender_document_changes",
    )

    class Meta:
        db_table = "tenders_document_change"
        verbose_name = "cambio de un documento del pliego"
        verbose_name_plural = "cambios de los documentos del pliego"
        indexes = [models.Index(fields=["document", "id"], name="tenders_docchange_document")]
        constraints = [
            _valid("action", DocumentChangeAction, "tenders_document_change_action_valid"),
            # El documento nuevo está si y solo si se reemplaza, y no es el mismo.
            models.CheckConstraint(
                condition=(
                    Q(action=DocumentChangeAction.REEMPLAZAR)
                    & Q(new_document__isnull=False)
                    & ~Q(new_document=F("document"))
                )
                | (
                    ~Q(action=DocumentChangeAction.REEMPLAZAR)
                    & Q(new_document__isnull=True)
                ),
                name="tenders_document_change_new_document_only_if_replaced",
            ),
        ]


class ProcedureDraft(models.Model):
    """El pliego subido que espera aprobación (ADR-0049, REQ-077). El procedimiento no puede
    existir antes de aprobarse (sus datos son obligatorios), así que el pliego espera aquí con
    la propuesta. `proposal` guarda cada dato con sus candidatos y su cita y, por dato,
    `{propuesto, corregido, motivo, quién, cuándo}`. No es un registro de hechos: cambia de
    estado."""

    file_name = models.CharField("nombre del archivo", max_length=255)
    file_format = models.CharField("formato", max_length=10, choices=FileFormat.choices)
    file_size = models.PositiveBigIntegerField("tamaño")
    file_sha256 = models.CharField("huella del archivo", max_length=64)
    content = models.BinaryField("contenido")
    proposal = models.JSONField("propuesta", default=dict)
    state = models.CharField(
        "estado", max_length=10, choices=ProposalState.choices,
        default=ProposalState.LEYENDO,
    )
    failure = models.TextField("motivo de la falla", blank=True)
    job = models.ForeignKey(
        Job, verbose_name="pedido", on_delete=models.PROTECT, null=True, blank=True,
        related_name="procedure_drafts",
    )
    created_by = _user_fk("subido por", "procedure_drafts_created")
    created_at = models.DateTimeField("subido", default=timezone.now)
    procedure = models.OneToOneField(
        Procedure, verbose_name="procedimiento resultante", on_delete=models.PROTECT,
        null=True, blank=True, related_name="draft",
    )

    class Meta:
        db_table = "tenders_procedure_draft"
        verbose_name = "borrador de procedimiento"
        verbose_name_plural = "borradores de procedimiento"
        constraints = [
            _valid("state", ProposalState, "tenders_procedure_draft_state_valid"),
            _valid("file_format", FileFormat, "tenders_procedure_draft_file_format_valid"),
            models.CheckConstraint(
                condition=Q(file_sha256__regex=SHA256_REGEX),
                name="tenders_procedure_draft_file_sha256_valid",
            ),
            # Aprobado dice qué procedimiento creó, y solo él.
            models.CheckConstraint(
                condition=(Q(state=ProposalState.APROBADO) & Q(procedure__isnull=False))
                | (~Q(state=ProposalState.APROBADO) & Q(procedure__isnull=True)),
                name="tenders_procedure_draft_procedure_only_if_approved",
            ),
        ]

    def __str__(self):
        return self.file_name
