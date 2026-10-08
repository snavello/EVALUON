"""Datos de una norma propuestos desde su encabezado y su pie (T-213; REQ-094, ADR-0051).

Entrada: la lectura de un documento (`norms/reading/`). Salida: por cada dato de
`loading.FIELDS`, lo que las reglas reconocen con su evidencia (página y texto de donde
salió) o `None` si no lo reconocen. Solo reglas sobre el texto, en CPU y sin los servicios
de IA: la misma lectura da siempre la misma propuesta (P6). Un dato dudoso no se propone:
queda sin reconocer para que la persona lo complete (mejor un dato que falta que uno
equivocado).

Reglas:

- **Tipo, número y año.** Una línea del encabezado que empieza con el tipo ("Disposición
  N° 297/2003", "Decreto 1030/2016", "Dictamen jurídico N° 99/2026"). No se buscan en
  cualquier parte del texto: una referencia a otra norma ("Referencia: ... Disposición N°
  297/03") no es la norma que se sube.
- **Organismo emisor.** Una línea anterior a la del tipo que nombra a AFIP o a ARCA (con
  sigla o nombre largo, ADR-0010) o al Poder Ejecutivo Nacional.
- **Título.** La línea que sigue a la del tipo, si no es un código ni la fecha; si no, el
  texto entre comillas de "Aprobar el «...»" del articulado; si no, las líneas en
  mayúsculas que siguen a "ANEXO (artículo N°)" en un anexo.
- **Nombre de cita.** Tipo, organismo y "número/año" ("Disposición AFIP 247/2022").
- **Categoría.** Dictamen jurídico: dictamen legal; la norma que aprueba el régimen
  general de contrataciones: régimen específico; decreto o ley: marco nacional; otra
  norma de AFIP o ARCA: otra normativa aplicable.
- **Fecha de publicación.** La del pie del Boletín Oficial ("e. 30/11/2022 N° 97811/22 v.
  30/11/2022"). La fecha del acto ("Ciudad de Buenos Aires, 28/11/2022") no lo es.
- **Fecha de vigencia.** Solo si la norma la dice con fecha ("entrará en vigencia el
  1/1/2023"). Si la deja en plazos ("a los veinte días hábiles desde su publicación") no se
  calcula: el sistema no calcula la vigencia (plan 001).
- **Fuente.** El archivo subido.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from evaluon.norms.models import Category
from evaluon.norms.services.loading import mentions_issuer

# Cuántas líneas del comienzo del documento forman el encabezado.
HEADER_LINES = 40
# Largo máximo del texto de la evidencia que se guarda.
EVIDENCE_LENGTH = 400

_TYPES = {
    "disposicion": "Disposición",
    "resolucion general": "Resolución General",
    "resolucion": "Resolución",
    "decreto": "Decreto",
    "circular": "Circular",
    "nota externa": "Nota Externa",
    "dictamen": "Dictamen",
}

_TYPE_LINE = re.compile(
    r"^(?P<type>Disposici[oó]n|Resoluci[oó]n General|Resoluci[oó]n|Decreto|Circular|"
    r"Nota Externa|Dictamen)(?:\s+(?!N[°º.o]?\s*\d)[^\W\d_]+){0,2}?\s*"
    r"(?:N[°º.o]*\s*)?(?P<number>\d[\d.]*)\s*/\s*(?P<year>\d{4}|\d{2})(?!\d)",
    re.IGNORECASE,
)
_PUBLICATION_FOOTER = re.compile(
    r"^e\.\s*(?P<day>\d{1,2})/(?P<month>\d{1,2})(?:/(?P<year>\d{2,4}))?\s+"
    r"N[°º]?\s*[\d./]+\s+v\.\s*\d{1,2}/\d{1,2}/(?P<end_year>\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    name: number for number, name in enumerate(
        ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"), start=1)
}
_DATE = r"(?P<date>\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4})"
_EFFECTIVE = re.compile(
    r"(?:entrar[áa]\s+en\s+vigencia|comenzar[áa]\s+a\s+regir|regir[áa])\s+"
    r"(?:a\s+partir\s+del|desde\s+el|el)\s+" + _DATE,
    re.IGNORECASE,
)
_ACT_DATE_LINE = re.compile(
    r"^(?:ciudad\s+de\s+buenos\s+aires|bs\.?\s*as\.?|buenos\s+aires)\b", re.IGNORECASE
)
_REFERENCE = re.compile(r"^(?:Ref(?:erencia)?\.?:)\s*", re.IGNORECASE)
_CODE_LINE = re.compile(r"^[A-Z]{2,}-\d{4}-")
_APPROVES = re.compile(
    r"(?:Aprobar|Apru[eé]base)\s+(?:el|la|los|las)\s+[“\"«](?P<title>.+?)[”\"»]",
    re.IGNORECASE,
)
_APPROVES_REGIME = re.compile(
    r"Aprobar\s+(?:el|la)\s+[“\"«]?\s*R[ÉE]GIMEN\s+GENERAL\s+PARA\s+CONTRATACIONES",
    re.IGNORECASE,
)
_ANNEX_TITLE = re.compile(r"^ANEXO\s*\(art[ií]culo\s+\d+", re.IGNORECASE)
_INDEX_LINE = re.compile(r"^[ÍI]NDICE\b", re.IGNORECASE)
_OPINION = re.compile(r"^Dictamen\b", re.IGNORECASE)
_RECOMMENDATION = re.compile(r"^Recomendaci[oó]n\b", re.IGNORECASE)
_PEN = re.compile(r"^PODER\s+EJECUTIVO\s+NACIONAL$", re.IGNORECASE)


@dataclass(frozen=True)
class Proposed:
    """Un dato propuesto y la evidencia de donde salió: la página (`None` en una página
    web o en el archivo mismo) y el texto."""

    value: object
    page: int | None
    text: str


def _plain(text):
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _year(text):
    year = int(text)
    if year >= 100:
        return year
    return 1900 + year if year >= 70 else 2000 + year


def _parse_date(text):
    text = text.strip()
    try:
        if "/" in text:
            day, month, year = (int(part) for part in text.split("/"))
            return date(year, month, day)
        day, _, month, _, year = text.lower().split()
        return date(int(year), _MONTHS[month], int(day))
    except (ValueError, KeyError):
        return None


def _lines(reading):
    """Las líneas del texto del documento, en orden, como `(página, texto)`. Sin las
    descartadas (navegación, scripts) ni las vacías."""
    lines = []
    for page in reading.pages:
        for line in page.lines:
            text = " ".join(line.text.split())
            if text and not line.discarded:
                lines.append((page.number, text))
    return lines


def _evidence(line):
    page, text = line
    return page, text[:EVIDENCE_LENGTH]


def _issuer(text):
    """La sigla del organismo que nombra la línea, o `None`."""
    if mentions_issuer(text):
        return "ARCA" if "recaudacion y control" in _plain(text) else "AFIP"
    if _PEN.match(text):
        return "Poder Ejecutivo Nacional"
    return None


def _type_line(header):
    for index, line in enumerate(header):
        match = _TYPE_LINE.match(line[1])
        if match:
            return index, match
    return None, None


def _title(lines, header, type_index):
    if type_index is not None:
        for line in header[type_index + 1:type_index + 5]:
            text = line[1]
            if _ACT_DATE_LINE.match(text) or text.upper().startswith("VISTO"):
                break
            if _CODE_LINE.match(text) or _issuer(text) or len(text.split()) < 3:
                continue
            return Proposed(_REFERENCE.sub("", text), *_evidence(line))
    for line in lines[:HEADER_LINES * 2]:
        match = _APPROVES.search(line[1])
        if match and "R" in match.group("title"):
            return Proposed(match.group("title").strip(), *_evidence(line))
    for index, line in enumerate(header):
        if _ANNEX_TITLE.match(line[1]):
            parts = []
            for follow in header[index + 1:index + 5]:
                if _INDEX_LINE.match(follow[1]) or follow[1] != follow[1].upper():
                    break
                parts.append(follow[1])
            if parts:
                return Proposed(" ".join(parts), line[0], " ".join(parts)[:EVIDENCE_LENGTH])
    return None


def _category(lines, header, type_name, issuer, type_line):
    for line in lines[:HEADER_LINES * 2]:
        if _APPROVES_REGIME.search(line[1]):
            return Proposed(Category.REGIMEN_ESPECIFICO, *_evidence(line))
    for line in header:
        if _OPINION.match(line[1]):
            return Proposed(Category.DICTAMEN_LEGAL, *_evidence(line))
        if _RECOMMENDATION.match(line[1]):
            return Proposed(Category.RECOMENDACION_AUDITORIA, *_evidence(line))
    if type_name in ("Decreto", "Ley"):
        return Proposed(Category.MARCO_NACIONAL, *_evidence(type_line))
    if issuer in ("AFIP", "ARCA") and type_line is not None:
        return Proposed(Category.OTRA_NORMATIVA, *_evidence(type_line))
    return None


def _publication(lines):
    for line in reversed(lines):
        match = _PUBLICATION_FOOTER.match(line[1])
        if match:
            year = _year(match.group("year")) if match.group("year") else int(
                match.group("end_year"))
            try:
                found = date(year, int(match.group("month")), int(match.group("day")))
            except ValueError:
                continue
            return Proposed(found, *_evidence(line))
    return None


def _effective(lines):
    for line in lines:
        match = _EFFECTIVE.search(line[1])
        if match:
            found = _parse_date(match.group("date"))
            if found is not None:
                return Proposed(found, *_evidence(line))
    return None


def propose_fields(reading, file_name):
    """Los datos de la norma que las reglas reconocen en `reading`, como un diccionario
    por nombre de dato (`loading.FIELDS`) de `Proposed` o `None` si no se reconoce."""
    lines = _lines(reading)
    header = lines[:HEADER_LINES]
    type_index, match = _type_line(header)

    found = dict.fromkeys(
        ("category", "norm_type", "number", "year", "issuer", "title", "citation",
         "publication_date", "effective_from", "source")
    )
    type_name = issuer = type_line = None
    # El organismo está antes de la línea del tipo; sin ella, entre las primeras líneas.
    for line in header[:type_index if type_index is not None else 5]:
        sigla = _issuer(line[1])
        if sigla:
            issuer = sigla
            found["issuer"] = Proposed(sigla, *_evidence(line))
    if match is not None:
        type_line = header[type_index]
        evidence = _evidence(type_line)
        type_name = _TYPES[" ".join(match.group("type").lower().split()).translate(
            str.maketrans("ó", "o"))]
        found["norm_type"] = Proposed(type_name, *evidence)
        found["number"] = Proposed(match.group("number").replace(".", ""), *evidence)
        found["year"] = Proposed(_year(match.group("year")), *evidence)
        if issuer is not None:
            number = int(match.group("number").replace(".", ""))
            # Un decreto no se cita con el organismo ("Decreto 1030/2016").
            parts = [type_name] if type_name == "Decreto" else [type_name, issuer]
            found["citation"] = Proposed(
                f"{' '.join(parts)} {number}/{found['year'].value}", *evidence
            )
    found["title"] = _title(lines, header, type_index)
    found["category"] = _category(lines, header, type_name, issuer, type_line)
    found["publication_date"] = _publication(lines)
    found["effective_from"] = _effective(lines)
    found["source"] = Proposed(file_name, None, f"Archivo subido: {file_name}")
    return found
