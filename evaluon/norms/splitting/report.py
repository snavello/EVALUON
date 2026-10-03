"""Informe de lectura (REQ-004, REQ-015; ADR-0004, "Qué contiene el informe de lectura";
T-013, T-023, T-024 y T-025).

Se arma en datos (`norms_reading.report`, JSON) y se entrega además como texto legible
(`norms_reading.report_text`), en español llano, porque esta feature no tiene pantalla
de carga. El texto se arma solo a partir de los datos (`report_text(report)`): lo
guardado y lo mostrado coinciden, y la validación firma la huella de ese texto (T-015).

Las diez partes del ADR-0004, en este orden:

1. **Requiere atención** (`attention`): lista corta de todo lo que sigue que no está en
   orden, cada aviso con su clase (`kind`) y su texto. La arma `attention_items(report)`
   a partir de las demás partes; quien cambie una parte después de armar el informe (la
   carga, al completar los posibles duplicados) la vuelve a armar con esa función.
2. **Documento** (`document`): nombre, huella y fecha de lectura del archivo si la carga
   los pasa, formato, cantidad de páginas, versiones de las herramientas (con la huella
   del modelo de español, si hubo reconocimiento), versión y regla de partición, parte y
   huella del texto canónico.
3. **Páginas** (`pages`, `page_list`, `page_summary`): por cada página, origen, estado,
   caracteres que aportó al texto canónico y confianza promedio si hubo reconocimiento;
   aparte, las listas de ilegibles, casi sin texto, dudosas, sin texto y en blanco.
   Estados del informe (`state`): `legible`, `dudosa`, `ilegible` (reconocida con
   confianza baja), `casi_sin_texto` (reconocida, pero con menos de `MIN_WORDS` palabras:
   la lectura la da como ilegible aunque se lea bien, como una carátula que dice solo
   "ANEXO"), `en_blanco` y `sin_texto` (no se obtuvo texto: sin capa de texto y sin
   reconocimiento; puede estar en blanco o traer solo una imagen o una firma digital,
   como la página 45 del anexo de la 247/2022). `pages` (total y no leídas, de la
   lectura) se conserva como estaba: lo usan la carga y su registro.
4. **Unidades reconocidas** (`units`, `sequence`, `doubtful_headings`,
   `uppercase_in_units`, `after_last_inciso`): cantidad por tipo y por contenedor, primer
   y último número, la cuenta esperada de artículos frente a la reconocida (según el
   índice, si el contenedor tiene uno, o según la numeración), saltos y repeticiones, y
   los avisos de la partición. Una cláusula se cuenta como un tipo más y no entra en el
   control de saltos.
5. **No ubicado** (`unlocated`): cada tramo, con su página y sus primeras palabras.
6. **Descartado** (`discarded`, `discarded_lines`, `discarded_line_list`,
   `discarded_line_forms`): los tramos (carátula, índice, títulos que pasan a la ruta) y
   las líneas que no entran en el texto canónico, con cuántas hay de cada forma y un
   ejemplo. Una forma es el motivo y el texto de la línea con sus números cambiados por
   `#`, para que "Página 3 de 40" y "Página 4 de 40" sean la misma.
7. **Uniones de palabras cortadas** (`hyphen_joins`): cuántas y cuáles.
8. **Reconocimiento sobre imagen** (`ocr`): cuántas unidades tienen ese origen y las
   palabras de menor confianza del texto de las unidades, con su página, para
   compararlas con el original.
9. **Control de cobertura** (`coverage`): caracteres en unidades, descartados, no
   ubicados y separadores (el salto de línea entre dos tramos), que la suma coincide con
   el total y, si no, dónde están los huecos y los solapamientos.
10. **Posibles duplicados** (`duplicates`): vacío (`None`) hasta que la carga lo
    completa (T-026) con una lista de avisos, cada uno con su `detail` en texto.

Al final, el texto lista las unidades con su clave (`unit_list`).
"""

import re

from evaluon.norms.reading import (
    FORMAT_HTML,
    FORMAT_PDF,
    ORIGIN_OCR,
    ORIGIN_PDF_TEXT,
    ORIGIN_WEB,
    PAGE_BLANK,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_NOT_READ,
    PAGE_READ,
)
from evaluon.norms.reading.ocr import DOUBTFUL_FROM, MIN_WORDS

FIRST_WORDS = 8
# Palabras y caracteres con que se muestra el ejemplo de una línea descartada: un script
# puede ser una sola "palabra" de miles de caracteres.
EXAMPLE_WORDS = 12
EXAMPLE_CHARS = 120
ELLIPSIS = "…"
# Cuántas palabras de menor confianza se listan.
LOWEST_WORDS = 20
# Cuántas formas de línea descartada se muestran por motivo en el texto (los datos las
# traen todas).
FORMS_PER_REASON = 5
# Cuántos casos se nombran en un aviso de "Requiere atención"; el resto se cuenta.
ATTENTION_LIMIT = 10

# Nombre de cada tipo de unidad en el texto del informe: singular y plural.
TYPE_NAMES = {
    "anexo": ("anexo", "anexos"),
    "articulo": ("artículo", "artículos"),
    "inciso": ("inciso", "incisos"),
    "considerando": ("considerando", "considerandos"),
    "clausula": ("cláusula", "cláusulas"),
    "punto": ("punto", "puntos"),
    "parrafo": ("párrafo", "párrafos"),
}
# Tipos de unidad que se cuentan por contenedor, en este orden.
CONTAINER_TYPES = ("considerando", "articulo", "clausula")

DISCARD_REASONS = {
    "indice": "Índice",
    "titulo": "Título o capítulo, que pasa a la ruta",
    "caratula": "Carátula (membrete y datos GDE)",
}
# Motivos de las líneas descartadas al armar el texto canónico (`canonical.py`); los de
# la lectura de páginas web ya vienen en español (`web.py`).
DISCARDED_LINE_REASONS = {
    "encabezado_o_pie": "Encabezado o pie de página repetido",
    "forma_conocida": "Forma conocida de encabezado o pie",
}

BODY_CONTAINER = "Cuerpo"

# Nombre de cada regla de partición en el texto del informe (T-024).
RULE_NAMES = {"normas": "normas", "dictamenes": "dictámenes y recomendaciones"}

FORMAT_NAMES = {FORMAT_PDF: "PDF", FORMAT_HTML: "página web"}
# Nombre en palabras de cada herramienta de `tool_versions` (las claves de los datos no
# cambian). Una clave que termina en `_sha256` es una huella, no una versión.
TOOL_NAMES = {
    "pdfplumber": "Lectura de PDF con texto (pdfplumber)",
    "pdfminer.six": "Base de la lectura de PDF (pdfminer.six)",
    "pypdfium2": "Dibujo de páginas de PDF (pypdfium2)",
    "tesseract": "Reconocimiento de texto sobre imagen (Tesseract)",
    "pytesseract": "Conexión con el reconocimiento (pytesseract)",
    "tesseract_spa_sha256": "Huella del idioma español del reconocimiento",
    "beautifulsoup4": "Lectura de páginas web (Beautiful Soup)",
    "lxml": "Análisis de páginas web (lxml)",
}
WEB_PAGE = "la página web"
ORIGIN_NAMES = {
    ORIGIN_PDF_TEXT: "texto del PDF",
    ORIGIN_OCR: "reconocimiento sobre imagen",
    ORIGIN_WEB: "página web",
}

# Estado de una página en el informe (parte 3).
STATE_LEGIBLE = "legible"
STATE_DOUBTFUL = "dudosa"
STATE_ILLEGIBLE = "ilegible"
STATE_ALMOST_EMPTY = "casi_sin_texto"
STATE_BLANK = "en_blanco"
STATE_WITHOUT_TEXT = "sin_texto"
STATE_NAMES = {
    STATE_LEGIBLE: "legible",
    STATE_DOUBTFUL: "dudosa",
    STATE_ILLEGIBLE: "ilegible",
    STATE_ALMOST_EMPTY: "casi sin texto",
    STATE_BLANK: "en blanco",
    STATE_WITHOUT_TEXT: "sin texto",
}
_STATUS_STATES = {
    PAGE_READ: STATE_LEGIBLE,
    PAGE_DOUBTFUL: STATE_DOUBTFUL,
    PAGE_BLANK: STATE_BLANK,
    PAGE_NOT_READ: STATE_WITHOUT_TEXT,
}
# Listas de `page_summary`, en el orden en que se muestran, con su estado.
PAGE_LISTS = (
    ("illegible", STATE_ILLEGIBLE, "Ilegibles"),
    ("almost_empty", STATE_ALMOST_EMPTY, "Casi sin texto"),
    ("doubtful", STATE_DOUBTFUL, "Dudosas"),
    ("without_text", STATE_WITHOUT_TEXT, "Sin texto"),
    ("blank", STATE_BLANK, "En blanco"),
)

_DIGITS = re.compile(r"\d+")


def first_words(text, count=FIRST_WORDS):
    """Las primeras palabras de un tramo, en una sola línea."""
    return " ".join(text.split()[:count])


def shorten(text):
    """El ejemplo de una línea descartada: sus primeras `EXAMPLE_WORDS` palabras y, si
    aun así pasa de `EXAMPLE_CHARS` caracteres, cortado ahí con "…"."""
    words = first_words(text, EXAMPLE_WORDS)
    if len(words) > EXAMPLE_CHARS:
        return words[:EXAMPLE_CHARS] + ELLIPSIS
    return words


# --- Datos --------------------------------------------------------------------------------


def build_report(
    *,
    reading,
    canonical,
    units,
    segments,
    part,
    rules_version,
    containers,
    rule="normas",
    sequence=(),
    uppercase_in_units=(),
    doubtful_headings=(),
    after_last_inciso=(),
    canonical_sha256=None,
    document_info=None,
):
    """Arma el informe en datos. `segments` son los tramos no unitarios: pares
    (`"discarded"` o `"unlocated"`, inicio, fin, motivo). `containers` trae, por cada
    contenedor de artículos, su nombre, su clave y los números que lista su índice
    (`index_numbers`)."""
    text = canonical.text
    discarded, unlocated = [], []
    for kind, start, end, reason in segments:
        page_start, page_end = canonical.pages_at(start, end)
        if kind == "discarded":
            discarded.append(
                {
                    "reason": reason,
                    "char_start": start,
                    "char_end": end,
                    "page_start": page_start,
                    "page_end": page_end,
                    "first_words": first_words(text[start:end]),
                }
            )
        else:
            unlocated.append(
                {
                    "char_start": start,
                    "char_end": end,
                    "page": page_start,
                    "first_words": first_words(text[start:end]),
                }
            )

    by_type = {}
    for unit in units:
        by_type[unit.unit_type] = by_type.get(unit.unit_type, 0) + 1
    by_container = []
    for container in containers:
        parent = container["key"] or None
        articles = [u for u in units if u.unit_type == "articulo" and u.parent_key == parent]
        by_container.append(
            {
                "container": container["name"],
                "key": container["key"],
                "articulo": len(articles),
                "first": articles[0].number if articles else None,
                "last": articles[-1].number if articles else None,
            }
        )

    page_list = _page_list(reading, canonical)
    report = {
        "rules_version": rules_version,
        # Regla elegida por la categoría: `normas` o `dictamenes` (T-024).
        "rule": rule,
        "part": part,
        "document": _document(reading, canonical_sha256, rules_version, rule, part, document_info),
        "pages": {"total": len(reading.pages), "not_read": list(reading.pages_not_read)},
        "page_list": page_list,
        "page_summary": {
            name: [page["number"] for page in page_list if page["state"] == state]
            for name, state, _ in PAGE_LISTS
        },
        "units": {
            "total": len(units),
            "with_text": sum(1 for unit in units if unit.char_end > unit.char_start),
            "by_type": by_type,
            "by_container": by_container,
            "containers": [_container(container, units) for container in containers],
        },
        # Control de secuencia por contenedor: números que faltan (saltos aceptados
        # dentro del margen) y encabezados que no se aceptaron (repeticiones,
        # transcripciones, saltos grandes), con la unidad en la que quedaron. En un
        # dictamen, `heading` es "punto"; si falta, son artículos.
        "sequence": [dict(item) for item in sequence],
        # Párrafos en mayúsculas sin forma reconocida que quedaron dentro de una unidad
        # (decisión del responsable del 2026-10-03): para que los revise quien valida.
        "uppercase_in_units": list(uppercase_in_units),
        # Encabezados de artículo leídos por reconocimiento con el número mal leído o
        # fuera de secuencia, aceptados por la secuencia: requieren atención.
        "doubtful_headings": list(doubtful_headings),
        # Párrafos sin encabezado que siguen al último inciso de una lista: el PDF no
        # distingue sangrías, así que pueden ser del inciso o de la unidad que lo
        # contiene, donde quedaron. Clave del inciso, unidad donde quedaron y cuántos.
        "after_last_inciso": list(after_last_inciso),
        "unit_list": [
            {
                "key": unit.key,
                "unit_type": unit.unit_type,
                "label": unit.label,
                "path": unit.path,
                "page_start": unit.page_start,
                "page_end": unit.page_end,
            }
            for unit in units
        ],
        "unlocated": unlocated,
        "discarded": discarded,
        "discarded_lines": canonical.discarded_lines,
        "discarded_line_list": [
            {"page": line.page, "reason": line.reason, "text": line.text}
            for line in canonical.discarded
        ],
        "discarded_line_forms": _discarded_forms(canonical.discarded),
        "hyphen_joins": [{"page": join.page, "word": join.word} for join in canonical.hyphen_joins],
        "ocr": _ocr(canonical, units),
        "coverage": coverage(text, units, segments),
        "duplicates": None,
    }
    report["attention"] = attention_items(report)
    return report


def _document(reading, canonical_sha256, rules_version, rule, part, document_info):
    info = document_info or {}
    return {
        "file_name": info.get("file_name"),
        "file_sha256": info.get("file_sha256"),
        "read_at": info.get("read_at"),
        "file_format": reading.file_format,
        "pages": len(reading.pages),
        "canonical_sha256": canonical_sha256,
        "tool_versions": dict(reading.tool_versions),
        "rules_version": rules_version,
        "rule": rule,
        "part": part,
    }


def _page_list(reading, canonical):
    chars = {}
    for line in canonical.lines:
        chars[line.page] = chars.get(line.page, 0) + line.end - line.start
    pages = []
    for page in reading.pages:
        confidence = page_confidence(page)
        pages.append(
            {
                "number": page.number,
                "origin": page_origin(page),
                "status": page.status,
                "state": page_state(page, confidence),
                "chars": chars.get(page.number, 0),
                "confidence": confidence,
            }
        )
    return pages


def page_origin(page):
    """Origen del texto de una página: el que informa la lectura o, si no lo informa, el
    de sus líneas (`ocr` si alguna vino de reconocimiento). Vacío si no tiene texto."""
    if page.origin:
        return page.origin
    origins = {line.origin for line in page.lines if not line.discarded}
    if ORIGIN_OCR in origins:
        return ORIGIN_OCR
    return origins.pop() if len(origins) == 1 else None


def page_confidence(page):
    """Confianza promedio de una página reconocida: la que informa la lectura o, si no
    la informa, el promedio de las palabras de sus líneas. Vacía sin reconocimiento."""
    if page.confidence is not None:
        return page.confidence
    values = [word.confidence for line in page.lines for word in line.words]
    return round(sum(values) / len(values), 2) if values else None


def page_state(page, confidence):
    """Estado de una página en el informe. Una página que la lectura da como ilegible es
    "casi sin texto" si se reconoció con confianza suficiente o sin ninguna palabra: el
    reconocimiento solo la da por ilegible por tener menos de `MIN_WORDS` palabras."""
    if page.status == PAGE_ILLEGIBLE:
        if confidence is not None and confidence >= DOUBTFUL_FROM:
            return STATE_ALMOST_EMPTY
        if confidence is None and page.origin == ORIGIN_OCR:
            return STATE_ALMOST_EMPTY
        return STATE_ILLEGIBLE
    return _STATUS_STATES.get(page.status, page.status)


def _container(container, units):
    """Unidades de un contenedor por tipo y la cuenta esperada de artículos frente a la
    reconocida: la esperada sale del índice del contenedor, si tiene, o del último número
    reconocido; la reconocida cuenta los números enteros distintos (un `14 bis` no
    suma)."""
    parent = container["key"] or None
    members = [u for u in units if u.parent_key == parent and u.unit_type in CONTAINER_TYPES]
    by_type = {}
    for unit_type in CONTAINER_TYPES:
        count = sum(1 for u in members if u.unit_type == unit_type)
        if count:
            by_type[unit_type] = count
    articles = [u for u in members if u.unit_type == "articulo"]
    numbers = {int(u.number) for u in articles if u.number.isdigit()}
    index_numbers = container.get("index_numbers") or []
    expected = max([0, *numbers, *index_numbers])
    return {
        "container": container["name"],
        "key": container["key"],
        "by_type": by_type,
        "first": articles[0].number if articles else None,
        "last": articles[-1].number if articles else None,
        "expected": expected,
        "expected_from": "indice" if index_numbers else "numeracion",
        "recognized": len(numbers),
        "missing": [str(n) for n in range(1, expected + 1) if n not in numbers],
    }


def _discarded_forms(lines):
    """Formas de las líneas descartadas, en el orden en que aparecen: motivo, forma (el
    texto con sus números cambiados por `#`), cuántas líneas tiene y la primera como
    ejemplo, con su página."""
    forms = {}
    for line in lines:
        key = (line.reason, _DIGITS.sub("#", line.text.strip()))
        if key not in forms:
            forms[key] = {
                "reason": line.reason,
                "form": shorten(key[1]),
                "count": 0,
                "page": line.page,
                "example": shorten(line.text),
            }
        forms[key]["count"] += 1
    return list(forms.values())


def _ocr(canonical, units):
    """Unidades con texto reconocido sobre imagen y las palabras de menor confianza, con
    su página (REQ-015). Las palabras son las de las líneas de reconocimiento que entran
    en una unidad base, que es el texto que se cita: las del índice, la carátula o un
    tramo sin ubicar no se citan y ya se listan en su parte del informe."""
    ranges = [(u.char_start, u.char_end) for u in units if u.unit_type != "inciso"]
    words = []
    for line in canonical.lines:
        if line.origin != ORIGIN_OCR:
            continue
        if not any(start < line.end and end > line.start for start, end in ranges):
            continue
        for word in line.words:
            words.append({"page": line.page, "word": word.text, "confidence": word.confidence})
    # Orden estable: a igual confianza, el orden del documento.
    lowest = sorted(words, key=lambda word: word["confidence"])[:LOWEST_WORDS]
    return {
        "units": sum(1 for unit in units if unit.text_origin == ORIGIN_OCR),
        "words": len(words),
        "lowest_words": lowest,
    }


def coverage(text, units, segments):
    """Control de cobertura: cada carácter del texto canónico está en una unidad base, en
    un tramo descartado, en un tramo no ubicado o es el salto de línea que separa dos
    tramos. La suma tiene que dar el total, sin solapamientos ni huecos; si no, `problems`
    dice dónde está cada hueco (`hole`) y cada solapamiento (`overlap`)."""
    # Los incisos son recortes de su artículo: cada carácter se cuenta en su unidad base.
    ranges = [("units", u.char_start, u.char_end) for u in units if u.unit_type != "inciso"]
    ranges += [(kind, start, end) for kind, start, end, _ in segments]
    ranges = sorted((r for r in ranges if r[2] > r[1]), key=lambda r: r[1])

    totals = {"units": 0, "discarded": 0, "unlocated": 0, "separators": 0}
    problems = []
    position = 0
    for index, (kind, start, end) in enumerate(ranges):
        gap = text[position:start]
        if start < position:
            # Dos tramos se solapan.
            problems.append({"kind": "overlap", "char_start": start, "char_end": min(position, end)})
        elif index and gap == "\n":
            totals["separators"] += 1
        elif gap:
            # Texto que no quedó en ningún tramo.
            problems.append({"kind": "hole", "char_start": position, "char_end": start})
        totals[kind] += end - start
        position = max(position, end)
    if position < len(text):
        problems.append({"kind": "hole", "char_start": position, "char_end": len(text)})

    matches = not problems and sum(totals.values()) == len(text)
    return {"total": len(text), **totals, "matches": matches, "problems": problems}


# --- Requiere atención ----------------------------------------------------------------


def attention_items(report):
    """Los avisos de "Requiere atención", a partir de las demás partes del informe, de lo
    más grave a lo que solo pide comparar con el original. Cada aviso es un diccionario
    con su clase (`kind`), su texto en lenguaje llano (`text`) y, según la clase, las
    páginas o el contenedor a los que se refiere."""
    items = []

    def add(kind, text, **detail):
        items.append({"kind": kind, "text": text, **detail})

    cover = report["coverage"]
    if not cover["matches"]:
        places = [
            f"{'un hueco' if p['kind'] == 'hole' else 'un solapamiento'} en los caracteres "
            f"{p['char_start']} a {p['char_end']}"
            for p in cover.get("problems", [])
        ]
        where = f" ({_limited(places)})" if places else ""
        add(
            "coverage",
            "El control de cobertura no cierra: unidades, descartado, no ubicado y "
            f"separadores no suman el total leído{where}. Es una falla de la partición: "
            "no valide este informe.",
        )

    if report["units"]["with_text"] == 0:
        add(
            "empty_document",
            "El documento no produjo ninguna unidad con texto. No valide una norma vacía: "
            "revise el original y su lectura.",
        )

    _page_attention(report, add)

    # En una página web toda ubicación es la misma página: no se repite en cada caso.
    web = _is_web(report)

    def located(text, page):
        return text if web else f"{text} ({_page_name(page)})"

    # La cuenta esperada y los saltos de la secuencia hablan de los mismos números que
    # faltan: un solo aviso por contenedor (los saltos son parte de lo que falta).
    counted = set()
    for container in report["units"]["containers"]:
        if not container["missing"]:
            continue
        counted.add(container["key"])
        source = "el índice" if container["expected_from"] == "indice" else "la numeración"
        missing = container["missing"]
        add(
            "expected_count",
            f"{container['container']}: se {_verb(container['expected'], 'esperaba', 'esperaban')} "
            f"{_plural(container['expected'], 'artículo', 'artículos')} según {source} y se "
            f"{_verb(container['recognized'], 'reconoció', 'reconocieron')} "
            f"{container['recognized']}; {_missing(missing)}. Compare con el original si "
            f"{_verb(len(missing), 'falta', 'faltan')} en el documento o si no se "
            f"{_verb(len(missing), 'reconoció', 'reconocieron')}.",
            container=container["container"],
            missing=list(missing),
        )

    gaps, not_accepted = [], []
    for item in report["sequence"]:
        noun = item.get("heading", "artículo")
        if item["gaps"] and item["key"] not in counted:
            gaps.append(f"{item['container']}: {_missing(item['gaps'], noun)}")
        for heading in item["not_accepted"]:
            inside = f", quedó dentro de {heading['inside']}" if heading["inside"] else ""
            where = "" if web else _page_name(heading["page"])
            detail = f"{where}{inside}".lstrip(", ")
            not_accepted.append(f"{noun} {heading['number']}" + (f" ({detail})" if detail else ""))
    if gaps:
        add(
            "sequence_gaps",
            "La numeración salta: " + "; ".join(gaps) + ". Compare con el original si "
            "faltan en el documento o si no se reconocieron.",
        )
    if not_accepted:
        add(
            "not_accepted",
            "Encabezados fuera de secuencia (repetidos, fuera de orden o transcriptos), que "
            f"no abrieron una unidad: {_limited(not_accepted)}. Revise que no sean una "
            "unidad perdida.",
        )

    doubtful = report["doubtful_headings"]
    if doubtful:
        add(
            "doubtful_headings",
            "Encabezados leídos por reconocimiento sobre imagen con el número dudoso y "
            "aceptados por la secuencia: "
            + _limited([f"{located(d['key'], d['page'])}: {d['label']}" for d in doubtful])
            + ". Compárelos con el original.",
        )

    unlocated = report["unlocated"]
    if unlocated:
        cases = [
            u["first_words"] if web else f"{_page_name(u['page'])}: {u['first_words']}"
            for u in unlocated
        ]
        add(
            "unlocated",
            f"{_plural(len(unlocated), 'tramo de texto', 'tramos de texto')} no "
            f"{_verb(len(unlocated), 'quedó', 'quedaron')} en ninguna unidad: "
            + _limited(cases, separator="; ")
            + ". Revise que no sea texto que deba citarse.",
        )

    upper = report["uppercase_in_units"]
    if upper:
        add(
            "uppercase_in_units",
            "Párrafos en mayúsculas que quedaron dentro de una unidad y pueden ser un "
            "encabezado que la partición no reconoce: "
            + _limited([located(u["key"], u["page"]) for u in upper])
            + ".",
        )

    after = report["after_last_inciso"]
    if after:
        add(
            "after_last_inciso",
            f"{_plural(len(after), 'lista', 'listas')} de incisos "
            f"{_verb(len(after), 'tiene', 'tienen')} párrafos después del último inciso, "
            "que quedaron en la unidad que contiene la lista y pueden ser del último inciso: "
            + _limited([located(a["key"], a["page"]) for a in after])
            + ".",
        )

    lines = report["discarded_lines"]
    if lines:
        add(
            "discarded_lines",
            f"{_plural(lines, 'línea descartada', 'líneas descartadas')} por la lectura o "
            "como encabezado o pie de página: verifique en los ejemplos de \"Descartado\" "
            "que ninguna sea texto del documento.",
        )

    ocr = report["ocr"]
    if ocr["units"]:
        add(
            "ocr",
            f"{_plural(ocr['units'], 'unidad tiene', 'unidades tienen')} texto reconocido "
            "sobre imagen, que puede diferir del impreso: compare con el original las "
            "palabras de menor confianza (\"Reconocimiento sobre imagen\").",
        )

    duplicates = report.get("duplicates")
    if duplicates:
        add(
            "duplicates",
            f"{_plural(len(duplicates), 'posible duplicado', 'posibles duplicados')}: "
            "revise \"Posibles duplicados\" antes de validar.",
        )
    return items


def _page_attention(report, add):
    pages = {page["number"]: page for page in report["page_list"]}
    summary = report["page_summary"]

    def named(numbers, with_confidence=False):
        names = []
        for number in numbers:
            name = _page_name(number)
            confidence = pages.get(number, {}).get("confidence")
            if with_confidence and confidence is not None:
                name += f" (confianza promedio {_number(confidence)})"
            names.append(name)
        return _limited(names)

    if summary["illegible"]:
        add(
            "illegible_pages",
            "Páginas ilegibles, reconocidas con confianza baja, que no aportan texto a las "
            f"unidades: {named(summary['illegible'], True)}. Compárelas con el original: "
            "si tienen texto, falta en las unidades.",
            pages=list(summary["illegible"]),
        )
    if summary["almost_empty"]:
        add(
            "almost_empty_pages",
            f"Páginas casi sin texto, con menos de {MIN_WORDS} palabras reconocidas, que no "
            f"aportan texto a las unidades: {named(summary['almost_empty'], True)}. Pueden "
            "ser una carátula o una página casi vacía: compárelas con el original.",
            pages=list(summary["almost_empty"]),
        )
    if summary["doubtful"]:
        add(
            "doubtful_pages",
            "Páginas dudosas, reconocidas con confianza media, cuyo texto entra en las "
            f"unidades: {named(summary['doubtful'], True)}. Compare sus palabras de menor "
            "confianza con el original.",
            pages=list(summary["doubtful"]),
        )
    if summary["without_text"]:
        add(
            "pages_without_text",
            f"Páginas sin texto: {named(summary['without_text'])}. No tienen capa de texto "
            "y no se reconocieron sobre imagen: pueden estar en blanco o traer solo una "
            "imagen o una firma digital. Compárelas con el original.",
            pages=list(summary["without_text"]),
        )
    if summary["blank"]:
        add(
            "blank_pages",
            f"Páginas en blanco, que no cuentan como ilegibles: {named(summary['blank'])}. "
            "Confirme en el original que no tienen texto.",
            pages=list(summary["blank"]),
        )


# --- Texto ------------------------------------------------------------------------------


def _plural(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def _verb(count, singular, plural):
    return singular if count == 1 else plural


def _number(value):
    """Un número con coma decimal y sin ceros de más: 60, 41,5."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _join(parts):
    """`a`, `a y b`, `a, b y c`."""
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def _limited(parts, separator=", "):
    """Los primeros `ATTENTION_LIMIT` casos y cuántos más hay."""
    shown = separator.join(parts[:ATTENTION_LIMIT])
    rest = len(parts) - ATTENTION_LIMIT
    return shown + (f" y {rest} más" if rest > 0 else "")


def _ranges(values):
    """Números en tramos: `3, 5 a 9, 12`. Si alguno no es entero, la lista tal cual."""
    if not all(str(value).isdigit() for value in values):
        return ", ".join(str(value) for value in values)
    numbers = sorted(int(value) for value in values)
    parts, start = [], None
    for index, number in enumerate(numbers):
        if start is None:
            start = number
        if index + 1 == len(numbers) or numbers[index + 1] != number + 1:
            parts.append(str(start) if start == number else f"{start} a {number}")
            start = None
    return ", ".join(parts)


def _missing(values, noun=None):
    """`falta el número 4` o `faltan los números 8 a 99`; con el nombre de la unidad, si
    se da: `falta el punto 3`, `faltan los artículos 3, 5`."""
    if len(values) == 1:
        return f"falta el {noun or 'número'} {values[0]}"
    return f"faltan los {noun + 's' if noun else 'números'} {_ranges(values)}"


def _is_web(report):
    return report["document"]["file_format"] == FORMAT_HTML


def _page_name(number):
    """`página 3`; la página web, que no tiene número, por su nombre."""
    return WEB_PAGE if number is None else f"página {number}"


def _pages(start, end, web=False):
    """`página 3`, `páginas 3 a 5`; sin página, "la página web" en un documento web y
    "sin página" en un tramo vacío de un PDF."""
    if start is None:
        return WEB_PAGE if web else "sin página"
    if start == end:
        return f"página {start}"
    return f"páginas {start} a {end}"


def _discarded_line_reason(reason):
    name = DISCARDED_LINE_REASONS.get(reason, reason)
    return name[:1].upper() + name[1:]


def report_text(report):
    """El informe en texto legible, en español llano, armado solo con los datos."""
    sections = [
        ["Informe de lectura"],
        _attention_text(report),
        _document_text(report),
        _pages_text(report),
        _units_text(report),
        _unlocated_text(report),
        _discarded_text(report),
        _joins_text(report),
        _ocr_text(report),
        _coverage_text(report),
        _duplicates_text(report),
        _unit_list_text(report),
    ]
    return "\n\n".join("\n".join(lines) for lines in sections) + "\n"


def _attention_text(report):
    items = report["attention"]
    if not items:
        return ["Requiere atención: nada."]
    return ["Requiere atención:"] + [f"  - {item['text']}" for item in items]


def _document_text(report):
    document = report["document"]
    lines = ["Documento:"]
    if document["file_name"]:
        lines.append(f"  Archivo: {document['file_name']}.")
    if document["file_sha256"]:
        lines.append(f"  Huella del archivo: {document['file_sha256']}.")
    if document["read_at"]:
        lines.append(f"  Fecha de lectura: {document['read_at']}.")
    file_format = FORMAT_NAMES.get(document["file_format"], document["file_format"])
    lines.append(f"  Formato: {file_format}. Cantidad de páginas: {document['pages']}.")
    tools = document["tool_versions"]
    lines.append("  Herramientas:" if tools else "  Herramientas: sin datos.")
    for tool, version in tools.items():
        name = TOOL_NAMES.get(tool, tool)
        if tool.endswith("_sha256"):
            lines.append(f"    - {name}: {version}.")
        else:
            lines.append(f"    - {name}: versión {version}.")
    rule = RULE_NAMES.get(report["rule"], report["rule"])
    lines.append(
        f"  Reglas para dividir el texto: versión {report['rules_version']} ({rule}). "
        f"Parte del documento: {report['part']}."
    )
    if document["canonical_sha256"]:
        lines.append(f"  Huella del texto extraído: {document['canonical_sha256']}.")
    return lines


def _pages_text(report):
    # Sin "páginas no leídas": junta las ilegibles con las que no tienen texto, y quien
    # valida entendería que estas tampoco se pudieron leer. Las cinco listas de estados
    # de abajo dan el dato separado (`pages.not_read` sigue en los datos).
    lines = [f"Páginas: {report['pages']['total']}."]
    for page in report["page_list"]:
        name = "La página web" if page["number"] is None else f"Página {page['number']}"
        parts = []
        # La página web no repite su origen: "La página web: legible".
        if page["origin"] and not (page["number"] is None and page["origin"] == ORIGIN_WEB):
            parts.append(ORIGIN_NAMES.get(page["origin"], page["origin"]))
        parts.append(STATE_NAMES.get(page["state"], page["state"]))
        parts.append(_plural(page["chars"], "carácter", "caracteres"))
        if page["confidence"] is not None:
            parts.append(f"confianza promedio {_number(page['confidence'])}")
        lines.append(f"  {name}: {', '.join(parts)}.")
    summary = report["page_summary"]
    lists = []
    for name, _, title in PAGE_LISTS:
        numbers = [
            WEB_PAGE if number is None else str(number) for number in summary[name]
        ]
        lists.append(f"{title}: {', '.join(numbers) or 'ninguna'}.")
    lines.append("  " + " ".join(lists))
    return lines


def _units_text(report):
    units = report["units"]
    web = _is_web(report)
    kinds = ", ".join(
        _plural(count, *TYPE_NAMES.get(unit_type, (unit_type, unit_type)))
        for unit_type, count in units["by_type"].items()
    )
    lines = [f"Unidades reconocidas: {units['total']}" + (f" ({kinds})." if kinds else ".")]
    for container in units["containers"]:
        lines.extend(_container_text(container))
    for item in report["sequence"]:
        if item["gaps"]:
            lines.append(f"  {item['container']}: {_missing(item['gaps'])}.")
        for heading in item["not_accepted"]:
            inside = f", quedó dentro de {heading['inside']}" if heading["inside"] else ""
            where = _pages(heading["page"], heading["page"], web)
            lines.append(
                f"  {item['container']}: encabezado del {item.get('heading', 'artículo')} "
                f"{heading['number']} fuera de secuencia, {where}{inside}."
            )

    doubtful = report["doubtful_headings"]
    if doubtful:
        lines.append(
            "Encabezados dudosos leídos por reconocimiento sobre imagen y aceptados por la "
            f"secuencia: {len(doubtful)}."
        )
        for item in doubtful:
            lines.append(f"  - {item['key']}, {_pages(item['page'], item['page'], web)}: {item['label']}")

    upper = report["uppercase_in_units"]
    if upper:
        lines.append(f"Párrafos en mayúsculas dentro de una unidad, para revisar: {len(upper)}.")
        for item in upper:
            lines.append(
                f"  - {item['key']}, {_pages(item['page'], item['page'], web)}: {item['first_words']}"
            )

    after = report["after_last_inciso"]
    if after:
        lines.append(
            "Párrafos después del último inciso de una lista, que pueden ser del inciso y "
            f"quedaron en la unidad que lo contiene, para revisar: {len(after)}."
        )
        for item in after:
            stayed = "párrafo quedó" if item["paragraphs"] == 1 else "párrafos quedaron"
            lines.append(
                f"  - {item['key']}, {_pages(item['page'], item['page'], web)}: "
                f"{item['paragraphs']} {stayed} en {item['inside']}"
            )
    return lines


def _container_text(container):
    name, by_type = container["container"], container["by_type"]
    articles = by_type.get("articulo", 0)
    parts = [_plural(count, *TYPE_NAMES[unit_type]) for unit_type, count in by_type.items()]
    span = f"del {container['first']} al {container['last']}"
    if not parts:
        lines = [f"  {name}: ningún artículo."]
    elif articles and len(parts) == 1:
        lines = [f"  {name}: {parts[0]}, {span}."]
    elif articles:
        lines = [f"  {name}: {_join(parts)}; artículos {span}."]
    else:
        lines = [f"  {name}: {_join(parts)}; ningún artículo."]
    expected = container["expected"]
    if expected:
        source = "el índice" if container["expected_from"] == "indice" else "la numeración"
        line = (
            f"    Según {source} se {_verb(expected, 'esperaba', 'esperaban')} "
            f"{_plural(expected, 'artículo', 'artículos')}; se "
            f"{_verb(container['recognized'], 'reconoció', 'reconocieron')} "
            f"{container['recognized']}."
        )
        if container["missing"]:
            line += f" {_missing(container['missing']).capitalize()}."
        lines.append(line)
    return lines


def _unlocated_text(report):
    unlocated = report["unlocated"]
    lines = [f"No ubicado: {_plural(len(unlocated), 'tramo', 'tramos')}."]
    for item in unlocated:
        where = _pages(item["page"], item["page"], _is_web(report)).capitalize()
        lines.append(f"  - {where}: {item['first_words']}")
    return lines


def _discarded_text(report):
    discarded = report["discarded"]
    lines = [f"Descartado: {_plural(len(discarded), 'tramo', 'tramos')}."]
    for item in discarded:
        reason = DISCARD_REASONS.get(item["reason"], item["reason"])
        lines.append(
            f"  - {reason}, {_pages(item['page_start'], item['page_end'], _is_web(report))}: "
            f"{item['first_words']}"
        )
    lines.append(f"Líneas descartadas en la lectura: {report['discarded_lines']}.")
    by_reason = {}
    for form in report["discarded_line_forms"]:
        by_reason.setdefault(form["reason"], []).append(form)
    for reason, forms in by_reason.items():
        name = _discarded_line_reason(reason)
        for form in forms[:FORMS_PER_REASON]:
            where = WEB_PAGE if form["page"] is None else f"la página {form['page']}"
            lines.append(
                f"  - {name}, {_plural(form['count'], 'línea', 'líneas')}, por ejemplo en "
                f"{where}: {form['example']}"
            )
        rest = len(forms) - FORMS_PER_REASON
        if rest > 0:
            lines.append(f"  - {name}: {_plural(rest, 'forma más', 'formas más')}.")
    return lines


def _joins_text(report):
    joins = report["hyphen_joins"]
    lines = [f"Uniones de palabras cortadas: {len(joins)}."]
    for join in joins:
        lines.append(f"  - {_pages(join['page'], join['page'], _is_web(report))}: {join['word']}")
    return lines


def _ocr_text(report):
    ocr = report["ocr"]
    if not ocr["units"]:
        return ["Reconocimiento sobre imagen: ninguna unidad."]
    lines = [
        f"Reconocimiento sobre imagen: {_plural(ocr['units'], 'unidad', 'unidades')} de "
        f"{report['units']['total']} {_verb(ocr['units'], 'tiene', 'tienen')} texto "
        "reconocido sobre imagen."
    ]
    if ocr["lowest_words"]:
        lines.append("  Palabras de menor confianza, para comparar con el original:")
        for word in ocr["lowest_words"]:
            lines.append(
                f"  - {_page_name(word['page'])}: {word['word']} "
                f"(confianza {_number(word['confidence'])})"
            )
    return lines


def _coverage_text(report):
    cover = report["coverage"]
    verdict = "la suma coincide con el total" if cover["matches"] else "la suma NO coincide con el total"
    lines = [
        f"Cobertura: {cover['total']} caracteres: {cover['units']} en unidades, "
        f"{cover['discarded']} descartados, {cover['unlocated']} no ubicados y "
        f"{cover['separators']} saltos de línea entre tramos; {verdict}."
    ]
    for problem in cover.get("problems", []):
        kind = "Hueco" if problem["kind"] == "hole" else "Solapamiento"
        lines.append(f"  - {kind} en los caracteres {problem['char_start']} a {problem['char_end']}.")
    return lines


def _duplicates_text(report):
    duplicates = report.get("duplicates")
    if duplicates is None:
        return ["Posibles duplicados: sin comprobar en la partición; los comprueba la carga del documento."]
    if not duplicates:
        return ["Posibles duplicados: ninguno."]
    return [f"Posibles duplicados: {len(duplicates)}."] + [
        f"  - {item['detail']}" for item in duplicates
    ]


def _unit_list_text(report):
    web = _is_web(report)
    lines = ["Unidades:"]
    for item in report["unit_list"]:
        lines.append(
            f"  {item['key']} · {item['path']} · {item['label']} · "
            f"{_pages(item['page_start'], item['page_end'], web)}"
        )
    return lines
