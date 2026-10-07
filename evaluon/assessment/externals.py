"""Verificaciones externas: lo que no se resuelve con la oferta (REQ-063; plan 004, "Qué se
decide sin el modelo y en qué orden", regla 1; ADR-0043; T-166).

Un requisito es externo si su texto vigente del pliego coincide con el catálogo de abajo o si el
modelo lo marcó `externo`. El resultado es siempre el mismo: "no determinado" con el motivo
`externo`, que la pantalla rotula «Falta la hoja de compliance». Nunca es una "duda", ni "no se
encontró el documento", ni una pregunta a la Comisión: la acción es subir la hoja (decisión
literal del responsable: «eso lo integrará un documento que llamamos hoja de compliance»). El
sistema no infiere la consulta (P9).

Si la Comisión ya subió la hoja (una decisión `subsanar` sobre un resultado `externo` del mismo
par), la regla no rige: la hoja es un documento más de la oferta y se evalúa por lectura, con su
cita.

El catálogo es una lista de expresiones en código, versionada con `ASSESSMENT_RULES_VERSION`.
Sumar un tipo de verificación es un cambio de código con su prueba. Cada entrada es lo más
específica que se pudo, para no marcar como externo un requisito que se resuelve con la oferta
(un documento que el oferente debe acompañar sigue su camino: lo marca el modelo si corresponde).
"""

import re
import unicodedata
from dataclasses import dataclass, replace

from evaluon.assessment import combine
from evaluon.assessment.models import Action, Decision, Doubt

RULE_CATALOG = "externo_catalogo"
RULE_MODEL = "externo_modelo"

EXPLANATION = ("Falta la hoja de compliance: este requisito se verifica con una consulta fuera "
               "de la oferta{what}, y esa hoja no está cargada. Se resuelve subiendo la hoja "
               "(aunque informe que no cumple).")


def fold(text):
    """Minúsculas, sin acentos y con los espacios colapsados: lo que se compara con el catálogo."""
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return " ".join(plain.lower().split())


# Verbos con que un pliego dice que algo se comprueba por una consulta de la Comisión.
_VERIFIED = r"(?:verific|consult|constat|comprob|control|valid)"

# Verbos con que un pliego dice que una póliza se comprueba (no «válida» como adjetivo).
_POLICY_VERB = r"(?:verific|consult|constat|comprob|validar|validacion|validen?\b)"


@dataclass(frozen=True)
class ExternalCheck:
    """Un tipo de verificación externa: clave estable, rótulo (qué consulta falta) y la
    expresión que lo reconoce en el texto del pliego (ya sin acentos y en minúsculas)."""

    key: str
    label: str
    pattern: re.Pattern

    def matches(self, folded):
        return self.pattern.search(folded) is not None


def _check(key, label, pattern):
    return ExternalCheck(key, label, re.compile(pattern))


CATALOG = (
    _check("registro_proveedores", "Registro de Proveedores",
           r"(?:(?:estar|encontrarse|hallarse|figurar)\s+inscript[oa]s?\b.{0,60}"
           r"registro de proveedores"
           rf"|registro de proveedores.{{0,80}}{_VERIFIED}"
           rf"|{_VERIFIED}\w*.{{0,80}}registro de proveedores"
           r"|tramite de inscripcion.{0,60}registro de proveedores"
           r"|estado de (?:la )?inscripcion.{0,60}registro de proveedores)"),
    _check("sancionados", "REPSAL o registro de sancionados",
           r"\brepsal\b|registro publico de empleadores con sanciones laborales"
           r"|registro de sancionados|\bsancionad[oa]s?\b"),
    _check("deuda", "situación de deuda del oferente",
           r"deuda exigible|existencia de deuda|deuda (?:tributaria|previsional|fiscal)"
           r"|situacion (?:fiscal|previsional)"),
    _check("seguros", "Superintendencia de Seguros de la Nación",
           # T-172 (H-C): la mención de la Superintendencia, o un verbo de verificación sobre la
           # póliza. Una póliza que el oferente presenta no es externa.
           r"superintendencia de seguros|\bssn\b"
           r"|validacion de (?:la |las )?polizas?|validez de (?:la |las )?polizas?"
           rf"|polizas?.{{0,80}}{_POLICY_VERB}|{_POLICY_VERB}\w*.{{0,80}}polizas?"),
    _check("habilidad_contratar", "habilidad para contratar",
           rf"habilidad para contratar.{{0,120}}{_VERIFIED}"
           rf"|{_VERIFIED}\w*.{{0,120}}habilidad para contratar"
           r"|habilidad para contratar.{0,120}(?:articulo 18|art\. ?18|causas? penal"
           r"|causales? de inhabilidad|sanciones)"
           r"|(?:articulo 18|art\. ?18|causas? penal|causales? de inhabilidad).{0,120}"
           r"habilidad para contratar"
           # T-172 (H-C): la declaración jurada de habilidad se reconoce por la palabra
           # «habilidad» o por los supuestos del artículo 18 junto a la declaración, en la forma
           # del pliego (completar o anexo); otra declaración jurada «que se agrega como Anexo»
           # no lo es, y «adjuntar la declaración de habilidad firmada» sigue siendo un
           # documento de la oferta.
           r"|(?=.*(?:completar|anexo))(?:.*declaracion jurada.{0,120}habilidad"
           r"|.*habilidad.{0,120}declaracion jurada)"
           r"|declaracion jurada.{0,200}(?:articulo 18|art\. ?18|causas? penal|inhabilidad"
           r"|sanciones)"
           r"|(?:articulo 18|art\. ?18|causas? penal|inhabilidad|sanciones).{0,200}"
           r"declaracion jurada"),
)


def match(text):
    """Las entradas del catálogo que reconocen el texto del requisito (lista, quizá vacía)."""
    folded = fold(text)
    return [check for check in CATALOG if check.matches(folded)]


def remedied(offer, requirement):
    """La Comisión ya subió la hoja para este par: hay una decisión `subsanar` sobre un
    resultado `externo` del par (`remedy.py`)."""
    return Decision.objects.filter(
        action=Action.SUBSANAR, result__offer=offer, result__requirement=requirement,
        result__doubt=Doubt.EXTERNO).exists()


def rule(pair, ctx):
    """La regla 1 de `rules.py`: devuelve el resultado nuevo del par (`Combined`) o `None` si
    el requisito no es externo o ya se subió la hoja."""
    combined = pair.combined
    found = match(pair.text.text)
    if not found and combined.doubt != combine.EXTERNAL:
        return None
    if remedied(ctx.offer, pair.requirement):
        return None
    what = f" ({'; '.join(c.label for c in found)})" if found else ""
    facts = {**combined.facts, "regla": RULE_CATALOG if found else RULE_MODEL,
             "externo": {"tipos": [c.key for c in found],
                         "consultas": [c.label for c in found]}}
    return replace(combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.EXTERNAL,
                   question="", explanation=EXPLANATION.format(what=what), facts=facts)
