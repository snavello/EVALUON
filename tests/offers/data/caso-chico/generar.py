"""Genera los documentos del caso chico (T-130): un pliego, la oferta de un oferente con texto
y una constancia escaneada. Todo el texto es inventado y público (P4): no hay datos de
personas ni de procedimientos reales.

Se corre dentro de la imagen de la aplicación, que trae la fuente DejaVu y las bibliotecas:

    docker compose run --rm --no-deps app python tests/offers/data/caso-chico/generar.py

Escribe en esta carpeta `pliego.pdf`, `oferta-propuesta.pdf` y `constancia-escaneada.pdf`.
El escaneado se arma dibujando una página de texto a 300 puntos por pulgada y guardándola como
imagen dentro de un PDF, sin capa de texto: la lectura tiene que reconocerlo (REQ-038). Los
tres archivos van al repositorio; si se vuelven a generar, hay que actualizar las huellas de
`fichas-esperadas.yaml` (la lectura de la lista las comprueba).
"""

import io
import sys
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tests.tenders.pdfs import para, tender_pdf  # noqa: E402

HERE = Path(__file__).resolve().parent
SCAN_DPI = 300

PLIEGO = [
    [
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. OBJETO",
             "1.1. El objeto es la adquisición de insumos de oficina sintéticos."),
        para("2. DOCUMENTACIÓN A PRESENTAR",
             "2.1. Presentar la declaración jurada de habilidad para contratar firmada por "
             "el oferente.",
             "2.2. Acompañar la constancia de inscripción del oferente en el registro de "
             "proveedores."),
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

OFERTA = [
    [
        para("OFERTA DEL OFERENTE A SINTÉTICO",
             "Procedimiento CASO-CHICO-SINTETICO"),
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
        para("Renglón 1: resma de papel A4 de 75 gramos, 100 unidades, precio unitario",
             "$ 3.000."),
        para("Renglón 2: cartucho de tóner negro, 30 unidades, precio unitario $ 4.500."),
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


def scanned_pdf(pages):
    """Un PDF solo de imágenes, sin capa de texto, a partir de las páginas de texto."""
    source = pdfium.PdfDocument(tender_pdf(pages, header=None))
    images = []
    for index in range(len(source)):
        bitmap = source[index].render(scale=SCAN_DPI / 72)
        images.append(bitmap.to_pil().convert("L"))
    out = io.BytesIO()
    images[0].save(out, format="PDF", resolution=float(SCAN_DPI), save_all=True,
                   append_images=images[1:])
    return out.getvalue()


def main():
    (HERE / "pliego.pdf").write_bytes(tender_pdf(PLIEGO, header=None))
    (HERE / "oferta-propuesta.pdf").write_bytes(tender_pdf(OFERTA, header=None))
    (HERE / "constancia-escaneada.pdf").write_bytes(scanned_pdf(CONSTANCIA))


if __name__ == "__main__":
    main()
