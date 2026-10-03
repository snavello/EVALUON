"""Búsqueda por palabras: tildes, singular y plural (T-009; plan 001, "Búsqueda por
palabras: tildes, singular y plural"; ADR-0007).

Comprueba en la base real las funciones `search_normalize`, `search_document` y
`search_query`, la columna `tsv` de `norms_passage` y la tabla "Resultado esperado" del
ADR-0007. Desde T-053, también la eñe (ADR-0007, adenda "La eñe") y el recálculo de
`tsv` de los pasajes ya guardados. Los textos son sintéticos.
"""

import importlib

import pytest
from django.db import connection

# Tabla "Resultado esperado" del ADR-0007: palabra, salida de `search_normalize` y
# lexema de `search_document`.
EXPECTED = [
    ("licitación", "licitación", "licit"),
    ("licitacion", "licitación", "licit"),
    ("LICITACIÓN", "LICITAción", "licit"),
    ("licitaciones", "licitaciones", "licit"),
    ("adjudicación", "adjudicación", "adjud"),
    ("adjudicaciones", "adjudicaciones", "adjud"),
    ("contratación", "contratación", "contrat"),
    ("contrataciones", "contrataciones", "contrat"),
    ("artículo", "articulo", "articul"),
    ("artículos", "articulos", "articul"),
    ("articulo", "articulo", "articul"),
    ("garantía", "garantia", "garanti"),
    ("garantías", "garantias", "garanti"),
    ("garantia", "garantia", "garanti"),
    ("297/03", "297/03", "297/03"),
    ("247/2022", "247/2022", "247/2022"),
]

FAMILIES = {
    "licitacion": ["licitación", "licitaciones", "licitacion", "LICITACIÓN"],
    "adjudicacion": ["adjudicación", "adjudicaciones"],
    "contratacion": ["contratación", "contrataciones"],
    "articulo": ["artículo", "artículos", "articulo"],
    "garantia": ["garantía", "garantías", "garantia"],
}


def _scalar(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


@pytest.mark.django_db
@pytest.mark.parametrize("word,normalized,lexeme", EXPECTED)
def test_lexemes_are_those_of_adr_0007(word, normalized, lexeme):
    """REQ-010: cada palabra de la tabla del ADR-0007 queda, después de
    `search_normalize`, como dice la tabla, y `search_document` la reduce al lexema de
    la tabla, con tilde o sin ella y en mayúsculas o minúsculas."""
    assert _scalar("SELECT search_normalize(%s)", [word]) == normalized
    assert _scalar("SELECT search_document(%s)::text", [word]) == f"'{lexeme}':1"


@pytest.mark.django_db
def test_search_query_uses_the_same_normalization():
    """REQ-010: `search_query` normaliza igual que `search_document`: la consulta sin
    tilde y en singular da el mismo lexema que el plural."""
    assert _scalar("SELECT search_query(%s)::text", ["licitacion"]) == "'licit'"
    assert _scalar("SELECT search_query(%s)::text", ["LICITACIONES"]) == "'licit'"
    assert (
        _scalar("SELECT search_query(%s)::text", ['"garantia de adjudicacion"'])
        == "'garanti' <2> 'adjud'"
    )


@pytest.mark.django_db
def test_the_three_functions_are_immutable_and_spanish_unaccent_is_not_created():
    """REQ-010: las tres funciones son inmutables (por eso `tsv` puede ser una columna
    calculada por la base) y no existe la configuración `spanish_unaccent` del plan
    anterior (ADR-0007)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT proname, provolatile FROM pg_proc"
            " WHERE proname IN ('search_normalize', 'search_document', 'search_query')"
        )
        volatility = dict(cursor.fetchall())
        cursor.execute("SELECT count(*) FROM pg_ts_config WHERE cfgname = 'spanish_unaccent'")
        configs = cursor.fetchone()[0]
    assert volatility == {
        "search_normalize": "i",
        "search_document": "i",
        "search_query": "i",
    }
    assert configs == 0


@pytest.mark.django_db
def test_tsv_is_a_generated_column_with_a_gin_index():
    """REQ-010: `norms_passage.tsv` la calcula la base con `search_document` sobre el
    texto del pasaje, y tiene un índice GIN."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type, is_generated, generation_expression"
            " FROM information_schema.columns"
            " WHERE table_name = 'norms_passage' AND column_name = 'tsv'"
        )
        data_type, is_generated, expression = cursor.fetchone()
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'norms_passage'"
            " AND indexdef LIKE '%%USING gin (tsv)%%'"
        )
        gin = cursor.fetchall()
    assert data_type == "tsvector"
    assert is_generated == "ALWAYS"
    assert "search_document" in expression and "text" in expression
    assert len(gin) == 1


def _passages_with_words(make_norm, make_document, make_reading, words):
    """Un pasaje por palabra, cada uno con una oración que solo contiene esa forma."""
    reading = make_reading(
        make_document(make_norm()),
        [(f"art-{i}", f"El pliego trata sobre {w} en este caso.")
         for i, w in enumerate(words, start=1)],
    )
    return {
        w: reading.units_by_key[f"art-{i}"].passages.get().pk
        for i, w in enumerate(words, start=1)
    }


def _matching(query, passage_ids):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM norms_passage WHERE tsv @@ search_query(%s) AND id = ANY(%s)",
            [query, list(passage_ids)],
        )
        return {row[0] for row in cursor.fetchall()}


@pytest.mark.django_db
def test_each_form_finds_every_form_of_its_family_and_no_other(
    make_norm, make_document, make_reading
):
    """REQ-010: cada palabra de la tabla, como consulta con `search_query`, encuentra
    el pasaje de cualquier otra forma de su familia (por ejemplo, "licitacion" encuentra
    el pasaje que solo dice "licitaciones") y ninguno de otra familia."""
    words = [w for forms in FAMILIES.values() for w in forms]
    passage_of = _passages_with_words(make_norm, make_document, make_reading, words)
    all_ids = set(passage_of.values())

    for forms in FAMILIES.values():
        family_ids = {passage_of[w] for w in forms}
        for query in forms:
            assert _matching(query, all_ids) == family_ids, query


@pytest.mark.django_db
def test_norm_numbers_find_the_passage_that_contains_them(
    make_norm, make_document, make_reading
):
    """REQ-010: "297/03" y "247/2022" encuentran el pasaje que los contiene, y solo ese."""
    reading = make_reading(
        make_document(make_norm()),
        [
            ("art-1", "Según la Disposición 297/03 de la AFIP."),
            ("art-2", "Según la Disposición 247/2022 de la AFIP."),
            ("art-3", "Según otra disposición de la AFIP."),
        ],
    )
    ids = {k: u.passages.get().pk for k, u in reading.units_by_key.items()}
    all_ids = set(ids.values())
    assert _matching("297/03", all_ids) == {ids["art-1"]}
    assert _matching("247/2022", all_ids) == {ids["art-2"]}


# --- La eñe (T-053; ADR-0007, adenda "La eñe") ---------------------------------------

# Palabra, salida de `search_normalize` y lexema de `search_document`. La "ñ" y la "Ñ" se
# conservan; las demás letras con acento o diéresis siguen perdiéndolo.
ENYE_EXPECTED = [
    ("año", "año", "año"),
    ("ano", "ano", "ano"),
    ("años", "años", "años"),
    ("AÑO", "AÑO", "año"),
    ("señal", "señal", "señal"),
    ("señales", "señales", "señal"),
    ("compañía", "compañia", "compañi"),
    ("compañías", "compañias", "compañi"),
    ("compania", "compania", "compani"),
    ("Ñandú", "Ñandu", "ñandu"),
    ("pingüino", "pinguino", "pinguin"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("word,normalized,lexeme", ENYE_EXPECTED)
def test_enye_is_kept_by_search_normalize(word, normalized, lexeme):
    """REQ-010: `search_normalize` conserva la "ñ" y la "Ñ" (ADR-0007, adenda "La
    eñe") y sigue quitando tildes y diéresis; `search_document` da el lexema esperado."""
    assert _scalar("SELECT search_normalize(%s)", [word]) == normalized
    assert _scalar("SELECT search_document(%s)::text", [word]) == f"'{lexeme}':1"


@pytest.mark.django_db
def test_enye_keeps_the_tilde_rule_of_acion():
    """REQ-010: la reposición de la tilde en "-acion" y "-ucion" sigue igual cuando la
    palabra lleva eñe, y `search_query` normaliza igual que `search_document`."""
    assert _scalar("SELECT search_normalize(%s)", ["señalizacion"]) == "señalización"
    assert _scalar("SELECT search_query(%s)::text", ["AÑO"]) == "'año'"
    assert _scalar("SELECT search_query(%s)::text", ["señales"]) == "'señal'"


@pytest.mark.django_db
def test_enye_words_find_only_their_own_family(make_norm, make_document, make_reading):
    """REQ-010: "año" y "ano" no se encuentran entre sí; "AÑO" encuentra "año";
    "señal" y "señales" se encuentran entre sí, igual que "compañía" y "compañías";
    "compania", escrita sin eñe, no encuentra "compañía" (ADR-0007, adenda)."""
    words = ["año", "ano", "señal", "señales", "compañía", "compañías", "compania"]
    passage_of = _passages_with_words(make_norm, make_document, make_reading, words)
    all_ids = set(passage_of.values())

    assert _matching("año", all_ids) == {passage_of["año"]}
    assert _matching("AÑO", all_ids) == {passage_of["año"]}
    assert _matching("ano", all_ids) == {passage_of["ano"]}
    assert _matching("señal", all_ids) == {passage_of["señal"], passage_of["señales"]}
    assert _matching("señales", all_ids) == {passage_of["señal"], passage_of["señales"]}
    assert _matching("compañía", all_ids) == {passage_of["compañía"], passage_of["compañías"]}
    assert _matching("compania", all_ids) == {passage_of["compania"]}


def _enye_migration():
    return importlib.import_module("evaluon.norms.migrations.0006_search_normalize_enye")


def _run(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)


@pytest.mark.django_db
def test_enye_migration_recalculates_tsv_of_existing_passages(
    make_norm, make_document, make_reading
):
    """REQ-010: un pasaje guardado con la definición anterior de `search_normalize`
    ("año" guardado como `ano`) deja de coincidir con "ano" después de la migración de
    la eñe, sin volver a cargarlo, porque la migración recalcula `tsv`. Su reversa
    vuelve a la definición anterior y también recalcula. Se corre el SQL de la
    migración dentro de la transacción de la prueba, que se deshace al terminar."""
    migration = _enye_migration()

    _run(migration.REVERSE)
    assert _scalar("SELECT search_normalize(%s)", ["año"]) == "ano"
    passage_of = _passages_with_words(make_norm, make_document, make_reading, ["año"])
    ids = set(passage_of.values())
    assert _matching("ano", ids) == ids

    _run(migration.FORWARD)
    assert _matching("ano", ids) == set()
    assert _matching("año", ids) == ids

    _run(migration.REVERSE)
    assert _matching("ano", ids) == ids

    _run(migration.FORWARD)
    assert _matching("ano", ids) == set()


@pytest.mark.django_db
@pytest.mark.parametrize("text", ["plazo\x01de", "plazo\x02de"])
def test_control_characters_used_to_protect_the_enye_are_separators(text):
    """REQ-010: los caracteres de control `\x01` y `\x02`, que `search_normalize` usa
    para proteger la eñe, separan palabras como antes de T-053: no salen como "ñ" ni
    "Ñ" ni pegan dos palabras ("plazo\x01de" da `plaz`, no `plazoñd`)."""
    assert _scalar("SELECT search_normalize(%s)", [text]) == "plazo de"
    assert _scalar("SELECT search_document(%s)::text", [text]) == "'plaz':1"
    assert (
        _scalar("SELECT search_normalize(%s)", ["AÑO Ñandú señalizacion licitacion"])
        == "AÑO Ñandu señalización licitación"
    )


@pytest.mark.django_db
def test_search_functions_work_with_an_empty_search_path():
    """REQ-010: las tres funciones nombran todo con su esquema y dan los lexemas
    esperados con `search_path` vacío, como en una restauración con `pg_restore`, que
    recalcula `tsv` al insertar cada pasaje."""
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL search_path = ''")
        cursor.execute(
            "SELECT public.search_normalize(w), public.search_document(w)::text,"
            " public.search_query(w)::text"
            " FROM unnest(ARRAY['año', 'licitacion']) AS w"
        )
        rows = cursor.fetchall()
    assert rows == [
        ("año", "'año':1", "'año'"),
        ("licitación", "'licit':1", "'licit'"),
    ]
