"""Unidades de cambio de una circular y aplicación por clave, sin modelo (REQ-031, REQ-028;
plan 003, "Rediseño de la pasada de circulares", entrega 1; ADR-0023; T-113).

La pasada de T-083 le pedía al modelo, por cada tramo que dejó la lectura, elegir la cita del
pliego alcanzada. Lo que una circular dice con precisión (la cláusula 7.5.4, el Anexo VI, el
Renglón 3) lo resuelve el código por la clave, siempre igual y a **todas** las citas
afectadas; el modelo queda para lo que pide lectura (el flujo de `circulars.Processor` como
respaldo).

**Unidades de cambio.** La circular se parte sobre los tramos ya leídos:

| Unidad | Cómo se detecta |
|---|---|
| `clausula` | Tramo `cláusula` de primer nivel (`1`, `2`) y lo que cuelga hasta la siguiente |
| `apartado` | Encabezado con numeración romana (`II. …`) y todo hasta el próximo límite |
| `par` | Rótulo "Donde dice" (sin mayúsculas ni tildes, con o sin dos puntos) y lo que sigue |
| `suelto` | Cualquier otro tramo: va al respaldo, como hoy |

Un par que cae dentro de una cláusula o de un apartado es parte de esa unidad: los tramos
`no_ubicado` y las tablas entre los rótulos pertenecen al par, y el lado "dice" no produce
nunca un efecto.

**Tipo, objetivo y efecto.** El tipo sale de listas cerradas de verbos (`CHANGE_PATTERNS`);
el objetivo, de lo que el encabezado de la unidad nombra (cláusula, renglón, anexo) y, en un
par, del número con que empieza el lado "debe decir" o del texto anterior. Todo lo que no se
resuelve con certeza (clave inexistente o ambigua, texto anterior sin coincidencia única,
cero citas) devuelve `respaldo` con su motivo: nada se pierde.

Este módulo no toca la base ni arma `circulars.Source`: devuelve `Resolution` con los
efectos (`Effect`) y los requisitos nuevos (`Addition`); `circulars.Processor` los aplica,
los registra y los pasa al resultado.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from evaluon.tenders.models import RequirementClass, SegmentType, SourceEffect
from evaluon.tenders.proposal import circulars
from evaluon.tenders.proposal.circulars import fold

# Tipos de unidad.
KIND_CLAUSE = "clausula"
KIND_SECTION = "apartado"
KIND_PAIR = "par"
KIND_LOOSE = "suelto"

# Tipos de cambio (por verbos y rótulos, en código).
CHANGE_REPLACES = "reemplaza"
CHANGE_SUPPRESSES = "suprime"
CHANGE_ADDS = "agrega"
CHANGE_CLARIFIES = "aclara"
CHANGE_DATA = "dato_del_tramite"

# Qué pasó con la unidad.
OUTCOME_APPLIED = "aplicada"
OUTCOME_DATA = "dato_del_tramite"
OUTCOME_FALLBACK = "respaldo"

# Motivos de respaldo.
FALLBACK_LOOSE = "tramo_suelto"
FALLBACK_NO_CHANGE = "sin_verbo_reconocible"
FALLBACK_NO_TARGET = "sin_objetivo"
FALLBACK_MISSING_KEY = "clave_inexistente"
FALLBACK_AMBIGUOUS = "clave_ambigua"
FALLBACK_NO_OLD_TEXT = "texto_anterior_sin_coincidencia"
FALLBACK_AMBIGUOUS_OLD_TEXT = "texto_anterior_ambiguo"
FALLBACK_NO_NEW_TEXT = "sin_texto_nuevo"
FALLBACK_ZERO = "cero_citas"
FALLBACK_SEVERAL_PAIRS = "varios_pares"
FALLBACK_EXISTING_KEY = "clave_existente"

# Una lista de datos del trámite: líneas cortas y de la forma rótulo y valor, sin marcadores
# de obligación. Se ajustan en T-120.
SHORT_LINE_CHARS = 100
DATA_SHARE = 0.6            # fracción de líneas cortas o rótulo y valor
DATA_LABELED_SHARE = 0.3    # fracción de líneas rótulo y valor
DATA_MIN_LINES = 2
HEAD_LINES = 4              # líneas del apartado en que se busca el título de un anexo
MIN_OVERLAP_WORDS = 2       # palabras seguidas en común para dar por alcanzada una cita
MIN_CONTAINED_CHARS = 15    # largo mínimo de una cita contenida en el texto anterior
SIMILAR_SENTENCE = 0.7      # parecido de palabras para tomar una oración por reformulación

_STOPWORDS = frozenset("de la el los las del en por y a que con al un una se lo su sus o e".split())


def _verb(*stems):
    """Patrón de las formas de un verbo (sobre texto sin tildes ni mayúsculas): "se
    modifica", "modificase", "modificar"…"""
    alternatives = "|".join(stems)
    return rf"\b(?:se\s+)?(?:{alternatives})(?:a|an|e|en|ase|anse|ese|ense|ar|ir|ye|yen|yese|yense)?\b"


# Cada tipo con sus patrones, sobre texto sin tildes ni mayúsculas. En el encabezado de una
# unidad gana el primero de esta lista que aparece (suprimir pesa más que aclarar).
CHANGE_PATTERNS = (
    (CHANGE_SUPPRESSES, (
        _verb("suprim", "elimin", "derog"),
        r"\b(?:se\s+)?(?:deja|dejan|dejase|dejanse|queda|quedan)\s+sin\s+efecto\b",
        r"\bno\s+(?:sera|seran|es|son|constituye|constituyen)\s+"
        r"(?:considerad[oa]s?\s+)?(?:como\s+)?(?:un\s+|los\s+)?requisitos?\b",
    )),
    (CHANGE_REPLACES, (
        _verb("modific", "reemplaz", "sustitu", "cambi"),
        r"\bpor\s+(?:la|el|lo)\s+siguientes?\b",
        r"\bqueda(?:ra)?\s+redactad[oa]\b",
    )),
    (CHANGE_ADDS, (
        _verb("agreg", "incorpor", "adicion"),
    )),
    (CHANGE_CLARIFIES, (
        _verb("aclar"),
        r"\bse\s+informa\b",
    )),
)
_CHANGE_RES = tuple((kind, tuple(re.compile(p) for p in patterns))
                    for kind, patterns in CHANGE_PATTERNS)

# Reemplazo de la cláusula entera ("por la siguiente:", "queda redactada de la siguiente
# manera:") y reemplazo de una parte ("el plazo de pago por 60 días").
_WHOLE = re.compile(r"\bpor\s+(?:la|el)\s+(?:siguientes?|texto\s+siguiente)\b"
                    r"|\bqueda(?:ra)?\s+redactad[oa]\b"
                    r"|\bcon\s+la\s+siguiente\s+redaccion\b|\bnueva\s+redaccion\b")
_PARTIAL = re.compile(
    r"\b(?:reemplaz\w*|sustitu\w*|modific\w*|cambi\w*)\b(?P<old>.{3,400}?)\spor\s+"
    r"(?P<new>(?:[^.\n]|\.(?!\s|$)){2,300}?)(?:\.(?:\s|$)|\n|$)", re.DOTALL)

# Marcadores de un par "Donde dice / Debe decir" (al comienzo de línea, sin tildes).
_DICE = re.compile(r"(?im)^[ \t]*donde[ \t]+dice[ \t]*:?")
_DEBE = re.compile(r"(?im)^[ \t]*debe[ \t]+decir[ \t]*:?")

# Encabezado romano: "I. ", "I.- ", "I - ", "I) " (T-120).
_ROMAN_HEADING = re.compile(r"^\s*[IVXLC]+(?:\.\s*-|\.|\s+-|\))\s+\S")
_ROMAN_PREFIX = re.compile(r"^\s*[IVXLC]+(?:\.\s*-|\.|\s+-|\))\s+")
_OWN_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s+\S")
_FIRST_LEVEL = re.compile(r"^\d+$")
_CLAUSE_WORD = r"(?:sub-?)?(?:clausulas?|articulos?|puntos?|apartados?|numerales?|incisos?)"
# El objeto directo del verbo es la cláusula o el renglón ("se suprime la cláusula 5.3"), sobre
# texto sin tildes ni mayúsculas.
_CLAUSE_OBJECT = re.compile(
    r"(?:suprim|elimin|derog|sin\s+efecto)\w*\s+(?:(?:la|el|las|los)\s+)?"
    + _CLAUSE_WORD + r"\s*(?:n[°º]\s*|num(?:ero)?s?\.?\s*|nros?\.?\s*)?\d")
_ITEM_OBJECT = re.compile(
    r"(?:suprim|elimin|derog|sin\s+efecto)\w*\s+(?:(?:la|el|las|los)\s+)?renglon")
# Una cláusula que pide un anexo: verbo de presentación y, seguido, el anexo.
_ASKS_FOR = re.compile(r"\b(?:complet|adjunt|present|acompan)\w*\b[^.;]{0,60}?\banexos?\b")
_PATH_PARTS = ("v-", "inc-", "p-", "tabla-")
# Rótulo y valor corto ("FECHA: 3 de marzo"). Las líneas "Consulta N° 1: ..." y "Respuesta: ..." de
# una circular de consultas no son rótulo y valor aunque tengan dos puntos (T-120).
LABEL_VALUE_MAX_CHARS = 80
_LABELED_RE = re.compile(rf"^[^\n:]{{2,60}}:\s*\S[^\n]{{0,{LABEL_VALUE_MAX_CHARS - 1}}}$")
_QUESTION_LINE = re.compile(r"^\s*(?:consulta|respuesta|pregunta)\b", re.IGNORECASE)


class _Labeled:
    @staticmethod
    def match(line):
        return None if _QUESTION_LINE.match(line) else _LABELED_RE.match(line)


_LABELED = _Labeled()

# Marcadores de obligación propios de las circulares (T-120): los de la extracción del pliego y
# "debe/deben", "corresponde" y "es obligatorio". "Debe decir" es el rótulo del par, no obligación.
_CIRCULAR_OBLIGATION = re.compile(
    r"\bdeb(?:e|en|era|eran)\b(?!\s+decir\b)|\bcorresponde(?:ra|n)?\b"
    r"|\bes\s+obligatori[oa]\b|\bson\s+obligatori[oa]s\b")


def has_circular_obligation(text):
    """Si el texto de una circular tiene un marcador de obligación."""
    from evaluon.tenders.proposal.run import has_obligation_markers

    return has_obligation_markers(text) or bool(_CIRCULAR_OBLIGATION.search(fold(text)))


# --- Tramos y unidades ---------------------------------------------------------------------------


@dataclass
class ChangeUnit:
    """Un cambio de la circular: los tramos que lo componen, en orden."""

    kind: str
    members: list

    @property
    def keys(self):
        return [m.segment.key for m in self.members]

    @property
    def start(self):
        return self.members[0].segment.char_start

    @property
    def end(self):
        return self.members[-1].segment.char_end


def _fold_char(char):
    base = char.lower()
    if len(base) != 1:
        base = base[:1]
    return unicodedata.normalize("NFD", base)[0]


def fold_aligned(text):
    """Como `fold`, con el mismo largo que `text`: las posiciones valen para los dos."""
    return "".join(_fold_char(c) for c in text)


def _is_heading(text):
    first = text.strip().split("\n")[0]
    return bool(_ROMAN_HEADING.match(first)) and len(first) <= circulars.CONTEXT_CHARS


def _is_first_level_clause(segment):
    if segment.segment_type != SegmentType.CLAUSULA:
        return False
    last = re.split(r"[#~]", segment.key.split("/")[-1])[0]
    return bool(_FIRST_LEVEL.match(last))


def _has_dice(text):
    return bool(_DICE.match(fold_aligned(text.lstrip())))


def partition(units):
    """Parte los tramos de una circular (`extraction.Unit`, en orden) en `ChangeUnit`."""
    out, current = [], None

    def close():
        nonlocal current
        if current is not None:
            out.append(current)
        current = None

    for unit in units:
        segment = unit.segment
        text = segment.text or ""
        if _is_heading(text):
            close()
            current = ChangeUnit(KIND_SECTION, [unit])
        elif _is_first_level_clause(segment):
            close()
            current = ChangeUnit(KIND_CLAUSE, [unit])
        elif _has_dice(text):
            # Un par dentro de una cláusula o un apartado es de esa unidad.
            if current is None or current.kind in (KIND_LOOSE, KIND_PAIR):
                close()
                current = ChangeUnit(KIND_PAIR, [unit])
            else:
                current.members.append(unit)
        elif current is not None and current.kind != KIND_LOOSE:
            current.members.append(unit)
        else:
            close()
            current = ChangeUnit(KIND_LOOSE, [unit])
            close()
    close()
    return out


# --- Lo que una unidad dice ----------------------------------------------------------------------------


def unit_text(unit, document):
    """El texto de la unidad: el recorte del texto canónico de la lectura de la circular."""
    return document.reading.canonical_text[unit.start:unit.end]


def introducer(text):
    """Lo que la unidad dice antes de su texto nuevo: sin su número ni su numeral romano,
    hasta los dos puntos o el fin de la primera oración."""
    body = _ROMAN_PREFIX.sub("", _OWN_NUMBER.sub("", text, count=1), count=1)
    cut = len(body)
    colon = body.find(":")
    if colon != -1:
        cut = colon
    sentence = re.search(r"(?<!\d)\.(?:\s|$)", body)
    if sentence and sentence.start() < cut:
        cut = sentence.start()
    return body[:min(cut, 400)]


def detect_change(head):
    """El tipo de cambio que dice `head` o `""` si ningún verbo de las listas aparece."""
    folded = fold_aligned(head)
    for kind, patterns in _CHANGE_RES:
        if any(p.search(folded) for p in patterns):
            return kind
    return ""


@dataclass
class Pair:
    """Un par "Donde dice / Debe decir" dentro de la unidad: el encabezado que lo precede,
    el lado "dice" y el lado "debe decir", este con sus posiciones absolutas."""

    head: str
    old: str
    new: str
    new_start: int
    new_end: int


def find_pair(unit, text):
    """El par de la unidad, `False` si hay más de uno o `None` si no hay."""
    folded = fold_aligned(text)
    dices = list(_DICE.finditer(folded))
    if not dices:
        return None
    if len(dices) > 1:
        return False
    first = dices[0]
    debe = _DEBE.search(folded, first.end())
    if debe is None:
        return None
    if len(list(_DEBE.finditer(folded, debe.end()))):
        return False
    new_from = debe.end()
    new_text = text[new_from:]
    lead = len(new_text) - len(new_text.lstrip())
    stripped = new_text.strip()
    start = unit.start + new_from + lead
    return Pair(head=text[:first.start()], old=text[first.end():debe.start()].strip(),
                new=stripped, new_start=start, new_end=start + len(stripped))


# --- Qué cita alcanza ---------------------------------------------------------------------------------


def _clause_root(key):
    parts = []
    for part in key.split("/"):
        base = re.split(r"[#~]", part)[0]
        if base.startswith(_PATH_PARTS):
            break
        parts.append(base)
    return "/".join(parts)


def _section_group(candidate):
    key = candidate.segment.key
    prefix = key.split("/")[0] if "/" in key else ""
    return (candidate.segment.reading_id, prefix)


def clause_candidates(candidates, number):
    """Las citas de la cláusula `number` y de lo que cuelga de ella (`7.5.4` no alcanza
    `7.5.41`)."""
    return [c for c in candidates
            if any(p == number or p.startswith(number + ".")
                   for p in circulars._key_numbers(c.segment.key))]


def _tech_items(candidate):
    return {i for t in candidate.targets if t.category == RequirementClass.TECNICO.value
            for i in t.items}


def _is_shared(candidate):
    """Una cita técnica común a varios renglones: un efecto suyo alcanza la fila de cada
    uno, así que solo se aplica si la unidad nombra su cláusula."""
    return len(_tech_items(candidate)) > 1


def _norm(text):
    return " ".join(fold(text).split())


def _words(text):
    return re.findall(r"[a-z0-9]+", fold(text))


def overlap(old, candidate_text):
    """Palabras seguidas en común entre `old` y la cita; las que no son solo de relleno."""
    a, b = _words(old), _words(candidate_text)
    best = 0
    previous = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        row = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                row[j] = previous[j - 1] + 1
                if row[j] > best and not set(a[i - row[j]:i]) <= _STOPWORDS:
                    best = row[j]
        previous = row
    return best


def match_old_text(old, pool):
    """Las citas de `pool` que el texto anterior `old` designa: las contenidas en él (o que
    lo contienen) o la única de mayor coincidencia de palabras. Devuelve `(citas, motivo)`."""
    folded = _norm(old)
    if not folded:
        return [], FALLBACK_NO_OLD_TEXT
    contained = []
    for c in pool:
        text = _norm(c.text)
        if (len(text) >= MIN_CONTAINED_CHARS and text in folded) or folded in text:
            contained.append(c)
    if contained:
        roots = {(c.segment.reading_id, _clause_root(c.segment.key)) for c in contained}
        if len(roots) > 1:
            return [], FALLBACK_AMBIGUOUS_OLD_TEXT
        return contained, ""
    scored = sorted(((overlap(old, c.text), i, c) for i, c in enumerate(pool)),
                    key=lambda s: (-s[0], s[1]))
    if not scored or scored[0][0] < MIN_OVERLAP_WORDS:
        return [], FALLBACK_NO_OLD_TEXT
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return [], FALLBACK_AMBIGUOUS_OLD_TEXT
    return [scored[0][2]], ""


# --- Resultado ---------------------------------------------------------------------------------------


@dataclass
class Original:
    """Dónde está el texto que la circular reemplaza cuando no es la cita alcanzada."""

    segment: object
    start: int
    end: int


@dataclass
class Effect:
    """Lo que la unidad hace a una cita del pliego."""

    candidate: object
    effect: str
    segment: object
    start: int
    end: int
    text: str
    original: Original | None = None


@dataclass
class Addition:
    """Un requisito que la unidad agrega."""

    category: str
    segment: object
    start: int
    end: int
    text: str
    suggested: bool = False     # se parece a una oración del lado "dice": va como sugerencia


@dataclass
class Resolution:
    unit: ChangeUnit
    outcome: str
    change: str = ""
    target: dict = field(default_factory=dict)
    reason: str = ""
    effects: list = field(default_factory=list)
    additions: list = field(default_factory=list)
    record: bool = True

    def fallback(self, reason):
        self.outcome, self.reason = OUTCOME_FALLBACK, reason
        self.effects, self.additions = [], []
        return self


def _segment_at(unit, position):
    for member in unit.members:
        if position < member.segment.char_end:
            return member.segment
    return unit.members[-1].segment


def _effect(unit, document, candidate, effect, start, end, original=None):
    canonical = document.reading.canonical_text
    return Effect(candidate, effect, _segment_at(unit, start), start, end,
                  canonical[start:end], original)


class _Ctx:
    """Lo que hace falta para resolver una unidad."""

    def __init__(self, unit, document, candidates, pliego):
        self.unit, self.document = unit, document
        self.candidates, self.pliego = candidates, pliego
        self.text = unit_text(unit, document)


def _single_group(found):
    """Si todas las citas son de una sola cláusula de un solo documento y sección."""
    return len({_section_group(c) for c in found}) <= 1


def _resolve_clauses(ctx, numbers):
    """Las citas de cada cláusula nombrada, juntas; `(citas, motivo)`."""
    out = []
    for number in sorted(numbers):
        found = clause_candidates(ctx.candidates, number)
        if not found:
            return [], FALLBACK_MISSING_KEY
        if not _single_group(found):
            return [], FALLBACK_AMBIGUOUS
        out.extend(c for c in found if c not in out)
    return out, ""


def _item_candidates(candidates, items):
    return [c for c in candidates if _tech_items(c) and _tech_items(c) <= set(items)]


def _new_text_span(ctx, after):
    """Posiciones absolutas del texto nuevo: lo que sigue, desde `after` (posición en
    `ctx.text`), a los dos puntos si los hay cerca, hasta el fin de la unidad."""
    colon = ctx.text.find(":", after, after + 80)
    start = (colon + 1) if colon != -1 else after
    text = ctx.text[start:]
    lead = len(text) - len(text.lstrip())
    stripped = text.strip()
    if len(stripped) < 5:
        return None
    absolute = ctx.unit.start + start + lead
    return absolute, absolute + len(stripped)


def _resolve_pair(ctx, pair):
    """El par se aplica como un solo `modifica` por cita; el lado "dice" no produce efecto."""
    res = Resolution(ctx.unit, OUTCOME_APPLIED, CHANGE_REPLACES)
    clauses, items = (circulars.named_in(introducer(pair.head)) if pair.head.strip()
                      else (set(), set()))
    if not clauses:
        for side in (pair.new, pair.old):
            number = _LEADING_NUMBER.match(side)
            if number:
                clauses = {number.group(1)}
                break
    if clauses:
        res.target = {"tipo": "clausula", "referencia": sorted(clauses)}
        found, reason = _resolve_clauses(ctx, clauses)
        if reason:
            return res.fallback(reason)
    else:
        pool = (_item_candidates(ctx.candidates, items) if items
                else [c for c in ctx.candidates if not _is_shared(c)])
        res.target = {"tipo": "texto_anterior", "referencia": sorted(items)}
        found, reason = match_old_text(pair.old, pool)
        if reason:
            return res.fallback(reason)
    for candidate in found:
        res.effects.append(_effect(ctx.unit, ctx.document, candidate, SourceEffect.MODIFICA.value,
                                   pair.new_start, pair.new_end))
    if not res.effects:
        return res.fallback(FALLBACK_ZERO)
    res.additions.extend(_added_obligations(ctx, pair, found))
    return res


_SENTENCE_BREAK = re.compile(r"(?<=[^\d][.;])\s+|\n+")
_LEADING_NUMBERING = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s*")


def _sentences(text, base):
    """Las oraciones de `text` con su posición absoluta (`base` es la de `text[0]`)."""
    start = 0
    for found in list(_SENTENCE_BREAK.finditer(text)) + [None]:
        end = found.start() if found else len(text)
        piece = text[start:end]
        lead = len(piece) - len(piece.lstrip())
        if piece.strip():
            yield base + start + lead, base + start + lead + len(piece.strip())
        if found:
            start = found.end()


def _similarity(a, b):
    """Parecido de dos oraciones por palabras: el mayor entre la secuencia común y el
    conjunto de palabras (cubre el orden distinto y una palabra cambiada o agregada)."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    sequence = difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()
    sa, sb = set(wa), set(wb)
    return max(sequence, len(sa & sb) / len(sa | sb))


def _added_obligations(ctx, pair, found):
    """Lo que el lado "debe decir" suma: las oraciones con marcador de obligación que no
    están en el lado "dice" ni en las citas alcanzadas. Las claramente nuevas son requisitos
    formales de origen `circular`; las que se parecen a una oración del lado "dice" (una
    reformulación) van como sugerencia. Una oración repetida da un solo requisito."""
    old_text = " ".join([pair.old] + [c.text for c in found])
    known = _norm(old_text)
    old_sentences = [old_text[a:b] for a, b in _sentences(old_text, 0)]
    canonical = ctx.document.reading.canonical_text
    out, seen = [], set()
    for member in ctx.unit.members:
        low = max(member.segment.char_start, pair.new_start)
        high = min(member.segment.char_end, pair.new_end)
        if low >= high:
            continue
        for start, end in _sentences(canonical[low:high], low):
            sentence = canonical[start:end]
            body = _norm(_LEADING_NUMBERING.sub("", sentence))
            if (not has_circular_obligation(sentence) or len(body) < MIN_CONTAINED_CHARS
                    or body in known or body in seen):
                continue
            seen.add(body)
            similar = any(_similarity(sentence, old) >= SIMILAR_SENTENCE
                          for old in old_sentences)
            out.append(Addition(RequirementClass.FORMAL.value, member.segment, start, end,
                                sentence, suggested=similar))
    return out


def _partial(text):
    """El reemplazo de una parte ("el plazo de pago por 60 días"): `(texto anterior,
    (inicio, fin) del nuevo dentro de `text`)` o `None`."""
    found = _PARTIAL.search(fold_aligned(text))
    if found is None:
        return None
    new_start = found.start("new")
    new_end = new_start + len(text[new_start:found.end("new")].rstrip())
    return text[found.start("old"):found.end("old")], (new_start, new_end)


def _without_names(text):
    """`text` sin las cláusulas y renglones que nombra: "en el Renglón N° 1" no dice qué texto
    cambia y coincidiría con el encabezado del renglón."""
    return circulars._CLAUSE.sub(" ", circulars._ITEM.sub(" ", text))


def _titles_in(text):
    """Los títulos entre comillas de anexos o documentos que nombra `text`, sin tildes ni
    mayúsculas (de dos palabras o más)."""
    return {fold(t).strip() for t in circulars._QUOTED_TITLE.findall(text)
            if len(fold(t).split()) >= 2}


def _mentions(text, annexes, titles):
    """Si `text` (sin tildes ni mayúsculas) nombra alguno de los anexos o títulos."""
    if annexes & set(circulars.named_annexes(text)):
        return True
    return any(title in text for title in titles)


def _asks_for_annex(candidate, annexes, titles):
    """Si la cláusula de la cita pide un anexo: lo nombra y le sigue un verbo de
    presentación sobre el anexo ("cargar y presentar la planilla del anexo")."""
    folded = candidate.folded
    return _mentions(folded, annexes, titles) and bool(_ASKS_FOR.search(folded))


def _in_annex(candidate, annexes):
    parts = {re.split(r"[#~]", p)[0].lower() for p in candidate.segment.key.split("/")}
    return any(f"anexo-{a}" in parts for a in annexes)




def _span_of_head(ctx):
    """El encabezado de la unidad (su primer tramo), entero: lo que dice que suprime o
    aclara."""
    first = ctx.unit.members[0].segment
    return first.char_start, first.char_end


def _whole_form(head):
    """Si el encabezado reemplaza la cláusula entera ("por la siguiente", "queda redactada")."""
    return bool(_WHOLE.search(fold_aligned(head)))


def _targets_of_clauses(ctx, res, head, change, clauses):
    """Las citas que una unidad que nombra cláusulas alcanza, o `None` si va al respaldo
    (con `res` ya marcada)."""
    res.target = {"tipo": "clausula", "referencia": sorted(clauses)}
    found, reason = _resolve_clauses(ctx, clauses)
    if reason:
        res.fallback(reason)
        return None
    whole = _whole_form(head) if change == CHANGE_REPLACES else (
        change == CHANGE_SUPPRESSES and bool(_CLAUSE_OBJECT.search(fold_aligned(head))))
    if whole:
        return found
    if len(found) == 1 and change in (CHANGE_REPLACES, CHANGE_CLARIFIES):
        return found
    partial = _partial(head) if change == CHANGE_REPLACES else None
    matched, reason = match_old_text(_without_names(partial[0] if partial else head), found)
    if reason:
        res.fallback(reason)
        return None
    return matched


def _targets_of_items(ctx, res, head, change, items):
    res.target = {"tipo": "renglon", "referencia": sorted(items)}
    pool = _item_candidates(ctx.candidates, items)
    if change == CHANGE_SUPPRESSES and _ITEM_OBJECT.search(fold_aligned(head)):
        return pool
    partial = _partial(head) if change == CHANGE_REPLACES else None
    matched, reason = match_old_text(_without_names(partial[0] if partial else head), pool)
    if reason:
        res.fallback(reason)
        return None
    return matched


def _new_text_of(ctx, whole):
    """Posiciones absolutas del texto nuevo de un `reemplaza`, o `None`."""
    if whole:
        marker = _WHOLE.search(fold_aligned(ctx.text))
        return _new_text_span(ctx, marker.end()) if marker else None
    partial = _partial(ctx.text)
    if partial is None:
        return None
    start = ctx.unit.start + partial[1][0]
    return start, ctx.unit.start + partial[1][1]


def _resolve_standard(ctx):
    """Cláusula numerada o apartado: el tipo por verbos y el objetivo por la clave."""
    res = Resolution(ctx.unit, OUTCOME_APPLIED)
    head = introducer(ctx.text)
    change = res.change = detect_change(head)
    if not change:
        return res.fallback(FALLBACK_NO_CHANGE)
    clauses, items = circulars.named_in(head)

    if change == CHANGE_ADDS:
        return _resolve_addition(ctx, res, head, clauses)

    if clauses:
        targets = _targets_of_clauses(ctx, res, head, change, clauses)
    elif items:
        targets = _targets_of_items(ctx, res, head, change, items)
    elif change == CHANGE_SUPPRESSES:
        annexes = circulars.named_annexes(head)
        titles = _titles_in(head)
        if not annexes and not titles:
            return res.fallback(FALLBACK_NO_TARGET)
        res.target = {"tipo": "anexo", "referencia": sorted(annexes | titles)}
        targets = [c for c in ctx.candidates
                   if _in_annex(c, annexes) or _asks_for_annex(c, annexes, titles)]
    else:
        return res.fallback(FALLBACK_NO_TARGET)
    if res.outcome == OUTCOME_FALLBACK:
        return res
    if not targets:
        return res.fallback(FALLBACK_ZERO)

    if change == CHANGE_REPLACES:
        span = _new_text_of(ctx, bool(clauses) and _whole_form(head))
        if span is None:
            return res.fallback(FALLBACK_NO_NEW_TEXT)
        effect = SourceEffect.MODIFICA.value
    else:
        span = _span_of_head(ctx)
        effect = (SourceEffect.SUPRIME if change == CHANGE_SUPPRESSES
                  else SourceEffect.ACLARA).value
    for candidate in targets:
        res.effects.append(_effect(ctx.unit, ctx.document, candidate, effect, *span))
    return res


def _resolve_addition(ctx, res, head, clauses):
    """Una cláusula nueva (que el pliego no tiene) es un requisito de origen `circular`."""
    if not clauses:
        return res.fallback(FALLBACK_NO_TARGET)
    res.target = {"tipo": "clausula", "referencia": sorted(clauses)}
    existing = ctx.pliego.numbers
    if any(n in existing or any(p.startswith(n + ".") for p in existing) for n in clauses):
        return res.fallback(FALLBACK_EXISTING_KEY)
    after = ctx.text.find(head) + len(head) if head else 0
    span = _new_text_span(ctx, after)
    if span is None:
        return res.fallback(FALLBACK_NO_NEW_TEXT)
    canonical = ctx.document.reading.canonical_text
    res.additions.append(Addition(RequirementClass.FORMAL.value, _segment_at(ctx.unit, span[0]),
                                  span[0], span[1], canonical[span[0]:span[1]]))
    return res


# --- Listas de datos del trámite -----------------------------------------------------------------------


def _body_members(unit):
    return [m for m in unit.members[1:]
            if m.segment.segment_type not in (SegmentType.TITULO, SegmentType.PAGINA)
            and (m.segment.text or "").strip()]


def is_procedure_data(unit):
    """Un apartado de líneas cortas, de la forma rótulo y valor, sin marcadores de
    obligación: fechas, horas, lugares, referentes. No son requisitos de la oferta."""
    if unit.kind != KIND_SECTION:
        return False
    lines = [m.segment.text.strip() for m in _body_members(unit)]
    if len(lines) < DATA_MIN_LINES:
        return False
    if any(has_circular_obligation(m.segment.text or "") for m in unit.members):
        return False
    labeled = sum(1 for line in lines if _LABELED.match(line))
    short = sum(1 for line in lines
                if len(line) <= SHORT_LINE_CHARS and not _LABELED.match(line))
    return (labeled / len(lines) >= DATA_LABELED_SHARE
            and (labeled + short) / len(lines) >= DATA_SHARE)


def _has_words(text, title):
    """Si `title` está en `text` como palabras completas y seguidas (sin mayúsculas, tildes,
    guiones ni guiones bajos), no como parte de otra palabra."""
    wanted = " ".join(_words(title))
    return bool(wanted) and f" {wanted} " in f" {' '.join(_words(text))} "


def _names_title(title, document_title, segments):
    """Si el documento lleva `title`: en su título (normalizado) o, si no, en sus primeros
    párrafos con texto (el primero suele ser el membrete de página)."""
    if _has_words(document_title, title):
        return True
    head = [s for s in segments if s.segment_type != SegmentType.PAGINA
            and (s.text or "").strip()][:HEAD_LINES]
    return any(_has_words(s.text, title) for s in head)


def _find_original(ctx, title, mentioning):
    """Dónde está en el pliego el anexo que lleva `title`: un documento que no es el de las
    citas y cuyo título lo nombra, o un anexo (`…/anexo-x`) cuyo encabezado lo nombra. `None`
    si no hay uno solo."""
    holders = {c.segment.reading_id for c in mentioning}
    title = _norm(title)
    by_reading = {}
    for unit in ctx.pliego.units:
        by_reading.setdefault(unit.segment.reading_id, []).append(unit.segment)
    found = {}
    for reading_id, segments in by_reading.items():
        if reading_id not in holders and _names_title(
                title, ctx.pliego.titles.get(reading_id, ""), segments):
            body = [s for s in segments if s.segment_type != SegmentType.PAGINA and s.text]
            if body:
                found[(reading_id, "")] = body
            continue
        for container in segments:
            parts = container.key.split("/")
            index = next((i for i, p in enumerate(parts) if p.lower().startswith("anexo-")),
                         None)
            if index is None or not _has_words(container.text, title):
                continue
            prefix = "/".join(parts[:index + 1])
            body = [s for s in segments
                    if (s.key == prefix or s.key.startswith(prefix + "/")) and s.text]
            if body:
                found[(reading_id, prefix)] = body
    if len(found) != 1:
        return None
    body = next(iter(found.values()))
    return Original(body[0], min(s.char_start for s in body), max(s.char_end for s in body))


def _resolve_data(ctx):
    """Una lista de datos: ningún requisito. Si la lista lleva el título de un anexo que
    alguna cita del pliego menciona, reemplaza ese anexo: una fuente `modifica` por cada
    una de esas citas, con la lista entera como texto vigente y el anexo como original."""
    res = Resolution(ctx.unit, OUTCOME_DATA, CHANGE_DATA)
    body = _body_members(ctx.unit)
    head = fold(" ".join(m.segment.text for m in ctx.unit.members[:HEAD_LINES]))
    titles = {t for c in ctx.candidates for t in _titles_in(c.text) if t in head}
    if len(titles) != 1 or not body:
        return res
    title = next(iter(titles))
    mentioning = [c for c in ctx.candidates if title in _titles_in(c.text)]
    start, end = body[0].segment.char_start, body[-1].segment.char_end
    original = _find_original(ctx, title, mentioning)
    res.target = {"tipo": "anexo", "referencia": [title]}
    for candidate in mentioning:
        res.effects.append(_effect(ctx.unit, ctx.document, candidate,
                                   SourceEffect.MODIFICA.value, start, end, original))
    return res


# --- Entrada -------------------------------------------------------------------------------------------------


@dataclass
class Pliego:
    """Los tramos del pliego (sin las circulares): sirven para saber qué claves existen y
    dónde está un anexo sin requisitos."""

    units: list = field(default_factory=list)
    titles: dict = field(default_factory=dict)       # lectura -> título del documento
    numbers: frozenset = frozenset()                 # números de cláusula que existen


def load_pliego(run):
    """El pliego de la propuesta (`run.documents`), solo lectura."""
    from evaluon.tenders.models import Segment
    from evaluon.tenders.proposal import extraction

    ids = [entry["reading"] for entry in run.documents]
    segments = list(Segment.objects.filter(reading_id__in=ids)
                    .select_related("reading__document").order_by("reading_id", "order"))
    units, titles, numbers = [], {}, set()
    for position, segment in enumerate(segments, start=1):
        title = segment.reading.document.title
        titles[segment.reading_id] = title
        units.append(extraction.Unit(segment, title, position))
        numbers.update(circulars._key_numbers(segment.key))
    return Pliego(units=units, titles=titles, numbers=frozenset(numbers))


def resolve(unit, document, candidates, pliego):
    """Resuelve una unidad de cambio sobre las citas del pliego (`circulars.Candidate`)."""
    if unit.kind == KIND_LOOSE:
        return Resolution(unit, OUTCOME_FALLBACK, reason=FALLBACK_LOOSE, record=False)
    ctx = _Ctx(unit, document, candidates, pliego)
    pair = find_pair(unit, ctx.text)
    if pair is False:
        return Resolution(unit, OUTCOME_FALLBACK, reason=FALLBACK_SEVERAL_PAIRS)
    if pair is not None:
        return _resolve_pair(ctx, pair)
    if is_procedure_data(unit):
        return _resolve_data(ctx)
    return _resolve_standard(ctx)
