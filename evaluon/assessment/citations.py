"""Ubicar la cita del modelo en el texto canónico del documento y sacar su página (REQ-053;
plan 004, "Cita"; ADR-0038; T-150).

El modelo copia un fragmento de un documento; el sistema lo busca en el texto canónico de la
lectura con `evaluon.tenders.proposal.quotes.locate` (igual con cualquier cantidad de espacios,
como en la 003). Si lo ubica, la cita guarda las posiciones y **el recorte del texto
canónico**, no lo que escribió el modelo; la página sale de las líneas de ese recorte
(`pages_at`) y la que diga el modelo no se usa. Si no lo ubica, se descarta y queda la
anomalía.

El texto canónico se arma de nuevo desde la lectura guardada una vez por lectura (como la
pantalla de la matriz); si no coincide con el guardado, la página sale de los pasajes, que
nunca cruzan una página.
"""

import re
from dataclasses import dataclass

from django.conf import settings

from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers.models import Passage
from evaluon.offers.reading import rebuild_reading
from evaluon.tenders.proposal import quotes

ANOMALY_NOT_FOUND = "cita_no_ubicada"
ANOMALY_UNKNOWN_ALIAS = "alias_inexistente"
ANOMALY_TOO_LONG = "cita_larga"
ANOMALY_REPEATED = "cita_repetida"
ANOMALY_ELLIPSIS = "cita_con_puntos_suspensivos"
ANOMALY_OTHER_DOCUMENT = "cita_en_otro_documento"


@dataclass(frozen=True)
class Located:
    """Una cita de la oferta ya ubicada: documento, lectura, página y posiciones en el
    texto canónico; `text` es el recorte de ese texto."""

    document: object
    reading: object
    page: int
    char_start: int
    char_end: int
    text: str

    @property
    def span(self):
        return (self.document.pk, self.char_start, self.char_end)


# Ruido típico del reconocimiento de un escaneo: el grado `°` sale como `*` y aparecen barras,
# guiones bajos y marcas sueltas. No cuentan al comparar; las letras, los números y la demás
# puntuación sí (T-156).
SCAN_NOISE = frozenset("*°º˚|¦_~^`´¨·•")
MIN_FOLDED_CHARS = 12


# Marca que el lector de PDF deja donde no pudo traducir un carácter, p. ej. `(cid:13)` (T-157).
READER_MARK = re.compile(r"\(cid:\d+\)")


def _fold(text):
    """El texto sin espacios, sin ruido de escaneo y sin marcas del lector y, para cada
    carácter que queda, su posición en el original."""
    skipped = set()
    for mark in READER_MARK.finditer(text):
        skipped.update(range(mark.start(), mark.end()))
    chars, positions = [], []
    for index, char in enumerate(text):
        if index not in skipped and not char.isspace() and char not in SCAN_NOISE:
            chars.append(char)
            positions.append(index)
    return "".join(chars), positions


def locate_text(text, quote):
    """Posiciones de `quote` en `text`: primero literal (espacios colapsados, como la 003) y, si
    no está, sin el ruido de escaneo. Lo que se guarda sigue siendo el recorte de `text`."""
    span = quotes.locate(text, quote)
    if span is not None:
        return span
    needle, _ = _fold(quote or "")
    if len(needle) < MIN_FOLDED_CHARS:
        return None
    haystack, positions = _fold(text)
    start = haystack.find(needle)
    if start == -1:
        return None
    return positions[start], positions[start + len(needle) - 1] + 1


class PageFinder:
    """Página de un tramo del texto canónico de una lectura."""

    def __init__(self):
        self._canonical = {}
        self._passages = {}

    def _canonical_of(self, reading):
        if reading.pk not in self._canonical:
            try:
                canonical = build_canonical_text(rebuild_reading(reading.pages))
            except Exception:  # noqa: BLE001 - sin líneas, se cae a los pasajes
                canonical = None
            if canonical is not None and canonical.text != reading.canonical_text:
                canonical = None
            self._canonical[reading.pk] = canonical
        return self._canonical[reading.pk]

    def _passages_of(self, reading):
        if reading.pk not in self._passages:
            self._passages[reading.pk] = list(
                Passage.objects.filter(reading=reading).order_by("order")
                .values_list("page", "char_start", "char_end"))
        return self._passages[reading.pk]

    def page_of(self, reading, start, end):
        """La primera página del tramo `canonical_text[start:end]`, o `None` si no se puede
        decir (una lectura sin líneas ni pasajes que lo cubran)."""
        canonical = self._canonical_of(reading)
        if canonical is not None:
            first, _ = canonical.pages_at(start, end)
            if first is not None:
                return first
        pages = [page for page, p_start, p_end in self._passages_of(reading)
                 if p_start < end and p_end > start]
        return min(pages) if pages else None


MIN_PIECE_CHARS = 20
ELLIPSIS = re.compile(r"\.{3,}|…")


def _locate_in(reading, quote):
    return locate_text(reading.canonical_text, quote) if reading is not None else None


def _make(document, reading, span, finder, anomalies, used):
    """La `Located` de `span`, o `None` (con la anomalía) si repite una ya ubicada o no se puede
    decir su página."""
    if (document.pk, *span) in used:
        anomalies.append({"type": ANOMALY_REPEATED, "document": document.pk})
        return None
    start, end = span
    page = finder.page_of(reading, start, end)
    if page is None:
        anomalies.append({"type": ANOMALY_NOT_FOUND, "document": document.pk,
                          "reason": "sin página"})
        return None
    return Located(document=document, reading=reading, page=page, char_start=start,
                   char_end=end, text=reading.canonical_text[start:end])


def locate_quote(document, quote, finder, used=(), anomalies=None, others=()):
    """Ubica `quote` (texto del modelo) en el documento `document` (`DocumentText`). Devuelve
    una `Located`, o `None` con la anomalía anotada en `anomalies` (una lista) si no está,
    es más larga que `ASSESSMENT_CITATION_MAX_CHARS` o repite una ya ubicada (`used`, de
    `Located.span`).

    Dos tolerancias (T-157) que no aceptan nada que no sea literal: si el texto no está en el
    documento que el modelo nombró pero está en exactamente uno de `others` (los demás
    documentos que recibió), se ubica ahí; y si la cita une trozos con puntos suspensivos, se
    guarda el trozo literal más largo."""
    anomalies = anomalies if anomalies is not None else []
    if len(quote or "") > settings.ASSESSMENT_CITATION_MAX_CHARS:
        anomalies.append({"type": ANOMALY_TOO_LONG, "document": document.document.pk,
                          "chars": len(quote)})
        return None
    span = _locate_in(document.reading, quote)
    if span is not None:
        return _make(document.document, document.reading, span, finder, anomalies, used)
    pieces = sorted((p.strip() for p in ELLIPSIS.split(quote or "")), key=len, reverse=True)
    pieces = [p for p in pieces if p]
    candidates = [p for p in pieces if len(p) >= MIN_PIECE_CHARS] if len(pieces) > 1 else [quote]
    for candidate in candidates:
        hits = [(entry, _locate_in(entry.reading, candidate)) for entry in (document, *others)]
        hits = [(entry, where) for entry, where in hits if where is not None]
        own = [hit for hit in hits if hit[0] is document]
        hits = own or hits
        if len(hits) != 1:
            continue
        entry, where = hits[0]
        if candidate is not quote:
            anomalies.append({"type": ANOMALY_ELLIPSIS, "document": entry.document.pk})
        if entry is not document:
            anomalies.append({"type": ANOMALY_OTHER_DOCUMENT,
                              "declared": document.document.pk,
                              "document": entry.document.pk})
        return _make(entry.document, entry.reading, where, finder, anomalies, used)
    anomalies.append({"type": ANOMALY_NOT_FOUND, "document": document.document.pk,
                      "quote": (quote or "")[:120]})
    return None
