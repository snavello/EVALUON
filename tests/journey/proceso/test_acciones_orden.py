"""El orden de «Qué se puede hacer ahora» y el corte de 6 (REQ-146, REQ-157; T-344). Sin base:
se arman `Accion` a mano."""

from evaluon.journey.proceso import acciones, pasos


def A(paso, tipo, kind, marca=""):
    return pasos.Accion(paso, tipo, kind, f"{paso}-{tipo}-{kind}", marca=marca)


def test_req157_vencido_hoy_pendientes_cierres_faltantes_y_por_paso():
    """REQ-157: primero lo vencido, después lo que vence hoy, y después pendientes, cierres y
    faltantes; dentro de cada grupo, por número de paso."""
    desordenadas = [
        A(1, "faltante", "datos"), A(6, "pendiente", "cumple"), A(2, "cierre", "proponer"),
        A(7, "cierre", "dictamen", "hoy"), A(4, "pendiente", "informe_ok"),
        A(3, "cierre", "acta", "hoy"), A(7, "pendiente", "dictamen", "vencido"),
        A(3, "faltante", "compliance"), A(4, "cierre", "evaluar"), A(1, "pendiente", "portal")]
    assert [a.id for a in acciones.ordenar(desordenadas)] == [
        "7-pendiente-dictamen",                      # vencido
        "3-cierre-acta", "7-cierre-dictamen",        # vence hoy, por paso
        "1-pendiente-portal", "4-pendiente-informe_ok", "6-pendiente-cumple",
        "2-cierre-proponer", "4-cierre-evaluar",
        "1-faltante-datos", "3-faltante-compliance"]


def test_el_orden_es_estable_dentro_del_mismo_paso():
    """REQ-147: a igual grupo y paso se conserva el orden en que se armaron."""
    a = A(6, "pendiente", "decidir")
    b = A(6, "pendiente", "no_cumple")
    c = A(6, "pendiente", "cumple")
    assert acciones.ordenar([a, b, c]) == [a, b, c]


def test_req146_mas_de_seis_se_cortan_en_seis_y_el_resto():
    """REQ-146: con 8 líneas se ven 6 y quedan 2 para «ver las 2 restantes», en el mismo orden."""
    todas = acciones.ordenar([A(n, "pendiente", "k") for n in (7, 1, 5, 3, 2, 6, 4, 1)])
    visibles, restantes = acciones.cortar(todas)
    assert len(visibles) == 6 and len(restantes) == 2
    assert visibles + restantes == todas and acciones.TOPE_VISIBLES == 6


def test_req146_hasta_seis_no_tienen_restantes():
    """REQ-146: con 6 o menos no hay «ver las restantes»."""
    for n in (0, 1, 6):
        visibles, restantes = acciones.cortar([A(1, "pendiente", str(i)) for i in range(n)])
        assert len(visibles) == n and restantes == []


def test_lo_vencido_siempre_entra_entre_las_seis():
    """REQ-157: con muchos pendientes, la línea vencida de un paso alto queda entre las visibles."""
    todas = acciones.ordenar([A(1, "pendiente", str(i)) for i in range(9)]
                             + [A(7, "cierre", "dictamen", "vencido")])
    visibles, _ = acciones.cortar(todas)
    assert visibles[0].id == "7-cierre-dictamen"
