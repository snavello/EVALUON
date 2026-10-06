"""Reglas de la 004 que la base hace valer con triggers (plan 004, "Modelo de datos";
ADR-0039; T-148).

**Solo inserción** (P6, P3): las ocho tablas de la evaluación rechazan todo UPDATE y DELETE,
venga el cambio del modelo, de `QuerySet.update()` o de SQL directo, como `offers_change` en
la 008. Un resultado nuevo no pisa al anterior: se inserta otro; una decisión, una pregunta
o una respuesta nuevas tampoco pisan a las anteriores.

Para limpiar datos de prueba hay que recrear la base.
"""

from django.db import migrations

TABLES = (
    "assessment_request",
    "assessment_run",
    "assessment_result",
    "assessment_citation",
    "assessment_step",
    "assessment_decision",
    "assessment_question",
    "assessment_answer",
)

FORWARD = r"""
CREATE FUNCTION assessment_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % solo admite agregar filas: una fila registrada no se puede modificar ni borrar.', TG_TABLE_NAME;
END;
$$;
""" + "".join(
    f"""
CREATE TRIGGER {table}_append_only
    BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION assessment_reject_change();
"""
    for table in TABLES
)

REVERSE = "".join(f"DROP TRIGGER {table}_append_only ON {table};\n" for table in TABLES) + (
    "DROP FUNCTION assessment_reject_change();\n"
)


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
