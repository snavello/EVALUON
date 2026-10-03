"""Unidades consultables a una fecha (plan 001, "Unidades consultables a una fecha";
REQ-005, REQ-007, REQ-020; ADR-0006).

La fecha es siempre la de autorización del procedimiento que recibe quien llama: ninguna
de estas funciones usa la fecha del día. Con una fecha vacía no devuelven filas.

- `consultable_units(fecha)`: unidades de lecturas `validated` de documentos `in_use`
  (de cualquier parte de la norma) vigentes a la fecha (`effective_from <= fecha` y
  `effective_to` vacío o posterior a la fecha). Para cada una, `repealed` y la relación
  `deroga` que la marca: la de `effective_date <= fecha` que alcanza a la norma entera
  (`target_unit_key` vacío), a la unidad o a una unidad que la contiene (la clave de la
  unidad empieza con la clave alcanzada seguida de `/`). Si hay varias, la de fecha más
  antigua (y, a igual fecha, la registrada primero).
- `unit_changes(fecha)`: para cada unidad de `consultable_units(fecha)`, las relaciones
  `modifica` o `deroga` con `effective_date <= fecha` cuya clave alcanzada es la de la
  unidad o la de una unidad contenida en ella, con la unidad de origen que trae el
  cambio: la de la norma de origen con esa clave entre sus unidades consultables a la
  fecha, o vacía si la relación viene de la norma entera o esa unidad no es consultable.
  Una relación sobre la norma entera no es un cambio de cada unidad: la derogación de una
  norma entera o de una unidad que contiene a otra se ve en `repealed`.
- `applicable_regimes(fecha)`: normas con `general_regime` verdadero que tienen al menos
  una unidad en `consultable_units(fecha)` con `repealed` falso.

Funciones SQL estables, sin `STRICT`, para que Postgres pueda incorporarlas a la consulta
que las llama. Los nombres van con su esquema, como en 0003.
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION public.consultable_units(reference_date date)
RETURNS TABLE (
    unit_id bigint,
    reading_id bigint,
    document_id bigint,
    norm_id bigint,
    repealed boolean,
    repealed_by_relation_id bigint,
    repealed_by_norm_id bigint,
    repealed_since date
)
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT u.id, r.id, d.id, d.norm_id,
         rep.id IS NOT NULL, rep.id, rep.source_norm_id, rep.effective_date
  FROM public.norms_unit u
  JOIN public.norms_reading r ON r.id = u.reading_id
  JOIN public.norms_document d ON d.id = r.document_id
  LEFT JOIN LATERAL (
    SELECT rel.id, rel.source_norm_id, rel.effective_date
    FROM public.norms_relation rel
    WHERE rel.relation_type = 'deroga'
      AND rel.target_norm_id = d.norm_id
      AND rel.effective_date <= reference_date
      AND (rel.target_unit_key = ''
           OR rel.target_unit_key = u.key
           OR pg_catalog.starts_with(u.key, rel.target_unit_key || '/'))
    ORDER BY rel.effective_date, rel.id
    LIMIT 1
  ) rep ON true
  WHERE r.status = 'validated'
    AND d.in_use
    AND d.effective_from <= reference_date
    AND (d.effective_to IS NULL OR d.effective_to > reference_date)
$$;

COMMENT ON FUNCTION public.consultable_units(date) IS
  'Unidades consultables a la fecha de autorización, con la marca repealed a esa fecha (plan 001).';

CREATE FUNCTION public.unit_changes(reference_date date)
RETURNS TABLE (
    unit_id bigint,
    relation_id bigint,
    relation_type text,
    target_unit_key text,
    effective_date date,
    source_norm_id bigint,
    source_unit_key text,
    source_unit_id bigint
)
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT cu.unit_id, rel.id, rel.relation_type::text, rel.target_unit_key::text,
         rel.effective_date, rel.source_norm_id, rel.source_unit_key::text, src.unit_id
  FROM public.consultable_units(reference_date) cu
  JOIN public.norms_unit u ON u.id = cu.unit_id
  JOIN public.norms_relation rel
    ON rel.target_norm_id = cu.norm_id
   AND rel.relation_type IN ('modifica', 'deroga')
   AND rel.effective_date <= reference_date
   AND rel.target_unit_key <> ''
   AND (rel.target_unit_key = u.key
        OR pg_catalog.starts_with(rel.target_unit_key, u.key || '/'))
  LEFT JOIN LATERAL (
    SELECT scu.unit_id
    FROM public.consultable_units(reference_date) scu
    JOIN public.norms_unit su ON su.id = scu.unit_id
    WHERE scu.norm_id = rel.source_norm_id
      AND rel.source_unit_key <> ''
      AND su.key = rel.source_unit_key
    ORDER BY scu.unit_id
    LIMIT 1
  ) src ON true
$$;

COMMENT ON FUNCTION public.unit_changes(date) IS
  'Relaciones modifica o deroga vigentes a la fecha que alcanzan a cada unidad o a una contenida (plan 001).';

CREATE FUNCTION public.applicable_regimes(reference_date date)
RETURNS TABLE (norm_id bigint)
LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT DISTINCT cu.norm_id
  FROM public.consultable_units(reference_date) cu
  JOIN public.norms_norm n ON n.id = cu.norm_id
  WHERE n.general_regime AND NOT cu.repealed
  ORDER BY cu.norm_id
$$;

COMMENT ON FUNCTION public.applicable_regimes(date) IS
  'Regímenes generales con alguna unidad consultable y no derogada a la fecha (plan 001).';
"""

REVERSE = """
DROP FUNCTION IF EXISTS public.applicable_regimes(date);
DROP FUNCTION IF EXISTS public.unit_changes(date);
DROP FUNCTION IF EXISTS public.consultable_units(date);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("norms", "0004_passage_tsv"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
