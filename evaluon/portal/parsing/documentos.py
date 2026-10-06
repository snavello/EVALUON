"""Lista de documentos de la página del proceso, clasificada (T-142; REQ-046, REQ-051).

Función pura: toma lo que leyó `parse_page` y devuelve, por cada documento y circular, su
clave estable, su clase y cómo abrirlo. No baja nada.

Clases: `pliego` (pliego general y cláusulas particulares), `anexo`, `circular`, `acto`
(acto administrativo), `acta` (acta de apertura) y `dictamen`. El cuadro comparativo lo
importa T-143 y no figura acá.

Un documento que el Portal no sabe abrir (`como` vacío) se lista igual: quien baja lo
informa como anomalía.
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from . import texto

# Clase de documento según la sección de la página donde aparece.
SECTION_CLASS = {
    "condiciones_generales": "pliego",
    "clausulas": "pliego",
    "anexos": "anexo",
    "actos": "acto",
    "acta": "acta",
    "dictamen": "dictamen",
}

CIRCULAR = "circular"
# Clases que se cargan como documento del pliego de la 003 (el resto queda como archivo del
# Portal, con su origen: plan 012, "Carga", punto 1).
LOADABLE = ("pliego", "anexo", "circular")

CLASS_LABELS = {
    "pliego": "Pliego",
    "anexo": "Anexo",
    "circular": "Circular",
    "acto": "Acto administrativo",
    "acta": "Acta de apertura",
    "dictamen": "Dictamen",
}

_KIND_IN_TEXT = (
    ("modificatoria", "circular_modificatoria"),
    ("aclaratoria", "circular_aclaratoria"),
)


@dataclass
class DocumentRef:
    key: str
    name: str
    document_class: str
    section: str
    issued_on: object = None
    gde_number: str = None
    how: str = None  # "url", "formulario" o None si no se sabe abrir
    target: str = None
    argument: str = None
    url: str = None
    circular_number: int = None
    portal_type: str = None  # lo que el Portal dice del tipo de la circular
    circular_kind: str = None  # tipo de circular de la 003 si el Portal lo dice


def circular_kind_from(text):
    """`circular_modificatoria` o `circular_aclaratoria` si el texto lo dice; si no, `None`
    (el Portal habla de «Con consulta» y similares: lo elige quien aprueba)."""
    lowered = texto.normalize(text or "").lower()
    for word, kind in _KIND_IN_TEXT:
        if word in lowered:
            return kind
    return None


def _clean_name(name):
    return re.sub(r"\s+", " ", name or "").strip()


def list_documents(page):
    """Los documentos y circulares de un `ProcessPage`, en el orden de la página."""
    refs, seen = [], {}

    def unique(key):
        seen[key] = seen.get(key, 0) + 1
        return key if seen[key] == 1 else f"{key}#{seen[key]}"

    for document in page.documents:
        document_class = SECTION_CLASS.get(document.get("seccion"))
        if document_class is None:
            continue  # el cuadro comparativo es de T-143
        name = _clean_name(document.get("nombre"))
        refs.append(DocumentRef(
            key=unique(f"{document_class}:{name}"),
            name=name,
            document_class=document_class,
            section=document["seccion"],
            issued_on=document.get("fecha") or document.get("fecha_vinculacion"),
            gde_number=document.get("numero_gde"),
            how=document.get("como"),
            target=document.get("target"),
            argument=document.get("argumento"),
            url=document.get("url"),
        ))
    for circular in page.circulars:
        number = circular.get("numero")
        label = f"Circular {number}" if number is not None else "Circular"
        refs.append(DocumentRef(
            key=unique(f"{CIRCULAR}:{number if number is not None else circular.get('url')}"),
            name=label,
            document_class=CIRCULAR,
            section="circulares",
            issued_on=circular.get("fecha_publicacion"),
            how="url" if circular.get("url") else None,
            url=circular.get("url"),
            circular_number=number,
            portal_type=circular.get("tipo"),
            circular_kind=circular_kind_from(circular.get("tipo")),
        ))
    return refs


def absolute_url(base, url):
    """La dirección del documento, completa, a partir de la de la página."""
    return urljoin(base, url) if url else None
