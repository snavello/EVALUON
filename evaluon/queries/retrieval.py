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
función no usa la fecha del día y, sin fecha, no busca. Los cupos, los cambios por
relación y el espacio del contexto son de T-033.

Los clientes se usan por su módulo (`embeddings.embed`, `reranker.rerank`) para que los
dobles de las pruebas los reemplacen. Sus errores propios (`evaluon.ai`) no se atrapan
acá: son fallas técnicas que resuelve quien llama.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.db import connection

from evaluon.ai import embeddings, reranker
from evaluon.norms import indexing

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
