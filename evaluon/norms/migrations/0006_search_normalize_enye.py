"""La eñe en la búsqueda por palabras (T-053; plan 001, "Búsqueda por palabras: tildes,
singular y plural"; ADR-0007, adenda "La eñe").

Reemplaza `search_normalize` para que la "ñ" y la "Ñ" no pasen por `unaccent`, que las
convertía en "n" ("año" y "ano" compartían lexema):

1. cambia por espacios los caracteres de control `\\x01` y `\\x02` que traiga el texto,
   que de todos modos separan palabras: así no se confunden con la eñe protegida en el
   paso siguiente ni pegan dos palabras;
2. cambia la "ñ" y la "Ñ" por `\\x01` y `\\x02`, que `unaccent` no toca;
3. quita los acentos con `unaccent`, como antes;
4. repone la "ñ" y la "Ñ";
5. repone la tilde de "-acion" y "-ucion", con la misma expresión que 0003.

La regla de la tilde corre sobre el texto ya repuesto, así no ve los caracteres de
control. `search_document` y `search_query` no cambian: llaman a `search_normalize`.
La función sigue inmutable y nombra todo con su esquema (ver 0003).

`norms_passage.tsv` es una columna calculada con `search_document`: al reemplazar la
función, los valores guardados no se recalculan solos. Por eso la migración, y también
su reversa, recalcula `tsv` de todos los pasajes (`UPDATE ... SET text = text`, que
vuelve a calcular la columna, como se comprobó en T-009) y reconstruye su índice GIN.

La reversa vuelve a la definición de 0003.
"""

from django.db import migrations

RECALCULATE = r"""
UPDATE public.norms_passage SET text = text;

REINDEX INDEX public.norms_passage_tsv_gin;
"""

FORWARD = r"""
CREATE OR REPLACE FUNCTION public.search_normalize(input text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT pg_catalog.regexp_replace(
           pg_catalog.translate(
             public.unaccent('public.unaccent'::regdictionary,
                             pg_catalog.translate(
                               pg_catalog.translate(input, E'\x01\x02', '  '),
                               'ñÑ', E'\x01\x02')),
             E'\x01\x02', 'ñÑ'),
           '([au])cion\M', '\1ción', 'gi')
$$;

COMMENT ON FUNCTION public.search_normalize(text) IS
  'Quita acentos salvo la eñe y repone la tilde de las palabras terminadas en -acion y -ucion (ADR-0007).';
""" + RECALCULATE

REVERSE = r"""
CREATE OR REPLACE FUNCTION public.search_normalize(input text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT pg_catalog.regexp_replace(
           public.unaccent('public.unaccent'::regdictionary, input),
           '([au])cion\M', '\1ción', 'gi')
$$;

COMMENT ON FUNCTION public.search_normalize(text) IS
  'Quita acentos y repone la tilde de las palabras terminadas en -acion y -ucion (ADR-0007).';
""" + RECALCULATE


class Migration(migrations.Migration):

    dependencies = [
        ("norms", "0005_date_functions"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
