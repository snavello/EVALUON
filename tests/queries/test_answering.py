"""Generación de la respuesta con esquema e inserción de citas (T-018 y T-034; plan 001,
"Generación", "Cita", "Abstención" y "Forma de la respuesta").

La generación recibe la pregunta, las unidades seleccionadas por la recuperación y la
fecha de autorización del procedimiento, le muestra al modelo cada unidad con su alias,
arma un esquema que enumera solo esos alias, hace un solo pedido al motor, valida la
salida y traduce cada alias al `id` de su unidad. El texto de una cita sale siempre de la
base, nunca de la salida del modelo. Con el doble del motor de `tests/conftest.py`; los
textos son sintéticos (P4).

Las pruebas consultan con una fecha de autorización (`DATE`): es el camino completo de
T-034 (`consulta-v2`, con `regimes_differ`). El camino sin fecha, que conserva
`consulta-v1` mientras `services.py` no pasa la fecha (T-040), tiene sus pruebas al final.
El orden por categoría, la marca de regímenes, los cambios y el contenido del pedido de
la v2 están en `test_answering_order.py`.
"""

import hashlib
import json
from datetime import date

import pytest
from django.conf import settings

from evaluon.norms import indexing
from evaluon.queries import answering

QUESTION = "¿Qué porcentaje tiene la garantía sintética de oferta?"

# Fecha de autorización del procedimiento con que se consulta.
DATE = date(2024, 5, 20)

TEXTS = {
    "art-1": "ARTICULO 1.- Objeto sintético del reglamento de prueba.",
    "art-2": "ARTICULO 2.- La garantía sintética de oferta es del cinco por ciento.",
    "art-3": "ARTICULO 3.- Los plazos sintéticos se cuentan en días hábiles.",
}


@pytest.fixture
def units(make_norm, make_document, make_reading):
    """Tres artículos de una norma sintética de régimen específico, por clave."""
    reading = make_reading(make_document(make_norm()), list(TEXTS.items()))
    return reading.units_by_key


def canonical(unit):
    """El texto literal según la única definición del proyecto."""
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def ids(units, *keys):
    return [units[key].pk for key in keys]


def user_message(fake_generation):
    [(messages, _)] = fake_generation.calls
    return next(m["content"] for m in messages if m["role"] == "user")


def st(text, *aliases, differ=False):
    """Afirmación tal como la devuelve el modelo con el esquema de `consulta-v2`."""
    return {"text": text, "citations": list(aliases), "regimes_differ": differ}


def ask(unit_ids):
    return answering.answer(QUESTION, unit_ids, reference_date=DATE)


def output(status, statements):
    return json.dumps({"status": status, "statements": statements}, ensure_ascii=False)


# --- REQ-008: pedido, esquema y respuesta con cita ------------------------------------


@pytest.mark.django_db
def test_grounded_answer_cites_unit_by_id_and_text_comes_from_base(units,
                                                                   fake_generation):
    """REQ-008: dada una pregunta que responde un artículo cargado, cuando el modelo cita
    su alias, entonces la respuesta cita ese artículo por su `id` y el texto de la cita es
    `canonical_text[char_start:char_end]` de su lectura, aunque el modelo haya escrito
    otra cosa como si fuera la norma."""
    fake_generation.answer([
        st("La garantía es del cinco por ciento: «texto inventado por el modelo».", "U2"),
    ])

    answer = ask(ids(units, "art-1", "art-2", "art-3"))

    art_2 = units["art-2"]
    assert answer.result["status"] == "grounded"
    assert answer.result["reason"] is None
    assert answer.result["statements"] == [
        {"text": "La garantía es del cinco por ciento: «texto inventado por el modelo».",
         "regimes_differ": False, "citations": [art_2.pk]},
    ]
    assert answering.citation_texts(answer.result) == {art_2.pk: canonical(art_2)}
    assert canonical(art_2) == TEXTS["art-2"]
    assert len(fake_generation.calls) == 1


@pytest.mark.django_db
def test_literal_text_is_the_canonical_slice_not_unit_text(units, fake_generation):
    """REQ-008: el texto literal de una cita es siempre
    `canonical_text[char_start:char_end]` de su lectura. Si la columna `text` de la
    unidad difiere de ese tramo, ni el pedido al modelo ni el texto de la cita la usan."""
    from evaluon.norms.models import Unit

    Unit.objects.filter(pk=units["art-2"].pk).update(text="texto distinto de la columna")
    art_2 = Unit.objects.select_related("reading").get(pk=units["art-2"].pk)
    assert art_2.text != canonical(art_2)
    fake_generation.answer([st("Afirmación.", "U1")])

    answer = ask([art_2.pk])

    assert answering.unit_text(art_2) == TEXTS["art-2"]
    assert answering.citation_texts(answer.result) == {art_2.pk: TEXTS["art-2"]}
    content = user_message(fake_generation)
    assert TEXTS["art-2"] in content
    assert "texto distinto de la columna" not in content


@pytest.mark.django_db
def test_result_has_cited_units_without_literal_text(units, fake_generation):
    """REQ-008: el resultado trae una vez cada unidad citada con norma, categoría, tipo,
    ruta, origen del texto, documento, página y cambios, con la forma de "Forma de la
    respuesta", y el texto literal no viaja en el resultado."""
    fake_generation.answer([
        st("Afirmación uno.", "U2", "U3"),
        st("Afirmación dos.", "U3"),
    ])

    answer = ask(ids(units, "art-1", "art-2", "art-3"))

    art_2, art_3 = units["art-2"], units["art-3"]
    norm = art_2.reading.document.norm
    assert answer.result["statements"] == [
        {"text": "Afirmación uno.", "regimes_differ": False,
         "citations": [art_2.pk, art_3.pk]},
        {"text": "Afirmación dos.", "regimes_differ": False, "citations": [art_3.pk]},
    ]
    assert set(answer.result["units"]) == {str(art_2.pk), str(art_3.pk)}
    assert answer.result["units"][str(art_2.pk)] == {
        "norm": indexing.norm_name(norm),
        "category": "regimen_especifico",
        "unit_type": "articulo",
        "path": art_2.path,
        "text_origin": "pdf_text",
        "document": art_2.reading.document.pk,
        "page_start": None,
        "changes": [],
    }
    stored = json.dumps(answer.result, ensure_ascii=False)
    for text in TEXTS.values():
        assert text not in stored
    assert answer.anomalies == []


@pytest.mark.django_db
def test_request_shows_each_unit_with_alias_and_base_text(units, fake_generation):
    """REQ-008: el pedido lleva las instrucciones versionadas (`consulta-v2`), la
    pregunta y cada unidad seleccionada con su alias en el orden recibido (misma
    categoría), su categoría, su norma, su ruta, su tipo y su texto tomado de la base."""
    selected = ids(units, "art-3", "art-1")

    answer = ask(selected)

    [(messages, _)] = fake_generation.calls
    assert answer.prompt_version == answering.PROMPT_VERSION_WITH_DATE == "consulta-v2"
    assert messages[0] == {"role": "system",
                           "content": answering.load_instructions("consulta-v2")}
    content = user_message(fake_generation)
    assert QUESTION in content
    norm = units["art-1"].reading.document.norm
    for alias, key in (("U1", "art-3"), ("U2", "art-1")):
        unit = units[key]
        block = content.split(f"[{alias}]", 1)[1].split("\n[U", 1)[0]
        assert "Régimen específico" in block
        assert indexing.norm_name(norm) in block
        assert unit.path in block
        assert "Artículo" in block
        assert canonical(unit) in block
    assert TEXTS["art-2"] not in content
    assert answer.aliases == {"U1": units["art-3"].pk, "U2": units["art-1"].pk}
    assert answer.request["messages"] == messages
    assert answer.request["response_format"]["json_schema"]["schema"] == \
        answering.build_schema(["U1", "U2"])


@pytest.mark.django_db
def test_schema_enumerates_only_the_aliases_shown(units, fake_generation):
    """REQ-008: el esquema de la consulta enumera solo los alias de las unidades
    mostradas, exige al menos una cita y un texto no vacío por afirmación, limita la
    cantidad de afirmaciones a 6 y pide la marca `regimes_differ` en cada una."""
    ask(ids(units, "art-2", "art-3"))

    [(_, schema)] = fake_generation.calls
    assert schema["required"] == ["status", "statements"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["status"]["enum"] == ["grounded", "undetermined"]
    statements = schema["properties"]["statements"]
    assert statements["maxItems"] == settings.GENERATION_MAX_STATEMENTS == 6
    item = statements["items"]
    assert item["required"] == ["text", "citations", "regimes_differ"]
    assert item["additionalProperties"] is False
    assert item["properties"]["text"] == {"type": "string", "minLength": 1}
    assert item["properties"]["regimes_differ"] == {"type": "boolean"}
    citations = item["properties"]["citations"]
    assert citations["minItems"] == 1
    assert citations["items"]["enum"] == ["U1", "U2"]


@pytest.mark.django_db
def test_duplicate_alias_in_a_statement_is_cited_once(units, fake_generation):
    """REQ-008: si una afirmación repite un alias, la unidad se cita una sola vez."""
    fake_generation.answer([st("Afirmación.", "U1", "U1")])

    answer = ask(ids(units, "art-2"))

    assert answer.result["statements"][0]["citations"] == [units["art-2"].pk]


@pytest.mark.django_db
def test_without_selected_units_the_model_is_not_called(fake_generation):
    """REQ-009: sin unidades seleccionadas no se llama al modelo; esa abstención
    (`below_threshold`) la resuelve quien llama."""
    with pytest.raises(ValueError):
        ask([])
    assert fake_generation.calls == []


# --- REQ-009: "no determinado", sin afirmaciones --------------------------------------


@pytest.mark.django_db
def test_model_abstains(units, fake_generation):
    """REQ-009: dada una pregunta que las unidades mostradas no responden, cuando el
    modelo devuelve `undetermined`, entonces el resultado es "no determinado" con motivo
    `model_abstained`, sin afirmaciones ni unidades."""
    fake_generation.abstain()

    answer = ask(ids(units, "art-1", "art-3"))

    assert answer.result == {"status": "undetermined", "reason": "model_abstained",
                             "statements": [], "units": {}}


@pytest.mark.django_db
def test_undetermined_with_statements_discards_them(units, fake_generation):
    """REQ-009: si el modelo devuelve `undetermined` junto con afirmaciones citadas, el
    resultado es `model_abstained` y las afirmaciones se descartan; queda la anomalía."""
    fake_generation.respond(output("undetermined", [
        st("Afirmación que no debe mostrarse.", "U1"),
    ]))

    answer = ask(ids(units, "art-2"))

    assert answer.result == {"status": "undetermined", "reason": "model_abstained",
                             "statements": [], "units": {}}
    assert answer.anomalies == [{"type": "statements_discarded", "count": 1}]
    assert "Afirmación que no debe mostrarse." in answer.raw_output


@pytest.mark.django_db
@pytest.mark.parametrize("statements", [
    [st("Cita un alias no mostrado.", "U9")],
    [st("Sin citas.")],
    [st("Válida.", "U1"), st("Cita un alias no mostrado.", "U1", "U2")],
    [],
], ids=["unknown-alias", "no-citations", "one-invalid-discards-all", "no-statements"])
def test_invalid_citation_discards_the_whole_answer(units, fake_generation, statements):
    """REQ-009: si alguna afirmación cita un alias que no se le mostró al modelo o no
    trae citas (o una respuesta con fundamento no trae ninguna afirmación), el resultado
    es "no determinado" con motivo `invalid_citation` y se descarta la respuesta entera:
    nunca una afirmación sin cita."""
    fake_generation.respond(output("grounded", statements))

    answer = ask(ids(units, "art-2"))

    assert answer.result == {"status": "undetermined", "reason": "invalid_citation",
                             "statements": [], "units": {}}
    assert answer.anomalies
    assert all(a["type"] == "invalid_citation" for a in answer.anomalies)


# --- Falla técnica: salida inválida y errores del servicio -----------------------------


@pytest.mark.django_db
def test_cut_output_is_an_error_not_undetermined(units, fake_generation):
    """REQ-009: una salida cortada no es un "no determinado": el resultado es una falla
    técnica (`error`) con motivo `invalid_output`, sin afirmaciones, y la salida queda sin
    tocar para el registro."""
    fake_generation.invalid_output()

    answer = ask(ids(units, "art-2"))

    assert answer.result == {"status": "error", "reason": "invalid_output",
                             "statements": [], "units": {}}
    assert answer.raw_output == '{"status": "grounded", "statements": [{"text": "La'
    assert answer.anomalies[0]["type"] == "invalid_output"
    assert answer.request is not None


def _statement(**fields):
    return json.dumps({"status": "grounded", "statements": [fields]})


@pytest.mark.django_db
@pytest.mark.parametrize("content", [
    "no es JSON",
    "[]",
    json.dumps({"status": "grounded"}),
    json.dumps({"status": "answered", "statements": []}),
    json.dumps({"status": "grounded", "statements": [], "extra": 1}),
    json.dumps({"status": "grounded", "statements": {}}),
    _statement(text="Sin la clave de citas.", regimes_differ=False),
    _statement(text="x", citations=["U1"], regimes_differ=False, extra=True),
    _statement(text=3, citations=["U1"], regimes_differ=False),
    _statement(text="", citations=["U1"], regimes_differ=False),
    _statement(text="x", citations="U1", regimes_differ=False),
    _statement(text="x", citations=[1], regimes_differ=False),
    _statement(text="x", citations=["U1"]),
    _statement(text="x", citations=["U1"], regimes_differ="false"),
    _statement(text="x", citations=["U1"], regimes_differ=None),
    _statement(text="x", citations=["U1"], regimes_differ=0),
    json.dumps({"status": "grounded",
                "statements": [st("x", "U1")] * (settings.GENERATION_MAX_STATEMENTS + 1)}),
], ids=["not-json", "not-object", "missing-statements", "unknown-status", "extra-key",
        "statements-not-list", "missing-citations", "statement-extra-key",
        "text-not-string", "empty-text", "citations-not-list", "citation-not-string",
        "missing-regimes-differ", "regimes-differ-string", "regimes-differ-null",
        "regimes-differ-number", "too-many-statements"])
def test_output_that_does_not_match_schema_is_invalid_output(units, fake_generation,
                                                            content):
    """REQ-009: una salida que no es un JSON que cumpla el esquema da falla técnica con
    motivo `invalid_output`, nunca una afirmación. Con `consulta-v2`, cada afirmación
    trae exactamente `text`, `citations` y `regimes_differ`, y la marca es booleana."""
    fake_generation.respond(content)

    answer = ask(ids(units, "art-2"))

    assert answer.result == {"status": "error", "reason": "invalid_output",
                             "statements": [], "units": {}}
    assert answer.raw_output == content


@pytest.mark.django_db
@pytest.mark.parametrize("mode, reason", [
    ("timeout", "timeout"),
    ("input_too_long", "input_too_long"),
    ("unavailable", "service_unavailable"),
])
def test_service_errors_are_technical_failures(units, fake_generation, mode, reason):
    """REQ-009: un motor que no responde, que agota la espera o que rechaza el pedido por
    no entrar en el contexto da falla técnica con su motivo, no "no determinado"; el
    pedido armado y el error quedan para el registro."""
    getattr(fake_generation, mode)()

    answer = ask(ids(units, "art-2"))

    assert answer.result == {"status": "error", "reason": reason,
                             "statements": [], "units": {}}
    assert answer.raw_output == ""
    assert answer.request["messages"] == fake_generation.calls[0][0]
    assert answer.error["service"] == "generation"
    assert "message" in answer.error


# --- Camino sin fecha: consulta-v1, hasta que T-040 pase la fecha ---------------------


@pytest.mark.django_db
def test_without_date_keeps_consulta_v1_and_its_schema(units, fake_generation):
    """REQ-008: sin fecha de autorización (así llama hoy `services.py`, hasta T-040) la
    generación usa `consulta-v1` sin modificar y su esquema, que no pide
    `regimes_differ`; el pedido no lleva fecha ni cambios. La respuesta con cita se
    arma igual, con la marca apagada."""
    fake_generation.answer([{"text": "Afirmación.", "citations": ["U1"]}])

    answer = answering.answer(QUESTION, ids(units, "art-2"))

    [(messages, schema)] = fake_generation.calls
    assert answer.prompt_version == answering.PROMPT_VERSION == "consulta-v1"
    assert answering.PROMPT_VERSION_WITHOUT_DATE == "consulta-v1"
    assert messages[0]["content"] == answering.load_instructions("consulta-v1")
    assert "Fecha de autorización" not in messages[1]["content"]
    item = schema["properties"]["statements"]["items"]
    assert item["required"] == ["text", "citations"]
    assert "regimes_differ" not in item["properties"]
    assert schema == answering.build_schema(["U1"], version="consulta-v1")
    assert answer.result["statements"] == [
        {"text": "Afirmación.", "regimes_differ": False,
         "citations": [units["art-2"].pk]},
    ]


@pytest.mark.django_db
def test_without_date_regimes_differ_is_not_accepted(units, fake_generation):
    """REQ-009: con `consulta-v1` el esquema no tiene `regimes_differ`: una salida que lo
    trae no cumple el esquema y da `invalid_output`."""
    fake_generation.respond(output("grounded", [st("Afirmación.", "U1")]))

    answer = answering.answer(QUESTION, ids(units, "art-2"))

    assert answer.result["reason"] == "invalid_output"


# Huella SHA-256 de `consulta-v1.txt` con finales de línea LF, tal como está guardado en
# el repositorio (`git show :evaluon/queries/prompts/consulta-v1.txt | sha256sum`).
CONSULTA_V1_SHA256 = "ba732859c34958d2c95bdecbb9554c9b8c8e4b53b6149f05464b58a94df35131"


def test_published_consulta_v1_does_not_change():
    """REQ-008: una versión publicada de las instrucciones no se modifica; un cambio es un
    archivo nuevo (P7). La huella de `consulta-v1.txt` queda fija.

    Finales de línea: el repositorio guarda el archivo con LF, pero `.gitattributes` no
    lo fija y con `core.autocrlf=true` la copia de trabajo de Windows lo tiene con CRLF
    (y así llega al contenedor si se monta esa copia). Para que la huella sea la misma en
    Linux y en Windows se calcula sobre los bytes con `\r\n` normalizado a `\n`, que es
    también lo que lee `load_instructions` (modo texto). Cualquier otro cambio de bytes,
    incluido un `\r` suelto, cambia la huella."""
    raw = (answering.PROMPTS_DIR / "consulta-v1.txt").read_bytes()

    normalized = raw.replace(b"\r\n", b"\n")

    assert hashlib.sha256(normalized).hexdigest() == CONSULTA_V1_SHA256
    assert answering.load_instructions("consulta-v1").encode("utf-8") == normalized
