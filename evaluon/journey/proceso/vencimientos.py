"""Qué vence hoy y qué venció, por paso y por acción (REQ-157; plan 018, «Vence hoy en lila»).

Traduce los plazos de `tablero/ingreso.plazos()` (REQ-131) a una marca: `"hoy"` (lila, «Vence
hoy»), `"vencido"` (rojo, «Vencido») o `""`.

- La apertura de ofertas pertenece al paso 3 y a su acción «Agregar las ofertas del acta». Es un
  hecho, no un plazo que se incumple: hoy es `"hoy"`, pasada o futura no marca nada.
- El vencimiento del mantenimiento pertenece al paso 7 y a su acción del dictamen. Es lo único
  que puede estar `"vencido"`, y solo con fecha calculable (`state == "computed"`) y sin dictamen.
- El dictamen no tiene fecha prevista: no vence. Sin fecha calculable, nada.
"""

from dataclasses import dataclass
from datetime import date

from evaluon.journey.proceso import pasos
from evaluon.journey.tablero import ingreso


def _evento(plazos, clave):
    return next((e for e in plazos.events if e.key == clave), None)


def _dictamen_cargado(plazos):
    """El dictamen existe si el plazo «dictamen» tiene fecha (`ingreso.dictamen_day`)."""
    evento = _evento(plazos, "dictamen")
    return evento is not None and evento.day is not None


def _mantenimiento(plazos, hoy):
    """La marca del mantenimiento: `hoy`, `vencido` o `""` (sin mirar el dictamen)."""
    if plazos.maintenance.state != "computed":
        return ""
    due = plazos.maintenance.due
    if due == hoy:
        return pasos.MARCA_HOY
    return pasos.MARCA_VENCIDO if due < hoy else ""


def _apertura(plazos, hoy):
    evento = _evento(plazos, "apertura")
    return pasos.MARCA_HOY if evento is not None and evento.day == hoy else ""


def _que_es(objeto):
    """`(paso, kind)` de un `Paso` (kind vacío) o de una `Accion`."""
    if hasattr(objeto, "kind"):
        return objeto.paso, objeto.kind
    return objeto.numero, ""


def marca_de(paso_o_accion, plazos, hoy=None, dictamen_cargado=None):
    """`"hoy"`, `"vencido"` o `""` para un `Paso` o una `Accion`. `dictamen_cargado` se deduce
    de los plazos si no se pasa."""
    hoy = hoy or ingreso.today()
    numero, kind = _que_es(paso_o_accion)
    if numero == 3 and kind in ("", pasos.KIND_ACTA):
        return _apertura(plazos, hoy)
    if numero == 7 and kind in ("", pasos.KIND_DICTAMEN):
        if dictamen_cargado is None:
            dictamen_cargado = _dictamen_cargado(plazos)
        return "" if dictamen_cargado else _mantenimiento(plazos, hoy)
    return ""


@dataclass(frozen=True)
class Vencimiento:
    """El vencimiento más próximo de un procedimiento, para el inicio. `orden` ordena: vencidos
    primero (el más viejo antes), después hoy, después los futuros por fecha."""

    marca: str  # hoy | vencido | "" (futuro)
    paso: int
    dia: date
    texto: str
    orden: tuple


def _texto(marca, dia, hoy):
    delta = (dia - hoy).days
    if marca == pasos.MARCA_VENCIDO:
        return f"Vencido hace {-delta} {'día' if delta == -1 else 'días'}"
    if marca == pasos.MARCA_HOY:
        return pasos.TEXTOS_MARCA[marca]
    return f"{dia:%d/%m/%Y} · faltan {delta} {'día' if delta == 1 else 'días'}"


def _orden(candidato):
    marca, paso, dia = candidato
    grupo = {pasos.MARCA_VENCIDO: 0, pasos.MARCA_HOY: 1}.get(marca, 2)
    return (grupo, dia, paso)


def proximo(plazos, hoy=None, dictamen_cargado=None):
    """El vencimiento más próximo (`Vencimiento`) o `None` si no hay fecha. Candidatos: la
    apertura que no pasó y el mantenimiento calculable sin dictamen (vencido, hoy o futuro)."""
    hoy = hoy or ingreso.today()
    if dictamen_cargado is None:
        dictamen_cargado = _dictamen_cargado(plazos)
    candidatos = []
    apertura = _evento(plazos, "apertura")
    if apertura is not None and apertura.day is not None and apertura.day >= hoy:
        candidatos.append((pasos.MARCA_HOY if apertura.day == hoy else "", 3, apertura.day))
    if not dictamen_cargado and plazos.maintenance.state == "computed":
        candidatos.append((_mantenimiento(plazos, hoy), 7, plazos.maintenance.due))
    if not candidatos:
        return None
    elegido = min(candidatos, key=_orden)
    marca, paso, dia = elegido
    return Vencimiento(marca, paso, dia, _texto(marca, dia, hoy), _orden(elegido))
