"""Candidatos de una oferta para un requisito (plan 008, "Flujo de IA"; ADR-0027, ADR-0003,
ADR-0007).

`retrieve(offer, query)`:

1. Dos caminos sobre los pasajes de la **última lectura de todos los documentos** de la
   oferta, sin filtrar por tipo de documento (decisión del responsable, 2026-10-05):
   - por significado: el vector de la consulta contra los vectores de los pasajes (distancia
     coseno, búsqueda exacta); los `OFFERS_CANDIDATES_EMBEDDINGS` más cercanos;
   - por palabras: `tsv @@ search_query(...)` con las palabras de la consulta unidas por
     "or" (normalización de tildes de la 001); los `OFFERS_CANDIDATES_WORDS` de mejor
     `ts_rank`.
2. Unión sin repetir pasajes, en el orden de los caminos; cada candidato anota por qué
   camino entró.
3. El reranker puntúa cada candidato contra la consulta en un solo pedido; pasan los
   `OFFERS_CANDIDATES_TO_MODEL` mejores, de mayor a menor puntaje (empate: orden de la unión).
4. Para una fila por renglón (`neighbors=True`, T-135) se suman, tras los mejores, los pasajes
   vecinos de la misma lectura y página de los `OFFERS_ITEM_NEIGHBOR_SEEDS` primeros (la zona
   de la tabla del renglón), hasta `OFFERS_ITEM_NEIGHBORS`, con la fuente "neighbor" y sin
   puntaje del reranker.

Devuelve todos los candidatos (con su puntaje) y los que pasan, para registrar en
`offers_sheet_step.candidates` lo que se vio y lo que se mandó al modelo (P6). Los clientes
se usan por su módulo para que los dobles de las pruebas los reemplacen; sus errores
propios (`evaluon.ai`) no se atrapan acá.
"""

import re
from dataclasses import dataclass, field

from django.conf import settings
from django.db import connection

from evaluon.ai import embeddings, reranker

SEMANTIC = "semantic"
WORDS = "words"
NEIGHBOR = "neighbor"

_JOINS = """
FROM offers_passage p
JOIN offers_reading r ON r.id = p.reading_id
JOIN offers_document d ON d.id = r.document_id
"""

# Solo la última lectura de cada documento de la oferta.
_LATEST = """
WHERE d.offer_id = %s
  AND r.sequence = (SELECT max(r2.sequence) FROM offers_reading r2
                    WHERE r2.document_id = r.document_id)
"""

_SEMANTIC_SQL = f"""
SELECT p.id, p.embedding <=> %s::vector AS distance
{_JOINS}{_LATEST}
ORDER BY distance, p.id
LIMIT %s
"""

_WORDS_SQL = f"""
SELECT p.id, ts_rank(p.tsv, q.query) AS rank
{_JOINS}
CROSS JOIN search_query(%s) AS q(query)
{_LATEST}
  AND p.tsv @@ q.query
ORDER BY rank DESC, p.id
LIMIT %s
"""

_NEIGHBORS_SQL = """
SELECT n.id
FROM offers_passage p
JOIN offers_passage n ON n.reading_id = p.reading_id AND n.page = p.page
                     AND n."order" IN (p."order" - 1, p."order" + 1)
WHERE p.id = %s
ORDER BY n."order", n.id
"""

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class Candidate:
    """Un pasaje candidato: de dónde viene (`sources`), su distancia por significado y
    su puntaje de palabras si los hubo, y el del reranker."""

    passage_id: int
    sources: list = field(default_factory=list)
    distance: float | None = None
    words_rank: float | None = None
    score: float | None = None

    def as_json(self):
        return {"passage": self.passage_id, "sources": self.sources,
                "distance": self.distance, "words_rank": self.words_rank,
                "score": self.score}


@dataclass
class Retrieval:
    """Resultado: la consulta, todos los candidatos y los que pasan al modelo."""

    query: str
    pool: list
    chosen: list


def _vector_literal(vector):
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def words_query(text):
    """Las palabras distintas del texto unidas por "or", para `search_query`. Vacío si no
    hay palabras."""
    words = []
    for word in _WORD_RE.findall(text):
        if word.lower() != "or" and word not in words:
            words.append(word)
    return " or ".join(words)


def _fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def passage_texts(passage_ids):
    """`{id: texto}` de los pasajes dados."""
    if not passage_ids:
        return {}
    rows = _fetch("SELECT id, text FROM offers_passage WHERE id = ANY(%s)",
                  [list(passage_ids)])
    return dict(rows)


def _add_neighbors(candidates, chosen):
    """Suma a `chosen` los vecinos de página de los primeros candidatos (y a `candidates` los
    que todavía no estaban)."""
    in_pool = {c.passage_id: c for c in candidates}
    taken = {c.passage_id for c in chosen}
    added = []
    for seed in chosen[:settings.OFFERS_ITEM_NEIGHBOR_SEEDS]:
        for (passage_id,) in _fetch(_NEIGHBORS_SQL, [seed.passage_id]):
            if passage_id in taken or len(added) >= settings.OFFERS_ITEM_NEIGHBORS:
                continue
            taken.add(passage_id)
            candidate = in_pool.get(passage_id)
            if candidate is None:
                candidate = Candidate(passage_id)
                candidates.append(candidate)
            candidate.sources.append(NEIGHBOR)
            added.append(candidate)
    return chosen + added


def retrieve(offer, query, neighbors=False):
    """Candidatos de `offer` para `query`, ya reordenados. Ver el módulo."""
    query = (query or "").strip()[:settings.OFFERS_QUERY_MAX_CHARS]
    pool = {}
    if query:
        [vector] = embeddings.embed([query])
        for passage_id, distance in _fetch(
                _SEMANTIC_SQL, [_vector_literal(vector), offer.pk,
                                settings.OFFERS_CANDIDATES_EMBEDDINGS]):
            candidate = pool.setdefault(passage_id, Candidate(passage_id))
            candidate.sources.append(SEMANTIC)
            candidate.distance = round(float(distance), 6)
        words = words_query(query)
        if words:
            for passage_id, rank in _fetch(
                    _WORDS_SQL, [words, offer.pk, settings.OFFERS_CANDIDATES_WORDS]):
                candidate = pool.setdefault(passage_id, Candidate(passage_id))
                candidate.sources.append(WORDS)
                candidate.words_rank = round(float(rank), 6)
    candidates = list(pool.values())
    if candidates:
        texts = passage_texts([c.passage_id for c in candidates])
        scores = reranker.rerank(query, [texts[c.passage_id] for c in candidates])
        for candidate, score in zip(candidates, scores, strict=True):
            candidate.score = round(float(score), 6)
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i].score, i))
    chosen = [candidates[i] for i in order[:settings.OFFERS_CANDIDATES_TO_MODEL]]
    if neighbors and chosen:
        chosen = _add_neighbors(candidates, chosen)
    return Retrieval(query=query, pool=candidates, chosen=chosen)
