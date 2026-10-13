"""Clase sugerida para un documento subido a una oferta (REQ-104; T-259; informe del comité, H4 y
acción A5; P9).

Al leer un documento de una oferta, el sistema mira su texto y, si corresponde, **sugiere** una
clase que una persona confirma. Por su cuenta no cambia el tipo del documento ni lo retira ni lo
borra (P3, P9):

- **Hoja de compliance** (`compliance`). El texto es el **resultado** de consultas a bases
  externas, no un texto que solo las nombra (D-259-1: una nota de presentación que enumera lo
  adjunto y una copia del pliego nombran los mismos temas). Hacen falta las tres cosas:
  al menos `MIN_COMPLIANCE_MARKS` de estas marcas (Registro de Proveedores o SIPRO, REPSAL,
  deuda con el Estado, constancia de inscripción, penalidades); el estado que devuelve una
  consulta (`RESULT`: «Estado: Inscripto», «no registra sanciones», «no registra deuda», «sin
  deuda», «sin sanciones»; no el infinitivo «no registrar» de un requisito ni lo que declara el
  oferente), y la fecha de la consulta o el organismo que la emite (`ISSUED`). Es la forma del
  informe del organismo que la oferta 3 del caso-00 trae como documento 41.
  Lo confirma un evaluador (la hoja de compliance la carga una persona identificada, P9): el
  documento pasa a hoja de compliance de la oferta con el hecho de quién lo confirmó.
- **Copia** (`duplicate`). Su texto es casi igual al de otro documento de la misma oferta ya
  leído: comparten `DUPLICATE_SHARE` o más de sus grupos de tres palabras seguidas. La sugerencia
  nombra el otro documento y la proporción; no se quita nada: si la Comisión lo cree, usa
  «Retirar», que lo deja en el historial.

Un documento ya marcado como hoja de compliance o informe técnico no recibe sugerencia de hoja de
compliance. Un texto de menos de `MIN_WORDS` palabras no se compara (dos escaneos sin texto no
son copias por eso). Todo corre en CPU, sin modelo ni red (P4). La sugerencia se guarda en el
informe de la lectura (`report["suggestion"]`) y sale en el hecho `offer_read`.
"""

import re
import unicodedata

SUGGEST_COMPLIANCE = "compliance"
SUGGEST_DUPLICATE = "duplicate"

# Marcas de una consulta a una base externa, sobre el texto en minúsculas y sin tildes. Valores
# de partida, tomados de la forma del informe del caso-00, sin medición detrás.
COMPLIANCE_MARKS = (
    ("Registro de Proveedores", re.compile(r"registro de proveedores|\bsipro\b")),
    ("REPSAL", re.compile(r"\brepsal\b")),
    ("deuda con el Estado", re.compile(
        r"sin deuda|consulta (?:de )?deuda|deuda (?:de )?proveedores|\b4164\b")),
    ("constancia de inscripción", re.compile(r"constancia de inscripcion")),
    ("penalidades", re.compile(r"\bpenalidades\b")),
)
# El estado que devuelve una consulta (D-259-1). «no registra» con la palabra entera: el
# infinitivo «no registrar» es el de un requisito o una declaración, no un resultado.
RESULT = re.compile(r"estado\s*:?\s*inscript[oa]|\bno registra\b|\bsin (?:deuda|sanciones)\b")
# La fecha de la consulta o el organismo que la emite (D-259-1).
ISSUED = re.compile(
    r"fecha de (?:la )?(?:consulta|emision)|a la fecha de emision"
    r"|fecha\s*:?\s*\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\b(?:arca|afip)\b|agencia de recaudacion|administracion federal de ingresos publicos"
    r"|oficina nacional de contrataciones|ministerio de trabajo")
MIN_COMPLIANCE_MARKS = 2
DUPLICATE_SHARE = 0.9
MIN_WORDS = 20
_SHINGLE = 3


def _plain(text):
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def compliance_marks(text):
    """Los nombres de las marcas de consulta externa que trae `text`, en el orden de la lista."""
    plain = _plain(text)
    return [name for name, pattern in COMPLIANCE_MARKS if pattern.search(plain)]


def _shingles(text):
    words = re.findall(r"\w+", _plain(text))
    if len(words) < MIN_WORDS:
        return None
    return {tuple(words[i:i + _SHINGLE]) for i in range(len(words) - _SHINGLE + 1)}


def similarity(a, b):
    """Proporción de grupos de tres palabras que comparten dos textos (de 0 a 1); `None` si alguno
    es demasiado corto para compararlo."""
    first, second = _shingles(a), _shingles(b)
    if not first or not second:
        return None
    return len(first & second) / len(first | second)


def suggest(text, others=(), *, fixed_kind=False):
    """La sugerencia para un documento con texto `text`, o `None`. `others` son los documentos de
    la misma oferta ya leídos: `(id, título, texto)`. `fixed_kind` dice si el documento ya es hoja
    de compliance o informe técnico (no se le sugiere hoja)."""
    marks = compliance_marks(text)
    plain = _plain(text)
    if (not fixed_kind and len(marks) >= MIN_COMPLIANCE_MARKS
            and RESULT.search(plain) and ISSUED.search(plain)):
        return {"kind": SUGGEST_COMPLIANCE, "marks": marks,
                "reason": ("Parece una hoja de compliance: trae consultas de "
                           + _enumerate(marks) + ".")}
    best = None
    for document_id, title, other in others:
        share = similarity(text, other)
        if share is not None and share >= DUPLICATE_SHARE and (best is None or share > best[0]):
            best = (share, document_id, title)
    if best is not None:
        share, document_id, title = best
        percent = int(share * 100)
        return {"kind": SUGGEST_DUPLICATE, "of_document": document_id, "of_title": title,
                "share": round(share, 4),
                "reason": (f"Parece una copia de «{title}»: comparten el {percent} % del "
                           "texto.")}
    return None


def _enumerate(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]
