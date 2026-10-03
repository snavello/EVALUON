"""Tabla de encabezados de las normas (ADR-0004, "Cómo se parte"; plan 001, "Texto
normativo sin número de artículo"; T-023).

Cada párrafo del texto canónico se clasifica por su comienzo. Un encabezado solo se
reconoce al comienzo de un párrafo; la partición (`partition.py`) decide después, con el
contexto, si se acepta (control de secuencia, índice, zona del documento).

| Tipo | Formas |
|---|---|
| Artículo | `ARTÍCULO 1°.-`, `ARTÍCULO 1º.-`, `ARTÍCULO 10.-`, `ARTICULO 1° —`, `ARTICULO 1.- OBJETO`, `ARTICULO 12.—`, `ARTICULO 11. —`, `ARTICULO 13 —`, `ARTICULO 27.`, `Art. 2º.-`, `Artículo 14 bis.-`; con o sin tilde, con `°`, `º`, `o` o sin signo. Siempre con un separador después del número, para no tomar "Artículo 2° de la Ley ...". Entre comillas no es un encabezado (artículo transcripto) |
| Artículo leído por reconocimiento | Solo en párrafos de origen `ocr`: en lugar de `°` o `º`, hasta tres de `* % ” " ' ? o O` (por ejemplo `9”%`) o nada, un espacio antes del `.-`, y un número que puede traer signos mal leídos (`$0`) |
| Inciso | `a)`, `ñ)`, `1)`, `1.`, `Inciso 1)`, `inc. a)`. No: `1.1.`, `1.000` |
| Título, capítulo, sección | `TÍTULO II`, `CAPÍTULO VIII`, `SECCIÓN 1ª`, en un párrafo en mayúsculas |
| Cláusula (texto sin número) | Lista `CLAUSE_FORMS`: `CLÁUSULA TRANSITORIA`, con o sin tilde y con o sin epígrafe, en un párrafo en mayúsculas |
| Anexo | `ANEXO`, `ANEXO I`, `ANEXO A`, `ANEXO (artículo 1°)`, con o sin título a continuación, en un párrafo en mayúsculas o que es solo el encabezado (con su referencia entre paréntesis, si la tiene). No: "ANEXO I forma parte integrante de la presente", que es prosa |
| Visto y considerandos | `VISTO`, `CONSIDERANDO:`, párrafos que empiezan con `Que` |
| Fórmula | `Por ello` |
| Firma | `Digitally signed by`, `Firmado digitalmente por`, `Date: 2022.11.29` (firma digital GDE) |
| Índice | `ÍNDICE`, `ÍNDICE:` |
| Mayúsculas | Un párrafo en mayúsculas que no tiene ninguna forma de la tabla: no corta (decisión del responsable del 2026-10-03) |
"""

import re
from dataclasses import dataclass

ARTICLE = "article"
INCISO = "inciso"
TITLE = "title"
CLAUSE = "clause"
ANNEX = "annex"
VISTO = "visto"
CONSIDERANDO_HEADING = "considerando_heading"
QUE = "que"
FORMULA = "formula"
SIGNATURE = "signature"
INDEX = "index"
UPPER = "upper"
TEXT = "text"

# Artículo. El separador es obligatorio: `.-`, `-`, `—`, `–` (con o sin punto y
# espacios antes) o un punto seguido de espacio o del fin del párrafo.
ARTICLE_HEADING = re.compile(
    r"(?:ART[IÍ]CULO|Art[ií]culo|ART\.|Art\.)\s*(?P<number>\d+)\s*(?:[°º]|o\b)?"
    r"(?:\s*(?P<suffix>bis|ter|quater|BIS|TER|QUATER)\b)?"
    r"(?:\s*\.?\s*[-—–]+|\.(?=\s|$))"
)

# Artículo leído por reconocimiento sobre imagen (Tesseract no reconoce `°` ni `º` y a
# veces lee el 8 como `$`). Solo se aplica a párrafos de origen `ocr`.
OCR_ARTICLE_HEADING = re.compile(
    r"(?:ART[IÍ]CULO|Art[ií]culo)\s*(?P<number>[0-9$§]{1,4})\s*[°º*%”\"'oO?]{0,3}"
    r"(?:\s*(?P<suffix>bis|BIS)\b)?"
    r"\s*\.\s?-"
)

INCISO_HEADING = re.compile(
    r"(?P<marker>(?:(?:Inciso|INCISO|inciso|Inc\.|inc\.)\s*)?"
    r"(?:(?P<letter>[a-zñ])\)|(?P<paren>\d{1,2})\)|(?P<dot>\d{1,2})\.))(?=\s)"
)

TITLE_HEADING = re.compile(
    r"(?P<kind>T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N)\s+(?P<number>[IVXLCDM]+|\d+[ªº°]?)(?=$|[\s\-—–.:])"
)
# Nivel y nombre de cada encabezado de título en la ruta.
TITLE_LEVELS = {"T": (0, "Título"), "C": (1, "Capítulo"), "S": (2, "Sección")}

# Lista de nombres de texto normativo sin número de artículo. Cada forma nueva se suma
# acá, con su fila en la tabla de encabezados de los tests.
CLAUSE_FORMS = [re.compile(r"CL[AÁ]USULA TRANSITORIA(?=$|\s)")]

ANNEX_HEADING = re.compile(
    r"ANEXO(?:\s+(?P<designator>[IVXLCDM]+|\d+|[A-Z]))?(?=$|[\s\-—–:.(])"
)
# Lo que puede seguir al encabezado de anexo en un párrafo que no está en mayúsculas:
# nada, o una referencia entre paréntesis ("ANEXO (artículo 1°)").
_ANNEX_ONLY_REST = re.compile(r"\s*(?:\([^()]*\)\s*)?")

VISTO_HEADING = re.compile(r"VISTO\b")
CONSIDERANDO = re.compile(r"(?:Y\s+)?CONSIDERANDO\s*:?\s*")
QUE_PARAGRAPH = re.compile(r"Que\s")
FORMULA_PARAGRAPH = re.compile(r"Por ello\b")
SIGNATURE_FORMS = re.compile(
    r"Digitally signed by|Firmado digitalmente por|Date:\s*\d{4}\.\d{2}\.\d{2}"
)
INDEX_MARKER = re.compile(r"[IÍ]NDICE:?")

# Epígrafe de un artículo: lo que sigue al encabezado, en mayúsculas, hasta el punto.
_EPIGRAPH = re.compile(r"\s*(?P<epigraph>[^.]*?)\.(?=\s|$)")
_LOWERCASE = re.compile(r"[a-záéíóúüñç]")
_LETTER = re.compile(r"[^\W\d_]")


@dataclass(frozen=True)
class Heading:
    """Clase de un párrafo según su comienzo.

    - `number`: número normalizado (artículo `14 bis`, inciso `a`, título `II`, anexo
      `I`); vacío si no tiene.
    - `article_number`: el número entero de un artículo; vacío si no se pudo leer (solo
      en párrafos de reconocimiento).
    - `label`: etiqueta como figura en el documento (artículo e inciso).
    - `name`: nombre en la ruta (título, cláusula, anexo).
    - `style`: forma de un inciso (`letter`, `paren` o `dot`), para su secuencia.
    - `heading_only`: un artículo sin texto propio después del encabezado.
    - `tolerant`: un artículo reconocido con la forma tolerante de reconocimiento.
    """

    kind: str
    number: str = ""
    article_number: int | None = None
    suffix: str = ""
    label: str = ""
    name: str = ""
    style: str = ""
    level: int = 0
    heading_only: bool = False
    tolerant: bool = False
    raw: str = ""


def is_uppercase(text):
    """Un párrafo en mayúsculas: sin minúsculas y con al menos tres letras."""
    return not _LOWERCASE.search(text) and len(_LETTER.findall(text)) >= 3


def classify_heading(text, ocr=False):
    """Clase de un párrafo. `ocr` habilita la forma tolerante de artículo."""
    article = _article(text, ARTICLE_HEADING)
    if article:
        return article
    if ocr:
        article = _article(text, OCR_ARTICLE_HEADING, tolerant=True)
        if article:
            return article
    if INDEX_MARKER.fullmatch(text):
        return Heading(INDEX)
    uppercase = is_uppercase(text)
    annex = ANNEX_HEADING.match(text)
    # Como el título y la cláusula: un párrafo en mayúsculas, o que es solo el
    # encabezado; un párrafo en prosa que empieza con "ANEXO I" no abre un anexo.
    if annex and (uppercase or _ANNEX_ONLY_REST.fullmatch(text, annex.end())):
        designator = annex.group("designator") or ""
        return Heading(ANNEX, number=designator, name="Anexo" + (f" {designator}" if designator else ""))
    if uppercase:
        title = TITLE_HEADING.match(text)
        if title:
            level, name = TITLE_LEVELS[title.group("kind")[0]]
            number = title.group("number")
            return Heading(TITLE, number=number, name=f"{name} {number}", level=level)
        for form in CLAUSE_FORMS:
            clause = form.match(text)
            if clause:
                return Heading(CLAUSE, name=clause.group(0).capitalize(), label=text)
    if VISTO_HEADING.match(text):
        return Heading(VISTO)
    if CONSIDERANDO.fullmatch(text):
        return Heading(CONSIDERANDO_HEADING)
    if QUE_PARAGRAPH.match(text):
        return Heading(QUE)
    if FORMULA_PARAGRAPH.match(text):
        return Heading(FORMULA)
    if SIGNATURE_FORMS.match(text):
        return Heading(SIGNATURE)
    inciso = INCISO_HEADING.match(text)
    if inciso:
        for style in ("letter", "paren", "dot"):
            if inciso.group(style):
                return Heading(INCISO, number=inciso.group(style), label=inciso.group("marker"), style=style)
    if uppercase and _LETTER.match(text):
        return Heading(UPPER)
    return Heading(TEXT)


def _article(text, pattern, tolerant=False):
    heading = pattern.match(text)
    if not heading:
        return None
    raw = heading.group("number")
    number = int(raw) if raw.isdigit() else None
    suffix = (heading.group("suffix") or "").lower()
    rest = text[heading.end() :]
    return Heading(
        ARTICLE,
        number=(str(number) if number is not None else raw) + (f" {suffix}" if suffix else ""),
        article_number=number,
        suffix=suffix,
        label=_article_label(text, heading.end()),
        heading_only=not _LOWERCASE.search(rest),
        tolerant=tolerant,
        raw=raw,
    )


def _article_label(text, end):
    """El encabezado y su epígrafe, sin el punto que cierra el epígrafe ni el texto que
    sigue: `ARTÍCULO 1°.- OBJETO`."""
    epigraph = _EPIGRAPH.match(text, end)
    if epigraph:
        words = epigraph.group("epigraph")
        if words.strip() and _LETTER.search(words) and not _LOWERCASE.search(words):
            end = epigraph.end("epigraph")
    elif _LETTER.search(text[end:]) and not _LOWERCASE.search(text[end:]):
        # Epígrafe solo, sin punto final (las entradas del índice).
        end = len(text)
    return text[:end].rstrip()


def starts_article(text, ocr=False):
    """Si un renglón empieza con un encabezado de artículo (para el texto canónico)."""
    return bool(ARTICLE_HEADING.match(text) or (ocr and OCR_ARTICLE_HEADING.match(text)))


def starts_structural_heading(text):
    """Si un renglón es un encabezado de título o de cláusula: en mayúsculas y con una
    forma de la tabla (para el texto canónico)."""
    if not is_uppercase(text):
        return False
    return bool(TITLE_HEADING.match(text) or any(form.match(text) for form in CLAUSE_FORMS))


def starts_inciso(text):
    return bool(INCISO_HEADING.match(text))
