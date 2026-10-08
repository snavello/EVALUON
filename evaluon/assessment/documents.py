"""Documentos de una oferta como texto por página, grupos y ventanas (REQ-054; plan 004, "Qué
se lee y cómo se agrupa"; ADR-0037; T-150).

Cada documento de la oferta es su última lectura, armada como texto por página con los pasajes
de la lectura (`sizing.render_page`: una página ilegible figura "no se pudo leer"; una página que la lectura con
visión transcribió cuenta como leída, `offers/vision.py`). Los
documentos de texto canónico idéntico se cuentan una vez: el resto figura como copia de otro
documento y la cita se hace sobre el que quedó. Los tokens se cuentan una vez por documento y
por página (`generation.count_tokens`), no por requisito.

El empaquetado reutiliza `sizing.pack` y `sizing.windows`:

- si toda la oferta entra en `ASSESSMENT_GROUP_TOKENS`, es un solo grupo y el orden no importa;
- si no entra, los documentos se ordenan por relevancia para el requisito (el mayor puntaje del
  reranker entre los pasajes recuperados de cada documento, `offers.retrieval.retrieve`, con
  la reescritura del requisito; los documentos sin pasaje recuperado van al final, por orden de
  carga). **La relevancia ordena, no descarta**: se pregunta por todos los grupos, hasta
  `ASSESSMENT_MAX_GROUPS`; los grupos que pasan del tope no se leen y quedan contados;
- un documento mayor que el presupuesto se parte por páginas en ventanas con una página de
  solape.

Solo entran los documentos vigentes (`offers.services.document_history`). No guarda nada en
la base.
"""

from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import generation
from evaluon.assessment import sizing
from evaluon.offers import retrieval, vision
from evaluon.offers.models import DocumentKind, Passage
from evaluon.offers.services import document_history


@dataclass
class DocumentText:
    """Un documento de la oferta con su última lectura armada como texto por página."""

    document: object
    reading: object | None = None
    sha256: str = ""
    pages: list = field(default_factory=list)
    page_tokens: list = field(default_factory=list)
    header: str = ""
    header_tokens: int = 0
    # Documento que tiene el mismo texto canónico y quedó en su lugar.
    copy_of: int | None = None
    # Páginas cuyo texto es la transcripción de la lectura con visión (ADR-0041): cuentan como
    # leídas, y las citas sobre ellas se rotulan "leída por visión".
    vision_pages: list = field(default_factory=list)

    @property
    def tokens(self):
        return self.header_tokens + sum(self.page_tokens)

    @property
    def unread_pages(self):
        return [page["page"] for page in self.pages if not page["readable"]]

    def render(self, first=None, last=None):
        """El documento como lo lee el modelo: encabezado y páginas `first` a `last`
        (de la 1 a la última, por omisión)."""
        selected = [p for p in self.pages
                    if (first is None or p["page"] >= first)
                    and (last is None or p["page"] <= last)]
        head = [self.header]
        if first is not None:
            head.append(f"Páginas {first} a {last} (el documento es más largo)")
        return "\n".join([*head, *[sizing.render_page(p) for p in selected]])


@dataclass
class Piece:
    """Lo que se empaqueta: un documento entero o una ventana de sus páginas."""

    doc: DocumentText
    tokens: int
    first_page: int | None = None
    last_page: int | None = None

    @property
    def windowed(self):
        return self.first_page is not None

    def render(self):
        return self.doc.render(self.first_page, self.last_page)

    def record(self):
        entry = {"document": self.doc.document.pk, "tokens": self.tokens}
        if self.windowed:
            entry["pages"] = [self.first_page, self.last_page]
        return entry


@dataclass
class OfferText:
    """Los documentos de una oferta listos para leer."""

    offer: object
    documents: list
    pieces: list
    budget: int
    # Páginas ilegibles de los documentos que quedaron (no de las copias) y documentos sin
    # lectura: lo que el modelo no pudo ver.
    unread: list
    without_reading: list

    @property
    def tokens(self):
        return sum(piece.tokens for piece in self.pieces)

    @property
    def has_unread(self):
        return bool(self.unread or self.without_reading)

    @property
    def fits(self):
        """Toda la oferta entra en un grupo."""
        return self.tokens <= self.budget

    def record(self, groups=None):
        """Los documentos usados, para el registro de la evaluación (P6): lectura, huella del
        texto canónico, páginas, tokens, copias omitidas y ventanas."""
        windowed = {}
        for piece in self.pieces:
            if piece.windowed:
                windowed.setdefault(piece.doc.document.pk, []).append(
                    [piece.first_page, piece.last_page])
        return [{
            "document": d.document.pk, "title": d.document.title,
            "file": d.document.file_name,
            "reading": d.reading.pk if d.reading else None, "sha256": d.sha256,
            "pages": len(d.pages), "unread_pages": d.unread_pages, "tokens": d.tokens,
            "page_tokens": d.page_tokens, "copy_of": d.copy_of,
            "windows": windowed.get(d.document.pk, []), "vision_pages": d.vision_pages,
        } for d in self.documents]


def read_document(document, count):
    """El documento con su última lectura y los tokens de su encabezado y de cada página."""
    entry = DocumentText(document=document, header=sizing.render_header(document))
    reading = document.readings.order_by("-sequence").first()
    if reading is None:
        return entry
    entry.reading = reading
    entry.sha256 = reading.canonical_sha256
    entry.pages = sizing.document_pages(reading)
    entry.vision_pages = sorted(vision.vision_pages(reading))
    entry.page_tokens = [count(sizing.render_page(p)) for p in entry.pages]
    entry.header_tokens = count(entry.header)
    return entry


def build_offer_text(offer, count=None, budget=None):
    """Los documentos de `offer` como texto por página, con las copias omitidas y las piezas
    (documentos enteros o ventanas) en el orden de carga."""
    count = count or generation.count_tokens
    budget = budget or settings.ASSESSMENT_GROUP_TOKENS
    documents, first_seen = [], {}
    # El informe técnico del área no es un documento de la oferta: no se lee para evaluarla
    # (T-190; REQ-074). Lo lee `services/technical_report.py` para proponer el ok técnico.
    # Los documentos retirados o reemplazados no se leen (REQ-099, ADR-0048).
    for document in document_history.current_documents(offer).exclude(
            kind=DocumentKind.INFORME_TECNICO).order_by("loaded_at", "id"):
        entry = read_document(document, count)
        if entry.sha256 in first_seen:
            entry.copy_of = first_seen[entry.sha256]
        elif entry.sha256:
            first_seen[entry.sha256] = document.pk
        documents.append(entry)

    pieces, unread, without_reading = [], [], []
    for entry in documents:
        if entry.reading is None:
            without_reading.append(entry.document.pk)
            continue
        if entry.copy_of is not None:
            continue
        unread.extend({"document": entry.document.pk, "title": entry.document.title,
                       "page": page} for page in entry.unread_pages)
        if entry.tokens <= budget:
            pieces.append(Piece(entry, entry.tokens))
            continue
        for part in sizing.windows(entry.page_tokens, budget):
            pieces.append(Piece(
                entry, entry.header_tokens + sum(entry.page_tokens[i] for i in part),
                first_page=part[0] + 1, last_page=part[-1] + 1))
    return OfferText(offer=offer, documents=documents, pieces=pieces, budget=budget,
                     unread=unread, without_reading=without_reading)


def relevance(offer_text, query, rewrite=""):
    """`{id del documento: mayor puntaje del reranker}` entre los pasajes recuperados de cada
    documento para `query` (y su reescritura). Los documentos sin pasaje recuperado no
    figuran. Usa `offers.retrieval.retrieve`."""
    found = retrieval.retrieve(offer_text.offer, query, rewrite=rewrite)
    ids = [c.passage_id for c in found.pool]
    document_of = dict(Passage.objects.filter(pk__in=ids)
                       .values_list("pk", "reading__document_id"))
    best = {}
    for candidate in found.pool:
        if candidate.score is None:
            continue
        document_id = document_of[candidate.passage_id]
        best[document_id] = max(best.get(document_id, candidate.score), candidate.score)
    return best, found


@dataclass
class GroupPlan:
    """Cómo se lee la oferta para un requisito: los grupos que se preguntan, las piezas de los
    grupos que pasaron del tope (no se leen) y si todo entró en un grupo."""

    groups: list
    skipped: list = field(default_factory=list)

    @property
    def unread_groups(self):
        return len(self.skipped)


def plan_groups(offer_text, scores=None, budget=None, max_groups=None):
    """Los grupos de `offer_text`. Con la oferta entera en un grupo no hace falta ordenar; si
    no, las piezas se ordenan por `scores` (`{documento: puntaje}`, de mayor a menor; sin
    puntaje, al final y por orden de carga) y se empaquetan hasta el presupuesto. Los grupos
    más allá de `max_groups` quedan en `skipped`."""
    budget = budget or offer_text.budget
    max_groups = max_groups or settings.ASSESSMENT_MAX_GROUPS
    pieces = list(offer_text.pieces)
    if not pieces:
        return GroupPlan(groups=[])
    if offer_text.tokens > budget:
        scores = scores or {}
        position = {id(piece): index for index, piece in enumerate(pieces)}
        pieces.sort(key=lambda p: (p.doc.document.pk not in scores,
                                   -scores.get(p.doc.document.pk, 0.0), position[id(p)]))
    packed = sizing.pack([{"piece": p, "tokens": p.tokens} for p in pieces], budget)
    groups = [[item["piece"] for item in group] for group in packed]
    return GroupPlan(groups=groups[:max_groups],
                     skipped=[p for group in groups[max_groups:] for p in group])
