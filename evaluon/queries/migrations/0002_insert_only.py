"""`queries_query` se inserta una vez, al terminar la consulta (REQ-012, P6; plan 001,
"Modelo de datos", sección `queries`).

Un trigger rechaza todo UPDATE y DELETE sobre la tabla, venga del modelo, de
`QuerySet.update()`, `bulk_update`, `QuerySet.delete()` o de SQL directo, como en
`audit_event` (`audit/0002_append_only`). Para limpiar datos de prueba hay que recrear la
base.
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION queries_query_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro de consultas solo admite agregar consultas: una consulta registrada no se puede modificar ni borrar.';
END;
$$;

CREATE TRIGGER queries_query_insert_only
    BEFORE UPDATE OR DELETE ON queries_query
    FOR EACH ROW EXECUTE FUNCTION queries_query_reject_change();
"""

REVERSE = """
DROP TRIGGER queries_query_insert_only ON queries_query;
DROP FUNCTION queries_query_reject_change();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("queries", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
