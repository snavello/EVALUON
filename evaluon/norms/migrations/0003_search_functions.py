"""Funciones de búsqueda por palabras (plan 001, "Búsqueda por palabras: tildes, singular y
plural"; ADR-0007).

- `search_normalize(texto)`: quita los acentos con `unaccent` y repone la tilde en las
  palabras terminadas en "acion" o "ucion", sin distinguir mayúsculas.
- `search_document(texto)`: `to_tsvector('spanish', search_normalize(texto))`.
- `search_query(texto)`: `websearch_to_tsquery('spanish', search_normalize(texto))`.

Las tres son inmutables, para que `norms_passage.tsv` pueda ser una columna calculada por
la base. `unaccent` está marcada como estable porque su resultado depende del
diccionario que encuentre; acá se la llama con el diccionario nombrado con su esquema
(`'public.unaccent'::regdictionary`), así el resultado no depende de `search_path`. La
promesa de inmutabilidad vale mientras no cambien las reglas de `unaccent` ni el
lematizador de español: al actualizar Postgres de versión mayor o la imagen fijada, hay
que recalcular `tsv` y repetir `tests/norms/test_text_search_config.py` (ADR-0007).

Todos los nombres van con su esquema (`public.` o `pg_catalog.`): una restauración con
`pg_restore` corre con `search_path` vacío y recalcula `tsv` al insertar cada pasaje.

No se crea la configuración `spanish_unaccent` del plan anterior (ADR-0007).
"""

from django.db import migrations

FORWARD = r"""
CREATE FUNCTION public.search_normalize(input text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT pg_catalog.regexp_replace(
           public.unaccent('public.unaccent'::regdictionary, input),
           '([au])cion\M', '\1ción', 'gi')
$$;

COMMENT ON FUNCTION public.search_normalize(text) IS
  'Quita acentos y repone la tilde de las palabras terminadas en -acion y -ucion (ADR-0007).';

CREATE FUNCTION public.search_document(input text) RETURNS tsvector
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT pg_catalog.to_tsvector('pg_catalog.spanish'::regconfig,
                                public.search_normalize(input))
$$;

COMMENT ON FUNCTION public.search_document(text) IS
  'Vector de búsqueda de un texto: search_normalize y configuración spanish (ADR-0007).';

CREATE FUNCTION public.search_query(input text) RETURNS tsquery
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT pg_catalog.websearch_to_tsquery('pg_catalog.spanish'::regconfig,
                                         public.search_normalize(input))
$$;

COMMENT ON FUNCTION public.search_query(text) IS
  'Consulta de búsqueda: search_normalize y websearch_to_tsquery con spanish (ADR-0007).';
"""

REVERSE = """
DROP FUNCTION IF EXISTS public.search_query(text);
DROP FUNCTION IF EXISTS public.search_document(text);
DROP FUNCTION IF EXISTS public.search_normalize(text);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("norms", "0002_tables"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
