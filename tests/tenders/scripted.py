"""Ayudas de las pruebas de la propuesta de la matriz (T-073): pliegos sintéticos con
renglones, el doble del modelo con guion y el camino de pedir y correr una propuesta.

Todo el texto es inventado (P4). El doble del modelo (`fake_generation` de
`tests/conftest.py`) responde por omisión con la forma de la consulta de la 001; la
propuesta necesita una respuesta por tramo, así que `Script` reemplaza `generate` por una
función que lee los tramos del pedido, decide qué devolver y la entrega por el mismo doble
(`respond`), que arma el resultado igual que el cliente real.
"""

import itertools
import json
import re
from datetime import date

import pytest
from django.db import connection

from evaluon.ai import generation as generation_client
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.services import documents, matrix
from tests.tenders.pdfs import para, tender_pdf

_counter = itertools.count(1)

# --- Pliegos sintéticos ----------------------------------------------------------------------

GARANTIA = "Los oferentes deberán constituir una garantía del 5 % del monto."
PAGO = "El pago se efectuará a los 90 días corridos de la factura."
ENTREGA = "Los bienes se entregan dentro de los 15 días hábiles."
MULTA = "En caso de atraso se aplicará una multa del 1 % diario."


def three_items_pdf(*, third_item_specs=False):
    """Un pliego con una sección de condiciones, una de especificaciones generales y tres
    renglones. El renglón 3 no tiene especificaciones propias, salvo que se pida."""
    third = [para("3. RENGLÓN N° 3 - PRODUCTO SINTÉTICO C")]
    if third_item_specs:
        third = [para("3. RENGLÓN N° 3 - PRODUCTO SINTÉTICO C",
                      "3.1. Bolsa de cinco kilogramos.")]
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. GARANTÍA", f"1.1. {GARANTIA}"),
            para("2. PAGO", f"2.1. {PAGO}"),
            para("3. ENTREGA", f"3.1. {ENTREGA}"),
            para("4. MULTAS", f"4.1. {MULTA}"),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS GENERALES"),
            para("1. CLÁUSULAS GENERALES",
                 "1.1. Los bienes tienen vencimiento mayor a once meses."),
        ],
        [
            para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
            para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A",
                 "1.1. Bolsa de veinte kilogramos."),
            para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B",
                 "2.1. Bolsa de diez kilogramos.",
                 "2.2. Rótulo sintético en idioma nacional."),
            *third,
        ],
    ])


# --- Doble del modelo con guion ---------------------------------------------------------------

_BLOCK = re.compile(r"\[(T\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)


def parse_blocks(user_content):
    """Los tramos de un pedido de extracción: `{alias: {"text", "path", "items",
    "section_class"}}`."""
    blocks = {}
    for alias, body in _BLOCK.findall(user_content):
        head, _, text = body.partition("\nTexto:\n")
        fields = dict(line.split(": ", 1) for line in head.split("\n") if ": " in line)
        blocks[alias] = {
            "text": text,
            "path": fields.get("Ruta", ""),
            "items": fields.get("Renglones", ""),
            "section_class": fields.get("Clase de la sección", ""),
            "document": fields.get("Documento", ""),
        }
    return blocks


def item(requirements=(), technical=(), discard=""):
    """Lo que el modelo devuelve para un tramo."""
    return {
        "requisitos": [{"cita": quote, "clase": kind} for quote, kind in requirements],
        "tecnico": list(technical),
        "descarte": discard,
    }


DEFAULT_DISCARD = item(discard="dato_procedimiento")


class Script:
    """Guion del doble del modelo. `when(texto, item)` responde `item` a todo tramo cuyo
    texto contiene `texto`; el resto se descarta como dato del procedimiento. `calls`
    guarda los tramos de cada pedido (`parse_blocks`). Con `override(función)` la función
    recibe `(blocks, número de pedido)` y devuelve un diccionario por alias, un texto
    (salida sin tocar) o `("corte", texto)` (salida cortada por el máximo)."""

    def __init__(self, fake, monkeypatch):
        self.fake = fake
        self.rules = []
        self.calls = []
        self.consequence_calls = []
        self.fallback = DEFAULT_DISCARD
        self._override = None
        self._failing = False
        monkeypatch.setattr(generation_client, "generate", self._generate)

    def when(self, needle, answer):
        self.rules.insert(0, (needle, answer))

    def override(self, function):
        self._override = function

    def recover(self):
        """El doble vuelve a responder con el guion."""
        self._failing = False

    def fail(self, mode="timeout"):
        """A partir de ahora el doble lanza el error del servicio (`timeout`,
        `unavailable` o `input_too_long`) en lugar de responder."""
        getattr(self.fake, mode)()
        self._failing = True

    def _answer(self, blocks):
        result = {}
        for alias, block in blocks.items():
            result[alias] = self.fallback
            for needle, answer in self.rules:
                if needle in block["text"]:
                    result[alias] = answer
                    break
        return result

    def _generate(self, messages, schema, **options):
        first = next(iter(schema.get("properties", {}).values()), {}).get("properties", {})
        if "opciones" in first:
            # Pedido de consecuencias (T-080): no entra en `calls`, que cuenta los pedidos
            # de extracción; el guion responde sin opciones.
            self.consequence_calls.append(messages)
            if not self._failing:
                self.fake.respond(json.dumps(
                    {alias: {"opciones": []} for alias in schema["properties"]}))
            return self.fake.generate(messages, schema, **options)
        blocks = parse_blocks(messages[-1]["content"])
        number = len(self.calls)
        self.calls.append(blocks)
        if self._failing:
            return self.fake.generate(messages, schema, **options)
        answer = self._answer(blocks)
        if self._override is not None:
            answer = self._override(blocks, number, answer)
        if isinstance(answer, tuple) and answer[0] == "corte":
            self.fake.invalid_output(answer[1])
        elif isinstance(answer, str):
            self.fake.respond(answer)
        else:
            self.fake.respond(json.dumps(answer, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)


# --- Camino de pedir y correr una propuesta ------------------------------------------------------


def make_procedure(user, authorization_date=date(2025, 11, 14)):
    return m.Procedure.objects.create(
        number=f"SINT-MAT-{next(_counter)}",
        procedure_type="Licitación pública",
        subject="Adquisición sintética de insumos de prueba",
        authorization_date=authorization_date,
        created_by=user,
    )


def run_jobs():
    """Ejecuta los pedidos en espera, de a uno, como el `worker`."""
    done = []
    while (job := jobs.run_next()) is not None:
        job.refresh_from_db()
        done.append(job)
    return done


def load_and_read(user, procedure, data, *, kind=m.DocumentKind.PLIEGO,
                  title="Pliego sintético", file_name=None, issued_on=None):
    loaded = documents.load_document(
        user, procedure, data=data, file_name=file_name or f"{title}.pdf", kind=kind,
        title=title, issued_on=issued_on,
    )
    run_jobs()
    return loaded.document


def propose(user, procedure, *, level=None):
    """Pide la propuesta y la corre. Devuelve `(Requested, job ya ejecutado)`."""
    requested = matrix.request_matrix(user, procedure, level=level)
    run_jobs()
    requested.job.refresh_from_db()
    requested.run.refresh_from_db()
    return requested, requested.job


def check_deferred():
    """Comprueba ya los controles diferidos de la base (un formal o económico sin cita)."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")


@pytest.fixture
def script(fake_generation, monkeypatch):
    """El guion del doble del modelo (`Script`). Se importa en cada módulo de pruebas."""
    return Script(fake_generation, monkeypatch)
