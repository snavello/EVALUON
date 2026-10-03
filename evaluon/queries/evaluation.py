"""Corrida del conjunto de preguntas y medida de las exigencias de la spec (P7; REQ-008,
REQ-009, REQ-020, REQ-021; plan 001, "Evals"). Versión de T-039, con el diagnóstico de
T-042, el corrector y la recalificación de T-058, y los lotes, el margen de error y la
calibración por hueco de T-060 (ADR-0014, puntos 1 y 2).

`run(usuario, carpeta_de_casos, carpeta_de_corridas)`:

1. Comprueba el rol (lectura; el de lectura y escritura lo incluye).
2. Lee los casos: un archivo `EV-NNN.yaml` por pregunta (`load_cases`). Un caso mal
   formado, o sin `fecha_autorizacion`, se informa y no se corre; un caso sin
   `visto_bueno` (vacío, "pendiente" o "no") tampoco se corre. Los demás archivos de la
   carpeta se ignoran. El campo optativo `lote` dice a qué lote pertenece el caso (ver
   "Lotes", más abajo).
3. Corre cada caso con la misma función que la pantalla, `services.ask`, con el canal
   `eval` y la `fecha_autorizacion` del caso, una pregunta por vez. Nunca pasa una
   fecha vacía: la función de consulta usaría la del día. Cada consulta queda en el
   registro de auditoría como cualquier otra (P6). Un caso que la consulta rechaza (por
   ejemplo, una fecha posterior al día) no sale de la medida: cuenta como incorrecto o
   como no abstenido, y el resumen lo marca.
4. Mide cada caso (`grade`) y la corrida (`required_measures`, con `measure`):
   - cita literal, sobre toda la corrida: sobre todas las citas de todas las
     respuestas, `Unit.text` guardado y el texto que entrega `answering.citation_texts`
     para mostrar son iguales a `canonical_text[char_start:char_end]` de la lectura de
     la unidad, leído acá por separado. Umbral 100 %;
   - respuesta correcta que cita la unidad correcta, sobre las preguntas con respuesta
     del lote de aceptación: `grounded`, régimen aplicado igual a `regimen`, cita todas
     las `unidades` (si el caso nombra un inciso, vale el artículo que lo contiene),
     contiene los `datos_clave` y, con `difieren`, trae la marca `regimes_differ` en una
     afirmación que cita al régimen específico y al marco nacional. Al menos 85 %;
   - abstención, sobre las preguntas sin respuesta (`esperado: no determinado`) del lote
     de aceptación: cuenta si el resultado es `undetermined`; una falla técnica no
     cuenta. Al menos 90 %;
   - tiempo de cada consulta, sobre toda la corrida: mediana y máximo. Máximo de 30
     segundos.
   Sin casos del lote de aceptación, el resumen y el comando dicen que las exigencias de
   respuesta correcta y abstención no se pueden dar por cumplidas con la corrida. Las
   mismas medidas del lote de ajuste van aparte, como diagnóstico. Aparte, con toda la
   corrida, y se espera cero fallas: los pares de REQ-020 (`check_pairs`) y el aviso de
   REQ-021 (`notice_ok`).
5. Diagnóstico (T-042; plan, "Evals", y ADR-0003, "Cómo se mide"), que no son
   exigencias de la spec:
   - recuperación de cada caso (`case_diagnostics`), leída del registro de su consulta:
     unidad correcta entre los candidatos, por camino y en la unión; entre las
     enviadas al modelo; su posición en el orden del reranker; puntaje más alto; si el
     umbral la frenó; tiempo de la recuperación. Y la del lote de ajuste
     (`retrieval_measures`), con las preguntas con y sin respuesta frenadas por el
     umbral;
   - salidas con falla de formato (`invalid_output`) o de cita (`invalid_citation`),
     contadas por el `type` de las anomalías en toda la corrida: una falla de servicio
     no cuenta;
   - los casos de REQ-018 (etiqueta "dos categorías") y de REQ-019 (`difieren`), aparte,
     de toda la corrida;
   - respuesta correcta y abstención por régimen (`regimen` del caso), del lote de
     ajuste;
   - calibración del umbral (`calibrate`), con el puntaje más alto de cada pregunta del
     lote de ajuste;
   - comparación con la corrida anterior de la misma carpeta, lote por lote, con la
     igualdad al repetir (`compare_runs`);
   - a pedido (`ablation=True`), la comparación quitando piezas (`run_ablation`), con
     el lote de ajuste.
6. Guarda la corrida en `carpeta_de_corridas/<fecha>T<hora>_<commit>_<modelo>/`:
   `parametros.json`, `resultados.jsonl` (un renglón por caso, con su lote, también los
   que no se corrieron) y `resumen.md`. Los casos fallados del lote de aceptación van en
   su propia sección, con el aviso de que no se usan para ajustar.

Lotes (ADR-0014, punto 1; plan, "Evals", "Lote de aceptación"). `lote` vale `ajuste` o
`aceptacion`, comparado sin tildes ni mayúsculas; sin el campo, el caso es de ajuste, y
cualquier otro valor lo deja mal formado. El lote de ajuste (EV-001 a EV-031 y todo caso
sin `lote` o con `lote: ajuste`) es el que se usa para ajustar el corrector, los datos
clave, el umbral y las instrucciones, y para el diagnóstico. Del lote de aceptación salen
la respuesta correcta y la abstención exigidas; no se usa nunca para ajustar. Un renglón
guardado sin lote (corridas anteriores a T-060) es del lote de ajuste (`line_lot`); la
recalificación toma el lote del caso vigente.

Margen de error (plan, "Evals", "Margen de error"). Cada medida que es una proporción
(cita literal, respuesta correcta y abstención, en la tabla de las exigencias, en la del
lote de ajuste y en las medidas por régimen) se informa con su intervalo de confianza al
95 % por el método de Wilson (`wilson_interval`, `z = 1,96`): "90,0 % (9 de 10; IC
95 %: 59,6 % a 98,2 %)"; sin casos, "—". El tiempo no lleva intervalo.

Datos clave y corrector (`key_data_missing`; ADR-0011; plan, "Evals", "Datos clave y
corrector"; T-058). Cada elemento de `datos_clave` es un dato: un texto (una sola forma)
o una lista de variantes; lista vacía, texto vacío, lista dentro de la lista o valor que
no sea texto dejan el caso mal formado. Un dato se cumple si aparece cualquiera de sus
variantes; si falta, se informa con todas (lista en `resultados.jsonl`, " / " en
`resumen.md`). Una variante "sí" o "no" se cumple solo si la primera afirmación empieza
con esa palabra seguida de un signo de puntuación o del final ("No obstante, …" no es un
"no"); las demás se buscan en todas las afirmaciones. La respuesta y la variante se
normalizan igual (`normalize_for_search`): sin tildes, mayúsculas ni espacios repetidos;
un número en letras de cualquier tamaño pasa a su cifra, también seguido de su cifra
entre paréntesis; la cifra pierde el punto de miles; "5%", "5 %" y "cinco por ciento"
son "5 %" ("por mil" no se convierte). Cada palabra de la variante vale en singular o
plural (diferencia final de "s", de "es", o de "z" por "ces"); las palabras van
seguidas, en el mismo orden, sin una letra, un dígito o un separador de número pegados
antes o después. No hay sinónimos: otra forma correcta entra como variante del caso. En
la corrida que se presenta para aprobar, el responsable revisa además las respuestas
contra la esperada (plan, "Evals").

Calibración por la regla del hueco (ADR-0014, punto 2; plan, "Abstención", "Calibración
del umbral"). Reemplaza la regla de T-042 (dejar una afuera y frenar a lo sumo el 5 %).
Entran solo casos del lote de ajuste, cada uno con su puntaje más alto: las preguntas
con respuesta con puntaje y las sin respuesta con la etiqueta "ajena a la normativa" con
puntaje; las de "tema cercano que la normativa no resuelve" no entran, porque las tiene
que frenar el modelo. `A` es la ajena más alta y `B` la pregunta con respuesta más baja.
Cada puntaje se acota entre 10⁻⁹ y 1 − 10⁻⁹ y se pasa a la escala anterior a la
sigmoide, `logit(p) = ln(p / (1 − p))`. Hay hueco si `logit(B) > logit(A)`: el umbral
propuesto es `sigmoid((logit(A) + logit(B)) / 2)`, redondeado hacia abajo a tres
decimales (la selección pasa con puntaje igual o mayor), y el margen es
`(logit(B) − logit(A)) / 2`, con un mínimo de 0,5 (`CALIBRATION_MIN_MARGIN`). Sin margen
suficiente, el valor se informa marcado: no se fija sin decisión del responsable. Sin
hueco, no hay umbral propuesto: se listan las ajenas con puntaje mayor o igual que `B` y
las preguntas con respuesta con puntaje menor o igual que `A`, y decide el responsable.
Sin ajenas o sin preguntas con respuesta con puntaje, la regla no se aplica y se dice
por qué. Se informan además las preguntas sin respuesta que frenan el umbral propuesto y
el actual, las de tema cercano por encima del propuesto, las preguntas con respuesta sin
puntaje y la tabla de puntajes del lote de ajuste. El valor es uno solo para los dos
regímenes, se informa como provisorio y no cambia `settings.py`.

Comparación quitando piezas (ADR-0003). Cada caso del lote de ajuste se corre con cuatro
configuraciones de `retrieval.retrieve(..., paths=, rerank=)` seguido de
`retrieval.select_units`, sin pasar por la consulta ni por el modelo de generación: solo
vectores (camino por significado, con reranker), solo palabras (camino por palabras, con
reranker), combinada sin reranker (los tres caminos, sin umbral) y completa. Para una
fecha sin régimen cargado no se busca, igual que en la consulta. "Entre las
seleccionadas" es lo que selecciona la recuperación (`retrieve(...).selected`: sin
reranker, toda la unión, así que coincide con "entre los candidatos", aclaración de
T-032); "entre las enviadas al modelo" es lo que deja `select_units` con los cupos y el
espacio. Estas recuperaciones no crean consultas ni hechos del registro de auditoría: lo
que recuperó cada configuración queda en `resultados.jsonl` de la corrida.
"""

import json
import math
import re
import statistics
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.ai import AIServiceError, generation
from evaluon.audit.models import Channel
from evaluon.audit.services import current_corpus_version
from evaluon.norms.models import Category, Unit, UnitType
from evaluon.queries import answering, retrieval, services
from evaluon.queries.models import Reason, Status

# Umbrales de las exigencias de la spec (plan 001, "Cómo se mide cada exigencia").
LITERAL_THRESHOLD = 1.0
CORRECT_THRESHOLD = 0.85
ABSTENTION_THRESHOLD = 0.90
MAX_SECONDS = 30.0

# Comparación con la corrida anterior: filas de tiempo y suba de la mediana que cuenta
# como baja (decisión del Coordinador, cierre de T-042).
TIME_MEDIAN = "response_time_median"
TIME_MAX = "response_time"
MEDIAN_RISE_LIMIT = 0.25

# Medidas que son proporciones: llevan margen de error y se comparan lote por lote.
PROPORTIONS = ("literal_citation", "correct_answer", "abstention")

NO_ANSWER = "no determinado"
PENDING_AMENDMENTS = "pending_amendments"

# Por qué un caso no se corrió.
MALFORMED = "malformed"
NOT_APPROVED = "not_approved"
REFUSED = "refused"
NOT_RESCORABLE = "not_rescorable"

# Sufijo de la carpeta de una recalificación y aviso que va en su `parametros.json`.
RESCORED_SUFFIX = "_recalificada"
RESCORE_NOTE = ("Recalificación: no se hicieron consultas ni se llamó a ningún servicio "
                "de IA. Las respuestas son las de la corrida de origen, medidas otra vez "
                "con los casos y el corrector vigentes.")

# Valores de `visto_bueno` que no son visto bueno, ya normalizados.
NOT_AN_APPROVAL = {"", "pendiente", "no"}

CASE_GLOB = "EV-*.yaml"
NO_COMMIT = "sin-commit"

# Estados de un par de REQ-020.
PAIR_PASSES = "pasa"
PAIR_FAILS = "falla"
PAIR_INCOMPLETE = "incompleto"

# Calibración por la regla del hueco (ADR-0014, punto 2; plan, "Abstención"): margen
# mínimo en la escala anterior a la sigmoide, decimales del umbral propuesto y cota de
# los puntajes antes de pasarlos a `logit`, para que un 0 o un 1 no den infinito.
CALIBRATION_MIN_MARGIN = 0.5
CALIBRATION_DECIMALS = 3
SCORE_BOUND = 1e-9

# Etiquetas de las preguntas sin respuesta (plan, "Evals", `etiquetas`), ya normalizadas.
FOREIGN = "ajena a la normativa"
NEAR = "tema cercano que la normativa no resuelve"

# Lotes (ADR-0014, punto 1; plan, "Evals", "Lote de aceptación"). Sin `lote`, el caso
# es del lote de ajuste.
ADJUSTMENT = "ajuste"
ACCEPTANCE = "aceptacion"
LOTS = (ACCEPTANCE, ADJUSTMENT)
LOT_TEXT = {ACCEPTANCE: "aceptación", ADJUSTMENT: "ajuste"}

# Margen de error: intervalo de Wilson al 95 % (plan, "Evals", "Margen de error").
WILSON_Z = 1.96

# Etiqueta de los casos de REQ-018 (plan, "Evals", `etiquetas`), ya normalizada.
TWO_CATEGORIES = "dos categorias"

# Lo que se mide de la recuperación: los caminos y la unión.
UNION = "union"

# Tipos de anomalía que son salidas con falla de formato o de cita (aviso de T-019).
FORMAT_FAILURE = Reason.INVALID_OUTPUT.value
CITATION_FAILURE = Reason.INVALID_CITATION.value

# Comparación quitando piezas (ADR-0003): nombre, caminos y reranker.
ABLATION_CONFIGS = (
    ("solo vectores", (retrieval.SEMANTIC,), True),
    ("solo palabras", (retrieval.WORDS,), True),
    ("combinada sin reranker", retrieval.ALL_PATHS, False),
    ("completa", retrieval.ALL_PATHS, True),
)

REQUIRED_FIELDS = (
    "id", "pregunta", "esperado", "fecha_autorizacion", "regimen", "unidades",
    "datos_clave", "difieren", "pareja", "aviso_modificatorias", "etiquetas",
    "visto_bueno",
)


class CaseError(ValueError):
    """El caso está mal formado. El mensaje dice por qué, en lenguaje llano."""


@dataclass(frozen=True)
class Case:
    """Un caso del conjunto de preguntas, ya validado."""

    id: str
    file: str
    question: str
    reference_date: date
    regime: str
    has_answer: bool
    units: tuple  # pares (norma, key)
    key_data: tuple  # cada dato, una tupla de variantes
    differ: bool
    pair: str
    notice: bool
    approval: str
    labels: tuple = ()
    lot: str = ADJUSTMENT


@dataclass(frozen=True)
class Skipped:
    """Un caso que no se corrió: `kind` es `malformed`, `not_approved` o `refused`."""

    file: str
    case_id: str
    kind: str
    reason: str


# --- Lectura de los casos --------------------------------------------------------------


def _text(data, name, *, empty=True):
    value = data.get(name)
    if value is None and empty:
        return ""
    if not isinstance(value, str):
        raise CaseError(f"`{name}` tiene que ser un texto")
    if not empty and not value.strip():
        raise CaseError(f"`{name}` no puede estar vacío")
    return value.strip()


def _flag(data, name):
    value = data.get(name)
    if not isinstance(value, bool):
        raise CaseError(f"`{name}` tiene que ser verdadero o falso")
    return value


def _texts(data, name):
    value = data.get(name)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CaseError(f"`{name}` tiene que ser una lista de textos")
    return tuple(v.strip() for v in value)


def _key_data(data):
    """`datos_clave` como una tupla de datos, cada uno una tupla de variantes (plan,
    "Datos clave y corrector"): un texto solo es un dato de una variante; una lista son
    las variantes del dato."""
    value = data.get("datos_clave")
    if not isinstance(value, list):
        raise CaseError("`datos_clave` tiene que ser una lista")
    key_data = []
    for item in value:
        if isinstance(item, str):
            if not item.strip():
                raise CaseError("`datos_clave` tiene un dato vacío")
            key_data.append((item.strip(),))
            continue
        if not isinstance(item, list):
            raise CaseError("cada dato de `datos_clave` tiene que ser un texto entre "
                            "comillas o una lista de textos entre comillas")
        if not item:
            raise CaseError("`datos_clave` tiene una lista de variantes vacía")
        for variant in item:
            if isinstance(variant, list):
                raise CaseError("`datos_clave` tiene una lista dentro de la lista de "
                                "variantes de un dato")
            if not isinstance(variant, str):
                raise CaseError("cada variante de `datos_clave` tiene que ser un texto "
                                "entre comillas")
            if not variant.strip():
                raise CaseError("`datos_clave` tiene una variante vacía")
        key_data.append(tuple(variant.strip() for variant in item))
    return tuple(key_data)


def _reference_date(data):
    value = data.get("fecha_autorizacion")
    if value is None or value == "":
        raise CaseError("falta `fecha_autorizacion`, que no tiene valor por omisión")
    if isinstance(value, datetime):
        raise CaseError("`fecha_autorizacion` tiene que ser una fecha AAAA-MM-DD, sin hora")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise CaseError("`fecha_autorizacion` tiene que ser una fecha AAAA-MM-DD") from None


def _units(data):
    value = data.get("unidades")
    if not isinstance(value, list):
        raise CaseError("`unidades` tiene que ser una lista")
    units = []
    for item in value:
        if (not isinstance(item, dict)
                or not isinstance(item.get("norma"), str) or not item["norma"].strip()
                or not isinstance(item.get("key"), str) or not item["key"].strip()):
            raise CaseError("cada unidad de `unidades` necesita `norma` y `key`")
        units.append((item["norma"].strip(), item["key"].strip()))
    return tuple(units)


def _approval(data):
    value = data.get("visto_bueno")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder) if value else ""
    raise CaseError("`visto_bueno` tiene que ser un texto")


def _lot(data):
    """`lote`: `ajuste` o `aceptacion`, sin distinguir tildes ni mayúsculas; sin el
    campo, `ajuste` (plan, "Evals", `lote`)."""
    value = data.get("lote")
    if value is None:
        return ADJUSTMENT
    lot = normalize(value) if isinstance(value, str) else None
    if lot not in LOTS:
        raise CaseError(f"`lote` tiene que ser `{ADJUSTMENT}` o `{ACCEPTANCE}` (dice "
                        f"{json.dumps(value, ensure_ascii=False, default=str)})")
    return lot


def line_lot(line):
    """El lote de un renglón de una corrida. Un renglón guardado sin lote (corridas
    anteriores a T-060) es del lote de ajuste."""
    return line.get("lot") or ADJUSTMENT


def lot_lines(lines, lot):
    """Los renglones de `lines` del lote `lot`."""
    return [line for line in lines if line_lot(line) == lot]


def parse_case(path):
    """Lee y valida un caso. Devuelve un `Case` o lanza `CaseError`."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise CaseError(f"no se puede leer como YAML ({error.__class__.__name__})") from None
    if not isinstance(data, dict):
        raise CaseError("no tiene la forma de un caso")
    missing = [name for name in REQUIRED_FIELDS
               if name not in data and name != "fecha_autorizacion"]
    if missing:
        raise CaseError("faltan los datos " + ", ".join(f"`{n}`" for n in missing))

    case_id = _text(data, "id", empty=False)
    if case_id != Path(path).stem:
        raise CaseError(f"`id` ({case_id}) no coincide con el nombre del archivo")
    reference_date = _reference_date(data)
    expected = _text(data, "esperado", empty=False)
    has_answer = expected.casefold() != NO_ANSWER
    regime = _text(data, "regimen")
    units = _units(data)
    differ = _flag(data, "difieren")
    pair = _text(data, "pareja")
    labels = _texts(data, "etiquetas")

    if has_answer and not units:
        raise CaseError("una pregunta con respuesta necesita `unidades`")
    if has_answer and not regime:
        raise CaseError("una pregunta con respuesta necesita `regimen`")
    if not has_answer and units:
        raise CaseError("una pregunta sin respuesta no lleva `unidades`")
    if differ and not has_answer:
        raise CaseError("`difieren` solo va en una pregunta con respuesta")
    if pair == case_id:
        raise CaseError("`pareja` no puede ser el mismo caso")

    return Case(
        id=case_id,
        file=Path(path).name,
        question=_text(data, "pregunta", empty=False),
        reference_date=reference_date,
        regime=regime,
        has_answer=has_answer,
        units=units,
        key_data=_key_data(data),
        differ=differ,
        pair=pair,
        notice=_flag(data, "aviso_modificatorias"),
        approval=_approval(data),
        labels=labels,
        lot=_lot(data),
    )


def is_approved(approval):
    """Un visto bueno vacío, "pendiente" o "no" (sin distinguir mayúsculas ni tildes) no
    es visto bueno."""
    return normalize(approval or "") not in NOT_AN_APPROVAL


def load_cases(directory):
    """Lee los `EV-*.yaml` de `directory`, en orden de nombre. Devuelve `(casos, no
    corridos)`: los casos bien formados y con visto bueno, y un `Skipped` por cada uno de
    los demás."""
    cases, skipped = [], []
    for path in sorted(Path(directory).glob(CASE_GLOB)):
        try:
            case = parse_case(path)
        except CaseError as error:
            skipped.append(Skipped(path.name, path.stem, MALFORMED, f"mal formado: {error}"))
            continue
        if not is_approved(case.approval):
            skipped.append(Skipped(path.name, case.id, NOT_APPROVED,
                                   "sin visto bueno de la Comisión"))
            continue
        cases.append(case)
    return cases, skipped


# --- Medida de un caso -----------------------------------------------------------------


def normalize(text):
    """Texto sin tildes, sin distinguir mayúsculas y con los espacios repetidos
    reducidos a uno."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain.casefold()).strip()


# Palabras de un número escrito en letras, ya sin tildes ni mayúsculas.
_NUMBER_WORD = (
    r"(?:un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|"
    r"catorce|quince|dieci[a-z]+|veinte|veinti[a-z]+|treinta|cuarenta|cincuenta|"
    r"sesenta|setenta|ochenta|noventa|cien|ciento|[a-z]+cientos|[a-z]+cientas|"
    r"quinientos|quinientas|mil|millon|millones)"
)
# "sesenta (60)", "treinta y cinco (35)", "cinco por ciento (5%)": queda la cifra.
_WORDS_WITH_FIGURE = re.compile(
    rf"\b{_NUMBER_WORD}(?:\s+(?:y\s+)?{_NUMBER_WORD})*(?:\s+por\s+ciento)?\s*"
    r"\(\s*(\d[\d.,]*(?:\s*%)?)\s*\)"
)

# Valores de las palabras de un número, por clase (ver `_number_at`).
_UNITS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
          "seis": 6, "siete": 7, "ocho": 8, "nueve": 9}
_TENS_TO_TWENTIES = {
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29,
}
_TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
         "ochenta": 80, "noventa": 90}
_HUNDREDS = {"cien": 100, "ciento": 100}
for _name, _value in (("dos", 2), ("tres", 3), ("cuatro", 4), ("seis", 6), ("sete", 7),
                      ("ocho", 8), ("nove", 9)):
    _HUNDREDS[f"{_name}cientos"] = _HUNDREDS[f"{_name}cientas"] = _value * 100
_HUNDREDS["quinientos"] = _HUNDREDS["quinientas"] = 500
_THOUSAND = "mil"
_MILLION = {"millon", "millones"}
# Después de "por", "ciento", "cien" y "mil" no son números: "cinco por ciento" es un
# porcentaje y "cinco por mil" queda "5 por mil" (plan, "Datos clave y corrector").
_NOT_AFTER_POR = {"ciento", "cien", _THOUSAND}

# Una palabra: letras, sin dígitos ni guion bajo.
_WORD = re.compile(r"[^\W\d_]+")
# Una cifra con punto de miles: "1.000", "2.500.000".
_THOUSANDS_POINT = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?!\d)")

# Datos clave que se responden con la primera palabra de la respuesta.
_YES_NO = {"si", "no"}


def _number_at(text, words, start):
    """El número en letras que empieza en la palabra `words[start]`: `(valor, índice de
    la palabra siguiente, fin en el texto)`, o `None` si ahí no empieza un número.

    Toma la sucesión más larga de palabras de número separadas por un espacio que forma
    un número bien escrito: centenas, decenas, "y" y unidades en ese orden dentro de
    cada grupo de tres cifras, y "mil" y "millón" o "millones" como multiplicadores. Lo
    que no encaja corta el número: "dos tres" son dos números."""
    first = words[start].group()
    if start and first in _NOT_AFTER_POR and words[start - 1].group() == "por" \
            and text[words[start - 1].end():words[start].start()] == " ":
        return None
    total = group = 0
    # Qué admite el grupo actual: 3 vacío, 2 después de una centena, 1 después de una
    # decena que admite "y" y unidad, 0 cerrado.
    level = 3
    thousands = millions = False
    index, end = start, None
    while index < len(words):
        word = words[index].group()
        if index > start and text[words[index - 1].end():words[index].start()] != " ":
            break
        if word == "y":
            following = words[index + 1] if index + 1 < len(words) else None
            if (level == 1 and following is not None and following.group() in _UNITS
                    and text[words[index].end():following.start()] == " "):
                group += _UNITS[following.group()]
                level, end, index = 0, following.end(), index + 2
                continue
            break
        if word in _HUNDREDS and level == 3:
            group += _HUNDREDS[word]
            level = 0 if word == "cien" else 2
        elif word in _TENS and level >= 2:
            group += _TENS[word]
            level = 1
        elif word in _TENS_TO_TWENTIES and level >= 2:
            group += _TENS_TO_TWENTIES[word]
            level = 0
        elif word in _UNITS and level >= 2:
            group += _UNITS[word]
            level = 0
        elif word == _THOUSAND and not thousands:
            total += (group or 1) * 1000
            group, level, thousands = 0, 3, True
        elif word in _MILLION and not (millions or thousands):
            total += (group or 1) * 1_000_000
            group, level, millions = 0, 3, True
        else:
            break
        end, index = words[index].end(), index + 1
    if end is None:
        return None
    return total + group, index, end


def _numbers_to_figures(text):
    """Cada número escrito en letras, de cualquier tamaño, pasa a su cifra: "treinta" a
    "30", "treinta y cinco" a "35", "ciento veinte" a "120", "dos mil quinientos" a
    "2500". `text` ya está normalizado (`normalize`)."""
    words = list(_WORD.finditer(text))
    pieces, position, index = [], 0, 0
    while index < len(words):
        found = _number_at(text, words, index)
        if found is None:
            index += 1
            continue
        value, index_after, end = found
        pieces += [text[position:words[index].start()], str(value)]
        position, index = end, index_after
    pieces.append(text[position:])
    return "".join(pieces)


def normalize_for_search(text):
    """Texto de la respuesta o de una variante de un dato clave tal como se comparan
    (ADR-0011; plan, "Datos clave y corrector", regla 3): además de `normalize`, un
    número en letras seguido de su cifra entre paréntesis queda solo con la cifra
    ("sesenta (60) días" pasa a "60 días"); un número en letras de cualquier tamaño
    pasa a su cifra ("ciento veinte" a "120"; "un", "una" y "uno" a "1"); una cifra con
    punto de miles lo pierde ("1.000" a "1000") y la coma decimal se mantiene; "por
    ciento" después de una cifra es el signo de porcentaje ("uno por ciento" pasa a "1
    %") y el signo va siempre separado por un espacio ("5%" a "5 %"). "Por mil" no se
    convierte ("cinco por mil" es "5 por mil")."""
    text = normalize(text)
    text = _WORDS_WITH_FIGURE.sub(lambda m: m.group(1), text)
    text = _numbers_to_figures(text)
    text = _THOUSANDS_POINT.sub(lambda m: m.group().replace(".", ""), text)
    text = re.sub(r"(\d)\s+por\s+ciento\b", r"\1 %", text)
    text = re.sub(r"(\d)\s*%", r"\1 %", text)
    return re.sub(r"\s+", " ", text).strip()


def _word_forms(word):
    """Las formas de `word` que valen en la respuesta (regla 4): igual, o con una
    diferencia final de "s", de "es", o de "z" por "ces", en los dos sentidos."""
    forms = {word, word + "s", word + "es"}
    if word.endswith("z"):
        forms.add(word[:-1] + "ces")
    if word.endswith("ces"):
        forms.add(word[:-3] + "z")
    if word.endswith("es"):
        forms.add(word[:-2])
    if word.endswith("s"):
        forms.add(word[:-1])
    forms.discard("")
    return sorted(forms, key=lambda form: (-len(form), form))


def _variant_pattern(variant):
    """Expresión que busca la variante ya normalizada (`normalize_for_search`) con
    singular y plural por palabra, las palabras seguidas y en el mismo orden, y los
    límites de `_contains`."""
    body, position = [], 0
    for word in _WORD.finditer(variant):
        body.append(re.escape(variant[position:word.start()]))
        body.append("(?:" + "|".join(re.escape(f) for f in _word_forms(word.group())) + ")")
        position = word.end()
    body.append(re.escape(variant[position:]))
    return r"(?<!\w)(?<!\d[.,])" + "".join(body) + r"(?!\w)(?![.,]\d)"


def _contains(text, fragment):
    """`fragment` aparece en `text`, cada palabra igual o en singular o plural
    (`_word_forms`), sin una letra, un dígito o un separador de número pegados antes o
    después. Una coma o un punto cuentan como pegados solo si están junto a un dígito
    ("0,1 %", "21.000"); el que cierra una frase no."""
    if not fragment:
        return True
    return re.search(_variant_pattern(fragment), text) is not None


def _is_punctuation(char):
    return unicodedata.category(char).startswith("P")


def _starts_with(text, word):
    """La afirmación empieza con `word`, salteando signos de puntuación y espacios
    iniciales, y a la palabra le sigue un signo de puntuación o el final (aviso de
    T-039): "No, …", "¡Sí!" y "«No»" cuentan; "No obstante, …" y "No hace falta" no."""
    index = 0
    while index < len(text) and (text[index].isspace() or _is_punctuation(text[index])):
        index += 1
    rest = text[index:]
    if not rest.startswith(word):
        return False
    after = rest[len(word):]
    return not after or _is_punctuation(after[0])


def _variants(datum):
    """Las variantes de un dato: un texto solo es una variante."""
    return [datum] if isinstance(datum, str) else list(datum)


def key_data_missing(key_data, statements):
    """Los datos clave que no están en las afirmaciones `statements` (textos, en orden),
    cada uno como la lista de todas sus variantes (ADR-0011; plan, "Datos clave y
    corrector").

    Cada dato es un texto o una lista de variantes, y se cumple si aparece cualquiera.
    Una variante "sí" o "no" se cumple solo si la primera afirmación empieza con esa
    palabra seguida de un signo de puntuación o del final. Las demás se buscan en todas
    las afirmaciones con `normalize_for_search` y `_contains`."""
    first = normalize(statements[0]) if statements else ""
    text = normalize_for_search("\n".join(statements))
    missing = []
    for datum in key_data:
        variants = _variants(datum)
        if not any(_variant_found(variant, first, text) for variant in variants):
            missing.append(variants)
    return missing


def _variant_found(variant, first, text):
    plain = normalize(variant)
    if plain in _YES_NO:
        return _starts_with(first, plain)
    return _contains(text, normalize_for_search(variant))


def key_data_text(missing):
    """Los datos faltantes para leer: las variantes de cada uno separadas por " / ", y
    los datos entre comillas y separados por coma. Acepta también la forma anterior a
    T-058, un texto por dato."""
    return ", ".join(f"\"{' / '.join(_variants(datum))}\"" for datum in missing)


def _statement_citations(result):
    return [unit_id for s in result.get("statements") or [] for unit_id in s["citations"]]


def cited_units(result):
    """Cada unidad citada en el resultado, una vez y en orden de aparición, con su norma
    (nombre de cita), su clave, su tipo, su categoría y la comprobación de cita literal
    contra `canonical_text[char_start:char_end]` de su lectura, en dos partes:

    - `stored_text_ok`: `Unit.text` guardado es igual al recorte (datos que se apartan
      del original);
    - `shown_text_ok`: el texto que entrega `answering.citation_texts` para mostrar
      también lo es.

    `literal` es verdadero solo si se cumplen las dos."""
    ids = list(dict.fromkeys(_statement_citations(result)))
    units = Unit.objects.select_related("reading__document__norm").in_bulk(ids)
    try:
        shown = answering.citation_texts(result)
    except (KeyError, ValueError):
        shown = {}
    cited = []
    for unit_id in ids:
        unit = units.get(unit_id)
        if unit is None:
            cited.append({"unit": unit_id, "norm": None, "key": None, "unit_type": None,
                          "category": None, "stored_text_ok": False,
                          "shown_text_ok": False, "literal": False})
            continue
        norm = unit.reading.document.norm
        expected = unit.reading.canonical_text[unit.char_start:unit.char_end]
        stored_ok = unit.text == expected
        shown_ok = unit_id in shown and shown[unit_id] == expected
        cited.append({
            "unit": unit_id,
            "norm": norm.citation,
            "key": unit.key,
            "unit_type": unit.unit_type,
            "category": norm.category,
            "stored_text_ok": stored_ok,
            "shown_text_ok": shown_ok,
            "literal": stored_ok and shown_ok,
        })
    return cited


def _unit_matches(expected, unit):
    norm, key = expected
    if unit["norm"] != norm:
        return False
    if unit["key"] == key:
        return True
    # Si el caso nombra un inciso, vale el artículo que lo contiene.
    return unit["unit_type"] == UnitType.ARTICULO and key.startswith(unit["key"] + "/")


def _differ_ok(result, by_id):
    for statement in result.get("statements") or []:
        if statement.get("regimes_differ") is not True:
            continue
        categories = {by_id[u]["category"] for u in statement["citations"] if u in by_id}
        if {Category.REGIMEN_ESPECIFICO.value, Category.MARCO_NACIONAL.value} <= categories:
            return True
    return False


def notice_ok(expected, result):
    """Comprobación de REQ-021: el resultado trae algún aviso de modificatorias sin
    cargar exactamente cuando el caso lo pide."""
    has_notice = any(n.get("type") == PENDING_AMENDMENTS
                     for n in result.get("notices") or [])
    return has_notice == bool(expected)


def grade(case, result, cited):
    """Medidas de un caso a partir de su resultado guardado y de `cited_units(result)`."""
    by_id = {unit["unit"]: unit for unit in cited}
    citations = _statement_citations(result)
    literal = sum(1 for u in citations if by_id.get(u, {}).get("literal"))
    regime = [r["name"] for r in result.get("regime") or []]
    status = result.get("status")

    measures = {
        "citations": len(citations),
        "literal_citations": literal,
        "correct": None,
        "abstained": None,
        "notice_ok": notice_ok(case.notice, result),
        "checks": {},
        "missing_units": [],
        "missing_key_data": [],
    }
    if not case.has_answer:
        measures["abstained"] = status == Status.UNDETERMINED
        return measures

    missing_units = [u for u in case.units
                     if not any(_unit_matches(u, unit) for unit in cited)]
    missing_data = key_data_missing(
        case.key_data, [s["text"] for s in result.get("statements") or []])
    checks = {
        "status": status == Status.GROUNDED,
        "regime": regime == ([case.regime] if case.regime else []),
        "units": not missing_units,
        "key_data": not missing_data,
    }
    if case.differ:
        checks["regimes_differ"] = _differ_ok(result, by_id)
    measures.update(
        correct=all(checks.values()),
        checks=checks,
        missing_units=[{"norma": n, "key": k} for n, k in missing_units],
        missing_key_data=missing_data,
    )
    return measures


def _passed(line):
    measures = line["measures"]
    answered = measures["correct"] if line["has_answer"] else measures["abstained"]
    return bool(answered)


# --- Pares de REQ-020 ------------------------------------------------------------------


def check_pairs(lines):
    """Un par pasa si sus dos casos tienen la misma pregunta, cada uno pasa por su
    cuenta y las normas citadas son distintas. Si uno de los dos no se corrió, el par
    queda incompleto. `lines` son los renglones de los casos corridos."""
    by_id = {line["id"]: line for line in lines}
    pairs = []
    seen = set()
    for line in lines:
        if not line["pair"]:
            continue
        ids = tuple(sorted((line["id"], line["pair"])))
        if ids in seen:
            continue
        seen.add(ids)
        missing = [case_id for case_id in ids if case_id not in by_id]
        if missing:
            pairs.append({"cases": list(ids), "status": PAIR_INCOMPLETE,
                          "problems": [f"{case_id} no se corrió" for case_id in missing]})
            continue
        first, second = by_id[ids[0]], by_id[ids[1]]
        problems = []
        if first["pair"] != second["id"] or second["pair"] != first["id"]:
            problems.append("los dos casos no se nombran entre sí como pareja")
        if first["question"].strip() != second["question"].strip():
            problems.append("las preguntas no son iguales")
        problems.extend(f"{one['id']} no pasa por su cuenta"
                        for one in (first, second) if not one["passed"])
        norms = [{u["norm"] for u in one["cited_units"]} for one in (first, second)]
        if norms[0] == norms[1]:
            problems.append("los dos casos citan las mismas normas")
        pairs.append({"cases": list(ids),
                      "status": PAIR_FAILS if problems else PAIR_PASSES,
                      "problems": problems})
    return pairs


# --- Medidas de la corrida -------------------------------------------------------------


def wilson_interval(ok, total, z=WILSON_Z):
    """Intervalo de confianza de la proporción `ok / total` por el método de Wilson,
    como `(inferior, superior)` entre 0 y 1, o `None` sin casos (plan, "Evals", "Margen
    de error"):

        centro = (p + z²/(2n)) / (1 + z²/n)
        radio  = z / (1 + z²/n) · √( p(1 − p)/n + z²/(4n²) )
    """
    if not total:
        return None
    p = ok / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    radius = z / denominator * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
    return max(0.0, center - radius), min(1.0, center + radius)


def _ratio(ok, total, threshold):
    rate = ok / total if total else None
    low, high = wilson_interval(ok, total) or (None, None)
    return {"ok": ok, "total": total, "rate": rate, "low": low, "high": high,
            "threshold": threshold,
            "meets": None if rate is None else rate >= threshold}


def measure(lines):
    """Las cuatro medidas sobre los renglones de los casos medidos: los corridos y los
    que la consulta rechazó, que cuentan como incorrectos o no abstenidos. El tiempo se
    mide solo sobre las consultas hechas. Cada proporción trae su intervalo de Wilson
    (`low` y `high`)."""
    answered = [line for line in lines if line["has_answer"]]
    unanswerable = [line for line in lines if not line["has_answer"]]
    times = [line["time_seconds"] for line in lines if line["time_seconds"] is not None]
    longest = max(times) if times else None
    return {
        "literal_citation": _ratio(
            sum(line["measures"]["literal_citations"] for line in lines),
            sum(line["measures"]["citations"] for line in lines),
            LITERAL_THRESHOLD),
        "correct_answer": _ratio(
            sum(1 for line in answered if line["measures"]["correct"]),
            len(answered), CORRECT_THRESHOLD),
        "abstention": _ratio(
            sum(1 for line in unanswerable if line["measures"]["abstained"]),
            len(unanswerable), ABSTENTION_THRESHOLD),
        "response_time": {
            "median": statistics.median(times) if times else None,
            "max": longest,
            "threshold": MAX_SECONDS,
            "meets": None if longest is None else longest <= MAX_SECONDS,
        },
    }


def required_measures(lines):
    """Las medidas exigidas (ADR-0014; plan, "Qué usa cada lote"): la cita literal y el
    tiempo sobre toda la corrida; la respuesta correcta y la abstención sobre el lote de
    aceptación. `acceptance_cases` es la cantidad de casos medidos de ese lote: sin
    ninguno, las exigencias no se pueden dar por cumplidas con la corrida."""
    whole = measure(lines)
    acceptance = lot_lines(lines, ACCEPTANCE)
    accepted = measure(acceptance)
    return {
        "literal_citation": whole["literal_citation"],
        "correct_answer": accepted["correct_answer"],
        "abstention": accepted["abstention"],
        "response_time": whole["response_time"],
        "acceptance_cases": len(acceptance),
    }


# --- Diagnóstico de la recuperación (T-042; ADR-0003, "Cómo se mide") --------------------


def _unit_info(ids):
    """`{id: {"norm", "key", "unit_type"}}` de las unidades `ids`, para compararlas con
    las `unidades` de un caso como en la respuesta correcta (`_unit_matches`)."""
    units = Unit.objects.select_related("reading__document__norm").in_bulk(set(ids))
    return {pk: {"norm": unit.reading.document.norm.citation, "key": unit.key,
                 "unit_type": unit.unit_type} for pk, unit in units.items()}


def _all_found(expected, ids, info):
    return all(any(_unit_matches(unit, info[pk]) for pk in ids if pk in info)
               for unit in expected)


def _worst_position(expected, ranked, info):
    positions = []
    for unit in expected:
        position = next((i for i, pk in enumerate(ranked, start=1)
                         if pk in info and _unit_matches(unit, info[pk])), None)
        if position is None:
            return None
        positions.append(position)
    return max(positions) if positions else None


def unit_hits(expected, candidates, selected, ranked, paths, delivered=None):
    """Dónde quedaron las unidades esperadas `expected` (pares norma y clave) de un caso.
    Con varias unidades esperadas, cada medida exige todas:

    - `found`: por cada camino de `paths` y en la unión (`union`), si todas estaban entre
      los candidatos que entraron por ahí. Los candidatos son pasajes de unidades base:
      un inciso esperado vale con el artículo que lo contiene, como en la respuesta
      correcta.
    - `selected`: si todas estaban entre `selected`.
    - `position`: la posición, desde 1, de la peor ubicada en `ranked` (el orden del
      reranker; sin reranker, el de la unión), o `None` si alguna no estaba.
    - `delivered` (solo si se pasa): si todas estaban entre las unidades enviadas al
      modelo, después de los cupos y del espacio.

    `candidates` son `{"unit", "path"}`, como los registra la consulta."""
    info = _unit_info([c["unit"] for c in candidates] + list(selected) + list(ranked)
                      + list(delivered or []))
    found = {path: _all_found(expected, [c["unit"] for c in candidates if path in c["path"]],
                              info)
             for path in paths}
    found[UNION] = _all_found(expected, [c["unit"] for c in candidates], info)
    hits = {"found": found, "selected": _all_found(expected, selected, info),
            "position": _worst_position(expected, ranked, info)}
    if delivered is not None:
        hits["delivered"] = _all_found(expected, delivered, info)
    return hits


def _anomalies_of(anomalies, kind):
    """Cuántas anomalías son del tipo `kind`. `anomalies` mezcla fallas de formato o de
    cita con las de los servicios (`service_error`): se filtra por `type` (aviso de
    T-019)."""
    return sum(1 for a in anomalies or [] if isinstance(a, dict) and a.get("type") == kind)


def case_diagnostics(case, query):
    """Diagnóstico de un caso corrido, leído del registro de su consulta (P6): puntaje
    más alto, motivo de la abstención, si la frenó el umbral, tiempo de la recuperación,
    fallas de formato y de cita y, si el caso tiene respuesta, `unit_hits`."""
    selected = query.selected or {}
    reason = (selected.get("abstention") or {}).get("reason")
    diagnostics = {
        "max_score": query.max_score,
        "abstention_reason": reason,
        "stopped_by_threshold": reason == Reason.BELOW_THRESHOLD.value,
        "retrieval_seconds": (query.timings or {}).get("retrieval"),
        "format_failures": _anomalies_of(query.anomalies, FORMAT_FAILURE),
        "citation_failures": _anomalies_of(query.anomalies, CITATION_FAILURE),
        "found": None,
        "selected": None,
        "position": None,
    }
    if case.has_answer:
        paths = (query.parameters or {}).get("paths") or list(retrieval.ALL_PATHS)
        ranked = [u["unit"] for u in (selected.get("retrieval") or {}).get("units") or []]
        sent = [u["unit"] for u in selected.get("sent") or []]
        diagnostics.update(unit_hits(case.units, query.candidates or [], sent, ranked,
                                     paths))
    return diagnostics


def _count(values):
    values = [v for v in values if v is not None]
    ok = sum(1 for v in values if v)
    return {"ok": ok, "total": len(values), "rate": ok / len(values) if values else None}


def _spread(values):
    values = [v for v in values if v is not None]
    return {"median": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def retrieval_measures(items, paths=retrieval.ALL_PATHS, thresholded=True):
    """Medidas de recuperación de la corrida (ADR-0003). `items` son `(id, con
    respuesta, diagnóstico)`; un diagnóstico vacío (caso no corrido o no buscado) no
    cuenta. Con `thresholded` falso (sin reranker) no hay frenadas por el umbral."""
    items = [(case_id, has_answer, d) for case_id, has_answer, d in items if d]
    answered = [(case_id, d) for case_id, has_answer, d in items if has_answer]
    unanswered = [d for _, has_answer, d in items if not has_answer]
    return {
        "found": {key: _count(d["found"].get(key) for _, d in answered)
                  for key in [*paths, UNION]},
        "selected": _count(d["selected"] for _, d in answered),
        "not_selected": [case_id for case_id, d in answered if not d["selected"]],
        "delivered": _count(d.get("delivered") for _, d in answered),
        "position": _spread(d["position"] for _, d in answered),
        "answered_stopped": (_count(d["stopped_by_threshold"] for _, d in answered)
                             if thresholded else None),
        "answered_stopped_ids": ([case_id for case_id, d in answered
                                  if d["stopped_by_threshold"]] if thresholded else []),
        "unanswered_stopped": (_count(d["stopped_by_threshold"] for d in unanswered)
                               if thresholded else None),
        "retrieval_time": _spread(d["retrieval_seconds"] for _, _, d in items),
    }


def measures_by_regime(lines):
    """Respuesta correcta y abstención separadas por el régimen del caso (`regimen`),
    como diagnóstico (plan, "Evals"). La clave vacía es la de los casos sin régimen."""
    groups = {}
    for line in lines:
        groups.setdefault(line["expected_regime"], []).append(line)
    measures = {}
    for regime in sorted(groups, key=lambda name: (name == "", name)):
        group = groups[regime]
        answered = [line for line in group if line["has_answer"]]
        unanswerable = [line for line in group if not line["has_answer"]]
        measures[regime] = {
            "correct_answer": _ratio(sum(1 for line in answered
                                         if line["measures"]["correct"]),
                                     len(answered), CORRECT_THRESHOLD),
            "abstention": _ratio(sum(1 for line in unanswerable
                                     if line["measures"]["abstained"]),
                                 len(unanswerable), ABSTENTION_THRESHOLD),
        }
    return measures


def output_failures(lines):
    """Casos cuya salida tuvo una falla de formato o de cita (ADR-0002). Se espera
    ninguno."""
    with_diagnostics = [line for line in lines if line.get("diagnostics")]
    return {
        "format": [line["id"] for line in with_diagnostics
                   if line["diagnostics"]["format_failures"]],
        "citation": [line["id"] for line in with_diagnostics
                     if line["diagnostics"]["citation_failures"]],
    }


def special_cases(lines):
    """Los casos de REQ-018 (etiqueta "dos categorías") y de REQ-019 (`difieren`), con
    si pasan, para informarlos aparte."""
    return {
        "REQ-018": [{"id": line["id"], "passed": line["passed"]} for line in lines
                    if TWO_CATEGORIES in {normalize(label) for label in line["labels"]}],
        "REQ-019": [{"id": line["id"], "passed": line["passed"]} for line in lines
                    if line["differ"]],
    }


# --- Calibración del umbral (ADR-0014, punto 2; plan, "Abstención") ---------------------


def _floor(value):
    factor = 10 ** CALIBRATION_DECIMALS
    return math.floor(round(value * factor, 6)) / factor


def logit(score):
    """El puntaje en la escala anterior a la sigmoide, `ln(p / (1 − p))`, con el puntaje
    acotado entre 10⁻⁹ y 1 − 10⁻⁹ para que un 0 o un 1 redondeados no den infinito."""
    p = min(max(score, SCORE_BOUND), 1 - SCORE_BOUND)
    return math.log(p / (1 - p))


def sigmoid(value):
    """La escala de 0 a 1 del valor `value` de la escala anterior a la sigmoide."""
    return 1 / (1 + math.exp(-value))


def _group(entry):
    """`answered`, `foreign`, `near` u `other` (sin respuesta sin ninguna de las dos
    etiquetas). Una pregunta con las dos etiquetas cuenta como ajena."""
    if entry["has_answer"]:
        return "answered"
    labels = {normalize(label) for label in entry.get("labels") or []}
    if FOREIGN in labels:
        return "foreign"
    if NEAR in labels:
        return "near"
    return "other"


def _point(entry):
    return {"id": entry["id"], "score": entry["max_score"],
            "logit": logit(entry["max_score"])}


def calibrate(entries, current):
    """Calibración del umbral con la regla del hueco (ADR-0014, punto 2; plan,
    "Abstención", "Calibración del umbral"). Ver el módulo.

    `entries` son `{"id", "has_answer", "max_score", "labels", "lot"}` (sin `lot`, de
    ajuste); `current` es el umbral con que se corrió. Entran solo las del lote de
    ajuste. `A` es la ajena a la normativa con el puntaje más alto y `B` la pregunta con
    respuesta con el puntaje más bajo; las de tema cercano no entran. Hay hueco si
    `logit(B) > logit(A)`; el umbral propuesto es `sigmoid` del punto medio, redondeado
    hacia abajo a tres decimales, y el margen, la mitad del hueco. Devuelve:

    - `proposed`: el umbral propuesto, o `None` (sin hueco o sin datos, con `reason`);
      `provisional`: siempre verdadero; `gap`: si hay hueco (`None` si la regla no se
      pudo aplicar).
    - `high_foreign` (`A`) y `low_answered` (`B`): `{"id", "score", "logit"}` o `None`;
      `midpoint`: el punto medio en la escala anterior a la sigmoide.
    - `margin`, `min_margin` y `meets_margin` (`None` sin hueco).
    - Sin hueco: `foreign_at_or_above_low`, las ajenas con puntaje mayor o igual que
      `B`, de mayor a menor; `answered_at_or_below_high`, las preguntas con respuesta
      con puntaje menor o igual que `A`, de menor a mayor.
    - `answered`: cuántas preguntas con respuesta tienen puntaje; `blocked`: las que
      frena el propuesto; `unanswered`: cuántas sin respuesta tienen puntaje;
      `unanswered_stopped`: las que frena el propuesto; `near_above`: las de tema
      cercano que quedan por encima del propuesto (las tiene que frenar el modelo).
    - `current`: el umbral actual, las preguntas con respuesta y las sin respuesta que
      frena.
    - `without_score`: preguntas con respuesta que no llegaron a puntuarse; ningún
      umbral las cambia.
    - `scores` y `table`: los puntajes del lote de ajuste (`table`, en el orden de
      `entries`, con el grupo y el valor en la escala anterior a la sigmoide).
    """
    adjustment = [e for e in entries if (e.get("lot") or ADJUSTMENT) == ADJUSTMENT]
    scored = [e for e in adjustment if e["max_score"] is not None]
    answered = [e for e in scored if _group(e) == "answered"]
    foreign = [e for e in scored if _group(e) == "foreign"]
    near = [e for e in scored if _group(e) == "near"]
    unanswered = [e for e in scored if not e["has_answer"]]

    def below(rows, threshold):
        if threshold is None:
            return []
        return [e["id"] for e in rows if e["max_score"] < threshold]

    high = _point(max(foreign, key=lambda e: e["max_score"])) if foreign else None
    low = _point(min(answered, key=lambda e: e["max_score"])) if answered else None
    result = {
        "proposed": None, "provisional": True, "reason": None, "gap": None,
        "high_foreign": high, "low_answered": low, "midpoint": None,
        "margin": None, "min_margin": CALIBRATION_MIN_MARGIN, "meets_margin": None,
        "foreign_at_or_above_low": [], "answered_at_or_below_high": [],
    }
    if high is None or low is None:
        missing = []
        if low is None:
            missing.append("preguntas con respuesta")
        if high is None:
            missing.append("preguntas ajenas a la normativa")
        result["reason"] = ("no hay " + " ni ".join(missing)
                            + " con puntaje en el lote de ajuste")
    elif low["logit"] > high["logit"]:
        midpoint = (high["logit"] + low["logit"]) / 2
        margin = (low["logit"] - high["logit"]) / 2
        result.update(gap=True, midpoint=midpoint, margin=margin,
                      proposed=_floor(sigmoid(midpoint)),
                      meets_margin=margin >= CALIBRATION_MIN_MARGIN)
    else:
        result.update(
            gap=False,
            foreign_at_or_above_low=[
                e["id"] for e in sorted(foreign, key=lambda e: -e["max_score"])
                if e["max_score"] >= low["score"]],
            answered_at_or_below_high=[
                e["id"] for e in sorted(answered, key=lambda e: e["max_score"])
                if e["max_score"] <= high["score"]],
        )

    proposed = result["proposed"]
    result.update(
        answered=len(answered),
        blocked=below(answered, proposed),
        unanswered=len(unanswered),
        unanswered_stopped=below(unanswered, proposed),
        near_above=([e["id"] for e in near if e["max_score"] >= proposed]
                    if proposed is not None else []),
        current={"threshold": current, "blocked": below(answered, current),
                 "unanswered_stopped": below(unanswered, current)},
        without_score=[e["id"] for e in adjustment
                       if e["has_answer"] and e["max_score"] is None],
        scores={e["id"]: e["max_score"] for e in scored},
        table=[{"id": e["id"], "group": _group(e), "score": e["max_score"],
                "logit": logit(e["max_score"])} for e in scored],
    )
    return result


def calibration_entries(lines):
    return [{"id": line["id"], "has_answer": line["has_answer"],
             "max_score": (line["diagnostics"] or {}).get("max_score")
             if line.get("diagnostics") else None,
             "labels": line.get("labels") or [],
             "lot": line_lot(line)}
            for line in lines]


# --- Comparación quitando piezas (ADR-0003) ---------------------------------------------


def _ablation_entry(case, name, paths, rerank, prompt_tokens, clock):
    """Una configuración de la comparación para un caso: recupera con `paths` y
    `rerank`, selecciona con `select_units` y mide. Devuelve la entrada y los tokens de
    instrucciones y pregunta, contados la primera vez como en la consulta."""
    entry = {"name": name, "paths": list(paths), "rerank": rerank, "skipped": None,
             "error": None}
    since = clock()
    try:
        found = retrieval.retrieve(case.question, case.reference_date, paths=paths,
                                   rerank=rerank)
        seconds = clock() - since
        if prompt_tokens is None:
            prompt_tokens = (generation.count_tokens(answering.load_instructions())
                             + generation.count_tokens(
                                 answering.request_head(case.question,
                                                        case.reference_date)))
        selection = retrieval.select_units(found, prompt_tokens)
    except AIServiceError as error:
        entry["error"] = error.reason
        return entry, prompt_tokens
    candidates = [c.as_record() for c in found.candidates]
    entry.update(
        max_score=found.max_score,
        stopped_by_threshold=(bool(found.candidates) and not found.selected) if rerank
        else None,
        retrieval_seconds=round(seconds, 3),
        candidates=candidates,
        units=[u.as_record() for u in found.units],
        selected_units=[u.unit_id for u in found.selected],
        sent=list(selection.unit_ids),
        found=None, selected=None, position=None, delivered=None,
    )
    if case.has_answer:
        # "Entre las seleccionadas" es lo que selecciona la recuperación (sin reranker,
        # toda la unión: coincide con "entre los candidatos", aclaración de T-032); "entre
        # las enviadas al modelo" es lo que deja `select_units` con cupos y espacio.
        entry.update(unit_hits(case.units, candidates, entry["selected_units"],
                               [u.unit_id for u in found.units], paths,
                               delivered=selection.unit_ids))
    return entry, prompt_tokens


def run_ablation(cases, clock=time.monotonic):
    """La comparación quitando piezas: `{id del caso: [entrada por configuración]}`, en
    el orden de `ABLATION_CONFIGS`. Ver el módulo."""
    ablated = {}
    for case in cases:
        if not services.applicable_regimes(case.reference_date):
            ablated[case.id] = [
                {"name": name, "paths": list(paths), "rerank": rerank,
                 "skipped": Reason.NO_REGIME_AT_DATE.value, "error": None}
                for name, paths, rerank in ABLATION_CONFIGS]
            continue
        entries, prompt_tokens = [], None
        for name, paths, rerank in ABLATION_CONFIGS:
            entry, prompt_tokens = _ablation_entry(case, name, paths, rerank,
                                                   prompt_tokens, clock)
            entries.append(entry)
        ablated[case.id] = entries
    return ablated


def ablation_measures(cases, ablated):
    """Medidas de recuperación de cada configuración, sobre los casos que se buscaron."""
    measures = []
    for index, (name, paths, rerank) in enumerate(ABLATION_CONFIGS):
        items = []
        errors = []
        for case in cases:
            entry = ablated[case.id][index]
            if entry["error"]:
                errors.append(case.id)
            usable = not entry["skipped"] and not entry["error"]
            items.append((case.id, case.has_answer, entry if usable else None))
        measures.append({"name": name, "paths": list(paths), "rerank": rerank,
                         "threshold": settings.RERANK_THRESHOLD if rerank else None,
                         "errors": errors,
                         **retrieval_measures(items, paths, thresholded=rerank)})
    return measures


# --- Comparación con la corrida anterior -------------------------------------------------


def find_previous_run(runs_dir, current_name):
    """La carpeta de la corrida anterior a `current_name` en `runs_dir`: la de nombre
    más alto entre las anteriores (el nombre empieza con la fecha y la hora) que tiene
    `resultados.jsonl`. `None` si no hay."""
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        return None
    names = sorted(p.name for p in runs_dir.iterdir()
                   if p.is_dir() and p.name < current_name
                   and (p / "resultados.jsonl").is_file())
    return runs_dir / names[-1] if names else None


def load_run(folder):
    """Parámetros y renglones de los casos medidos de una corrida guardada."""
    folder = Path(folder)
    rows = [json.loads(row) for row in
            (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()
            if row.strip()]
    parameters_file = folder / "parametros.json"
    parameters = (json.loads(parameters_file.read_text(encoding="utf-8"))
                  if parameters_file.is_file() else {})
    return {"folder": folder, "parameters": parameters,
            "lines": [row for row in rows if "measures" in row]}


_MODEL_KEYS = ("generation", "embeddings", "reranker")


def _conditions(parameters):
    search = dict(parameters.get("search") or {})
    models = {key: search.pop(key, None) for key in _MODEL_KEYS}
    return {
        "commit": parameters.get("commit"),
        "models": models,
        "prompt_version": parameters.get("prompt_version"),
        "corpus_version": parameters.get("corpus_version"),
        "search": search,
    }


def _cited_keys(line):
    return [(u["norm"], u["key"]) for u in line.get("cited_units") or []]


def _result_signature(line, with_text):
    keys = {u["unit"]: (u["norm"], u["key"]) for u in line.get("cited_units") or []}
    signature = [line["status"], line["reason"], _cited_keys(line)]
    if with_text:
        signature.append([(s.get("text"), bool(s.get("regimes_differ")),
                           [keys.get(u) for u in s.get("citations") or []])
                          for s in line.get("statements") or []])
    return json.dumps(signature, ensure_ascii=False, cls=DjangoJSONEncoder)


def compare_runs(previous, lines, parameters):
    """Comparación con la corrida anterior (plan, "Evals", y ADR-0002):

    - `measures`: cada proporción (cita literal, respuesta correcta y abstención) lote
      por lote (`lot`), cada lote con el mismo lote de la anterior; un renglón guardado
      sin lote es del lote de ajuste (`line_lot`). Y el tiempo de toda la corrida
      (`lot` `None`; la mediana y el máximo). En la anterior y en esta (`rate`);
    - `regressions` y `improvements`: casos que pasaban y ahora fallan, y al revés;
    - `changed`: casos que cambiaron de estado, de motivo o de citas sin cambiar si
      pasan; `only_previous` y `only_current`: casos medidos en una sola;
    - `equality`: entre los casos corridos en las dos, cuántos dan el mismo resultado
      (`same`: estado, motivo, citas y texto de las afirmaciones) y cuántos el mismo
      estado, el mismo motivo y las mismas citas (`same_status_reason_and_citations`);
    - `drops`: las medidas que bajaron, `{"name", "lot"}`: cada una requiere aprobación
      del responsable (P7). El tiempo cuenta como baja solo si el máximo supera 30 s
      (`response_time`) o si la mediana sube más de un 25 % (`response_time_median`);
    - `conditions_changed`: qué cambió entre las dos (commit, modelos, instrucciones,
      normativa o parámetros de búsqueda). Vacío: es una repetición."""
    old_lines = previous["lines"]
    old = {line["id"]: line for line in old_lines}
    new = {line["id"]: line for line in lines}
    both = [case_id for case_id in new if case_id in old]

    rows = []
    for lot in LOTS:
        old_lot = measure(lot_lines(old_lines, lot))
        new_lot = measure(lot_lines(lines, lot))
        for name in PROPORTIONS:
            before, now = old_lot[name]["rate"], new_lot[name]["rate"]
            rows.append({"name": name, "lot": lot, "previous": before, "current": now,
                         "drop": before is not None and now is not None and now < before})
    old_measures, new_measures = measure(old_lines), measure(lines)
    # Tiempo (decisión del Coordinador): es baja solo si el máximo supera el límite de
    # 30 s o si la mediana sube más de un 25 % respecto de la anterior. Cualquier otra
    # variación se muestra sin marcarla.
    median_before = old_measures["response_time"]["median"]
    median_now = new_measures["response_time"]["median"]
    max_now = new_measures["response_time"]["max"]
    rows.append({"name": TIME_MEDIAN, "lot": None, "previous": median_before,
                 "current": median_now,
                 "drop": (median_before is not None and median_now is not None
                          and median_before > 0
                          and median_now > median_before * (1 + MEDIAN_RISE_LIMIT))})
    rows.append({"name": TIME_MAX, "lot": None,
                 "previous": old_measures["response_time"]["max"],
                 "current": max_now,
                 "drop": max_now is not None and max_now > MAX_SECONDS})

    regressions = [c for c in both if old[c]["passed"] and not new[c]["passed"]]
    improvements = [c for c in both if not old[c]["passed"] and new[c]["passed"]]
    changed = [c for c in both if c not in regressions and c not in improvements
               and _result_signature(old[c], False) != _result_signature(new[c], False)]

    ran = [c for c in both if old[c].get("ran") and new[c].get("ran")]
    current = json.loads(_dumps(parameters))
    old_conditions = _conditions(previous["parameters"])
    new_conditions = _conditions(current)
    return {
        "previous": previous["folder"].name,
        "measures": rows,
        "drops": [{"name": row["name"], "lot": row["lot"]} for row in rows if row["drop"]],
        "lots": {lot: {"previous": len(lot_lines(old_lines, lot)),
                       "current": len(lot_lines(lines, lot))} for lot in LOTS},
        "regressions": regressions,
        "improvements": improvements,
        "changed": changed,
        "only_previous": [c for c in old if c not in new],
        "only_current": [c for c in new if c not in old],
        "equality": {
            "same": sum(1 for c in ran if _result_signature(old[c], True)
                        == _result_signature(new[c], True)),
            "same_status_reason_and_citations": sum(1 for c in ran
                                             if _result_signature(old[c], False)
                                             == _result_signature(new[c], False)),
            "total": len(ran),
        },
        "conditions_changed": [key for key in new_conditions
                               if old_conditions.get(key) != new_conditions[key]],
    }


def _comparison(previous, lines, parameters):
    """`compare_runs` con la corrida anterior, si hay. Si no se puede leer, se informa y
    la corrida actual se guarda igual."""
    if previous is None:
        return None
    try:
        loaded = load_run(previous)
        return compare_runs(loaded, lines, parameters)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"previous": previous.name,
                "error": f"no se pudo leer ({error.__class__.__name__}: {error})"}


@dataclass
class RunReport:
    """Lo que dejó una corrida.

    - `folder`: la carpeta de la corrida.
    - `results`: un renglón por caso medido, como en `resultados.jsonl`: los corridos
      y los que la consulta rechazó (`status` `refused`, `ran` falso).
    - `skipped`: los casos que no se corrieron ni se miden (mal formados o sin visto
      bueno), con su motivo.
    - `measures`: las cuatro medidas exigidas (`required_measures`): cita literal y
      tiempo de toda la corrida; respuesta correcta y abstención del lote de aceptación.
    - `adjustment_measures`: las medidas del lote de ajuste (`measure`), aparte, como
      diagnóstico.
    - `pairs`: los pares de REQ-020 (`check_pairs`).
    - `notices`: la comprobación de REQ-021: `ok`, `total` y los casos `failed`.
    - `parameters`: lo que se guardó en `parametros.json`.

    Diagnóstico (T-042), con el lote de ajuste salvo donde se dice (T-060):

    - `by_regime`: respuesta correcta y abstención por régimen (`measures_by_regime`).
    - `retrieval`: medidas de recuperación (`retrieval_measures`).
    - `output_failures`: casos con falla de formato o de cita (`output_failures`), de
      toda la corrida.
    - `special`: los casos de REQ-018 y REQ-019 (`special_cases`), de toda la corrida.
    - `calibration`: la calibración del umbral (`calibrate`).
    - `ablation`: medidas de cada configuración de la comparación quitando piezas
      (`ablation_measures`), o `None` si no se pidió.
    - `comparison`: la comparación con la corrida anterior (`compare_runs`), o `None` si
      no hay una.
    """

    folder: Path
    results: list
    skipped: list
    measures: dict
    pairs: list
    notices: dict
    parameters: dict
    adjustment_measures: dict = None
    by_regime: dict = None
    retrieval: dict = None
    output_failures: dict = None
    special: dict = None
    calibration: dict = None
    ablation: list = None
    comparison: dict = None

    def failed_ids(self):
        """Casos medidos que fallaron alguna medida o comprobación, en orden."""
        return [line["id"] for line in self.results if _failures(line)]

    def ran(self):
        """Renglones de los casos que se corrieron de verdad."""
        return [line for line in self.results if line["ran"]]


def _failures(line):
    measures = line["measures"]
    reasons = []
    if line["status"] == REFUSED:
        reasons.append(f"consulta rechazada ({line['reason']}), cuenta como "
                       + ("incorrecta" if line["has_answer"] else "no abstenida"))
    elif line["has_answer"] and not measures["correct"]:
        failed = [name for name, ok in measures["checks"].items() if not ok]
        texts = [_CHECK_TEXT[n] if n != "key_data" or not measures["missing_key_data"]
                 else f"{_CHECK_TEXT[n]}: {key_data_text(measures['missing_key_data'])}"
                 for n in failed]
        reasons.append("respuesta incorrecta (" + ", ".join(texts) + ")")
    elif not line["has_answer"] and not measures["abstained"]:
        reasons.append("no se abstuvo" if line["status"] != Status.ERROR
                       else "falla técnica en lugar de abstención")
    if measures["literal_citations"] != measures["citations"]:
        reasons.append("cita que no es literal")
    if not measures["notice_ok"]:
        reasons.append("aviso de modificatorias distinto del esperado")
    if line["time_seconds"] is not None and line["time_seconds"] > MAX_SECONDS:
        reasons.append("superó los 30 segundos")
    return reasons


_CHECK_TEXT = {
    "status": "no hubo respuesta con fundamento",
    "regime": "régimen aplicado distinto",
    "units": "no cita la unidad esperada",
    "key_data": "faltan datos clave",
    "regimes_differ": "sin la marca de regímenes que difieren con sus dos citas",
}


# --- Corrida ---------------------------------------------------------------------------


def detect_commit():
    """Commit del código, abreviado, si hay un repositorio de git a mano; si no,
    `sin-commit`. Dentro del contenedor no hay `.git`: conviene pasar `--commit`."""
    try:
        done = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=settings.BASE_DIR, capture_output=True, text=True,
                              timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return NO_COMMIT
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else NO_COMMIT


def _slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-") or "x"


def run_folder_name(started_at, commit, model):
    """`AAAA-MM-DDTHHMMSS_<commit>_<modelo>`, con la hora de Buenos Aires."""
    local = timezone.localtime(started_at)
    return f"{local:%Y-%m-%dT%H%M%S}_{_slug(commit)}_{_slug(model)}"


def run_parameters(started_at, commit, cases_dir):
    """Lo que se guarda en `parametros.json` al empezar la corrida (plan, "Dónde se
    guarda")."""
    return {
        "started_at": timezone.localtime(started_at).isoformat(),
        "commit": commit,
        "cases_dir": str(cases_dir),
        "corpus_version": current_corpus_version(),
        "prompt_version": None,  # se completa con las de las consultas
        "search": services.parameters(),
    }


def prompt_versions(lines):
    """Versiones de las instrucciones que usaron las consultas, en orden de aparición:
    la única si fue una sola, la lista si hubo varias, o `None` si ninguna consulta
    llamó al modelo."""
    versions = list(dict.fromkeys(line["prompt_version"] for line in lines
                                  if line.get("prompt_version")))
    if not versions:
        return None
    return versions[0] if len(versions) == 1 else versions


def _refused_result(error):
    return {"status": REFUSED, "reason": str(error), "regime": [], "notices": [],
            "statements": [], "units": {}}


def _case_line(case, result, query=None, elapsed=None):
    """Renglón de un caso medido. Sin `query`, la consulta se rechazó."""
    cited = cited_units(result)
    line = {
        "id": case.id,
        "file": case.file,
        "ran": query is not None,
        "question": case.question,
        "reference_date": case.reference_date.isoformat(),
        "expected_regime": case.regime,
        "has_answer": case.has_answer,
        "pair": case.pair,
        "expected_notice": case.notice,
        "labels": list(case.labels),
        "differ": case.differ,
        "lot": case.lot,
        "query_id": query.pk if query else None,
        "corpus_version": query.corpus_version if query else None,
        "prompt_version": query.prompt_version if query else "",
        "status": result["status"],
        "reason": result["reason"],
        "regime": [r["name"] for r in result.get("regime") or []],
        "notices": result.get("notices") or [],
        "statements": result.get("statements") or [],
        "cited_units": cited,
        "measures": grade(case, result, cited),
        "time_seconds": round(elapsed, 3) if query else None,
        "timings": query.timings if query else {},
        "diagnostics": case_diagnostics(case, query) if query else None,
    }
    line["passed"] = _passed(line)
    return line


def _skipped_line(skipped):
    return {"id": skipped.case_id, "file": skipped.file, "ran": False,
            "skipped": skipped.kind, "reason": skipped.reason}


def run(user, cases_dir, runs_dir, *, commit=None, clock=time.monotonic, ablation=False):
    """Corre los casos de `cases_dir` y guarda la corrida en una carpeta nueva dentro de
    `runs_dir`. Ver el módulo. Lanza `RoleRejected` sin rol, antes de leer nada; el
    rechazo queda registrado con el canal `eval` y esta función como operación (T-038).

    - `commit`: el commit del código; si no se indica, `detect_commit()`.
    - `clock`: reloj en segundos para medir cada consulta y cada recuperación de la
      comparación quitando piezas (las pruebas lo reemplazan).
    - `ablation`: si es verdadero, corre además la comparación quitando piezas.
    """
    require_role(user, Role.READ, channel=Channel.EVAL)
    cases_dir = Path(cases_dir)
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de casos {cases_dir}.")
    cases, skipped = load_cases(cases_dir)
    started_at = timezone.now()
    commit = commit or detect_commit()
    parameters = run_parameters(started_at, commit, cases_dir)

    lines = []
    for case in cases:
        since = clock()
        try:
            query = services.ask(user, case.question, case.reference_date,
                                 channel=Channel.EVAL)
        except services.QueryRefused as error:
            clock()
            lines.append(_case_line(case, _refused_result(error)))
            continue
        elapsed = clock() - since
        lines.append(_case_line(case, query.result, query, elapsed))

    # La comparación quitando piezas es diagnóstico: solo con el lote de ajuste.
    adjustment_cases = [case for case in cases if case.lot == ADJUSTMENT]
    ablated = run_ablation(adjustment_cases, clock) if ablation else None
    for line in lines:
        line["ablation"] = ablated.get(line["id"]) if ablated else None

    parameters["prompt_version"] = prompt_versions(lines)
    parameters["finished_at"] = timezone.localtime(timezone.now()).isoformat()
    folder = Path(runs_dir) / run_folder_name(started_at, commit, settings.GENERATION_MODEL)
    previous = find_previous_run(runs_dir, folder.name)
    report = _report(
        folder, lines, skipped, parameters, parameters["search"]["rerank_threshold"],
        ablation=(ablation_measures(adjustment_cases, ablated)
                  if ablated is not None else None),
        comparison=_comparison(previous, lines, parameters),
    )
    _write(report)
    return report


def _report(folder, lines, skipped, parameters, threshold, *, ablation, comparison):
    """El `RunReport` de una corrida o de una recalificación, con cada parte medida
    sobre los casos que le corresponden (plan, "Qué usa cada lote"): las medidas
    exigidas según `required_measures`; el lote de ajuste aparte; la recuperación, las
    medidas por régimen y la calibración solo con el lote de ajuste; los pares, el aviso,
    las salidas con falla y los casos de REQ-018 y REQ-019 con toda la corrida."""
    adjustment = lot_lines(lines, ADJUSTMENT)
    notice_lines = [line for line in lines if not line["measures"]["notice_ok"]]
    return RunReport(
        folder=folder,
        results=lines,
        skipped=skipped,
        measures=required_measures(lines),
        adjustment_measures=measure(adjustment),
        pairs=check_pairs(lines),
        notices={"ok": len(lines) - len(notice_lines), "total": len(lines),
                 "failed": [line["id"] for line in notice_lines]},
        parameters=parameters,
        by_regime=measures_by_regime(adjustment),
        retrieval=retrieval_measures(
            [(line["id"], line["has_answer"], line.get("diagnostics"))
             for line in adjustment]),
        output_failures=output_failures(lines),
        special=special_cases(lines),
        calibration=calibrate(calibration_entries(lines), threshold),
        ablation=ablation,
        comparison=comparison,
    )


# --- Recalificar una corrida guardada (T-058; plan, "Recalificar una corrida guardada") --


def _rescore_mismatch(case, row):
    """Por qué el renglón guardado no corresponde al caso vigente, o `None` si
    corresponde."""
    problems = []
    if (row.get("question") or "").strip() != case.question:
        problems.append("la pregunta")
    if row.get("reference_date") != case.reference_date.isoformat():
        problems.append("la fecha de autorización")
    if row.get("has_answer") is not case.has_answer:
        problems.append("si tiene respuesta")
    if not problems:
        return None
    return "no recalificable: no coincide con la corrida en " + " ni en ".join(problems)


def _rescored_line(case, row):
    """El renglón guardado, medido otra vez con el caso vigente: las respuestas, las
    citas con su comprobación de cita literal, los tiempos y el diagnóstico quedan como
    se guardaron."""
    result = {"status": row["status"], "reason": row.get("reason"),
              "regime": [{"name": name} for name in row.get("regime") or []],
              "notices": row.get("notices") or [],
              "statements": row.get("statements") or []}
    line = dict(row)
    line.update(
        file=case.file,
        expected_regime=case.regime,
        pair=case.pair,
        expected_notice=case.notice,
        labels=list(case.labels),
        differ=case.differ,
        lot=case.lot,
        measures=grade(case, result, row.get("cited_units") or []),
    )
    line["passed"] = _passed(line)
    return line


def rescore(user, source, cases_dir, runs_dir, *, commit=None):
    """Vuelve a medir la corrida guardada en `source` con los casos de `cases_dir` y el
    corrector vigente, y guarda una carpeta nueva en `runs_dir` (plan, "Recalificar una
    corrida guardada"). No consulta ni llama a ningún servicio de IA: no crea consultas
    ni hechos del registro de auditoría. Lanza `RoleRejected` sin rol, antes de leer
    nada, como `run`.

    - Mide otra vez solo los casos cuya `pregunta`, `fecha_autorizacion` y presencia de
      respuesta coinciden con las del renglón guardado; los demás quedan como no
      recalificables (`NOT_RESCORABLE`) y fuera de la medida.
    - El lote de cada caso es el del caso vigente (T-060), aunque el renglón guardado no
      lo traiga.
    - La carpeta nueva lleva la fecha y el commit del momento, el modelo de la corrida
      original y termina en `_recalificada`. `parametros.json` copia los de la original
      y suma `rescore` (origen, aviso, commit, casos y fecha); `resumen.md` dice que es
      una recalificación y se compara con la original, que no se modifica.
    - `commit`: el commit del código; si no se indica, `detect_commit()`."""
    require_role(user, Role.READ, channel=Channel.EVAL)
    source = Path(source)
    if not (source / "resultados.jsonl").is_file():
        raise FileNotFoundError(f"No hay una corrida guardada en {source}: falta "
                                "resultados.jsonl.")
    cases_dir = Path(cases_dir)
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de casos {cases_dir}.")
    original = load_run(source)
    rows = {row["id"]: row for row in original["lines"]}
    cases, skipped = load_cases(cases_dir)
    started_at = timezone.now()
    commit = commit or detect_commit()

    lines = []
    for case in cases:
        row = rows.get(case.id)
        reason = (_rescore_mismatch(case, row) if row is not None
                  else "no recalificable: el caso no está en la corrida")
        if reason:
            skipped.append(Skipped(case.file, case.id, NOT_RESCORABLE, reason))
            continue
        lines.append(_rescored_line(case, row))

    parameters = json.loads(_dumps(original["parameters"]))
    parameters["rescore"] = {
        "source": source.name,
        "note": RESCORE_NOTE,
        "commit": commit,
        "cases_dir": str(cases_dir),
        "rescored_at": timezone.localtime(started_at).isoformat(),
    }
    search = parameters.get("search") or {}
    model = (search.get("generation") or {}).get("model") or "sin-modelo"
    folder = Path(runs_dir) / (run_folder_name(started_at, commit, model) + RESCORED_SUFFIX)
    comparison = compare_runs(original, lines, parameters)
    comparison["rescore"] = True
    report = _report(folder, lines, skipped, parameters, search.get("rerank_threshold"),
                     ablation=None, comparison=comparison)
    _write(report)
    return report


# --- Archivos de la corrida ------------------------------------------------------------


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


def _write(report):
    report.folder.mkdir(parents=True, exist_ok=False)
    (report.folder / "parametros.json").write_text(
        _dumps(report.parameters, indent=2) + "\n", encoding="utf-8")
    rows = report.results + [_skipped_line(s) for s in report.skipped]
    rows.sort(key=lambda row: row["file"])
    (report.folder / "resultados.jsonl").write_text(
        "".join(_dumps(row) + "\n" for row in rows), encoding="utf-8")
    (report.folder / "resumen.md").write_text(summary_markdown(report), encoding="utf-8")


def _percent(value):
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def _seconds(value):
    return "—" if value is None else f"{value:.2f} s".replace(".", ",")


def _meets(value):
    return {True: "sí", False: "no", None: "sin casos"}[value]


def counts(report):
    """Cantidades de casos leídos, corridos, rechazados por la consulta (se miden igual)
    y no corridos por motivo."""
    by_kind = {kind: sum(1 for s in report.skipped if s.kind == kind)
               for kind in (NOT_APPROVED, MALFORMED, NOT_RESCORABLE)}
    ran = len(report.ran())
    refused = len(report.results) - ran
    return {"read": len(report.results) + len(report.skipped), "ran": ran,
            REFUSED: refused, **by_kind}


def counts_line(report):
    """Una línea en lenguaje llano con las cantidades de casos."""
    c = counts(report)
    line = (f"Casos leídos: {c['read']} · corridos: {c['ran']} · "
            f"{c[NOT_APPROVED]} sin visto bueno · {c[MALFORMED]} mal formados")
    if c[REFUSED]:
        line += (f" · {c[REFUSED]} rechazados por la consulta (cuentan como "
                 "incorrectos o no abstenidos)")
    if c[NOT_RESCORABLE]:
        line += f" · {c[NOT_RESCORABLE]} no recalificables (quedan fuera de la medida)"
    return line


NOTHING_RAN = ("No se corrió ningún caso: ninguno está bien formado y con visto bueno "
               "de la Comisión. Las medidas quedan sin valor.")


def _bound(value):
    """Un extremo del intervalo: con un decimal y coma; 0 y 100 sin decimales."""
    text = f"{value * 100:.1f}"
    if text in ("0.0", "100.0"):
        return f"{text[:-2]} %"
    return f"{text.replace('.', ',')} %"


def proportion_text(ratio):
    """Una proporción con su margen de error (plan, "Margen de error"): "90,0 % (9 de
    10; IC 95 %: 59,6 % a 98,2 %)"; sin casos, "—"."""
    if not ratio or not ratio.get("total"):
        return "—"
    low, high = wilson_interval(ratio["ok"], ratio["total"])
    return (f"{_percent(ratio['ok'] / ratio['total'])} ({ratio['ok']} de {ratio['total']}; "
            f"IC 95 %: {_bound(low)} a {_bound(high)})")


ACCEPTANCE_MISSING = ("La corrida no tiene casos del lote de aceptación: las exigencias de "
                      "respuesta correcta y abstención no se pueden dar por cumplidas con "
                      "ella.")

ACCEPTANCE_FAILED_NOTE = ("Estos casos no se usan para ajustar (plan, \"Lote de "
                          "aceptación\"): cambiar instrucciones, umbral, parámetros de "
                          "búsqueda, reglas de partición, o datos clave o variantes a "
                          "partir de ellos le quita al lote su condición.")

INTERVAL_NOTE = ("IC 95 %: intervalo de confianza al 95 % por el método de Wilson (plan, "
                 "\"Margen de error\"). La exigencia se compara con el valor medido; el "
                 "intervalo dice cuánto se le puede creer.")


def measure_rows(measures):
    """Renglones de la tabla de medidas exigidas: exigencia, resultado, umbral, cumple.
    La cita literal y el tiempo son de toda la corrida; la respuesta correcta y la
    abstención, del lote de aceptación (`required_measures`)."""
    timing = measures["response_time"]
    return [
        ("Cita literal (toda la corrida)", proportion_text(measures["literal_citation"]),
         "100 %", _meets(measures["literal_citation"]["meets"])),
        ("Respuesta correcta que cita la unidad correcta (lote de aceptación)",
         proportion_text(measures["correct_answer"]),
         "al menos 85 %", _meets(measures["correct_answer"]["meets"])),
        ("Abstención (lote de aceptación)", proportion_text(measures["abstention"]),
         "al menos 90 %", _meets(measures["abstention"]["meets"])),
        ("Tiempo de respuesta (toda la corrida)",
         f"mediana {_seconds(timing['median'])} · máximo {_seconds(timing['max'])}",
         "máximo de 30 s", _meets(timing["meets"])),
    ]


def adjustment_rows(measures):
    """Renglones de la tabla del lote de ajuste (diagnóstico): medida y resultado."""
    return [(_MEASURE_TEXT[name], proportion_text(measures[name])) for name in PROPORTIONS]


def _score(value):
    return "—" if value is None else f"{value:.3f}".replace(".", ",")


def _number(value):
    """Un número para leer: entero sin decimales; si no, con un decimal y coma."""
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}".replace(".", ",")


def _when(iso):
    """Fecha y hora ISO como día/mes/año y hora:minuto ("03/10/2026 08:21")."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "—"


_FOLDER_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})")


def run_date(folder_name):
    """Una corrida por su fecha ("la del 03/10/2026 08:21"), leída del nombre de su
    carpeta; si el nombre no empieza con la fecha, `None`."""
    match = _FOLDER_DATE.match(folder_name)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    return f"la del {day}/{month}/{year} {hour}:{minute}"


def _run_name(folder_name):
    """Una corrida por su fecha, con la carpeta para encontrarla."""
    when = run_date(folder_name)
    if when is None:
        return f"carpeta `{folder_name}`"
    return f"{when} (carpeta `{folder_name}`)"


def drop_text(drop):
    """Una baja para leer: la medida y, si es de un lote, cuál."""
    text = _MEASURE_TEXT[drop["name"]].lower()
    if drop["lot"]:
        text += f" del lote de {LOT_TEXT[drop['lot']]}"
    return text


def comparison_lines(comparison):
    """Las líneas del comando sobre la corrida anterior: cuál fue, por su fecha, y si
    hay bajas que requieren aprobación (P7)."""
    if comparison is None:
        return ["Corrida anterior: ninguna"]
    previous = run_date(comparison["previous"]) or comparison["previous"]
    if comparison.get("error"):
        return [f"Corrida anterior: {previous}: {comparison['error']}. No se comparó."]
    drops = comparison["drops"]
    if drops:
        drop_line = ("Hay bajas respecto de la corrida anterior que requieren la aprobación "
                     "del responsable: " + ", ".join(drop_text(d) for d in drops) + ".")
    else:
        drop_line = "Sin bajas respecto de la corrida anterior."
    return [f"Corrida anterior: {previous}", drop_line]


def _ratio_text(ratio, unit=""):
    if ratio is None:
        return "no aplica"
    return f"{_percent(ratio['rate'])} ({ratio['ok']} de {ratio['total']}{unit})"


def _ids(ids, none="ninguno"):
    return ", ".join(ids) if ids else none


def _precise(value):
    """Un puntaje o un valor de la escala anterior a la sigmoide, con cuatro decimales,
    coma decimal y signo menos."""
    return "—" if value is None else f"{value:.4f}".replace(".", ",").replace("-", "−")


def _margin(value):
    return "—" if value is None else f"{value:.3f}".replace(".", ",")


def _sides(calibration):
    high, low = calibration["high_foreign"], calibration["low_answered"]
    return (f"A (ajena a la normativa más alta): {high['id']}, {_precise(high['score'])}"
            f" · B (con respuesta más baja): {low['id']}, {_precise(low['score'])}")


def threshold_line(calibration):
    """La línea del umbral propuesto, igual en `resumen.md` y en el comando (plan,
    "Abstención", "Qué se informa")."""
    head = "Umbral propuesto (provisorio): "
    if calibration["gap"] is None:
        return head + f"ninguno · la regla no se puede aplicar: {calibration['reason']}"
    if not calibration["gap"]:
        return (head + f"ninguno · No hay hueco: {_sides(calibration)}; A es mayor o igual "
                "que B. La decisión es del responsable")
    line = (head + f"{_score(calibration['proposed'])} · {_sides(calibration)} · margen "
            f"{_margin(calibration['margin'])} (mínimo "
            f"{_number(calibration['min_margin'])}) · cumple el margen mínimo: "
            f"{_meets(calibration['meets_margin'])}")
    if not calibration["meets_margin"]:
        line += " · sin margen: el valor no se fija sin decisión del responsable"
    return line


_PATH_TEXT = {
    retrieval.SEMANTIC: "por significado",
    retrieval.WORDS: "por palabras",
    retrieval.REFERENCE: "por referencia exacta",
    UNION: "en la unión",
}

_CONDITION_TEXT = {
    "commit": "commit",
    "models": "modelos",
    "prompt_version": "instrucciones",
    "corpus_version": "normativa",
    "search": "parámetros de búsqueda",
}

_MEASURE_TEXT = {
    "literal_citation": "Cita literal",
    "correct_answer": "Respuesta correcta que cita la unidad correcta",
    "abstention": "Abstención",
    "response_time_median": "Tiempo de respuesta (mediana)",
    "response_time": "Tiempo de respuesta (máximo)",
}

SMALL_SET_NOTE = ("Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia "
                  "de una pregunta no demuestra nada.")


def _by_regime_section(by_regime):
    out = ["## Medidas por régimen (diagnóstico)", "",
           "Casos del lote de ajuste, separados según el régimen esperado de cada caso. Son "
           "de diagnóstico: las exigencias de la spec se miden con el lote de aceptación, "
           "y con pocos casos por régimen sirven solo para orientar.", ""]
    if not by_regime:
        return out + ["Ningún caso medido.", ""]
    out += ["| Régimen | Respuesta correcta | Abstención |", "|---|---|---|"]
    for regime, measures in by_regime.items():
        out.append(f"| {regime or 'Sin régimen cargado a la fecha'} | "
                   f"{proportion_text(measures['correct_answer'])} | "
                   f"{proportion_text(measures['abstention'])} |")
    return out + [""]


def _adjustment_section(measures):
    out = ["## Lote de ajuste (diagnóstico)", "",
           "Casos sin `lote` o con `lote: ajuste` (ADR-0014): son los que se usan para "
           "ajustar el corrector, los datos clave, el umbral y las instrucciones. Se "
           "informan como diagnóstico; no sirven para dar por cumplidas las exigencias.", "",
           "| Medida | Resultado |", "|---|---|"]
    out += [f"| {name} | {result} |" for name, result in adjustment_rows(measures)]
    return out + [""]


def _retrieval_section(measures):
    out = ["## Recuperación (diagnóstico)", "",
           "Casos del lote de ajuste, leído del registro de cada consulta. La unidad "
           "correcta cuenta si están "
           "todas las unidades esperadas del caso (un inciso vale con su artículo); se "
           "mide sobre las preguntas con respuesta (ADR-0003).", "",
           "| Medida | Resultado |", "|---|---|"]
    for key, ratio in measures["found"].items():
        out.append(f"| Unidad correcta entre los candidatos {_PATH_TEXT[key]} | "
                   f"{_ratio_text(ratio)} |")
    position = measures["position"]
    timing = measures["retrieval_time"]
    out += [
        f"| Unidad correcta entre las enviadas al modelo | "
        f"{_ratio_text(measures['selected'])} |",
        f"| Posición de la unidad correcta en el orden del reranker | mediana "
        f"{_number(position['median'])} · peor {_number(position['max'])} |",
        f"| Preguntas con respuesta frenadas por el umbral | "
        f"{_ratio_text(measures['answered_stopped'])} |",
        f"| Preguntas sin respuesta frenadas por el umbral | "
        f"{_ratio_text(measures['unanswered_stopped'])} |",
        f"| Tiempo de la recuperación | mediana {_seconds(timing['median'])} · máximo "
        f"{_seconds(timing['max'])} |",
        "",
        f"Preguntas con respuesta frenadas por el umbral: "
        f"{_ids(measures['answered_stopped_ids'], 'ninguna')}.",
        f"Preguntas con respuesta cuya unidad correcta no llegó al modelo: "
        f"{_ids(measures['not_selected'], 'ninguna')}.",
        "",
    ]
    return out


def _output_failures_section(failures):
    return ["## Salidas con falla de formato o de cita", "",
            "Se cuentan por el tipo de anomalía; una falla de un servicio no cuenta. Se "
            "espera ninguna.", "",
            f"- Falla de formato (la salida no cumple el esquema): {len(failures['format'])}"
            f" ({_ids(failures['format'])}).",
            f"- Falla de cita (cita una unidad que no se mostró o una afirmación sin cita): "
            f"{len(failures['citation'])} ({_ids(failures['citation'])}).",
            ""]


def _special_section(special):
    def describe(entries):
        if not entries:
            return "ningún caso corrido"
        return ", ".join(f"{e['id']} {'pasa' if e['passed'] else 'falla'}" for e in entries)

    return ["## Casos de REQ-018 y REQ-019", "",
            f"- REQ-018 (etiqueta \"dos categorías\"): {describe(special['REQ-018'])}.",
            "- REQ-019 (casos con la marca de regímenes distintos: el régimen específico "
            f"y el marco nacional difieren): {describe(special['REQ-019'])}.",
            ""]


_GROUP_TEXT = {
    "answered": "con respuesta",
    "foreign": "ajena a la normativa",
    "near": "tema cercano",
    "other": "sin respuesta (otra)",
}


def _scored_ids(ids, scores):
    if not ids:
        return "ninguna"
    return ", ".join(f"{case_id} ({_precise(scores[case_id])})" for case_id in ids)


def _calibration_section(calibration, lines):
    current = calibration["current"]
    proposed = calibration["proposed"]
    scores = calibration["scores"]
    out = ["## Calibración del umbral (provisoria)", "",
           f"{threshold_line(calibration)} · umbral actual: {_score(current['threshold'])}.",
           "",
           "Regla del hueco (ADR-0014, punto 2; plan, \"Abstención\"): con las preguntas "
           "del lote de ajuste, el umbral va en el punto medio, en la escala anterior a la "
           "sigmoide, entre la pregunta ajena a la normativa con el puntaje más alto (A) y "
           "la pregunta con respuesta con el puntaje más bajo (B), redondeado hacia abajo "
           "a tres decimales; el margen es la mitad del hueco y el mínimo, "
           f"{_number(calibration['min_margin'])}. Las preguntas de tema cercano no entran: "
           "las tiene que frenar el modelo. La calibración no cambia el umbral configurado "
           "del sistema: el valor es provisorio y fijarlo es una decisión aparte.", ""]
    if calibration["gap"] is None:
        out += [f"La regla no se puede aplicar: {calibration['reason']}.", ""]
    else:
        high, low = calibration["high_foreign"], calibration["low_answered"]
        out += ["| Dato | Caso | Puntaje | Escala anterior a la sigmoide |",
                "|---|---|---|---|",
                f"| A: ajena a la normativa más alta | {high['id']} | "
                f"{_precise(high['score'])} | {_precise(high['logit'])} |",
                f"| B: con respuesta más baja | {low['id']} | {_precise(low['score'])} | "
                f"{_precise(low['logit'])} |"]
        if calibration["gap"]:
            midpoint = calibration["midpoint"]
            out += [f"| Punto medio | — | {_precise(sigmoid(midpoint))} | "
                    f"{_precise(midpoint)} |", "",
                    f"- Margen: {_margin(calibration['margin'])} (mínimo "
                    f"{_number(calibration['min_margin'])}); cumple el margen mínimo: "
                    f"{_meets(calibration['meets_margin'])}."]
            if not calibration["meets_margin"]:
                out += ["", "**El margen no llega al mínimo: el umbral propuesto queda "
                        "marcado como sin margen y no se fija sin decisión del "
                        "responsable.**"]
            out.append("")
        else:
            out += ["", "**No hay hueco: A es mayor o igual que B. La decisión es del "
                    "responsable.**", "",
                    "- Ajenas a la normativa con puntaje mayor o igual que B: "
                    f"{_scored_ids(calibration['foreign_at_or_above_low'], scores)}.",
                    "- Preguntas con respuesta con puntaje menor o igual que A: "
                    f"{_scored_ids(calibration['answered_at_or_below_high'], scores)}.",
                    ""]
    without = "sin umbral propuesto"
    out += [
        "- Preguntas sin respuesta que frena el umbral propuesto: "
        + (_ids(calibration["unanswered_stopped"], "ninguna") if proposed is not None
           else without)
        + f" (de {calibration['unanswered']} con puntaje); las que frena el actual: "
        f"{_ids(current['unanswered_stopped'], 'ninguna')}.",
        "- Preguntas con respuesta que frena el umbral propuesto: "
        + (_ids(calibration["blocked"], "ninguna") if proposed is not None else without)
        + f" (de {calibration['answered']} con puntaje); las que frena el actual: "
        f"{_ids(current['blocked'], 'ninguna')}.",
        "- Preguntas de tema cercano que quedan por encima del umbral propuesto (las "
        "tiene que frenar el modelo): "
        + (_ids(calibration["near_above"], "ninguna") if proposed is not None
           else without) + ".",
        "- Preguntas con respuesta sin puntaje (ningún umbral las cambia): "
        f"{_ids(calibration['without_score'], 'ninguna')}.",
        ""]
    if calibration["table"]:
        regimes = {line["id"]: line.get("expected_regime") for line in lines}
        out += ["Puntajes del lote de ajuste:", "",
                "| Caso | Grupo | Régimen | Puntaje más alto | Escala anterior a la "
                "sigmoide |", "|---|---|---|---|---|"]
        out += [f"| {row['id']} | {_GROUP_TEXT[row['group']]} | "
                f"{regimes.get(row['id']) or '—'} | {_precise(row['score'])} | "
                f"{_precise(row['logit'])} |" for row in calibration["table"]]
        out.append("")
    return out


def _ablation_section(ablation):
    out = ["## Comparación quitando piezas", ""]
    if ablation is None:
        return out + ["No se corrió en esta corrida. Se corre una vez, con "
                      "`correr_evals --quitando-piezas` (ADR-0003).", ""]
    out += ["Cada caso del lote de ajuste se recupera y se selecciona con cada "
            "configuración, sin el modelo de generación.", "",
            "\"Entre las seleccionadas\" son las que la recuperación deja pasar por el "
            "umbral; sin reranker no hay umbral y pasan todas las de la unión, así que "
            "coincide con \"entre los candidatos\". \"Entre las enviadas al modelo\" son "
            "las que quedan después de los cupos por categoría y del espacio del pedido.",
            "",
            "| Configuración | Umbral | Entre los candidatos | Entre las seleccionadas | "
            "Entre las enviadas al modelo | "
            "Posición (mediana · peor) | Con respuesta frenadas por el umbral | "
            "Sin respuesta frenadas por el umbral | Tiempo de la recuperación |",
            "|---|---|---|---|---|---|---|---|---|"]
    for config in ablation:
        position = config["position"]
        timing = config["retrieval_time"]
        threshold = (_score(config["threshold"]) if config["threshold"] is not None
                     else "sin umbral")
        out.append(
            f"| {config['name']} | {threshold} | {_ratio_text(config['found'][UNION])} | "
            f"{_ratio_text(config['selected'])} | {_ratio_text(config['delivered'])} | "
            f"{_number(position['median'])} · {_number(position['max'])} | "
            f"{_ratio_text(config['answered_stopped'])} | "
            f"{_ratio_text(config['unanswered_stopped'])} | "
            f"mediana {_seconds(timing['median'])} · máximo {_seconds(timing['max'])} |")
    errors = [f"{config['name']}: {', '.join(config['errors'])}"
              for config in ablation if config["errors"]]
    out += ["", "Fallas técnicas: " + ("; ".join(errors) if errors else "ninguna") + ".",
            SMALL_SET_NOTE, ""]
    return out


def _comparison_value(name, value):
    if name in (TIME_MEDIAN, TIME_MAX):
        return _seconds(value)
    return _percent(value)


def _change_text(row):
    before, now = row["previous"], row["current"]
    if row["name"] == TIME_MAX and row["drop"]:
        return f"baja (supera el límite de {_number(MAX_SECONDS)} s)"
    if row["name"] == TIME_MEDIAN and row["drop"]:
        return f"baja (sube más del {_number(MEDIAN_RISE_LIMIT * 100)} %)"
    if row["drop"]:
        return "baja"
    if before is None or now is None:
        return "—"
    if before == now:
        return "igual"
    if row["name"] in (TIME_MEDIAN, TIME_MAX):
        return "más lento" if now > before else "más rápido"
    return "mejora"


def _comparison_section(comparison):
    out = ["## Comparación con la corrida anterior", ""]
    if comparison is None:
        return out + ["No hay una corrida anterior en la carpeta de corridas.", ""]
    if comparison.get("error"):
        return out + [f"Corrida anterior: {_run_name(comparison['previous'])}: "
                      f"{comparison['error']}. No se comparó.", ""]
    changed = comparison["conditions_changed"]
    if comparison.get("rescore"):
        conditions = ("Esta carpeta es una recalificación de esa corrida: las respuestas "
                      "son las mismas y solo cambian los casos o el corrector. Una "
                      "recalificación no es una corrida nueva a los efectos de P7.")
    elif changed:
        conditions = ("Cambió: " + ", ".join(_CONDITION_TEXT[c] for c in changed)
                      + ". No es una repetición: las diferencias pueden venir de ese cambio.")
    else:
        conditions = ("Las dos corridas tienen las mismas condiciones (commit, modelos, "
                      "instrucciones, normativa y parámetros de búsqueda): cuenta como "
                      "repetición.")
    out += [f"Corrida anterior: {_run_name(comparison['previous'])}.", "", conditions, "",
            "Cada lote se compara con el mismo lote de la anterior; en una corrida sin el "
            "campo `lote`, todos los casos son del lote de ajuste. El tiempo es de toda la "
            "corrida.", ""]
    header = ["| Medida | Anterior | Actual | Cambio |", "|---|---|---|---|"]

    def table(rows):
        return header + [f"| {_MEASURE_TEXT[row['name']]} | "
                         f"{_comparison_value(row['name'], row['previous'])} | "
                         f"{_comparison_value(row['name'], row['current'])} | "
                         f"{_change_text(row)} |" for row in rows]

    lots = comparison.get("lots") or {}
    for lot in LOTS:
        out += [f"### Lote de {LOT_TEXT[lot]}", ""]
        counted = lots.get(lot, {})
        if not counted.get("previous") and not counted.get("current"):
            out += ["Ninguna de las dos corridas tiene casos de este lote.", ""]
            continue
        out += table([row for row in comparison["measures"] if row["lot"] == lot]) + [""]
    out += ["### Tiempo de toda la corrida", ""]
    out += table([row for row in comparison["measures"] if row["lot"] is None])
    equality = comparison["equality"]
    if comparison["drops"]:
        out += ["", "**Hay bajas respecto de la corrida anterior ("
                + ", ".join(drop_text(drop) for drop in comparison["drops"])
                + "): cada una requiere la aprobación explícita del responsable (P7).**"]
    out += ["",
            f"- Pasaban y ahora fallan: {_ids(comparison['regressions'])}.",
            f"- Fallaban y ahora pasan: {_ids(comparison['improvements'])}.",
            f"- Cambiaron de resultado o de citas sin cambiar si pasan: "
            f"{_ids(comparison['changed'])}.",
            f"- Solo en la anterior: {_ids(comparison['only_previous'])}. Solo en esta: "
            f"{_ids(comparison['only_current'])}.",
            ""]
    if comparison.get("rescore"):
        return out + [SMALL_SET_NOTE, ""]
    out += [f"Igualdad al repetir: {equality['same']} de {equality['total']} casos corridos "
            "en las dos dan el mismo resultado (estado, motivo, citas y texto de las "
            f"afirmaciones); {equality['same_status_reason_and_citations']} de "
            f"{equality['total']} con el mismo estado, el mismo motivo y las mismas citas. "
            "Con temperatura 0 y semilla fija, la primera consulta después de levantar el "
            "motor puede redactar distinto sin cambiar estado, motivo ni citas (T-018).",
            "", SMALL_SET_NOTE, ""]
    return out


def summary_markdown(report):
    """Contenido de `resumen.md`."""
    p = report.parameters
    search = p["search"]
    versions = p["prompt_version"]
    if versions is None:
        versions = "ninguna (ninguna consulta llamó al modelo)"
    elif isinstance(versions, list):
        versions = "varias: " + ", ".join(versions)
    rescored = p.get("rescore")
    if rescored:
        out = [
            f"# Recalificación de la corrida del {_when(p['started_at'])}",
            "",
            f"Recalificación de la carpeta `{rescored['source']}`, hecha el "
            f"{_when(rescored['rescored_at'])} con el commit `{rescored['commit']}` y los "
            f"casos de `{rescored['cases_dir']}`. {RESCORE_NOTE} Se compara con esa "
            "corrida al final. Salvo la carpeta y las cantidades de casos, los datos que "
            "siguen son los de la corrida de origen.",
            "",
        ]
    else:
        out = [f"# Corrida del {_when(p['started_at'])}", ""]
    out += [
        f"- Carpeta: `{report.folder.name}`",
        f"- Comienzo: {_when(p['started_at'])} · fin: {_when(p['finished_at'])}",
        f"- Commit: `{p['commit']}`",
        f"- Modelo de generación: `{search['generation']['model']}` "
        f"(compilación `{search['generation']['engine_build']}`)",
        f"- Versión de las instrucciones: {versions}",
        f"- Versión de la normativa: {p['corpus_version'] if p['corpus_version'] is not None else 'ninguna'}",
        "- Umbral del modelo que reordena los resultados (reranker): "
        f"{_score(search['rerank_threshold'])}",
        f"- {counts_line(report)}",
        "",
    ]
    if not report.results:
        out += [f"**{NOTHING_RAN}**", ""]

    out += ["## Medidas exigidas", "",
            "La cita literal y el tiempo se miden sobre toda la corrida; la respuesta "
            "correcta y la abstención, sobre el lote de aceptación (ADR-0014; plan, "
            "\"Lote de aceptación\").", "",
            "| Exigencia | Resultado | Umbral | Cumple |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in measure_rows(report.measures)]
    out.append("")
    if not report.measures["acceptance_cases"]:
        out += [f"**{ACCEPTANCE_MISSING}**", ""]
    out += [INTERVAL_NOTE + " Una falla técnica no cuenta como abstención. El responsable "
            "revisa además las respuestas contra la esperada.", ""]

    out += _adjustment_section(report.adjustment_measures)
    out += _by_regime_section(report.by_regime)

    out += ["## Pares de REQ-020", ""]
    if report.pairs:
        out += ["| Par | Resultado | Detalle |", "|---|---|---|"]
        out += [f"| {' y '.join(pair['cases'])} | {pair['status']} | "
                f"{'; '.join(pair['problems']) or '—'} |" for pair in report.pairs]
    else:
        out.append("Ningún par entre los casos corridos.")
    out.append("")

    notices = report.notices
    out += ["## Aviso de REQ-021", "",
            f"{notices['ok']} de {notices['total']} casos traen o no traen el aviso de "
            "modificatorias sin cargar según lo esperado.", ""]
    if notices["failed"]:
        out += ["Fallan: " + ", ".join(notices["failed"]) + ".", ""]

    out += _retrieval_section(report.retrieval)
    out += _output_failures_section(report.output_failures)
    out += _special_section(report.special)
    out += _calibration_section(report.calibration, report.results)
    out += _ablation_section(report.ablation)
    out += _comparison_section(report.comparison)

    def failed_cases(lines):
        failed = [(line["id"], _failures(line)) for line in lines if _failures(line)]
        if not failed:
            return ["Ninguno."]
        return [f"- {case_id}: {'; '.join(reasons)}." for case_id, reasons in failed]

    out += ["## Casos fallados", "", "Casos del lote de ajuste.", ""]
    out += failed_cases(lot_lines(report.results, ADJUSTMENT)) + [""]
    out += ["## Casos fallados del lote de aceptación", ""]
    acceptance = lot_lines(report.results, ACCEPTANCE)
    if acceptance:
        out += [ACCEPTANCE_FAILED_NOTE, ""] + failed_cases(acceptance) + [""]
    else:
        out += ["La corrida no tiene casos del lote de aceptación.", ""]

    out += ["## Casos no corridos", ""]
    if report.skipped:
        out += [f"- {s.file}: {s.reason}." for s in report.skipped]
    else:
        out.append("Ninguno.")
    out.append("")
    return "\n".join(out)
