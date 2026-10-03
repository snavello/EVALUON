"""Recuperación de unidades para una consulta (plan 001, "Recuperación", "Reordenamiento"
y "Abstención"; ADR-0003). Versión mínima de T-017: solo el camino por significado.

`retrieve(pregunta, fecha)`:

1. Calcula el vector de la pregunta con el cliente de embeddings.
2. Busca entre los pasajes de las unidades de `consultable_units(fecha)` con `repealed`
   falso los `RETRIEVAL_CANDIDATES_PER_PATH` más cercanos por distancia coseno, con
   búsqueda exacta (sin índice aproximado). Así una norma sin validar (REQ-005), un
   documento fuera de uso o fuera de vigencia y una unidad derogada a la fecha no entran.
3. El reranker puntúa cada pasaje (encabezado más texto) contra la pregunta, en un solo
   pedido; el cliente devuelve el puntaje entre 0 y 1 (sigmoide).
4. Agrupa los pasajes por unidad base con el mejor puntaje de sus pasajes. Los pasajes
   son solo de unidades base (los incisos no generan pasajes), así que la unidad del
   pasaje es su unidad base.
5. Primera barrera de abstención: si ninguna unidad alcanza `RERANK_THRESHOLD` (puntaje
   igual o mayor), no hay seleccionadas y el motivo es `below_threshold` (REQ-009).
6. Pasan las unidades que alcanzan el umbral, de mayor a menor puntaje.

La fecha es siempre la de autorización del procedimiento que recibe quien llama: esta
función no usa la fecha del día y, sin fecha, no busca. Los otros dos caminos, los
cupos, los cambios por relación y el espacio del contexto son de T-032 y T-033.

Los clientes se usan por su módulo (`embeddings.embed`, `reranker.rerank`) para que los
dobles de las pruebas los reemplacen. Sus errores propios (`evaluon.ai`) no se atrapan
acá: son fallas técnicas que resuelve quien llama.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.db import connection

from evaluon.ai import embeddings, reranker

# Camino por el que entró un candidato (los otros dos son de T-032).
SEMANTIC = "semantic"

# Motivo de la primera barrera de abstención (plan 001, "Abstención").
BELOW_THRESHOLD = "below_threshold"

_SEMANTIC_SQL = """
SELECT p.id, p.unit_id, p.header, p.text, p.embedding <=> %s::vector AS distance
FROM norms_passage p
JOIN consultable_units(%s) cu ON cu.unit_id = p.unit_id
WHERE NOT cu.repealed
ORDER BY distance, p.id
LIMIT %s
"""


def passage_document(header, text):
    """Texto de un pasaje tal como lo recibe el reranker: encabezado más texto."""
    return f"{header}\n{text}"


@dataclass(frozen=True)
class Candidate:
    """Un pasaje recuperado: por qué camino entró, a qué distancia de la pregunta estaba
    y qué puntaje le dio el reranker."""

    passage_id: int
    unit_id: int
    path: str
    distance: float
    score: float

    def as_record(self):
        return {"passage": self.passage_id, "unit": self.unit_id, "path": self.path,
                "distance": self.distance, "score": self.score}


@dataclass(frozen=True)
class UnitScore:
    """Una unidad base con el mejor puntaje de sus pasajes y los pasajes que aportó."""

    unit_id: int
    score: float
    passage_ids: tuple = ()

    def as_record(self):
        return {"unit": self.unit_id, "score": self.score,
                "passages": list(self.passage_ids)}


@dataclass(frozen=True)
class RetrievalResult:
    """Resultado de la recuperación.

    - `candidates`: cada pasaje recuperado, en el orden del camino por significado.
    - `units`: cada unidad base candidata con su mejor puntaje, de mayor a menor.
    - `selected`: las unidades de `units` que alcanzan el umbral.
    - `max_score`: el puntaje más alto, o `None` si no hubo candidatos.
    - `reason`: `below_threshold` si ninguna unidad alcanza el umbral; si no, `None`.
    - `parameters`: los parámetros de búsqueda usados.
    """

    reference_date: object
    candidates: list = field(default_factory=list)
    units: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    max_score: float | None = None
    reason: str | None = None
    parameters: dict = field(default_factory=dict)

    def as_record(self):
        """El resultado en datos que se pueden guardar como JSON en el registro (P6)."""
        return {
            "reference_date": self.reference_date.isoformat(),
            "parameters": dict(self.parameters),
            "candidates": [c.as_record() for c in self.candidates],
            "units": [u.as_record() for u in self.units],
            "selected": [u.as_record() for u in self.selected],
            "max_score": self.max_score,
            "reason": self.reason,
        }


def _vector_literal(vector):
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _semantic_passages(question, reference_date, limit):
    [vector] = embeddings.embed([question])
    with connection.cursor() as cursor:
        cursor.execute(_SEMANTIC_SQL, [_vector_literal(vector), reference_date, limit])
        return cursor.fetchall()


def retrieve(question, reference_date):
    """Recupera y reordena las unidades para `question` según lo que regía en
    `reference_date`, la fecha de autorización del procedimiento. Ver el módulo."""
    if reference_date is None:
        raise ValueError(
            "La recuperación necesita la fecha de autorización del procedimiento."
        )
    threshold = settings.RERANK_THRESHOLD
    limit = settings.RETRIEVAL_CANDIDATES_PER_PATH
    parameters = {"candidates_per_path": limit, "rerank_threshold": threshold}

    rows = _semantic_passages(question, reference_date, limit)
    scores = reranker.rerank(
        question, [passage_document(header, text) for _, _, header, text, _ in rows]
    )
    candidates = [
        Candidate(passage_id=passage_id, unit_id=unit_id, path=SEMANTIC,
                  distance=float(distance), score=float(score))
        for (passage_id, unit_id, _, _, distance), score in zip(rows, scores)
    ]

    best = {}
    passages = {}
    for candidate in candidates:
        passages.setdefault(candidate.unit_id, []).append(candidate.passage_id)
        best[candidate.unit_id] = max(best.get(candidate.unit_id, candidate.score),
                                      candidate.score)
    units = sorted(
        (UnitScore(unit_id, score, tuple(passages[unit_id]))
         for unit_id, score in best.items()),
        key=lambda unit: (-unit.score, unit.unit_id),
    )
    selected = [unit for unit in units if unit.score >= threshold]

    return RetrievalResult(
        reference_date=reference_date,
        candidates=candidates,
        units=units,
        selected=selected,
        max_score=units[0].score if units else None,
        reason=None if selected else BELOW_THRESHOLD,
        parameters=parameters,
    )
