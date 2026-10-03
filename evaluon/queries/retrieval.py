"""Recuperación de unidades para una consulta (plan 001, "Recuperación", "Reordenamiento"
y "Abstención"; ADR-0003, ADR-0007). T-017 dejó el camino por significado; T-032 suma los
caminos por palabras y por referencia exacta y la unión de los tres.

`retrieve(pregunta, fecha, paths=ALL_PATHS, rerank=True)`:

1. Tres caminos, cada uno sobre los pasajes de las unidades de `consultable_units(fecha)`
   con `repealed` falso. Así una norma sin validar (REQ-005), un documento fuera de uso
   o fuera de vigencia y una unidad derogada a la fecha (REQ-020) no entran por ninguno.
   - Por significado (`semantic`): el vector de la pregunta contra los vectores de los
     pasajes, distancia coseno, búsqueda exacta; los `RETRIEVAL_CANDIDATES_PER_PATH`
     más cercanos.
   - Por palabras (`words`): `tsv @@ search_query(...)` (ADR-0007) con las palabras de
     la pregunta unidas por "or"; los `RETRIEVAL_CANDIDATES_PER_PATH` de mejor
     `ts_rank`. `tsv` es solo del texto del pasaje, sin el encabezado.
   - Por referencia exacta (`reference`): `find_references` detecta en la pregunta
     números de artículo ("artículo 23", "art. 5 inc. b", "14 bis") y normas por número
     y año ("Disposición 297/03", "297/2003", "Disposición 247/2022"). Trae todos los
     pasajes de las unidades `articulo` con esos números, de todas las partes de la
     norma; si la pregunta nombra normas, solo de esas (la norma se identifica por sus
     campos `number` y `year`, no por palabras). Si nombra un inciso, entra el artículo
     que lo contiene. Una norma nombrada sin artículo no trae unidades.
2. Unión sin repetir pasajes y sin fórmula de fusión: en el orden de los caminos
   (significado, palabras, referencia) y, dentro de cada uno, en su orden. Cada candidato
   anota por qué caminos entró y, si entró por significado, su distancia.
3. El reranker puntúa cada pasaje (`indexing.passage_document`: encabezado más texto)
   contra la pregunta, en un solo pedido; el cliente devuelve el puntaje entre 0 y 1.
4. Agrupa los pasajes por unidad base con el mejor puntaje de sus pasajes (los incisos
   no generan pasajes: la unidad del pasaje es su unidad base).
5. Primera barrera de abstención: si ninguna unidad alcanza `RERANK_THRESHOLD` (puntaje
   igual o mayor), no hay seleccionadas y el motivo es `below_threshold` (REQ-009).
6. Pasan las unidades que alcanzan el umbral, de mayor a menor puntaje.

Comparación quitando piezas (ADR-0003, evals): `paths` dice qué caminos se corren y
`rerank=False` apaga el reranker. Sin reranker no hay puntajes: las unidades quedan en
el orden de la unión, todas pasan y no hay barrera de umbral (`max_score` vacío).

La fecha es siempre la de autorización del procedimiento que recibe quien llama: esta
función no usa la fecha del día y, sin fecha, no busca.

`select_units(resultado, prompt_tokens)` (T-033) toma las unidades que pasaron y arma lo
que se le muestra al modelo (plan, "Reordenamiento", pasos 4 a 7): cupos por categoría,
cambios por relación, espacio del contexto y orden de entrega. Ver su docstring.

Los clientes se usan por su módulo (`embeddings.embed`, `reranker.rerank`,
`generation.count_tokens`) para que los dobles de las pruebas los reemplacen. Sus errores
propios (`evaluon.ai`) no se atrapan acá: son fallas técnicas que resuelve quien llama.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.db import connection

from evaluon.ai import embeddings, generation, reranker
from evaluon.norms import indexing
from evaluon.norms.models import Passage, Unit, UnitType
from evaluon.queries import answering

# Caminos por los que entra un candidato, en el orden de la unión.
SEMANTIC = "semantic"
WORDS = "words"
REFERENCE = "reference"
ALL_PATHS = (SEMANTIC, WORDS, REFERENCE)

# Motivo de la primera barrera de abstención (plan 001, "Abstención").
BELOW_THRESHOLD = "below_threshold"

_CONSULTABLE = """
FROM norms_passage p
JOIN consultable_units(%s) cu ON cu.unit_id = p.unit_id
"""

_SEMANTIC_SQL = f"""
SELECT p.id, p.unit_id, p.header, p.text, p.embedding <=> %s::vector AS distance
{_CONSULTABLE}
WHERE NOT cu.repealed
ORDER BY distance, p.id
LIMIT %s
"""

_WORDS_SQL = f"""
SELECT p.id, p.unit_id, p.header, p.text
{_CONSULTABLE}
CROSS JOIN search_query(%s) q
WHERE NOT cu.repealed AND p.tsv @@ q
ORDER BY ts_rank(p.tsv, q) DESC, p.id
LIMIT %s
"""

_REFERENCE_SQL = f"""
SELECT p.id, p.unit_id, p.header, p.text
{_CONSULTABLE}
JOIN norms_unit u ON u.id = p.unit_id
JOIN norms_norm n ON n.id = cu.norm_id
WHERE NOT cu.repealed
  AND u.unit_type = 'articulo'
  AND u.number = ANY(%s)
  AND ({{norms}})
ORDER BY cu.norm_id, cu.document_id, u."order", p."order", p.id
"""

# Una norma nombrada: número sin puntos y año, de dos o de cuatro cifras.
_NORM_SQL = "(replace(n.number, '.', '') = %s AND {year})"
_YEAR_4_SQL = "n.year = %s"
_YEAR_2_SQL = "mod(n.year, 100) = %s"


# --- Referencias exactas -------------------------------------------------------------

# Se buscan sobre la pregunta en minúsculas y sin tildes (ver `_plain`).
_SUFFIX = r"(?:bis|ter|quater|quinquies)"
_ARTICLE_RE = re.compile(
    r"\bart(?:iculo|\.)?\s*(?:n\s*[°º.]+\s*)?(\d+)(?:\s*[°º])?"
    rf"(?:\s+({_SUFFIX})\b)?"
)
_SUFFIXED_RE = re.compile(rf"\b(\d+)\s+({_SUFFIX})\b")
# Número y año con barra, que no sea parte de una fecha ("15/03/2021"). El número puede
# llevar puntos de miles ("13.064/47").
_NORM_RE = re.compile(
    r"(?<![\d/.])(\d{1,3}(?:\.\d{3})+|\d+)\s*/\s*(\d{4}|\d{2})(?![\d/])"
)


@dataclass(frozen=True)
class NormReference:
    """Una norma nombrada en la pregunta: número sin puntos, año como figura y cuántas
    cifras tiene (2 o 4)."""

    number: str
    year: int
    year_digits: int


@dataclass(frozen=True)
class References:
    """Lo que el patrón de referencia exacta encontró en la pregunta: números de
    artículo normalizados como `norms_unit.number` ("23", "14 bis") y normas."""

    articles: frozenset = frozenset()
    norms: frozenset = frozenset()


def _plain(text):
    """Minúsculas y sin tildes. Descomposición canónica (NFD), para que "º" no pase a
    "o"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _article_number(digits, suffix):
    number = str(int(digits))
    return f"{number} {suffix}" if suffix else number


def find_references(question):
    """Referencias exactas de la pregunta: artículos y normas (plan 001, "Recuperación").
    Un inciso nombrado no se devuelve: entra el artículo que lo contiene."""
    text = _plain(question)
    articles = {_article_number(m.group(1), m.group(2))
                for pattern in (_ARTICLE_RE, _SUFFIXED_RE)
                for m in pattern.finditer(text)}
    norms = {
        NormReference(number=m.group(1).replace(".", ""), year=int(m.group(2)),
                      year_digits=len(m.group(2)))
        for m in _NORM_RE.finditer(text)
    }
    return References(articles=frozenset(articles), norms=frozenset(norms))


# --- Palabras --------------------------------------------------------------------------

_WORD_RE = re.compile(r"\w+(?:/\w+)*")


def _words_query(question):
    """Las palabras de la pregunta unidas por "or", para `search_query`. Solo letras,
    números y barras ("297/03"): comillas y guiones no se leen como frase ni exclusión.
    Vacío si la pregunta no tiene palabras."""
    words = []
    for word in _WORD_RE.findall(question):
        if word.lower() != "or" and word not in words:
            words.append(word)
    return " or ".join(words)


# --- Resultado -----------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """Un pasaje recuperado: por qué caminos entró (en el orden de `ALL_PATHS`), qué
    puntaje le dio el reranker (vacío sin reranker) y, si entró por significado, a qué
    distancia de la pregunta estaba."""

    passage_id: int
    unit_id: int
    path: tuple
    score: float | None
    distance: float | None = None

    def as_record(self):
        return {"passage": self.passage_id, "unit": self.unit_id, "path": list(self.path),
                "distance": self.distance, "score": self.score}


@dataclass(frozen=True)
class UnitScore:
    """Una unidad base con el mejor puntaje de sus pasajes (vacío sin reranker) y los
    pasajes que aportó."""

    unit_id: int
    score: float | None
    passage_ids: tuple = ()

    def as_record(self):
        return {"unit": self.unit_id, "score": self.score,
                "passages": list(self.passage_ids)}


@dataclass(frozen=True)
class RetrievalResult:
    """Resultado de la recuperación.

    - `candidates`: cada pasaje recuperado, una vez, en el orden de la unión.
    - `units`: cada unidad base candidata con su mejor puntaje, de mayor a menor (sin
      reranker, en el orden de la unión).
    - `selected`: las unidades de `units` que alcanzan el umbral (sin reranker, todas).
    - `max_score`: el puntaje más alto, o `None` si no hubo candidatos o reranker.
    - `reason`: `below_threshold` si ninguna unidad pasa; si no, `None`.
    - `parameters`: los parámetros de búsqueda usados, con los caminos y el reranker.
    - `path_counts`: por cada camino corrido, cuántos pasajes y cuántas unidades
      distintas trajo (para ver si unas pocas unidades largas llenan un camino).
    """

    reference_date: object
    candidates: list = field(default_factory=list)
    units: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    max_score: float | None = None
    reason: str | None = None
    parameters: dict = field(default_factory=dict)
    path_counts: dict = field(default_factory=dict)

    def as_record(self):
        """El resultado en datos que se pueden guardar como JSON en el registro (P6)."""
        return {
            "reference_date": self.reference_date.isoformat(),
            "parameters": dict(self.parameters),
            "path_counts": {path: dict(counts)
                            for path, counts in self.path_counts.items()},
            "candidates": [c.as_record() for c in self.candidates],
            "units": [u.as_record() for u in self.units],
            "selected": [u.as_record() for u in self.selected],
            "max_score": self.max_score,
            "reason": self.reason,
        }


# --- Caminos -------------------------------------------------------------------------


def _vector_literal(vector):
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def _semantic_passages(question, reference_date, limit):
    """Filas `(pasaje, unidad, encabezado, texto, distancia)`."""
    [vector] = embeddings.embed([question])
    return _fetch(_SEMANTIC_SQL, [_vector_literal(vector), reference_date, limit])


def _word_passages(question, reference_date, limit):
    """Filas `(pasaje, unidad, encabezado, texto)`."""
    query = _words_query(question)
    if not query:
        return []
    return _fetch(_WORDS_SQL, [reference_date, query, limit])


def _reference_passages(question, reference_date):
    """Filas `(pasaje, unidad, encabezado, texto)`."""
    references = find_references(question)
    if not references.articles:
        return []
    params = [reference_date, sorted(references.articles)]
    if references.norms:
        clauses = []
        for norm in sorted(references.norms, key=lambda r: (r.number, r.year)):
            year = _YEAR_4_SQL if norm.year_digits == 4 else _YEAR_2_SQL
            clauses.append(_NORM_SQL.format(year=year))
            params += [norm.number, norm.year]
        norms = " OR ".join(clauses)
    else:
        norms = "true"
    return _fetch(_REFERENCE_SQL.format(norms=norms), params)


# --- Recuperación ----------------------------------------------------------------------


def retrieve(question, reference_date, *, paths=ALL_PATHS, rerank=True):
    """Recupera y reordena las unidades para `question` según lo que regía en
    `reference_date`, la fecha de autorización del procedimiento. `paths` elige los
    caminos (de `ALL_PATHS`) y `rerank` el reranker. Ver el módulo."""
    if reference_date is None:
        raise ValueError(
            "La recuperación necesita la fecha de autorización del procedimiento."
        )
    unknown = set(paths) - set(ALL_PATHS)
    if unknown:
        raise ValueError(f"Caminos de recuperación desconocidos: {sorted(unknown)}.")
    paths = [path for path in ALL_PATHS if path in paths]
    threshold = settings.RERANK_THRESHOLD
    limit = settings.RETRIEVAL_CANDIDATES_PER_PATH
    parameters = {"candidates_per_path": limit, "rerank_threshold": threshold,
                  "paths": list(paths), "reranker": rerank}

    # Unión sin repetir: pasaje -> datos, en el orden en que entró por primera vez.
    union = {}
    path_counts = {}
    for path in paths:
        if path == SEMANTIC:
            rows = _semantic_passages(question, reference_date, limit)
        elif path == WORDS:
            rows = _word_passages(question, reference_date, limit)
        else:
            rows = _reference_passages(question, reference_date)
        path_counts[path] = {"passages": len(rows),
                             "units": len({row[1] for row in rows})}
        for row in rows:
            passage_id, unit_id, header, text = row[:4]
            entry = union.setdefault(passage_id, {
                "unit_id": unit_id, "header": header, "text": text, "paths": [],
                "distance": None,
            })
            entry["paths"].append(path)
            if path == SEMANTIC:
                entry["distance"] = float(row[4])

    entries = list(union.items())
    if rerank:
        scores = reranker.rerank(
            question, [indexing.passage_document(e["header"], e["text"])
                       for _, e in entries]
        )
        scores = [float(score) for score in scores]
    else:
        scores = [None] * len(entries)
    candidates = [
        Candidate(passage_id=passage_id, unit_id=e["unit_id"], path=tuple(e["paths"]),
                  score=score, distance=e["distance"])
        for (passage_id, e), score in zip(entries, scores)
    ]

    units = _group_by_unit(candidates, rerank)
    if rerank:
        selected = [unit for unit in units if unit.score >= threshold]
        max_score = units[0].score if units else None
    else:
        selected = list(units)
        max_score = None

    return RetrievalResult(
        reference_date=reference_date,
        candidates=candidates,
        units=units,
        selected=selected,
        max_score=max_score,
        reason=None if selected else BELOW_THRESHOLD,
        parameters=parameters,
        path_counts=path_counts,
    )


def _group_by_unit(candidates, ranked):
    """Agrupa los pasajes por unidad base. Con puntajes, cada unidad lleva el mejor y se
    ordenan de mayor a menor; sin puntajes, quedan en el orden de la unión."""
    passages = {}
    best = {}
    for candidate in candidates:
        passages.setdefault(candidate.unit_id, []).append(candidate.passage_id)
        if ranked:
            best[candidate.unit_id] = max(best.get(candidate.unit_id, candidate.score),
                                          candidate.score)
    units = [UnitScore(unit_id, best.get(unit_id), tuple(ids))
             for unit_id, ids in passages.items()]
    if ranked:
        units.sort(key=lambda unit: (-unit.score, unit.unit_id))
    return units


# --- Selección (T-033) -----------------------------------------------------------------

# Unidades que traen un cambio a la fecha (plan, "Reordenamiento", paso 5). Sin unidad de
# origen (relación desde la norma entera, o unidad no consultable) no hay nada que sumar.
_CHANGE_SOURCES_SQL = """
SELECT unit_id, source_unit_id
FROM unit_changes(%s)
WHERE unit_id = ANY(%s) AND source_unit_id IS NOT NULL AND source_unit_id <> unit_id
ORDER BY unit_id, effective_date, relation_id
"""

# Grupo de cupo y de espacio de los considerandos, aparte de las categorías.
_CONSIDERANDOS = "considerandos"


@dataclass(frozen=True)
class Selection:
    """Lo que se le muestra al modelo, listo para `answering.answer` (T-040):

        answering.answer(pregunta, sel.unit_ids, fecha, passages=sel.passages)

    - `unit_ids`: las unidades seleccionadas que entraron, en el orden de entrega
      (régimen específico, otra normativa aplicable, marco nacional, dictamen legal,
      recomendación de auditoría; dentro de cada una, por puntaje, o en el orden de la
      unión sin reranker; los considerandos al final). No incluye las agregadas por
      relación: `answer` las busca sola con `unit_changes` y las muestra a continuación
      de la que modifican.
    - `passages`: `{id de unidad: [(char_start, char_end), …]}`, tramos relativos al
      texto de la unidad, en orden de texto, solo para las unidades más largas que
      `UNIT_BY_PASSAGES_FROM_TOKENS` que se muestran por pasajes. Puede traer unidades
      agregadas por relación.
    - `added`: unidades que entraron por relación y no por parecido y no están en
      `unit_ids`: `[{"unit": id, "modifies": [ids de unit_ids]}]`.
    - `over_quota`: ids de las unidades que alcanzaron el umbral y quedaron afuera por
      el cupo de su categoría o el de considerandos, en el orden en que llegaron.
    - `left_out`: unidades seleccionadas que quedaron afuera por espacio, en el orden en
      que se intentaron: `[{"unit": id, "tokens": n}]`, con `n` lo que costaba la unidad
      junto con las que la modifican y todavía no habían entrado.
    - `tokens`: `{id: tokens}` de cada unidad contada (las que pasaron el cupo y las que
      las modifican), sobre `answering.prompt_text(unidad, tramos)`.
    - `prompt_tokens`: los tokens de las instrucciones con la pregunta que informó quien
      llama; `available_tokens`: el espacio para unidades; `used_tokens`: lo que ocupan
      las que entraron, contando las agregadas por relación.
    - `parameters`: los parámetros de `settings.py` usados.

    `unit_ids` vacío con `left_out` no vacío quiere decir que ninguna unidad entró en el
    espacio: no es un "no determinado" por umbral; lo resuelve quien llama.
    """

    unit_ids: list = field(default_factory=list)
    passages: dict = field(default_factory=dict)
    added: list = field(default_factory=list)
    over_quota: list = field(default_factory=list)
    left_out: list = field(default_factory=list)
    tokens: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    available_tokens: int = 0
    used_tokens: int = 0
    parameters: dict = field(default_factory=dict)

    def as_record(self):
        """La selección en datos que se pueden guardar como JSON en el registro (P6)."""
        return {
            "units": list(self.unit_ids),
            "passages": {str(unit_id): [list(span) for span in spans]
                         for unit_id, spans in self.passages.items()},
            "added": [{"unit": a["unit"], "modifies": list(a["modifies"])}
                      for a in self.added],
            "over_quota": list(self.over_quota),
            "left_out": [dict(entry) for entry in self.left_out],
            "tokens": {str(unit_id): n for unit_id, n in self.tokens.items()},
            "prompt_tokens": self.prompt_tokens,
            "available_tokens": self.available_tokens,
            "used_tokens": self.used_tokens,
            "parameters": dict(self.parameters),
        }


def _group(unit):
    """Grupo de cupo y de espacio: la categoría de su norma, o los considerandos."""
    if unit.unit_type == UnitType.CONSIDERANDO:
        return _CONSIDERANDOS
    return unit.reading.document.norm.category


def _apply_quotas(units):
    """Hasta `SELECTION_UNITS_PER_CATEGORY` por categoría y `SELECTION_CONSIDERANDOS`
    considerandos en total, en el orden recibido. Devuelve las que entran y los ids de
    las que no."""
    chosen, over_quota, counts = [], [], {}
    for unit in units:
        group = _group(unit)
        limit = (settings.SELECTION_CONSIDERANDOS if group == _CONSIDERANDOS
                 else settings.SELECTION_UNITS_PER_CATEGORY)
        if counts.get(group, 0) < limit:
            counts[group] = counts.get(group, 0) + 1
            chosen.append(unit)
        else:
            over_quota.append(unit.pk)
    return chosen, over_quota


def _priority(units):
    """Orden en que se reparte el espacio: la mejor de cada categoría (en el orden de las
    categorías), después la segunda de cada una, y así; los considerandos después de todo
    el articulado, para que un fundamento no desplace a un artículo."""
    groups = {category: [] for category in answering.CATEGORY_ORDER}
    considerandos = []
    for unit in units:
        group = _group(unit)
        (considerandos if group == _CONSIDERANDOS else groups[group]).append(unit)
    rounds = max((len(g) for g in groups.values()), default=0)
    articulado = [g[i] for i in range(rounds) for g in groups.values() if i < len(g)]
    return articulado + considerandos


def _modifiers(reference_date, unit_ids):
    """`{id de unidad: [ids de las unidades que la modifican o derogan en parte]}` a la
    fecha, por relación (`unit_changes`), sin repetir."""
    if not unit_ids:
        return {}
    by_unit = {}
    rows = _fetch(_CHANGE_SOURCES_SQL, [reference_date, list(unit_ids)])
    for unit_id, source_id in rows:
        sources = by_unit.setdefault(unit_id, [])
        if source_id not in sources:
            sources.append(source_id)
    return by_unit


def _passing_spans(result):
    """`{id de unidad: [(char_start, char_end), …]}` de los pasajes candidatos que
    alcanzaron el umbral (sin reranker, todos los candidatos), en orden de texto."""
    threshold = result.parameters.get("rerank_threshold", settings.RERANK_THRESHOLD)
    passing = [c.passage_id for c in result.candidates
               if c.score is None or c.score >= threshold]
    spans = {}
    rows = Passage.objects.filter(pk__in=passing).values_list("unit_id", "char_start",
                                                              "char_end")
    for unit_id, start, end in rows:
        spans.setdefault(unit_id, []).append((start, end))
    return {unit_id: sorted(found) for unit_id, found in spans.items()}


def select_units(result, prompt_tokens):
    """Selección de las unidades que se le muestran al modelo, a partir de un
    `RetrievalResult` (plan 001, "Reordenamiento", pasos 4 a 7, y "Conteo de tokens").
    `prompt_tokens` son los tokens de las instrucciones con la pregunta, contados por
    quien llama con `generation.count_tokens`. Devuelve una `Selection`.

    1. Cupos: de `result.selected` (las que alcanzaron el umbral, de mayor a menor
       puntaje; sin reranker, todas en el orden de la unión), hasta
       `SELECTION_UNITS_PER_CATEGORY` por categoría y hasta `SELECTION_CONSIDERANDOS`
       considerandos, que no ocupan el cupo de su categoría (REQ-018, REQ-019).
    2. Cambios: a cada una se le suman, por relación y no por parecido, las unidades
       que la modifican a la fecha (`unit_changes(result.reference_date)`, REQ-007).
    3. Tokens: cada unidad se cuenta con `generation.count_tokens` sobre
       `answering.prompt_text`, el texto que ve el modelo. Una unidad más larga que
       `UNIT_BY_PASSAGES_FROM_TOKENS` se muestra solo por sus pasajes candidatos que
       alcanzaron el umbral (sin reranker, los que entraron a la unión) y se cuenta así;
       si no tiene ninguno (una unidad que entró solo por relación), va entera.
    4. Espacio: `GENERATION_CONTEXT_TOKENS` menos `prompt_tokens`, menos
       `GENERATION_MAX_OUTPUT_TOKENS`, menos `PROMPT_TEMPLATE_MARGIN_TOKENS`. Se reparte
       por rondas (`_priority`): la mejor de cada categoría, después la segunda, y así;
       los considerandos al final. Cada unidad entra junto con las que la modifican y
       todavía no entraron, o no entra; si no entra, se anota en `left_out` y se sigue
       con la próxima, que puede caber.
    5. Orden de entrega: `answering.order_key`, estable sobre el orden de puntaje.
    """
    parameters = {
        "units_per_category": settings.SELECTION_UNITS_PER_CATEGORY,
        "considerandos": settings.SELECTION_CONSIDERANDOS,
        "context_tokens": settings.GENERATION_CONTEXT_TOKENS,
        "max_output_tokens": settings.GENERATION_MAX_OUTPUT_TOKENS,
        "template_margin_tokens": settings.PROMPT_TEMPLATE_MARGIN_TOKENS,
        "unit_by_passages_from_tokens": settings.UNIT_BY_PASSAGES_FROM_TOKENS,
    }
    available = (settings.GENERATION_CONTEXT_TOKENS - prompt_tokens
                 - settings.GENERATION_MAX_OUTPUT_TOKENS
                 - settings.PROMPT_TEMPLATE_MARGIN_TOKENS)
    common = {"prompt_tokens": prompt_tokens, "available_tokens": available,
              "parameters": parameters}
    if not result.selected:
        return Selection(**common)

    found = Unit.objects.select_related("reading__document__norm").in_bulk(
        [unit.unit_id for unit in result.selected])
    chosen, over_quota = _apply_quotas([found[u.unit_id] for u in result.selected])

    modifiers = _modifiers(result.reference_date, [unit.pk for unit in chosen])
    by_id = {unit.pk: unit for unit in chosen}
    missing = {pk for sources in modifiers.values() for pk in sources} - set(by_id)
    by_id.update(Unit.objects.select_related("reading").in_bulk(list(missing)))

    spans = _passing_spans(result)
    tokens, passages = {}, {}
    for unit_id, unit in by_id.items():
        count = generation.count_tokens(answering.prompt_text(unit))
        if count > settings.UNIT_BY_PASSAGES_FROM_TOKENS and spans.get(unit_id):
            passages[unit_id] = spans[unit_id]
            count = generation.count_tokens(answering.prompt_text(unit, spans[unit_id]))
        tokens[unit_id] = count

    included = set()
    left_out = []
    remaining = available
    for unit in _priority(chosen):
        package = [pk for pk in dict.fromkeys([unit.pk, *modifiers.get(unit.pk, ())])
                   if pk not in included]
        cost = sum(tokens[pk] for pk in package)
        if cost <= remaining:
            included.update(package)
            remaining -= cost
        else:
            left_out.append({"unit": unit.pk, "tokens": cost})

    unit_ids = [unit.pk for unit in sorted((u for u in chosen if u.pk in included),
                                           key=answering.order_key)]
    added = {}
    for unit_id in unit_ids:
        for source_id in modifiers.get(unit_id, ()):
            if source_id not in unit_ids:
                added.setdefault(source_id, []).append(unit_id)

    return Selection(
        unit_ids=unit_ids,
        passages={pk: found_spans for pk, found_spans in passages.items()
                  if pk in included},
        added=[{"unit": pk, "modifies": targets} for pk, targets in added.items()],
        over_quota=over_quota,
        left_out=[entry for entry in left_out if entry["unit"] not in included],
        tokens=tokens,
        used_tokens=available - remaining,
        **common,
    )
