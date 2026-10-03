"""Tablas de la normativa (plan 001, "Modelo de datos", sección `norms`).

Una norma tiene uno o más documentos (cada archivo cargado, que es una parte de la norma:
el cuerpo o un anexo); cada documento, una o más lecturas; cada lectura, sus unidades
citables; cada unidad base, sus pasajes de búsqueda. Las relaciones entre normas, las
modificatorias sin cargar y las versiones de la normativa completan el modelo.

Las restricciones que el plan fija van en la base, para que valgan venga de donde venga
la escritura. La columna `tsv` de `norms_passage` y las funciones SQL de unidades
consultables son de T-009.

Los valores que nombran un concepto jurídico van en español sin tildes (ADR-0004); los
estados propios del sistema, en inglés.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from pgvector.django import VectorField

# Dimensiones del vector de `bge-m3` (plan 001, "Servicios"). Se definen una sola vez, en
# settings.EMBEDDINGS_DIMENSIONS (T-054).
EMBEDDING_DIMENSIONS = settings.EMBEDDINGS_DIMENSIONS

# Parte de una norma: `cuerpo` o la clave de un anexo (`anexo`, `anexo-i`, `anexo-ii`).
BODY_PART = "cuerpo"
ANNEX_PART_REGEX = r"^anexo(-[a-z0-9]+)?$"

SHA256_REGEX = r"^[0-9a-f]{64}$"


class Category(models.TextChoices):
    """Categoría de la norma (REQ-017)."""

    REGIMEN_ESPECIFICO = "regimen_especifico", "Régimen específico"
    OTRA_NORMATIVA = "otra_normativa", "Otra normativa aplicable"
    MARCO_NACIONAL = "marco_nacional", "Marco nacional"
    DICTAMEN_LEGAL = "dictamen_legal", "Dictamen legal"
    RECOMENDACION_AUDITORIA = "recomendacion_auditoria", "Recomendación de auditoría"


class SameNormConfirmation(models.TextChoices):
    """Qué confirmó la persona ante el aviso de "misma norma" (REQ-011)."""

    OTHER_FILE = "other_file", "Otro archivo de la misma norma"
    NEW_VERSION = "new_version", "Versión nueva"


class FileFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    HTML = "html", "Página web"


class ReadingStatus(models.TextChoices):
    PENDING = "pending", "Leída, sin validar"
    VALIDATED = "validated", "Validada"
    SUPERSEDED = "superseded", "Reemplazada"


class UnitType(models.TextChoices):
    """Tipos de unidad citable (REQ-003; ADR-0004 y plan, "Texto normativo sin número de
    artículo")."""

    ARTICULO = "articulo", "Artículo"
    INCISO = "inciso", "Inciso"
    ANEXO = "anexo", "Anexo"
    CONSIDERANDO = "considerando", "Considerando"
    CLAUSULA = "clausula", "Cláusula"
    PUNTO = "punto", "Punto"
    PARRAFO = "parrafo", "Párrafo"


class TextOrigin(models.TextChoices):
    """De dónde salió el texto de una unidad (REQ-015)."""

    PDF_TEXT = "pdf_text", "PDF con texto"
    OCR = "ocr", "Reconocimiento de texto"
    WEB = "web", "Página web"


class RelationType(models.TextChoices):
    MODIFICA = "modifica", "Modifica"
    COMPLEMENTA = "complementa", "Complementa"
    REGLAMENTA = "reglamenta", "Reglamenta"
    DEROGA = "deroga", "Deroga"


class TsvectorField(models.Field):
    """Columna `tsvector` de Postgres. Solo declara el tipo: el valor lo calcula la base
    (ver `Passage.tsv`). Así no hace falta instalar `django.contrib.postgres`."""

    description = "Vector de búsqueda de texto de Postgres"

    def db_type(self, connection):
        return "tsvector"


def _user_fk(verbose_name, related_name, null=False):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        related_name=related_name,
        null=null,
        blank=null,
    )


class Norm(models.Model):
    """Una fila por norma (REQ-001, REQ-017, REQ-020)."""

    category = models.CharField("categoría", max_length=30, choices=Category.choices)
    # Tipo, número, año y organismo, normalizados por la carga (T-014). Juntos
    # identifican "la misma norma" (REQ-011).
    norm_type = models.CharField("tipo", max_length=50)
    number = models.CharField("número", max_length=30)
    year = models.PositiveSmallIntegerField("año")
    issuer = models.CharField("organismo emisor", max_length=200)
    title = models.TextField("título")
    # Nombre con que se cita la norma, tal como lo escribe la persona al cargarla
    # ("Disposición AFIP 297/03"). Obligatorio y no vacío (T-055).
    citation = models.TextField("nombre de cita")
    # Verdadero en la norma que aprueba un régimen general de contrataciones (REQ-020).
    general_regime = models.BooleanField("régimen general", default=False)
    created_at = models.DateTimeField("alta", default=timezone.now)
    created_by = _user_fk("dada de alta por", "norms_created")

    class Meta:
        db_table = "norms_norm"
        verbose_name = "norma"
        verbose_name_plural = "normas"
        constraints = [
            models.CheckConstraint(
                condition=Q(category__in=Category.values),
                name="norms_norm_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(citation__regex=r"\S"),
                name="norms_norm_citation_not_blank",
            ),
            models.UniqueConstraint(
                fields=["norm_type", "number", "year", "issuer"],
                name="norms_norm_identity_unique",
            ),
            models.CheckConstraint(
                condition=Q(general_regime=False)
                | Q(category=Category.REGIMEN_ESPECIFICO),
                name="norms_norm_general_regime_only_specific",
            ),
        ]

    def __str__(self):
        return f"{self.norm_type} {self.number}/{self.year} ({self.issuer})"


class Document(models.Model):
    """Una fila por archivo cargado; cada uno es una parte de la norma."""

    norm = models.ForeignKey(
        Norm, verbose_name="norma", on_delete=models.PROTECT, related_name="documents"
    )
    part = models.CharField("parte", max_length=30, default=BODY_PART)
    publication_date = models.DateField("fecha de publicación")
    # Desde cuándo rige el texto; lo escribe la persona, el sistema no lo calcula.
    effective_from = models.DateField("vigente desde")
    effective_to = models.DateField("vigente hasta", null=True, blank=True)
    source = models.TextField("fuente")
    version_number = models.PositiveIntegerField(
        "número de versión", null=True, blank=True
    )
    in_use = models.BooleanField("en uso", default=False)
    same_norm_confirmation = models.CharField(
        "confirmación de misma norma",
        max_length=20,
        choices=SameNormConfirmation.choices,
        blank=True,
    )
    file_name = models.CharField("nombre del archivo", max_length=255)
    file_format = models.CharField("formato", max_length=10, choices=FileFormat.choices)
    file_size = models.PositiveBigIntegerField("tamaño")
    # Huella del archivo original: comprobación de "mismo archivo" (REQ-011).
    file_sha256 = models.CharField("huella del archivo", max_length=64, unique=True)
    loaded_at = models.DateTimeField("cargado", default=timezone.now)
    loaded_by = _user_fk("cargado por", "documents_loaded")

    class Meta:
        db_table = "norms_document"
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        constraints = [
            models.CheckConstraint(
                condition=Q(part=BODY_PART) | Q(part__regex=ANNEX_PART_REGEX),
                name="norms_document_part_valid",
            ),
            models.CheckConstraint(
                condition=Q(same_norm_confirmation="")
                | Q(same_norm_confirmation__in=SameNormConfirmation.values),
                name="norms_document_same_norm_confirmation_valid",
            ),
            models.CheckConstraint(
                condition=Q(file_format__in=FileFormat.values),
                name="norms_document_file_format_valid",
            ),
            models.CheckConstraint(
                condition=Q(file_sha256__regex=SHA256_REGEX),
                name="norms_document_file_sha256_valid",
            ),
            # Un documento en uso es el de una versión de su parte.
            models.CheckConstraint(
                condition=Q(in_use=False) | Q(version_number__isnull=False),
                name="norms_document_in_use_has_version",
            ),
            # A lo sumo un documento en uso por norma, parte y versión.
            models.UniqueConstraint(
                fields=["norm", "part", "version_number"],
                condition=Q(in_use=True),
                name="norms_document_one_in_use_per_part_version",
            ),
        ]

    def __str__(self):
        return f"{self.norm} · {self.part} · {self.file_name}"


class DocumentFile(models.Model):
    """El archivo original, byte por byte (REQ-002). Aparte, para que listar documentos
    no arrastre los archivos."""

    document = models.OneToOneField(
        Document,
        verbose_name="documento",
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="file",
    )
    content = models.BinaryField("contenido")

    class Meta:
        db_table = "norms_document_file"
        verbose_name = "archivo original"
        verbose_name_plural = "archivos originales"


class Reading(models.Model):
    """Una fila por lectura de un documento (REQ-004, REQ-005)."""

    document = models.ForeignKey(
        Document,
        verbose_name="documento",
        on_delete=models.PROTECT,
        related_name="readings",
    )
    sequence = models.PositiveIntegerField("número de lectura")
    status = models.CharField(
        "estado",
        max_length=20,
        choices=ReadingStatus.choices,
        default=ReadingStatus.PENDING,
    )
    pages = models.JSONField("lectura")
    canonical_text = models.TextField("texto canónico")
    canonical_sha256 = models.CharField("huella del texto canónico", max_length=64)
    tool_versions = models.JSONField("versiones de las herramientas")
    report = models.JSONField("informe")
    report_text = models.TextField("informe legible")
    created_at = models.DateTimeField("leída", default=timezone.now)
    created_by = _user_fk("leída por", "readings_created")
    validated_at = models.DateTimeField("validada", null=True, blank=True)
    validated_by = _user_fk("validada por", "readings_validated", null=True)
    superseded_at = models.DateTimeField("reemplazada", null=True, blank=True)

    class Meta:
        db_table = "norms_reading"
        verbose_name = "lectura"
        verbose_name_plural = "lecturas"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=ReadingStatus.values),
                name="norms_reading_status_valid",
            ),
            models.UniqueConstraint(
                fields=["document", "sequence"],
                name="norms_reading_sequence_unique",
            ),
        ]

    def __str__(self):
        return f"{self.document} · lectura {self.sequence}"


class Unit(models.Model):
    """Una fila por unidad citable (REQ-003). No se modifica."""

    reading = models.ForeignKey(
        Reading, verbose_name="lectura", on_delete=models.PROTECT, related_name="units"
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="contenida en",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    unit_type = models.CharField("tipo", max_length=20, choices=UnitType.choices)
    # Vacío en una unidad `clausula`: no se le inventa un número.
    number = models.CharField("número", max_length=30, blank=True)
    label = models.TextField("etiqueta")
    key = models.CharField("clave", max_length=255)
    path = models.TextField("ruta")
    order = models.PositiveIntegerField("orden")
    page_start = models.PositiveIntegerField("página inicial", null=True, blank=True)
    page_end = models.PositiveIntegerField("página final", null=True, blank=True)
    char_start = models.PositiveIntegerField("inicio en el texto canónico")
    char_end = models.PositiveIntegerField("fin en el texto canónico")
    # Igual a canonical_text[char_start:char_end] de su lectura.
    text = models.TextField("texto literal")
    text_origin = models.CharField(
        "origen del texto", max_length=10, choices=TextOrigin.choices
    )
    ocr_confidence_min = models.FloatField("confianza mínima", null=True, blank=True)
    ocr_confidence_avg = models.FloatField("confianza promedio", null=True, blank=True)

    class Meta:
        db_table = "norms_unit"
        verbose_name = "unidad"
        verbose_name_plural = "unidades"
        constraints = [
            models.CheckConstraint(
                condition=Q(unit_type__in=UnitType.values),
                name="norms_unit_unit_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(text_origin__in=TextOrigin.values),
                name="norms_unit_text_origin_valid",
            ),
            models.CheckConstraint(
                condition=Q(char_end__gte=models.F("char_start")),
                name="norms_unit_char_range_valid",
            ),
            models.UniqueConstraint(
                fields=["reading", "key"], name="norms_unit_key_unique_in_reading"
            ),
        ]

    def __str__(self):
        return self.key


class Passage(models.Model):
    """Pasaje de búsqueda de una unidad base. Solo sirve para buscar; nunca se muestra
    ni se cita. La columna `tsv` la calcula la base (T-009)."""

    unit = models.ForeignKey(
        Unit, verbose_name="unidad", on_delete=models.PROTECT, related_name="passages"
    )
    order = models.PositiveIntegerField("orden")
    char_start = models.PositiveIntegerField("inicio en el texto de la unidad")
    char_end = models.PositiveIntegerField("fin en el texto de la unidad")
    header = models.TextField("encabezado de contexto")
    text = models.TextField("texto")
    # Búsqueda por palabras (REQ-010; ADR-0007): la calcula la base con la función SQL
    # `search_document` sobre el texto del pasaje (sin el encabezado). Nada fuera de
    # esa función arma `tsv`. Se consulta con `tsv @@ search_query(...)`. Su índice
    # GIN, `norms_passage_tsv_gin`, lo crea la migración 0004 con SQL propio.
    tsv = models.GeneratedField(
        expression=models.Func(
            models.F("text"), function="search_document", output_field=TsvectorField()
        ),
        output_field=TsvectorField(),
        db_persist=True,
        verbose_name="vector de búsqueda por palabras",
    )
    # Vector de header más text; sin índice aproximado (búsqueda exacta).
    embedding = VectorField("vector", dimensions=EMBEDDING_DIMENSIONS)
    embedding_model = models.CharField("modelo de embeddings", max_length=200)
    embedding_revision = models.CharField("huella del modelo", max_length=64)

    class Meta:
        db_table = "norms_passage"
        verbose_name = "pasaje"
        verbose_name_plural = "pasajes"
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "order"], name="norms_passage_order_unique_in_unit"
            ),
            models.CheckConstraint(
                condition=Q(char_end__gte=models.F("char_start")),
                name="norms_passage_char_range_valid",
            ),
        ]


class Relation(models.Model):
    """Relación entre normas y, cuando corresponde, entre unidades (REQ-006, REQ-007).
    Guarda claves de unidad, no identificaciones internas: vale para la norma y no para
    una lectura."""

    relation_type = models.CharField(
        "tipo de relación", max_length=20, choices=RelationType.choices
    )
    source_norm = models.ForeignKey(
        Norm,
        verbose_name="norma de origen",
        on_delete=models.PROTECT,
        related_name="relations_from",
    )
    target_norm = models.ForeignKey(
        Norm,
        verbose_name="norma alcanzada",
        on_delete=models.PROTECT,
        related_name="relations_to",
    )
    source_unit_key = models.CharField("unidad de origen", max_length=255, blank=True)
    target_unit_key = models.CharField("unidad alcanzada", max_length=255, blank=True)
    # Desde cuándo rige el cambio; lo escribe la persona.
    effective_date = models.DateField("vigente desde")
    registered_at = models.DateTimeField("registrada", default=timezone.now)
    registered_by = _user_fk("registrada por", "relations_registered")

    class Meta:
        db_table = "norms_relation"
        verbose_name = "relación"
        verbose_name_plural = "relaciones"
        constraints = [
            models.CheckConstraint(
                condition=Q(relation_type__in=RelationType.values),
                name="norms_relation_relation_type_valid",
            ),
        ]


class PendingAmendment(models.Model):
    """Modificatoria de una norma que todavía no está cargada (REQ-021)."""

    target_norm = models.ForeignKey(
        Norm,
        verbose_name="norma alcanzada",
        on_delete=models.PROTECT,
        related_name="pending_amendments",
    )
    norm_type = models.CharField("tipo", max_length=50)
    number = models.CharField("número", max_length=30)
    year = models.PositiveSmallIntegerField("año")
    issuer = models.CharField("organismo emisor", max_length=200)
    source_ref = models.TextField("referencia en la fuente")
    registered_at = models.DateTimeField("anotada", default=timezone.now)
    registered_by = _user_fk("anotada por", "pending_amendments_registered")
    # La norma cargada que le corresponde; vacío mientras está sin cargar.
    loaded_norm = models.ForeignKey(
        Norm,
        verbose_name="norma cargada",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="amendment_entries",
    )

    class Meta:
        db_table = "norms_pending_amendment"
        verbose_name = "modificatoria sin cargar"
        verbose_name_plural = "modificatorias sin cargar"
        constraints = [
            models.UniqueConstraint(
                fields=["target_norm", "norm_type", "number", "year", "issuer"],
                name="norms_pending_amendment_unique_in_target",
            ),
        ]


class CorpusVersion(models.Model):
    """Versión de la normativa (REQ-012, P8). `id` es el número de versión, creciente.

    Se crea solo con `evaluon.audit.services.record(..., creates_corpus_version=True)`,
    que reserva el número, inserta el hecho que la origina ya con ese número y después
    la versión: un hecho registrado nunca se modifica.
    """

    created_at = models.DateTimeField("creada", default=timezone.now)
    event = models.OneToOneField(
        "audit.AuditEvent",
        verbose_name="hecho que la originó",
        on_delete=models.PROTECT,
        related_name="created_corpus_version",
    )

    class Meta:
        db_table = "norms_corpus_version"
        verbose_name = "versión de la normativa"
        verbose_name_plural = "versiones de la normativa"

    def __str__(self):
        return f"versión {self.pk}"
