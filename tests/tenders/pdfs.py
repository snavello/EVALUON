"""Pliegos sintéticos en PDF para las pruebas de la 003 (T-070).

Imitan la forma del pliego del caso de referencia (plan 003, "El pliego del caso de
referencia") sin tomar nada de él: todo el texto es inventado y no hay datos de personas
(P4). Se arman con pypdfium2, la misma biblioteca de la lectura, con una fuente
TrueType incrustada para que la capa de texto traiga los signos del pliego (`−`, `•`,
`°`, `“`).

Un pliego es una lista de páginas; cada página, una lista de bloques:

- `para(*lines)`: un párrafo, con sus líneas una debajo de otra, sin espacio entre
  ellas. Entre dos párrafos queda un espacio, que la lectura toma como cambio de párrafo.
- `table(*rows)`: una tabla con bordes dibujados, una línea de texto por celda.

`fields_only_page()` es una página sin texto ni tinta, con una anotación: la lectura la
deja `no_leida` (como la hoja de firma digital de la 001).

Cada página lleva el encabezado repetido (el lema del año) y el pie "Página N de M", que
la lectura descarta.
"""

import ctypes
import io
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN_LEFT = 50
TOP_START = 100  # distancia desde arriba de la primera línea del cuerpo
FONT_SIZE = 10.0
LINE_STEP = 12  # entre líneas de un mismo párrafo
PARAGRAPH_STEP = 24  # entre el comienzo de un párrafo y el del siguiente
ROW_HEIGHT = 18
HEADER = "“2099 - Año sintético de las pruebas”"

# Fuente TrueType con los signos del pliego. La imagen de la aplicación la trae.
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
)


@dataclass(frozen=True)
class Para:
    lines: tuple


@dataclass(frozen=True)
class Table:
    rows: tuple


@dataclass(frozen=True)
class FieldsOnlyPage:
    pass


def para(*lines):
    return Para(tuple(lines))


def table(*rows):
    return Table(tuple(tuple(row) for row in rows))


def fields_only_page():
    return FieldsOnlyPage()


def _font_bytes():
    for path in FONT_CANDIDATES:
        if path.exists():
            return path.read_bytes()
    raise RuntimeError(
        "No se encontró la fuente DejaVuSans.ttf para armar los pliegos sintéticos: "
        "las pruebas corren en la imagen de la aplicación, que la trae."
    )


class _Writer:
    def __init__(self):
        self.pdf = pdfium.PdfDocument.new()
        data = _font_bytes()
        self._font_buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        self.font = raw.FPDFText_LoadFont(
            self.pdf.raw, self._font_buffer, len(data), raw.FPDF_FONT_TRUETYPE, True
        )
        self._keep = []

    def text(self, page, text, x, top):
        """Escribe `text` con su borde superior a `top` puntos del borde de arriba."""
        obj = raw.FPDFPageObj_CreateTextObj(self.pdf.raw, self.font, FONT_SIZE)
        wide = (text + "\x00").encode("utf-16-le")
        buffer = ctypes.create_string_buffer(wide, len(wide))
        self._keep.append(buffer)
        raw.FPDFText_SetText(obj, ctypes.cast(buffer, raw.FPDF_WIDESTRING))
        baseline = PAGE_HEIGHT - top - FONT_SIZE
        raw.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, baseline)
        raw.FPDFPage_InsertObject(page.raw, obj)

    def line(self, page, x0, top0, x1, top1):
        path = raw.FPDFPageObj_CreateNewPath(x0, PAGE_HEIGHT - top0)
        raw.FPDFPath_LineTo(path, x1, PAGE_HEIGHT - top1)
        raw.FPDFPageObj_SetStrokeColor(path, 0, 0, 0, 255)
        raw.FPDFPageObj_SetStrokeWidth(path, 0.8)
        raw.FPDFPath_SetDrawMode(path, raw.FPDF_FILLMODE_NONE, True)
        raw.FPDFPage_InsertObject(page.raw, path)

    def table(self, page, rows, top):
        """Dibuja la tabla con su grilla y devuelve dónde termina."""
        columns = max(len(row) for row in rows)
        width = PAGE_WIDTH - 2 * MARGIN_LEFT
        column_width = width / columns
        bottom = top + ROW_HEIGHT * len(rows)
        for index in range(len(rows) + 1):
            y = top + ROW_HEIGHT * index
            self.line(page, MARGIN_LEFT, y, MARGIN_LEFT + width, y)
        for index in range(columns + 1):
            x = MARGIN_LEFT + column_width * index
            self.line(page, x, top, x, bottom)
        for row_index, row in enumerate(rows):
            for column_index, cell in enumerate(row):
                self.text(
                    page,
                    cell,
                    MARGIN_LEFT + column_width * column_index + 4,
                    top + ROW_HEIGHT * row_index + 4,
                )
        return bottom

    def annotation(self, page):
        annot = raw.FPDFPage_CreateAnnot(page.raw, raw.FPDF_ANNOT_SQUARE)
        rect = raw.FS_RECTF(100, 400, 300, 500)
        raw.FPDFAnnot_SetRect(annot, rect)
        raw.FPDFPage_CloseAnnot(annot)

    def save(self):
        buffer = io.BytesIO()
        self.pdf.save(buffer)
        return buffer.getvalue()


def tender_pdf(pages, header=HEADER):
    """Arma el PDF de un pliego sintético. `pages` es una lista de páginas: cada una, una
    lista de bloques (`para`, `table`) o `fields_only_page()`. Con `header=None`, sin
    encabezado: en un PDF de una sola página no se repite y la lectura no lo descarta."""
    writer = _Writer()
    total = len(pages)
    for number, blocks in enumerate(pages, start=1):
        page = writer.pdf.new_page(PAGE_WIDTH, PAGE_HEIGHT)
        if isinstance(blocks, FieldsOnlyPage):
            writer.annotation(page)
            raw.FPDFPage_GenerateContent(page.raw)
            continue
        if header:
            writer.text(page, header, 200, 40)
        writer.text(page, f"Página {number} de {total}", 260, PAGE_HEIGHT - 40)
        top = TOP_START
        for block in blocks:
            if isinstance(block, Para):
                for index, text in enumerate(block.lines):
                    writer.text(page, text, MARGIN_LEFT, top + LINE_STEP * index)
                top += LINE_STEP * (len(block.lines) - 1) + PARAGRAPH_STEP
            elif isinstance(block, Table):
                top = writer.table(page, block.rows, top) + PARAGRAPH_STEP
            else:  # pragma: no cover - error del armado de la prueba
                raise TypeError(block)
        raw.FPDFPage_GenerateContent(page.raw)
    return writer.save()


# --- El pliego sintético con la forma del caso de referencia -------------------------

LEADER = " " + "." * 40 + " "

SYNTHETIC_TENDER = [
    # 1. Carátula
    [
        para("PLIEGO DE BASES Y CONDICIONES PARTICULARES"),
        para("NOMBRE DEL PROCESO: ADQUISICIÓN DE INSUMOS SINTÉTICOS DE PRUEBA"),
        para("PROCESO Nº: SINT-0001-PRUEBA"),
    ],
    # 2. Índice
    [
        para("ÍNDICE"),
        para(
            "SECCIÓN I - CONDICIONES PARTICULARES" + LEADER + "3",
            "1. OBJETO" + LEADER + "3",
            "7. REQUISITOS DE LA PRESENTACIÓN" + LEADER + "3",
            "SECCIÓN II - ESPECIFICACIONES TÉCNICAS GENERALES" + LEADER + "5",
            "SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES" + LEADER + "6",
            "SECCIÓN IV - ANEXOS" + LEADER + "8",
        ),
    ],
    # 3. Sección I
    [
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para(
            "1. OBJETO",
            "1.1. El objeto es la adquisición de insumos sintéticos de prueba.",
        ),
        para("2. NORMATIVA APLICABLE"),
        para(
            "2.1. El procedimiento se rige por la normativa siguiente:",
            "− Régimen sintético de contrataciones de prueba.",
            "− Pliego sintético de condiciones generales, sus",
            "complementarias y modificatorias.",
        ),
        para("3. DETALLE DE LOS BIENES"),
        table(
            ("RENGLÓN", "DESCRIPCIÓN", "CANTIDAD"),
            ("1", "PRODUCTO SINTÉTICO A", "100 UNIDADES"),
            ("2", "PRODUCTO SINTÉTICO B", "50 UNIDADES"),
        ),
        para("Instrucciones para cotizar en el portal de prueba."),
        para(
            "4. DEFINICIONES",
            "4.1. Los términos del pliego son los del régimen sintético.",
        ),
        para(
            "5. DOMICILIO ELECTRÓNICO",
            "5.1. Se toma el domicilio electrónico sintético declarado.",
        ),
        para(
            "6. MONEDA DE COTIZACIÓN",
            "6.1. Las cotizaciones se realizan en pesos con impuestos incluidos.",
        ),
    ],
    # 4. Sección I (sigue)
    [
        para(
            "7. REQUISITOS DE LA PRESENTACIÓN",
            "7.1. La oferta se presenta por el portal de prueba.",
            "7.2. La oferta se redacta en idioma nacional.",
            "7.3. La falta de documentación se intima a subsanar.",
            "7.4. La falsedad de lo declarado desestima la oferta.",
            "7.5. Documentación a presentar con la oferta:",
            "7.5.1. Constancia sintética de inscripción.",
            "7.5.2. Presentar la declaración jurada de habilidad para contratar.",
            "7.5.2.1. Firmada por el representante legal sintético.",
            "7.5.2.2.Con la fecha de la presentación.",
            "7.5.3. Las ofertas que no cumplan serán desestimadas, cuando:",
            "a) falte la firma del oferente;",
            "b) falte la garantía.",
        ),
        para("8. VIGENCIA DE LA ORDEN DE COMPRA"),
        para("8.1. La orden de compra rige por sesenta días corridos."),
        para(
            "9. PLAN DE ENTREGA",
            "9.1. Los bienes se entregan dentro de los quince días hábiles.",
        ),
        para(
            "10. CONFORMIDAD",
            "10.1. La conformidad se otorga en dos etapas.",
            "10.2. Etapas de la conformidad:",
            "10.2.1.Una vez entregados los bienes, se emite la conformidad provisoria.",
            "10.2.2.La conformidad definitiva se emite a los diez días.",
        ),
    ],
    # 5. Sección II
    [
        para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS GENERALES"),
        para(
            "1. CLÁUSULAS GENERALES",
            "1.1. Los bienes se entregan en el depósito sintético.",
            "1.2. Los bienes deberán cumplir con lo siguiente:",
            "• Vencimiento mayor a once meses.",
            "• Envase cerrado y rotulado.",
        ),
    ],
    # 6. Sección III
    [
        para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
        para(
            "1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A",
            "1.1. Composición del producto, con los valores mínimos de",
            "3.972 kcal por kilogramo de energía metabolizable y de",
            "1.300 mg por kilogramo de un componente sintético.",
            "1.2. Se admite un desvío de más o menos cinco por ciento.",
        ),
        para(
            "2. RENGLONES NROS. 2 A 4 - PRODUCTO SINTÉTICO B",
            "2.1. Bolsa de diez kilogramos con rótulo sintético.",
        ),
    ],
    # 7. Página sin texto, con una anotación
    fields_only_page(),
    # 8. Sección IV
    [
        para("SECCIÓN IV - ANEXOS"),
        para("ANEXO I - DECLARACIÓN JURADA SINTÉTICA"),
        para(
            "El que suscribe declara bajo juramento que la persona que representa",
            "está habilitada para contratar.",
        ),
        para("Razón Social: ______________________________"),
        para("Fecha: ________/_________/_________"),
    ],
]


def synthetic_tender_pdf():
    """El pliego sintético con la forma del caso de referencia: carátula, índice, cuatro
    secciones (dos técnicas por el título), numeración de hasta cuatro niveles con y sin
    espacio, renglones (uno solo y un rango), viñetas, incisos, una tabla, un anexo y
    una página sin texto (la 7)."""
    return tender_pdf(SYNTHETIC_TENDER)
