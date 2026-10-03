"""Búsqueda directa por norma y número de artículo, y por palabras (REQ-005, REQ-006,
REQ-010, REQ-020; plan 001, "Búsqueda directa (REQ-010)", "Identificación de unidades" y
"Unidades consultables a una fecha"). T-035.

Sin modelos de IA. Las dos búsquedas leen siempre de `consultable_units(fecha)`, con la
fecha de autorización del procedimiento que reciben: nunca usan la fecha del día y, sin
fecha, no buscan. Así una norma sin validar (REQ-005), un documento fuera de uso y una
norma que todavía no regía a la fecha no aparecen. A diferencia de la consulta, la
búsqueda devuelve también las unidades derogadas a la fecha, marcadas.

- `by_article(norma, número, fecha, subsection="")`: las unidades de tipo `articulo` con
  ese número en todos los documentos en uso de la norma (cuerpo y anexos, en uno o en
  varios archivos), cada una con su ruta. Con `subsection`, los incisos con ese número
  dentro de esos artículos. El número se compara sin espacios de más, sin distinguir
  mayúsculas y sin el signo de grado; un número vacío no busca (las cláusulas sin número
  tienen `number` vacío y no salen por acá).
- `by_words(texto, fecha, norm_id=None)`: búsqueda de texto sobre los pasajes con
  `tsv @@ search_query(texto)` (ADR-0007): sin distinguir acentos ni singular y plural,
  con comillas para frase exacta. Agrupada por unidad base (los pasajes son solo de
  unidades base). El número de la norma no se busca por palabras: la norma se filtra con
  `norm_id`.

Cada resultado (`SearchResult`) trae la categoría de su norma, el texto literal de la
unidad (el tramo `canonical_text[char_start:char_end]` de su lectura, no la copia de
`norms_unit.text`), el documento, la marca de derogada a la fecha con la relación, la
norma que la derogó y desde cuándo (de `consultable_units`), los cambios vigentes a la
fecha (de `unit_changes`, que no incluye las relaciones sobre la norma entera: esas se ven
como vínculo y, si son `deroga`, en la marca; el texto de la unidad de origen es también
su tramo del texto canónico) y los vínculos de su norma con otras, en los dos sentidos:
todos los registrados, sin filtro de fecha (REQ-006), cada uno con la fecha desde la que
rige. Orden: por norma, primero el cuerpo y después los anexos,
y dentro de cada parte en el orden del documento.

La pantalla, la línea de régimen y el registro de la búsqueda son de T-041; los avisos de
modificatorias sin cargar, de T-052.
"""

from dataclasses import asdict, dataclass
from datetime import date

from django.db import connection

# Sentido de un vínculo visto desde la norma del resultado.
OUTGOING = "outgoing"  # la norma del resultado es la de origen
INCOMING = "incoming"  # la norma del resultado es la alcanzada

_ARTICLE_SQL = """
SELECT u.id
FROM consultable_units(%(date)s) cu
JOIN norms_unit u ON u.id = cu.unit_id
WHERE cu.norm_id = %(norm)s
  AND u.unit_type = 'articulo'
  AND lower(u.number) = %(number)s
"""

_SUBSECTION_SQL = """
SELECT i.id
FROM consultable_units(%(date)s) cu
JOIN norms_unit a ON a.id = cu.unit_id
JOIN consultable_units(%(date)s) ci ON ci.reading_id = cu.reading_id
JOIN norms_unit i ON i.id = ci.unit_id
WHERE cu.norm_id = %(norm)s
  AND a.unit_type = 'articulo'
  AND lower(a.number) = %(number)s
  AND i.unit_type = 'inciso'
  AND lower(i.number) = %(subsection)s
  AND starts_with(i.key, a.key || '/')
"""

_WORDS_SQL = """
SELECT DISTINCT p.unit_id
FROM norms_passage p
JOIN consultable_units(%(date)s) cu ON cu.unit_id = p.unit_id
WHERE p.tsv @@ search_query(%(text)s)
  AND (%(norm)s::bigint IS NULL OR cu.norm_id = %(norm)s::bigint)
"""

_UNITS_SQL = """
SELECT u.id, u.key, u.path, u.unit_type, u.number,
       substr(r.canonical_text, u.char_start + 1, u.char_end - u.char_start),
       u.text_origin,
       cu.norm_id, n.citation, n.category, cu.document_id, d.part,
       cu.repealed, cu.repealed_by_relation_id, cu.repealed_by_norm_id, rn.citation,
       cu.repealed_since
FROM consultable_units(%(date)s) cu
JOIN norms_unit u ON u.id = cu.unit_id
JOIN norms_reading r ON r.id = cu.reading_id
JOIN norms_document d ON d.id = cu.document_id
JOIN norms_norm n ON n.id = cu.norm_id
LEFT JOIN norms_norm rn ON rn.id = cu.repealed_by_norm_id
WHERE cu.unit_id = ANY(%(units)s)
ORDER BY cu.norm_id, d.part <> 'cuerpo', d.part, u."order", u.id
"""

_CHANGES_SQL = """
SELECT uc.unit_id, uc.relation_id, uc.relation_type, uc.target_unit_key,
       uc.effective_date, uc.source_norm_id, sn.citation, uc.source_unit_key,
       uc.source_unit_id, su.path,
       substr(sr.canonical_text, su.char_start + 1, su.char_end - su.char_start)
FROM unit_changes(%(date)s) uc
JOIN norms_norm sn ON sn.id = uc.source_norm_id
LEFT JOIN norms_unit su ON su.id = uc.source_unit_id
LEFT JOIN norms_reading sr ON sr.id = su.reading_id
WHERE uc.unit_id = ANY(%(units)s)
ORDER BY uc.unit_id, uc.effective_date, uc.relation_id
"""

_LINKS_SQL = """
SELECT rel.id, rel.relation_type, rel.source_norm_id, sn.citation,
       rel.target_norm_id, tn.citation, rel.source_unit_key, rel.target_unit_key,
       rel.effective_date
FROM norms_relation rel
JOIN norms_norm sn ON sn.id = rel.source_norm_id
JOIN norms_norm tn ON tn.id = rel.target_norm_id
WHERE rel.source_norm_id = ANY(%(norms)s) OR rel.target_norm_id = ANY(%(norms)s)
ORDER BY rel.effective_date, rel.id
"""


@dataclass(frozen=True)
class Repeal:
    """La derogación que alcanza a la unidad a la fecha: relación, norma que la derogó y
    desde cuándo."""

    relation_id: int
    norm_id: int
    norm_name: str
    since: date


@dataclass(frozen=True)
class Change:
    """Una relación `modifica` o `deroga` vigente a la fecha que alcanza a la unidad o a
    una unidad contenida en ella. `source_unit_*` vacíos si la relación viene de la
    norma entera o si esa unidad no es consultable a la fecha."""

    relation_id: int
    relation_type: str
    target_unit_key: str
    effective_date: date
    source_norm_id: int
    source_norm_name: str
    source_unit_key: str
    source_unit_id: int | None
    source_unit_path: str | None
    source_unit_text: str | None


@dataclass(frozen=True)
class Link:
    """Una relación registrada de la norma del resultado con otra, rija o no a la fecha
    de la búsqueda (REQ-006); `effective_date` dice desde cuándo rige."""

    relation_id: int
    relation_type: str
    direction: str
    other_norm_id: int
    other_norm_name: str
    source_unit_key: str
    target_unit_key: str
    effective_date: date


@dataclass(frozen=True)
class SearchResult:
    """Una unidad encontrada, con lo que la pantalla muestra de ella."""

    unit_id: int
    key: str
    path: str
    unit_type: str
    number: str
    text: str
    text_origin: str
    norm_id: int
    norm_name: str
    category: str
    document_id: int
    document_part: str
    repealed: bool
    repealed_by: Repeal | None
    changes: tuple[Change, ...]
    links: tuple[Link, ...]

    def as_record(self):
        """El resultado como diccionario serializable en JSON, con las fechas en formato
        ISO, para el registro de la búsqueda (P6)."""
        return _jsonable(asdict(self))


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _require_date(reference_date):
    if reference_date is None:
        raise ValueError(
            "La búsqueda necesita la fecha de autorización del procedimiento."
        )


def _normalize_number(number):
    """Número escrito por la persona, para compararlo con `norms_unit.number`: sin
    espacios de más, en minúsculas y sin el signo de grado."""
    return " ".join((number or "").replace("°", " ").replace("º", " ").split()).lower()


def by_article(norm_id, number, reference_date, *, subsection=""):
    """Unidades de tipo `articulo` con `number` de la norma `norm_id` consultables en
    `reference_date` (o, con `subsection`, sus incisos con ese número). Ver el módulo."""
    _require_date(reference_date)
    number = _normalize_number(number)
    subsection = _normalize_number(subsection)
    if not number:
        return []
    params = {"date": reference_date, "norm": norm_id, "number": number,
              "subsection": subsection}
    sql = _SUBSECTION_SQL if subsection else _ARTICLE_SQL
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        unit_ids = [unit_id for (unit_id,) in cursor.fetchall()]
    return _results(unit_ids, reference_date)


def by_words(text, reference_date, *, norm_id=None):
    """Unidades base consultables en `reference_date` con algún pasaje que coincide con
    `text` según `search_query`, de cualquier norma o solo de `norm_id`. Ver el
    módulo."""
    _require_date(reference_date)
    if not (text or "").strip():
        return []
    with connection.cursor() as cursor:
        cursor.execute(_WORDS_SQL,
                       {"date": reference_date, "text": text, "norm": norm_id})
        unit_ids = [unit_id for (unit_id,) in cursor.fetchall()]
    return _results(unit_ids, reference_date)


def _results(unit_ids, reference_date):
    """Arma los resultados de las unidades `unit_ids` con su marca de derogada, sus
    cambios a `reference_date` y todos los vínculos registrados de su norma."""
    if not unit_ids:
        return []
    params = {"date": reference_date, "units": list(unit_ids)}
    with connection.cursor() as cursor:
        cursor.execute(_UNITS_SQL, params)
        units = cursor.fetchall()
        cursor.execute(_CHANGES_SQL, params)
        change_rows = cursor.fetchall()
        norms = sorted({row[7] for row in units})
        cursor.execute(_LINKS_SQL, {"norms": norms})
        link_rows = cursor.fetchall()

    changes = {}
    for unit_id, *fields in change_rows:
        changes.setdefault(unit_id, []).append(Change(*fields))

    links = {}
    for (relation_id, relation_type, source_norm, source_name, target_norm,
         target_name, source_key, target_key, effective_date) in link_rows:
        for norm, direction, other, other_name in (
            (source_norm, OUTGOING, target_norm, target_name),
            (target_norm, INCOMING, source_norm, source_name),
        ):
            links.setdefault(norm, []).append(Link(
                relation_id=relation_id, relation_type=relation_type,
                direction=direction, other_norm_id=other, other_norm_name=other_name,
                source_unit_key=source_key, target_unit_key=target_key,
                effective_date=effective_date,
            ))

    results = []
    for (unit_id, key, path, unit_type, number, unit_text, text_origin, norm_id,
         norm_name, category, document_id, part, repealed, repeal_relation,
         repeal_norm, repeal_norm_name, repeal_since) in units:
        results.append(SearchResult(
            unit_id=unit_id, key=key, path=path, unit_type=unit_type, number=number,
            text=unit_text, text_origin=text_origin, norm_id=norm_id,
            norm_name=norm_name, category=category, document_id=document_id,
            document_part=part, repealed=repealed,
            repealed_by=Repeal(repeal_relation, repeal_norm, repeal_norm_name,
                               repeal_since) if repealed else None,
            changes=tuple(changes.get(unit_id, ())),
            links=tuple(links.get(norm_id, ())),
        ))
    return results
