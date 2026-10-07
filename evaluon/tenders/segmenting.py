"""Partición de un pliego en tramos (ADR-0019, decisión 1; plan 003, "Tramos" y "Qué es
un requisito y su clase"; T-070).

Las reglas son propias del pliego (no las de normas de la 001) y trabajan sobre el mismo
texto canónico (`build_canonical_text`, sin cambios). Un encabezado solo se reconoce al
comienzo de una línea de la lectura: el texto canónico une en un párrafo las líneas de
una cláusula y de su título ("1. OBJETO 1.1. El objeto…"), así que las reglas miran el
lugar de cada línea leída dentro del texto canónico (`CanonicalText.lines`).

| Elemento | Forma | Qué produce |
|---|---|---|
| Índice | "ÍNDICE" y las líneas con puntos guía | Se descarta, como el índice de la 001, y se cuenta aparte |
| Sección | Línea en mayúsculas `SECCIÓN I - …` | Contenedor `sec-i`; su encabezado es un tramo `titulo`. Si el título nombra una clase, la pasa a todos sus tramos |
| Cláusula | `7.`, `7.5.`, `7.5.2.`, `10.2.1.Una vez` | Tramo `clausula` `sec-i/7.5.2`, si continúa la numeración de su sección |
| Título de cláusula | La cláusula es solo su título en mayúsculas y le sigue algo que cuelga de ella | Tramo `titulo` |
| Renglón | Cláusula que empieza "RENGLÓN N° k" o "RENGLONES NROS. j A k" | Renglones del tramo y de lo que cuelga de él; lista de renglones de la lectura, donde un encabezado de un solo renglón gana sobre un rango |
| Viñeta o inciso | `•`, `−`, `–`, `-` o `a)` al comienzo de una línea, dentro de una cláusula | Tramo `vineta` `sec-ii/1.2/v-1` o `…/inc-b` |
| Anexo | Párrafo en mayúsculas `ANEXO I - …` | Contenedor `sec-iv/anexo-i` (tramo `titulo`); cada párrafo, un tramo `parrafo` `…/p-3` |
| Tabla | Líneas dentro de una zona de tabla (`tables.py`) | Un tramo `tabla` por zona, `sec-i/6/tabla-1`, pendiente de revisión |
| Después de una tabla | Lo que sigue a la tabla, hasta el próximo encabezado | Tramo `parrafo` de lo que contiene a la tabla, `sec-i/6/p-1` |
| Carátula | Antes de la primera sección (o cláusula, si no hay secciones) | Un tramo `parrafo` por párrafo, `pre/p-1` |
| Página sin texto legible | Página ilegible o no leída | Tramo `pagina` `pagina-7`, sin texto, pendiente de revisión |
| Ninguna regla | Lo que queda entre el título de una sección y su primera cláusula | Tramo `no_ubicado`, `sec-ii/no-ubicado-1`, pendiente de revisión |
| Numeración inesperada | Un encabezado que la secuencia rechaza | Tramo `no_ubicado`, pendiente (detalle `numeracion_inesperada`), hasta el próximo encabezado aceptado |
| Tramo largo | Más de `SEGMENT_MAX_CHARS` caracteres | Se parte en límites de oración: `sec-iii/1.1`, `sec-iii/1.1#2` |

- **Secuencia.** Una cláusula se acepta si continúa la numeración de su sección: el
  hermano siguiente, el primer hijo o la vuelta a un nivel superior. La primera de una
  sección puede tener cualquier número de un nivel. Un número de un solo nivel necesita
  su punto ("7."); uno de varios niveles, no ("7.5.2 Texto"). Todo número rechazado va
  al informe (`rejected_headings`).
  - Si tiene forma de encabezado (con su punto al comienzo de un párrafo o después de
    un texto que cierra, o seguido de un título en mayúsculas o de un renglón), no se
    absorbe en silencio (decisión del Coordinador, verificación de T-070): abre un tramo
    `no_ubicado` pendiente hasta el próximo encabezado aceptado. Si nombra un renglón,
    abre su propio tramo y el renglón entra en la lista de la lectura con esa clave,
    aunque la numeración esté rota.
  - Si no la tiene, como "3.972 kcal" o "1.300 mg" en medio de una oración, no corta:
    queda dentro del tramo abierto.
- **Incisos.** Una línea que empieza con `a)` es un inciso solo si el texto anterior
  termina en punto, dos puntos o punto y coma, como en el texto canónico de la 001.
- **Claves.** Un pliego sin secciones usa las claves sin prefijo (`7.5.2`). Una clave
  repetida suma `~2`.
- **Texto.** Cada tramo va desde el comienzo de su primera línea hasta el final de la
  última, sin el espacio o el salto de línea que lo separa del siguiente: `text` es igual
  a `canonical_text[char_start:char_end]`.
- **Cobertura.** Cada carácter del texto canónico está en un solo tramo, en el índice
  descartado o es un separador (espacio o salto de línea) entre dos tramos; la suma da el
  total. Las líneas que la lectura descartó (encabezados, pies) no están en el texto
  canónico y se cuentan aparte (`discarded_lines`).
- **Pendientes** (`review_reason`, REQ-028): `tabla`, `no_ubicado`, `pagina_ilegible`
  (tramo `pagina`) y `pagina_dudosa` (un tramo con texto de una página dudosa).

Todo corre en CPU y sin conexión (P4). Cambiar estas reglas cambia `RULES_VERSION`, que
la lectura guarda en `tool_versions` (P6).
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from evaluon.norms.reading import (
    FORMAT_HTML,
    ORIGIN_OCR,
    ORIGIN_PDF_TEXT,
    ORIGIN_WEB,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_NOT_READ,
)
from evaluon.norms.splitting.canonical import (
    build_canonical_text,
    normalize_line,
    page_furniture,
)
from evaluon.norms.splitting.headings import ANNEX_HEADING, TITLE_HEADING, is_uppercase

# Versión de las reglas de tramos. La lectura la guarda en `tool_versions`.
RULES_VERSION = "tramos-2"

# Tipos de tramo (`tenders_segment.segment_type`).
TITULO = "titulo"
CLAUSULA = "clausula"
VINETA = "vineta"
PARRAFO = "parrafo"
TABLA = "tabla"
PAGINA = "pagina"
NO_UBICADO = "no_ubicado"
SEGMENT_TYPES = (TITULO, CLAUSULA, VINETA, PARRAFO, TABLA, PAGINA, NO_UBICADO)

# Motivos de revisión (`tenders_segment.review_reason`).
REVIEW_ILLEGIBLE_PAGE = "pagina_ilegible"
REVIEW_DOUBTFUL_PAGE = "pagina_dudosa"
REVIEW_TABLE = "tabla"
REVIEW_UNLOCATED = "no_ubicado"
# Detalle de un tramo `no_ubicado` que abre un encabezado rechazado por la secuencia. El
# motivo de revisión sigue siendo `no_ubicado`, el valor que admite la tabla; el detalle
# va en el informe.
DETAIL_UNEXPECTED_NUMBERING = "numeracion_inesperada"

# Motivo de lo que se descarta del texto canónico.
DISCARDED_INDEX = "indice"

# Profundidad máxima de la numeración de cláusulas ("11.6.1.", "17.3.2.").
CLAUSE_LEVELS = 4
# Decimales de la confianza del reconocimiento, como en la 001.
_CONFIDENCE_DECIMALS = 2

# Número de cláusula al comienzo de una línea: hasta cuatro niveles, con el punto final
# obligatorio en un número de un nivel ("7.") y optativo en uno de varios ("7.5.2"). Le
# sigue un espacio, el fin de la línea o una mayúscula ("10.2.1.Una vez").
_CLAUSE = re.compile(
    r"(?P<number>\d{1,3}(?:\.\d{1,3}){0,%d})(?P<dot>\.)?(?=\s|$|[A-ZÁÉÍÓÚÑ“\"(])"
    % (CLAUSE_LEVELS - 1)
)
# Viñeta: el signo y un espacio.
_BULLET = re.compile(r"[•−–\-](?=\s)")
# Inciso de letra: `a)` y un espacio.
_INCISO = re.compile(r"(?P<letter>[a-zñ])\)(?=\s)")
_INCISO_BEFORE = (".", ":", ";")
# Renglones al comienzo del texto de una cláusula.
_ITEM = re.compile(
    r"RENGL[OÓ]N\s+(?:N(?:[°º]|RO\.?|O\.?)\s*)?(?P<number>\d+)\b", re.IGNORECASE
)
_ITEM_RANGE = re.compile(
    r"RENGLONES\s+(?:N(?:ROS?\.?|[°º]S?|OS\.?)\s*)?(?P<first>\d+)\s+(?:A|AL)\s+(?P<last>\d+)\b",
    re.IGNORECASE,
)
# Índice: puntos guía (cinco o más) y, quizás, el número de página al final de la línea;
# o la palabra "ÍNDICE" sola.
_LEADER = re.compile(r"(?:\.\s?){5,}\s*\d{0,4}\s*$")
_INDEX_MARKER = re.compile(r"[IÍ]NDICE:?")
# Cuántas líneas sin puntos guía puede haber entre dos que los tienen (una entrada del
# índice partida en dos renglones).
_INDEX_WRAPPED_LINES = 2
# Clase que nombra el título de una sección (spec 003, "Qué es un requisito").
_SECTION_CLASSES = (
    (re.compile(r"especificaci(?:on|ones) tecnicas?"), "tecnico"),
    (re.compile(r"requisitos? economicos?"), "economico"),
    (re.compile(r"requisitos? formales?"), "formal"),
)
# Fin de oración, para partir un tramo largo: un punto, punto y coma o dos puntos
# después de una letra minúscula o de un cierre, y un espacio.
_SENTENCE_END = re.compile(r"(?<=[a-záéíóúüñ)\]”\"%])[.;:](?= )")

_UNREADABLE_PAGES = (PAGE_ILLEGIBLE, PAGE_NOT_READ)
_PATH_SEPARATOR = " › "


@dataclass
class TenderSegment:
    """Un tramo, con los campos de `tenders_segment` salvo la lectura."""

    order: int
    key: str
    label: str
    path: str
    segment_type: str
    section_class: str
    items: list
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
    text: str
    text_origin: str
    ocr_confidence_min: float | None = None
    ocr_confidence_avg: float | None = None
    review_reason: str = ""
    # Por qué quedó pendiente, más allá del motivo (`numeracion_inesperada`); va en el
    # informe, no en la tabla.
    review_detail: str = ""


@dataclass
class TenderSplit:
    """El resultado de partir un pliego: el texto canónico, los tramos en orden, los
    renglones (`tenders_reading.items`), lo descartado del texto canónico
    (`(inicio, fin, motivo)`), el control de cobertura y el informe
    (`tenders_reading.report`)."""

    canonical: object
    segments: list[TenderSegment]
    items: list[dict]
    discarded: list[tuple[int, int, str]]
    coverage: dict
    report: dict = field(default_factory=dict)


@dataclass
class _Opening:
    """Dónde empieza un tramo: la línea, y lo que se sabe del tramo al empezar."""

    line: int
    key: str
    segment_type: str
    label: str
    path: str
    section_class: str
    items: list
    levels: tuple = ()
    parent: str = ""
    zone: int | None = None
    detail: str = ""


@dataclass
class _Clause:
    levels: tuple
    key: str
    path: str
    items: list


@dataclass
class _Container:
    """Una sección, un anexo o la carátula: prefijo de clave, ruta y clase."""

    key: str
    path: str
    section_class: str


def split_tender(reading, tables=(), max_chars=None):
    """Parte la lectura de un documento del pliego (`DocumentReading`) en tramos.

    `tables` son las zonas de tabla de `tables.table_zones`. `max_chars` es el largo a
    partir del cual se parte un tramo; por omisión, `SEGMENT_MAX_CHARS`.
    """
    if max_chars is None:
        from django.conf import settings

        max_chars = settings.SEGMENT_MAX_CHARS
    canonical = build_canonical_text(reading)
    lines = _lines(reading, canonical, list(tables))
    index_lines = _index_lines(lines)
    walker = _Walker(lines, index_lines, has_sections=_has_sections(lines, index_lines))
    walker.walk()

    segments = _segments(reading, canonical, lines, walker.openings, index_lines, max_chars)
    segments += _unreadable_pages(reading, canonical)
    segments.sort(key=lambda s: (s.char_start, s.segment_type != PAGINA, s.char_end))
    _unique_keys(segments)
    for order, segment in enumerate(segments, start=1):
        segment.order = order

    discarded = _index_spans(lines, index_lines)
    coverage = check_coverage(canonical, segments, discarded)
    result = TenderSplit(
        canonical=canonical,
        segments=segments,
        items=walker.items,
        discarded=discarded,
        coverage=coverage,
    )
    result.report = _report(reading, result, walker.rejected)
    return result


# --- Líneas -----------------------------------------------------------------------------


@dataclass
class _Line:
    """Una línea leída, con su lugar en el texto canónico y su zona de tabla."""

    page: int | None
    start: int
    end: int
    text: str
    paragraph_start: bool
    zone: int | None


def _lines(reading, canonical, zones):
    """Las líneas del texto canónico con su posición en la página, recorridas en el
    mismo orden en que las arma `build_canonical_text`: sin las descartadas ni las
    vacías."""
    furniture = page_furniture(reading)
    read_lines = []
    for page_index, page in enumerate(reading.pages):
        for line_index, line in enumerate(page.lines):
            if line.discarded or furniture.get((page_index, line_index)):
                continue
            if not normalize_line(line.text).strip():
                continue
            read_lines.append((page, line))
    if len(read_lines) != len(canonical.lines):  # pragma: no cover - invariante
        raise RuntimeError("Las líneas leídas no coinciden con las del texto canónico.")

    paragraph_starts = {start for start, _ in canonical.paragraphs}
    result = []
    for (page, line), placed in zip(read_lines, canonical.lines):
        result.append(
            _Line(
                page=placed.page,
                start=placed.start,
                end=placed.end,
                text=canonical.text[placed.start : placed.end],
                paragraph_start=placed.start in paragraph_starts,
                zone=_zone_of(page, line, zones),
            )
        )
    return result


def _zone_of(page, line, zones):
    """La zona de tabla que contiene la línea: misma página, el centro vertical de la
    línea dentro de la zona y algo de superposición horizontal."""
    if line.top is None or line.bottom is None:
        return None
    middle = (line.top + line.bottom) / 2
    for number, zone in enumerate(zones):
        if zone["page"] != page.number:
            continue
        inside = zone["top"] <= middle <= zone["bottom"]
        if inside and line.x0 < zone["x1"] and line.x1 > zone["x0"]:
            return number
    return None


def _index_lines(lines):
    """Las líneas del índice: series de líneas con puntos guía (al menos dos), con hasta
    `_INDEX_WRAPPED_LINES` líneas sin puntos entre dos de ellas, y la palabra "ÍNDICE"
    sola justo antes."""
    leaders = [bool(_LEADER.search(line.text)) for line in lines]
    index = set()
    position = 0
    while position < len(lines):
        if not leaders[position]:
            position += 1
            continue
        run = [position]
        cursor = position + 1
        while cursor < len(lines):
            if leaders[cursor]:
                run.append(cursor)
                cursor += 1
                continue
            ahead = [
                step
                for step in range(cursor, min(cursor + _INDEX_WRAPPED_LINES, len(lines) - 1) + 1)
                if leaders[step]
            ]
            if not ahead:
                break
            run.append(ahead[0])
            cursor = ahead[0] + 1
        if len(run) >= 2:
            first, last = run[0], run[-1]
            if first > 0 and _INDEX_MARKER.fullmatch(lines[first - 1].text.strip()):
                first -= 1
            index.update(range(first, last + 1))
        position = cursor
    return index


def _index_spans(lines, index_lines):
    spans = []
    for number in sorted(index_lines):
        line = lines[number]
        if spans and number - 1 in index_lines:
            spans[-1] = (spans[-1][0], line.end, DISCARDED_INDEX)
        else:
            spans.append((line.start, line.end, DISCARDED_INDEX))
    return spans


def _section_heading(text):
    if not is_uppercase(text):
        return None
    heading = TITLE_HEADING.match(text)
    if not heading or not heading.group("kind").upper().startswith("SECCI"):
        return None
    return heading


def _annex_heading(line):
    text = line.text.strip()
    if not line.paragraph_start or not is_uppercase(text):
        return None
    return ANNEX_HEADING.match(text)


def _has_sections(lines, index_lines):
    return any(
        _section_heading(line.text.strip())
        for number, line in enumerate(lines)
        if number not in index_lines and line.zone is None
    )


# --- Recorrido ----------------------------------------------------------------------------


class _Walker:
    """Recorre las líneas y anota dónde empieza cada tramo (`openings`)."""

    def __init__(self, lines, index_lines, has_sections):
        self.lines = lines
        self.index_lines = index_lines
        self.has_sections = has_sections
        self.openings = []
        self.item_headings = []  # (renglón, clave, es un encabezado de un solo renglón)
        self.rejected = []
        self.section = None
        self.annex = None
        self.stack = []  # cláusulas abiertas de la sección
        # Tramo `no_ubicado` abierto por un encabezado rechazado: (clave, ruta, renglones).
        self.unlocated = None
        self.last_levels = None  # última cláusula aceptada de la sección
        self.counters = Counter()
        self.pre = _Container("pre", "Carátula", "")

    # Contexto -------------------------------------------------------------------------

    def _prefix(self):
        return f"{self.section.key}/" if self.section else ""

    def _container(self):
        if self.annex:
            return self.annex
        if self.section:
            return self.section
        if not self.has_sections and self.last_levels is not None:
            return _Container("", "", "")
        return self.pre

    def _section_class(self):
        return self.section.section_class if self.section else ""

    def _items(self):
        items = []
        for clause in self.stack:
            for number in clause.items:
                if number not in items:
                    items.append(number)
        return items

    def _parent(self):
        """Clave y ruta de lo que contiene a un tramo hijo (tabla, párrafo, viñeta)."""
        if self.unlocated:
            return self.unlocated[0], self.unlocated[1]
        if self.stack and not self.annex:
            return self.stack[-1].key, self.stack[-1].path
        container = self._container()
        return container.key, container.path

    def _child(self, line, segment_type, suffix, path_name, label="", zone=None):
        parent_key, parent_path = self._parent()
        self.counters[(parent_key, suffix)] += 1
        number = self.counters[(parent_key, suffix)]
        key = f"{parent_key}/{suffix}-{number}" if parent_key else f"{suffix}-{number}"
        self._open(
            line,
            key=key,
            segment_type=segment_type,
            label=label,
            path=_join(parent_path, f"{path_name} {number}"),
            parent=parent_key,
            zone=zone,
        )

    def _open(self, line, **fields):
        fields.setdefault("section_class", self._section_class())
        fields.setdefault("items", self._items())
        self.openings.append(_Opening(line=line, **fields))

    def _current(self):
        return self.openings[-1] if self.openings else None

    @property
    def items(self):
        """Los renglones de la lectura, por número, con la clave del tramo de su
        encabezado: el primero que nombra solo ese renglón ("RENGLÓN N° 3"); si no hay,
        el primer rango que lo incluye ("RENGLONES NROS. 2 A 4"). Así una cláusula de
        condiciones para todos los renglones no le quita la clave al encabezado de las
        especificaciones de cada uno."""
        chosen = {}
        for number, key, single in self.item_headings:
            if number not in chosen or (single and not chosen[number][1]):
                chosen[number] = (key, single)
        return [{"number": number, "key": chosen[number][0]} for number in sorted(chosen)]

    # Recorrido ------------------------------------------------------------------------

    def walk(self):
        after_gap = True  # la línea anterior no es de ningún tramo (índice o inicio)
        for number, line in enumerate(self.lines):
            if number in self.index_lines:
                after_gap = True
                continue
            self._line(number, line, after_gap)
            after_gap = False

    def _line(self, number, line, after_gap):
        text = line.text.strip()
        current = self._current()

        if line.zone is not None:
            if current is None or current.zone != line.zone or after_gap:
                self._child(number, TABLA, "tabla", "tabla", zone=line.zone)
            return

        section = _section_heading(text)
        if section:
            self._open_section(number, text, section)
            return

        annex = _annex_heading(line)
        if annex:
            self._open_annex(number, text, annex)
            return

        after_table = current is not None and current.segment_type == TABLA

        if self.annex:
            if line.paragraph_start or after_gap or after_table:
                self._child(number, PARRAFO, "p", "párrafo")
            return

        if self._try_clause(number, line, text):
            return

        if self.unlocated:
            # Hasta el próximo encabezado aceptado, todo sigue en el tramo no ubicado;
            # después de una tabla, en otro.
            if after_gap or after_table:
                self._unlocated_opening(number, self.unlocated[2])
            return

        if self.stack:
            if self._try_bullet(number, line, text):
                return
            if after_gap or after_table:
                self._child(number, PARRAFO, "p", "párrafo")
            return

        # Sin cláusula abierta: carátula, o lo que sigue al título de una sección.
        if self.section is None:
            if line.paragraph_start or after_gap or after_table:
                self._child(number, PARRAFO, "p", "párrafo")
            return
        heading_continues = (
            current is not None
            and current.segment_type == TITULO
            and current.key == self.section.key
            and not line.paragraph_start
            and not after_gap
        )
        if heading_continues:
            return
        if current is not None and current.segment_type == NO_UBICADO and not after_gap:
            return
        self._child(number, NO_UBICADO, "no-ubicado", "no ubicado")

    def _open_section(self, number, text, heading):
        designator = re.sub(r"[^0-9A-Za-z]", "", heading.group("number"))
        self.section = _Container(
            key=f"sec-{designator.lower()}",
            path=f"Sección {designator}",
            section_class=_section_class(text),
        )
        self.annex = None
        self.stack = []
        self.unlocated = None
        self.last_levels = None
        self._open(
            number,
            key=self.section.key,
            segment_type=TITULO,
            label=text,
            path=self.section.path,
            items=[],
        )

    def _open_annex(self, number, text, heading):
        designator = heading.group("designator") or ""
        name = "Anexo" + (f" {designator}" if designator else "")
        key = self._prefix() + "anexo" + (f"-{designator.lower()}" if designator else "")
        # Una clave de anexo repetida: el contenedor toma la clave con su sufijo, para
        # que sus párrafos cuelguen de él.
        self.counters[("annex", key)] += 1
        repeated = self.counters[("annex", key)]
        if repeated > 1:
            key = f"{key}~{repeated}"
        section_path = self.section.path if self.section else ""
        self.annex = _Container(key, _join(section_path, name), self._section_class())
        self.stack = []
        self.unlocated = None
        self._open(
            number,
            key=key,
            segment_type=TITULO,
            label=text,
            path=self.annex.path,
            items=[],
        )

    def _try_clause(self, number, line, text):
        match = _CLAUSE.match(text)
        if not match:
            return False
        raw = match.group("number")
        levels = tuple(int(part) for part in raw.split("."))
        rest = text[match.end() :].strip()
        if len(levels) == 1 and not match.group("dot"):
            # "5 DEFINICIÓN DEL SERVICIO.": sin punto, solo si es un título en
            # mayúsculas al comienzo de un párrafo y continúa la numeración (T-178). Si
            # no, es parte de una oración ("3 UNIDADES") y no abre ni rechaza nada.
            if not (
                rest
                and is_uppercase(rest)
                and (line.paragraph_start or self._previous_text_closes(number))
                and self._continues(levels)
            ):
                return False
        clause_items = _clause_items(rest)
        title = rest if rest and is_uppercase(rest) else ""
        if not self._continues(levels):
            rejected = {"number": raw, "page": line.page, "char_start": line.start, "key": ""}
            self.rejected.append(rejected)
            in_clauses = self.section is not None or self.last_levels is not None
            if in_clauses and self._looks_like_heading(number, line, match, title, clause_items):
                rejected["key"] = self._open_unlocated(number, text, match, title, clause_items)
                return True
            return False

        while self.stack and not _is_ancestor(self.stack[-1].levels, levels):
            self.stack.pop()
        self.unlocated = None
        label = text if title else text[: match.end()]
        name = raw + (f". {_sentence_case(title)}" if title else "")
        if self.stack:
            parent_path = self.stack[-1].path
        else:
            parent_path = self.section.path if self.section else ""
        key = self._prefix() + raw
        clause = _Clause(levels=levels, key=key, path=_join(parent_path, name), items=clause_items)
        self.stack.append(clause)
        self.last_levels = levels
        for item in clause_items:
            self.item_headings.append((item, key, len(clause_items) == 1))
        self._open(
            number,
            key=key,
            segment_type=CLAUSULA,
            label=label,
            path=clause.path,
            levels=levels,
        )
        return True

    def _looks_like_heading(self, number, line, match, title, clause_items):
        """Si un número rechazado por la secuencia tiene forma de encabezado: con su
        punto, un título en mayúsculas o un renglón, y al comienzo de un párrafo, después
        de un texto que cierra o seguido de ese título o renglón. "3.972 kcal" en medio
        de una oración no lo es."""
        if not (match.group("dot") or title or clause_items):
            return False
        if title or clause_items:
            return True
        return line.paragraph_start or self._previous_text_closes(number)

    def _open_unlocated(self, number, text, match, title, clause_items):
        """Un encabezado rechazado abre un tramo `no_ubicado`, pendiente por numeración
        inesperada, hasta el próximo encabezado aceptado. Otro encabezado rechazado lo
        continúa, salvo que nombre un renglón: entonces abre otro, para que cada renglón
        tenga su tramo y su clave. Sin renglón propio, el tramo lleva los renglones de lo
        que estaba abierto (ante la duda, de más)."""
        current = self._current()
        if self.unlocated and not clause_items and current.key == self.unlocated[0]:
            return self.unlocated[0]
        if clause_items:
            items = clause_items
        elif self.unlocated:
            items = self.unlocated[2]
        else:
            items = self._items()
        label = text if title else text[: match.end()]
        key, _ = self._unlocated_opening(number, items, label)
        for item in clause_items:
            self.item_headings.append((item, key, len(clause_items) == 1))
        return key

    def _unlocated_opening(self, number, items, label="", detail=DETAIL_UNEXPECTED_NUMBERING):
        container = self._container()
        self.counters[(container.key, "no-ubicado")] += 1
        count = self.counters[(container.key, "no-ubicado")]
        suffix = f"no-ubicado-{count}"
        key = f"{container.key}/{suffix}" if container.key else suffix
        path = _join(container.path, f"no ubicado {count}")
        self._open(
            number,
            key=key,
            segment_type=NO_UBICADO,
            label=label,
            path=path,
            items=list(items),
            detail=detail,
        )
        if detail == DETAIL_UNEXPECTED_NUMBERING:
            self.unlocated = (key, path, list(items))
        return key, path

    def _continues(self, levels):
        """Si el número continúa la numeración de la sección (o del pliego, sin
        secciones)."""
        if self.annex:
            return False
        if self.last_levels is None:
            if not self.has_sections or self.section is not None:
                return len(levels) == 1
            return False
        current = self.last_levels
        valid = {current[:depth] + (current[depth] + 1,) for depth in range(len(current))}
        if len(current) < CLAUSE_LEVELS:
            valid.add(current + (1,))
        return levels in valid

    def _try_bullet(self, number, line, text):
        bullet = _BULLET.match(text)
        if bullet:
            self._child(number, VINETA, "v", "viñeta", label=bullet.group(0))
            return True
        inciso = _INCISO.match(text)
        if inciso and self._previous_text_closes(number):
            letter = inciso.group("letter")
            parent_key, parent_path = self._parent()
            self._open(
                number,
                key=f"{parent_key}/inc-{letter}",
                segment_type=VINETA,
                label=inciso.group(0),
                path=_join(parent_path, f"inciso {letter})"),
                parent=parent_key,
            )
            return True
        return False

    def _previous_text_closes(self, number):
        if number == 0:
            return True
        return self.lines[number - 1].text.rstrip().endswith(_INCISO_BEFORE)


def _is_ancestor(levels, child):
    return len(levels) < len(child) and child[: len(levels)] == levels


def _clause_items(rest):
    """Los renglones que nombra el comienzo del texto de una cláusula."""
    ranged = _ITEM_RANGE.match(rest)
    if ranged:
        first, last = int(ranged.group("first")), int(ranged.group("last"))
        if first <= last:
            return list(range(first, last + 1))
    single = _ITEM.match(rest)
    if single:
        return [int(single.group("number"))]
    return []


def _section_class(title):
    plain = "".join(
        char
        for char in unicodedata.normalize("NFD", title.lower())
        if unicodedata.category(char) != "Mn"
    )
    for pattern, section_class in _SECTION_CLASSES:
        if pattern.search(plain):
            return section_class
    return ""


def _sentence_case(title):
    """"GARANTÍA DE MANTENIMIENTO" → "Garantía de mantenimiento", para la ruta."""
    return title[:1].upper() + title[1:].lower()


def _join(*parts):
    return _PATH_SEPARATOR.join(part for part in parts if part)


# --- Tramos -------------------------------------------------------------------------------


def _segments(reading, canonical, lines, openings, index_lines, max_chars):
    """Arma los tramos: cada uno va desde la línea donde empieza hasta la anterior al
    próximo comienzo o a la próxima línea del índice."""
    boundaries = sorted({opening.line for opening in openings} | set(index_lines))
    doubtful = {page.number for page in reading.pages if page.status == PAGE_DOUBTFUL}
    segments = []
    for position, opening in enumerate(openings):
        following = [b for b in boundaries if b > opening.line]
        last_line = (following[0] if following else len(lines)) - 1
        start, end = lines[opening.line].start, lines[last_line].end
        segment_type = opening.segment_type
        following_opening = openings[position + 1 : position + 2]
        if segment_type == CLAUSULA and _is_title(
            canonical.text[start:end], opening, following_opening
        ):
            segment_type = TITULO
        parts = _split_long(canonical.text, start, end, max_chars)
        for part, (part_start, part_end) in enumerate(parts, start=1):
            segments.append(
                _segment(
                    reading,
                    canonical,
                    opening,
                    segment_type,
                    part,
                    part_start,
                    part_end,
                    doubtful,
                )
            )
    return segments


def _is_title(text, opening, following):
    """Una cláusula que es solo su título en mayúsculas, seguida de algo que cuelga de
    ella (una subcláusula, una viñeta, una tabla), es un título."""
    if not is_uppercase(text) or not following:
        return False
    nxt = following[0]
    if nxt.segment_type == CLAUSULA:
        return _is_ancestor(opening.levels, nxt.levels)
    return nxt.parent == opening.key


def _segment(reading, canonical, opening, segment_type, part, start, end, doubtful):
    page_start, page_end = canonical.pages_at(start, end)
    origin = _origin(reading, canonical, start, end)
    confidence = _confidence(canonical, start, end) if origin == ORIGIN_OCR else (None, None)
    review = ""
    if segment_type == TABLA:
        review = REVIEW_TABLE
    elif segment_type == NO_UBICADO:
        review = REVIEW_UNLOCATED
    elif page_start is not None and any(
        page in doubtful for page in range(page_start, page_end + 1)
    ):
        review = REVIEW_DOUBTFUL_PAGE
    return TenderSegment(
        order=0,
        key=opening.key if part == 1 else f"{opening.key}#{part}",
        label=opening.label if part == 1 else "",
        path=opening.path,
        segment_type=segment_type,
        section_class=opening.section_class,
        items=list(opening.items),
        page_start=page_start,
        page_end=page_end,
        char_start=start,
        char_end=end,
        text=canonical.text[start:end],
        text_origin=origin,
        ocr_confidence_min=confidence[0],
        ocr_confidence_avg=confidence[1],
        review_reason=review,
        review_detail=opening.detail,
    )


def _split_long(text, start, end, max_chars):
    """Parte `text[start:end]` en partes de hasta `max_chars` caracteres: después del
    último fin de oración que entra; si no hay, en el último espacio; si tampoco, en el
    máximo. Las partes no llevan los espacios que las separan."""
    parts = []
    while end - start > max_chars:
        window = text[start : start + max_chars + 1]
        cut = None
        for sentence in _SENTENCE_END.finditer(window):
            if sentence.end() <= max_chars:
                cut = sentence.end()
        if cut is None:
            space = window.rfind(" ", 1, max_chars + 1)
            cut = space if space > 0 else max_chars
        parts.append((start, start + cut))
        start += cut
        while start < end and text[start].isspace():
            start += 1
    parts.append((start, end))
    return parts


def _origin(reading, canonical, start, end):
    """Origen del texto, como en la 001: `ocr` si alguna línea vino de reconocimiento."""
    origins = {line.origin for line in canonical.lines_in(start, end)}
    if ORIGIN_OCR in origins:
        return ORIGIN_OCR
    if origins == {ORIGIN_WEB} or (not origins and reading.file_format == FORMAT_HTML):
        return ORIGIN_WEB
    return ORIGIN_PDF_TEXT


def _confidence(canonical, start, end):
    """Confianza mínima y promedio del reconocimiento, como en la 001."""
    values = []
    for line in canonical.lines_in(start, end):
        if line.origin != ORIGIN_OCR:
            continue
        if line.words:
            values.extend(word.confidence for word in line.words)
        elif line.confidence is not None:
            values.append(line.confidence)
    if not values:
        return None, None
    return (
        round(min(values), _CONFIDENCE_DECIMALS),
        round(sum(values) / len(values), _CONFIDENCE_DECIMALS),
    )


def _unreadable_pages(reading, canonical):
    """Un tramo `pagina`, sin texto, por cada página ilegible o no leída, en el lugar
    del texto canónico donde estaría."""
    segments = []
    for page in reading.pages:
        if page.status not in _UNREADABLE_PAGES or page.number is None:
            continue
        later = [line.start for line in canonical.lines if line.page and line.page > page.number]
        position = later[0] if later else len(canonical.text)
        segments.append(
            TenderSegment(
                order=0,
                key=f"pagina-{page.number}",
                label="",
                path=f"Página {page.number}",
                segment_type=PAGINA,
                section_class="",
                items=[],
                page_start=page.number,
                page_end=page.number,
                char_start=position,
                char_end=position,
                text="",
                text_origin="",
                review_reason=REVIEW_ILLEGIBLE_PAGE,
            )
        )
    return segments


def _unique_keys(segments):
    """Una clave repetida suma `~2`, `~3`."""
    seen = Counter()
    for segment in segments:
        seen[segment.key] += 1
        if seen[segment.key] > 1:
            segment.key = f"{segment.key}~{seen[segment.key]}"


# --- Cobertura e informe ------------------------------------------------------------------


def check_coverage(canonical, segments, discarded):
    """Control de cobertura: cada carácter del texto canónico está en un tramo, en lo
    descartado o es un separador (espacio o salto de línea) entre dos de ellos. La suma
    tiene que dar el total, sin huecos ni solapamientos; si no, `problems` dice dónde."""
    text = canonical.text
    ranges = [("segments", s.char_start, s.char_end) for s in segments]
    ranges += [("discarded", start, end) for start, end, _ in discarded]
    ranges = sorted((r for r in ranges if r[2] > r[1]), key=lambda r: r[1])
    totals = {"segments": 0, "discarded": 0, "separators": 0}
    problems = []
    position = 0
    for kind, start, end in ranges:
        if start < position:
            overlap = {"kind": "overlap", "char_start": start, "char_end": min(position, end)}
            problems.append(overlap)
        else:
            gap = text[position:start]
            if gap and gap.strip():
                problems.append({"kind": "hole", "char_start": position, "char_end": start})
            else:
                totals["separators"] += len(gap)
        totals[kind] += end - start
        position = max(position, end)
    tail = text[position:]
    if tail.strip():
        problems.append({"kind": "hole", "char_start": position, "char_end": len(text)})
    else:
        totals["separators"] += len(tail)
    matches = not problems and sum(totals.values()) == len(text)
    return {
        "total": len(text),
        **totals,
        "discarded_lines": canonical.discarded_lines,
        "matches": matches,
        "problems": problems,
    }


def _report(reading, result, rejected):
    """El informe de la lectura (`tenders_reading.report`): páginas por estado, tramos
    por tipo, cobertura, pendientes, renglones y números que no continuaron la
    numeración."""
    pages = Counter(page.status for page in reading.pages)
    types = Counter(segment.segment_type for segment in result.segments)
    return {
        "rules_version": RULES_VERSION,
        "pages_by_status": dict(pages),
        "segments_by_type": {kind: types[kind] for kind in SEGMENT_TYPES},
        "segments": len(result.segments),
        "coverage": result.coverage,
        "pending": [
            {
                "key": segment.key,
                "reason": segment.review_reason,
                "detail": segment.review_detail,
            }
            for segment in result.segments
            if segment.review_reason
        ],
        "items": result.items,
        "rejected_headings": rejected,
    }
