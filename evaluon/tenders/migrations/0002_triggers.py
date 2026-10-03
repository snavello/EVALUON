"""Reglas de la 003 que la base hace valer con triggers (plan 003, "Modelo de datos";
T-067).

1. **Solo inserción** (P6, REQ-026): `tenders_run_step` y `tenders_requirement_change`
   rechazan todo UPDATE y DELETE, como `audit_event` en la 001.
2. **Una versión validada no cambia** (REQ-027): UPDATE y DELETE sobre los requisitos,
   citas, fuentes, consecuencias y pendientes de una versión `validated` se rechazan,
   venga el cambio del modelo, de `QuerySet.update()` o de SQL directo. En un UPDATE se
   mira la versión de antes y la de después, para que una fila tampoco pueda pasar a
   una versión validada. La versión de una fila sale de su `version_id` o, en las tablas
   que cuelgan de un requisito, del `version_id` de su requisito. Además:
   - solo se insertan filas en esas cinco tablas si la versión es un borrador;
   - la fila de una versión validada o descartada no se modifica ni se borra; un
     borrador solo sale de ese estado hacia `validated` o `discarded` (quién y cuándo
     los exigen las restricciones de la tabla).
3. **Un formal o económico tiene exactamente una cita** (REQ-025). Una segunda cita, o
   pasar a formal o económico un requisito con más de una, se rechaza en el momento. Un
   formal o económico sin cita se rechaza al confirmar la transacción (trigger de
   restricción diferido): el requisito se inserta antes que su cita.

Para limpiar datos de prueba hay que recrear la base.
"""

from django.db import migrations

FORWARD = r"""
CREATE FUNCTION tenders_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % solo admite agregar filas: una fila registrada no se puede modificar ni borrar.', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER tenders_run_step_append_only
    BEFORE UPDATE OR DELETE ON tenders_run_step
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_change();

CREATE TRIGGER tenders_requirement_change_append_only
    BEFORE UPDATE OR DELETE ON tenders_requirement_change
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_change();


CREATE FUNCTION tenders_row_version_status(row_data jsonb, link text) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT v.status
    FROM tenders_matrix_version v
    WHERE v.id = CASE
        WHEN link = 'version_id' THEN (row_data->>'version_id')::bigint
        ELSE (
            SELECT r.version_id FROM tenders_requirement r
            WHERE r.id = (row_data->>'requirement_id')::bigint
        )
    END
$$;

CREATE FUNCTION tenders_reject_validated_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF tenders_row_version_status(to_jsonb(OLD), TG_ARGV[0]) = 'validated'
       OR (TG_OP = 'UPDATE'
           AND tenders_row_version_status(to_jsonb(NEW), TG_ARGV[0]) = 'validated') THEN
        RAISE EXCEPTION 'Una versión validada de la matriz no cambia (tabla %): para modificarla hay que abrir una versión nueva.', TG_TABLE_NAME;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION tenders_reject_insert_outside_draft() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF tenders_row_version_status(to_jsonb(NEW), TG_ARGV[0]) IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'Solo se agregan filas a un borrador de la matriz (tabla %): una versión validada o descartada no cambia.', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tenders_requirement_validated_fixed
    BEFORE UPDATE OR DELETE ON tenders_requirement
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_validated_change('version_id');

CREATE TRIGGER tenders_pending_item_validated_fixed
    BEFORE UPDATE OR DELETE ON tenders_pending_item
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_validated_change('version_id');

CREATE TRIGGER tenders_requirement_quote_validated_fixed
    BEFORE UPDATE OR DELETE ON tenders_requirement_quote
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_validated_change('requirement_id');

CREATE TRIGGER tenders_requirement_source_validated_fixed
    BEFORE UPDATE OR DELETE ON tenders_requirement_source
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_validated_change('requirement_id');

CREATE TRIGGER tenders_consequence_validated_fixed
    BEFORE UPDATE OR DELETE ON tenders_consequence
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_validated_change('requirement_id');

CREATE TRIGGER tenders_requirement_insert_in_draft
    BEFORE INSERT ON tenders_requirement
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_insert_outside_draft('version_id');

CREATE TRIGGER tenders_pending_item_insert_in_draft
    BEFORE INSERT ON tenders_pending_item
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_insert_outside_draft('version_id');

CREATE TRIGGER tenders_requirement_quote_insert_in_draft
    BEFORE INSERT ON tenders_requirement_quote
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_insert_outside_draft('requirement_id');

CREATE TRIGGER tenders_requirement_source_insert_in_draft
    BEFORE INSERT ON tenders_requirement_source
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_insert_outside_draft('requirement_id');

CREATE TRIGGER tenders_consequence_insert_in_draft
    BEFORE INSERT ON tenders_consequence
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_insert_outside_draft('requirement_id');

-- La fila de la versión: solo un borrador cambia, y un borrador solo sale de ese
-- estado hacia validada o descartada (quién y cuándo los exigen las restricciones de
-- la tabla). Una validada o descartada no se modifica ni se borra.
CREATE FUNCTION tenders_matrix_version_fixed() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'draft' THEN
        RAISE EXCEPTION 'Una versión % de la matriz no cambia: para modificarla hay que abrir una versión nueva.',
            CASE OLD.status WHEN 'validated' THEN 'validada' ELSE 'descartada' END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER tenders_matrix_version_fixed
    BEFORE UPDATE OR DELETE ON tenders_matrix_version
    FOR EACH ROW EXECUTE FUNCTION tenders_matrix_version_fixed();


CREATE FUNCTION tenders_quote_count(requirement bigint) RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT count(*) FROM tenders_requirement_quote q WHERE q.requirement_id = requirement
$$;

CREATE FUNCTION tenders_is_single_quote(requirement bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM tenders_requirement r
        WHERE r.id = requirement AND r.category IN ('formal', 'economico')
    )
$$;

-- En el momento: a lo sumo una cita.
CREATE FUNCTION tenders_reject_second_quote() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    requirement bigint;
BEGIN
    -- Con IF y no con CASE: PL/pgSQL compila cada rama recién al ejecutarla, y la fila
    -- de un requisito no tiene `requirement_id`.
    IF TG_TABLE_NAME = 'tenders_requirement' THEN
        requirement := NEW.id;
    ELSE
        requirement := NEW.requirement_id;
    END IF;
    IF tenders_is_single_quote(requirement) AND tenders_quote_count(requirement) > 1 THEN
        RAISE EXCEPTION 'Un requisito formal o económico tiene una sola cita (requisito %).', requirement;
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER tenders_requirement_quote_at_most_one
    AFTER INSERT OR UPDATE ON tenders_requirement_quote
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_second_quote();

CREATE TRIGGER tenders_requirement_category_at_most_one_quote
    AFTER UPDATE OF category ON tenders_requirement
    FOR EACH ROW EXECUTE FUNCTION tenders_reject_second_quote();

-- Al confirmar: exactamente una cita.
CREATE FUNCTION tenders_require_one_quote() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    requirement bigint;
BEGIN
    IF TG_TABLE_NAME = 'tenders_requirement' THEN
        requirement := NEW.id;
    ELSE
        requirement := OLD.requirement_id;
    END IF;
    IF tenders_is_single_quote(requirement) AND tenders_quote_count(requirement) <> 1 THEN
        RAISE EXCEPTION 'Un requisito formal o económico tiene exactamente una cita (requisito %).', requirement;
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER tenders_requirement_exactly_one_quote
    AFTER INSERT OR UPDATE ON tenders_requirement
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION tenders_require_one_quote();

CREATE CONSTRAINT TRIGGER tenders_requirement_quote_exactly_one
    AFTER UPDATE OR DELETE ON tenders_requirement_quote
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION tenders_require_one_quote();
"""

REVERSE = r"""
DROP TRIGGER tenders_requirement_quote_exactly_one ON tenders_requirement_quote;
DROP TRIGGER tenders_requirement_exactly_one_quote ON tenders_requirement;
DROP FUNCTION tenders_require_one_quote();
DROP TRIGGER tenders_requirement_category_at_most_one_quote ON tenders_requirement;
DROP TRIGGER tenders_requirement_quote_at_most_one ON tenders_requirement_quote;
DROP FUNCTION tenders_reject_second_quote();
DROP FUNCTION tenders_is_single_quote(bigint);
DROP FUNCTION tenders_quote_count(bigint);

DROP TRIGGER tenders_matrix_version_fixed ON tenders_matrix_version;
DROP FUNCTION tenders_matrix_version_fixed();

DROP TRIGGER tenders_consequence_insert_in_draft ON tenders_consequence;
DROP TRIGGER tenders_requirement_source_insert_in_draft ON tenders_requirement_source;
DROP TRIGGER tenders_requirement_quote_insert_in_draft ON tenders_requirement_quote;
DROP TRIGGER tenders_pending_item_insert_in_draft ON tenders_pending_item;
DROP TRIGGER tenders_requirement_insert_in_draft ON tenders_requirement;
DROP FUNCTION tenders_reject_insert_outside_draft();

DROP TRIGGER tenders_consequence_validated_fixed ON tenders_consequence;
DROP TRIGGER tenders_requirement_source_validated_fixed ON tenders_requirement_source;
DROP TRIGGER tenders_requirement_quote_validated_fixed ON tenders_requirement_quote;
DROP TRIGGER tenders_pending_item_validated_fixed ON tenders_pending_item;
DROP TRIGGER tenders_requirement_validated_fixed ON tenders_requirement;
DROP FUNCTION tenders_reject_validated_change();
DROP FUNCTION tenders_row_version_status(jsonb, text);

DROP TRIGGER tenders_requirement_change_append_only ON tenders_requirement_change;
DROP TRIGGER tenders_run_step_append_only ON tenders_run_step;
DROP FUNCTION tenders_reject_change();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("tenders", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
