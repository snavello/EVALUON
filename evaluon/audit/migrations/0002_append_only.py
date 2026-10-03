"""`audit_event` solo admite inserciones (REQ-012, P6; plan 001: "Solo se insertan filas").

Un trigger rechaza todo UPDATE y DELETE sobre la tabla, venga del modelo, de
`QuerySet.update()`, `bulk_update`, `QuerySet.delete()` o de SQL directo. Para limpiar
datos de prueba hay que recrear la base.
"""

from django.db import migrations

FORWARD = """
CREATE FUNCTION audit_event_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro de auditoría solo admite agregar hechos: un hecho registrado no se puede modificar ni borrar.';
END;
$$;

CREATE TRIGGER audit_event_append_only
    BEFORE UPDATE OR DELETE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_reject_change();
"""

REVERSE = """
DROP TRIGGER audit_event_append_only ON audit_event;
DROP FUNCTION audit_event_reject_change();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
