"""Lectura de la página pública del proceso del Portal (T-140; REQ-046; ADR-0032).

`parse_page(bytes)` es una función pura: devuelve los datos básicos, los renglones, el
cronograma, las garantías y la lista de documentos con la forma de abrir cada uno (URL
directa o envío de formulario de ASP.NET). No inventa: lo que falta se informa en
`missing` (dato obligatorio) o en `issues` (sección ausente) y el resto se lee igual.

Los textos salen normalizados (`texto.py`); los campos con letras reemplazadas por `¿` o
`�` quedan tal como los entrega el Portal y se listan en `damaged`.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from . import texto

PREFIX = "ctl00_CPH1_UCVistaPreviaPliego_"
CIRCULAR_PATH = "/PLIEGO/VistaPreviaCircularCiudadano.aspx?qs="
REQUIRED = ("numero", "nombre", "tipo")

_POSTBACK = re.compile(r"__doPostBack\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)")
_POSTBACK_OPTIONS = re.compile(
    r'WebForm_PostBackOptions\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*\w+\s*,\s*"[^"]*"\s*,\s*"([^"]*)"'
)
_CIRCULAR_ID = re.compile(r"VerCircularCiudadano\(\s*'([^']*)'")
_QUANTITY = re.compile(r"^([\d.,]+)\s*(.*)$")
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Campos de "Información básica" (sufijo del id del span) -> clave del dato.
_BASIC = {
    "lblNumeroProceso": "numero",
    "lblNombreProceso": "nombre",
    "lblObjetoContratacion": "objeto",
    "lblProcedimientoSeleccion": "tipo",
    "lblEtapa": "etapa",
    "lblModalidad": "modalidad",
    "lblAlcance": "alcance",
    "lblMoneda": "moneda",
    "lblEncuadreLegal": "encuadre_legal",
    "lblTipoProcesoGen": "documento_que_genera",
    "lblLugarRecepcionFisica": "lugar_recepcion",
    "lblPlazoMantenimientoOferta": "mantenimiento_oferta",
}
_HEADER = {
    "lblNumPliego": "numero",
    "lblNumExpediente": "expediente",
    "lblNomPliego": "nombre",
    "lblUnidadOperativa": "unidad_operativa",
}
_LISTS = {
    "tipo_cotizacion": ("lblTipoCotizacionCantidad", "lblTipoCotizacionLinea"),
    "tipo_adjudicacion": ("lblTipoAdjudicacionCantidad", "lblTipoAdjudicacionLinea"),
}


@dataclass
class ProcessPage:
    """Lo leído de la página. Las claves de `data` y de cada documento son las de
    `tests/portal/data/portal-chico/portal-esperado.yaml`."""

    data: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    circulars: list = field(default_factory=list)
    versions: list = field(default_factory=list)
    acta: dict = None
    dictamen: dict = None
    cuadro: dict = None
    damaged: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def parse_page(data: bytes) -> ProcessPage:
    """Lee los bytes de la página pública de un proceso."""
    soup = BeautifulSoup(texto.decode(data), "lxml")
    page = ProcessPage()
    _read_basic(soup, page)
    _read_cronograma(soup, page)
    _read_guarantees(soup, page)
    _read_offers_summary(soup, page)
    _read_lines(soup, page)
    _read_documents(soup, page)
    _read_circulars(soup, page)
    _read_versions(soup, page)
    _read_authorization(page)
    for key in REQUIRED:
        if not page.data.get(key):
            page.missing.append(key)
    return page


# --- Utilidades ---------------------------------------------------------------------------


def _span(soup, suffix, group=None):
    """El span cuyo id es `PREFIX + [group_] + suffix`."""
    if group:
        return soup.find("span", id=f"{PREFIX}{group}_{suffix}")
    return soup.find("span", id=re.compile(re.escape(PREFIX) + suffix + "$"))


def _value(page, key, raw):
    """Guarda un texto limpio en `data[key]` y marca el campo si viene dañado."""
    cleaned = texto.clean(raw)
    page.data[key] = cleaned.value or None
    if cleaned.damaged and key not in page.damaged:
        page.damaged.append(key)
    return cleaned.value


def _issue(page, section, reason):
    page.issues.append({"seccion": section, "motivo": reason})


def _parse_date(text):
    found = _DATE.search(text or "")
    if not found:
        return None
    day, month, year = (int(g) for g in found.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_quantity(text):
    """`'2700 kg'` -> (Decimal o int, 'kg'); formato argentino: `1.500,5` o `1.500`."""
    found = _QUANTITY.match(text or "")
    if not found:
        return None, text or ""
    number, unit = found.groups()
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", number):
        number = number.replace(".", "")
    try:
        value = Decimal(number)
    except InvalidOperation:
        return None, text
    return (int(value) if value == value.to_integral_value() else value), unit.strip()


def _postback(anchor):
    """(target, argumento, url directa) del enlace, o None si no es un envío de formulario.

    `__doPostBack('t','a')` es un envío; `WebForm_DoPostBackWithOptions(...)` trae además la
    URL a la que va el envío, que cuando es una dirección de documento se abre por GET.
    """
    href = anchor.get("href", "")
    found = _POSTBACK_OPTIONS.search(href)
    if found:
        target, argument, url = found.groups()
        return target, argument, url
    found = _POSTBACK.search(href)
    if found:
        return found.group(1), found.group(2), ""
    return None


def _table(soup, suffix):
    return soup.find("table", id=re.compile(re.escape(PREFIX) + suffix + "$"))


def _rows(table):
    return table.find("tbody").find_all("tr") if table and table.find("tbody") else []


def _link_fields(anchor):
    """Cómo se abre un documento: `como`, `target`, `argumento`, `url`."""
    if anchor is None:
        return {"como": None, "target": None, "argumento": None, "url": None}
    postback = _postback(anchor)
    if postback is None:
        return {"como": None, "target": None, "argumento": None, "url": None}
    target, argument, url = postback
    if url:  # el envío trae la dirección directa del documento: se abre por GET
        return {"como": "url", "target": target, "argumento": argument, "url": url}
    return {"como": "formulario", "target": target, "argumento": argument, "url": None}


# --- Secciones ----------------------------------------------------------------------------


def _read_basic(soup, page):
    header_found = False
    for suffix, key in _HEADER.items():
        span = _span(soup, suffix, "usrCabeceraPliego")
        if span is not None:
            header_found = True
            _value(page, key, span.get_text())
    basic_found = False
    for suffix, key in _BASIC.items():
        span = _span(soup, suffix, "UC_InformacionBasica")
        if span is not None:
            basic_found = True
            # La información básica manda sobre la cabecera para lo que ambas traen.
            _value(page, key, span.get_text())
    for key, suffixes in _LISTS.items():
        values = []
        for suffix in suffixes:
            span = _span(soup, suffix, "UC_InformacionBasica")
            if span is not None:
                basic_found = True
                cleaned = texto.clean(span.get_text())
                if cleaned.value:
                    values.append(cleaned.value)
                if cleaned.damaged and key not in page.damaged:
                    page.damaged.append(key)
        page.data[key] = values
    for key in ("numero", "nombre", "objeto", "tipo", "expediente", "unidad_operativa"):
        page.data.setdefault(key, None)
    if not header_found:
        _issue(page, "cabecera", "no se encontró la cabecera del proceso")
    if not basic_found:
        _issue(page, "informacion_basica", "no se encontró la información básica")


def _read_cronograma(soup, page):
    schedule = {}
    for span in soup.find_all("span", id=re.compile(re.escape(PREFIX) + r"UC_Cronograma_lbl")):
        if "lblTit" in span["id"]:
            continue
        panel = span.find_parent("div")
        label = panel.find("label") if panel else None
        if label is None:
            continue
        name = texto.clean(label.get_text())
        schedule[name.value] = texto.clean(span.get_text()).value
        if name.damaged and "cronograma" not in page.damaged:
            page.damaged.append("cronograma")
    page.data["cronograma"] = schedule
    if not schedule:
        _issue(page, "cronograma", "no se encontró el cronograma")


def _read_guarantees(soup, page):
    items = []
    for span in soup.find_all("span", id=re.compile(re.escape(PREFIX) + r"UC_Garantias_")):
        cleaned = texto.clean(span.get_text())
        if not cleaned.value:
            continue
        items.append(cleaned.value)
        if cleaned.damaged and "garantias" not in page.damaged:
            page.damaged.append("garantias")
    page.data["garantias"] = items
    if not items:
        _issue(page, "garantias", "no se encontraron las garantías")


def _read_offers_summary(soup, page):
    for suffix, key in (
        ("lblOfertasPresentadas", "proveedores_participantes"),
        ("lblOfertasConfirmadas", "ofertas_confirmadas"),
    ):
        span = _span(soup, suffix, "UC_OfertasProceso")
        text = texto.normalize(span.get_text()) if span is not None else ""
        page.data[key] = int(text) if text.isdigit() else None
    link = soup.find("a", id=re.compile(r"UC_OfertasProceso_lnkVerCuadroComparativo$"))
    if link is not None and _postback(link):
        target, argument, _ = _postback(link)
        page.cuadro = {"nombre": "Cuadro comparativo de ofertas", "como": "formulario",
                       "target": target, "argumento": argument}


def _read_lines(soup, page):
    table = _table(soup, "UC_DetalleProductos_gvLineaPliego")
    if table is None:
        _issue(page, "renglones", "no se encontró la tabla de renglones")
        return
    for row in _rows(table):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5 or not texto.normalize(cells[0].get_text()).isdigit():
            continue
        description = texto.clean(cells[3].get_text())
        quantity, unit = _parse_quantity(texto.normalize(cells[4].get_text()))
        number = int(texto.normalize(cells[0].get_text()))
        if quantity is None:
            _issue(page, "renglones", f"el renglón {number} no trae una cantidad legible")
        page.lines.append({
            "numero": number,
            "objeto_gasto": texto.normalize(cells[1].get_text()),
            "codigo_item": texto.normalize(cells[2].get_text()),
            "descripcion": description.value,
            "cantidad": quantity,
            "unidad": unit,
            "danado": description.damaged,
        })
        if description.damaged:
            page.damaged.append(f"renglones.{number}.descripcion")
    if not page.lines:
        _issue(page, "renglones", "la tabla de renglones no tiene filas")


def _read_documents(soup, page):
    # Pliego general y su disposición: una fila con dos enlaces.
    for row in _rows(_table(soup, "UCCondicionesGenerales_gvCondicionesGenerales")):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        name = texto.clean(cells[0].get_text()).value
        for anchor in row.find_all("a"):
            fields = _link_fields(anchor)
            if fields["como"] is None:
                continue
            is_disposition = "Disposicion" in anchor.get("id", "")
            _add_document(page, {
                "nombre": "Disposición Aprobatoria del pliego general" if is_disposition else name,
                "seccion": "condiciones_generales",
                "numero_gde": None,
                "fecha": _parse_date(cells[2].get_text()) if len(cells) > 2 else None,
                **fields,
            })
    # Cláusulas particulares y actos administrativos: misma estructura.
    for suffix, section in (("UC_Clausulas_gvActosAdministrativos", "clausulas"),
                            ("UC_ActosAdministrativos_gvActosAdministrativos", "actos")):
        for row in _rows(_table(soup, suffix)):
            _add_document(page, _act_row(row, section))
    # Anexos (rptAnexos): nombre, tipo, descripción.
    for row in soup.find_all("tr"):
        link = row.find("a", id=re.compile(r"UCAnexos_rptAnexos_.*_btnVerAnexo$"))
        if link is None:
            continue
        spans = row.find_all("span", id=re.compile(r"UCAnexos_rptAnexos_"))
        by_suffix = {s["id"].rsplit("_", 1)[-1]: texto.clean(s.get_text()).value for s in spans}
        _add_document(page, {
            "nombre": by_suffix.get("Label4"),
            "seccion": "anexos",
            "tipo_anexo": by_suffix.get("Label2"),
            "descripcion": by_suffix.get("Label6"),
            "numero_gde": None,
            "fecha_vinculacion": None,
            **_link_fields(link),
        })
    # Acta de apertura y dictamen: se abren por la URL directa que trae el enlace.
    page.acta = _dated_document(soup, page, "UC_VistaPreviaActasApertura_gvActasApertura",
                                "lblNombreActaApertura", "acta")
    page.dictamen = _dated_document(
        soup, page, "UC_VistaPreviaDictamenesPreAdjudicacion_gvDictamenesPreAdjudicacion",
        "lblNombreDictamen", "dictamen")
    if page.cuadro is not None:
        _add_document(page, {**page.cuadro, "seccion": "cuadro", "numero_gde": None})


def _act_row(row, section):
    def text(suffix):
        span = row.find("span", id=re.compile(suffix + "$"))
        return texto.clean(span.get_text()).value if span is not None else ""

    link = row.find("a", id=re.compile(r"_btnVer$"))
    return {
        "nombre": text("lblDocumento"),
        "seccion": section,
        "numero_gde": text("lblNumeroSade") or None,
        "numero_especial": text("lblNumeroEspecial") or None,
        "fecha_vinculacion": _parse_date(text("lblFechaVinculacion")),
        **_link_fields(link),
    }


def _dated_document(soup, page, table_suffix, name_suffix, section):
    result = None
    for row in _rows(_table(soup, table_suffix)):
        name = row.find("span", id=re.compile(name_suffix + "$"))
        link = row.find("a", id=re.compile(r"_lnkVer(ActaApertura|Dictamen)$"))
        if name is None or link is None:
            continue
        cells = row.find_all("td", recursive=False)
        document = {
            "nombre": texto.clean(name.get_text()).value,
            "seccion": section,
            "numero_gde": None,
            "fecha": _parse_date(cells[1].get_text()) if len(cells) > 1 else None,
            **_link_fields(link),
        }
        if section == "dictamen" and len(cells) > 2:
            document["estado"] = texto.clean(cells[2].get_text()).value or None
        _add_document(page, document)
        result = result or document
    return result


def _add_document(page, document):
    if not document.get("nombre"):
        _issue(page, "documentos", "una fila de documentos no trae nombre")
        return
    if document.get("como") is None:
        _issue(page, "documentos", f"el documento «{document['nombre']}» no trae forma de abrirlo")
    page.documents.append(document)
    if texto.is_damaged(document["nombre"]):
        page.damaged.append(f"documentos.{document['nombre']}")


def _read_circulars(soup, page):
    for row in _rows(_table(soup, "UC_Circulares_gvCirculares")):
        def text(suffix):
            span = row.find("span", id=re.compile(suffix + "$"))
            return texto.clean(span.get_text()).value if span is not None else ""

        link = row.find("a", id=re.compile(r"_btnVerCircular$"))
        found = _CIRCULAR_ID.search(link.get("onclick", "")) if link is not None else None
        number = text("lblNumero")
        circular = {
            "numero": int(number) if number.isdigit() else None,
            "fecha_publicacion": _parse_date(text("lblFechaCreacion")),
            "tipo": text("lblTipo") or None,
            "url": CIRCULAR_PATH + found.group(1) if found else None,
        }
        if circular["url"] is None:
            _issue(page, "circulares", f"la circular {number} no trae el identificador para abrirla")
        page.circulars.append(circular)


def _read_versions(soup, page):
    for row in _rows(_table(soup, "UC_VersionesAnteriores_gvVersiones")):
        cells = row.find_all("td", recursive=False)
        if len(cells) >= 2 and texto.normalize(cells[0].get_text()).isdigit():
            page.versions.append({
                "numero": int(texto.normalize(cells[0].get_text())),
                "fecha_publicacion": _parse_date(cells[1].get_text()),
            })


def _read_authorization(page):
    """La página no muestra la fecha de autorización: la deja pendiente para quien aprueba y
    propone como candidata la fecha de vinculación de «Autorización llamado»."""
    candidate = None
    for document in page.documents:
        name = texto.normalize(document["nombre"]).lower()
        if document.get("seccion") == "actos" and name.startswith("autoriza") and "llamado" in name:
            candidate = document
            break
    page.data["fecha_autorizacion"] = {
        "valor": None,
        "estado": "pendiente: la página no la muestra",
        "candidata": candidate["fecha_vinculacion"] if candidate else None,
        "origen_candidata": (
            "fecha de vinculación de «Autorización llamado» en Actos administrativos; "
            "la aprueba quien carga" if candidate else None
        ),
    }
