"""Partición de documentos en unidades citables (ADR-0004; plan 001, "Ingesta"; T-013,
T-023 y T-024).

Entrada única: `split_document(lectura, parte, categoria, document_info)`. Recibe la
lectura de `norms/reading/`, la parte del documento (`cuerpo`, por omisión, o la clave de
un anexo: `anexo`, `anexo-i`), la categoría de su norma (REQ-017), que elige la regla, y,
si la carga los pasa, el nombre, la huella y la fecha de lectura del archivo, que van a
la parte "Documento" del informe:

- **Normas** (`NORM_RULE`): régimen específico, otra normativa aplicable y marco
  nacional, y también la categoría omitida, que es como se partía antes de T-024.
  Artículos, incisos, cláusulas, anexos, visto y considerandos (`partition.py`).
- **Dictámenes y recomendaciones** (`OPINION_RULE`): dictamen legal y recomendación de
  auditoría. Puntos numerados o, si no hay numeración, párrafos (`opinions.py`). Por
  ahora solo como documento único (`cuerpo`).

Devuelve un `SplitResult` con:

- el texto canónico, su huella y la versión de las reglas (`canonical.py`);
- las unidades, en el orden del documento (`Unit`): artículos con sus incisos, cláusulas
  (texto normativo sin número), anexos, visto y considerandos (`headings.py` y
  `partition.py`), o puntos y párrafos (`opinions.py`). Con una parte que es un anexo, la primera es la unidad raíz de tipo
  `anexo`, cuya clave es la parte, y las demás cuelgan de ella (`anexo/art-1`); con
  `cuerpo` no hay unidad raíz (`art-1`). Una unidad viene siempre después de la que la
  contiene. El texto de cada unidad es igual a `canonical_text[char_start:char_end]`;
- el informe de lectura completo, con las diez partes del ADR-0004, en datos y en texto
  (`report.py`, T-025).

Cada unidad lleva su origen (`text_origin`) y, si alguna de sus líneas vino de
reconocimiento sobre imagen, la confianza mínima y promedio de las palabras de esas
líneas (REQ-015).

Todo corre en CPU, sin los servicios de IA, y la misma lectura da siempre el mismo
resultado.
"""

import hashlib
import re
from dataclasses import dataclass, field

from evaluon.norms.reading import FORMAT_HTML, ORIGIN_OCR, ORIGIN_PDF_TEXT, ORIGIN_WEB
from evaluon.norms.splitting import opinions
from evaluon.norms.splitting import partition as rules
from evaluon.norms.splitting.canonical import CanonicalText, build_canonical_text
from evaluon.norms.splitting.headings import ARTICLE
from evaluon.norms.splitting.report import build_report, report_text

# Versión de las reglas de partición; se guarda con la lectura (`tool_versions`) y en el
# informe. Cambia cada vez que cambia una regla, para saber con qué reglas se partió.
# 2: T-023 (incisos, títulos en la ruta, cláusulas, anexos, considerandos, carátula,
# encabezados y pies, secuencia con margen, encabezados de reconocimiento).
# 3: T-023, ajustes de verificación (el índice se confirma dentro de su contenedor; un
# párrafo en prosa que empieza con "ANEXO I" no abre un anexo).
# 4: T-024 (reglas de dictámenes y recomendaciones, en puntos y párrafos, elegidas por la
# categoría; el informe dice qué regla se usó). Las reglas de normas no cambian: una
# norma da las mismas unidades y el mismo texto canónico que con la versión 3.
# 5: T-025 (informe de lectura completo y confianza mínima y promedio de las unidades
# reconocidas sobre imagen). Las reglas de corte no cambian: el texto canónico, las
# unidades, sus claves y sus textos son los de la versión 4. Cambia lo que se guarda con
# la lectura: el informe (cuya huella firma la validación) y la confianza de las unidades
# `ocr`, que antes quedaba vacía. Se sube para que una lectura guardada diga con qué
# versión se armaron su informe y sus unidades, y para que `releer_norma` sepa cuáles
# conviene releer.
# 6: T-050 (reglas para las páginas web de la 297/03 y del cuerpo de la 247/2022). Cambian
# las unidades de esas páginas: el artículo de forma no se lleva lo que le sigue; los
# datos de publicación del Boletín Oficial se descartan; un título solo se descarta con
# su nombre de la línea siguiente; el índice admite incisos y epígrafes partidos;
# `Inciso N)` es del primer nivel y su último lleva sus párrafos; un párrafo que presenta
# una lista abre otra en el primer nivel; incisos `c)Nombre` e `Inciso 1).`. En los PDF
# del corpus y de las pruebas el texto canónico y las unidades no cambian; se sube para
# que una lectura guardada diga con qué reglas se partió y `releer_norma` sepa cuáles
# releer. Ajustes de la verificación de T-050, dentro de la misma versión porque la 6
# todavía no se integró: un inciso no repite la clave de otro de su nivel (se anida o
# queda dentro, y se informa); el artículo de forma exige la fórmula completa; la nota
# de publicación es solo la del BORA; el informe cuenta el visto aparte.
# 7: T-028 (decisión del Coordinador). En una lectura de reconocimiento sobre imagen, el
# informe avisa los incisos que saltan letras de su lista y los párrafos que empiezan como
# un inciso mal leído (`ocr_inciso_gaps`). Los cortes no cambian: el texto canónico, las
# unidades, sus claves y sus textos son los de la versión 6 en los tres formatos; cambia
# el informe de las lecturas con reconocimiento, cuya huella firma la validación.
# Corrección (T-043): el informe de toda lectura cambia con la versión 7, no solo el de
# las lecturas con reconocimiento, porque lleva la versión de las reglas.
# 8: T-043, ajuste contra el corpus real. Un último inciso sin incisos propios cuyo texto
# termina en dos puntos se lleva los párrafos que le siguen hasta el final de la unidad
# que contiene la lista, y el informe ya no lo señala para revisar: "f) OTRAS
# OBLIGACIONES DEL CO-CONTRATANTE:" (297/03, Anexo I, art. 14) y el punto 4 del inciso e
# del art. 33 del anexo de la 247/2022 con sus puntos 4.1 y 4.2. El texto canónico, las
# claves y los textos de las unidades base no cambian; cambian el texto de esos dos
# incisos y el informe.
# 9: T-043, observaciones del testeador. El informe señala en "Requiere atención" cada
# último inciso que se llevó párrafos por terminar en dos puntos (`presenting_inciso`).
# Si el inciso que contiene la lista es el último del artículo, su último punto que
# termina en dos puntos también se lleva lo que le sigue, hasta el final del artículo.
# En el corpus no cambia ninguna unidad respecto de la versión 8; cambia el informe.
RULES_VERSION = "9"

# Reglas de partición y categorías que las eligen (REQ-017; `Norm.Category`).
NORM_RULE = "normas"
OPINION_RULE = "dictamenes"
NORM_RULE_CATEGORIES = ("regimen_especifico", "otra_normativa", "marco_nacional")
OPINION_RULE_CATEGORIES = ("dictamen_legal", "recomendacion_auditoria")

BODY = "cuerpo"
# `cuerpo`, o la clave de un anexo: `anexo` o `anexo-` y su número o letra.
_PART = re.compile(r"cuerpo|anexo(?:-[a-z0-9]+)?")

PATH_SEPARATOR = rules.PATH_SEPARATOR

# Decimales de la confianza de una unidad, como los de la lectura.
CONFIDENCE_DECIMALS = 2


@dataclass
class Unit:
    """Una unidad citable, con los campos de `norms_unit`. `parent_key` es la clave de
    la unidad que la contiene; vacía si cuelga de la norma."""

    unit_type: str
    number: str
    label: str
    key: str
    path: str
    order: int
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
    text: str
    text_origin: str
    parent_key: str | None = None
    ocr_confidence_min: float | None = None
    ocr_confidence_avg: float | None = None


@dataclass
class SplitResult:
    canonical: CanonicalText
    canonical_sha256: str
    rules_version: str
    units: list[Unit] = field(default_factory=list)
    report: dict = field(default_factory=dict)
    report_text: str = ""

    @property
    def canonical_text(self):
        return self.canonical.text


def rule_for(category):
    """La regla de partición que corresponde a la categoría de la norma. Sin categoría,
    la de normas."""
    if category is None or category in NORM_RULE_CATEGORIES:
        return NORM_RULE
    if category in OPINION_RULE_CATEGORIES:
        return OPINION_RULE
    raise ValueError(
        f"La categoría {category!r} no es válida: tiene que ser una de "
        + ", ".join(NORM_RULE_CATEGORIES + OPINION_RULE_CATEGORIES)
        + "."
    )


def split_document(reading, part=BODY, category=None, document_info=None):
    """Parte la lectura de un documento en unidades y arma su informe de lectura, con la
    regla que corresponde a la categoría de su norma. `document_info` trae, si la carga
    los conoce, `file_name`, `file_sha256` y `read_at` (texto), para la parte "Documento"
    del informe; la partición no los calcula, para que la misma lectura dé siempre el
    mismo informe."""
    rule = rule_for(category)
    if not isinstance(part, str) or not _PART.fullmatch(part):
        raise ValueError(
            f"La parte {part!r} no es válida: tiene que ser 'cuerpo' o la clave de un "
            "anexo, como 'anexo' o 'anexo-i'."
        )
    if rule == OPINION_RULE and part != BODY:
        raise ValueError(
            f"La parte {part!r} no es válida para un dictamen o una recomendación: por "
            "ahora se parten como documento único, con la parte 'cuerpo'."
        )
    canonical = build_canonical_text(reading)
    text = canonical.text
    ocr_flags = [
        any(line.origin == ORIGIN_OCR for line in canonical.lines_in(start, end))
        for start, end in canonical.paragraphs
    ]
    paragraphs = rules.classify(canonical.paragraphs, text, canonical, ocr_flags)
    if rule == OPINION_RULE:
        result = opinions.partition(paragraphs)
    else:
        root = _annex_root(part) if part != BODY else None
        result = rules.partition(paragraphs, root=root)

    units, spans, after_last_inciso, inciso_key_taken, ocr_inciso_gaps = [], [], [], [], []
    presenting_inciso = []
    for item in result.items:
        start, end = _range(paragraphs, item.first, item.last, len(text))
        if isinstance(item, rules.Span):
            spans.append((item.kind, start, end, item.reason))
            continue
        unit = _unit(canonical, reading, item, start, end)
        units.append(unit)
        if item.unit_type == "articulo":
            nodes = rules.find_incisos(
                paragraphs,
                item,
                key_taken=inciso_key_taken,
                ocr_gaps=ocr_inciso_gaps,
                presenting=presenting_inciso,
            )
            for node in nodes:
                _add_incisos(units, canonical, reading, paragraphs, unit, node)
            for path, count in rules.after_last_inciso(nodes, item.last):
                keys = [unit.key] + [f"inc-{node.heading.number}" for node in path]
                after_last_inciso.append(
                    {
                        "key": "/".join(keys),
                        "inside": "/".join(keys[:-1]),
                        "paragraphs": count,
                        "page": paragraphs[path[-1].end + 1].page,
                    }
                )
    for order, unit in enumerate(units, start=1):
        unit.order = order

    sequence = [
        {"container": c.name, "key": c.key, "gaps": c.gaps, "not_accepted": c.not_accepted}
        for c in result.containers
    ]
    if rule == OPINION_RULE:
        # Un dictamen no tiene artículos por contenedor; su secuencia es la de los puntos.
        containers = []
        for item in sequence:
            item["heading"] = "punto"
    else:
        index_numbers = _index_numbers(result, paragraphs)
        containers = [
            {"name": c.name, "key": c.key, "index_numbers": index_numbers[c.key]}
            for c in result.containers
        ]

    canonical_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    report = build_report(
        reading=reading,
        canonical=canonical,
        units=units,
        segments=spans,
        part=part,
        rules_version=RULES_VERSION,
        rule=rule,
        containers=containers,
        sequence=sequence,
        uppercase_in_units=result.uppercase_in_units,
        doubtful_headings=result.doubtful_headings,
        after_last_inciso=after_last_inciso,
        presenting_inciso=presenting_inciso,
        inciso_key_taken=inciso_key_taken,
        ocr_inciso_gaps=ocr_inciso_gaps,
        canonical_sha256=canonical_sha256,
        document_info=document_info,
    )
    return SplitResult(
        canonical=canonical,
        canonical_sha256=canonical_sha256,
        rules_version=RULES_VERSION,
        units=units,
        report=report,
        report_text=report_text(report),
    )


def _index_numbers(result, paragraphs):
    """Números de artículo que lista el índice de cada contenedor, por su clave: la
    cuenta esperada del informe (T-025). Un índice pertenece al contenedor en el que
    aparece: el cuerpo, la unidad raíz de un anexo o el último anexo abierto en el
    cuerpo."""
    numbers = {container.key: set() for container in result.containers}
    current = result.containers[0].key
    for item in result.items:
        if isinstance(item, rules.Block):
            if item.unit_type == "anexo" and item.parent_key is None and item.key in numbers:
                current = item.key
            continue
        if item.kind != rules.DISCARDED or item.reason != "indice":
            continue
        for paragraph in paragraphs[item.first : item.last + 1]:
            heading = paragraph.heading
            if heading.kind == ARTICLE and heading.article_number is not None and not heading.suffix:
                numbers[current].add(heading.article_number)
    return {key: sorted(values) for key, values in numbers.items()}


def _annex_root(part):
    """Clave, número y nombre de la unidad raíz de un anexo: `anexo-i` → `I`, "Anexo I"."""
    suffix = part.partition("-")[2]
    number = suffix.upper()
    return {"key": part, "number": number, "path": "Anexo" + (f" {number}" if number else "")}


def _range(paragraphs, first, last, length):
    """Posición en el texto canónico de los párrafos `first` a `last`. Un tramo vacío
    queda en el comienzo del párrafo que le seguiría."""
    if first > last:
        start = paragraphs[first].start if first < len(paragraphs) else length
        return start, start
    return paragraphs[first].start, paragraphs[last].end


def _unit(canonical, reading, block, start, end):
    page_start, page_end = canonical.pages_at(start, end)
    text_origin = _origin(canonical, reading, start, end)
    confidence_min, confidence_avg = (
        _confidence(canonical, start, end) if text_origin == ORIGIN_OCR else (None, None)
    )
    return Unit(
        unit_type=block.unit_type,
        number=block.number,
        label=block.label,
        key=block.key,
        path=block.path,
        order=0,
        page_start=page_start,
        page_end=page_end,
        char_start=start,
        char_end=end,
        text=canonical.text[start:end],
        text_origin=text_origin,
        parent_key=block.parent_key,
        ocr_confidence_min=confidence_min,
        ocr_confidence_avg=confidence_avg,
    )


def _confidence(canonical, start, end):
    """Confianza mínima y promedio de una unidad reconocida sobre imagen (REQ-015): sobre
    las palabras de sus líneas de reconocimiento; una línea sin palabras cuenta con su
    propia confianza. Vacías si ninguna línea trae confianza."""
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
    return round(min(values), CONFIDENCE_DECIMALS), round(sum(values) / len(values), CONFIDENCE_DECIMALS)


def _add_incisos(units, canonical, reading, paragraphs, parent, node):
    """Suma el inciso `node` y los suyos, en el orden del documento."""
    start, end = paragraphs[node.index].start, paragraphs[node.end].end
    number = node.heading.number
    block = rules.Block(
        unit_type="inciso",
        number=number,
        label=node.heading.label,
        key=f"{parent.key}/inc-{number}",
        path=f"{parent.path}{PATH_SEPARATOR}Inciso {number}",
        parent_key=parent.key,
        first=node.index,
        last=node.end,
    )
    unit = _unit(canonical, reading, block, start, end)
    units.append(unit)
    for child in node.children:
        _add_incisos(units, canonical, reading, paragraphs, unit, child)


def _origin(canonical, reading, start, end):
    """Origen del texto de una unidad (REQ-015): `ocr` si alguna de sus líneas vino de
    reconocimiento; si no, el de sus líneas. Una unidad sin texto toma el del formato."""
    origins = {line.origin for line in canonical.lines_in(start, end)}
    if ORIGIN_OCR in origins:
        return ORIGIN_OCR
    if origins == {ORIGIN_WEB} or (not origins and reading.file_format == FORMAT_HTML):
        return ORIGIN_WEB
    return ORIGIN_PDF_TEXT
