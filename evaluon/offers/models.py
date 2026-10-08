"""Tablas de ofertas y fichas (plan 008, "Modelo de datos"; ADR-0026).

Un procedimiento tiene ofertas (una por oferente); cada oferta, sus documentos (con el
original byte por byte); cada documento, sus lecturas; cada lectura, sus pasajes de
búsqueda con su vector. Una ficha se arma contra una versión validada de la matriz y tiene
una fila por requisito, cada una con sus fragmentos; cada pedido al modelo y cada cambio
de una persona quedan registrados.

Las lecturas, los pasajes, los pedidos al modelo y el historial son de solo inserción:
triggers de la migración `0002_triggers` rechazan UPDATE y DELETE (P6), como en la 003.

Los valores de dominio van en español sin tildes; los estados propios del sistema, en
inglés, como en la 001 y la 003. Los datos personales del oferente solo existen en la base
(P4).
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from pgvector.django import VectorField

from evaluon.norms.models import SHA256_REGEX, ProposalState, TsvectorField
from evaluon.tenders.models import (
    DocumentChangeAction,
    Job,
    MatrixVersion,
    Procedure,
    Requirement,
)

EMBEDDING_DIMENSIONS = settings.EMBEDDINGS_DIMENSIONS


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
    condition = Q(**{f"{field}__in": choices.values})
    if blank:
        condition |= Q(**{field: ""})
    return models.CheckConstraint(condition=condition, name=name)


# --- Oferta y documentos ----------------------------------------------------------------


class Offer(models.Model):
    """Una oferta de un procedimiento (REQ-037). `bidder` es texto que escribe la
    persona: son datos personales que solo existen en la base (P4)."""

    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="offers",
    )
    number = models.PositiveIntegerField("número")
    bidder = models.CharField("oferente", max_length=300)
    created_at = models.DateTimeField("alta", default=timezone.now)
    created_by = _user_fk("dada de alta por", "offers_created")

    class Meta:
        db_table = "offers_offer"
        verbose_name = "oferta"
        verbose_name_plural = "ofertas"
        constraints = [
            models.UniqueConstraint(fields=["procedure", "number"],
                                    name="offers_offer_number_unique"),
            models.UniqueConstraint(fields=["procedure", "bidder"],
                                    name="offers_offer_bidder_unique"),
        ]

    def __str__(self):
        return f"{self.procedure} · oferta {self.number}"


class DocumentKind(models.TextChoices):
    """Tipo de un documento de la oferta: lo pone el sistema al leer, por reglas; nunca
    la persona que carga, y nunca excluye al documento de la búsqueda. Única excepción
    (T-189; REQ-073): la hoja de compliance la fija la acción "Subir hoja de compliance" de la
    Comisión y la clasificación por reglas no la pisa. Lo mismo el informe técnico del área
    (T-190; REQ-074)."""

    ECONOMICA = "economica", "Propuesta económica"
    TECNICA = "tecnica", "Documentación técnica"
    GARANTIA = "garantia", "Garantía"
    COMPLIANCE = "compliance", "Hoja de compliance"
    INFORME_TECNICO = "informe_tecnico", "Informe técnico del área"
    # Feature 014 (REQ-087): ficha o folleto técnico del oferente; lo fija la acción de la
    # Comisión al subirlo dentro de la oferta y la clasificación por reglas no lo pisa.
    ANEXO_TECNICO = "anexo_tecnico", "Anexo técnico de la oferta"
    OTRO = "otro", "Otro"


class FileFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    JPG = "jpg", "Foto JPG"
    PNG = "png", "Foto PNG"
    DOCX = "docx", "Word"


class Document(models.Model):
    """Un archivo de la oferta (REQ-037)."""

    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT, related_name="documents"
    )
    # Vacío si el sistema no pudo clasificarlo.
    kind = models.CharField("tipo", max_length=20, choices=DocumentKind.choices,
                            blank=True)
    title = models.TextField("título")
    file_name = models.CharField("nombre del archivo", max_length=255)
    file_format = models.CharField("formato", max_length=10, choices=FileFormat.choices)
    file_size = models.PositiveBigIntegerField("tamaño")
    file_sha256 = models.CharField("huella del archivo", max_length=64)
    loaded_at = models.DateTimeField("cargado", default=timezone.now)
    loaded_by = _user_fk("cargado por", "offer_documents_loaded")

    class Meta:
        db_table = "offers_document"
        verbose_name = "documento de la oferta"
        verbose_name_plural = "documentos de las ofertas"
        constraints = [
            _valid("kind", DocumentKind, "offers_document_kind_valid", blank=True),
            _valid("file_format", FileFormat, "offers_document_file_format_valid"),
            models.CheckConstraint(condition=Q(file_sha256__regex=SHA256_REGEX),
                                   name="offers_document_file_sha256_valid"),
            # El mismo archivo dos veces en una oferta se rechaza.
            models.UniqueConstraint(fields=["offer", "file_sha256"],
                                    name="offers_document_sha256_unique_in_offer"),
        ]

    def __str__(self):
        return f"{self.offer} · {self.title}"


class DocumentFile(models.Model):
    """El archivo original, byte por byte, en tabla aparte como en la 003."""

    document = models.OneToOneField(
        Document, verbose_name="documento", on_delete=models.PROTECT,
        primary_key=True, related_name="file",
    )
    content = models.BinaryField("contenido")

    class Meta:
        db_table = "offers_document_file"
        verbose_name = "archivo original de la oferta"
        verbose_name_plural = "archivos originales de las ofertas"


class Reading(models.Model):
    """Una lectura de un documento de la oferta. No se modifica."""

    document = models.ForeignKey(
        Document, verbose_name="documento", on_delete=models.PROTECT,
        related_name="readings",
    )
    sequence = models.PositiveIntegerField("número de lectura")
    # La lectura de la 001, página por página.
    pages = models.JSONField("lectura")
    canonical_text = models.TextField("texto canónico")
    canonical_sha256 = models.CharField("huella del texto canónico", max_length=64)
    tool_versions = models.JSONField("versiones de las herramientas")
    # Páginas por estado y origen; páginas no leídas y de baja confianza.
    report = models.JSONField("informe")
    created_at = models.DateTimeField("leída", default=timezone.now)
    job = models.ForeignKey(
        Job, verbose_name="pedido", on_delete=models.PROTECT, null=True, blank=True,
        related_name="offer_readings",
    )

    class Meta:
        db_table = "offers_reading"
        verbose_name = "lectura de la oferta"
        verbose_name_plural = "lecturas de las ofertas"
        constraints = [
            models.UniqueConstraint(fields=["document", "sequence"],
                                    name="offers_reading_sequence_unique"),
        ]

    def __str__(self):
        return f"{self.document} · lectura {self.sequence}"


class PassageOrigin(models.TextChoices):
    """Origen del texto de un pasaje de una oferta: los de la 001 y `vision`, el texto que el
    modelo transcribió mirando la imagen de la página (T-160; ADR-0041)."""

    PDF_TEXT = "pdf_text", "PDF con texto"
    OCR = "ocr", "Reconocimiento de texto"
    WEB = "web", "Página web"
    VISION = "vision", "Leída por visión"


class Passage(models.Model):
    """Un pasaje de una lectura: un bloque de texto de una sola página, con su vector y
    sus palabras. No se modifica. `text` es igual a `canonical_text[char_start:char_end]`."""

    reading = models.ForeignKey(
        Reading, verbose_name="lectura", on_delete=models.PROTECT, related_name="passages"
    )
    order = models.PositiveIntegerField("orden")
    key = models.CharField("clave", max_length=40)
    page = models.PositiveIntegerField("página")
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal")
    text_origin = models.CharField("origen del texto", max_length=10,
                                   choices=PassageOrigin.choices)
    ocr_confidence_min = models.FloatField("confianza mínima", null=True, blank=True)
    ocr_confidence_avg = models.FloatField("confianza promedio", null=True, blank=True)
    embedding = VectorField("vector", dimensions=EMBEDDING_DIMENSIONS)
    # Búsqueda por palabras con la normalización de la 001 (ADR-0007): la calcula la base.
    tsv = models.GeneratedField(
        expression=models.Func(F("text"), function="search_document",
                               output_field=TsvectorField()),
        output_field=TsvectorField(),
        db_persist=True,
        verbose_name="vector de búsqueda por palabras",
    )

    class Meta:
        db_table = "offers_passage"
        verbose_name = "pasaje de la oferta"
        verbose_name_plural = "pasajes de las ofertas"
        constraints = [
            _valid("text_origin", PassageOrigin, "offers_passage_text_origin_valid"),
            models.CheckConstraint(condition=Q(char_end__gte=F("char_start")),
                                   name="offers_passage_char_range_valid"),
            models.UniqueConstraint(fields=["reading", "key"],
                                    name="offers_passage_key_unique_in_reading"),
            models.UniqueConstraint(fields=["reading", "order"],
                                    name="offers_passage_order_unique_in_reading"),
        ]

    def __str__(self):
        return self.key


# --- Ficha -------------------------------------------------------------------------------


class SheetChannel(models.TextChoices):
    SCREEN = "screen", "Pantalla"
    EVAL = "eval", "Evaluación"


class Sheet(models.Model):
    """Una ficha: lo que una oferta dice de cada requisito de una matriz validada
    (REQ-039, REQ-043). Armar de nuevo crea una ficha nueva."""

    offer = models.ForeignKey(
        Offer, verbose_name="oferta", on_delete=models.PROTECT, related_name="sheets"
    )
    matrix_version = models.ForeignKey(
        MatrixVersion, verbose_name="versión de la matriz", on_delete=models.PROTECT,
        related_name="offer_sheets",
    )
    number = models.PositiveIntegerField("número")
    channel = models.CharField("canal", max_length=10, choices=SheetChannel.choices)
    # Cada lectura usada, con su huella.
    readings = models.JSONField("lecturas usadas")
    models_used = models.JSONField("modelos", db_column="models")
    parameters = models.JSONField("parámetros")
    prompt_versions = models.JSONField("versiones de las instrucciones")
    counts = models.JSONField("cuentas", default=dict)
    timings = models.JSONField("tiempos", default=dict)
    anomalies = models.JSONField("anomalías", default=list)
    # REQ-044: si la oferta trae documentación técnica y de qué documentos.
    technical_documents = models.JSONField("documentación técnica", default=dict)
    built_at = models.DateTimeField("armada", default=timezone.now)
    requested_by = _user_fk("pedida por", "sheets_requested")
    job = models.ForeignKey(
        Job, verbose_name="pedido", on_delete=models.PROTECT, null=True, blank=True,
        related_name="offer_sheets",
    )

    class Meta:
        db_table = "offers_sheet"
        verbose_name = "ficha"
        verbose_name_plural = "fichas"
        constraints = [
            _valid("channel", SheetChannel, "offers_sheet_channel_valid"),
            models.UniqueConstraint(fields=["offer", "number"],
                                    name="offers_sheet_number_unique"),
        ]

    def __str__(self):
        return f"{self.offer} · ficha {self.number}"


class Outcome(models.TextChoices):
    ENCONTRADO = "encontrado", "Encontrado"
    NO_ENCONTRADO = "no_encontrado", "No se encontró en la oferta"


class Quoted(models.TextChoices):
    """Estado de cotización de una fila técnica por renglón (REQ-044)."""

    COTIZADO = "cotizado", "Cotizado"
    NO_COTIZADO = "no_cotizado", "No cotizado"
    NO_SE_PUDO_LEER = "no_se_pudo_leer", "No se pudo leer"


class EntryState(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto"
    CONFIRMADO = "confirmado", "Confirmado"


class SheetEntry(models.Model):
    """Una fila de la ficha: un requisito no quitado de la matriz."""

    sheet = models.ForeignKey(
        Sheet, verbose_name="ficha", on_delete=models.PROTECT, related_name="entries"
    )
    requirement = models.ForeignKey(
        Requirement, verbose_name="requisito", on_delete=models.PROTECT,
        related_name="offer_entries",
    )
    outcome = models.CharField("resultado", max_length=20, choices=Outcome.choices)
    # Síntesis breve de lo ofrecido, sin juicio (REQ-041); puede estar vacía.
    synthesis = models.TextField("síntesis", blank=True)
    # Solo en filas técnicas por renglón.
    quoted = models.CharField("cotización", max_length=20, choices=Quoted.choices,
                              blank=True)
    unread_pages_warning = models.BooleanField("hay páginas sin leer", default=False)
    state = models.CharField("estado", max_length=20, choices=EntryState.choices,
                             default=EntryState.PROPUESTO)

    class Meta:
        db_table = "offers_sheet_entry"
        verbose_name = "fila de la ficha"
        verbose_name_plural = "filas de las fichas"
        constraints = [
            _valid("outcome", Outcome, "offers_sheet_entry_outcome_valid"),
            _valid("quoted", Quoted, "offers_sheet_entry_quoted_valid", blank=True),
            _valid("state", EntryState, "offers_sheet_entry_state_valid"),
            models.UniqueConstraint(fields=["sheet", "requirement"],
                                    name="offers_sheet_entry_requirement_unique"),
        ]


class FragmentOrigin(models.TextChoices):
    SISTEMA = "sistema", "Propuesto por el sistema"
    PERSONA = "persona", "Agregado por una persona"


class FragmentState(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto"
    CONFIRMADO = "confirmado", "Confirmado"
    QUITADO = "quitado", "Quitado"


class Fragment(models.Model):
    """Un fragmento de una fila. `text` es igual al recorte `char_start:char_end` del
    texto canónico de la lectura del pasaje (P3: literal por construcción)."""

    entry = models.ForeignKey(
        SheetEntry, verbose_name="fila", on_delete=models.PROTECT,
        related_name="fragments",
    )
    order = models.PositiveIntegerField("orden")
    passage = models.ForeignKey(
        Passage, verbose_name="pasaje", on_delete=models.PROTECT,
        related_name="fragments",
    )
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    text = models.TextField("texto literal")
    origin = models.CharField("origen", max_length=10, choices=FragmentOrigin.choices)
    state = models.CharField("estado", max_length=20, choices=FragmentState.choices,
                             default=FragmentState.PROPUESTO)
    # Copia de lo propuesto por el sistema; no cambia (REQ-042).
    proposed = models.JSONField("propuesto", default=dict)

    class Meta:
        db_table = "offers_fragment"
        verbose_name = "fragmento"
        verbose_name_plural = "fragmentos"
        constraints = [
            _valid("origin", FragmentOrigin, "offers_fragment_origin_valid"),
            _valid("state", FragmentState, "offers_fragment_state_valid"),
            models.CheckConstraint(condition=Q(char_end__gte=F("char_start")),
                                   name="offers_fragment_char_range_valid"),
            models.UniqueConstraint(fields=["entry", "order"],
                                    name="offers_fragment_order_unique_in_entry"),
        ]


class SheetStep(models.Model):
    """Un pedido al modelo (P6): candidatos con puntajes, pedido, salida cruda y lo
    interpretado. Solo se insertan filas."""

    sheet = models.ForeignKey(
        Sheet, verbose_name="ficha", on_delete=models.PROTECT, related_name="steps"
    )
    entry = models.ForeignKey(
        SheetEntry, verbose_name="fila", on_delete=models.PROTECT, related_name="steps",
    )
    candidates = models.JSONField("candidatos")
    request = models.JSONField("pedido", null=True, blank=True)
    raw_output = models.TextField("salida cruda", blank=True)
    parsed = models.JSONField("interpretado", null=True, blank=True)
    anomalies = models.JSONField("anomalías", default=list)
    retry_of = models.ForeignKey(
        "self", verbose_name="reintento de", on_delete=models.PROTECT, null=True,
        blank=True, related_name="retries",
    )
    timings = models.JSONField("tiempos", default=dict)

    class Meta:
        db_table = "offers_sheet_step"
        verbose_name = "pedido al modelo de la ficha"
        verbose_name_plural = "pedidos al modelo de las fichas"


class ChangeAction(models.TextChoices):
    CONFIRMAR = "confirmar", "Confirmar"
    CORREGIR = "corregir", "Corregir"
    QUITAR = "quitar", "Quitar"
    RESTITUIR = "restituir", "Restituir"
    AGREGAR = "agregar", "Agregar"


class Change(models.Model):
    """Historial de la ficha (REQ-042). Solo se insertan filas."""

    entry = models.ForeignKey(
        SheetEntry, verbose_name="fila", on_delete=models.PROTECT, related_name="changes"
    )
    fragment = models.ForeignKey(
        Fragment, verbose_name="fragmento", on_delete=models.PROTECT, null=True,
        blank=True, related_name="changes",
    )
    action = models.CharField("acción", max_length=20, choices=ChangeAction.choices)
    before = models.JSONField("antes", null=True, blank=True)
    after = models.JSONField("después", null=True, blank=True)
    user = _user_fk("usuario", "offer_changes")
    at = models.DateTimeField("momento", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent", verbose_name="hecho registrado", on_delete=models.PROTECT,
        related_name="offer_changes",
    )

    class Meta:
        db_table = "offers_change"
        verbose_name = "cambio de la ficha"
        verbose_name_plural = "cambios de las fichas"
        constraints = [
            _valid("action", ChangeAction, "offers_change_action_valid"),
        ]


# --- Feature 014: historial de documentos y alta desde los archivos --------------------------


class DocumentChange(models.Model):
    """Un cambio de un documento de la oferta. Solo se insertan filas (P6); ver
    `tenders.DocumentChange`, de la que es gemela (ADR-0048, REQ-099)."""

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
    user = _user_fk("usuario", "offer_document_changes")
    at = models.DateTimeField("momento", default=timezone.now)
    event = models.ForeignKey(
        "audit.AuditEvent", verbose_name="hecho registrado", on_delete=models.PROTECT,
        related_name="offer_document_changes",
    )

    class Meta:
        db_table = "offers_document_change"
        verbose_name = "cambio de un documento de la oferta"
        verbose_name_plural = "cambios de los documentos de las ofertas"
        indexes = [models.Index(fields=["document", "id"], name="offers_docchange_document")]
        constraints = [
            _valid("action", DocumentChangeAction, "offers_document_change_action_valid"),
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
                name="offers_document_change_new_document_only_if_replaced",
            ),
        ]


class OfferDraft(models.Model):
    """Los archivos de una oferta que espera aprobación (REQ-083; ADR-0049): la oferta no
    puede existir sin oferente, así que los archivos esperan aquí hasta que la Comisión aprueba
    o corrige el nombre y el CUIT propuestos. `proposal` guarda cada dato con su cita y, por
    dato, `{propuesto, corregido, motivo, quién, cuándo}`. Los datos personales solo existen
    en la base (P4). No es un registro de hechos: cambia de estado."""

    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="offer_drafts",
    )
    proposal = models.JSONField("propuesta", default=dict)
    state = models.CharField(
        "estado", max_length=10, choices=ProposalState.choices,
        default=ProposalState.LEYENDO,
    )
    failure = models.TextField("motivo de la falla", blank=True)
    job = models.ForeignKey(
        Job, verbose_name="pedido", on_delete=models.PROTECT, null=True, blank=True,
        related_name="offer_drafts",
    )
    created_by = _user_fk("subido por", "offer_drafts_created")
    created_at = models.DateTimeField("subido", default=timezone.now)
    offer = models.OneToOneField(
        Offer, verbose_name="oferta resultante", on_delete=models.PROTECT, null=True,
        blank=True, related_name="draft",
    )

    class Meta:
        db_table = "offers_offer_draft"
        verbose_name = "borrador de oferta"
        verbose_name_plural = "borradores de oferta"
        constraints = [
            _valid("state", ProposalState, "offers_offer_draft_state_valid"),
            models.CheckConstraint(
                condition=(Q(state=ProposalState.APROBADO) & Q(offer__isnull=False))
                | (~Q(state=ProposalState.APROBADO) & Q(offer__isnull=True)),
                name="offers_offer_draft_offer_only_if_approved",
            ),
        ]

    def __str__(self):
        return f"{self.procedure} · borrador {self.pk}"


class OfferDraftFile(models.Model):
    """Un archivo de un borrador de oferta (bytes y huella)."""

    draft = models.ForeignKey(
        OfferDraft, verbose_name="borrador", on_delete=models.PROTECT, related_name="files"
    )
    file_name = models.CharField("nombre del archivo", max_length=255)
    file_format = models.CharField("formato", max_length=10, choices=FileFormat.choices)
    file_size = models.PositiveBigIntegerField("tamaño")
    file_sha256 = models.CharField("huella del archivo", max_length=64)
    content = models.BinaryField("contenido")

    class Meta:
        db_table = "offers_offer_draft_file"
        verbose_name = "archivo de un borrador de oferta"
        verbose_name_plural = "archivos de los borradores de oferta"
        constraints = [
            _valid("file_format", FileFormat, "offers_offer_draft_file_format_valid"),
            models.CheckConstraint(
                condition=Q(file_sha256__regex=SHA256_REGEX),
                name="offers_offer_draft_file_sha256_valid",
            ),
            # El mismo archivo dos veces en un borrador se rechaza.
            models.UniqueConstraint(
                fields=["draft", "file_sha256"], name="offers_offer_draft_file_sha256_unique"
            ),
        ]

    def __str__(self):
        return self.file_name
