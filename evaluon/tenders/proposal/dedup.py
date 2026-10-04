"""Unificación de las filas que repiten la misma condición (REQ-025, REQ-033; plan 003,
"Unificación de repetidas"; ADR-0021).

Es una regla, sin modelo: la coincidencia del texto es objetiva. Junta las filas formales
y económicas, de cualquier tramo, cuyo fragmento normalizado (minúsculas, sin tildes, con
los espacios y los signos de puntuación colapsados) es igual, o uno contiene al otro, o
cuya similitud de palabras (en su orden, sin las de uso común) es de al menos
`DEDUP_MIN_SIMILARITY`; es conservadora: por similitud o contención exige las mismas cifras,
negaciones y verbos modales, en el mismo orden. Con el umbral en 1,0 solo se unen las filas de texto igual.

La fila que queda es la primera en el orden del pliego, con su cita como cita principal; las
citas de las otras quedan como citas adicionales (`scope` `repetida`), cada una con su texto
literal y su ubicación.

No junta las filas con cita amplia (el tramo entero no dice cuál es la condición) ni dos
filas de un mismo tramo con citas que no se superponen: son condiciones distintas aunque se
parezcan. Las filas técnicas y las de circulares no pasan por acá: se arman después, por
otro camino.

`unify` no toca la base; `record` deja el pedido de la pasada en `tenders_run_step`, con el
umbral y los pares unidos (P6).
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from evaluon.tenders.models import PassName, RunStep
from evaluon.tenders.proposal import quotes

RULE_VERSION = "unificacion-v1"

# Una contención solo une si lo contenido tiene al menos estas palabras: un fragmento de una
# o dos palabras ("garantía") está en cualquier fila y no dice nada de la condición.
MIN_CONTAINED_WORDS = 3

# Palabras de uso común, que no cuentan para la similitud.
COMMON_WORDS = frozenset((
    "a ante bajo con contra de del desde durante e el en entre la las lo los o para por "
    "segun sin sobre u un una uno unos unas y al se su sus que es son ser sera seran "
    "este esta estos estas ese esa"
).split())


def normalize(text):
    """Minúsculas, sin tildes, con los signos de puntuación y los espacios colapsados a un
    espacio."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w%]+", " ", plain).split())


def content_words(normalized):
    """Las palabras de un texto normalizado, en su orden y sin las de uso común."""
    return [word for word in normalized.split() if word not in COMMON_WORDS]


# Lo que cambia la condición aunque pese poco en el texto: la unión por similitud o por
# contención exige que el texto tenga lo mismo, en el mismo orden (ante la duda, no une).
NUMBER_WORDS = frozenset((
    "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce quince veinte "
    "treinta cuarenta cincuenta sesenta setenta ochenta noventa cien ciento mil millon "
    "millones primero segundo tercero cuarto quinto"
).split())
SENSE_WORDS = frozenset((
    "no sin ni nunca jamas tampoco nada ningun ninguna ninguno salvo excepto minimo minima "
    "maximo maxima menor mayor inferior superior menos mas antes despues hasta desde "
    "cuando si siempre solo solamente unicamente cada todo toda todos todas cualquier"
).split())
MODAL_WORDS = frozenset((
    "debe deben debera deberan debia deberia podra podran puede pueden podria tendra "
    "tendran tiene tienen sera seran estara estaran queda quedara quedaran corresponde "
    "correspondera"
).split())

# Palabras con contenido que pueden sobrar en la frase más larga de una contención sin
# cambiar la condición (más de una, o una que cambia el sentido, no une).
MAX_EXTRA_WORDS = 1


def _figures(token):
    return token in NUMBER_WORDS or token == "%" or any(c.isdigit() for c in token)


def signature(normalized):
    """Lo que no puede cambiar entre dos filas de la misma condición: la secuencia de
    cifras, porcentajes y números en letras, la de negaciones e inversores, y la de verbos
    de obligación o facultad."""
    tokens = normalized.split()
    return (
        tuple(t for t in tokens if _figures(t)),
        tuple(t for t in tokens if t in SENSE_WORDS),
        tuple(t for t in tokens if t in MODAL_WORDS),
    )


def _contains(long_, short):
    """Si `short` está dentro de `long_` como secuencia de palabras enteras."""
    return f" {short} " in f" {long_} "


def _order_similarity(a, b):
    """Similitud de las palabras con contenido de dos textos, respetando su orden."""
    words_a, words_b = content_words(a), content_words(b)
    if not words_a or not words_b:
        return 0.0
    return difflib.SequenceMatcher(None, words_a, words_b, autojunk=False).ratio()


def _contained(short, long_):
    """Si `long_` es `short` y nada más que un par de palabras sin condición: lo que sobra
    es, como mucho, una palabra con contenido y ninguna de las que cambian el sentido."""
    if not _contains(long_, short):
        return False
    extra = content_words(long_.replace(short, " ", 1))
    return len(extra) <= MAX_EXTRA_WORDS and not any(
        w in SENSE_WORDS or w in MODAL_WORDS or _figures(w) for w in extra)


def similar(a, b, threshold):
    """Si dos textos normalizados dicen la misma condición, y por qué (`igual`,
    `contenida` o `similar`), o `None`. Es conservador: por similitud o por contención solo
    une si las cifras, las negaciones y los verbos modales son los mismos y en el mismo
    orden; la contención, solo si lo contenido es una frase de al menos
    `MIN_CONTAINED_WORDS` palabras y lo que sobra no le agrega una condición."""
    if not a or not b:
        return None
    if a == b:
        return "igual"
    if threshold >= 1.0 or signature(a) != signature(b):
        return None
    short, long_ = sorted((a, b), key=len)
    if len(short.split()) >= MIN_CONTAINED_WORDS and _contained(short, long_):
        return "contenida"
    if _order_similarity(a, b) >= threshold:
        return "similar"
    return None


@dataclass
class Row:
    """Una fila formal o económica en el orden del pliego, con su texto normalizado."""

    unit: object
    found: object
    normalized: str
    words: list

    @property
    def segment(self):
        return self.unit.segment

    @property
    def span(self):
        return self.found.span

    @property
    def text(self):
        return self.segment.text[self.found.span[0]:self.found.span[1]]


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _same_condition(row, other, threshold):
    """El motivo por el que `row` repite a `other`, o `None`."""
    if row.segment.pk == other.segment.pk and not _overlap(row.span, other.span):
        return None
    return similar(row.normalized, other.normalized, threshold)


@dataclass
class Group:
    """Una fila que queda y las que repiten su condición."""

    kept: Row
    repeated: list = field(default_factory=list)
    reasons: list = field(default_factory=list)


@dataclass
class Result:
    """`body` es la lista `[(unidad, Found)]` sin las filas unidas; `repeated`, para cada
    fila que queda (por `id` del `Found`), las que repiten su condición."""

    body: list
    groups: list
    threshold: float
    steps: list = field(default_factory=list)  # el pedido registrado, para el conteo

    @property
    def merged(self):
        return [g for g in self.groups if g.repeated]

    @property
    def repeated(self):
        return {id(g.kept.found): [(r.unit, r.found) for r in g.repeated]
                for g in self.merged}

    @property
    def pairs(self):
        """Los pares unidos, con la clave del tramo, las posiciones, el motivo y el texto."""
        return [
            {"queda": _ref(g.kept), "repetida": _ref(row), "motivo": reason}
            for g in self.merged for row, reason in zip(g.repeated, g.reasons)
        ]


def _ref(row):
    return {"segment": row.segment.key, "span": list(row.span), "text": row.text}


def unify(body, threshold):
    """Junta las filas de `body` (`[(unidad, Found)]`, en el orden del pliego) que repiten
    la misma condición. Devuelve un `Result`."""
    groups = []
    for unit, found in body:
        row = Row(unit, found, "", [])
        if found.flag == quotes.WIDE:
            groups.append(Group(row))
            continue
        row.normalized = normalize(row.text)
        row.words = content_words(row.normalized)
        for group in groups:
            if group.kept.found.flag == quotes.WIDE:
                continue
            members = [group.kept, *group.repeated]
            reason = next(filter(None, (_same_condition(row, member, threshold)
                                        for member in members)), None)
            if reason:
                group.repeated.append(row)
                group.reasons.append(reason)
                break
        else:
            groups.append(Group(row))
    return Result(body=[(g.kept.unit, g.kept.found) for g in groups], groups=groups,
                  threshold=threshold)


def record(run, result):
    """Guarda la pasada en `tenders_run_step`: la versión de la regla, el umbral y los pares
    unidos. Devuelve el `RunStep`."""
    pairs = result.pairs
    return RunStep.objects.create(
        run=run,
        pass_name=PassName.UNIFICACION.value,
        batch=1,
        segment_keys=sorted({p[k]["segment"] for p in pairs for k in ("queda", "repetida")}),
        request={"rule": RULE_VERSION, "min_similarity": result.threshold,
                 "rows": len(result.groups) + sum(len(g.repeated) for g in result.groups)},
        raw_output="",
        parsed={"pairs": pairs, "merged": len(pairs)},
        anomalies=[],
        timings={},
    )
