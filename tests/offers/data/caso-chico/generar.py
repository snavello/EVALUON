"""Genera los documentos del caso chico (T-130): un pliego y la oferta de un oferente armada
con la variedad de una oferta real. Todo el texto es inventado y público (P4): no hay datos de
personas ni de procedimientos reales, y nada de las ofertas reales se copia (solo se tomó
como guía su forma, ver `specs/008-ofertas-ficha/verificacion/T-130.md`).

Se corre dentro de la imagen de la aplicación, que trae la fuente DejaVu y las bibliotecas:

    docker compose run --rm --no-deps app python tests/offers/data/caso-chico/generar.py

Escribe en esta carpeta, con esta variedad:

- `pliego.pdf`: el pliego, con texto.
- `oferta-propuesta.pdf`: tres páginas con texto, encabezado y pie repetidos: carta de
  presentación con la declaración jurada y la validez (lo formal junto con lo económico), la
  propuesta económica con una tabla de precios por renglón, y un anexo con una respuesta
  implícita ("según pliego").
- `poliza-caucion.pdf`: una póliza con texto (la garantía).
- `constancia-escaneada.pdf`: una constancia escaneada, torcida, con ruido, con un sello y una
  firma encima del texto.
- `documento-firmado-mixto.pdf`: un PDF con una página de texto y otra escaneada y borrosa,
  que la lectura no puede leer bien (la lista de páginas no leídas o de baja confianza).

Los escaneos se arman dibujando una página de texto a 300 puntos por pulgada y deformándola
(giro, ruido, desenfoque, sello, firma); se guardan como imagen dentro de un PDF, sin capa de
texto: la lectura tiene que reconocerlos (REQ-038). El azar usa una semilla fija. Si se vuelven
a generar, hay que actualizar las huellas de `fichas-esperadas.yaml` (la lectura de la lista las
comprueba).
"""

import io
import random
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tests.tenders.pdfs import FONT_CANDIDATES, para, table, tender_pdf  # noqa: E402

HERE = Path(__file__).resolve().parent
SCAN_DPI = 300
SEED = 130

PLIEGO = [
    [
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. OBJETO",
             "1.1. El objeto es la adquisición de insumos de oficina sintéticos."),
        para("2. DOCUMENTACIÓN A PRESENTAR",
             "2.1. Presentar la declaración jurada de habilidad para contratar firmada por "
             "el oferente.",
             "2.2. Acompañar la constancia de inscripción del oferente en el registro de "
             "proveedores.",
             "2.3. Acompañar el certificado fiscal de libre deuda vigente."),
        para("3. GARANTÍAS",
             "3.1. Constituir una garantía de mantenimiento de la oferta del cinco por "
             "ciento del monto cotizado."),
        para("4. COTIZACIÓN",
             "4.1. Cotizar en pesos con impuestos incluidos, indicando el precio unitario "
             "de cada renglón.",
             "4.2. Mantener la validez de la oferta por sesenta días corridos desde la "
             "apertura."),
    ],
    [
        para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
        para("1. RENGLÓN N° 1 - RESMA DE PAPEL A4 DE 75 GRAMOS",
             "1.1. Resma de quinientas hojas, blancas."),
        para("2. RENGLÓN N° 2 - CARTUCHO DE TÓNER NEGRO",
             "2.1. Cartucho compatible con la impresora láser del organismo."),
        para("3. RENGLÓN N° 3 - ARCHIVADOR DE PALANCA",
             "3.1. Archivador de palanca, lomo ancho, tamaño oficio."),
    ],
]

HEADER = "OFERENTE A SINTÉTICO · Procedimiento CASO-CHICO-SINTETICO"

OFERTA = [
    [
        para("NOTA DE PRESENTACIÓN",
             "Me dirijo a la Comisión Evaluadora para presentar la oferta del Oferente A",
             "Sintético en el procedimiento de referencia."),
        para("DECLARACIÓN JURADA",
             "Declaro bajo juramento que me encuentro habilitado para contratar con el",
             "organismo y que no estoy comprendido en ninguna causal de inhabilidad."),
        para("VALIDEZ DE LA OFERTA",
             "La oferta mantiene su validez por sesenta días corridos desde la fecha de",
             "apertura."),
    ],
    [
        para("PROPUESTA ECONÓMICA",
             "Los precios se cotizan en pesos con impuestos incluidos."),
        table(("Renglón", "Descripción", "Cantidad", "Precio unitario"),
              ("1", "Resma de papel A4 de 75 gramos", "100", "$ 3.000"),
              ("2", "Cartucho de tóner negro", "30", "$ 4.500")),
        para("Total de la oferta: $ 435.000."),
    ],
    [
        para("ANEXO - CONDICIONES COMERCIALES",
             "Plazo de entrega: según pliego.",
             "Lugar de entrega: según pliego."),
    ],
]

POLIZA = [
    [
        para("PÓLIZA DE SEGURO DE CAUCIÓN N° 000-0000000",
             "Aseguradora Sintética S.A. garantiza, hasta la suma de $ 21.750, el",
             "cumplimiento de la obligación del Oferente A Sintético de mantener su oferta en",
             "el procedimiento CASO-CHICO-SINTETICO, equivalente al cinco por ciento del monto",
             "cotizado."),
        para("Esta póliza constituye la garantía de mantenimiento de la oferta."),
    ],
    [
        para("CONDICIONES GENERALES",
             "La presente póliza rige desde la fecha de su emisión hasta la extinción de la",
             "obligación asegurada."),
    ],
]

CONSTANCIA = [
    [
        para("CONSTANCIA DE INSCRIPCIÓN EN EL REGISTRO DE PROVEEDORES",
             "Se deja constancia de que el Oferente A Sintético, CUIT 00-00000000-0, se",
             "encuentra inscripto en el registro de proveedores con el número 000123 desde",
             "el 10 de marzo de 2025."),
    ],
]

IDENTIDAD = [
    [
        para("DOCUMENTO DE IDENTIDAD DEL REPRESENTANTE",
             "Copia del documento de identidad sintético número 00.000.000, del representante",
             "legal del Oferente A Sintético."),
    ],
]

CARATULA = [
    [
        para("DOCUMENTACIÓN FIRMADA DEL REPRESENTANTE",
             "Se adjunta la copia del documento de identidad del representante legal."),
    ],
]


def _font(size):
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("No se encontró la fuente DejaVuSans.ttf.")


def render(pages, header=None):
    """Las páginas de texto como imágenes en escala de grises a `SCAN_DPI`."""
    source = pdfium.PdfDocument(tender_pdf(pages, header=header))
    return [source[i].render(scale=SCAN_DPI / 72).to_pil().convert("L")
            for i in range(len(source))]


def stamp_and_signature(image, rng):
    """Un sello circular con texto y una firma a mano alzada encima del texto."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    cx, cy, radius = int(width * 0.68), int(height * 0.2), 260
    box = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.ellipse(box, outline=90, width=10)
    draw.ellipse((box[0] + 30, box[1] + 30, box[2] - 30, box[3] - 30), outline=90, width=4)
    font = _font(46)
    for index, line in enumerate(("RECIBIDO", "MESA DE", "ENTRADAS")):
        w = draw.textlength(line, font=font)
        draw.text((cx - w / 2, cy - 80 + index * 70), line, fill=90, font=font)
    x, y = int(width * 0.18), int(height * 0.3)
    points = []
    for step in range(40):
        x += rng.randint(8, 22)
        y += rng.randint(-30, 30)
        points.append((x, y))
    draw.line(points, fill=40, width=7)


def degrade(image, rng, *, angle=0.0, noise=0, blur=0.0, contrast=1.0):
    """Gira, agrega ruido y desenfoca, como un escaneo o una foto de mala calidad."""
    image = image.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    if contrast != 1.0:
        image = image.point(lambda v: int(128 + (v - 128) * contrast))
    if noise:
        pixels = image.load()
        width, height = image.size
        for _ in range(width * height // 40):
            x, y = rng.randrange(width), rng.randrange(height)
            pixels[x, y] = max(0, min(255, pixels[x, y] + rng.randint(-noise, noise)))
    return image


def images_pdf(images):
    out = io.BytesIO()
    images[0].save(out, format="PDF", resolution=float(SCAN_DPI), save_all=True,
                   append_images=images[1:])
    return out.getvalue()


def mixed_pdf(text_pages, scanned_images):
    """Un PDF con las páginas de texto primero y las escaneadas después."""
    target = pdfium.PdfDocument(tender_pdf(text_pages, header=None))
    scanned = pdfium.PdfDocument(images_pdf(scanned_images))
    target.import_pages(scanned)
    out = io.BytesIO()
    target.save(out)
    return out.getvalue()


def main():
    rng = random.Random(SEED)
    (HERE / "pliego.pdf").write_bytes(tender_pdf(PLIEGO, header=None))
    (HERE / "oferta-propuesta.pdf").write_bytes(tender_pdf(OFERTA, header=HEADER))
    (HERE / "poliza-caucion.pdf").write_bytes(tender_pdf(POLIZA, header=HEADER))

    constancia = render(CONSTANCIA)[0]
    stamp_and_signature(constancia, rng)
    constancia = degrade(constancia, rng, angle=1.6, noise=40, blur=0.8)
    (HERE / "constancia-escaneada.pdf").write_bytes(images_pdf([constancia]))

    identidad = render(IDENTIDAD)[0]
    identidad = degrade(identidad, rng, angle=-3.0, noise=110, blur=6.0, contrast=0.55)
    (HERE / "documento-firmado-mixto.pdf").write_bytes(mixed_pdf(CARATULA, [identidad]))


if __name__ == "__main__":
    main()
