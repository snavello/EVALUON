"""Genera los documentos del caso chico de la evaluación asistida (T-149, feature 004): un pliego
y tres ofertas inventadas, calcadas en su forma de las ofertas del caso de referencia (documentos
que mezclan temas, un escaneo, una póliza, una hoja técnica, una página ilegible, un documento
exigido que falta). Todo el texto es inventado y público (P4): no hay datos de personas ni de
procedimientos reales, y nada de las ofertas reales se copia.

Se corre dentro de la imagen de la aplicación (trae la fuente DejaVu y las bibliotecas):

    docker compose run --rm --no-deps app python tests/assessment/data/caso-chico/generar.py

Escribe `pliego.pdf` y la carpeta `ofertas/` de esta carpeta. Si se vuelven a generar hay que
actualizar las huellas de `evaluacion-esperada.yaml`. Reutiliza las funciones de armado de
escaneos del caso chico de la 008 (`tests/offers/data/caso-chico/generar.py`).
"""

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tests.tenders.pdfs import para, table, tender_pdf  # noqa: E402

HERE = Path(__file__).resolve().parent
SEED = 149

_spec = importlib.util.spec_from_file_location(
    "caso_chico_008", ROOT / "tests" / "offers" / "data" / "caso-chico" / "generar.py")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

PLIEGO = [
    [
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. OBJETO",
             "1.1. El objeto es la adquisición de insumos de oficina sintéticos."),
        para("2. DOCUMENTACIÓN A PRESENTAR",
             "2.1. Presentar la declaración jurada de habilidad para contratar firmada por el oferente.",
             "La declaración que informe una causal de inhabilidad provoca la desestimación de la",
             "oferta.",
             "2.2. Acompañar la constancia de inscripción del oferente en el registro de "
             "proveedores.",
             "2.3. Acompañar el certificado de vigencia del contrato social del oferente.",
             "2.4. Acompañar copia del documento de identidad del representante legal."),
        para("3. VERIFICACIONES DEL ORGANISMO",
             "3.1. La inexistencia de sanciones y de deuda exigible del oferente se verificará en la",
             "etapa de evaluación, consultando el registro de proveedores y el registro de",
             "sancionados."),
    ],
    [
        para("4. GARANTÍAS",
             "4.1. Constituir una garantía de mantenimiento de la oferta del cinco por "
             "ciento del monto cotizado."),
        para("5. COTIZACIÓN",
             "5.1. Cotizar en pesos con impuestos incluidos, indicando el precio unitario "
             "de cada renglón."),
        para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
        para("1. RENGLÓN N° 1 - RESMA DE PAPEL A4",
             "1.1. Resma de quinientas hojas, blancas, de 75 gramos por metro cuadrado."),
        para("2. RENGLÓN N° 2 - CARTUCHO DE TÓNER NEGRO",
             "2.1. Cartucho compatible con la impresora láser del organismo."),
        para("3. RENGLÓN N° 3 - ARCHIVADOR DE PALANCA",
             "3.1. Archivador de palanca, lomo ancho, tamaño oficio."),
    ],
]

# Precios del Portal (inventados): renglón -> (cantidad, unitario por oferente).
CANTIDADES = {1: 100, 2: 30, 3: 50}
PRECIOS = {
    "a": {1: 3000, 2: 4500, 3: 2000},
    "b": {1: 2800, 2: 4800, 3: 1900},
    "c": {1: 2600, 2: 4200, 3: 1800},
}
NOMBRES = {"a": "Oferente A Sintético", "b": "Oferente B Sintético",
           "c": "Oferente C Sintético"}
GRAMAJE = {"a": "75", "b": "75", "c": "70"}


def money(value):
    return f"$ {value:,}".replace(",", ".")


def total(key):
    return sum(CANTIDADES[r] * PRECIOS[key][r] for r in CANTIDADES)


def header(key):
    return f"{NOMBRES[key].upper()} · Procedimiento CASO-CHICO-EVALUACION"


def propuesta(key):
    name = NOMBRES[key]
    if key == "c":
        declaracion = para(
            "DECLARACIÓN JURADA",
            "Declaro bajo juramento que el oferente se encuentra comprendido en una causal de",
            "inhabilidad para contratar por deuda exigible con el organismo.")
    else:
        declaracion = para(
            "DECLARACIÓN JURADA",
            "Declaro bajo juramento que me encuentro habilitado para contratar con el",
            "organismo y que no estoy comprendido en ninguna causal de inhabilidad.")
    rows = [("Renglón", "Descripción", "Cantidad", "Precio unitario")]
    rows.append(("1", "Resma de papel A4", str(CANTIDADES[1]), money(PRECIOS[key][1])))
    rows.append(("2", "Cartucho de tóner negro", str(CANTIDADES[2]), money(PRECIOS[key][2])))
    rows.append(("3", "Archivador de palanca", str(CANTIDADES[3]), money(PRECIOS[key][3])))
    descripcion = {
        "a": "Cartucho de tóner negro compatible con la impresora láser del organismo.",
        "b": "Cartucho de tóner negro, modelo compatible con impresoras láser del organismo.",
        "c": "Cartucho de tóner negro compatible con la impresora láser del organismo.",
    }[key]
    archivador = {
        "a": "Archivador de palanca de lomo ancho, tamaño oficio.",
        "b": "Archivador de palanca, lomo ancho, tamaño oficio.",
        "c": "Archivador de palanca con lomo ancho y tamaño oficio.",
    }[key]
    return [
        [
            para("NOTA DE PRESENTACIÓN",
                 f"Me dirijo a la Comisión Evaluadora para presentar la oferta de {name}",
                 "en el procedimiento de referencia."),
            declaracion,
            para("VALIDEZ DE LA OFERTA",
                 "La oferta mantiene su validez por sesenta días corridos desde la fecha de",
                 "apertura."),
        ],
        [
            para("PROPUESTA ECONÓMICA",
                 "Los precios se cotizan en pesos con impuestos incluidos."),
            table(*rows),
            para(f"Total de la oferta: {money(total(key))}."),
        ],
        [
            para("ANEXO - DESCRIPCIÓN DE LOS RENGLONES 2 Y 3",
                 descripcion, archivador),
            para("CONDICIONES COMERCIALES",
                 "Plazo de entrega: según pliego.",
                 "Lugar de entrega: según pliego."),
        ],
    ]


def poliza(key):
    garantia = money(total(key) * 5 // 100)
    return [
        [
            para("PÓLIZA DE SEGURO DE CAUCIÓN N° 000-0000000",
                 f"Aseguradora Sintética S.A. garantiza, hasta la suma de {garantia}, el",
                 f"cumplimiento de la obligación de {NOMBRES[key]} de mantener su oferta en",
                 "el procedimiento CASO-CHICO-EVALUACION, equivalente al cinco por ciento del",
                 "monto cotizado."),
            para("Esta póliza constituye la garantía de mantenimiento de la oferta."),
        ],
        [
            para("CONDICIONES GENERALES",
                 "La presente póliza rige desde la fecha de su emisión hasta la extinción de la",
                 "obligación asegurada."),
        ],
    ]


def hoja_tecnica(key):
    return [
        [
            para("HOJA TÉCNICA · RESMA DE PAPEL A4",
                 f"Producto ofrecido por {NOMBRES[key]}: marca sintética, modelo S-{GRAMAJE[key]}."),
            table(("Característica", "Valor"), ("Gramaje", f"{GRAMAJE[key]} g/m²"),
                  ("Hojas por resma", "500"), ("Blancura", "92 %")),
            para(f"Firmado: Responsable técnico sintético, en representación de {NOMBRES[key]}."),
        ],
    ]


def constancia(key):
    return [
        [
            para("CONSTANCIA DE INSCRIPCIÓN EN EL REGISTRO DE PROVEEDORES",
                 f"Se deja constancia de que {NOMBRES[key]}, CUIT 00-00000000-0, se",
                 "encuentra inscripto en el registro de proveedores con el número 000123 desde",
                 "el 10 de marzo de 2025."),
        ],
    ]


def vigencia(key):
    return [
        [
            para("CERTIFICADO DE VIGENCIA DEL CONTRATO SOCIAL",
                 f"Se certifica que el contrato social de {NOMBRES[key]} se encuentra vigente",
                 "a la fecha de este certificado y que su representante legal tiene facultades",
                 "suficientes para presentar la oferta."),
        ],
    ]


def identidad(key):
    return [
        [
            para("DOCUMENTO DE IDENTIDAD DEL REPRESENTANTE",
                 "Copia del documento de identidad sintético número 00.000.000, del",
                 f"representante legal de {NOMBRES[key]}."),
        ],
    ]


CARATULA = [
    [
        para("DOCUMENTACIÓN FIRMADA DEL REPRESENTANTE",
             "Se adjunta la copia del documento de identidad del representante legal."),
    ],
]


def write(folder, name, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)


def main():
    rng = random.Random(SEED)
    write(HERE, "pliego.pdf", tender_pdf(PLIEGO, header=None))
    for key in ("a", "b", "c"):
        folder = HERE / "ofertas" / f"oferente-{key}"
        head = header(key)
        write(folder, "oferta-propuesta.pdf", tender_pdf(propuesta(key), header=head))
        write(folder, "poliza-caucion.pdf", tender_pdf(poliza(key), header=head))
        write(folder, "hoja-tecnica-resma.pdf", tender_pdf(hoja_tecnica(key), header=head))

        sheet = _base.render(constancia(key))[0]
        _base.stamp_and_signature(sheet, rng)
        sheet = _base.degrade(sheet, rng, angle=1.6, noise=40, blur=0.8)
        write(folder, "constancia-escaneada.pdf", _base.images_pdf([sheet]))

        # La oferta B no trae el certificado de vigencia del contrato social y tiene una página
        # sin leer (no se puede decir que falta: ADR-0038, regla 3); la C tampoco lo trae y se
        # lee completa: ahí el documento está ausente (T-151).
        if key == "a":
            write(folder, "certificado-vigencia.pdf", tender_pdf(vigencia(key), header=head))
        if key == "b":  # la oferta B trae el documento con una página escaneada e ilegible
            scan = _base.render(identidad(key))[0]
            scan = _base.degrade(scan, rng, angle=-3.0, noise=110, blur=6.0, contrast=0.55)
            write(folder, "documento-firmado-mixto.pdf", _base.mixed_pdf(CARATULA, [scan]))
        else:
            write(folder, "documento-identidad.pdf", tender_pdf(identidad(key), header=head))
        if key == "a":  # copia de texto idéntico (byte a byte) de la póliza
            write(folder, "poliza-caucion-copia.pdf",
                  (folder / "poliza-caucion.pdf").read_bytes())


if __name__ == "__main__":
    main()
