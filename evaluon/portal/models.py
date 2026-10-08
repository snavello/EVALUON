"""Tablas de la importación desde el Portal de Compras (plan 012, "Modelo de datos";
ADR-0030).

Un enlace (`PortalLink`) es un proceso seguido. Cada exploración guarda las páginas y los
archivos bajados tal cual (`PortalPage`, `PortalFile`, solo inserción) y arma una propuesta
(`PortalProposal`) de ítems (`PortalItem`). Un ítem aprobado se carga llamando a los
servicios de la 003 y la 008; lo que esos servicios no tienen donde guardar va a
`PortalProcedureData`, `PortalLine`, `PortalOfferData` y `PortalQuote`, cada una con el
ítem que la originó (su origen, REQ-049).

Las páginas, los archivos y el contenido de un ítem no se modifican: triggers de la
migración `0002_triggers` rechazan los cambios. Los datos personales de los oferentes solo
existen en la base (P4). Valores de dominio en español sin tildes, como en la 003.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from evaluon.norms.models import SHA256_REGEX
from evaluon.tenders.models import Procedure


def _user_fk(verbose_name, related_name, null=False):
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        related_name=related_name,
        null=null,
        blank=null,
    )


def _valid(field, choices, name):
    return models.CheckConstraint(
        condition=Q(**{f"{field}__in": choices.values}), name=name
    )


def _sha256(field, name):
    return models.CheckConstraint(
        condition=Q(**{f"{field}__regex": SHA256_REGEX}), name=name
    )


def _exactly_one_origin(name):
    """El dato viene del ítem del Portal o del documento subido, y de uno solo."""
    return models.CheckConstraint(
        condition=(Q(item__isnull=False) & Q(document__isnull=True))
        | (Q(item__isnull=True) & Q(document__isnull=False)),
        name=name,
    )


class PageKind(models.TextChoices):
    PROCESO = "proceso", "Página del proceso"
    ACTA = "acta", "Acta de apertura"
    DICTAMEN = "dictamen", "Dictamen"
    CUADRO = "cuadro", "Cuadro comparativo"


class Origin(models.TextChoices):
    IMPORTACION = "importacion", "Importación"
    REVISION = "revision", "Revisión periódica"


class ItemKind(models.TextChoices):
    PROCEDIMIENTO = "procedimiento", "Procedimiento"
    RENGLONES = "renglones", "Renglones"
    DOCUMENTO = "documento", "Documento"
    OFERTA = "oferta", "Oferta"


class ItemState(models.TextChoices):
    PROPUESTO = "propuesto", "Propuesto"
    APROBADO = "aprobado", "Aprobado"
    RECHAZADO = "rechazado", "Rechazado"
    CARGADO = "cargado", "Cargado"
    FALLIDO = "fallido", "Fallido"


class LoadedModel(models.TextChoices):
    PROCEDURE = "tenders_procedure", "Procedimiento"
    DOCUMENT = "tenders_document", "Documento del pliego"
    OFFER = "offers_offer", "Oferta"


class PortalLink(models.Model):
    """Un proceso seguido (REQ-045). `url` es el enlace público con su `qs`."""

    url = models.CharField("enlace", max_length=2000, unique=True)
    process_number = models.CharField("número del proceso", max_length=100, blank=True)
    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        null=True, blank=True, related_name="portal_links",
    )
    following = models.BooleanField("se sigue revisando", default=True)
    last_review_on = models.DateField("última revisión", null=True, blank=True)
    created_at = models.DateTimeField("alta", default=timezone.now)
    created_by = _user_fk("alta por", "portal_links_created")

    class Meta:
        db_table = "portal_link"
        verbose_name = "enlace del Portal"
        verbose_name_plural = "enlaces del Portal"

    def __str__(self):
        return self.process_number or self.url


class PortalPage(models.Model):
    """Una página o respuesta bajada, tal cual. Solo se insertan filas."""

    link = models.ForeignKey(
        PortalLink, verbose_name="enlace", on_delete=models.PROTECT, related_name="pages"
    )
    exploration = models.PositiveIntegerField("exploración")
    kind = models.CharField("tipo", max_length=10, choices=PageKind.choices)
    url = models.CharField("dirección", max_length=2000)
    fetched_at = models.DateTimeField("consultada", default=timezone.now)
    sha256 = models.CharField("huella", max_length=64)
    content = models.BinaryField("contenido")

    class Meta:
        db_table = "portal_page"
        verbose_name = "página del Portal"
        verbose_name_plural = "páginas del Portal"
        indexes = [models.Index(fields=["link", "exploration"], name="portal_page_link_expl")]
        constraints = [
            _valid("kind", PageKind, "portal_page_kind_valid"),
            _sha256("sha256", "portal_page_sha256_valid"),
        ]


class PortalFile(models.Model):
    """Un documento bajado del Portal. Solo se insertan filas."""

    link = models.ForeignKey(
        PortalLink, verbose_name="enlace", on_delete=models.PROTECT, related_name="files"
    )
    exploration = models.PositiveIntegerField("exploración")
    url = models.CharField("dirección", max_length=2000)
    file_name = models.CharField("nombre del archivo", max_length=300)
    file_format = models.CharField("formato", max_length=20, blank=True)
    sha256 = models.CharField("huella", max_length=64)
    content = models.BinaryField("contenido")
    fetched_at = models.DateTimeField("consultado", default=timezone.now)
    page = models.ForeignKey(
        PortalPage, verbose_name="página de origen", on_delete=models.PROTECT,
        related_name="files",
    )

    class Meta:
        db_table = "portal_file"
        verbose_name = "archivo del Portal"
        verbose_name_plural = "archivos del Portal"
        indexes = [models.Index(fields=["link", "exploration"], name="portal_file_link_expl")]
        constraints = [_sha256("sha256", "portal_file_sha256_valid")]


class PortalProposal(models.Model):
    """Una propuesta: lo que una exploración encontró para cargar."""

    link = models.ForeignKey(
        PortalLink, verbose_name="enlace", on_delete=models.PROTECT,
        related_name="proposals",
    )
    exploration = models.PositiveIntegerField("exploración")
    origin = models.CharField("origen", max_length=12, choices=Origin.choices)
    created_at = models.DateTimeField("creada", default=timezone.now)
    job = models.ForeignKey(
        "tenders.Job", verbose_name="pedido", on_delete=models.PROTECT,
        null=True, blank=True, related_name="portal_proposals",
    )
    anomalies = models.JSONField("anomalías", default=list)

    class Meta:
        db_table = "portal_proposal"
        verbose_name = "propuesta del Portal"
        verbose_name_plural = "propuestas del Portal"
        constraints = [
            _valid("origin", Origin, "portal_proposal_origin_valid"),
            models.UniqueConstraint(
                fields=["link", "exploration", "origin"], name="portal_proposal_unique"
            ),
        ]


class PortalItem(models.Model):
    """Una cosa propuesta. El contenido no se modifica; cambian el estado y la decisión
    (trigger de la migración `0002_triggers`)."""

    proposal = models.ForeignKey(
        PortalProposal, verbose_name="propuesta", on_delete=models.PROTECT,
        related_name="items",
    )
    kind = models.CharField("tipo", max_length=15, choices=ItemKind.choices)
    key = models.CharField("clave", max_length=300)
    payload = models.JSONField("datos propuestos")
    content_sha256 = models.CharField("huella del contenido", max_length=64)
    damaged_fields = models.JSONField("campos con texto dañado", default=list)
    page = models.ForeignKey(
        PortalPage, verbose_name="página de origen", on_delete=models.PROTECT,
        related_name="items",
    )
    file = models.ForeignKey(
        PortalFile, verbose_name="archivo", on_delete=models.PROTECT,
        null=True, blank=True, related_name="items",
    )
    state = models.CharField(
        "estado", max_length=10, choices=ItemState.choices, default=ItemState.PROPUESTO
    )
    decided_by = _user_fk("decidido por", "portal_items_decided", null=True)
    decided_at = models.DateTimeField("decidido", null=True, blank=True)
    loaded_model = models.CharField(
        "objeto creado o asociado", max_length=20, blank=True
    )
    loaded_id = models.PositiveBigIntegerField("id del objeto", null=True, blank=True)
    failure = models.TextField("motivo de la falla", blank=True)

    class Meta:
        db_table = "portal_item"
        verbose_name = "ítem de la propuesta"
        verbose_name_plural = "ítems de la propuesta"
        indexes = [models.Index(fields=["key", "kind"], name="portal_item_key_kind")]
        constraints = [
            _valid("kind", ItemKind, "portal_item_kind_valid"),
            _valid("state", ItemState, "portal_item_state_valid"),
            _sha256("content_sha256", "portal_item_sha256_valid"),
            models.UniqueConstraint(fields=["proposal", "key"], name="portal_item_key_unique"),
            # Un ítem decidido dice quién y cuándo.
            models.CheckConstraint(
                condition=Q(state=ItemState.PROPUESTO)
                | (Q(decided_by__isnull=False) & Q(decided_at__isnull=False)),
                name="portal_item_decision_has_author",
            ),
            # Un ítem cargado dice qué creó.
            models.CheckConstraint(
                condition=~Q(state=ItemState.CARGADO)
                | (~Q(loaded_model="") & Q(loaded_id__isnull=False)),
                name="portal_item_loaded_has_object",
            ),
            models.CheckConstraint(
                condition=Q(loaded_model="") | Q(loaded_model__in=LoadedModel.values),
                name="portal_item_loaded_model_valid",
            ),
        ]


class PortalProcedureData(models.Model):
    """Datos del procedimiento que `tenders_procedure` no tiene donde guardar."""

    procedure = models.OneToOneField(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="portal_data",
    )
    file_number = models.CharField("expediente", max_length=100, blank=True)
    legal_framework = models.CharField("encuadre legal", max_length=500, blank=True)
    schedule = models.JSONField("cronograma", default=list)
    guarantees = models.JSONField("garantías", default=list)
    # Origen: el ítem del Portal o el documento del pliego subido, exactamente uno
    # (feature 014, ADR-0049; restricción `portal_procedure_data_exactly_one_origin`).
    item = models.ForeignKey(
        PortalItem, verbose_name="ítem de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="procedure_data",
    )
    document = models.ForeignKey(
        "tenders.Document", verbose_name="documento de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="portal_procedure_data",
    )

    class Meta:
        db_table = "portal_procedure_data"
        verbose_name = "datos del procedimiento del Portal"
        verbose_name_plural = "datos del procedimiento del Portal"
        constraints = [_exactly_one_origin("portal_procedure_data_exactly_one_origin")]


class PortalLine(models.Model):
    """Un renglón del procedimiento, con su cantidad."""

    procedure = models.ForeignKey(
        Procedure, verbose_name="procedimiento", on_delete=models.PROTECT,
        related_name="portal_lines",
    )
    number = models.PositiveIntegerField("número")
    description = models.TextField("descripción")
    quantity = models.DecimalField(
        "cantidad", max_digits=18, decimal_places=4, null=True, blank=True
    )
    unit = models.CharField("unidad", max_length=100, blank=True)
    # Origen: el ítem del Portal o el documento del pliego subido, exactamente uno.
    item = models.ForeignKey(
        PortalItem, verbose_name="ítem de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="lines",
    )
    document = models.ForeignKey(
        "tenders.Document", verbose_name="documento de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="portal_lines",
    )

    class Meta:
        db_table = "portal_line"
        verbose_name = "renglón del Portal"
        verbose_name_plural = "renglones del Portal"
        ordering = ["procedure_id", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["procedure", "number"], name="portal_line_number_unique"
            ),
            _exactly_one_origin("portal_line_exactly_one_origin"),
        ]


class PortalOfferData(models.Model):
    """Datos de una oferta que `offers_offer` no tiene donde guardar (acta de apertura)."""

    offer = models.OneToOneField(
        "offers.Offer", verbose_name="oferta", on_delete=models.PROTECT,
        related_name="portal_data",
    )
    cuit = models.CharField("CUIT", max_length=13)
    confirmed_on = models.DateField("confirmada el", null=True, blank=True)
    currency = models.CharField("moneda", max_length=10, blank=True)
    total = models.DecimalField(
        "total", max_digits=20, decimal_places=2, null=True, blank=True
    )
    # Origen: el ítem del acta o el documento de la oferta del que salió el CUIT, exactamente
    # uno (feature 014, REQ-083).
    item = models.ForeignKey(
        PortalItem, verbose_name="ítem de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="offer_data",
    )
    document = models.ForeignKey(
        "offers.Document", verbose_name="documento de origen", on_delete=models.PROTECT,
        null=True, blank=True, related_name="portal_offer_data",
    )

    class Meta:
        db_table = "portal_offer_data"
        verbose_name = "datos de la oferta del Portal"
        verbose_name_plural = "datos de la oferta del Portal"
        constraints = [_exactly_one_origin("portal_offer_data_exactly_one_origin")]


class PortalGuarantee(models.Model):
    """Una garantía de una oferta (acta de apertura). Una oferta puede tener varias."""

    offer_data = models.ForeignKey(
        PortalOfferData, verbose_name="datos de la oferta", on_delete=models.CASCADE,
        related_name="guarantees",
    )
    guarantee_type = models.CharField("tipo de garantía", max_length=100, blank=True)
    guarantee_form = models.CharField("forma de garantía", max_length=100, blank=True)
    amount = models.DecimalField(
        "monto de la garantía", max_digits=20, decimal_places=2, null=True, blank=True
    )
    item = models.ForeignKey(
        PortalItem, verbose_name="ítem de origen", on_delete=models.PROTECT,
        related_name="guarantees",
    )

    class Meta:
        db_table = "portal_guarantee"
        verbose_name = "garantía de la oferta del Portal"
        verbose_name_plural = "garantías de la oferta del Portal"
        ordering = ["offer_data_id", "id"]


class PortalQuote(models.Model):
    """Precio y cantidad que cotizó una oferta para un renglón (cuadro comparativo)."""

    offer = models.ForeignKey(
        "offers.Offer", verbose_name="oferta", on_delete=models.PROTECT,
        related_name="portal_quotes",
    )
    line = models.ForeignKey(
        PortalLine, verbose_name="renglón", on_delete=models.PROTECT, related_name="quotes"
    )
    price = models.DecimalField(
        "precio", max_digits=20, decimal_places=4, null=True, blank=True
    )
    quantity = models.DecimalField(
        "cantidad", max_digits=18, decimal_places=4, null=True, blank=True
    )

    class Meta:
        db_table = "portal_quote"
        verbose_name = "cotización del Portal"
        verbose_name_plural = "cotizaciones del Portal"
        constraints = [
            models.UniqueConstraint(fields=["offer", "line"], name="portal_quote_unique"),
        ]
