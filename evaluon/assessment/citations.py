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


def _fold(text):
    """El texto sin espacios ni ruido de escaneo y, para cada carácter que queda, su posición
    en el original."""
    chars, positions = [], []
    for index, char in enumerate(text):
        if not char.isspace() and char not in SCAN_NOISE:
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


def locate_quote(document, quote, finder, used=(), anomalies=None):
    """Ubica `quote` (texto del modelo) en el documento `document` (`DocumentText`). Devuelve
    una `Located`, o `None` con la anomalía anotada en `anomalies` (una lista) si no está,
    es más larga que `ASSESSMENT_CITATION_MAX_CHARS` o repite una ya ubicada (`used`, de
    `Located.span`)."""
    anomalies = anomalies if anomalies is not None else []
    reading = document.reading
    if len(quote or "") > settings.ASSESSMENT_CITATION_MAX_CHARS:
        anomalies.append({"type": ANOMALY_TOO_LONG, "document": document.document.pk,
                          "chars": len(quote)})
        return None
    span = locate_text(reading.canonical_text, quote) if reading is not None else None
    if span is None:
        anomalies.append({"type": ANOMALY_NOT_FOUND, "document": document.document.pk,
                          "quote": (quote or "")[:120]})
        return None
    if (document.document.pk, *span) in used:
        anomalies.append({"type": ANOMALY_REPEATED, "document": document.document.pk})
        return None
    start, end = span
    page = finder.page_of(reading, start, end)
    if page is None:
        anomalies.append({"type": ANOMALY_NOT_FOUND, "document": document.document.pk,
                          "quote": (quote or "")[:120], "reason": "sin página"})
        return None
    return Located(document=document.document, reading=reading, page=page, char_start=start,
                   char_end=end, text=reading.canonical_text[start:end])
