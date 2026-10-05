"""Decodificación y normalización del texto del Portal (ADR-0032).

Regla del lector, no del modelo: lo recuperable se recupera (codificación declarada,
UTF-8 leído como latin-1, entidades, espacios, forma NFC) y lo que ya viene roto en los
bytes (`¿¿` o `�` en lugar de una letra acentuada) no se adivina (P3): se conserva tal
como lo entrega el Portal y se marca como dañado.
"""

import html
import re
import unicodedata
from typing import NamedTuple

from evaluon.norms.reading.web import _BOMS, detect_encoding

# Texto en UTF-8 leído como latin-1: una letra acentuada queda como `Ã` + un carácter.
_DOUBLE_ENCODED = re.compile("Ã[\u0080-¿]|Â[\u0080-¿]")
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_SPACES = re.compile(r"\s+")
# Daño que ya viene en los bytes: `¿` pegado a una letra (garant¿a) o repetido (LOG¿¿STICA),
# el carácter de reemplazo y la `è` (no existe en español: llega por `é`). El `¿` que abre una
# pregunta no cuenta: va después de un espacio o al principio y antes de una letra.
_DAMAGED = re.compile(r"(?<=[^\W\d_])¿|¿¿|�|è")


class Text(NamedTuple):
    """Texto normalizado y si trae caracteres dañados en el Portal."""

    value: str
    damaged: bool


def decode(data: bytes) -> str:
    """Decodifica los bytes de una página según lo que declara (`detect_encoding` de la 001).

    Si el texto resulta ser UTF-8 leído como latin-1, se recupera. Lo que ya viene roto en
    los bytes no se toca.
    """
    encoding = detect_encoding(data)
    for bom, bom_encoding in _BOMS:
        if encoding == bom_encoding and data.startswith(bom):
            data = data[len(bom):]
            break
    text = data.decode(encoding, errors="replace")
    return _repair_double_encoding(text)


def _repair_double_encoding(text: str) -> str:
    if not _DOUBLE_ENCODED.search(text):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text  # no es recuperable para toda la página: se deja como está
    return repaired


def normalize(text) -> str:
    """Entidades desescapadas (con o sin punto y coma), caracteres de control fuera,
    espacios y saltos duplicados colapsados y forma Unicode NFC."""
    if text is None:
        return ""
    text = html.unescape(str(text))
    text = text.replace("\xa0", " ")
    text = _CONTROL.sub("", text)
    text = unicodedata.normalize("NFC", text)
    return _SPACES.sub(" ", text).strip()


def is_damaged(text: str) -> bool:
    """El texto trae letras reemplazadas por `¿`, `�` o `è`: no hay forma de recuperarlas."""
    return bool(_DAMAGED.search(text or ""))


def clean(text) -> Text:
    """Normaliza y marca el daño sin corregirlo."""
    value = normalize(text)
    return Text(value, is_damaged(value))
