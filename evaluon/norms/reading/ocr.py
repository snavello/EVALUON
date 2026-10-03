"""Lectura de una página escaneada con Tesseract (ADR-0004, alternativa D; T-021).

Recibe una página de PDF, la dibuja como imagen con pypdfium2 a 300 puntos por pulgada,
en escala de grises, y la reconoce con Tesseract y el modelo de español (`spa`, de
`tessdata_best`, que trae la imagen). Devuelve la página en el resultado común de la
lectura (`evaluon.norms.reading`): líneas de arriba hacia abajo, con su posición en
puntos de la página (como `pdf_text.py`), origen `ocr`, la confianza de cada palabra y la
de la línea, que es el promedio de sus palabras. El texto de una línea son sus palabras,
tal como las reconoce Tesseract, separadas por un espacio: no se corrige nada.

El estado de la página sale de la confianza promedio de todas sus palabras (ADR-0004,
"Cómo se lee", punto 3): legible desde `LEGIBLE_FROM`, dudosa desde `DOUBTFUL_FROM`,
ilegible por debajo, o si casi no hay palabras. Una página ilegible no aporta líneas
(REQ-004); una dudosa conserva su texto y el informe la señala.

No decide qué páginas se reconocen: eso lo hace la entrada única de la lectura (T-028).
No depende de que el documento sea una norma, así que sirve igual para pliegos y
ofertas. Corre en CPU y sin conexión (P4).
"""

import hashlib
import re
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytesseract

from evaluon.norms.reading import (
    ORIGIN_OCR,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_READ,
    Line,
    Page,
    Word,
)

# Resolución a la que se dibuja la página: la que pide la documentación de Tesseract.
RENDER_DPI = 300

# Modelo de español y modo de Tesseract: motor LSTM (`--oem 1`) y segmentación
# automática de la página (`--psm 3`). Se fijan acá para que la misma entrada dé siempre
# la misma salida.
LANGUAGE = "spa"
TESSERACT_CONFIG = f"--oem 1 --psm 3 --dpi {RENDER_DPI}"

# Umbrales del estado de la página, sobre la confianza promedio de sus palabras (0 a
# 100). Son valores de partida del plan, sin medición detrás: se calibran con los
# escaneos reales del corpus (T-043).
LEGIBLE_FROM = 80
DOUBTFUL_FROM = 50

# "Casi ninguna palabra": con menos de estas palabras que tengan alguna letra o cifra,
# la página es ilegible aunque su confianza sea alta. Valor de partida, como los de
# arriba. Una página en blanco no llega acá: la clasifica antes T-028.
MIN_WORDS = 3

# Decimales con que se guardan posiciones y confianzas.
DECIMALS = 2

_ALPHANUMERIC = re.compile(r"\w")
_TESSERACT_WORD_LEVEL = 5


def read_page_ocr(page, number: int) -> Page:
    """Reconoce una página de PDF (`pypdfium2.PdfPage`) y la devuelve como `Page`.

    `number` es el número de la página en su documento, desde 1.
    """
    width, height = page.get_size()
    image = page.render(scale=RENDER_DPI / 72, grayscale=True).to_pil()
    data = pytesseract.image_to_data(
        image,
        lang=LANGUAGE,
        config=TESSERACT_CONFIG,
        output_type=pytesseract.Output.DICT,
    )
    lines = _lines(data)
    words = [word for line in lines for word in line.words]
    status = page_status(words)
    # Origen y confianza promedio de la página (T-025), también en una página ilegible,
    # que no aporta líneas: así el informe distingue la confianza baja de la página casi
    # sin texto. Sin palabras no hay confianza.
    confidence = _round(sum(word.confidence for word in words) / len(words)) if words else None
    return Page(
        number=number,
        width=_round(width),
        height=_round(height),
        status=status,
        lines=lines if status != PAGE_ILLEGIBLE else [],
        origin=ORIGIN_OCR,
        confidence=confidence,
    )


def page_status(words: list[Word]) -> str:
    """Estado de una página reconocida según sus palabras: legible, dudosa o ilegible."""
    if sum(1 for word in words if _ALPHANUMERIC.search(word.text)) < MIN_WORDS:
        return PAGE_ILLEGIBLE
    average = sum(word.confidence for word in words) / len(words)
    if average >= LEGIBLE_FROM:
        return PAGE_READ
    if average >= DOUBTFUL_FROM:
        return PAGE_DOUBTFUL
    return PAGE_ILLEGIBLE


def tool_versions():
    """Versiones de las herramientas del reconocimiento y huella SHA-256 del modelo de
    español, para registrarlas con la lectura (P6)."""
    return {
        "tesseract": str(pytesseract.get_tesseract_version()),
        "pytesseract": version("pytesseract"),
        "pypdfium2": version("pypdfium2"),
        "tesseract_spa_sha256": _model_sha256(),
    }


def _lines(data):
    """Agrupa las palabras de Tesseract por línea (bloque, párrafo, línea)."""
    grouped = {}
    for index, level in enumerate(data["level"]):
        text = data["text"][index].strip()
        if level != _TESSERACT_WORD_LEVEL or not text:
            continue
        key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        left, top = data["left"][index], data["top"][index]
        box = (left, top, left + data["width"][index], top + data["height"][index])
        # Tesseract marca con -1 lo que no es una palabra; si una palabra con texto lo
        # trajera, cuenta como confianza 0, no como texto sin confianza.
        word = Word(text=text, confidence=_round(max(float(data["conf"][index]), 0)))
        grouped.setdefault(key, []).append((word, box))

    lines = []
    for entries in grouped.values():
        words = [word for word, _ in entries]
        boxes = [box for _, box in entries]
        lines.append(
            Line(
                text=" ".join(word.text for word in words),
                x0=_points(min(box[0] for box in boxes)),
                top=_points(min(box[1] for box in boxes)),
                x1=_points(max(box[2] for box in boxes)),
                bottom=_points(max(box[3] for box in boxes)),
                origin=ORIGIN_OCR,
                confidence=_round(sum(word.confidence for word in words) / len(words)),
                words=words,
            )
        )
    lines.sort(key=lambda line: (line.top, line.x0))
    return lines


def _points(pixels):
    return _round(pixels * 72 / RENDER_DPI)


def _round(value):
    return round(float(value), DECIMALS)


def _model_sha256():
    """Huella del `spa.traineddata` que usa Tesseract, buscado en la carpeta de modelos
    que informa el propio Tesseract."""
    listing = subprocess.run(
        [pytesseract.pytesseract.tesseract_cmd, "--list-langs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    folder = re.search(r'"(?P<path>[^"]+)"', listing).group("path")
    model = Path(folder) / f"{LANGUAGE}.traineddata"
    return hashlib.sha256(model.read_bytes()).hexdigest()
