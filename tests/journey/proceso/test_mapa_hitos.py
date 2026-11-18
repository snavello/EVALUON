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
