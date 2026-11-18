"""Hitos de la línea de plazos (T-349, REQ-158): posición en el eje, niveles y hitos sin fecha."""

from datetime import date

from evaluon.journey.proceso import mapa
from evaluon.journey.tablero.ingreso import Terms


def _t(key, day, state="future", note=""):
    return Terms(key, key.capitalize(), key, day, day.strftime("%d/%m") if day else ("Pendiente" if key == "dictamen" else "Falta"), state, note)


def test_REQ_158_hitos_proporcionales_a_la_fecha():
    """REQ-158: la posición es proporcional a la fecha, del primer al último día."""
    r = mapa.hitos_en_eje([_t("apertura", date(2026, 11, 1), "past"),
                           _t("hoy", date(2026, 11, 11), "now"),
                           _t("vence", date(2026, 12, 1))])
    assert {h.key: h.posicion for h in r.hitos} == {"apertura": 0.0, "hoy": 33.33, "vence": 100.0}
    assert all(h.nivel == 0 for h in r.hitos) and r.sin_fecha == ()


def test_REQ_158_dos_hitos_a_menos_de_12_por_ciento_bajan_un_nivel():
    """REQ-158: el segundo de dos hitos cercanos baja un nivel."""
    r = mapa.hitos_en_eje([_t("apertura", date(2026, 11, 1), "past"),
                           _t("hoy", date(2026, 11, 3), "now"),
                           _t("vence", date(2026, 12, 1))])
    assert {h.key: h.nivel for h in r.hitos} == {"apertura": 0, "hoy": 1, "vence": 0}


def test_REQ_158_hitos_sin_fecha_van_como_texto_aparte():
    """REQ-158: sin fecha no hay hito en el eje; queda su motivo."""
    r = mapa.hitos_en_eje([_t("apertura", None, "pending", "Falta la apertura en el cronograma"),
                           _t("hoy", date(2026, 11, 17), "now"),
                           _t("vence", None, "pending", "Falta el calendario"),
                           _t("dictamen", None, "pending")])
    assert [h.key for h in r.hitos] == ["hoy"]
    assert [(s.key, s.motivo) for s in r.sin_fecha] == [
        ("apertura", "Falta la apertura en el cronograma"),
        ("vence", "Falta el calendario"),
        ("dictamen", "Pendiente")]
    assert r.hitos[0].posicion == 50.0 and r.hitos[0].etiqueta == "Hoy · 17/11"


def test_REQ_158_hoy_fuera_de_rango_amplia_el_eje():
    """REQ-158: si hoy cae antes de la apertura, el eje empieza en hoy."""
    r = mapa.hitos_en_eje([_t("apertura", date(2026, 11, 20), "future"),
                           _t("hoy", date(2026, 11, 10), "now"),
                           _t("vence", date(2026, 12, 10))])
    pos = {h.key: h.posicion for h in r.hitos}
    assert pos["hoy"] == 0.0 and pos["vence"] == 100.0 and 0 < pos["apertura"] < 100


def test_REQ_158_sin_eventos():
    """REQ-158: sin eventos, nada."""
    r = mapa.hitos_en_eje([])
    assert r.hitos == () and r.sin_fecha == ()


def test_REQ_158_el_estado_pasa_tal_cual():
    """REQ-158: el estado del hito se conserva (para «Vence hoy» y «Vencido»)."""
    r = mapa.hitos_en_eje([_t("vence", date(2026, 11, 17), "now"), _t("hoy", date(2026, 11, 17), "now")])
    assert {h.estado for h in r.hitos} == {"now"}
    assert [h.nivel for h in r.hitos] == [0, 1]


def _real(key, etiqueta, day, state="future", note=""):
    return Terms(key, etiqueta, key, day, day.strftime("%d/%m"), state, note)


def _sin_pisarse(eje):
    """Ningún par de etiquetas del mismo nivel se cruza (con el mismo cálculo del eje)."""
    cajas = [(h.nivel, *mapa._ocupa(h.posicion, h.etiqueta if h.key == "hoy" else h.texto,
                                    "" if h.key == "hoy" else h.etiqueta.split(" · ")[0],
                                    h.nota or "", h.key == "hoy")) for h in eje.hitos]
    return all(a[0] != b[0] or a[2] <= b[1] or b[2] <= a[1]
               for i, a in enumerate(cajas) for b in cajas[i + 1:])


def test_T361_H2_con_fechas_reales_cercanas_las_etiquetas_no_se_pisan():
    """REQ-158 (T-361, H-2): apertura y mantenimiento a ~17 % uno del otro con las etiquetas largas
    de verdad: no comparten nivel (antes, a más de 12 % de distancia, se pisaban)."""
    r = mapa.hitos_en_eje([
        _real("apertura", "Apertura de ofertas", date(2026, 3, 2), "past", "hace 8 meses"),
        _real("hoy", "Hoy", date(2026, 11, 18), "now"),
        _real("vence", "Vence el mantenimiento de las ofertas", date(2026, 5, 4), "past",
              "venció hace 6 meses"),
        _real("dictamen", "Dictamen de la Comisión", date(2027, 2, 19), "future", "faltan 93 días")])
    assert _sin_pisarse(r) and not r.en_lista
    niveles = {h.key: h.nivel for h in r.hitos}
    assert niveles["apertura"] != niveles["vence"]


def test_T361_H2_lo_que_no_entra_en_los_dos_niveles_va_en_la_lista():
    """REQ-158 (T-361): con cuatro fechas pegadas lo que no entra no se dibuja pisado: va en
    `en_lista`, con su fecha, y las que quedan sobre el eje no se cruzan."""
    r = mapa.hitos_en_eje([
        _real("apertura", "Apertura de ofertas", date(2026, 11, 10), "past"),
        _real("hoy", "Hoy", date(2026, 11, 11), "now"),
        _real("vence", "Vence el mantenimiento de las ofertas", date(2026, 11, 12)),
        _real("dictamen", "Dictamen de la Comisión", date(2027, 11, 1), "future")])
    assert _sin_pisarse(r) and r.en_lista
    assert {h.key for h in r.hitos} | {h.key for h in r.en_lista} == {
        "apertura", "hoy", "vence", "dictamen"}
    assert all(h.nivel in (0, 1) for h in r.hitos)
